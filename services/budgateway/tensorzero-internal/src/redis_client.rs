use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;

use futures::StreamExt;
use redis::aio::MultiplexedConnection;
use redis::AsyncCommands;
use secrecy::SecretString;
use tracing::instrument;
use url::Url;

use crate::auth::{APIConfig, ApiKeyMetadata, Auth, PublishedModelInfo};
use crate::config_parser::ProviderTypesConfig;
use crate::encryption::{decrypt_api_key, is_decryption_enabled, load_private_key};
use crate::endpoints::inference::InferenceCredentials;
use crate::error::{Error, ErrorDetails};
use crate::gateway_util::AppStateData;
use crate::guardrail::build_bud_sentinel_profile;
use crate::guardrail_table::GuardrailConfig;
use crate::inference::providers::bud_sentinel::BudSentinelProvider;
use crate::model::{CredentialLocation, ModelTable, UninitializedModelConfig};

const MODEL_TABLE_KEY_PREFIX: &str = "model_table:";
const API_KEY_KEY_PREFIX: &str = "api_key:";
const PUBLISHED_MODEL_INFO_KEY: &str = "published_model_info";
const GUARDRAIL_KEY_PREFIX: &str = "guardrail_table:";
const BLOCKING_RULES_KEY_PREFIX: &str = "blocking_rules:";
const DEFAULT_CONFIG_GET_RETRIES: u32 = 3;

pub struct RedisClient {
    pub(crate) client: redis::Client,
    conn: MultiplexedConnection,
    app_state: AppStateData,
    auth: Auth,
    db_number: u32,
}

impl RedisClient {
    pub async fn new(url: &str, app_state: AppStateData, auth: Auth) -> Result<Self, Error> {
        let (client, conn) = Self::init_conn(url).await.map_err(|e| {
            tracing::error!("Failed to connect to Redis: {e}");
            Error::new(ErrorDetails::InternalError {
                message: format!("Redis connection failed: {e}"),
            })
        })?;

        // Extract database number from URL (e.g., redis://host:port/2 -> 2)
        let db_number = Self::extract_db_from_url(url);

        Ok(Self {
            client,
            conn,
            app_state,
            auth,
            db_number,
        })
    }

    /// Extract the database number from a Redis URL.
    /// Returns 0 if no database is specified or if parsing fails.
    fn extract_db_from_url(url: &str) -> u32 {
        // Parse URL and extract the path component (database number)
        // Format: redis://[user:pass@]host:port[/db]
        if let Ok(parsed) = Url::parse(url) {
            let path = parsed.path().trim_start_matches('/');
            if !path.is_empty() {
                if let Ok(db) = path.parse::<u32>() {
                    return db;
                }
            }
        }
        0 // Default to database 0
    }

    /// Retry a Redis GET operation with exponential backoff to handle race conditions
    /// where SET events arrive before the value is fully committed
    async fn get_with_retry<T: redis::FromRedisValue>(
        conn: &mut MultiplexedConnection,
        key: &str,
        max_retries: u32,
    ) -> Result<T, redis::RedisError> {
        let mut delay_ms = 10;

        for attempt in 0..max_retries {
            if let Ok(value) = conn.get::<_, T>(key).await {
                return Ok(value);
            }

            tracing::debug!(
                "Redis GET failed for key '{}' (attempt {}/{}), retrying in {}ms",
                key,
                attempt + 1,
                max_retries + 1,
                delay_ms
            );
            tokio::time::sleep(tokio::time::Duration::from_millis(delay_ms)).await;
            delay_ms *= 2; // Exponential backoff: 10ms, 20ms, 40ms
        }

        // Final attempt
        conn.get::<_, T>(key).await
    }

    async fn init_conn(url: &str) -> Result<(redis::Client, MultiplexedConnection), Error> {
        let client = redis::Client::open(url).map_err(|e| {
            Error::new(ErrorDetails::Config {
                message: format!("Failed to create Redis client: {e}"),
            })
        })?;
        let conn = client
            .get_multiplexed_async_connection()
            .await
            .map_err(|e| {
                Error::new(ErrorDetails::Config {
                    message: format!("Failed to get Redis connection: {e}"),
                })
            })?;

        Ok((client, conn))
    }

    async fn parse_models(
        json: &str,
        provider_types: &ProviderTypesConfig,
        app_state: &AppStateData,
    ) -> Result<ModelTable, Error> {
        // First parse as generic JSON to extract API keys
        let mut json_value: serde_json::Value = serde_json::from_str(json).map_err(|e| {
            Error::new(ErrorDetails::Config {
                message: format!("Failed to parse models JSON from redis: {e}"),
            })
        })?;

        let mut models = HashMap::new();
        let mut api_keys_to_store = HashMap::new();

        // Load RSA private key if decryption is enabled
        let private_key = if is_decryption_enabled() {
            load_private_key()?
        } else {
            None
        };

        // Process each model
        if let serde_json::Value::Object(ref mut models_map) = json_value {
            // First pass: collect API keys and remove them
            for (model_name, model_value) in models_map.iter_mut() {
                // Extract api_key if present
                if let serde_json::Value::Object(ref mut model_obj) = model_value {
                    if let Some(serde_json::Value::String(key_string)) = model_obj.remove("api_key")
                    {
                        let decrypted_key = if let Some(ref pk) = private_key {
                            // Decrypt the key using RSA
                            decrypt_api_key(pk, &key_string)?
                        } else {
                            // No decryption configured, use the key as-is
                            SecretString::from(key_string)
                        };

                        let credential_key = format!("store_{model_name}");
                        api_keys_to_store.insert(credential_key, decrypted_key);
                    }
                }
            }

            // Now parse each model individually by taking ownership of each entry
            for (name, model_value) in std::mem::take(models_map) {
                let config: UninitializedModelConfig = serde_json::from_value(model_value)
                    .map_err(|e| {
                        Error::new(ErrorDetails::Config {
                            message: format!("Failed to parse model '{name}' from redis: {e}"),
                        })
                    })?;

                let loaded_config = config.load(&name, provider_types)?;
                models.insert(Arc::<str>::from(name), loaded_config);
            }
        } else {
            return Err(Error::new(ErrorDetails::Config {
                message: "Expected JSON object for models".to_string(),
            }));
        }

        // Store API keys in the credential store
        if !api_keys_to_store.is_empty() {
            if let Ok(mut credential_store) = app_state.model_credential_store.write() {
                for (key, secret) in api_keys_to_store {
                    credential_store.insert(key, secret);
                }
            } else {
                tracing::error!("Failed to acquire credential store write lock (poisoned) when storing API keys");
                return Err(Error::new(ErrorDetails::InternalError {
                    message: "Credential store lock is poisoned".to_string(),
                }));
            }
        }

        models.try_into().map_err(|e| {
            Error::new(ErrorDetails::Config {
                message: format!("Failed to load models: {e}"),
            })
        })
    }

