//! W3C Baggage support for propagating business context to downstream services.
//!
//! This module provides utilities for attaching business context (project_id, prompt_id,
//! endpoint_id, etc.) to OpenTelemetry baggage for downstream propagation to services
//! like budprompt.
//!
//! # Security Considerations
//! - Baggage is visible in HTTP headers - only UUIDs are propagated (no PII)
//! - Keys are prefixed with "bud." to avoid collisions with external baggage
//! - Maximum baggage size is ~200 bytes (well under W3C 8KB limit)

use opentelemetry::{baggage::BaggageExt, Context, KeyValue};

/// Baggage key constants with "bud." prefix to avoid collisions
pub mod keys {
    /// Project ID key for baggage
    pub const PROJECT_ID: &str = "bud.project_id";
    /// Prompt ID key for baggage
    pub const PROMPT_ID: &str = "bud.prompt_id";
    /// Endpoint ID key for baggage
    pub const ENDPOINT_ID: &str = "bud.endpoint_id";
    /// API Key ID key for baggage
    pub const API_KEY_ID: &str = "bud.api_key_id";
    /// User ID key for baggage
    pub const USER_ID: &str = "bud.user_id";
}

/// Creates a new Context with baggage entries from the provided values.
///
/// Only non-None values are added to baggage. The base context is preserved,
/// allowing trace context to be maintained while adding business context.
///
/// # Arguments
/// * `base_context` - The existing context (typically with trace propagation)
/// * `project_id` - Optional project identifier
/// * `prompt_id` - Optional prompt identifier
/// * `endpoint_id` - Optional endpoint identifier
/// * `api_key_id` - Optional API key identifier
/// * `user_id` - Optional user identifier
///
/// # Returns
/// A new Context with baggage entries attached
pub fn context_with_baggage(
    base_context: Context,
    project_id: Option<&str>,
    prompt_id: Option<&str>,
    endpoint_id: Option<&str>,
    api_key_id: Option<&str>,
    user_id: Option<&str>,
) -> Context {
    let mut baggage_items: Vec<KeyValue> = Vec::with_capacity(5);

    if let Some(id) = project_id {
        baggage_items.push(KeyValue::new(keys::PROJECT_ID, id.to_string()));
    }
    if let Some(id) = prompt_id {
        baggage_items.push(KeyValue::new(keys::PROMPT_ID, id.to_string()));
    }
    if let Some(id) = endpoint_id {
        baggage_items.push(KeyValue::new(keys::ENDPOINT_ID, id.to_string()));
    }
    if let Some(id) = api_key_id {
        baggage_items.push(KeyValue::new(keys::API_KEY_ID, id.to_string()));
    }
    if let Some(id) = user_id {
        baggage_items.push(KeyValue::new(keys::USER_ID, id.to_string()));
    }

    if baggage_items.is_empty() {
        base_context
    } else {
        base_context.with_baggage(baggage_items)
    }
}

/// Baggage data for propagation to downstream services
/// This struct holds business context that should be propagated to downstream services
/// like budprompt via W3C Baggage headers.
#[derive(Debug, Clone, Default)]
pub struct BaggageData {
    pub project_id: Option<String>,
    pub prompt_id: Option<String>,
    pub endpoint_id: Option<String>,
    pub api_key_id: Option<String>,
    pub user_id: Option<String>,
}

impl BaggageData {
    /// Create BaggageData from HTTP headers (set by auth middleware)
    pub fn from_headers(headers: &http::HeaderMap) -> Self {
        Self {
            project_id: headers
                .get("x-tensorzero-project-id")
                .and_then(|v| v.to_str().ok())
                .map(|s| s.to_string()),
            prompt_id: headers
                .get("x-tensorzero-prompt-id")
                .and_then(|v| v.to_str().ok())
                .map(|s| s.to_string()),
            endpoint_id: headers
                .get("x-tensorzero-endpoint-id")
                .and_then(|v| v.to_str().ok())
                .map(|s| s.to_string()),
            api_key_id: headers
                .get("x-tensorzero-api-key-id")
                .and_then(|v| v.to_str().ok())
                .map(|s| s.to_string()),
            user_id: headers
                .get("x-tensorzero-user-id")
                .and_then(|v| v.to_str().ok())
                .map(|s| s.to_string()),
        }
    }

    /// Attach this baggage data to a context
    pub fn attach_to_context(&self, base_context: Context) -> Context {
        context_with_baggage(
            base_context,
            self.project_id.as_deref(),
            self.prompt_id.as_deref(),
            self.endpoint_id.as_deref(),
            self.api_key_id.as_deref(),
            self.user_id.as_deref(),
        )
    }

    /// Check if any baggage data is present
    pub fn has_data(&self) -> bool {
        self.project_id.is_some()
            || self.prompt_id.is_some()
            || self.endpoint_id.is_some()
            || self.api_key_id.is_some()
            || self.user_id.is_some()
    }
}

/// Shared container for passing baggage data between middleware layers.
/// Analytics middleware creates this and inserts into request extensions.
/// Auth middleware populates it with baggage data.
/// Analytics middleware reads it after next.run() to set span attributes.
pub type SharedBaggageData = std::sync::Arc<std::sync::Mutex<Option<BaggageData>>>;

