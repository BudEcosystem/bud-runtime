use std::collections::HashMap;
use std::future::IntoFuture;
use std::net::SocketAddr;
use std::path::Path;
use std::sync::Arc;
use uaparser::UserAgentParser;

use axum::extract::{rejection::JsonRejection, FromRequest, Json, Request};
use axum::routing::post;
use axum::Router;
use reqwest::{Client, Proxy};
use secrecy::SecretString;
use serde::de::DeserializeOwned;
use tokio::sync::oneshot::Sender;
use tracing::instrument;

use crate::auth::Auth;
use crate::blocking_rules::BlockingRulesManager;
use crate::clickhouse::migration_manager;
use crate::clickhouse::ClickHouseConnectionInfo;
use crate::config_parser::Config;
use crate::endpoints;
use crate::error::{Error, ErrorDetails};
use crate::geoip::GeoIpService;
use crate::guardrail_table::GuardrailTable;
use crate::kafka::KafkaConnectionInfo;
use crate::model::ModelTable;
use crate::rate_limit::DistributedRateLimiter;
use crate::redis_client::RedisClient;
use crate::usage_limit::{UsageLimiter, UsageLimiterConfig};

/// Represents the authentication state of the gateway
#[derive(Clone)]
pub enum AuthenticationInfo {
    Enabled(Auth),
    Disabled,
}

/// State for the API
#[derive(Clone)]
pub struct AppStateData {
    pub config: Arc<Config<'static>>,
    pub http_client: Client,
    pub clickhouse_connection_info: ClickHouseConnectionInfo,
    pub kafka_connection_info: KafkaConnectionInfo,
    pub authentication_info: AuthenticationInfo,
    pub model_credential_store: Arc<std::sync::RwLock<HashMap<String, SecretString>>>,
    pub rate_limiter: Option<Arc<DistributedRateLimiter>>,
    pub usage_limiter: Option<Arc<UsageLimiter>>,
    pub geoip_service: Option<Arc<GeoIpService>>,
    pub ua_parser: Option<Arc<UserAgentParser>>,
    pub blocking_manager: Option<Arc<BlockingRulesManager>>,
    pub guardrails: Arc<tokio::sync::RwLock<GuardrailTable>>,
}
pub type AppState = axum::extract::State<AppStateData>;

impl AppStateData {
    pub async fn new(config: Arc<Config<'static>>) -> Result<Self, Error> {
        let clickhouse_url = std::env::var("TENSORZERO_CLICKHOUSE_URL")
            .ok()
            .or_else(|| {
                std::env::var("CLICKHOUSE_URL").ok().inspect(|_| {
                    tracing::warn!("Deprecation Warning: The environment variable \"CLICKHOUSE_URL\" has been renamed to \"TENSORZERO_CLICKHOUSE_URL\" and will be removed in a future version. Please update your environment to use \"TENSORZERO_CLICKHOUSE_URL\" instead.");
                })
            });
        let state = Self::new_with_clickhouse(config, clickhouse_url).await?;
        Ok(state)
    }

    async fn new_with_clickhouse(
        config: Arc<Config<'static>>,
        clickhouse_url: Option<String>,
    ) -> Result<Self, Error> {
        let clickhouse_connection_info = setup_clickhouse(&config, clickhouse_url, false).await?;
        let kafka_connection_info = setup_kafka(&config).await?;
        let http_client = setup_http_client()?;
        let authentication_info = setup_authentication(&config);

        // Initialize analytics services if enabled
        let (geoip_service, ua_parser) = if config.gateway.analytics.enabled {
            let geoip = config
                .gateway
                .analytics
                .geoip_db_path
                .as_ref()
                .map(|path| Arc::new(GeoIpService::new(Some(path))));

            let parser = match UserAgentParser::from_bytes(include_bytes!("../regexes.yaml")) {
                Ok(p) => Some(Arc::new(p)),
                Err(e) => {
                    tracing::warn!("Failed to initialize user agent parser: {}", e);
                    None
                }
            };

            (geoip, parser)
        } else {
            (None, None)
        };

        Ok(Self {
            config,
            http_client,
            clickhouse_connection_info,
            kafka_connection_info,
            authentication_info,
            model_credential_store: Arc::new(std::sync::RwLock::new(HashMap::new())),
            rate_limiter: None,  // Will be initialized later with Redis client
            usage_limiter: None, // Will be initialized later with Redis client
            geoip_service,
            ua_parser,
            blocking_manager: None, // Will be initialized later with Redis client
            guardrails: Arc::new(tokio::sync::RwLock::new(HashMap::new())),
        })
    }
    pub async fn update_model_table(&self, mut new_models: ModelTable) {
        let mut models = self.config.models.write().await;

        for (name, config) in std::mem::take(&mut *new_models).into_iter() {
            models.insert(name, config);
        }

        // Sync rate limiter configurations if rate limiting is enabled
        if let Some(rate_limiter) = &self.rate_limiter {
            rate_limiter.sync_from_model_table(&models);
        }
    }

