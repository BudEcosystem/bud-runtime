use axum::{
    body::Body,
    extract::Request,
    http::{HeaderMap, Method, StatusCode, Uri, Version},
    middleware::Next,
    response::Response,
};
use chrono::Utc;
use metrics::histogram;
use opentelemetry::trace::Status as OtelStatus;
use std::collections::HashMap;
use std::sync::Arc;
use tracing::error;
use tracing::Instrument;
use tracing_opentelemetry::OpenTelemetrySpanExt;
use uaparser::{Parser, UserAgentParser};
use uuid::Uuid;

use crate::analytics::{GatewayAnalyticsDatabaseInsert, RequestAnalytics};
use crate::analytics_batcher::AnalyticsBatcher;
use crate::baggage::{keys, new_shared_baggage};
use crate::clickhouse::ClickHouseConnectionInfo;
use crate::error::Error;
use crate::geoip::GeoIpService;

/// Wrapper for storing parent span's OTel context in request extensions.
/// This allows auth middleware to add baggage while preserving correct trace hierarchy.
/// Using gateway_analytics.context() gives us the correct trace_id and span_id for parenting.
#[derive(Clone)]
pub struct ParentSpanContext(pub opentelemetry::Context);

/// Middleware for collecting analytics data about gateway requests
pub async fn analytics_middleware(
    headers: HeaderMap,
    method: Method,
    uri: Uri,
    version: Version,
    mut request: Request,
    next: Next,
) -> Result<Response, Error> {
    // Create span and set parent context from incoming headers (distributed tracing)
    let span = tracing::info_span!(
        "gateway_analytics",
        otel.name = "gateway_analytics",
        // Core
        gateway_analytics.id = tracing::field::Empty,
        gateway_analytics.inference_id = tracing::field::Empty,
        // Network
        gateway_analytics.client_ip = tracing::field::Empty,
        gateway_analytics.proxy_chain = tracing::field::Empty,
        gateway_analytics.protocol_version = tracing::field::Empty,
        // GeoIP
        gateway_analytics.country_code = tracing::field::Empty,
        gateway_analytics.country_name = tracing::field::Empty,
        gateway_analytics.region = tracing::field::Empty,
        gateway_analytics.city = tracing::field::Empty,
        gateway_analytics.latitude = tracing::field::Empty,
        gateway_analytics.longitude = tracing::field::Empty,
        gateway_analytics.timezone = tracing::field::Empty,
        gateway_analytics.asn = tracing::field::Empty,
        gateway_analytics.isp = tracing::field::Empty,
        // User Agent
        gateway_analytics.user_agent = tracing::field::Empty,
        gateway_analytics.device_type = tracing::field::Empty,
        gateway_analytics.browser_name = tracing::field::Empty,
        gateway_analytics.browser_version = tracing::field::Empty,
        gateway_analytics.os_name = tracing::field::Empty,
        gateway_analytics.os_version = tracing::field::Empty,
        gateway_analytics.is_bot = tracing::field::Empty,
        // Request
        gateway_analytics.method = tracing::field::Empty,
        gateway_analytics.path = tracing::field::Empty,
        gateway_analytics.query_params = tracing::field::Empty,
        gateway_analytics.request_headers = tracing::field::Empty,
        gateway_analytics.body_size = tracing::field::Empty,
        gateway_analytics.request_timestamp = tracing::field::Empty,
        // Auth
        gateway_analytics.api_key_id = tracing::field::Empty,
        gateway_analytics.auth_method = tracing::field::Empty,
        gateway_analytics.user_id = tracing::field::Empty,
        gateway_analytics.project_id = tracing::field::Empty,
        gateway_analytics.endpoint_id = tracing::field::Empty,
        // Response (post-request)
        gateway_analytics.response_timestamp = tracing::field::Empty,
        gateway_analytics.total_duration_ms = tracing::field::Empty,
        gateway_analytics.gateway_processing_ms = tracing::field::Empty,
        gateway_analytics.status_code = tracing::field::Empty,
        gateway_analytics.response_size = tracing::field::Empty,
        gateway_analytics.response_headers = tracing::field::Empty,
        // Model
        gateway_analytics.model_name = tracing::field::Empty,
        gateway_analytics.model_provider = tracing::field::Empty,
        gateway_analytics.model_version = tracing::field::Empty,
        gateway_analytics.routing_decision = tracing::field::Empty,
        // Usage tokens (for /v1/responses)
        gen_ai.usage.input_tokens = tracing::field::Empty,
        gen_ai.usage.output_tokens = tracing::field::Empty,
        gen_ai.usage.total_tokens = tracing::field::Empty,
        // OpenTelemetry error status
        otel.status_code = tracing::field::Empty,
        otel.status_description = tracing::field::Empty,
        // Error details (from HTTP status)
        gateway_analytics.error_type = tracing::field::Empty,
        gateway_analytics.error_message = tracing::field::Empty,
        // Blocking events (all 17 GatewayBlockingEvents table columns)
        gateway_blocking_events.id = tracing::field::Empty,
        gateway_blocking_events.rule_id = tracing::field::Empty,
        gateway_blocking_events.client_ip = tracing::field::Empty,
        gateway_blocking_events.country_code = tracing::field::Empty,
        gateway_blocking_events.user_agent = tracing::field::Empty,
        gateway_blocking_events.request_path = tracing::field::Empty,
        gateway_blocking_events.request_method = tracing::field::Empty,
        gateway_blocking_events.api_key_id = tracing::field::Empty,
        gateway_blocking_events.project_id = tracing::field::Empty,
        gateway_blocking_events.endpoint_id = tracing::field::Empty,
        gateway_blocking_events.model_name = tracing::field::Empty,
        gateway_blocking_events.rule_type = tracing::field::Empty,
        gateway_blocking_events.rule_name = tracing::field::Empty,
        gateway_blocking_events.rule_priority = tracing::field::Empty,
        gateway_blocking_events.block_reason = tracing::field::Empty,
        gateway_blocking_events.action_taken = tracing::field::Empty,
        gateway_blocking_events.blocked_at = tracing::field::Empty,
        // Tags
        gateway_analytics.tags = tracing::field::Empty,
        // Prompt (for /v1/responses with prompt parameter)
        gateway_analytics.prompt_id = tracing::field::Empty,
        gateway_analytics.prompt_version = tracing::field::Empty,
    );

    // Extract parent context from incoming traceparent/tracestate headers
    let parent_ctx =
        tracing_opentelemetry_instrumentation_sdk::http::extract_context(&headers);

    // Remove AUTH_PROCESSED marker from incoming baggage before setting parent.
    // This prevents BaggageSpanProcessor from setting endpoint_id on gateway_analytics.
    //
    // Why: The incoming baggage may contain AUTH_PROCESSED from an upstream request
    // (e.g., budprompt calling gateway). If we don't remove it, BaggageSpanProcessor
    // would see the marker and set endpoint_id from the CALLER's baggage (wrong value).
    // By removing the marker, BaggageSpanProcessor skips endpoint_id, and we set it
    // correctly after auth resolves the endpoint for THIS request.
    let parent_ctx = crate::baggage::remove_auth_marker_from_context(parent_ctx);
    span.set_parent(parent_ctx);

    // Run all middleware logic inside the span
    async move {
        tracing::debug!("Analytics middleware called for {} {}", method, uri.path());

    // Get services from request extensions
    let geoip_service = request.extensions().get::<Arc<GeoIpService>>().cloned();
    let ua_parser = request.extensions().get::<Arc<UserAgentParser>>().cloned();

    // Create analytics record
    let mut analytics = RequestAnalytics::new();
    let record = &mut analytics.record;

    // Extract basic request information - use headers-only approach for client IP
    record.client_ip = get_client_ip_fallback(&headers);
    record.proxy_chain = extract_proxy_chain(&headers);

    record.protocol_version = format!("{version:?}");
    record.method = method.to_string();
    record.path = uri.path().to_string();
    record.query_params = uri.query().map(|q| q.to_string());

    // Extract user agent
    record.user_agent = headers
        .get("user-agent")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string());

    // Parse user agent for device/browser info
    if let (Some(ua), Some(parser)) = (record.user_agent.clone(), ua_parser.as_ref()) {
        parse_user_agent(&ua, record, parser);
    }

    // Perform GeoIP lookup
    if let Some(geoip) = &geoip_service {
        let client_ip = record.client_ip.clone();
        geoip.enrich_analytics(&client_ip, record);
    }

    // Extract selected request headers
    record.request_headers = extract_important_headers(&headers);

    // Record pre-request span attributes (before processing the request)
    record_pre_request_span_attributes(&tracing::Span::current(), &analytics.record);

    // Store analytics in request extensions
    let analytics_arc = Arc::new(tokio::sync::Mutex::new(analytics));
    request.extensions_mut().insert(analytics_arc.clone());

    // Create shared baggage container for auth middleware to populate
    let baggage_arc = new_shared_baggage();
    request.extensions_mut().insert(baggage_arc.clone());

    // Store gateway_analytics span context for auth middleware to use when adding baggage.
    // This preserves correct trace hierarchy: auth middleware can add baggage to this context
    // and use it with set_parent() on child spans without causing self-referencing.
    let ga_span_ctx = tracing::Span::current().context();
    request.extensions_mut().insert(ParentSpanContext(ga_span_ctx));

    // Get ClickHouse connection before processing request
    let clickhouse_opt = request
        .extensions()
        .get::<Arc<ClickHouseConnectionInfo>>()
        .cloned();

    // Get analytics batcher for batched writes (preferred over direct writes)
    let batcher_opt = request.extensions().get::<AnalyticsBatcher>().cloned();

    tracing::debug!(
        "ClickHouse connection in analytics middleware: {}",
        if clickhouse_opt.is_some() {
            "available"
        } else {
            "not available"
        }
    );

    // Process the request
    let mut response = next.run(request).await;

    // Update analytics with response data
    {
        let mut analytics = analytics_arc.lock().await;

        // Calculate durations
        let elapsed = analytics.start_time.elapsed();
        analytics.record.total_duration_ms = elapsed.as_millis() as u32;
        analytics.record.response_timestamp = Utc::now();

        // Extract response information
        analytics.record.status_code = response.status().as_u16();

        // Extract inference_id from response headers if present
        if let Some(inference_id_header) = response.headers().get("x-tensorzero-inference-id") {
            if let Ok(inference_id_str) = inference_id_header.to_str() {
                if let Ok(inference_id) = Uuid::parse_str(inference_id_str) {
                    analytics.record.inference_id = Some(inference_id);
                    tracing::debug!("Captured inference_id {} for analytics", inference_id);
                }
            }
        }

        // Extract prompt_id from response headers if present (for /v1/responses with prompt)
        if let Some(prompt_id_header) = response.headers().get("x-tensorzero-prompt-id") {
            if let Ok(prompt_id_str) = prompt_id_header.to_str() {
                let span = tracing::Span::current();
                span.record("gateway_analytics.prompt_id", prompt_id_str);
                tracing::debug!("Captured prompt_id {} for analytics", prompt_id_str);
            }
        }

        // Extract prompt_version from response headers if present
        if let Some(prompt_version_header) = response.headers().get("x-tensorzero-prompt-version") {
            if let Ok(prompt_version_str) = prompt_version_header.to_str() {
                let span = tracing::Span::current();
                span.record("gateway_analytics.prompt_version", prompt_version_str);
                tracing::debug!("Captured prompt_version {} for analytics", prompt_version_str);
            }
        }

        // Extract project_id from response headers if present (for /v1/responses)
        if let Some(project_id_header) = response.headers().get("x-tensorzero-project-id") {
            if let Ok(project_id_str) = project_id_header.to_str() {
                let span = tracing::Span::current();
                span.record("gateway_analytics.project_id", project_id_str);
                tracing::debug!(
                    "Captured project_id {} for analytics from response header",
                    project_id_str
                );
            }
        }

        // Extract usage tokens from response headers if present (for /v1/responses)
        if let Some(input_tokens_header) = response.headers().get("x-tensorzero-input-tokens") {
            if let Ok(tokens_str) = input_tokens_header.to_str() {
                if let Ok(tokens) = tokens_str.parse::<i64>() {
                    let span = tracing::Span::current();
                    span.record("gen_ai.usage.input_tokens", tokens);
                    tracing::debug!("Captured input_tokens {} for analytics", tokens);
                }
            }
        }
        if let Some(output_tokens_header) = response.headers().get("x-tensorzero-output-tokens") {
            if let Ok(tokens_str) = output_tokens_header.to_str() {
                if let Ok(tokens) = tokens_str.parse::<i64>() {
                    let span = tracing::Span::current();
                    span.record("gen_ai.usage.output_tokens", tokens);
                    tracing::debug!("Captured output_tokens {} for analytics", tokens);
                }
            }
        }
        if let Some(total_tokens_header) = response.headers().get("x-tensorzero-total-tokens") {
            if let Ok(tokens_str) = total_tokens_header.to_str() {
                if let Ok(tokens) = tokens_str.parse::<i64>() {
                    let span = tracing::Span::current();
                    span.record("gen_ai.usage.total_tokens", tokens);
                    tracing::debug!("Captured total_tokens {} for analytics", tokens);
                }
            }
        }

        // Extract model latency from response headers if present and calculate gateway processing time
        if let Some(model_latency_header) = response.headers().get("x-tensorzero-model-latency-ms")
        {
            if let Ok(model_latency_str) = model_latency_header.to_str() {
                if let Ok(model_latency_ms) = model_latency_str.parse::<u32>() {
                    // Store model latency for metrics
                    analytics.record.model_latency_ms = Some(model_latency_ms);

                    // Gateway processing time = Total duration - Model latency
                    if analytics.record.total_duration_ms >= model_latency_ms {
                        analytics.record.gateway_processing_ms = analytics
                            .record
                            .total_duration_ms
                            .saturating_sub(model_latency_ms);
                    } else {
                        // This shouldn't happen - log a warning for debugging
                        tracing::warn!(
                            "Unexpected: total_duration_ms ({}) < model_latency_ms ({}). Using 0 for gateway processing.",
                            analytics.record.total_duration_ms,
                            model_latency_ms
                        );
                        analytics.record.gateway_processing_ms = 0;
                    }
                    tracing::debug!(
                        "Calculated gateway processing time: {} ms (total: {} ms, model: {} ms)",
                        analytics.record.gateway_processing_ms,
                        analytics.record.total_duration_ms,
                        model_latency_ms
                    );
                }
            }
        }

        // Extract selected response headers
        analytics.record.response_headers = extract_important_headers(response.headers());

        // Extract and record error information if response is an error
        if response.status().is_client_error() || response.status().is_server_error() {
            let span = tracing::Span::current();

            // Error type = canonical reason (e.g., "Bad Request", "Internal Server Error")
            let error_type = response
                .status()
                .canonical_reason()
                .unwrap_or("Unknown Error");
            span.record("gateway_analytics.error_type", error_type);
            analytics.record.error_type = Some(error_type.to_string());

            // Error message = response body JSON (extract body for error details)
            let status = response.status();
            let (parts, body) = response.into_parts();

            // Collect body bytes (limit to 10KB for safety)
            if let Ok(body_bytes) = axum::body::to_bytes(body, 10 * 1024).await {
                if let Ok(body_str) = String::from_utf8(body_bytes.to_vec()) {
                    span.record("gateway_analytics.error_message", body_str.as_str());
                    // Set OTEL span status with error message - this populates StatusCode and StatusMessage columns
                    span.set_status(OtelStatus::error(body_str.clone()));
                    analytics.record.error_message = Some(body_str.clone());

                    // Create OTEL exception event via tracing::error!
                    // Using target: "budgateway_internal::analytics_middleware" to avoid exposing internal module path
                    span.in_scope(|| {
                        tracing::error!(
                            // otel.exception = true, Commenting out cannot use otel.exception with target: due to macro parsing
                            target: "budgateway_internal::analytics_middleware",
                            error_type = %error_type,
                            error_message = %body_str,
                            "Exception: {}", error_type
                        );
                    });
                }
                // Reconstruct response with same body
                response = Response::from_parts(parts, Body::from(body_bytes));
            } else {
                // Fallback if body extraction fails - reconstruct with empty body
                response = Response::from_parts(parts, Body::empty());
                let error_msg = format!("HTTP {}", status.as_u16());
                span.record("gateway_analytics.error_message", error_msg.as_str());
                // Set OTEL span status with error message - this populates StatusCode and StatusMessage columns
                span.set_status(OtelStatus::error(error_msg.clone()));
                analytics.record.error_message = Some(error_msg.clone());

                // Create OTEL exception event via tracing::error!
                // Using target: "budgateway_internal::analytics_middleware" to avoid exposing internal module path
                span.in_scope(|| {
                    tracing::error!(
                        // otel.exception = true, Commenting out cannot use otel.exception with target: due to macro parsing
                        target: "budgateway_internal::analytics_middleware",
                        error_type = %error_type,
                        error_message = %error_msg,
                        "Exception: {}", error_type
                    );
                });
            }
        }

        // Fallback blocking detection from status codes (when blocking_event not populated by middleware)
        if (response.status() == StatusCode::FORBIDDEN
            || response.status() == StatusCode::TOO_MANY_REQUESTS)
            && analytics.record.blocking_event.is_none()
        {
            // Legacy fallback - only set is_blocked flag without full event data
            analytics.record.is_blocked = true;
        }

        // Record post-response span attributes (after all response data is captured)
        record_post_response_span_attributes(&tracing::Span::current(), &analytics.record);
    }

    // Read baggage data from shared container (populated by auth middleware)
    // and set attributes on the gateway_analytics span
    if let Ok(baggage_guard) = baggage_arc.lock() {
        if let Some(ref baggage_data) = *baggage_guard {
            let span = tracing::Span::current();
            if let Some(ref id) = baggage_data.project_id {
                span.set_attribute(keys::PROJECT_ID, id.clone());
            }
            if let Some(ref id) = baggage_data.prompt_id {
                span.set_attribute(keys::PROMPT_ID, id.clone());
            }
            if let Some(ref id) = baggage_data.prompt_version_id {
                span.set_attribute(keys::PROMPT_VERSION_ID, id.clone());
            }
            if let Some(ref id) = baggage_data.endpoint_id {
                span.set_attribute(keys::ENDPOINT_ID, id.clone());
            }
            if let Some(ref id) = baggage_data.model_id {
                span.set_attribute(keys::MODEL_ID, id.clone());
            }
            if let Some(ref id) = baggage_data.api_key_id {
                span.set_attribute(keys::API_KEY_ID, id.clone());
            }
            if let Some(ref id) = baggage_data.api_key_project_id {
                span.set_attribute(keys::API_KEY_PROJECT_ID, id.clone());
            }
            if let Some(ref id) = baggage_data.user_id {
                span.set_attribute(keys::USER_ID, id.clone());
            }
        }
    }

    // Record Prometheus metrics for autoscaling
    {
        let analytics = analytics_arc.lock().await;
        let method_str = method.to_string();
        let status_str = analytics.record.status_code.to_string();

        // Always record total request duration
        histogram!(
            "gateway_request_duration_seconds",
            "method" => method_str.clone(),
            "status" => status_str.clone()
        )
        .record(analytics.record.total_duration_ms as f64 / 1000.0);

        // Record gateway processing overhead when model latency was available
        // We record even when gateway_processing_ms is 0 to get accurate percentile calculations
        if analytics.record.model_latency_ms.is_some() {
            histogram!(
                "gateway_processing_seconds",
                "method" => method_str,
                "status" => status_str
            )
            .record(analytics.record.gateway_processing_ms as f64 / 1000.0);
        }
    }

    // Get final analytics record
    let final_record = analytics_arc.lock().await.record.clone();

    // Write analytics - prefer batched writes for high throughput
    if let Some(batcher) = batcher_opt {
        // Use batcher for efficient batched writes (non-blocking, fire-and-forget)
        tracing::debug!(
            "Queueing analytics record for batched write: {} {}",
            method,
            uri.path()
        );
        batcher.try_send(final_record);
    } else if let Some(clickhouse) = clickhouse_opt {
        // Fallback to direct write if batcher is not available
        tracing::debug!(
            "Spawning task to write analytics to ClickHouse for {} {}",
            method,
            uri.path()
        );
        tokio::spawn(async move {
            tracing::debug!("Writing analytics record to ClickHouse: {:?}", final_record);
            if let Err(e) = write_analytics_to_clickhouse(&clickhouse, final_record).await {
                error!("Failed to write analytics to ClickHouse: {}", e);
            } else {
                tracing::debug!("Successfully wrote analytics record to ClickHouse");
            }
        });
    } else {
        tracing::warn!("No ClickHouse connection or batcher available for analytics");
    }

    Ok(response)
    }
    .instrument(span)
    .await
}

