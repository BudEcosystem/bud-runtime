use axum::{
    extract::Request,
    http::{HeaderMap, Method, StatusCode, Uri, Version},
    middleware::Next,
    response::Response,
};
use chrono::Utc;
use metrics::histogram;
use std::collections::HashMap;
use std::sync::Arc;
use std::time::Instant;
use tracing::error;
use uaparser::{Parser, UserAgentParser};
use uuid::Uuid;

use crate::analytics::{GatewayAnalyticsDatabaseInsert, RequestAnalytics};
use crate::analytics_batcher::AnalyticsBatcher;
use crate::clickhouse::ClickHouseConnectionInfo;
use crate::error::Error;
use crate::geoip::GeoIpService;

/// Middleware for collecting analytics data about gateway requests
pub async fn analytics_middleware(
    headers: HeaderMap,
    method: Method,
    uri: Uri,
    version: Version,
    mut request: Request,
    next: Next,
) -> Result<Response, Error> {
    let analytics_start = Instant::now();
    tracing::debug!("Analytics middleware called for {} {}", method, uri.path());

    // Get services from request extensions
    let geoip_service = request.extensions().get::<Arc<GeoIpService>>().cloned();
    let ua_parser = request.extensions().get::<Arc<UserAgentParser>>().cloned();

    // Create analytics record
    let mut analytics = RequestAnalytics::new();
    let record = &mut analytics.record;

    // Extract basic request information - use headers-only approach for client IP
    let ip_extraction_start = Instant::now();
    record.client_ip = get_client_ip_fallback(&headers);
    record.proxy_chain = extract_proxy_chain(&headers);
    histogram!("analytics_ip_extraction_seconds").record(ip_extraction_start.elapsed().as_secs_f64());

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
    let ua_parse_start = Instant::now();
    if let (Some(ua), Some(parser)) = (record.user_agent.clone(), ua_parser.as_ref()) {
        parse_user_agent(&ua, record, parser);
    }
    histogram!("analytics_ua_parse_seconds").record(ua_parse_start.elapsed().as_secs_f64());

    // Perform GeoIP lookup
    let geoip_start = Instant::now();
    if let Some(geoip) = &geoip_service {
        let client_ip = record.client_ip.clone();
        geoip.enrich_analytics(&client_ip, record);
    }
    histogram!("analytics_geoip_lookup_seconds").record(geoip_start.elapsed().as_secs_f64());

    // Extract selected request headers
    record.request_headers = extract_important_headers(&headers);

    // Store analytics in request extensions
    let analytics_arc = Arc::new(tokio::sync::Mutex::new(analytics));
    request.extensions_mut().insert(analytics_arc.clone());

    // Get ClickHouse connection before processing request
    let clickhouse_opt = request
        .extensions()
        .get::<Arc<ClickHouseConnectionInfo>>()
        .cloned();

    // Get analytics batcher for batched writes (preferred over direct writes)
    let batcher_opt = request.extensions().get::<AnalyticsBatcher>().cloned();

    // Record pre-handler analytics time
    histogram!("analytics_pre_handler_seconds").record(analytics_start.elapsed().as_secs_f64());

    tracing::debug!(
        "ClickHouse connection in analytics middleware: {}",
        if clickhouse_opt.is_some() {
            "available"
        } else {
            "not available"
        }
    );

    // Process the request
    let response = next.run(request).await;

    // Start post-handler timing
    let post_handler_start = Instant::now();

    // Update analytics with response data
    {
        let lock_start = Instant::now();
        let mut analytics = analytics_arc.lock().await;
        histogram!("analytics_lock_acquire_seconds").record(lock_start.elapsed().as_secs_f64());

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

        // Check if request was blocked
        if response.status() == StatusCode::FORBIDDEN
            || response.status() == StatusCode::TOO_MANY_REQUESTS
        {
            analytics.record.is_blocked = true;
            // Block reason might be in a custom header or response body
            if let Some(reason) = response.headers().get("x-block-reason") {
                analytics.record.block_reason = reason.to_str().ok().map(|s| s.to_string());
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
    let write_start = Instant::now();
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
    histogram!("analytics_write_queue_seconds").record(write_start.elapsed().as_secs_f64());

    // Record total post-handler analytics time
    histogram!("analytics_post_handler_seconds").record(post_handler_start.elapsed().as_secs_f64());

    Ok(response)
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