    async fn parse_api_keys(
        json: &str,
    ) -> Result<(APIConfig, Option<crate::auth::AuthMetadata>), Error> {
        // Parse as generic JSON first to extract metadata
        let json_value: serde_json::Value = serde_json::from_str(json).map_err(|e| {
            Error::new(ErrorDetails::Config {
                message: format!("Failed to parse API keys JSON from redis: {e}"),
            })
        })?;

        let mut api_config = APIConfig::new();
        let mut auth_metadata = None;

        if let serde_json::Value::Object(mut obj) = json_value {
            // Extract __metadata__ if present
            if let Some(metadata_value) = obj.remove("__metadata__") {
                auth_metadata = serde_json::from_value(metadata_value).ok();
            }

            // Parse the remaining fields as ApiKeyMetadata and add to APIConfig
            for (key, value) in obj {
                if let Ok(metadata) = serde_json::from_value::<ApiKeyMetadata>(value) {
                    api_config.insert(key, metadata);
                }
            }
        }

        Ok((api_config, auth_metadata))
    }

    async fn parse_published_model_info(json: &str) -> Result<PublishedModelInfo, Error> {
        serde_json::from_str(json).map_err(|e| {
            Error::new(ErrorDetails::Config {
                message: format!("Failed to parse published model info from redis: {e}"),
            })
        })
    }

    async fn parse_guardrail(
        json: &str,
        guardrail_id: &str,
        app_state: &AppStateData,
    ) -> Result<crate::guardrail_table::GuardrailConfig, Error> {
        use crate::guardrail_table::UninitializedGuardrailConfig;

        // First parse as generic JSON to extract API keys
        let mut json_value: serde_json::Value = serde_json::from_str(json).map_err(|e| {
            Error::new(ErrorDetails::Config {
                message: format!("Failed to parse guardrail JSON from redis: {e}"),
            })
        })?;

        let mut api_key_to_store = None;

        // Load RSA private key if decryption is enabled
        let private_key = if is_decryption_enabled() {
            load_private_key()?
        } else {
            None
        };

        // The guardrail data is stored as {profile_id: data}, so we need to extract the data
        let mut guardrail_data = if let serde_json::Value::Object(ref mut wrapper) = json_value {
            // Get the guardrail data from the wrapper object
            if let Some(data) = wrapper.remove(guardrail_id) {
                data
            } else {
                // If the guardrail_id key doesn't exist, try to use the first (and should be only) entry
                if wrapper.len() == 1 {
                    let (_, data) = wrapper.iter_mut().next().unwrap();
                    data.take()
                } else {
                    return Err(Error::new(ErrorDetails::Config {
                        message: format!(
                            "Expected guardrail data for '{}' in redis JSON",
                            guardrail_id
                        ),
                    }));
                }
            }
        } else {
            json_value
        };

        // Extract api_key if present
        if let serde_json::Value::Object(ref mut obj) = guardrail_data {
            if let Some(serde_json::Value::String(key_string)) = obj.remove("api_key") {
                let decrypted_key = if let Some(ref pk) = private_key {
                    // Decrypt the key using RSA
                    decrypt_api_key(pk, &key_string)?
                } else {
                    // No decryption configured, use the key as-is
                    SecretString::from(key_string)
                };

                let credential_key = format!("store_{guardrail_id}");
                api_key_to_store = Some((credential_key, decrypted_key));
            }
        }

        // Parse the guardrail configuration
        let uninitialized_config: UninitializedGuardrailConfig =
            serde_json::from_value(guardrail_data).map_err(|e| {
                Error::new(ErrorDetails::Config {
                    message: format!(
                        "Failed to parse guardrail '{}' from redis: {e}",
                        guardrail_id
                    ),
                })
            })?;

        // Store API key in the credential store if present
        if let Some((key, secret)) = api_key_to_store {
            if let Ok(mut credential_store) = app_state.model_credential_store.write() {
                credential_store.insert(key, secret);
            } else {
                tracing::error!("Failed to acquire credential store write lock (poisoned) when storing guardrail API key");
                return Err(Error::new(ErrorDetails::InternalError {
                    message: "Credential store lock is poisoned".to_string(),
                }));
            }
        }

        // Load the configuration
        let mut config = uninitialized_config.load(guardrail_id)?;
        Self::sync_bud_sentinel_profiles(guardrail_id, &mut config, app_state).await?;
        Ok(config)
    }

