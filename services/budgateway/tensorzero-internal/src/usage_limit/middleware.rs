use axum::body::{to_bytes, Body};
use axum::extract::{Request, State};
use axum::http::StatusCode;
use axum::middleware::Next;
use axum::response::{IntoResponse, Response};
use serde_json::Value;
use std::sync::Arc;
use tracing::{debug, warn};

use crate::auth::Auth;
use crate::usage_limit::{UsageLimiter, UsageLimitDecision};

/// Middleware for checking usage limits
pub async fn usage_limit_middleware(
    State((auth, usage_limiter)): State<(Auth, Arc<UsageLimiter>)>,
    request: Request,
    next: Next,
) -> Result<Response, Response> {
    let (parts, body) = request.into_parts();
    let bytes = to_bytes(body, 1024 * 1024).await.unwrap_or_default();

    // Extract the API key from authorization header
    let api_key = parts
        .headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.trim())
        .map(|s| s.strip_prefix("Bearer ").unwrap_or(s))
        .map(|s| s.to_string());

    if let Some(key) = api_key {
        // Get user_id from auth metadata
        if let Some(metadata) = auth.get_auth_metadata(&key) {
            if let Some(user_id) = metadata.user_id {
                // For now, just check without consuming (consumption happens after successful response)
                // TODO: Extract estimated tokens/cost from request body for pre-check
                match usage_limiter.check_usage(&user_id, None, None).await {
                    UsageLimitDecision::Allow => {
                        debug!("Usage limit check passed for user {}", user_id);
                    }
                    UsageLimitDecision::Deny { reason } => {
                        warn!("Usage limit exceeded for user {}: {}", user_id, reason);

                        let error_body = serde_json::json!({
                            "error": {
                                "message": format!("Usage quota exceeded: {}", reason),
                                "type": "insufficient_quota",
                                "code": 402
                            }
                        });

                        return Err((
                            StatusCode::PAYMENT_REQUIRED,
                            axum::Json(error_body)
                        ).into_response());
                    }
                }
            }
        }
    }

    // Reconstruct request and continue
    let request = Request::from_parts(parts, Body::from(bytes));
    Ok(next.run(request).await)
}