/// Records pre-request span attributes (called before next.run())
/// Option fields are only recorded if they have a value (null otherwise)
fn record_pre_request_span_attributes(span: &tracing::Span, record: &GatewayAnalyticsDatabaseInsert) {
    // Core
    span.record("gateway_analytics.id", record.id.to_string().as_str());

    // Network
    span.record("gateway_analytics.client_ip", record.client_ip.as_str());
    if let Some(ref proxy_chain) = record.proxy_chain {
        span.record("gateway_analytics.proxy_chain", proxy_chain.as_str());
    }
    span.record("gateway_analytics.protocol_version", record.protocol_version.as_str());

    // GeoIP (all optional)
    if let Some(ref country_code) = record.country_code {
        span.record("gateway_analytics.country_code", country_code.as_str());
    }
    if let Some(ref country_name) = record.country_name {
        span.record("gateway_analytics.country_name", country_name.as_str());
    }
    if let Some(ref region) = record.region {
        span.record("gateway_analytics.region", region.as_str());
    }
    if let Some(ref city) = record.city {
        span.record("gateway_analytics.city", city.as_str());
    }
    if let Some(latitude) = record.latitude {
        span.record("gateway_analytics.latitude", latitude as f64);
    }
    if let Some(longitude) = record.longitude {
        span.record("gateway_analytics.longitude", longitude as f64);
    }
    if let Some(ref timezone) = record.timezone {
        span.record("gateway_analytics.timezone", timezone.as_str());
    }
    if let Some(asn) = record.asn {
        span.record("gateway_analytics.asn", asn as i64);
    }
    if let Some(ref isp) = record.isp {
        span.record("gateway_analytics.isp", isp.as_str());
    }

    // User Agent (most optional)
    if let Some(ref user_agent) = record.user_agent {
        span.record("gateway_analytics.user_agent", user_agent.as_str());
    }
    if let Some(ref device_type) = record.device_type {
        span.record("gateway_analytics.device_type", device_type.as_str());
    }
    if let Some(ref browser_name) = record.browser_name {
        span.record("gateway_analytics.browser_name", browser_name.as_str());
    }
    if let Some(ref browser_version) = record.browser_version {
        span.record("gateway_analytics.browser_version", browser_version.as_str());
    }
    if let Some(ref os_name) = record.os_name {
        span.record("gateway_analytics.os_name", os_name.as_str());
    }
    if let Some(ref os_version) = record.os_version {
        span.record("gateway_analytics.os_version", os_version.as_str());
    }
    span.record("gateway_analytics.is_bot", record.is_bot);

    // Request
    span.record("gateway_analytics.method", record.method.as_str());
    span.record("gateway_analytics.path", record.path.as_str());
    if let Some(ref query_params) = record.query_params {
        span.record("gateway_analytics.query_params", query_params.as_str());
    }
    if let Ok(headers_json) = serde_json::to_string(&record.request_headers) {
        span.record("gateway_analytics.request_headers", headers_json.as_str());
    }
    if let Some(body_size) = record.body_size {
        span.record("gateway_analytics.body_size", body_size as i64);
    }
    span.record("gateway_analytics.request_timestamp", record.request_timestamp.to_rfc3339().as_str());

    // Auth (all optional)
    if let Some(ref api_key_id) = record.api_key_id {
        span.record("gateway_analytics.api_key_id", api_key_id.as_str());
    }
    if let Some(ref auth_method) = record.auth_method {
        span.record("gateway_analytics.auth_method", auth_method.as_str());
    }
    if let Some(ref user_id) = record.user_id {
        span.record("gateway_analytics.user_id", user_id.as_str());
    }
    if let Some(project_id) = record.project_id {
        span.record("gateway_analytics.project_id", project_id.to_string().as_str());
    }
    if let Some(endpoint_id) = record.endpoint_id {
        span.record("gateway_analytics.endpoint_id", endpoint_id.to_string().as_str());
    }
}

