//! Blocking Middleware for Gateway

use axum::{
    extract::Request,
    http::{HeaderMap, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
};
use std::sync::Arc;

use crate::analytics::RequestAnalytics;
use crate::blocking_rules::BlockingRulesManager;
use crate::error::Error;

/// Middleware for enforcing blocking rules
pub async fn blocking_middleware(
    headers: HeaderMap,
    request: Request,
    next: Next,
) -> Result<Response, Error> {
    tracing::debug!("=== BLOCKING MIDDLEWARE CALLED ===");
    // Get blocking rules manager from extensions
    let blocking_manager = request
        .extensions()
        .get::<Arc<BlockingRulesManager>>()
        .cloned();

    let Some(manager) = blocking_manager else {
        tracing::debug!("No blocking manager configured, proceeding with request");
        return Ok(next.run(request).await);
    };

    // Get analytics data if available (populated by analytics middleware)
    let analytics = request
        .extensions()
        .get::<Arc<tokio::sync::Mutex<RequestAnalytics>>>()
        .cloned();

    // Extract request metadata from analytics or headers
    let (client_ip, country_code, user_agent) = if let Some(ref analytics) = analytics {
        let analytics = analytics.lock().await;
        tracing::debug!(
            "Using analytics data - IP: {}, Country: {:?}, User-Agent: {:?}",
            analytics.record.client_ip,
            analytics.record.country_code,
            analytics.record.user_agent
        );
        (
            analytics.record.client_ip.clone(),
            analytics.record.country_code.clone(),
            analytics.record.user_agent.clone(),
        )
    } else {
        // Fall back to extracting from headers when analytics is disabled
        let client_ip = get_client_ip_from_headers(&headers);
        let user_agent_from_header = headers
            .get("user-agent")
            .and_then(|v| v.to_str().ok())
            .map(|s| s.to_string());

        tracing::debug!(
            "Using header data - IP: {}, User-Agent: {:?}",
            client_ip,
            user_agent_from_header
        );

        (client_ip, None, user_agent_from_header)
    };

    tracing::debug!(
        "Blocking middleware - checking request: IP={}, Country={:?}, User-Agent={:?}",
        client_ip,
        country_code,
        user_agent
    );

    // Check if request should be blocked
    match manager
        .should_block(&client_ip, country_code.as_deref(), user_agent.as_deref())
        .await
    {
        Ok(Some((rule, reason))) => {
            tracing::warn!(
                "Request BLOCKED - Rule: {} (type: {:?}), Reason: {}, IP: {}, User-Agent: {:?}",
                rule.name,
                rule.rule_type,
                reason,
                client_ip,
                user_agent
            );

            // Update analytics if available
            if let Some(analytics) = request
                .extensions()
                .get::<Arc<tokio::sync::Mutex<RequestAnalytics>>>()
            {
                let mut analytics = analytics.lock().await;
                analytics.record.is_blocked = true;
                analytics.record.block_reason = Some(reason.clone());
                analytics.record.block_rule_id = Some(rule.id.to_string());
            }

            // Return 403 Forbidden response
            let mut response = (
                StatusCode::FORBIDDEN,
                [("x-block-reason", reason.as_str())],
                format!(r#"{{"error":"forbidden","message":"{}"}}"#, reason),
            )
                .into_response();

            // Add custom headers
            if let Ok(header_value) = rule.id.to_string().parse() {
                response
                    .headers_mut()
                    .insert("x-blocked-by-rule", header_value);
            }

            Ok(response)
        }
        Ok(None) => {
            tracing::debug!(
                "Request ALLOWED - No blocking rules matched for IP: {}, User-Agent: {:?}",
                client_ip,
                user_agent
            );
            Ok(next.run(request).await)
        }
        Err(e) => {
            // Log error but don't block request on error
            tracing::error!("Error checking blocking rules: {}", e);
            Ok(next.run(request).await)
        }
    }
}

/// Extract the real client IP from headers only (fallback when analytics is disabled)
fn get_client_ip_from_headers(headers: &HeaderMap) -> String {
    // Check X-Forwarded-For first
    if let Some(forwarded_for) = headers.get("x-forwarded-for") {
        if let Ok(forwarded_str) = forwarded_for.to_str() {
            // X-Forwarded-For can contain multiple IPs, take the first one
            if let Some(first_ip) = forwarded_str.split(',').next() {
                return first_ip.trim().to_string();
            }
        }
    }

    // Check X-Real-IP
    if let Some(real_ip) = headers.get("x-real-ip") {
        if let Ok(ip_str) = real_ip.to_str() {
            return ip_str.to_string();
        }
    }

    // Fallback to unknown when no IP can be determined
    "unknown".to_string()
}

/// Middleware to attach blocking rules manager to request extensions
pub async fn attach_blocking_manager(
    manager: axum::extract::State<Arc<BlockingRulesManager>>,
    mut request: Request,
    next: Next,
) -> Result<Response, Error> {
    request.extensions_mut().insert(manager.0);
    Ok(next.run(request).await)
}

/// Background task to periodically sync rules and cleanup rate limits
pub async fn blocking_rules_sync_task(manager: Arc<BlockingRulesManager>) {
    let mut interval = tokio::time::interval(tokio::time::Duration::from_secs(300)); // 5 minutes

    loop {
        interval.tick().await;

        // Cleanup old rate limit states
        manager.cleanup_rate_limits().await;

        // Note: Project-specific rule syncing happens on-demand in should_block()
        // This is more efficient than pre-loading all rules for all projects
    }
}