    pub async fn remove_model_table(&self, model_name: &str) {
        let mut models = self.config.models.write().await;
        models.remove(model_name);

        // Remove rate limiter configuration if it exists
        if let Some(rate_limiter) = &self.rate_limiter {
            rate_limiter.remove_model_config(model_name);
        }

        // Also remove associated credential if it exists
        let credential_key = format!("store_{model_name}");
        if let Ok(mut credential_store) = self.model_credential_store.write() {
            credential_store.remove(&credential_key);
        } else {
            tracing::error!(
                "Failed to acquire credential store write lock (poisoned) when removing model {}",
                model_name
            );
        }
    }

    /// Update guardrail configuration
    pub async fn update_guardrail(
        &self,
        guardrail_id: &str,
        config: Arc<crate::guardrail_table::GuardrailConfig>,
    ) {
        let mut guardrails = self.guardrails.write().await;
        guardrails.insert(Arc::from(guardrail_id), config);
    }

    /// Remove guardrail configuration
    pub async fn remove_guardrail(&self, guardrail_id: &str) {
        let mut guardrails = self.guardrails.write().await;
        guardrails.remove(guardrail_id);
    }

    /// Create a new instance with rate limiter initialized
    pub fn with_rate_limiter(mut self, rate_limiter: Arc<DistributedRateLimiter>) -> Self {
        self.rate_limiter = Some(rate_limiter);
        self
    }

    /// Create a new instance with usage limiter initialized
    pub fn with_usage_limiter(mut self, usage_limiter: Arc<UsageLimiter>) -> Self {
        self.usage_limiter = Some(usage_limiter);
        self
    }

    /// Check if rate limiting is enabled
    pub fn is_rate_limiting_enabled(&self) -> bool {
        // Rate limiting is enabled if we have both a rate limiter and global config enables it
        if let Some(global_config) = &self.config.gateway.rate_limits {
            global_config.enabled && self.rate_limiter.is_some()
        } else {
            false
        }
    }
}

pub async fn setup_clickhouse(
    config: &Config<'static>,
    clickhouse_url: Option<String>,
    embedded_client: bool,
) -> Result<ClickHouseConnectionInfo, Error> {
    let clickhouse_connection_info = match (config.gateway.observability.enabled, clickhouse_url) {
        // Observability disabled by config
        (Some(false), _) => {
            tracing::info!("Disabling observability: `gateway.observability.enabled` is set to false in config.");
            ClickHouseConnectionInfo::new_disabled()
        }
        // Observability enabled but no ClickHouse URL
        (Some(true), None) => {
            return Err(ErrorDetails::AppState {
                message: "Missing environment variable TENSORZERO_CLICKHOUSE_URL".to_string(),
            }
            .into())
        }
        // Observability enabled and ClickHouse URL provided
        (Some(true), Some(clickhouse_url)) => {
            ClickHouseConnectionInfo::new(&clickhouse_url).await?
        }
        // Observability default and no ClickHouse URL
        (None, None) => {
            let msg_suffix = if embedded_client {
                "`clickhouse_url` was not provided."
            } else {
                "`TENSORZERO_CLICKHOUSE_URL` is not set."
            };
            tracing::warn!("Disabling observability: `gateway.observability.enabled` is not explicitly specified in config and {msg_suffix}");
            ClickHouseConnectionInfo::new_disabled()
        }
        // Observability default and ClickHouse URL provided
        (None, Some(clickhouse_url)) => ClickHouseConnectionInfo::new(&clickhouse_url).await?,
    };

    // Run ClickHouse migrations (if any) if we have a production ClickHouse connection
    if let ClickHouseConnectionInfo::Production { .. } = &clickhouse_connection_info {
        migration_manager::run(&clickhouse_connection_info).await?;
    }
    Ok(clickhouse_connection_info)
}

