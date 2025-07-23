use crate::error::Error;
use crate::rate_limit::{DistributedRateLimiter, RateLimitDecision};
use axum::{
    extract::{Request, State},
    http::StatusCode,
    middleware::Next,
    response::{IntoResponse, Response},
};
use std::sync::Arc;
use tracing::{debug, warn};

/// Header-based rate limiting middleware
/// 
/// This middleware extracts the model name from a header instead of parsing the body,
/// which allows it to run before body parsing and achieve much better performance.
/// 
/// Clients should pass the model name in the X-Model-Name header for optimal performance.
pub async fn rate_limit_middleware_headers(
    State(limiter): State<Arc<DistributedRateLimiter>>,
    request: Request,
    next: Next,
) -> Result<Response, RateLimitError> {
    // Extract model from header or path
    let model_name = extract_model_from_request(&request)?;
    
    // Extract API key from authorization header
    let api_key = extract_api_key_from_request(&request)
        .unwrap_or_else(|_| "anonymous".to_string());

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

/// Extract model name from request headers or path
fn extract_model_from_request(request: &Request) -> Result<String, RateLimitError> {
    // First, check for X-Model-Name header (fastest path)
    if let Some(model_header) = request.headers().get("x-model-name") {
        if let Ok(model) = model_header.to_str() {
            return Ok(model.to_string());
        }
    }

    // Second, try to extract from URL path
    let path = request.uri().path();
    
    // For paths like /v1/models/{model}/...
    let segments: Vec<&str> = path.split('/').collect();
    if segments.len() >= 4 && segments[1] == "v1" && segments[2] == "models" {
        return Ok(segments[3].to_string());
    }
    
    // For OpenAI endpoints, we'll need to use a default or extract from body later
    // For now, return an error to indicate model extraction is needed
    Err(RateLimitError::ModelNotFound)
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
                        "message": "Model not specified. Please include X-Model-Name header for rate limiting.",
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