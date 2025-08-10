//! Blocking Middleware for Gateway

use axum::{
    extract::{ConnectInfo, Request},
    http::{HeaderMap, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
};
use std::net::SocketAddr;
use std::sync::Arc;
use uuid::Uuid;

use crate::analytics::RequestAnalytics;
use crate::blocking_rules::BlockingRulesManager;
use crate::error::Error;

/// Middleware for enforcing blocking rules
pub async fn blocking_middleware(
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
    headers: HeaderMap,
    request: Request,
    next: Next,
) -> Result<Response, Error> {
    // Get blocking rules manager from extensions
    let blocking_manager = request
        .extensions()
        .get::<Arc<BlockingRulesManager>>()
        .cloned();

    let Some(manager) = blocking_manager else {
        // No blocking manager configured, proceed with request
        return Ok(next.run(request).await);
    };

    // Extract request metadata
    let client_ip = get_client_ip(&addr, &headers);

    // Get analytics data if available (populated by analytics middleware)
    let analytics = request
        .extensions()
        .get::<Arc<tokio::sync::Mutex<RequestAnalytics>>>()
        .cloned();

    let (country_code, user_agent, project_id, endpoint_id) = if let Some(ref analytics) = analytics
    {
        let analytics = analytics.lock().await;
        (
            analytics.record.country_code.clone(),
            analytics.record.user_agent.clone(),
            analytics.record.project_id,
            analytics.record.endpoint_id,
        )
    } else {
        // Try to extract from headers or other sources
        let project_id = headers
            .get("x-project-id")
            .and_then(|v| v.to_str().ok())
            .and_then(|s| Uuid::parse_str(s).ok());
        let endpoint_id = headers
            .get("x-endpoint-id")
            .and_then(|v| v.to_str().ok())
            .and_then(|s| Uuid::parse_str(s).ok());
        (
            None,
            headers
                .get("user-agent")
                .and_then(|v| v.to_str().ok())
                .map(|s| s.to_string()),
            project_id,
            endpoint_id,
        )
    };

    // For now, if no project ID is available, we'll check global rules
    // or rules based on IP/country/user-agent only
    let project_id = project_id.unwrap_or_else(|| {
        // Use a default project ID for global rules
        Uuid::nil()
    });

    // Check if request should be blocked
    match manager
        .should_block(
            &project_id,
            endpoint_id.as_ref(),
            &client_ip,
            country_code.as_deref(),
            user_agent.as_deref(),
        )
        .await
    {
        Ok(Some((rule, reason))) => {
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
                format!(
                    r#"{{"error":"forbidden","message":"{}","rule":"{}"}}"#,
                    reason, rule.name
                ),
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
            // No blocking rule matched, proceed
            Ok(next.run(request).await)
        }
        Err(e) => {
            // Log error but don't block request on error
            tracing::error!("Error checking blocking rules: {}", e);
            Ok(next.run(request).await)
        }
    }
}

/// Extract the real client IP considering proxy headers
fn get_client_ip(addr: &SocketAddr, headers: &HeaderMap) -> String {
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

    // Fallback to socket address
    addr.ip().to_string()
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