pub async fn setup_kafka(config: &Config<'static>) -> Result<KafkaConnectionInfo, Error> {
    let kafka_config = config.gateway.observability.kafka.as_ref();

    match kafka_config {
        Some(kafka_conf) if kafka_conf.enabled => {
            tracing::info!(
                "Initializing Kafka producer with brokers: {}",
                kafka_conf.brokers
            );
            match KafkaConnectionInfo::new(Some(kafka_conf)) {
                Ok(conn) => {
                    tracing::info!("Successfully initialized Kafka producer");

                    // Start the background flush task for the buffer
                    if let Some(handle) = conn.start_flush_task() {
                        // Store the handle to prevent it from being dropped
                        // In a production system, you might want to store this handle
                        // for graceful shutdown
                        tokio::spawn(async move {
                            handle.await.ok();
                        });
                        tracing::info!("Started Kafka buffer flush task");
                    }

                    Ok(conn)
                }
                Err(e) => {
                    tracing::error!("Failed to initialize Kafka producer: {}", e);
                    // Return error since Kafka is explicitly enabled
                    Err(e)
                }
            }
        }
        _ => {
            tracing::info!("Kafka integration is disabled");
            Ok(KafkaConnectionInfo::Disabled)
        }
    }
}

pub fn setup_authentication(config: &Config<'static>) -> AuthenticationInfo {
    match config.gateway.authentication.enabled {
        Some(false) => {
            tracing::info!("Authentication explicitly disabled via configuration");
            AuthenticationInfo::Disabled
        }
        Some(true) | None => {
            if config.api_keys.is_empty() && config.gateway.authentication.enabled == Some(true) {
                tracing::warn!("Authentication enabled but no API keys configured");
            }
            AuthenticationInfo::Enabled(Auth::new(config.api_keys.clone()))
        }
    }
}