    fn collect_credentials(app_state: &AppStateData) -> Result<InferenceCredentials, Error> {
        let credential_store = app_state.model_credential_store.read().map_err(|_| {
            Error::new(ErrorDetails::InternalError {
                message: "Credential store lock is poisoned".to_string(),
            })
        })?;

        let mut credentials = InferenceCredentials::default();
        for (key, value) in credential_store.iter() {
            credentials.insert(key.clone(), value.clone());
        }

        Ok(credentials)
    }

    async fn sync_bud_sentinel_profiles(
        guardrail_id: &str,
        config: &mut GuardrailConfig,
        app_state: &AppStateData,
    ) -> Result<(), Error> {
        if !config
            .providers
            .iter()
            .any(|provider| provider.provider_type == "bud_sentinel")
        {
            return Ok(());
        }

        let credentials = Self::collect_credentials(app_state)?;

        for provider in &mut config.providers {
            if provider.provider_type != "bud_sentinel" {
                continue;
            }

            let provider_config_snapshot = provider
                .provider_config
                .as_object()
                .ok_or_else(|| Error::new(ErrorDetails::Config {
                    message: format!(
                        "Bud Sentinel provider configuration for guardrail '{guardrail_id}' must be a JSON object"
                    ),
                }))?
                .clone();

            let endpoint = provider_config_snapshot
                .get("endpoint")
                .and_then(|v| v.as_str())
                .ok_or_else(|| {
                    Error::new(ErrorDetails::Config {
                        message: format!(
                            "Missing 'endpoint' for Bud Sentinel provider in guardrail '{guardrail_id}'"
                        ),
                    })
                })?
                .to_string();

            let api_key_location = provider_config_snapshot
                .get("api_key_location")
                .cloned()
                .and_then(|value| serde_json::from_value::<CredentialLocation>(value).ok());

            let provider_severity = provider_config_snapshot
                .get("severity_threshold")
                .and_then(|v| v.as_f64())
                .map(|v| v as f32);

            let mut profile = build_bud_sentinel_profile(
                guardrail_id,
                config.severity_threshold,
                &provider.enabled_probes,
                &provider.enabled_rules,
                &provider_config_snapshot,
            )?;

            let endpoint_url = Url::parse(&endpoint).map_err(|e| {
                Error::new(ErrorDetails::Config {
                    message: format!(
                        "Invalid Bud Sentinel endpoint '{endpoint}' for guardrail '{guardrail_id}': {e}"
                    ),
                })
            })?;

            let sentinel_provider = BudSentinelProvider::new(
                endpoint_url,
                api_key_location.clone(),
                Some(profile.id.clone()),
                provider_severity,
            )?;

            let mut sync_pending = false;
            let ensured_profile = {
                let mut attempt = 0usize;
                let mut backoff = Duration::from_millis(100);

                loop {
                    match sentinel_provider
                        .ensure_profile(profile.clone(), &credentials)
                        .await
                    {
                        Ok(p) => break Ok(p),
                        Err(err) => {
                            attempt += 1;
                            let err_display = err.to_string();
                            if attempt >= 3 {
                                break Err(err);
                            }
                            tracing::warn!(
                                guardrail_id,
                                attempt,
                                error = err_display.as_str(),
                                "Bud Sentinel profile sync attempt {attempt} failed; retrying"
                            );
                            tokio::time::sleep(backoff).await;
                            backoff = (backoff * 2).min(Duration::from_secs(2));
                        }
                    }
                }
            };

            match ensured_profile {
                Ok(updated_profile) => {
                    profile = updated_profile;
                    tracing::info!(
                        guardrail_id,
                        profile_id = profile.id,
                        "Bud Sentinel profile synchronized"
                    );
                }
                Err(err) => {
                    sync_pending = true;
                    tracing::warn!(
                        guardrail_id,
                        profile_id = profile.id,
                        "Unable to synchronize Bud Sentinel profile; guardrail will retry lazily: {err}"
                    );
                }
            }

            let config_obj = provider
                .provider_config
                .as_object_mut()
                .ok_or_else(|| Error::new(ErrorDetails::Config {
                    message: format!(
                        "Bud Sentinel provider configuration for guardrail '{guardrail_id}' must be a JSON object"
                    ),
                }))?;

            config_obj.insert(
                "profile_id".to_string(),
                serde_json::Value::String(profile.id.clone()),
            );

            if let Some(threshold) = profile.severity_threshold {
                if let Some(number) = serde_json::Number::from_f64(threshold as f64) {
                    config_obj.insert(
                        "severity_threshold".to_string(),
                        serde_json::Value::Number(number),
                    );
                }
            }

            config_obj.insert(
                "strategy_id".to_string(),
                serde_json::Value::String(profile.strategy_id.clone()),
            );
            config_obj.insert(
                "description".to_string(),
                serde_json::Value::String(profile.description.clone()),
            );
            config_obj.insert(
                "version".to_string(),
                serde_json::Value::String(profile.version.clone()),
            );
            config_obj.insert(
                "metadata_json".to_string(),
                serde_json::Value::String(profile.metadata_json.clone()),
            );
            config_obj.insert(
                "rule_overrides_json".to_string(),
                serde_json::Value::String(profile.rule_overrides_json.clone()),
            );
            config_obj.insert(
                "profile_sync_pending".to_string(),
                serde_json::Value::Bool(sync_pending),
            );
        }

        Ok(())
    }

