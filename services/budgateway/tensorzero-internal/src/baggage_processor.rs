//! Custom SpanProcessor that copies W3C Baggage to span attributes.
//!
//! This processor runs on every span start and copies any baggage values
//! from the Context to the span as attributes, enabling observability
//! of business context (project_id, prompt_id, etc.) in Grafana/Tempo.

use opentelemetry::baggage::BaggageExt;
use opentelemetry::trace::Span as OtelSpan;
use opentelemetry::{Context, KeyValue};
use opentelemetry_sdk::error::OTelSdkResult;
use opentelemetry_sdk::trace::{Span, SpanData, SpanProcessor};

use crate::baggage::keys;

/// A SpanProcessor that copies baggage values to span attributes.
///
/// When a span starts, this processor reads baggage from the Context
/// and adds any present values as span attributes with the same keys.
#[derive(Debug, Default)]
pub struct BaggageSpanProcessor;

impl BaggageSpanProcessor {
    pub fn new() -> Self {
        Self
    }
}

impl SpanProcessor for BaggageSpanProcessor {
    fn on_start(&self, span: &mut Span, cx: &Context) {
        let baggage = cx.baggage();

        // Check if auth middleware has processed this request.
        // - If AUTH_PROCESSED is present: baggage was set by auth with correct endpoint_id
        // - If AUTH_PROCESSED is absent: baggage is from incoming headers (upstream caller's endpoint_id)
        //
        // This distinction is important for gateway_analytics span which is created BEFORE auth runs.
        // Without this check, gateway_analytics would get the caller's endpoint_id instead of the
        // resolved endpoint_id for this specific request.
        let auth_processed = baggage.get(keys::AUTH_PROCESSED).is_some();

        // Copy baggage keys to span attributes
        if let Some(value) = baggage.get(keys::PROJECT_ID) {
            span.set_attribute(KeyValue::new(keys::PROJECT_ID, value.as_str().to_string()));
        }
        if let Some(value) = baggage.get(keys::PROMPT_ID) {
            span.set_attribute(KeyValue::new(keys::PROMPT_ID, value.as_str().to_string()));
        }
        if let Some(value) = baggage.get(keys::PROMPT_VERSION_ID) {
            span.set_attribute(KeyValue::new(keys::PROMPT_VERSION_ID, value.as_str().to_string()));
        }
        // Only set endpoint_id if auth has processed the request (baggage has correct value).
        // For spans created before auth (gateway_analytics), analytics_middleware sets endpoint_id.
        if auth_processed {
            if let Some(value) = baggage.get(keys::ENDPOINT_ID) {
                span.set_attribute(KeyValue::new(keys::ENDPOINT_ID, value.as_str().to_string()));
            }
        }
        if let Some(value) = baggage.get(keys::MODEL_ID) {
            span.set_attribute(KeyValue::new(keys::MODEL_ID, value.as_str().to_string()));
        }
        if let Some(value) = baggage.get(keys::API_KEY_ID) {
            span.set_attribute(KeyValue::new(keys::API_KEY_ID, value.as_str().to_string()));
        }
        if let Some(value) = baggage.get(keys::API_KEY_PROJECT_ID) {
            span.set_attribute(KeyValue::new(keys::API_KEY_PROJECT_ID, value.as_str().to_string()));
        }
        if let Some(value) = baggage.get(keys::USER_ID) {
            span.set_attribute(KeyValue::new(keys::USER_ID, value.as_str().to_string()));
        }
    }

    fn on_end(&self, _span: SpanData) {
        // No action needed on span end
    }

    fn force_flush(&self) -> OTelSdkResult {
        Ok(())
    }

    fn shutdown(&self) -> OTelSdkResult {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_baggage_processor_copies_attributes() {
        // Create context with baggage
        let ctx = Context::new().with_baggage(vec![
            KeyValue::new(keys::PROJECT_ID, "proj-123"),
            KeyValue::new(keys::PROMPT_ID, "prompt-456"),
            KeyValue::new(keys::PROMPT_VERSION_ID, "version-789"),
            KeyValue::new(keys::MODEL_ID, "model-abc"),
            KeyValue::new(keys::API_KEY_PROJECT_ID, "key-proj-def"),
        ]);

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
            baggage.get(keys::PROMPT_VERSION_ID).map(|v| v.as_str()),
            Some("version-789")
        );
        assert_eq!(
            baggage.get(keys::MODEL_ID).map(|v| v.as_str()),
            Some("model-abc")
        );
        assert_eq!(
            baggage.get(keys::API_KEY_PROJECT_ID).map(|v| v.as_str()),
            Some("key-proj-def")
        );
    }

    #[test]
    fn test_baggage_processor_handles_empty_baggage() {
        let ctx = Context::new();
        let baggage = ctx.baggage();
        assert!(baggage.get(keys::PROJECT_ID).is_none());
    }
}