/// Setup Redis clients and rate limiter based on configuration
pub async fn setup_redis_and_rate_limiter(
    app_state: AppStateData,
    config: &Config<'static>,
) -> Result<AppStateData, Error> {
    // Check if authentication is enabled and requires Redis
    let auth_info = match &app_state.authentication_info {
        AuthenticationInfo::Enabled(auth) => Some(auth.clone()),
        AuthenticationInfo::Disabled => None,
    };

    // Get Redis URL from environment
    let redis_url = std::env::var("TENSORZERO_REDIS_URL").ok();

    // Setup blocking manager first if enabled
    let blocking_manager = if config.gateway.blocking.enabled {
        if let Some(ref url) = redis_url {
            if !url.is_empty() {
                // Create a Redis client for blocking manager operations
                let auth = auth_info
                    .clone()
                    .unwrap_or_else(|| Auth::new(config.api_keys.clone()));
                match RedisClient::new(url, app_state.clone(), auth).await {
                    Ok(redis_client) => {
                        let manager = Arc::new(BlockingRulesManager::new_with_clickhouse(
                            Some(Arc::new(redis_client)),
                            Some(Arc::new(app_state.clickhouse_connection_info.clone())),
                        ));
                        tracing::info!(
                            "Blocking rules manager initialized with ClickHouse logging"
                        );
                        Some(manager)
                    }
                    Err(e) => {
                        tracing::error!(
                            "Failed to create Redis client for blocking manager: {}",
                            e
                        );
                        None
                    }
                }
            } else {
                tracing::warn!("Blocking is enabled but TENSORZERO_REDIS_URL is empty");
                None
            }
        } else {
            tracing::warn!("Blocking is enabled but TENSORZERO_REDIS_URL is not set");
            None
        }
    } else {
        tracing::info!("Blocking is disabled in configuration");
        None
    };

    // Setup Redis client for authentication/models/blocking if needed
    if let Some(auth) = auth_info {
        if let Some(ref url) = redis_url {
            if !url.is_empty() {
                // Create Redis client
                let auth_redis_client = RedisClient::new(url, app_state.clone(), auth.clone())
                    .await
                    .map_err(|e| {
                        Error::new(ErrorDetails::AppState {
                            message: format!(
                                "Failed to create Redis client for authentication: {e}"
                            ),
                        })
                    })?;

                auth_redis_client.start().await.map_err(|e| {
                    Error::new(ErrorDetails::AppState {
                        message: format!("Failed to start Redis client: {e}"),
                    })
                })?;

                tracing::info!(
                    "Redis client started successfully with auth{}",
                    if blocking_manager.is_some() {
                        " and blocking rules"
                    } else {
                        ""
                    }
                );
            } else {
                tracing::warn!("TENSORZERO_REDIS_URL is empty, Redis client will not be started");
            }
        } else {
            tracing::info!("TENSORZERO_REDIS_URL not set, authentication will work without Redis");
        }
    }

    // Setup rate limiter if configured
    let app_state = if let Some(ref global_rate_config) = config.gateway.rate_limits {
        if global_rate_config.enabled {
            if let Some(ref url) = redis_url {
                if !url.is_empty() {
                    match setup_rate_limiter(url, &app_state, config).await {
                        Ok(rate_limiter) => {
                            tracing::info!("Distributed rate limiter initialized successfully");
                            app_state.with_rate_limiter(rate_limiter)
                        }
                        Err(e) => {
                            tracing::error!("Failed to initialize rate limiter: {}", e);
                            app_state
                        }
                    }
                } else {
                    tracing::warn!("Rate limiting is enabled but TENSORZERO_REDIS_URL is empty");
                    app_state
                }
            } else {
                tracing::warn!("Rate limiting is enabled but TENSORZERO_REDIS_URL is not set");
                app_state
            }
        } else {
            tracing::info!("Rate limiting is disabled in configuration");
            app_state
        }
    } else {
        tracing::info!("No rate limiting configuration found");
        app_state
    };

    // Add blocking manager to app_state if it was created
    let app_state = if let Some(manager) = blocking_manager {
        let mut app_state = app_state;
        app_state.blocking_manager = Some(manager);
        app_state
    } else {
        app_state
    };

    // Initialize usage limiter if authentication is enabled
    let app_state = if matches!(
        app_state.authentication_info,
        AuthenticationInfo::Enabled(_)
    ) {
        if let Ok(redis_url_var) = std::env::var("TENSORZERO_REDIS_URL") {
            if !redis_url_var.is_empty() {
                match UsageLimiter::new(redis_url_var.clone(), UsageLimiterConfig::default()).await
                {
                    Ok(usage_limiter) => {
                        tracing::info!("Usage limiter initialized successfully");
                        app_state.with_usage_limiter(Arc::new(usage_limiter))
                    }
                    Err(e) => {
                        tracing::error!("Failed to initialize usage limiter: {}", e);
                        app_state
                    }
                }
            } else {
                tracing::warn!("Authentication is enabled but TENSORZERO_REDIS_URL is empty");
                app_state
            }
        } else {
            tracing::warn!("Authentication is enabled but TENSORZERO_REDIS_URL is not set");
            app_state
        }
    } else {
        tracing::info!("Authentication is disabled, skipping usage limiter initialization");
        app_state
    };

    Ok(app_state)
}

