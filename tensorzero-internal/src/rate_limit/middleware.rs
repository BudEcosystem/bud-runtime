use crate::error::Error;
use crate::rate_limit::{DistributedRateLimiter, RateLimitDecision};
use axum::{
    body::Body,
    extract::{Request, State},
    http::StatusCode,
    middleware::Next,
    response::{IntoResponse, Response},
};
use bytes::Bytes;
use serde_json::Value;
use std::sync::Arc;
use tracing::{debug, warn};

/// Rate limiting middleware for Axum
pub async fn rate_limit_middleware(
    State(limiter): State<Arc<DistributedRateLimiter>>,
    mut request: Request,
    next: Next,
) -> Result<Response, RateLimitError> {
    // Extract model name from the request path or body
    let model_name = extract_model_from_request(&mut request).await?;

    // Extract API key from authorization header (use "anonymous" if no auth)
    let api_key =
        extract_api_key_from_request(&request).unwrap_or_else(|_| "anonymous".to_string());

    debug!(model = model_name, "Checking rate limit");

    // Check rate limit
    match limiter.check_rate_limit(&model_name, &api_key).await {
        Ok(RateLimitDecision::Allow(headers)) => {
            debug!(
                model = model_name,
                remaining = headers.remaining,
                "Rate limit check passed"
            );

            // Continue with the request
            let mut response = next.run(request).await;

            // Add rate limit headers to response
            let header_map = headers.to_header_map();
            response.headers_mut().extend(header_map);

            Ok(response)
        }
        Ok(RateLimitDecision::Deny(headers)) => {
            warn!(
                model = model_name,
                remaining = headers.remaining,
                "Rate limit exceeded"
            );

            Err(RateLimitError::Exceeded(headers))
        }
        Err(e) => {
            warn!(
                model = model_name,
                error = %e,
                "Rate limit check failed"
            );

            Err(RateLimitError::InternalError(e))
        }
    }
}

/// Extract model name from the request path or body
async fn extract_model_from_request(request: &mut Request) -> Result<String, RateLimitError> {
    let path = request.uri().path();

    // Try to extract model from various OpenAI-compatible endpoints
    if let Some(model) = try_extract_from_path(path) {
        return Ok(model);
    }

    // Try to extract from request body (for POST requests with JSON bodies)
    if request.method() == axum::http::Method::POST {
        // Read the body
        let body = std::mem::replace(request.body_mut(), Body::empty());
        let bytes = match axum::body::to_bytes(body, usize::MAX).await {
            Ok(bytes) => bytes,
            Err(_) => return Err(RateLimitError::ModelNotFound),
        };

        // Try to parse as JSON and extract model field
        if let Ok(json_str) = std::str::from_utf8(&bytes) {
            if let Ok(json_value) = serde_json::from_str::<Value>(json_str) {
                if let Some(model) = json_value.get("model").and_then(|m| m.as_str()) {
                    // Reconstruct the request body for the next handler
                    *request.body_mut() = Body::from(bytes);
                    return Ok(model.to_string());
                }
            }
        }

        // Reconstruct the request body even if we couldn't parse it
        *request.body_mut() = Body::from(bytes);
    }

    // Fallback to a default model or error
    Err(RateLimitError::ModelNotFound)
}

/// Try to extract model name from URL path
fn try_extract_from_path(path: &str) -> Option<String> {
    // For paths like /v1/models/{model}/...
    let segments: Vec<&str> = path.split('/').collect();

    // Look for model patterns in different endpoints
    if segments.len() >= 4 {
        if segments[1] == "v1" && segments[2] == "models" {
            return Some(segments[3].to_string());
        }
    }

    None
}

