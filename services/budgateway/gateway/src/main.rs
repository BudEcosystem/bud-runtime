use axum::extract::{DefaultBodyLimit, Request};
use axum::http::HeaderValue;
use axum::middleware::Next;
use axum::response::Response;
use axum::routing::{any, delete, get, post, put};
use axum::Router;
use clap::Parser;
use mimalloc::MiMalloc;
use std::fmt::Display;
use std::io::ErrorKind;
use std::net::SocketAddr;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tokio::signal;
use tower_http::trace::{DefaultOnFailure, TraceLayer};
use tracing::Level;

use tensorzero_internal::analytics_batcher::AnalyticsBatcher;
use tensorzero_internal::analytics_middleware::{
    analytics_middleware, attach_analytics_batcher_middleware, attach_clickhouse_middleware,
    attach_geoip_middleware, attach_ua_parser_middleware,
};
use tensorzero_internal::auth::{require_api_key, require_api_key_telemetry};
use tensorzero_internal::blocking_middleware::{attach_blocking_manager, blocking_middleware};
use tensorzero_internal::clickhouse::ClickHouseConnectionInfo;
use tensorzero_internal::config_parser::Config;
use tensorzero_internal::endpoints;
use tensorzero_internal::endpoints::status::TENSORZERO_VERSION;
use tensorzero_internal::error;
use tensorzero_internal::gateway_util::{self, AuthenticationInfo};
use tensorzero_internal::observability::{self, LogFormat, RouterExt};
use tensorzero_internal::rate_limit::{
    early_extract::early_model_extraction, middleware::rate_limit_middleware,
};
use tensorzero_internal::usage_limit::usage_limit_middleware;

#[global_allocator]
static GLOBAL: MiMalloc = MiMalloc;

#[derive(Parser, Debug)]
#[command(version, about)]
struct Args {
    /// Use the `tensorzero.toml` config file at the specified path. Incompatible with `--default-config`
    #[arg(long)]
    config_file: Option<PathBuf>,

    /// Use a default config file. Incompatible with `--config-file`
    #[arg(long)]
    default_config: bool,

    // Hidden flag used by our `Dockerfile` to warn users who have not overridden the default CMD
    #[arg(long)]
    #[clap(hide = true)]
    warn_default_cmd: bool,

    /// Sets the log format used for all gateway logs.
    #[arg(long)]
    #[arg(value_enum)]
    #[clap(default_value_t = LogFormat::default())]
    log_format: LogFormat,

    /// Deprecated: use `--config-file` instead
    tensorzero_toml: Option<PathBuf>,
}

async fn add_version_header(request: Request, next: Next) -> Response {
    #[cfg_attr(not(feature = "e2e_tests"), expect(unused_mut))]
    let mut version = HeaderValue::from_static(TENSORZERO_VERSION);

    #[cfg(feature = "e2e_tests")]
    {
        if request
            .headers()
            .contains_key("x-tensorzero-e2e-version-remove")
        {
            tracing::info!("Removing version header due to e2e header");
            return next.run(request).await;
        }
        if let Some(header_version) = request.headers().get("x-tensorzero-e2e-version-override") {
            tracing::info!("Overriding version header with e2e header: {header_version:?}");
            version = header_version.clone();
        }
    }

    let mut response = next.run(request).await;
    response
        .headers_mut()
        .insert("x-tensorzero-gateway-version", version);
    response
}