/// Setup the distributed rate limiter with Redis backend
async fn setup_rate_limiter(
    redis_url: &str,
    app_state: &AppStateData,
    config: &Config<'static>,
) -> Result<Arc<DistributedRateLimiter>, Error> {
    tracing::info!("Initializing distributed rate limiter");

    // Create a new Redis client for rate limiting
    let auth = match &app_state.authentication_info {
        AuthenticationInfo::Enabled(auth) => auth.clone(),
        AuthenticationInfo::Disabled => Auth::new(config.api_keys.clone()),
    };

    let rate_limit_redis_client = RedisClient::new(redis_url, app_state.clone(), auth)
        .await
        .map_err(|e| {
            Error::new(ErrorDetails::AppState {
                message: format!("Failed to create Redis client for rate limiting: {e}"),
            })
        })?;

    let rate_limit_redis_client = Arc::new(rate_limit_redis_client);

    // Create the distributed rate limiter
    let rate_limiter = DistributedRateLimiter::new(rate_limit_redis_client)
        .await
        .map_err(|e| {
            Error::new(ErrorDetails::AppState {
                message: format!("Failed to create distributed rate limiter: {e}"),
            })
        })?;

    let rate_limiter = Arc::new(rate_limiter);

    // Load model rate limit configurations
    let models = config.models.read().await;
    for (model_name, model_config) in models.iter() {
        if let Some(model_rate_config) = &model_config.rate_limits {
            rate_limiter.update_model_config(model_name.to_string(), model_rate_config.clone());
            tracing::debug!("Configured rate limits for model {}", model_name);
        }
    }
    drop(models); // Release the read lock

    // Start background sync for distributed rate limiting
    rate_limiter.start_background_sync().await;
    tracing::info!("Started background sync for distributed rate limiting");

    // Start pub/sub listener for dynamic configuration updates
    if let Err(e) = rate_limiter.start_pubsub_listener() {
        tracing::warn!(
            "Failed to start pub/sub listener for rate limit updates: {}",
            e
        );
    }

    Ok(rate_limiter)
}

/// Custom Axum extractor that validates the JSON body and deserializes it into a custom type
///
/// When this extractor is present, we don't check if the `Content-Type` header is `application/json`,
/// and instead simply assume that the request body is a JSON object.
pub struct StructuredJson<T>(pub T);

impl<S, T> FromRequest<S> for StructuredJson<T>
where
    Json<T>: FromRequest<S, Rejection = JsonRejection>,
    S: Send + Sync,
    T: Send + Sync + DeserializeOwned,
{
    type Rejection = Error;

    #[instrument(skip_all, level = "trace", name = "StructuredJson::from_request")]
    async fn from_request(req: Request, state: &S) -> Result<Self, Self::Rejection> {
        // Retrieve the request body as Bytes before deserializing it
        let bytes = bytes::Bytes::from_request(req, state).await.map_err(|e| {
            Error::new(ErrorDetails::JsonRequest {
                message: format!("{} ({})", e, e.status()),
            })
        })?;

        // Convert the entire body into `serde_json::Value`
        let value = Json::<serde_json::Value>::from_bytes(&bytes)
            .map_err(|e| {
                Error::new(ErrorDetails::JsonRequest {
                    message: format!("{} ({})", e, e.status()),
                })
            })?
            .0;

        // Now use `serde_path_to_error::deserialize` to attempt deserialization into `T`
        let deserialized: T = serde_path_to_error::deserialize(&value).map_err(|e| {
            Error::new(ErrorDetails::JsonRequest {
                message: e.to_string(),
            })
        })?;

        Ok(StructuredJson(deserialized))
    }
}

// This is set high enough that it should never be hit for a normal model response.
// In the future, we may want to allow overriding this at the model provider level.
pub const DEFAULT_HTTP_CLIENT_TIMEOUT: std::time::Duration = std::time::Duration::from_secs(20 * 60);

pub fn setup_http_client() -> Result<Client, Error> {
    let mut http_client_builder = Client::builder().timeout(DEFAULT_HTTP_CLIENT_TIMEOUT);

    if cfg!(feature = "e2e_tests") {
        if let Ok(proxy_url) = std::env::var("TENSORZERO_E2E_PROXY") {
            tracing::info!("Using proxy URL from TENSORZERO_E2E_PROXY: {proxy_url}");
            http_client_builder = http_client_builder
                .proxy(Proxy::all(proxy_url).map_err(|e| {
                    Error::new(ErrorDetails::AppState {
                        message: format!("Invalid proxy URL: {e}"),
                    })
                })?)
                // When running e2e tests, we use `provider-proxy` as an MITM proxy
                // for caching, so we need to accept the invalid (self-signed) cert.
                .danger_accept_invalid_certs(true);
        }
    }

    http_client_builder.build().map_err(|e| {
        Error::new(ErrorDetails::AppState {
            message: format!("Failed to build HTTP client: {e}"),
        })
    })
}

