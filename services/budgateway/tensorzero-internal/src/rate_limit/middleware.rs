use crate::error::Error;
use crate::rate_limit::early_extract::ExtractedModel;
use crate::rate_limit::{DistributedRateLimiter, RateLimitDecision};
use axum::{
    body::Body,
    extract::{Request, State},
    http::StatusCode,
    middleware::Next,
    response::{IntoResponse, Response},
};
use serde_json::Value;
use std::sync::Arc;
use tracing::{debug, warn};

/// Unified rate limiting middleware
///
/// This middleware combines the best features from all previous implementations:
/// - Prioritizes resolved endpoint ID from authentication for accurate rate limiting
/// - Checks pre-extracted model from early extraction layer
/// - Falls back to X-Model-Name header
/// - Falls back to URL path extraction
/// - Falls back to body parsing only when necessary
pub async fn rate_limit_middleware(
    State(limiter): State<Arc<DistributedRateLimiter>>,
    mut request: Request,
    next: Next,
) -> Result<Response, RateLimitError> {
    // Extract model name using the best available method
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

/// Extract model name from the request using multiple strategies
async fn extract_model_from_request(request: &mut Request) -> Result<String, RateLimitError> {
    // Strategy 1: Check for resolved endpoint ID from authentication (highest priority for rate limiting)
    if let Some(endpoint_id_header) = request.headers().get("x-tensorzero-endpoint-id") {
        if let Ok(endpoint_id) = endpoint_id_header.to_str() {
            debug!(
                "Using resolved endpoint ID for rate limiting: {}",
                endpoint_id
            );
            return Ok(endpoint_id.to_string());
        }
    }

    // Strategy 2: Check for prompt ID from authentication (for prompt-based requests)
    if let Some(prompt_id_header) = request.headers().get("x-tensorzero-prompt-id") {
        if let Ok(prompt_id) = prompt_id_header.to_str() {
            debug!("Using prompt ID for rate limiting: {}", prompt_id);
            return Ok(prompt_id.to_string());
        }
    }

    // Strategy 3: Check for pre-extracted model from early extraction layer
    if let Some(extracted) = request.extensions().get::<ExtractedModel>() {
        debug!("Using pre-extracted model: {}", extracted.0);
        return Ok(extracted.0.clone());
    }

    // Strategy 4: Check for X-Model-Name header (fastest path)
    if let Some(model_header) = request.headers().get("x-model-name") {
        if let Ok(model) = model_header.to_str() {
            debug!("Extracted model from X-Model-Name header: {}", model);
            return Ok(model.to_string());
        }
    }

    // Strategy 5: Try to extract from URL path
    let path = request.uri().path().to_string(); // Clone the path to avoid borrow issues
    if let Some(model) = try_extract_from_path(&path) {
        debug!("Extracted model from URL path: {}", model);
        return Ok(model);
    }

    // Strategy 6: Try to extract from request body (slowest path, only for POST)
    if request.method() == axum::http::Method::POST {
        // Read the body
        let body = std::mem::replace(request.body_mut(), Body::empty());
        let bytes = match axum::body::to_bytes(body, usize::MAX).await {
            Ok(bytes) => bytes,
            Err(_) => {
                debug!("Failed to read request body for model extraction");
                return Err(RateLimitError::ModelNotFound);
            }
        };

        // Try to parse as JSON and extract model field
        if let Ok(json_str) = std::str::from_utf8(&bytes) {
            if let Ok(json_value) = serde_json::from_str::<Value>(json_str) {
                if let Some(model) = json_value.get("model").and_then(|m| m.as_str()) {
                    // Reconstruct the request body for the next handler
                    *request.body_mut() = Body::from(bytes);
                    debug!("Extracted model from request body: {}", model);
                    return Ok(model.to_string());
                }
            }
        }

        // Reconstruct the request body even if we couldn't parse it
        *request.body_mut() = Body::from(bytes);
    }

    // No model found anywhere
    debug!(
        "Could not determine model for rate limiting on path: {}. \
        Consider using early extraction layer or X-Model-Name header for better performance.",
        path
    );
    Err(RateLimitError::ModelNotFound)
}

/// Try to extract model name from URL path
fn try_extract_from_path(path: &str) -> Option<String> {
    // For paths like /v1/models/{model}/...
    let segments: Vec<&str> = path.split('/').collect();

    // Look for model patterns in different endpoints
    if segments.len() >= 4 && segments[1] == "v1" && segments[2] == "models" {
        return Some(segments[3].to_string());
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
                        "message": "Could not determine model from request. For optimal performance, use the X-Model-Name header or ensure the 'model' field is present in the JSON body.",
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

    #[tokio::test]
    async fn test_extract_model_prioritizes_endpoint_id() {
        use axum::http::{HeaderMap, HeaderValue, Method};

        let mut headers = HeaderMap::new();
        // Set both headers - endpoint ID should take priority
        headers.insert(
            "x-tensorzero-endpoint-id",
            HeaderValue::from_static("6eb1afa1-281f-4023-bc4f-4531c3e2100d"),
        );
        headers.insert(
            "x-tensorzero-model-name",
            HeaderValue::from_static("voice-assistant"),
        );

        let mut req_with_headers = Request::builder()
            .method(Method::POST)
            .uri("/v1/chat/completions");

        for (key, value) in headers.iter() {
            req_with_headers = req_with_headers.header(key, value);
        }

        let mut request = req_with_headers
            .body(Body::from(
                r#"{"model": "voice-assistant", "messages": []}"#,
            ))
            .unwrap();

        let model_name = extract_model_from_request(&mut request).await.unwrap();
        // Should use endpoint ID, not the original model name
        assert_eq!(model_name, "6eb1afa1-281f-4023-bc4f-4531c3e2100d");
    }
}