#[tokio::main]
async fn main() {
    let args = Args::parse();
    // Set up logs and metrics immediately, so that we can use `tracing`.
    // OTLP will be enabled based on the config file
    let delayed_log_config = observability::setup_observability(args.log_format)
        .await
        .expect_pretty("Failed to set up logs");

    let git_sha = tensorzero_internal::built_info::GIT_COMMIT_HASH_SHORT.unwrap_or("unknown");

    tracing::info!("Starting Bud Gateway {TENSORZERO_VERSION} (commit: {git_sha})");

    let metrics_handle = observability::setup_metrics().expect_pretty("Failed to set up metrics");

    if args.warn_default_cmd {
        tracing::warn!("Deprecation Warning: Running gateway from Docker container without overriding default CMD. Please override the command to either `--config-file` to specify a custom configuration file (e.g. `--config-file /path/to/tensorzero.toml`) or `--default-config` to use default settings (i.e. no custom functions, metrics, etc.).");
    }

    if args.tensorzero_toml.is_some() && args.config_file.is_some() {
        tracing::error!("Cannot specify both `--config-file` and a positional path argument");
        std::process::exit(1);
    }

    if args.tensorzero_toml.is_some() {
        tracing::warn!(
            "`Specifying a positional path argument is deprecated. Use `--config-file path/to/tensorzero.toml` instead."
        );
    }

    let config_path = args.config_file.or(args.tensorzero_toml);

    if config_path.is_some() && args.default_config {
        tracing::error!("Cannot specify both `--config-file` and `--default-config`");
        std::process::exit(1);
    }

    if !args.default_config && config_path.is_none() {
        tracing::warn!("Running the gateway without any config-related arguments is deprecated. Use `--default-config` to start the gateway with the default config.");
    }

    let config = if let Some(path) = &config_path {
        Arc::new(
            Config::load_and_verify_from_path(Path::new(&path))
                .await
                .ok() // Don't print the error here, since it was already printed when it was constructed
                .expect_pretty("Failed to load config"),
        )
    } else {
        tracing::warn!("No config file provided, so only default functions will be available. Use `--config-file path/to/tensorzero.toml` to specify a config file.");
        Arc::new(Config::default())
    };

    if config.gateway.debug {
        delayed_log_config
            .delayed_debug_logs
            .enable_debug()
            .expect_pretty("Failed to enable debug logs");
    }

    // Note: We only enable OTLP after config file parsing/loading is complete,
    // so that the config file can control whether OTLP is enabled or not.
    // This means that any tracing spans created before this point will not be exported to OTLP.
    // For now, this is fine, as we only ever export spans for inference/batch/feedback requests,
    // which cannot have occurred up until this point.
    // If we ever want to emit earlier OTLP spans, we'll need to come up with a different way
    // of doing OTLP initialization (e.g. buffer spans, and submit them once we know if OTLP should be enabled).
    // See `build_opentelemetry_layer` for the details of exactly what spans we export.
    if config.gateway.export.otlp.traces.enabled {
        if std::env::var("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT").is_err() {
            // This makes it easier to run the gateway in local development and CI
            if cfg!(feature = "e2e_tests") {
                tracing::warn!("Running without explicit `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` environment variable in e2e tests mode.");
            } else {
                tracing::error!("The `gateway.export.otlp.traces.enabled` configuration option is `true`, but environment variable `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` is not set. Please set it to the OTLP endpoint (e.g. `http://localhost:4317`).");
                std::process::exit(1);
            }
        }

        delayed_log_config
            .delayed_otel
            .enable_otel()
            .expect_pretty("Failed to enable OpenTelemetry");

        tracing::info!("Enabled OpenTelemetry OTLP export");
    }

    // Initialize AppState
    let app_state = gateway_util::AppStateData::new(config.clone())
        .await
        .expect_pretty("Failed to initialize AppState");

    // Setup Redis and rate limiter
    let app_state = gateway_util::setup_redis_and_rate_limiter(app_state, &config)
        .await
        .expect_pretty("Failed to setup Redis and rate limiter");

    // Create a new observability_enabled_pretty string for the log message below
    let observability_enabled_pretty = match &app_state.clickhouse_connection_info {
        ClickHouseConnectionInfo::Disabled => "disabled".to_string(),
        ClickHouseConnectionInfo::Mock { healthy, .. } => {
            format!("mocked (healthy={healthy})")
        }
        ClickHouseConnectionInfo::Production { database, .. } => {
            format!("enabled (database: {database})")
        }
    };

    // Create authentication status string for logging
    let authentication_enabled_pretty = match &app_state.authentication_info {
        AuthenticationInfo::Disabled => "disabled",
        AuthenticationInfo::Enabled(_) => "enabled",
    };

    // Set debug mode
    error::set_debug(config.gateway.debug).expect_pretty("Failed to set debug mode");

    // OpenAI-compatible routes (conditionally authenticated)
    let openai_routes = Router::new()
        .route(
            "/v1/chat/completions",
            post(endpoints::openai_compatible::inference_handler),
        )
        .route(
            "/v1/completions",
            post(endpoints::openai_compatible::completion_handler),
        )
        .route(
            "/v1/messages",
            post(endpoints::openai_compatible::anthropic_messages_handler),
        )
        .route(
            "/v1/embeddings",
            post(endpoints::openai_compatible::embedding_handler),
        )
        .route(
            "/v1/classify",
            post(endpoints::openai_compatible::classify_handler),
        )
        .route("/v1/models", get(endpoints::openai_compatible::list_models))
        .route(
            "/v1/moderations",
            post(endpoints::openai_compatible::moderation_handler),
        )
        .route(
            "/v1/audio/transcriptions",
            post(endpoints::openai_compatible::audio_transcription_handler),
        )
        .route(
            "/v1/audio/translations",
            post(endpoints::openai_compatible::audio_translation_handler),
        )
        .route(
            "/v1/audio/speech",
            post(endpoints::openai_compatible::text_to_speech_handler),
        )
        .route(
            "/v1/images/generations",
            post(endpoints::openai_compatible::image_generation_handler),
        )
        .route(
            "/v1/images/edits",
            post(endpoints::openai_compatible::image_edit_handler),
        )
        .route(
            "/v1/images/variations",
            post(endpoints::openai_compatible::image_variation_handler),
        )
        .route(
            "/v1/documents",
            post(endpoints::openai_compatible::document_processing_handler),
        )
        .route(
            "/v1/realtime/sessions",
            post(endpoints::openai_compatible::realtime_session_handler),
        )
        .route(
            "/v1/realtime/transcription_sessions",
            post(endpoints::openai_compatible::realtime_transcription_session_handler),
        )
        .route(
            "/v1/responses",
            post(endpoints::openai_compatible::response_create_handler),
        )
        .route(
            "/v1/responses/{response_id}",
            get(endpoints::openai_compatible::response_retrieve_handler),
        )
        .route(
            "/v1/responses/{response_id}",
            delete(endpoints::openai_compatible::response_delete_handler),
        )
        .route(
            "/v1/responses/{response_id}/cancel",
            post(endpoints::openai_compatible::response_cancel_handler),
        )
        .route(
            "/v1/responses/{response_id}/input_items",
            get(endpoints::openai_compatible::response_input_items_handler),
        )
        // File management endpoints for OpenAI Batch API
        .route(
            "/v1/files",
            post(endpoints::openai_compatible::file_upload_handler),
        )
        .route(
            "/v1/files/{file_id}",
            get(endpoints::openai_compatible::file_retrieve_handler),
        )
        .route(
            "/v1/files/{file_id}",
            delete(endpoints::openai_compatible::file_delete_handler),
        )
        .route(
            "/v1/files/{file_id}/content",
            get(endpoints::openai_compatible::file_content_handler),
        )
        // Batch management endpoints for OpenAI Batch API
        .route(
            "/v1/batches",
            post(endpoints::openai_compatible::batch_create_handler),
        )
        .route(
            "/v1/batches",
            get(endpoints::openai_compatible::batch_list_handler),
        )
        .route(
            "/v1/batches/{batch_id}",
            get(endpoints::openai_compatible::batch_retrieve_handler),
        )
        .route(
            "/v1/batches/{batch_id}/cancel",
            post(endpoints::openai_compatible::batch_cancel_handler),
        );

    // Apply rate limiting middleware if enabled
    // Note: In Axum, middleware layers run in REVERSE order of application
    let openai_routes = if app_state.is_rate_limiting_enabled() {
        if let Some(ref rate_limiter) = app_state.rate_limiter {
            tracing::info!("Applying rate limiting middleware to OpenAI routes");
            openai_routes.layer(axum::middleware::from_fn_with_state(
                rate_limiter.clone(),
                rate_limit_middleware,
            ))
        } else {
            openai_routes
        }
    } else {
        openai_routes
    };

    // Apply usage limiting middleware if enabled (runs after rate limiting)
    let openai_routes = if let Some(ref usage_limiter) = app_state.usage_limiter {
        if let AuthenticationInfo::Enabled(ref auth) = &app_state.authentication_info {
            tracing::info!("Applying usage limiting middleware to OpenAI routes");
            openai_routes.layer(axum::middleware::from_fn_with_state(
                (auth.clone(), usage_limiter.clone()),
                usage_limit_middleware,
            ))
        } else {
            openai_routes
        }
    } else {
        openai_routes
    };

    // Apply early model extraction layer (runs before rate limiting to avoid double parsing)
    let openai_routes = openai_routes.layer(axum::middleware::from_fn(early_model_extraction));

    // Apply authentication middleware only if authentication is enabled (runs first)
    let openai_routes = match &app_state.authentication_info {
        AuthenticationInfo::Enabled(auth) => openai_routes.layer(
            axum::middleware::from_fn_with_state(auth.clone(), require_api_key),
        ),
        AuthenticationInfo::Disabled => openai_routes,
    };

    // Enable OpenTelemetry tracing for OpenAI-compatible routes
    // This extracts incoming traceparent headers for distributed tracing
    let openai_routes = openai_routes.apply_otel_http_trace_layer();

    // OTLP telemetry proxy routes (conditionally enabled)
    let otlp_routes = if app_state.config.gateway.otlp_proxy.enabled {
        tracing::info!("OTLP proxy routes enabled");
        let routes = Router::new()
            .route(
                "/v1/traces",
                post(endpoints::otlp_proxy::otlp_proxy_handler),
            )
            .route(
                "/v1/metrics",
                post(endpoints::otlp_proxy::otlp_proxy_handler),
            )
            .route(
                "/v1/logs",
                post(endpoints::otlp_proxy::otlp_proxy_handler),
            )
            .layer(DefaultBodyLimit::max(5 * 1024 * 1024)); // 5 MB limit

        let routes = match &app_state.authentication_info {
            AuthenticationInfo::Enabled(auth) => routes.layer(
                axum::middleware::from_fn_with_state(auth.clone(), require_api_key_telemetry),
            ),
            AuthenticationInfo::Disabled => routes,
        };
        Some(routes)
    } else {
        None
    };

    // Routes that don't require authentication
    let public_routes = Router::new()
        .route("/inference", post(endpoints::inference::inference_handler))
        .route(
            "/batch_inference",
            post(endpoints::batch_inference::start_batch_inference_handler),
        )
        .route(
            "/batch_inference/{batch_id}",
            get(endpoints::batch_inference::poll_batch_inference_handler),
        )
        .route(
            "/batch_inference/{batch_id}/inference/{inference_id}",
            get(endpoints::batch_inference::poll_batch_inference_handler),
        )
        .route("/feedback", post(endpoints::feedback::feedback_handler))
        // Everything above this layer has OpenTelemetry tracing enabled
        // Note - we do *not* attach a `OtelInResponseLayer`, as this seems to be incorrect according to the W3C Trace Context spec
        // (the only response header is `traceresponse` for a completed trace)
        .apply_otel_http_trace_layer()
        // Everything below the Otel layers does not have OpenTelemetry tracing enabled
        .route(
            "/datasets/{dataset_name}/datapoints/bulk",
            post(endpoints::datasets::bulk_insert_datapoints_handler),
        )
        .route(
            "/datasets/{dataset_name}/datapoints/{datapoint_id}",
            delete(endpoints::datasets::delete_datapoint_handler),
        )
        .route(
            "/datasets/{dataset_name}/datapoints",
            get(endpoints::datasets::list_datapoints_handler),
        )
        .route(
            "/datasets/{dataset_name}/datapoints/{datapoint_id}",
            get(endpoints::datasets::get_datapoint_handler),
        )
        .route(
            "/internal/datasets/{dataset_name}/datapoints",
            post(endpoints::datasets::insert_from_existing_datapoint_handler),
        )
        .route(
            "/internal/datasets/{dataset_name}/datapoints/{datapoint_id}",
            put(endpoints::datasets::update_datapoint_handler),
        )
        .route(
            "/internal/object_storage",
            get(endpoints::object_storage::get_object_handler),
        )
        .route(
            "/dynamic_evaluation_run",
            post(endpoints::dynamic_evaluation_run::dynamic_evaluation_run_handler),
        )
        .route(
            "/dynamic_evaluation_run/{run_id}/episode",
            post(endpoints::dynamic_evaluation_run::dynamic_evaluation_run_episode_handler),
        )
        .route("/status", get(endpoints::status::status_handler))
        .route("/health", get(endpoints::status::health_handler))
        .route(
            "/metrics",
            get(move || std::future::ready(metrics_handle.render())),
        );

    // Use case proxy routes — handles authentication internally
    // because it validates API key project_id against the deployment's project_id,
    // which differs from the standard model-based auth middleware flow.
    let usecase_proxy_routes = Router::new().route(
        "/usecases/{deployment_id}/api/{*rest}",
        any(endpoints::usecase_proxy::usecase_api_proxy_handler),
    );

    let mut router = Router::new()
        .merge(openai_routes);
    // NOTE: OTLP routes are merged AFTER analytics/blocking middleware layers (below)
    // so they bypass analytics_middleware, blocking_middleware, TraceLayer, and the 100MB body limit.
    router = router
        .merge(public_routes)
        .merge(usecase_proxy_routes)
        .fallback(endpoints::fallback::handle_404)
        .layer(axum::middleware::from_fn(add_version_header))
        .layer(DefaultBodyLimit::max(100 * 1024 * 1024)) // increase the default body limit from 2MB to 100MB
        // Note - this is intentionally *not* used by our OTEL exporter (it creates a span without any `http.` or `otel.` fields)
        // This is only used to output request/response information to our logs
        // OTEL exporting is done by the `OtelAxumLayer` above, which is only enabled for certain routes (and includes much more information)
        // We log failed requests messages at 'DEBUG', since we already have our own error-logging code,
        .layer(TraceLayer::new_for_http().on_failure(DefaultOnFailure::new().level(Level::DEBUG)));

    // Apply blocking middleware if enabled (must run AFTER analytics for data access)
    if app_state.config.gateway.blocking.enabled {
        tracing::info!("Gateway blocking rules enabled");

        if let Some(blocking_manager) = app_state.blocking_manager.clone() {
            // Apply blocking enforcement middleware FIRST (so it runs AFTER analytics)
            router = router.layer(axum::middleware::from_fn(blocking_middleware));

            // Attach blocking manager to request extensions (runs before blocking middleware)
            router = router.layer(axum::middleware::from_fn_with_state(
                blocking_manager,
                attach_blocking_manager,
            ));
        } else {
            tracing::warn!("Blocking is enabled but no blocking manager available");
        }
    }

    // Apply analytics middleware if enabled (must run BEFORE blocking to provide data)
    if app_state.config.gateway.analytics.enabled {
        tracing::info!("Gateway analytics enabled");

        // Apply analytics collection middleware (will run before blocking)
        router = router.layer(axum::middleware::from_fn(analytics_middleware));

        // Attach required services to request extensions (run first to provide data)
        if let Some(parser) = app_state.ua_parser.clone() {
            router = router.layer(axum::middleware::from_fn_with_state(
                parser,
                attach_ua_parser_middleware,
            ));
        }

        if let Some(geoip) = app_state.geoip_service.clone() {
            router = router.layer(axum::middleware::from_fn_with_state(
                geoip,
                attach_geoip_middleware,
            ));
        }

        // Initialize and attach analytics batcher for efficient batched ClickHouse writes
        // This reduces individual writes from N to N/500, improving throughput under high load
        if let ClickHouseConnectionInfo::Production { .. } = &app_state.clickhouse_connection_info {
            let batcher =
                AnalyticsBatcher::new(Arc::new(app_state.clickhouse_connection_info.clone()));
            tracing::info!("Analytics batcher initialized (batch_size=500, flush_interval=1000ms)");
            router = router.layer(axum::middleware::from_fn_with_state(
                batcher,
                attach_analytics_batcher_middleware,
            ));
        }

        router = router.layer(axum::middleware::from_fn_with_state(
            Arc::new(app_state.clickhouse_connection_info.clone()),
            attach_clickhouse_middleware,
        ));
    }

    // Merge OTLP proxy routes AFTER analytics/blocking middleware layers.
    // In Axum, .layer() only wraps routes already in the router, so OTLP routes
    // bypass: analytics_middleware (no gateway_analytics spans), blocking_middleware,
    // TraceLayer (no recursive tracing), and the 100MB DefaultBodyLimit (OTLP has its own 5MB limit).
    if let Some(otlp) = otlp_routes {
        router = router.merge(otlp);
    }

    let router = router.with_state(app_state);

    // Bind to the socket address specified in the config, or default to 0.0.0.0:3000
    let bind_address = config
        .gateway
        .bind_address
        .unwrap_or_else(|| SocketAddr::from(([0, 0, 0, 0], 3000)));

    let listener = match tokio::net::TcpListener::bind(bind_address).await {
        Ok(listener) => listener,
        Err(e) if e.kind() == ErrorKind::AddrInUse => {
            tracing::error!(
                "Failed to bind to socket address {bind_address}: {e}. Tip: Ensure no other process is using port {} or try a different port.",
                bind_address.port()
            );
            std::process::exit(1);
        }
        Err(e) => {
            tracing::error!("Failed to bind to socket address {bind_address}: {e}");
            std::process::exit(1);
        }
    };
    // This will give us the chosen port if the user specified a port of 0
    let actual_bind_address = listener
        .local_addr()
        .expect_pretty("Failed to get bind address from listener");

    let config_path_pretty = if let Some(path) = &config_path {
        format!("config file `{}`", path.to_string_lossy())
    } else {
        "no config file".to_string()
    };

    tracing::info!(
        "Bud Gateway is listening on {actual_bind_address} with {config_path_pretty}, observability {observability_enabled_pretty}, and authentication {authentication_enabled_pretty}.",
    );

    axum::serve(listener, router)
        .with_graceful_shutdown(shutdown_signal())
        .await
        .expect_pretty("Failed to start server");
}