pub struct ShutdownHandle {
    #[expect(dead_code)]
    sender: Sender<()>,
}

/// Starts a new HTTP TensorZero gateway on an unused port, with only the openai-compatible endpoint enabled.
/// This is used in by `patch_openai_client` in the Python client to allow pointing the OpenAI client
/// at a local gateway (via `base_url`).
///
/// Returns the address the gateway is listening on, and a future resolves (after the gateway starts up)
/// to a `ShutdownHandle` which shuts down the gateway when dropped.
pub async fn start_openai_compatible_gateway(
    config_file: Option<String>,
    clickhouse_url: Option<String>,
) -> Result<(SocketAddr, ShutdownHandle), Error> {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0")
        .await
        .map_err(|e| {
            Error::new(ErrorDetails::InternalError {
                message: format!("Failed to bind to a port: {e}"),
            })
        })?;
    let bind_addr = listener.local_addr().map_err(|e| {
        Error::new(ErrorDetails::InternalError {
            message: format!("Failed to get local address: {e}"),
        })
    })?;

    let config = if let Some(config_file) = config_file {
        Arc::new(Config::load_and_verify_from_path(Path::new(&config_file)).await?)
    } else {
        Arc::new(Config::default())
    };
    let app_state = AppStateData::new_with_clickhouse(config, clickhouse_url).await?;

    let router = Router::new()
        .route(
            "/openai/v1/chat/completions",
            post(endpoints::openai_compatible::inference_handler),
        )
        .fallback(endpoints::fallback::handle_404)
        .with_state(app_state);

    let (sender, recv) = tokio::sync::oneshot::channel::<()>();
    let shutdown_fut = async move {
        let _ = recv.await;
    };

    tokio::spawn(
        axum::serve(listener, router)
            .with_graceful_shutdown(shutdown_fut)
            .into_future(),
    );
    Ok((bind_addr, ShutdownHandle { sender }))
}

#[cfg(test)]
mod tests {
    use tracing_test::traced_test;

    use super::*;
    use crate::config_parser::{
        AnalyticsConfig, AuthenticationConfig, BlockingConfig, GatewayConfig, ObservabilityConfig,
    };
    use secrecy::SecretString;
    use std::collections::HashMap;
    use std::sync::RwLock;

