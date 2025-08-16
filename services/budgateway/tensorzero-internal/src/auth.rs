use axum::body::{to_bytes, Body};
use axum::extract::{Request, State};
use axum::http::StatusCode;
use axum::middleware::Next;
use axum::response::{IntoResponse, Response};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::sync::{Arc, RwLock};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiKeyMetadata {
    pub endpoint_id: String,
    pub model_id: String,
    pub project_id: String,
}

pub type APIConfig = HashMap<String, ApiKeyMetadata>;
pub type PublishedModelInfo = HashMap<String, ApiKeyMetadata>;

// Common error response helper
fn auth_error_response(status: StatusCode, message: &str) -> Response {
    let body = serde_json::json!({
        "error": {
            "message": message,
            "type": "invalid_request_error",
            "code": status.as_u16()
        }
    });
    (status, axum::Json(body)).into_response()
}

#[derive(Clone)]
pub struct Auth {
    api_keys: Arc<RwLock<HashMap<String, APIConfig>>>,
    published_model_info: Arc<RwLock<PublishedModelInfo>>,
}

impl Auth {
    pub fn new(api_keys: HashMap<String, APIConfig>) -> Self {
        Self {
            api_keys: Arc::new(RwLock::new(api_keys)),
            published_model_info: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub fn update_api_keys(&self, api_key: &str, api_config: APIConfig) {
        // In practice, a poisoned RwLock indicates a panic in another thread while holding the lock.
        // This is a catastrophic failure that should not be recovered from.
        #[expect(clippy::expect_used)]
        let mut api_keys = self.api_keys.write().expect("RwLock poisoned");
        api_keys.insert(api_key.to_string(), api_config);
    }

    pub fn delete_api_key(&self, api_key: &str) {
        #[expect(clippy::expect_used)]
        let mut api_keys = self.api_keys.write().expect("RwLock poisoned");
        api_keys.remove(api_key);
    }

    pub fn validate_api_key(&self, api_key: &str) -> Result<APIConfig, StatusCode> {
        #[expect(clippy::expect_used)]
        let api_keys = self.api_keys.read().expect("RwLock poisoned");
        if let Some(api_config) = api_keys.get(api_key) {
            return Ok(api_config.clone());
        }
        Err(StatusCode::UNAUTHORIZED)
    }

    pub fn update_published_model_info(&self, model_info: PublishedModelInfo) {
        #[expect(clippy::expect_used)]
        let mut published_model_info = self.published_model_info.write().expect("RwLock poisoned");
        *published_model_info = model_info;
    }

    pub fn clear_published_model_info(&self) {
        #[expect(clippy::expect_used)]
        let mut published_model_info = self.published_model_info.write().expect("RwLock poisoned");
        published_model_info.clear();
    }

    pub fn get_published_model_info(&self) -> PublishedModelInfo {
        #[expect(clippy::expect_used)]
        let published_model_info = self.published_model_info.read().expect("RwLock poisoned");
        published_model_info.clone()
    }
}

pub async fn require_api_key(
    State(auth): State<Auth>,
    request: Request,
    next: Next,
) -> Result<Response, Response> {
    let (parts, body) = request.into_parts();
    let bytes = to_bytes(body, 1024 * 1024).await.unwrap_or_default();

    let key = parts
        .headers
        .get("authorization")
        .and_then(|v| v.to_str().ok());

    let key = match key {
        Some(key) => {
            // Strip "Bearer " prefix if present (case-insensitive)
            let key = key.trim();
            key.strip_prefix("Bearer ").unwrap_or(key)
        }
        None => {
            return Err(auth_error_response(
                StatusCode::UNAUTHORIZED,
                "Missing authorization header",
            ))
        }
    };

    let mut api_config = auth.validate_api_key(key);
    if api_config.is_err() {
        return Err(auth_error_response(
            StatusCode::UNAUTHORIZED,
            "Invalid API key",
        ));
    }

    // If the key starts with 'bud_client', extend api_config with published_model_info
    if key.starts_with("bud_client") {
        #[expect(clippy::unwrap_used)]
        let mut config = api_config.unwrap();
        let published_models = auth.get_published_model_info();
        // Extend the config with published model info
        config.extend(published_models);
        api_config = Ok(config);
    }

    // Check if this is a batch or file endpoint (which don't require model validation)
    let path = parts.uri.path();
    let is_batch_or_file_endpoint =
        path.starts_with("/v1/batches") || path.starts_with("/v1/files");

    let mut request = Request::from_parts(parts, Body::from(bytes.clone()));

    if !is_batch_or_file_endpoint {
        // Parse the JSON body to validate and extract model name
        let val: Value = match serde_json::from_slice(&bytes) {
            Ok(v) => v,
            Err(_) => {
                return Err(auth_error_response(
                    StatusCode::BAD_REQUEST,
                    "Invalid request body",
                ))
            }
        };

        let model = match val.get("model").and_then(|v| v.as_str()) {
            Some(m) => m,
            None => {
                return Err(auth_error_response(
                    StatusCode::BAD_REQUEST,
                    "Missing model name in request body",
                ))
            }
        };

        // We already checked that api_config is Ok in the if statement above
        #[expect(clippy::unwrap_used)]
        let api_config = api_config.unwrap();
        let metadata = match api_config.get(model) {
            Some(v) => v,
            None => {
                return Err(auth_error_response(
                    StatusCode::NOT_FOUND,
                    &format!("Model not found: {model}"),
                ))
            }
        };

        // Add the model name as a custom header for downstream handlers
        if let Ok(header_value) = model.parse() {
            request
                .headers_mut()
                .insert("x-tensorzero-model-name", header_value);
        }

        // Add metadata headers for observability
        if let Ok(header_value) = metadata.project_id.parse() {
            request
                .headers_mut()
                .insert("x-tensorzero-project-id", header_value);
        }
        if let Ok(header_value) = metadata.endpoint_id.parse() {
            request
                .headers_mut()
                .insert("x-tensorzero-endpoint-id", header_value);
        }
        if let Ok(header_value) = metadata.model_id.parse() {
            request
                .headers_mut()
                .insert("x-tensorzero-model-id", header_value);
        }
    }

    Ok(next.run(request).await)
}
