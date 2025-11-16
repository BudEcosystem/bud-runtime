use axum::body::{to_bytes, Body};
use axum::extract::{Request, State};
use axum::http::StatusCode;
use axum::middleware::Next;
use axum::response::{IntoResponse, Response};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::sync::{Arc, RwLock};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiKeyMetadata {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub endpoint_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prompt_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub project_id: Option<String>,
}

// Auth metadata from Redis __metadata__ field
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthMetadata {
    pub api_key_id: Option<String>,
    pub user_id: Option<String>,
    pub api_key_project_id: Option<String>,
}

pub type APIConfig = HashMap<String, ApiKeyMetadata>;
pub type PublishedModelInfo = HashMap<String, ApiKeyMetadata>;

// Hash API key using SHA256 with "bud-" prefix (matching Python implementation)
fn hash_api_key(api_key: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(b"bud-");
    hasher.update(api_key.as_bytes());
    format!("{:x}", hasher.finalize())
}

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
    auth_metadata: Arc<RwLock<HashMap<String, AuthMetadata>>>,
}

impl Auth {
    pub fn new(api_keys: HashMap<String, APIConfig>) -> Self {
        Self {
            api_keys: Arc::new(RwLock::new(api_keys)),
            published_model_info: Arc::new(RwLock::new(HashMap::new())),
            auth_metadata: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub fn update_api_keys(&self, api_key: &str, api_config: APIConfig) {
        // In practice, a poisoned RwLock indicates a panic in another thread while holding the lock.
        // This is a catastrophic failure that should not be recovered from.
        #[expect(clippy::expect_used)]
        let mut api_keys = self.api_keys.write().expect("RwLock poisoned");
        api_keys.insert(api_key.to_string(), api_config);
    }

    pub fn update_auth_metadata(&self, api_key: &str, metadata: AuthMetadata) {
        #[expect(clippy::expect_used)]
        let mut auth_metadata = self.auth_metadata.write().expect("RwLock poisoned");
        auth_metadata.insert(api_key.to_string(), metadata);
    }

    pub fn delete_api_key(&self, api_key: &str) {
        #[expect(clippy::expect_used)]
        let mut api_keys = self.api_keys.write().expect("RwLock poisoned");
        api_keys.remove(api_key);

        // Also remove auth metadata
        #[expect(clippy::expect_used)]
        let mut auth_metadata = self.auth_metadata.write().expect("RwLock poisoned");
        auth_metadata.remove(api_key);
    }

    pub fn get_auth_metadata(&self, api_key: &str) -> Option<AuthMetadata> {
        // Hash the API key before lookup (consistent with storage)
        let hashed_key = hash_api_key(api_key);

        #[expect(clippy::expect_used)]
        let auth_metadata = self.auth_metadata.read().expect("RwLock poisoned");
        auth_metadata.get(&hashed_key).cloned()
    }

    pub fn validate_api_key(&self, api_key: &str) -> Result<APIConfig, StatusCode> {
        // Hash the API key before lookup (consistent with Redis storage)
        let hashed_key = hash_api_key(api_key);

        #[expect(clippy::expect_used)]
        let api_keys = self.api_keys.read().expect("RwLock poisoned");
        if let Some(api_config) = api_keys.get(&hashed_key) {
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

    // Extract the key as an owned String to avoid borrowing parts
    let key = parts
        .headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string());

    let key = match key {
        Some(key) => {
            // Strip "Bearer " prefix if present (case-insensitive)
            let key = key.trim();
            key.strip_prefix("Bearer ").unwrap_or(key).to_string()
        }
        None => {
            return Err(auth_error_response(
                StatusCode::UNAUTHORIZED,
                "Missing authorization header",
            ))
        }
    };

    let mut api_config = auth.validate_api_key(&key);
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
    let is_responses_endpoint = path.starts_with("/v1/responses");
    let is_models_list_endpoint = path == "/v1/models";

    let mut request = Request::from_parts(parts, Body::from(bytes.clone()));

    // Special handling for /v1/models endpoint - it lists all available models
    if is_models_list_endpoint {
        // We already checked that api_config is Ok in the if statement above
        #[expect(clippy::unwrap_used)]
        let api_config = api_config.as_ref().unwrap();

        // Get all model names (keys) available to this API key
        let model_names: Vec<String> = api_config
            .keys()
            .filter(|k| !k.starts_with("prompt:")) // Exclude prompt-based keys
            .map(|k| k.to_string())
            .collect();

        // Pass the available models as a comma-separated header
        let models_header = model_names.join(",");
        if let Ok(header_value) = models_header.parse() {
            request
                .headers_mut()
                .insert("x-tensorzero-available-models", header_value);
        }

        // Mark as authenticated - use from_static for known static string
        request.headers_mut().insert(
            "x-tensorzero-endpoint-id",
            axum::http::HeaderValue::from_static("models_list"),
        );

        return Ok(next.run(request).await);
    }

    if !is_batch_or_file_endpoint {
        // Parse the JSON body to validate and extract model name or prompt.id
        let val: Value = match serde_json::from_slice(&bytes) {
            Ok(v) => v,
            Err(_) => {
                return Err(auth_error_response(
                    StatusCode::BAD_REQUEST,
                    "Invalid request body",
                ))
            }
        };

        // Determine lookup key: either model OR prompt.id with prompt: prefix
        let (lookup_key, is_prompt_based, _original_prompt_id) =
            if let Some(model) = val.get("model").and_then(|v| v.as_str()) {
                // Traditional model-based request
                (model.to_string(), false, None)
            } else if let Some(prompt_id) = val
                .get("prompt")
                .and_then(|p| p.get("id"))
                .and_then(|id| id.as_str())
            {
                // Add prompt: prefix for authorization lookup
                (
                    format!("prompt:{}", prompt_id),
                    true,
                    Some(prompt_id.to_string()),
                )
            } else {
                // Provide endpoint-specific error message
                let error_message = if is_responses_endpoint {
                    "Model name or prompt.id required in request body"
                } else {
                    "Missing model name in request body"
                };
                return Err(auth_error_response(StatusCode::BAD_REQUEST, error_message));
            };

        // We already checked that api_config is Ok in the if statement above
        #[expect(clippy::unwrap_used)]
        let api_config = api_config.unwrap();
        let metadata = match api_config.get(&lookup_key) {
            Some(v) => v,
            None => {
                let error_message = if is_prompt_based {
                    // Strip "prompt:" prefix for clearer error message
                    let prompt_id = lookup_key.strip_prefix("prompt:").unwrap_or(&lookup_key);
                    format!("Prompt not found: {}", prompt_id)
                } else {
                    format!("Model not found: {}", lookup_key)
                };
                return Err(auth_error_response(StatusCode::NOT_FOUND, &error_message));
            }
        };

        // Add headers based on request type
        if is_prompt_based {
            // For prompt-based requests, use prompt_id from config for routing
            if let Some(ref prompt_id) = metadata.prompt_id {
                if let Ok(header_value) = prompt_id.parse() {
                    request
                        .headers_mut()
                        .insert("x-tensorzero-prompt-id", header_value);
                }
            }
        } else {
            // For model-based requests, add the model name header
            if let Ok(header_value) = lookup_key.parse() {
                request
                    .headers_mut()
                    .insert("x-tensorzero-model-name", header_value);
            }
            // For model-based requests, set endpoint_id for routing
            if let Some(ref endpoint_id) = metadata.endpoint_id {
                if let Ok(header_value) = endpoint_id.parse() {
                    request
                        .headers_mut()
                        .insert("x-tensorzero-endpoint-id", header_value);
                }
            }
        }

        // Add metadata headers for observability (if present)
        if let Some(ref project_id) = metadata.project_id {
            if let Ok(header_value) = project_id.parse() {
                request
                    .headers_mut()
                    .insert("x-tensorzero-project-id", header_value);
            }
        }

        // Add model_id header if present (optional for prompt-based requests)
        if let Some(ref model_id) = metadata.model_id {
            if let Ok(header_value) = model_id.parse() {
                request
                    .headers_mut()
                    .insert("x-tensorzero-model-id", header_value);
            }
        }

        // Add auth metadata headers if available
        if let Some(auth_meta) = auth.get_auth_metadata(&key) {
            if let Some(api_key_id) = auth_meta.api_key_id {
                if let Ok(header_value) = api_key_id.parse() {
                    request
                        .headers_mut()
                        .insert("x-tensorzero-api-key-id", header_value);
                }
            }
            if let Some(user_id) = auth_meta.user_id {
                if let Ok(header_value) = user_id.parse() {
                    request
                        .headers_mut()
                        .insert("x-tensorzero-user-id", header_value);
                }
            }
            if let Some(api_key_project_id) = auth_meta.api_key_project_id {
                if let Ok(header_value) = api_key_project_id.parse() {
                    request
                        .headers_mut()
                        .insert("x-tensorzero-api-key-project-id", header_value);
                }
            }
        }
    }

    Ok(next.run(request).await)
}