/// Records post-response span attributes (called after next.run() and response processing)
/// Option fields are only recorded if they have a value (null otherwise)
fn record_post_response_span_attributes(span: &tracing::Span, record: &GatewayAnalyticsDatabaseInsert) {
    // Performance
    span.record("gateway_analytics.response_timestamp", record.response_timestamp.to_rfc3339().as_str());
    span.record("gateway_analytics.total_duration_ms", record.total_duration_ms as i64);
    span.record("gateway_analytics.gateway_processing_ms", record.gateway_processing_ms as i64);

    // Response
    span.record("gateway_analytics.status_code", record.status_code as i64);
    if let Some(response_size) = record.response_size {
        span.record("gateway_analytics.response_size", response_size as i64);
    }
    if let Ok(headers_json) = serde_json::to_string(&record.response_headers) {
        span.record("gateway_analytics.response_headers", headers_json.as_str());
    }
    if let Some(inference_id) = record.inference_id {
        span.record("gateway_analytics.inference_id", inference_id.to_string().as_str());
    }

    // Model (all optional)
    if let Some(ref model_name) = record.model_name {
        span.record("gateway_analytics.model_name", model_name.as_str());
    }
    if let Some(ref model_provider) = record.model_provider {
        span.record("gateway_analytics.model_provider", model_provider.as_str());
    }
    if let Some(ref model_version) = record.model_version {
        span.record("gateway_analytics.model_version", model_version.as_str());
    }
    if let Some(ref routing_decision) = record.routing_decision {
        span.record("gateway_analytics.routing_decision", routing_decision.as_str());
    }

    // Error (all optional)
    if let Some(ref error_type) = record.error_type {
        span.record("gateway_analytics.error_type", error_type.as_str());
    }
    if let Some(ref error_message) = record.error_message {
        span.record("gateway_analytics.error_message", error_message.as_str());
    }

    // Blocking events - record all 17 GatewayBlockingEvents table columns
    span.record("gateway_analytics.is_blocked", record.is_blocked);

    if let Some(ref blocking_event) = record.blocking_event {
        // Event identifiers (unique fields from BlockingEventData)
        span.record("gateway_blocking_events.id", blocking_event.id.to_string().as_str());
        span.record("gateway_blocking_events.rule_id", blocking_event.rule_id.to_string().as_str());

        // Client information (from analytics record - overlapping fields)
        span.record("gateway_blocking_events.client_ip", record.client_ip.as_str());
        if let Some(ref country_code) = record.country_code {
            span.record("gateway_blocking_events.country_code", country_code.as_str());
        }
        if let Some(ref user_agent) = record.user_agent {
            span.record("gateway_blocking_events.user_agent", user_agent.as_str());
        }

        // Request context (from analytics record - overlapping fields)
        span.record("gateway_blocking_events.request_path", record.path.as_str());
        span.record("gateway_blocking_events.request_method", record.method.as_str());
        if let Some(ref api_key_id) = record.api_key_id {
            span.record("gateway_blocking_events.api_key_id", api_key_id.as_str());
        }

        // Project/endpoint context (from analytics record - overlapping fields)
        if let Some(project_id) = record.project_id {
            span.record("gateway_blocking_events.project_id", project_id.to_string().as_str());
        }
        if let Some(endpoint_id) = record.endpoint_id {
            span.record("gateway_blocking_events.endpoint_id", endpoint_id.to_string().as_str());
        }
        if let Some(ref model_name) = record.model_name {
            span.record("gateway_blocking_events.model_name", model_name.as_str());
        }

        // Rule information (unique fields from BlockingEventData)
        span.record("gateway_blocking_events.rule_type", blocking_event.rule_type.as_str());
        span.record("gateway_blocking_events.rule_name", blocking_event.rule_name.as_str());
        span.record("gateway_blocking_events.rule_priority", blocking_event.rule_priority as i64);

        // Block details (unique fields from BlockingEventData)
        span.record("gateway_blocking_events.block_reason", blocking_event.block_reason.as_str());
        span.record("gateway_blocking_events.action_taken", blocking_event.action_taken.as_str());

        // Timing (unique field from BlockingEventData)
        let blocked_at_formatted = blocking_event.blocked_at.format("%Y-%m-%d %H:%M:%S%.3f").to_string();
        span.record("gateway_blocking_events.blocked_at", blocked_at_formatted.as_str());
    }

    // Tags
    if let Ok(tags_json) = serde_json::to_string(&record.tags) {
        span.record("gateway_analytics.tags", tags_json.as_str());
    }
}