    #[tokio::test]
    #[traced_test]
    async fn test_setup_clickhouse() {
        // Disabled observability
        let gateway_config = GatewayConfig {
            observability: ObservabilityConfig {
                enabled: Some(false),
                async_writes: false,
                kafka: None,
            },
            authentication: AuthenticationConfig::default(),
            bind_address: None,
            debug: false,
            enable_template_filesystem_access: false,
            export: Default::default(),
            rate_limits: None,
            analytics: AnalyticsConfig {
                enabled: false,
                geoip_db_path: None,
            },
            blocking: BlockingConfig { enabled: false },
        };

        let config = Box::leak(Box::new(Config {
            gateway: gateway_config,
            ..Default::default()
        }));

        let clickhouse_connection_info = setup_clickhouse(config, None, false).await.unwrap();
        assert!(matches!(
            clickhouse_connection_info,
            ClickHouseConnectionInfo::Disabled
        ));
        assert!(!logs_contain(
            "Missing environment variable TENSORZERO_CLICKHOUSE_URL"
        ));

        // Default observability and no ClickHouse URL
        let gateway_config = GatewayConfig {
            observability: ObservabilityConfig {
                enabled: None,
                async_writes: false,
                kafka: None,
            },
            authentication: AuthenticationConfig::default(),
            ..Default::default()
        };
        let config = Box::leak(Box::new(Config {
            gateway: gateway_config,
            ..Default::default()
        }));
        let clickhouse_connection_info = setup_clickhouse(config, None, false).await.unwrap();
        assert!(matches!(
            clickhouse_connection_info,
            ClickHouseConnectionInfo::Disabled
        ));
        assert!(!logs_contain(
            "Missing environment variable TENSORZERO_CLICKHOUSE_URL"
        ));
        assert!(logs_contain("Disabling observability: `gateway.observability.enabled` is not explicitly specified in config and `TENSORZERO_CLICKHOUSE_URL` is not set."));

        // We do not test the case where a ClickHouse URL is provided but observability is default,
        // as this would require a working ClickHouse and we don't have one in unit tests.

        // Observability enabled but ClickHouse URL is missing
        let gateway_config = GatewayConfig {
            observability: ObservabilityConfig {
                enabled: Some(true),
                async_writes: false,
                kafka: None,
            },
            authentication: AuthenticationConfig::default(),
            bind_address: None,
            debug: false,
            enable_template_filesystem_access: false,
            export: Default::default(),
            rate_limits: None,
            analytics: AnalyticsConfig {
                enabled: false,
                geoip_db_path: None,
            },
            blocking: BlockingConfig { enabled: false },
        };

        let config = Box::leak(Box::new(Config {
            gateway: gateway_config,
            ..Default::default()
        }));

        let err = setup_clickhouse(config, None, false).await.unwrap_err();
        assert!(err
            .to_string()
            .contains("Missing environment variable TENSORZERO_CLICKHOUSE_URL"));

        // Bad URL
        let gateway_config = GatewayConfig {
            observability: ObservabilityConfig {
                enabled: Some(true),
                async_writes: false,
                kafka: None,
            },
            authentication: AuthenticationConfig::default(),
            bind_address: None,
            debug: false,
            enable_template_filesystem_access: false,
            export: Default::default(),
            rate_limits: None,
            analytics: AnalyticsConfig {
                enabled: false,
                geoip_db_path: None,
            },
            blocking: BlockingConfig { enabled: false },
        };
        let config = Box::leak(Box::new(Config {
            gateway: gateway_config,
            ..Default::default()
        }));
        setup_clickhouse(config, Some("bad_url".to_string()), false)
            .await
            .expect_err("ClickHouse setup should fail given a bad URL");
        assert!(logs_contain("Invalid ClickHouse database URL"));
    }

    #[test]
    fn test_setup_authentication() {
        // Test explicitly disabled authentication
        let gateway_config = GatewayConfig {
            authentication: AuthenticationConfig {
                enabled: Some(false),
            },
            ..Default::default()
        };
        let config = Config {
            gateway: gateway_config,
            api_keys: HashMap::from([("test_key".to_string(), HashMap::new())]),
            ..Default::default()
        };

        let auth_info = setup_authentication(&config);
        assert!(matches!(auth_info, AuthenticationInfo::Disabled));

        // Test explicitly enabled authentication with API keys
        let gateway_config = GatewayConfig {
            authentication: AuthenticationConfig {
                enabled: Some(true),
            },
            ..Default::default()
        };
        let config = Config {
            gateway: gateway_config,
            api_keys: HashMap::from([("test_key".to_string(), HashMap::new())]),
            ..Default::default()
        };

        let auth_info = setup_authentication(&config);
        assert!(matches!(auth_info, AuthenticationInfo::Enabled(_)));

        // Test explicitly enabled authentication without API keys (should still enable)
        let gateway_config = GatewayConfig {
            authentication: AuthenticationConfig {
                enabled: Some(true),
            },
            ..Default::default()
        };
        let config = Config {
            gateway: gateway_config,
            api_keys: HashMap::new(),
            ..Default::default()
        };

        let auth_info = setup_authentication(&config);
        assert!(matches!(auth_info, AuthenticationInfo::Enabled(_)));

        // Test default authentication (None) with API keys (should enable)
        let gateway_config = GatewayConfig {
            authentication: AuthenticationConfig { enabled: None },
            ..Default::default()
        };
        let config = Config {
            gateway: gateway_config,
            api_keys: HashMap::from([("test_key".to_string(), HashMap::new())]),
            ..Default::default()
        };

        let auth_info = setup_authentication(&config);
        assert!(matches!(auth_info, AuthenticationInfo::Enabled(_)));

        // Test default authentication (None) without API keys (should still enable for backward compatibility)
        let gateway_config = GatewayConfig {
            authentication: AuthenticationConfig { enabled: None },
            ..Default::default()
        };
        let config = Config {
            gateway: gateway_config,
            api_keys: HashMap::new(),
            ..Default::default()
        };

        let auth_info = setup_authentication(&config);
        assert!(matches!(auth_info, AuthenticationInfo::Enabled(_)));
    }