/// Extract API key from authorization header
fn extract_api_key_from_request(request: &Request) -> Result<String, RateLimitError> {
    let headers = request.headers();

    if let Some(auth_header) = headers.get("authorization") {
        if let Ok(auth_str) = auth_header.to_str() {
            if let Some(key) = auth_str.strip_prefix("Bearer ") {
                return Ok(key.to_string());
            }
        }
    }

    // Try X-API-Key header as fallback
    if let Some(api_key_header) = headers.get("x-api-key") {
        if let Ok(key) = api_key_header.to_str() {
            return Ok(key.to_string());
        }
    }

    Err(RateLimitError::ApiKeyMissing)
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
                    serde_json::json!({
                        "error": {
                            "message": "Rate limit exceeded",
                            "type": "rate_limit_error",
                            "code": "rate_limit_exceeded"
                        }
                    })
                    .to_string(),
                )
                    .into_response();

                // Add rate limit headers
                let header_map = headers.to_header_map();
                response.headers_mut().extend(header_map);

                response
            }
            RateLimitError::ModelNotFound => (
                StatusCode::BAD_REQUEST,
                serde_json::json!({
                    "error": {
                        "message": "Could not determine model from request",
                        "type": "invalid_request_error",
                        "code": "model_not_found"
                    }
                })
                .to_string(),
            )
                .into_response(),
            RateLimitError::ApiKeyMissing => (
                StatusCode::UNAUTHORIZED,
                serde_json::json!({
                    "error": {
                        "message": "No API key provided",
                        "type": "authentication_error",
                        "code": "api_key_missing"
                    }
                })
                .to_string(),
            )
                .into_response(),
            RateLimitError::InternalError(_e) => (
                StatusCode::INTERNAL_SERVER_ERROR,
                serde_json::json!({
                    "error": {
                        "message": "Internal server error during rate limiting",
                        "type": "internal_server_error",
                        "code": "internal_error"
                    }
                })
                .to_string(),
            )
                .into_response(),
        }
    }
}

// Helper function to create rate limiting layer - users can call axum::middleware::from_fn_with_state directly

/// Conditional rate limiting middleware - only applies if rate limiting is enabled
pub async fn conditional_rate_limit_middleware(
    State((limiter, enabled)): State<(Arc<DistributedRateLimiter>, bool)>,
    request: Request,
    next: Next,
) -> Result<Response, RateLimitError> {
    if enabled {
        // Use the regular rate limit middleware
        rate_limit_middleware(State(limiter), request, next).await
    } else {
        // Skip rate limiting
        Ok(next.run(request).await)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::Body;
    use axum::http::{HeaderMap, HeaderValue, Method};

    #[test]
    fn test_extract_api_key_from_bearer() {
        let mut headers = HeaderMap::new();
        headers.insert(
            "authorization",
            HeaderValue::from_static("Bearer sk-test-key-123"),
        );

        let _request = Request::builder()
            .method(Method::GET)
            .uri("/test")
            .body(())
            .unwrap();

        let mut req_with_headers = Request::builder().method(Method::GET).uri("/test");

        for (key, value) in headers.iter() {
            req_with_headers = req_with_headers.header(key, value);
        }

        let request = req_with_headers.body(Body::empty()).unwrap();

        let api_key = extract_api_key_from_request(&request).unwrap();
        assert_eq!(api_key, "sk-test-key-123");
    }

    #[test]
    fn test_extract_api_key_from_x_api_key() {
        let mut headers = HeaderMap::new();
        headers.insert("x-api-key", HeaderValue::from_static("sk-test-key-456"));

        let mut req_with_headers = Request::builder().method(Method::GET).uri("/test");

        for (key, value) in headers.iter() {
            req_with_headers = req_with_headers.header(key, value);
        }

        let request = req_with_headers.body(Body::empty()).unwrap();

        let api_key = extract_api_key_from_request(&request).unwrap();
        assert_eq!(api_key, "sk-test-key-456");
    }

    #[test]
    fn test_try_extract_from_path() {
        assert_eq!(
            try_extract_from_path("/v1/models/gpt-4/completions"),
            Some("gpt-4".to_string())
        );

        assert_eq!(try_extract_from_path("/v1/chat/completions"), None);
    }
}