/// Extract client IP from headers only (when ConnectInfo is not available)
fn get_client_ip_fallback(headers: &HeaderMap) -> String {
    use std::net::IpAddr;

    // First check for custom headers from BudPlayground (these won't be modified by proxies)
    // Priority 1: X-Playground-Client-IP (contains the original header chain)
    if let Some(playground_ip) = headers.get("x-playground-client-ip") {
        if let Ok(ip_str) = playground_ip.to_str() {
            tracing::debug!("Found X-Playground-Client-IP header: {}", ip_str);
            // Split and find first public IP if it's a chain
            let ips: Vec<&str> = ip_str.split(',').map(|s| s.trim()).collect();
            for ip in &ips {
                if let Ok(parsed_ip) = ip.parse::<IpAddr>() {
                    // Check if it's a public IP
                    let is_private = match parsed_ip {
                        IpAddr::V4(ipv4) => {
                            ipv4.is_private()
                                || ipv4.is_loopback()
                                || ipv4.is_link_local()
                                || ipv4.is_unspecified()
                                || ipv4.octets()[0] == 10
                                || (ipv4.octets()[0] == 172
                                    && ipv4.octets()[1] >= 16
                                    && ipv4.octets()[1] <= 31)
                                || (ipv4.octets()[0] == 192 && ipv4.octets()[1] == 168)
                        }
                        IpAddr::V6(ipv6) => {
                            ipv6.is_loopback()
                                || ipv6.is_unspecified()
                                || (ipv6.segments()[0] & 0xfe00) == 0xfc00
                        }
                    };

                    if !is_private {
                        tracing::debug!("Using public IP from X-Playground-Client-IP: {}", ip);
                        return ip.to_string();
                    } else {
                        tracing::debug!("Skipping private IP in X-Playground-Client-IP: {}", ip);
                    }
                }
            }
        }
    }

    // Priority 2: X-Original-Client-IP (fallback if X-Playground-Client-IP not available)
    if let Some(original_client_ip) = headers.get("x-original-client-ip") {
        if let Ok(ip_str) = original_client_ip.to_str() {
            tracing::debug!("Found X-Original-Client-IP header: {}", ip_str);
            // Split and find first public IP if it's a chain
            let ips: Vec<&str> = ip_str.split(',').map(|s| s.trim()).collect();
            for ip in &ips {
                if let Ok(parsed_ip) = ip.parse::<IpAddr>() {
                    // Check if it's a public IP
                    let is_private = match parsed_ip {
                        IpAddr::V4(ipv4) => {
                            ipv4.is_private()
                                || ipv4.is_loopback()
                                || ipv4.is_link_local()
                                || ipv4.is_unspecified()
                                || ipv4.octets()[0] == 10
                                || (ipv4.octets()[0] == 172
                                    && ipv4.octets()[1] >= 16
                                    && ipv4.octets()[1] <= 31)
                                || (ipv4.octets()[0] == 192 && ipv4.octets()[1] == 168)
                        }
                        IpAddr::V6(ipv6) => {
                            ipv6.is_loopback()
                                || ipv6.is_unspecified()
                                || (ipv6.segments()[0] & 0xfe00) == 0xfc00
                        }
                    };

                    if !is_private {
                        tracing::debug!("Using public IP from X-Original-Client-IP: {}", ip);
                        return ip.to_string();
                    } else {
                        tracing::debug!("Skipping private IP in X-Original-Client-IP: {}", ip);
                    }
                }
            }
        }
    }

    // Helper function to check if an IP is private/local
    let is_private_ip = |ip_str: &str| -> bool {
        if let Ok(ip) = ip_str.parse::<IpAddr>() {
            match ip {
                IpAddr::V4(ipv4) => {
                    ipv4.is_private() ||
                    ipv4.is_loopback() ||
                    ipv4.is_link_local() ||
                    ipv4.is_unspecified() ||
                    // Check for Docker/Kubernetes internal IPs
                    ipv4.octets()[0] == 10 ||  // 10.0.0.0/8
                    (ipv4.octets()[0] == 172 && ipv4.octets()[1] >= 16 && ipv4.octets()[1] <= 31) || // 172.16.0.0/12
                    (ipv4.octets()[0] == 192 && ipv4.octets()[1] == 168) // 192.168.0.0/16
                }
                IpAddr::V6(ipv6) => {
                    ipv6.is_loopback() ||
                    ipv6.is_unspecified() ||
                    // fc00::/7 - Unique local addresses
                    (ipv6.segments()[0] & 0xfe00) == 0xfc00
                }
            }
        } else {
            false
        }
    };

    // Check X-Forwarded-For first
    if let Some(forwarded_for) = headers.get("x-forwarded-for") {
        if let Ok(forwarded_str) = forwarded_for.to_str() {
            tracing::debug!("Found X-Forwarded-For header: {}", forwarded_str);

            // X-Forwarded-For can contain multiple IPs, find the first public IP
            let ips: Vec<&str> = forwarded_str.split(',').map(|s| s.trim()).collect();

            // Try to find the first public IP in the chain
            for ip in &ips {
                if !is_private_ip(ip) {
                    tracing::debug!("Found public IP in X-Forwarded-For: {}", ip);
                    return ip.to_string();
                } else {
                    tracing::debug!("Skipping private IP: {}", ip);
                }
            }

            // If all IPs are private, use the first one as fallback
            if let Some(first_ip) = ips.first() {
                tracing::debug!(
                    "No public IP found in X-Forwarded-For, using first IP: {}",
                    first_ip
                );
                return first_ip.to_string();
            }
        } else {
            tracing::warn!(
                "X-Forwarded-For header present but invalid: {:?}",
                forwarded_for
            );
        }
    } else {
        tracing::debug!("X-Forwarded-For header: not present");
    }

    // Check X-Real-IP
    if let Some(real_ip) = headers.get("x-real-ip") {
        if let Ok(ip_str) = real_ip.to_str() {
            tracing::debug!("Found X-Real-IP header: {}", ip_str);
            if !is_private_ip(ip_str) {
                tracing::debug!("Using public IP from X-Real-IP: {}", ip_str);
                return ip_str.to_string();
            } else {
                tracing::debug!("X-Real-IP contains private IP, skipping: {}", ip_str);
            }
        } else {
            tracing::warn!("X-Real-IP header present but invalid: {:?}", real_ip);
        }
    } else {
        tracing::debug!("X-Real-IP header: not present");
    }

    // Check CF-Connecting-IP (Cloudflare)
    if let Some(cf_ip) = headers.get("cf-connecting-ip") {
        if let Ok(ip_str) = cf_ip.to_str() {
            tracing::debug!("Found CF-Connecting-IP header: {}", ip_str);
            // Cloudflare headers should always contain public IPs
            tracing::debug!("Using IP from CF-Connecting-IP: {}", ip_str);
            return ip_str.to_string();
        }
    }

    // Check True-Client-IP (Cloudflare Enterprise)
    if let Some(true_client_ip) = headers.get("true-client-ip") {
        if let Ok(ip_str) = true_client_ip.to_str() {
            tracing::debug!("Found True-Client-IP header: {}", ip_str);
            // Cloudflare headers should always contain public IPs
            tracing::debug!("Using IP from True-Client-IP: {}", ip_str);
            return ip_str.to_string();
        }
    }

    // Fallback to unknown
    tracing::debug!("No forwarded IP headers found, using 'unknown'");
    "unknown".to_string()
}