    #[tokio::test]
    #[cfg(feature = "e2e_tests")]
    async fn test_model_credential_store_initialization() {
        let config = Arc::new(Config::default());
        let app_state = AppStateData::new_with_clickhouse(config, None)
            .await
            .unwrap();

        // Verify credential store is initialized empty
        let store = app_state.model_credential_store.read().unwrap(); // Test code can panic
        assert!(store.is_empty());
    }

    #[tokio::test]
    #[cfg(feature = "e2e_tests")]
    async fn test_model_credential_store_operations() {
        let config = Arc::new(Config::default());
        let app_state = AppStateData::new_with_clickhouse(config, None)
            .await
            .unwrap();

        // Add a credential
        {
            let mut store = app_state.model_credential_store.write().unwrap(); // Test code can panic
            store.insert(
                "store_test-model".to_string(),
                SecretString::from("test-api-key"),
            );
        }

        // Verify credential exists
        {
            let store = app_state.model_credential_store.read().unwrap(); // Test code can panic
            assert!(store.contains_key("store_test-model"));
            assert_eq!(store.len(), 1);
        }

        // Remove credential when model is deleted
        app_state.remove_model_table("test-model").await;

        // Verify credential was removed
        {
            let store = app_state.model_credential_store.read().unwrap(); // Test code can panic
            assert!(!store.contains_key("store_test-model"));
            assert!(store.is_empty());
        }
    }

    #[tokio::test]
    async fn test_credential_store_thread_safety() {
        let store = Arc::new(RwLock::new(HashMap::<String, SecretString>::new()));
        let store_clone1 = Arc::clone(&store);
        let store_clone2 = Arc::clone(&store);

        // Spawn multiple tasks to test concurrent access
        let handle1 = tokio::spawn(async move {
            for i in 0..10 {
                let mut s = store_clone1.write().unwrap(); // Test code can panic
                s.insert(
                    format!("key1_{i}"),
                    SecretString::from(format!("value1_{i}")),
                );
            }
        });

        let handle2 = tokio::spawn(async move {
            for i in 0..10 {
                let mut s = store_clone2.write().unwrap(); // Test code can panic
                s.insert(
                    format!("key2_{i}"),
                    SecretString::from(format!("value2_{i}")),
                );
            }
        });

        handle1.await.unwrap();
        handle2.await.unwrap();

        // Verify all keys were inserted
        let final_store = store.read().unwrap(); // Test code can panic
        assert_eq!(final_store.len(), 20);
        for i in 0..10 {
            assert!(final_store.contains_key(&format!("key1_{i}")));
            assert!(final_store.contains_key(&format!("key2_{i}")));
        }
    }

    #[tokio::test]
    #[traced_test]
    async fn test_unhealthy_clickhouse() {
        // Sensible URL that doesn't point to ClickHouse
        let gateway_config = GatewayConfig {
            observability: ObservabilityConfig {
                enabled: Some(true),
                async_writes: false,
                kafka: None,
            },
            authentication: AuthenticationConfig::default(),
            bind_address: None,
            debug: false,
            enable_template_filesystem_access: false,
            export: Default::default(),
            rate_limits: None,
            analytics: AnalyticsConfig {
                enabled: false,
                geoip_db_path: None,
            },
            blocking: BlockingConfig { enabled: false },
        };
        let config = Config {
            gateway: gateway_config,
            ..Default::default()
        };
        setup_clickhouse(
            &config,
            Some("https://tensorzero.invalid:8123".to_string()),
            false,
        )
        .await
        .expect_err("ClickHouse setup should fail given a URL that doesn't point to ClickHouse");
        assert!(logs_contain(
            "Error connecting to ClickHouse: ClickHouse is not healthy"
        ));
        // We do not test the case where a ClickHouse URL is provided and observability is on,
        // as this would require a working ClickHouse and we don't have one in unit tests.
    }
}
