//! Blocking Middleware for Gateway

use axum::{
    extract::Request,
    http::{HeaderMap, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
};
use std::sync::Arc;

use crate::analytics::{BlockingEventData, RequestAnalytics};
use crate::blocking_rules::BlockingRulesManager;
use crate::error::Error;
use axum::http::{Method, Uri};
use chrono::Utc;
use uuid::Uuid;

/// Middleware for enforcing blocking rules
pub async fn blocking_middleware(
    method: Method,
    uri: Uri,
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

    // Extract request metadata from analytics or headers/parameters
    let (
        client_ip,
        country_code,
        user_agent,
        request_path,
        request_method,
        api_key_id,
        project_id,
        endpoint_id,
        model_name,
    ) = if let Some(ref analytics) = analytics {
        let analytics = analytics.lock().await;
        (
            analytics.record.client_ip.clone(),
            analytics.record.country_code.clone(),
            analytics.record.user_agent.clone(),
            analytics.record.path.clone(),
            analytics.record.method.clone(),
            analytics.record.api_key_id.clone(),
            analytics.record.project_id,
            analytics.record.endpoint_id,
            analytics.record.model_name.clone(),
        )
    } else {
        // Fallback when analytics disabled
        let client_ip = get_client_ip_from_headers(&headers);
        let user_agent_from_header = headers
            .get("user-agent")
            .and_then(|v| v.to_str().ok())
            .map(|s| s.to_string());

        (
            client_ip,
            None,                   // country_code
            user_agent_from_header, // user_agent
            uri.path().to_string(), // request_path
            method.to_string(),     // request_method
            None,                   // api_key_id
            None,                   // project_id
            None,                   // endpoint_id
            None,                   // model_name
        )
    };

    tracing::debug!(
        "Blocking middleware - checking request: IP={}, Country={:?}, User-Agent={:?}",
        client_ip,
        country_code,
        user_agent
    );

    // Check if request should be blocked
    match manager
        .should_block(
            &client_ip,
            country_code.as_deref(),
            user_agent.as_deref(),
            &request_path,
            &request_method,
            api_key_id.clone(),
            project_id,
            endpoint_id,
            model_name.clone(),
        )
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

            // Update analytics if available - create full blocking event record
            if let Some(analytics) = request
                .extensions()
                .get::<Arc<tokio::sync::Mutex<RequestAnalytics>>>()
            {
                let mut analytics = analytics.lock().await;

                // Create blocking event data with all unique fields
                let blocking_event = BlockingEventData {
                    id: Uuid::now_v7(),
                    rule_id: rule.id,
                    rule_type: format!("{:?}", rule.rule_type),
                    rule_name: rule.name.clone(),
                    rule_priority: rule.priority,
                    block_reason: reason.clone(),
                    action_taken: rule.action.clone(),
                    blocked_at: Utc::now(),
                };

                analytics.record.is_blocked = true;
                analytics.record.blocking_event = Some(blocking_event);
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