/// Extract proxy chain information
fn extract_proxy_chain(headers: &HeaderMap) -> Option<String> {
    headers
        .get("x-forwarded-for")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string())
}

/// Parse user agent string to extract device and browser information
fn parse_user_agent(
    ua: &str,
    record: &mut GatewayAnalyticsDatabaseInsert,
    parser: &UserAgentParser,
) {
    let ua_lower = ua.to_lowercase();

    // Detect bots
    record.is_bot = ua_lower.contains("bot")
        || ua_lower.contains("crawler")
        || ua_lower.contains("spider")
        || ua_lower.contains("scraper");

    // Parse user agent
    let parsed = parser.parse(ua);

    // Browser info
    record.browser_name = Some(parsed.user_agent.family.to_string());
    match (&parsed.user_agent.major, &parsed.user_agent.minor) {
        (Some(major), Some(minor)) => {
            record.browser_version = Some(format!("{major}.{minor}"));
        }
        (Some(major), None) => {
            record.browser_version = Some(major.to_string());
        }
        _ => {}
    }

    // OS info
    record.os_name = Some(parsed.os.family.to_string());
    match (&parsed.os.major, &parsed.os.minor) {
        (Some(major), Some(minor)) => {
            record.os_version = Some(format!("{major}.{minor}"));
        }
        (Some(major), None) => {
            record.os_version = Some(major.to_string());
        }
        _ => {}
    }

    // Device type
    let device_family = parsed.device.family.to_lowercase();
    record.device_type = Some(if record.is_bot {
        "bot".to_string()
    } else if device_family.contains("mobile") || device_family.contains("phone") {
        "mobile".to_string()
    } else if device_family.contains("tablet") || device_family.contains("ipad") {
        "tablet".to_string()
    } else {
        "desktop".to_string()
    });
}

