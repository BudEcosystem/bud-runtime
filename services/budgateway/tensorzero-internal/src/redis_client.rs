use std::collections::HashMap;
use std::sync::Arc;

use futures::StreamExt;
use redis::aio::MultiplexedConnection;
use redis::AsyncCommands;
use secrecy::SecretString;
use tracing::instrument;

use crate::auth::{APIConfig, ApiKeyMetadata, Auth, PublishedModelInfo};
use crate::config_parser::ProviderTypesConfig;
use crate::encryption::{decrypt_api_key, is_decryption_enabled, load_private_key};
use crate::error::{Error, ErrorDetails};
use crate::gateway_util::AppStateData;
use crate::model::{ModelTable, UninitializedModelConfig};

const MODEL_TABLE_KEY_PREFIX: &str = "model_table:";
const API_KEY_KEY_PREFIX: &str = "api_key:";
const PUBLISHED_MODEL_INFO_KEY: &str = "published_model_info";
const GUARDRAIL_KEY_PREFIX: &str = "guardrail_table:";

pub struct RedisClient {
    pub(crate) client: redis::Client,
    conn: MultiplexedConnection,
    app_state: AppStateData,
    auth: Auth,
}

impl RedisClient {
    pub async fn new(url: &str, app_state: AppStateData, auth: Auth) -> Result<Self, Error> {
        let (client, conn) = Self::init_conn(url).await.map_err(|e| {
            tracing::error!("Failed to connect to Redis: {e}");
            Error::new(ErrorDetails::InternalError {
                message: format!("Redis connection failed: {e}"),
            })
        })?;
        Ok(Self {
            client,
            conn,
            app_state,
            auth,
        })
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
        uninitialized_config.load(guardrail_id)
    }

    async fn handle_set_key_event(
        key: &str,
        conn: &mut MultiplexedConnection,
        app_state: &AppStateData,
        auth: &Auth,
    ) -> Result<(), Error> {
        match key {
            k if k.starts_with(API_KEY_KEY_PREFIX) => {
                let value = conn.get::<_, String>(key).await.map_err(|e| {
                    Error::new(ErrorDetails::Config {
                        message: format!("Failed to get value for key {key} from Redis: {e}"),
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
                let value = conn.get::<_, String>(key).await.map_err(|e| {
                    Error::new(ErrorDetails::Config {
                        message: format!("Failed to get value for key {key} from Redis: {e}"),
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
                let value = conn.get::<_, String>(key).await.map_err(|e| {
                    Error::new(ErrorDetails::Config {
                        message: format!("Failed to get value for key {key} from Redis: {e}"),
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
                let value = conn.get::<_, String>(key).await.map_err(|e| {
                    Error::new(ErrorDetails::Config {
                        message: format!("Failed to get value for key {key} from Redis: {e}"),
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
            k if k.starts_with("usage_limit:") => {
                // Usage limit keys are handled by other components, ignore silently
            }
            _ => {
                tracing::info!("Received message from unknown key pattern: {key}");
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
                app_state.remove_guardrail(guardrail_id).await;
                tracing::info!("Deleted guardrail: {guardrail_id}");
            }
            k if k.starts_with("usage_limit:") => {
                // Usage limit keys are handled by other components, ignore silently
            }
            _ => {
                tracing::info!("Received message from unknown key pattern: {key}");
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

        // Get a connection for pubsub
        let mut pubsub_conn = self.client.get_async_pubsub().await.map_err(|e| {
            Error::new(ErrorDetails::Config {
                message: format!("Failed to connect to redis: {e}"),
            })
        })?;

        pubsub_conn
            .psubscribe("__keyevent@*__:set")
            .await
            .map_err(|e| {
                Error::new(ErrorDetails::Config {
                    message: format!("Failed to subscribe to redis: {e}"),
                })
            })?;

        pubsub_conn
            .psubscribe("__keyevent@*__:del")
            .await
            .map_err(|e| {
                Error::new(ErrorDetails::Config {
                    message: format!("Failed to subscribe to redis: {e}"),
                })
            })?;

        pubsub_conn
            .psubscribe("__keyevent@*__:expired")
            .await
            .map_err(|e| {
                Error::new(ErrorDetails::Config {
                    message: format!("Failed to subscribe to redis: {e}"),
                })
            })?;

        // Subscribe to usage limit update channels

        let app_state = self.app_state.clone();
        let auth = self.auth.clone();
        let mut conn = self.conn.clone();

        tokio::spawn(async move {
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
                            Self::handle_del_key_event(payload.as_str(), &app_state, &auth).await
                        {
                            tracing::error!("Failed to handle del key event: {e}");
                        }
                    }
                    c if c.ends_with("__:expired") => {
                        if let Err(e) =
                            Self::handle_del_key_event(payload.as_str(), &app_state, &auth).await
                        {
                            tracing::error!("Failed to handle expired key event: {e}");
                        }
                    }

                    _ => {
                        tracing::warn!("Received message from unknown channel: {channel}");
                    }
                }
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