    async fn delete_bud_sentinel_profiles(
        guardrail_id: &str,
        app_state: &AppStateData,
    ) -> Result<(), Error> {
        let guardrails = app_state.guardrails.read().await;
        let Some(config) = guardrails.get(guardrail_id).cloned() else {
            return Ok(());
        };
        drop(guardrails);

        let credentials = Self::collect_credentials(app_state)?;

        for provider in &config.providers {
            if provider.provider_type != "bud_sentinel" {
                continue;
            }

            let config_obj = provider.provider_config.as_object().ok_or_else(|| {
                Error::new(ErrorDetails::Config {
                    message: format!(
                        "Bud Sentinel provider configuration for guardrail '{guardrail_id}' must be a JSON object"
                    ),
                })
            })?;

            let endpoint = config_obj
                .get("endpoint")
                .and_then(|v| v.as_str())
                .ok_or_else(|| {
                    Error::new(ErrorDetails::Config {
                        message: format!(
                        "Missing 'endpoint' for Bud Sentinel provider in guardrail '{guardrail_id}'"
                    ),
                    })
                })?
                .to_string();

            let api_key_location = config_obj
                .get("api_key_location")
                .cloned()
                .and_then(|value| serde_json::from_value::<CredentialLocation>(value).ok());

            let Some(profile_id) = config_obj
                .get("profile_id")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string())
            else {
                continue;
            };

            let endpoint_url = Url::parse(&endpoint).map_err(|e| {
                Error::new(ErrorDetails::Config {
                    message: format!(
                        "Invalid Bud Sentinel endpoint '{endpoint}' for guardrail '{guardrail_id}': {e}"
                    ),
                })
            })?;

            let provider_instance = BudSentinelProvider::new(
                endpoint_url,
                api_key_location.clone(),
                Some(profile_id.clone()),
                None,
            )?;

            if let Err(e) = provider_instance
                .delete_profile(&profile_id, &credentials)
                .await
            {
                tracing::warn!(
                    guardrail_id,
                    profile_id,
                    "Failed to delete Bud Sentinel profile during guardrail removal: {e}"
                );
            }
        }

