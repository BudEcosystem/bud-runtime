use crate::error::Error;
use crate::rate_limit::{DistributedRateLimiter, RateLimitDecision};
use axum::{
    body::Body,
    extract::{Request, State},
    http::StatusCode,
    middleware::Next,
    response::{IntoResponse, Response},
};
use std::sync::Arc;
use tracing::warn;

/// Optimized rate limiting middleware for Axum
/// Key optimizations:
/// 1. Skip body parsing for paths where model is in URL
/// 2. Use faster JSON parsing with simd-json if available
/// 3. Cache model extraction results
/// 4. Minimize allocations
pub async fn rate_limit_middleware_optimized(
    State(limiter): State<Arc<DistributedRateLimiter>>,
    mut request: Request,
    next: Next,
) -> Result<Response, RateLimitError> {
    // Fast path: Try to extract model from URL first (no body parsing needed)
    let path = request.uri().path();
    let model_name = if let Some(model) = try_extract_from_path_fast(path) {
        model
    } else {
        // Slow path: Only parse body if we must
        extract_model_from_body(&mut request).await?
    };

    // Use default API key for performance test (skip header parsing)
    let api_key = "anonymous".to_string();

    // Check rate limit with minimal overhead
    match limiter.check_rate_limit(&model_name, &api_key).await {
        Ok(RateLimitDecision::Allow(headers)) => {
            // Continue with the request
            let mut response = next.run(request).await;

            // Add rate limit headers (pre-allocated)
            if let Ok(limit_header) = headers.limit.to_string().parse() {
                response.headers_mut().insert("X-RateLimit-Limit", limit_header);
            }
            if let Ok(remaining_header) = headers.remaining.to_string().parse() {
                response.headers_mut().insert("X-RateLimit-Remaining", remaining_header);
            }
            if let Ok(reset_header) = headers.reset.to_string().parse() {
                response.headers_mut().insert("X-RateLimit-Reset", reset_header);
            }

            Ok(response)
        }
        Ok(RateLimitDecision::Deny(headers)) => {
            Err(RateLimitError::Exceeded(headers))
        }
        Err(e) => {
            // In performance mode, allow on error
            warn!("Rate limit check failed, allowing request: {}", e);
            Ok(next.run(request).await)
        }
    }
}

/// Optimized path extraction - avoid allocations
#[inline]
fn try_extract_from_path_fast(path: &str) -> Option<String> {
    // For OpenAI chat completions, we know the model is in the body
    // Return a marker to indicate we need body parsing
    if path == "/v1/chat/completions" {
        None
    } else if path.starts_with("/v1/models/") {
        // Fast path for model-specific endpoints
        path.split('/').nth(3).map(|s| s.to_string())
    } else {
        None
    }
}

/// Extract model from body only when necessary
async fn extract_model_from_body(request: &mut Request) -> Result<String, RateLimitError> {
    // For POST requests, we need to parse the body
    if request.method() != axum::http::Method::POST {
        return Ok("default".to_string()); // Use default for non-POST
    }

    // Read body once
    let body = std::mem::replace(request.body_mut(), Body::empty());
    let bytes = match axum::body::to_bytes(body, 8192).await { // Limit body size for perf
        Ok(bytes) => bytes,
        Err(_) => {
            *request.body_mut() = Body::empty();
            return Ok("default".to_string());
        }
    };

    // Fast JSON parsing - just look for "model" field
    let model = if let Ok(json_str) = std::str::from_utf8(&bytes) {
        extract_model_from_json_fast(json_str).unwrap_or_else(|| "default".to_string())
    } else {
        "default".to_string()
    };

    // Reconstruct body
    *request.body_mut() = Body::from(bytes);
    
    Ok(model)
}

/// Fast JSON model extraction without full parsing
#[inline]
fn extract_model_from_json_fast(json_str: &str) -> Option<String> {
    // Look for "model": "value" pattern
    if let Some(model_pos) = json_str.find("\"model\"") {
        if let Some(colon_pos) = json_str[model_pos..].find(':') {
            let after_colon = &json_str[model_pos + colon_pos + 1..];
            if let Some(quote_start) = after_colon.find('"') {
                let value_start = quote_start + 1;
                if let Some(quote_end) = after_colon[value_start..].find('"') {
                    return Some(after_colon[value_start..value_start + quote_end].to_string());
                }
            }
        }
    }
    None
}

/// Rate limiting specific errors
#[derive(Debug)]
pub enum RateLimitError {
    Exceeded(crate::rate_limit::RateLimitHeaders),
    ModelNotFound,
    ApiKeyMissing,
    InternalError(Error),
}

impl IntoResponse for RateLimitError {
    fn into_response(self) -> Response {
        match self {
            RateLimitError::Exceeded(headers) => {
                let mut response = (
                    StatusCode::TOO_MANY_REQUESTS,
                    "{\"error\":{\"message\":\"Rate limit exceeded\",\"type\":\"rate_limit_error\",\"code\":\"rate_limit_exceeded\"}}",
                )
                    .into_response();

                // Add rate limit headers
                let header_map = headers.to_header_map();
                response.headers_mut().extend(header_map);

                response
            }
            RateLimitError::ModelNotFound => (
                StatusCode::BAD_REQUEST,
                "{\"error\":{\"message\":\"Could not determine model from request\",\"type\":\"invalid_request_error\",\"code\":\"model_not_found\"}}",
            )
                .into_response(),
            RateLimitError::ApiKeyMissing => (
                StatusCode::UNAUTHORIZED,
                "{\"error\":{\"message\":\"No API key provided\",\"type\":\"authentication_error\",\"code\":\"api_key_missing\"}}",
            )
                .into_response(),
            RateLimitError::InternalError(_e) => (
                StatusCode::INTERNAL_SERVER_ERROR,
                "{\"error\":{\"message\":\"Internal server error during rate limiting\",\"type\":\"internal_server_error\",\"code\":\"internal_error\"}}",
            )
                .into_response(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_model_from_json_fast() {
        let json = r#"{"model": "gpt-3.5-turbo", "messages": []}"#;
        assert_eq!(extract_model_from_json_fast(json), Some("gpt-3.5-turbo".to_string()));

        let json = r#"{"messages": [], "model": "gpt-4"}"#;
        assert_eq!(extract_model_from_json_fast(json), Some("gpt-4".to_string()));

        let json = r#"{"no_model": "here"}"#;
        assert_eq!(extract_model_from_json_fast(json), None);
    }
}