/// Create a new shared baggage container
pub fn new_shared_baggage() -> SharedBaggageData {
    std::sync::Arc::new(std::sync::Mutex::new(None))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_context_with_baggage_all_values() {
        let base_ctx = Context::new();
        let ctx = context_with_baggage(
            base_ctx,
            Some("proj-123"),
            Some("prompt-456"),
            Some("endpoint-789"),
            Some("key-abc"),
            Some("user-xyz"),
        );

        let baggage = ctx.baggage();
        assert_eq!(
            baggage.get(keys::PROJECT_ID).map(|v| v.as_str()),
            Some("proj-123")
        );
        assert_eq!(
            baggage.get(keys::PROMPT_ID).map(|v| v.as_str()),
            Some("prompt-456")
        );
        assert_eq!(
            baggage.get(keys::ENDPOINT_ID).map(|v| v.as_str()),
            Some("endpoint-789")
        );
        assert_eq!(
            baggage.get(keys::API_KEY_ID).map(|v| v.as_str()),
            Some("key-abc")
        );
        assert_eq!(
            baggage.get(keys::USER_ID).map(|v| v.as_str()),
            Some("user-xyz")
        );
    }

    #[test]
    fn test_context_with_baggage_partial_values() {
        let base_ctx = Context::new();
        let ctx = context_with_baggage(base_ctx, Some("proj-123"), None, None, None, None);

        let baggage = ctx.baggage();
        assert_eq!(
            baggage.get(keys::PROJECT_ID).map(|v| v.as_str()),
            Some("proj-123")
        );
        assert!(baggage.get(keys::PROMPT_ID).is_none());
        assert!(baggage.get(keys::ENDPOINT_ID).is_none());
        assert!(baggage.get(keys::API_KEY_ID).is_none());
        assert!(baggage.get(keys::USER_ID).is_none());
    }

    #[test]
    fn test_context_with_baggage_no_values() {
        let base_ctx = Context::new();
        let ctx = context_with_baggage(base_ctx.clone(), None, None, None, None, None);

        // Should return the same context when no values provided
        let baggage = ctx.baggage();
        assert!(baggage.get(keys::PROJECT_ID).is_none());
        assert!(baggage.get(keys::PROMPT_ID).is_none());
    }

    #[test]
    fn test_context_with_baggage_replaces_existing() {
        // Note: with_baggage replaces existing baggage rather than merging.
        // This is fine for our use case since incoming requests won't have
        // bud.* baggage - we set it fresh at the gateway.
        let initial_baggage = vec![KeyValue::new("existing.key", "existing-value")];
        let base_ctx = Context::new().with_baggage(initial_baggage);

        let ctx = context_with_baggage(base_ctx, Some("proj-123"), None, None, None, None);

        let baggage = ctx.baggage();
        // New baggage should be present
        assert_eq!(
            baggage.get(keys::PROJECT_ID).map(|v| v.as_str()),
            Some("proj-123")
        );
        // Note: Existing baggage is replaced (OTel behavior), not merged
        // This is acceptable for our use case
    }

    #[test]
    fn test_baggage_data_from_headers() {
        let mut headers = http::HeaderMap::new();
        headers.insert("x-tensorzero-project-id", "proj-123".parse().unwrap());
        headers.insert("x-tensorzero-prompt-id", "prompt-456".parse().unwrap());
        headers.insert("x-tensorzero-endpoint-id", "endpoint-789".parse().unwrap());
        headers.insert("x-tensorzero-api-key-id", "key-abc".parse().unwrap());
        headers.insert("x-tensorzero-user-id", "user-xyz".parse().unwrap());

        let baggage_data = BaggageData::from_headers(&headers);

        assert_eq!(baggage_data.project_id, Some("proj-123".to_string()));
        assert_eq!(baggage_data.prompt_id, Some("prompt-456".to_string()));
        assert_eq!(baggage_data.endpoint_id, Some("endpoint-789".to_string()));
        assert_eq!(baggage_data.api_key_id, Some("key-abc".to_string()));
        assert_eq!(baggage_data.user_id, Some("user-xyz".to_string()));
        assert!(baggage_data.has_data());
    }

    #[test]
    fn test_baggage_data_from_empty_headers() {
        let headers = http::HeaderMap::new();
        let baggage_data = BaggageData::from_headers(&headers);

        assert!(baggage_data.project_id.is_none());
        assert!(baggage_data.prompt_id.is_none());
        assert!(baggage_data.endpoint_id.is_none());
        assert!(baggage_data.api_key_id.is_none());
        assert!(baggage_data.user_id.is_none());
        assert!(!baggage_data.has_data());
    }

    #[test]
    fn test_baggage_data_attach_to_context() {
        let baggage_data = BaggageData {
            project_id: Some("proj-123".to_string()),
            prompt_id: Some("prompt-456".to_string()),
            endpoint_id: None,
            api_key_id: None,
            user_id: None,
        };

        let base_ctx = Context::new();
        let ctx = baggage_data.attach_to_context(base_ctx);

        let baggage = ctx.baggage();
        assert_eq!(
            baggage.get(keys::PROJECT_ID).map(|v| v.as_str()),
            Some("proj-123")
        );
        assert_eq!(
            baggage.get(keys::PROMPT_ID).map(|v| v.as_str()),
            Some("prompt-456")
        );
        assert!(baggage.get(keys::ENDPOINT_ID).is_none());
    }
}