        Ok(())
    }

    async fn handle_set_key_event(
        key: &str,
        conn: &mut MultiplexedConnection,
        app_state: &AppStateData,
        auth: &Auth,
    ) -> Result<(), Error> {
        match key {
            k if k.starts_with(API_KEY_KEY_PREFIX) => {
                let value = Self::get_with_retry::<String>(conn, key, DEFAULT_CONFIG_GET_RETRIES)
                    .await
                    .map_err(|e| {
                        Error::new(ErrorDetails::Config {
                            message: format!(
                                "Failed to get value for key {key} from Redis after retries: {e}"
                            ),
                        })
                    })?;

                match Self::parse_api_keys(&value).await {
                    Ok((api_config, metadata)) => {
                        // Extract the actual API key from Redis key format "api_key:actual_key"
                        let actual_api_key = key.strip_prefix(API_KEY_KEY_PREFIX).unwrap_or(key);

                        // Update the API configuration for this key
                        auth.update_api_keys(actual_api_key, api_config);

                        // Update auth metadata if present
                        if let Some(auth_meta) = metadata {
                            auth.update_auth_metadata(actual_api_key, auth_meta);
                        }
                    }
                    Err(e) => {
                        tracing::error!("Failed to parse API keys from redis (key: {key}): {e}")
                    }
                }
            }
            k if k.starts_with(MODEL_TABLE_KEY_PREFIX) => {
                let value = Self::get_with_retry::<String>(conn, key, DEFAULT_CONFIG_GET_RETRIES)
                    .await
                    .map_err(|e| {
                        Error::new(ErrorDetails::Config {
                            message: format!(
                                "Failed to get value for key {key} from Redis after retries: {e}"
                            ),
                        })
                    })?;

                match Self::parse_models(&value, &app_state.config.provider_types, app_state).await
                {
                    Ok(models) => {
                        // Publish rate limit config updates for models that have rate limits
                        Self::publish_rate_limit_updates(&models, app_state).await;
                        app_state.update_model_table(models).await;
                    }
                    Err(e) => {
                        tracing::error!("Failed to parse models from redis (key: {key}): {e}")
                    }
                }
            }
            k if k == PUBLISHED_MODEL_INFO_KEY => {
                let value = Self::get_with_retry::<String>(conn, key, DEFAULT_CONFIG_GET_RETRIES)
                    .await
                    .map_err(|e| {
                        Error::new(ErrorDetails::Config {
                            message: format!(
                                "Failed to get value for key {key} from Redis after retries: {e}"
                            ),
                        })
                    })?;

                match Self::parse_published_model_info(&value).await {
                    Ok(model_info) => {
                        auth.update_published_model_info(model_info);
                        tracing::debug!("Updated published model info");
                    }
                    Err(e) => {
                        tracing::error!("Failed to parse published model info from redis: {e}")
                    }
                }
            }
            k if k.starts_with(GUARDRAIL_KEY_PREFIX) => {
                let value = Self::get_with_retry::<String>(conn, key, DEFAULT_CONFIG_GET_RETRIES)
                    .await
                    .map_err(|e| {
                        Error::new(ErrorDetails::Config {
                            message: format!(
                                "Failed to get value for key {key} from Redis after retries: {e}"
                            ),
                        })
                    })?;

                // Extract the guardrail ID from Redis key format "guardrail_table:id"
                let guardrail_id = key.strip_prefix(GUARDRAIL_KEY_PREFIX).unwrap_or(key);

                match Self::parse_guardrail(&value, guardrail_id, app_state).await {
                    Ok(config) => {
                        app_state
                            .update_guardrail(guardrail_id, Arc::new(config))
                            .await;
                        tracing::debug!("Updated guardrail config: {guardrail_id}");
                    }
                    Err(e) => {
                        tracing::error!("Failed to parse guardrail from redis (key: {key}): {e}")
                    }
                }
            }
            k if k.starts_with(BLOCKING_RULES_KEY_PREFIX) => {
                // Blocking rules updated - invalidate cache and reload
                let key_suffix = key
                    .strip_prefix(BLOCKING_RULES_KEY_PREFIX)
                    .unwrap_or("global");

                if let Some(ref blocking_manager) = app_state.blocking_manager {
                    tracing::info!(
                        "Blocking rules updated in Redis (key: {}), invalidating cache",
                        key
                    );
                    blocking_manager
                        .invalidate_and_reload(Some(key_suffix))
                        .await;
                } else {
                    tracing::warn!(
                        "Blocking rules updated but no blocking manager configured: {}",
                        key
                    );
                }
            }
            k if k.starts_with("usage_limit:") => {
                // Usage limit keys are handled by other components, ignore silently
            }
            _ => {
                tracing::debug!("Ignoring unhandled Redis key: {}", key);
            }
        }

        Ok(())
    }

    async fn handle_del_key_event(
        key: &str,
        app_state: &AppStateData,
        auth: &Auth,
    ) -> Result<(), Error> {
        match key {
            k if k.starts_with(API_KEY_KEY_PREFIX) => {
                if let Some(api_key) = key.rsplit(':').next() {
                    auth.delete_api_key(api_key);
                } else {
                    tracing::error!("Invalid API key format: {key}");
                }
                tracing::info!("Deleted API key");
            }
            k if k.starts_with(MODEL_TABLE_KEY_PREFIX) => {
                if let Some(model_name) = key.rsplit(':').next() {
                    // Publish rate limit deletion if rate limiting is enabled
                    if app_state.is_rate_limiting_enabled() {
                        if let Some(rate_limiter) = &app_state.rate_limiter {
                            if let Err(e) =
                                crate::rate_limit::DistributedRateLimiter::publish_config_update(
                                    &rate_limiter.redis_client,
                                    model_name,
                                    "delete",
                                    None,
                                )
                                .await
                            {
                                tracing::warn!(
                                    "Failed to publish rate limit config deletion for model {}: {}",
                                    model_name,
                                    e
                                );
                            } else {
                                tracing::debug!(
                                    "Published rate limit config deletion for model: {}",
                                    model_name
                                );
                            }
                        }
                    }

                    app_state.remove_model_table(model_name).await;
                } else {
                    tracing::error!("Invalid model table key format: {key}");
                }
                tracing::info!("Deleted model table: {key}");
            }
            k if k == PUBLISHED_MODEL_INFO_KEY => {
                auth.clear_published_model_info();
                tracing::debug!("Cleared published model info");
            }
            k if k.starts_with(GUARDRAIL_KEY_PREFIX) => {
                let guardrail_id = key.strip_prefix(GUARDRAIL_KEY_PREFIX).unwrap_or(key);
                if let Err(e) = Self::delete_bud_sentinel_profiles(guardrail_id, app_state).await {
                    tracing::warn!(
                        guardrail_id,
                        "Failed to clean up Bud Sentinel profile for guardrail removal: {e}"
                    );
                }
                app_state.remove_guardrail(guardrail_id).await;
                tracing::info!("Deleted guardrail: {guardrail_id}");
            }
            k if k.starts_with(BLOCKING_RULES_KEY_PREFIX) => {
                // Blocking rules deleted - clear cache
                let key_suffix = key
                    .strip_prefix(BLOCKING_RULES_KEY_PREFIX)
                    .unwrap_or("global");

                if let Some(ref blocking_manager) = app_state.blocking_manager {
                    tracing::info!(
                        "Blocking rules deleted in Redis (key: {}), clearing cache",
                        key
                    );
                    blocking_manager.clear_rules_cache(Some(key_suffix)).await;
                } else {
                    tracing::debug!(
                        "Blocking rules deleted but no blocking manager configured: {}",
                        key
                    );
                }
            }
            k if k.starts_with("usage_limit:") => {
                // Usage limit keys are handled by other components, ignore silently
            }
            _ => {
                tracing::debug!("Received message from unknown key pattern: {key}");
            }
        }

        Ok(())
    }

    /// Get a connection for rate limiting operations
    pub async fn get_connection(&self) -> Result<MultiplexedConnection, redis::RedisError> {
        self.client.get_multiplexed_async_connection().await
    }

    /// Publish rate limit configuration updates for models with rate limits
    async fn publish_rate_limit_updates(models: &ModelTable, app_state: &AppStateData) {
        // Only publish if rate limiting is enabled
        if !app_state.is_rate_limiting_enabled() {
            return;
        }

        if let Some(rate_limiter) = &app_state.rate_limiter {
            for (model_name, model_config) in models.iter() {
                if let Some(rate_config) = &model_config.rate_limits {
                    // Publish configuration update
                    if let Err(e) =
                        crate::rate_limit::DistributedRateLimiter::publish_config_update(
                            &rate_limiter.redis_client,
                            model_name,
                            "update",
                            Some(rate_config.clone()),
                        )
                        .await
                    {
                        tracing::warn!(
                            "Failed to publish rate limit config update for model {}: {}",
                            model_name,
                            e
                        );
                    } else {
                        tracing::debug!(
                            "Published rate limit config update for model: {}",
                            model_name
                        );
                    }
                }
            }
        }
    }

    #[instrument(skip(self))]
    pub async fn start(mut self) -> Result<(), Error> {
        // Initial fetch: fetch all model_table:* and api_key:* keys
        // Fetch all model_table:* keys
        if let Ok(model_keys) = self
            .conn
            .keys::<_, Vec<String>>(format!("{MODEL_TABLE_KEY_PREFIX}*"))
            .await
        {
            for key in model_keys {
                if let Ok(json) = self.conn.get::<_, String>(&key).await {
                    match Self::parse_models(&json, &self.app_state.config.provider_types, &self.app_state).await {
                        Ok(models) => {
                            // Publish rate limit config updates for models that have rate limits
                            Self::publish_rate_limit_updates(&models, &self.app_state).await;
                            self.app_state.update_model_table(models).await;
                        }
                        Err(e) => tracing::error!(
                            "Failed to parse initial model table from redis (key: {key}): {e} -> data in redis -> {json:?}"
                        ),
                    }
                }
            }
        }
        // Fetch all api_key:* keys
        if let Ok(api_keys_keys) = self
            .conn
            .keys::<_, Vec<String>>(format!("{API_KEY_KEY_PREFIX}*"))
            .await
        {
            for key in api_keys_keys {
                if let Ok(json) = self.conn.get::<_, String>(&key).await {
                    match Self::parse_api_keys(&json).await {
                        Ok((api_config, metadata)) => {
                            // Extract the actual API key from Redis key format "api_key:actual_key"
                            let actual_api_key =
                                key.strip_prefix(API_KEY_KEY_PREFIX).unwrap_or(&key);

                            // Update the API configuration for this key
                            self.auth.update_api_keys(actual_api_key, api_config);

                            // Update auth metadata if present
                            if let Some(auth_meta) = metadata {
                                self.auth.update_auth_metadata(actual_api_key, auth_meta);
                            }
                        }
                        Err(e) => tracing::error!(
                            "Failed to parse initial api keys from redis (key: {key}): {e}"
                        ),
                    }
                }
            }
        }

        // Fetch the published_model_info key
        if let Ok(json) = self.conn.get::<_, String>(PUBLISHED_MODEL_INFO_KEY).await {
            match Self::parse_published_model_info(&json).await {
                Ok(model_info) => {
                    self.auth.update_published_model_info(model_info);
                    tracing::debug!("Loaded initial published model info");
                }
                Err(e) => {
                    tracing::error!("Failed to parse initial published model info from redis: {e}")
                }
            }
        }

        // Fetch all guardrail:* keys
        if let Ok(guardrail_keys) = self
            .conn
            .keys::<_, Vec<String>>(format!("{GUARDRAIL_KEY_PREFIX}*"))
            .await
        {
            for key in guardrail_keys {
                if let Ok(json) = self.conn.get::<_, String>(&key).await {
                    let guardrail_id = key.strip_prefix(GUARDRAIL_KEY_PREFIX).unwrap_or(&key);
                    match Self::parse_guardrail(&json, guardrail_id, &self.app_state).await {
                        Ok(config) => {
                            self.app_state
                                .update_guardrail(guardrail_id, Arc::new(config))
                                .await;
                        }
                        Err(e) => tracing::error!(
                            "Failed to parse initial guardrail from redis (key: {key}): {e}"
                        ),
                    }
                }
            }
        }

        // Clone data for the pub-sub reconnection loop
        let client = self.client.clone();
        let app_state = self.app_state.clone();
        let auth = self.auth.clone();
        let db_number = self.db_number;

        // Spawn pub-sub event loop with automatic reconnection
        tokio::spawn(async move {
            let mut backoff_seconds = 1;
            let max_backoff_seconds = 60;

            loop {
                tracing::info!("Establishing Redis pub-sub connection...");

                // Acquire fresh multiplexed connection for GET operations
                let mut conn = match client.get_multiplexed_async_connection().await {
                    Ok(c) => {
                        tracing::debug!("Redis multiplexed connection acquired for GET operations");
                        c
                    }
                    Err(e) => {
                        tracing::error!(
                            "Failed to get Redis multiplexed connection: {}, retrying in {}s",
                            e,
                            backoff_seconds
                        );
                        tokio::time::sleep(tokio::time::Duration::from_secs(backoff_seconds)).await;
                        backoff_seconds = (backoff_seconds * 2).min(max_backoff_seconds);
                        continue;
                    }
                };

                // Attempt to create pub-sub connection
                let pubsub_result = client.get_async_pubsub().await;
                let mut pubsub_conn = match pubsub_result {
                    Ok(conn) => {
                        tracing::info!("Redis pub-sub connection established");
                        backoff_seconds = 1; // Reset backoff on successful connection
                        conn
                    }
                    Err(e) => {
                        tracing::error!(
                            "Failed to create Redis pub-sub connection: {}, retrying in {}s",
                            e,
                            backoff_seconds
                        );
                        tokio::time::sleep(tokio::time::Duration::from_secs(backoff_seconds)).await;
                        backoff_seconds = (backoff_seconds * 2).min(max_backoff_seconds);
                        continue;
                    }
                };

                // Subscribe to keyspace events for the specific database
                // Note: We subscribe to specific database patterns because some Redis
                // implementations (like Valkey) may not properly deliver events when
                // using wildcard patterns with PSUBSCRIBE.
                let patterns = vec![
                    format!("__keyevent@{db_number}__:set"),
                    format!("__keyevent@{db_number}__:del"),
                    format!("__keyevent@{db_number}__:expired"),
                ];
                let mut all_subscribed = true;
                for pattern in &patterns {
                    if let Err(e) = pubsub_conn.psubscribe(pattern.as_str()).await {
                        tracing::error!(
                            "Failed to subscribe to Redis '{}' events: {}, reconnecting in {}s",
                            pattern,
                            e,
                            backoff_seconds
                        );
                        tokio::time::sleep(tokio::time::Duration::from_secs(backoff_seconds)).await;
                        backoff_seconds = (backoff_seconds * 2).min(max_backoff_seconds);
                        all_subscribed = false;
                        break;
                    }
                }
                if !all_subscribed {
                    continue;
                }

                tracing::info!(
                    "Successfully subscribed to Redis keyspace events for database {}",
                    db_number
                );

                // Process events until stream ends
                let mut stream = pubsub_conn.on_message();
                while let Some(msg) = stream.next().await {
                    let channel: String = msg.get_channel_name().to_string();

                    let payload: String = match msg.get_payload() {
                        Ok(p) => p,
                        Err(e) => {
                            tracing::error!("Failed to decode redis message: {e}");
                            continue;
                        }
                    };

                    // Log at debug level to avoid noise; redact api_key values to prevent credential exposure
                    let redacted_key = if payload.starts_with(API_KEY_KEY_PREFIX) {
                        format!("{}[REDACTED]", API_KEY_KEY_PREFIX)
                    } else {
                        payload.clone()
                    };
                    tracing::debug!(
                        "Received Redis pub/sub message on channel: {}, key: {}",
                        channel,
                        redacted_key
                    );

                    match channel.as_str() {
                        c if c.ends_with("__:set") => {
                            if let Err(e) = Self::handle_set_key_event(
                                payload.as_str(),
                                &mut conn,
                                &app_state,
                                &auth,
                            )
                            .await
                            {
                                tracing::error!("Failed to handle set key event: {e}");
                            }
                        }
                        c if c.ends_with("__:del") => {
                            if let Err(e) =
                                Self::handle_del_key_event(payload.as_str(), &app_state, &auth)
                                    .await
                            {
                                tracing::error!("Failed to handle del key event: {e}");
                            }
                        }
                        c if c.ends_with("__:expired") => {
                            if let Err(e) =
                                Self::handle_del_key_event(payload.as_str(), &app_state, &auth)
                                    .await
                            {
                                tracing::error!("Failed to handle expired key event: {e}");
                            }
                        }

                        _ => {
                            tracing::warn!("Received message from unknown channel: {channel}");
                        }
                    }
                }

                // Stream ended - this could be due to connection loss
                tracing::warn!(
                    "Redis pub-sub stream ended, reconnecting in {}s",
                    backoff_seconds
                );
                tokio::time::sleep(tokio::time::Duration::from_secs(backoff_seconds)).await;
                backoff_seconds = (backoff_seconds * 2).min(max_backoff_seconds);
            }
        });

        Ok(())
    }
}

