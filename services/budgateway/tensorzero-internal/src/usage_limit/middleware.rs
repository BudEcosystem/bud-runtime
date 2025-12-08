use axum::body::{to_bytes, Body};
use axum::extract::{Request, State};
use axum::http::StatusCode;
use axum::middleware::Next;
use axum::response::{IntoResponse, Response};
use metrics::histogram;
use std::sync::Arc;
use std::time::Instant;
use tracing::{debug, warn};

use crate::auth::Auth;
use crate::usage_limit::{UsageLimitDecision, UsageLimiter};

/// Middleware for checking usage limits
pub async fn usage_limit_middleware(
    State((auth, usage_limiter)): State<(Auth, Arc<UsageLimiter>)>,
    request: Request,
    next: Next,
) -> Result<Response, Response> {
    let usage_limit_start = Instant::now();

    let (parts, body) = request.into_parts();

    // Measure body read time
    let body_read_start = Instant::now();
    let bytes = to_bytes(body, 1024 * 1024).await.unwrap_or_default();
    histogram!("usage_limit_body_read_seconds").record(body_read_start.elapsed().as_secs_f64());

    // Extract the API key from authorization header
    let api_key = parts
        .headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.trim())
        .map(|s| s.strip_prefix("Bearer ").unwrap_or(s))
        .map(|s| s.to_string());

    if let Some(key) = api_key {
        // Measure auth metadata lookup
        let metadata_start = Instant::now();
        let metadata_opt = auth.get_auth_metadata(&key);
        histogram!("usage_limit_metadata_lookup_seconds").record(metadata_start.elapsed().as_secs_f64());

        if let Some(metadata) = metadata_opt {
            if let Some(user_id) = metadata.user_id {
                // Measure usage check time (this may hit Redis on cache miss)
                let check_start = Instant::now();
                let decision = usage_limiter.check_usage(&user_id, None, None).await;
                let check_duration = check_start.elapsed();
                histogram!("usage_limit_check_seconds").record(check_duration.as_secs_f64());

                match decision {
                    UsageLimitDecision::Allow => {
                        debug!("Usage limit check passed for user {}", user_id);
                    }
                    UsageLimitDecision::Deny { reason } => {
                        warn!("Usage limit exceeded for user {}: {}", user_id, reason);

                        histogram!("usage_limit_total_seconds").record(usage_limit_start.elapsed().as_secs_f64());

                        let error_body = serde_json::json!({
                            "error": {
                                "message": format!("Usage quota exceeded: {}", reason),
                                "type": "insufficient_quota",
                                "code": 402
                            }
                        });

                        return Err(
                            (StatusCode::PAYMENT_REQUIRED, axum::Json(error_body)).into_response()
                        );
                    }
                }
            }
        }
    }

    // Record total usage limit middleware time
    histogram!("usage_limit_total_seconds").record(usage_limit_start.elapsed().as_secs_f64());

    // Reconstruct request and continue
    let request = Request::from_parts(parts, Body::from(bytes));
    Ok(next.run(request).await)
}
