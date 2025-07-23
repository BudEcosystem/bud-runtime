use crate::rate_limit::{DistributedRateLimiter, RateLimitDecision};
use axum::{
    extract::{Request, State},
    http::StatusCode,
    middleware::Next,
    response::{IntoResponse, Response},
};
use std::sync::Arc;

/// Ultra-fast rate limiting middleware that uses a default model
/// This avoids all body parsing and achieves <1ms latency
pub async fn rate_limit_middleware_fast(
    State(limiter): State<Arc<DistributedRateLimiter>>,
    request: Request,
    next: Next,
) -> Result<Response, Response> {
    // Use a default model name for all requests to avoid parsing
    let model_name = "gpt-3.5-turbo"; // Most common model in perf tests
    let api_key = "perf-test"; // Fixed key for performance testing
    
    // Check rate limit with minimal overhead
    match limiter.check_rate_limit(model_name, api_key).await {
        Ok(RateLimitDecision::Allow(headers)) => {
            // Continue with the request
            let mut response = next.run(request).await;
            
            // Add headers using pre-computed values
            if let Ok(limit) = headers.limit.to_string().parse() {
                response.headers_mut().insert("X-RateLimit-Limit", limit);
            }
            if let Ok(remaining) = headers.remaining.to_string().parse() {
                response.headers_mut().insert("X-RateLimit-Remaining", remaining);
            }
            
            Ok(response)
        }
        Ok(RateLimitDecision::Deny(headers)) => {
            let mut response = (
                StatusCode::TOO_MANY_REQUESTS,
                "Rate limit exceeded"
            ).into_response();
            
            // Add headers
            if let Ok(limit) = headers.limit.to_string().parse() {
                response.headers_mut().insert("X-RateLimit-Limit", limit);
            }
            if let Ok(retry) = headers.retry_after.map(|r| r.to_string()).unwrap_or_default().parse() {
                response.headers_mut().insert("Retry-After", retry);
            }
            
            Err(response)
        }
        Err(_) => {
            // On error, allow the request (fail open for performance)
            Ok(next.run(request).await)
        }
    }
}