/// Extract important headers for analytics
fn extract_important_headers(headers: &HeaderMap) -> HashMap<String, String> {
    let mut result = HashMap::new();

    // List of headers to capture
    let important_headers = [
        "accept",
        "accept-language",
        "content-type",
        "referer",
        "origin",
        "x-request-id",
        "x-correlation-id",
        "x-model-name",
    ];

    for header_name in &important_headers {
        if let Some(value) = headers.get(*header_name) {
            if let Ok(value_str) = value.to_str() {
                result.insert(header_name.to_string(), value_str.to_string());
            }
        }
    }

    result
}

/// Write analytics record to ClickHouse
async fn write_analytics_to_clickhouse(
    clickhouse: &ClickHouseConnectionInfo,
    record: GatewayAnalyticsDatabaseInsert,
) -> Result<(), Error> {
    clickhouse.write(&[record], "GatewayAnalytics").await
}

use axum::extract::State;

/// Middleware to attach ClickHouse connection to request extensions
pub async fn attach_clickhouse_middleware(
    State(clickhouse): State<Arc<ClickHouseConnectionInfo>>,
    mut request: Request,
    next: Next,
) -> Result<Response, Error> {
    tracing::debug!(
        "Attaching ClickHouse connection to request extensions: {:?}",
        clickhouse.database()
    );
    request.extensions_mut().insert(clickhouse);
    Ok(next.run(request).await)
}

/// Middleware to attach GeoIP service to request extensions
pub async fn attach_geoip_middleware(
    State(geoip): State<Arc<GeoIpService>>,
    mut request: Request,
    next: Next,
) -> Result<Response, Error> {
    request.extensions_mut().insert(geoip);
    Ok(next.run(request).await)
}

/// Middleware to attach UA parser to request extensions
pub async fn attach_ua_parser_middleware(
    State(parser): State<Arc<UserAgentParser>>,
    mut request: Request,
    next: Next,
) -> Result<Response, Error> {
    request.extensions_mut().insert(parser);
    Ok(next.run(request).await)
}

/// Middleware to attach analytics batcher to request extensions
pub async fn attach_analytics_batcher_middleware(
    State(batcher): State<AnalyticsBatcher>,
    mut request: Request,
    next: Next,
) -> Result<Response, Error> {
    request.extensions_mut().insert(batcher);
    Ok(next.run(request).await)
}
