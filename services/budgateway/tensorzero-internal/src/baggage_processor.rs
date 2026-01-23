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

        // Copy each baggage key to span attributes if present
        if let Some(value) = baggage.get(keys::PROJECT_ID) {
            span.set_attribute(KeyValue::new(keys::PROJECT_ID, value.as_str().to_string()));
        }
        if let Some(value) = baggage.get(keys::PROMPT_ID) {
            span.set_attribute(KeyValue::new(keys::PROMPT_ID, value.as_str().to_string()));
        }
        if let Some(value) = baggage.get(keys::ENDPOINT_ID) {
            span.set_attribute(KeyValue::new(keys::ENDPOINT_ID, value.as_str().to_string()));
        }
        if let Some(value) = baggage.get(keys::API_KEY_ID) {
            span.set_attribute(KeyValue::new(keys::API_KEY_ID, value.as_str().to_string()));
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
    }

    #[test]
    fn test_baggage_processor_handles_empty_baggage() {
        let ctx = Context::new();
        let baggage = ctx.baggage();
        assert!(baggage.get(keys::PROJECT_ID).is_none());
    }
}