#[cfg(all(test, feature = "e2e_tests"))]
mod tests {
    use super::*;
    use crate::config_parser::{Config, ProviderTypesConfig};
    use crate::gateway_util::AppStateData;
    use std::sync::Arc;

    #[tokio::test]
    async fn test_parse_models_with_api_key() {
        // Create a mock AppStateData with credential store
        let config = Arc::new(Config::default());
        let app_state = AppStateData::new(config).await.unwrap();

        // JSON with model containing api_key
        let json = r#"{
            "test-model": {
                "routing": ["dummy"],
                "endpoints": ["chat"],
                "providers": {
                    "dummy": {
                        "type": "dummy",
                        "model_name": "gpt-4"
                    }
                },
                "api_key": "sk-test-key-12345"
            }
        }"#;

        let provider_types = ProviderTypesConfig::default();

        // Parse models
        let result = RedisClient::parse_models(json, &provider_types, &app_state).await;
        assert!(result.is_ok());

        // Verify API key was stored
        let store = app_state.model_credential_store.read().unwrap(); // Test code can panic
        assert!(store.contains_key("store_test-model"));
        assert_eq!(store.len(), 1);
    }

    #[tokio::test]
    async fn test_parse_real_world_model_with_api_key() {
        // Test with the exact JSON structure from the error log
        let config = Arc::new(Config::default());
        let app_state = AppStateData::new(config).await.unwrap();

        let json = r#"{
            "f5b083f4-c4eb-4fa7-b190-1002a65b1326": {
                "routing": ["openai"],
                "providers": {
                    "openai": {
                        "type": "openai",
                        "model_name": "model-6ae7c295-908d-4529-bd68-bd1fc8fa48c3-1752985696",
                        "api_key_location": "dynamic::store_f5b083f4-c4eb-4fa7-b190-1002a65b1326"
                    }
                },
                "endpoints": ["embedding"],
                "api_key": "sk-test-12345-example-api-key-for-testing-purposes-only"
            }
        }"#;

        let provider_types = ProviderTypesConfig::default();

        // Parse models
        let result = RedisClient::parse_models(json, &provider_types, &app_state).await;
        if let Err(e) = &result {
            tracing::error!("Parse error: {e}");
        }
        assert!(result.is_ok(), "Failed to parse real-world model JSON");

        // Verify API key was stored
        let store = app_state.model_credential_store.read().unwrap(); // Test code can panic
        assert!(store.contains_key("store_f5b083f4-c4eb-4fa7-b190-1002a65b1326"));
        assert_eq!(store.len(), 1);
    }

    #[tokio::test]
    async fn test_parse_models_without_api_key() {
        let config = Arc::new(Config::default());
        let app_state = AppStateData::new(config).await.unwrap();

        // JSON without api_key field
        let json = r#"{
            "test-model": {
                "routing": ["dummy"],
                "endpoints": ["chat"],
                "providers": {
                    "dummy": {
                        "type": "dummy",
                        "model_name": "gpt-4"
                    }
                }
            }
        }"#;

        let provider_types = ProviderTypesConfig::default();

        // Parse models
        let result = RedisClient::parse_models(json, &provider_types, &app_state).await;
        if let Err(e) = &result {
            tracing::error!("Parse error: {e}");
        }
        assert!(result.is_ok());

        // Verify no API key was stored
        let store = app_state.model_credential_store.read().unwrap(); // Test code can panic
        assert!(store.is_empty());
    }

    #[tokio::test]
    async fn test_parse_multiple_models_with_mixed_api_keys() {
        let config = Arc::new(Config::default());
        let app_state = AppStateData::new(config).await.unwrap();

        // JSON with multiple models, some with API keys
        let json = r#"{
            "model-with-key": {
                "routing": ["dummy"],
                "endpoints": ["chat"],
                "providers": {
                    "dummy": {
                        "type": "dummy",
                        "model_name": "gpt-4",
                        "api_key_location": "dynamic::store_model-with-key"
                    }
                },
                "api_key": "sk-test-key-12345"
            },
            "model-without-key": {
                "routing": ["dummy"],
                "endpoints": ["chat"],
                "providers": {
                    "dummy": {
                        "type": "dummy",
                        "model_name": "gpt-3.5-turbo"
                    }
                }
            },
            "another-model-with-key": {
                "routing": ["dummy"],
                "endpoints": ["chat"],
                "providers": {
                    "dummy": {
                        "type": "dummy",
                        "model_name": "claude-3-sonnet",
                        "api_key_location": "dynamic::store_another-model-with-key"
                    }
                },
                "api_key": "sk-ant-test-67890"
            }
        }"#;

        let provider_types = ProviderTypesConfig::default();

        // Parse models
        let result = RedisClient::parse_models(json, &provider_types, &app_state).await;
        if let Err(e) = &result {
            tracing::error!("Parse error in test_parse_multiple_models_with_mixed_api_keys: {e}");
        }
        assert!(result.is_ok());

        // Verify correct API keys were stored
        let store = app_state.model_credential_store.read().unwrap(); // Test code can panic
        assert_eq!(store.len(), 2);
        assert!(store.contains_key("store_model-with-key"));
        assert!(store.contains_key("store_another-model-with-key"));
        assert!(!store.contains_key("store_model-without-key"));
    }

    #[tokio::test]
    async fn test_parse_model_with_encrypted_api_key() {
        use base64::{engine::general_purpose::STANDARD as BASE64, Engine as _};
        use rsa::pkcs1::EncodeRsaPrivateKey;
        use rsa::{Pkcs1v15Encrypt, RsaPrivateKey, RsaPublicKey};
        use secrecy::ExposeSecret;

        // Generate test RSA key pair
        use rsa::rand_core::OsRng;
        let bits = 2048;
        let private_key = RsaPrivateKey::new(&mut OsRng, bits).expect("failed to generate key");
        let public_key = RsaPublicKey::from(&private_key);

        // Convert private key to PEM format
        let private_key_pem = private_key
            .to_pkcs1_pem(rsa::pkcs1::LineEnding::LF)
            .expect("failed to encode PEM")
            .to_string();

        // Set the private key in environment variable for the test
        std::env::set_var("TENSORZERO_RSA_PRIVATE_KEY", private_key_pem);

        // Create app state
        let config = Arc::new(Config::default());
        let app_state = AppStateData::new(config).await.unwrap();

        // Encrypt test API key
        let test_api_key = "sk-test-encrypted-key-12345";
        let encrypted = public_key
            .encrypt(&mut OsRng, Pkcs1v15Encrypt, test_api_key.as_bytes())
            .expect("encryption failed");
        let encrypted_base64 = BASE64.encode(&encrypted);

        // JSON with encrypted API key
        let json = format!(
            r#"{{
            "model-with-encrypted-key": {{
                "routing": ["dummy"],
                "endpoints": ["chat"],
                "providers": {{
                    "dummy": {{
                        "type": "dummy",
                        "model_name": "gpt-4",
                        "api_key_location": "dynamic::store_model-with-encrypted-key"
                    }}
                }},
                "api_key": "{encrypted_base64}"
            }}
        }}"#
        );

        let provider_types = ProviderTypesConfig::default();

        // Parse models
        let result = RedisClient::parse_models(&json, &provider_types, &app_state).await;
        if let Err(e) = &result {
            tracing::error!("Parse error: {e}");
        }
        assert!(result.is_ok());

        // Verify decrypted API key was stored correctly
        let store = app_state.model_credential_store.read().unwrap(); // Test code can panic
        assert_eq!(store.len(), 1);
        assert!(store.contains_key("store_model-with-encrypted-key"));

        // Verify the decrypted value matches the original
        let stored_key = store.get("store_model-with-encrypted-key").unwrap(); // Test code can panic
        assert_eq!(stored_key.expose_secret(), test_api_key);

        // Clean up
        std::env::remove_var("TENSORZERO_RSA_PRIVATE_KEY");
    }

    #[tokio::test]
    async fn test_parse_guardrail_with_wrapper() {
        // Create a mock AppStateData
        let config = Arc::new(Config::default());
        let app_state = AppStateData::new(config).await.unwrap();

        let guardrail_id = "3ef707ff-ca1d-413a-8807-e5c8bb819c43";

        // JSON with guardrail data wrapped in {profile_id: data} format
        let json = format!(
            r#"{{
            "{}": {{
                "name": "oai_omni_moderation_guardrail",
                "providers": {{
                    "openai": {{
                        "type": "openai",
                        "probe_config": {{"omni-moderation-latest": ["harassment", "hate"]}},
                        "api_key_location": "dynamic::store_{}"
                    }}
                }},
                "severity_threshold": 0.75,
                "guard_types": ["input"],
                "api_key": "sk-test-guardrail-key-12345"
            }}
        }}"#,
            guardrail_id, guardrail_id
        );

        // Parse guardrail
        let result = RedisClient::parse_guardrail(&json, guardrail_id, &app_state).await;
        assert!(
            result.is_ok(),
            "Failed to parse guardrail with wrapper format"
        );

        // Verify API key was stored
        let store = app_state.model_credential_store.read().unwrap();
        assert!(store.contains_key(&format!("store_{}", guardrail_id)));
        assert_eq!(store.len(), 1);
    }
}