pub async fn shutdown_signal() {
    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .expect_pretty("Failed to install Ctrl+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect_pretty("Failed to install SIGTERM handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    #[cfg(unix)]
    let hangup = async {
        signal::unix::signal(signal::unix::SignalKind::hangup())
            .expect_pretty("Failed to install SIGHUP handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let hangup = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {
            tracing::info!("Received Ctrl+C signal");
        }
        _ = terminate => {
            tracing::info!("Received SIGTERM signal");
        }
        _ = hangup => {
            tokio::time::sleep(std::time::Duration::from_secs(1)).await;
            tracing::info!("Received SIGHUP signal");
        }
    };
}

/// ┌──────────────────────────────────────────────────────────────────────────┐
/// │                           MAIN.RS ESCAPE HATCH                           │
/// └──────────────────────────────────────────────────────────────────────────┘
///
/// We don't allow panic, escape, unwrap, or similar methods in the codebase,
/// except for the private `expect_pretty` method, which is to be used only in
/// main.rs during initialization. After initialization, we expect all code to
/// handle errors gracefully.
///
/// We use `expect_pretty` for better DX when handling errors in main.rs.
/// `expect_pretty` will print an error message and exit with a status code of 1.
trait ExpectPretty<T> {
    fn expect_pretty(self, msg: &str) -> T;
}

impl<T, E: Display> ExpectPretty<T> for Result<T, E> {
    fn expect_pretty(self, msg: &str) -> T {
        match self {
            Ok(value) => value,
            Err(err) => {
                tracing::error!("{msg}: {err}");
                std::process::exit(1);
            }
        }
    }
}

impl<T> ExpectPretty<T> for Option<T> {
    fn expect_pretty(self, msg: &str) -> T {
        match self {
            Some(value) => value,
            None => {
                tracing::error!("{msg}");
                std::process::exit(1);
            }
        }
    }
}
