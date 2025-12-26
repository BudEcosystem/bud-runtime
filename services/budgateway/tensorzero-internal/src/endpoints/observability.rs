//! Gateway observability utilities for tracing and span management.

use tracing::Span;

use crate::endpoints::inference::InferenceDatabaseInsertMetadata;
use crate::inference::types::resolved_input::ResolvedInput;
use crate::inference::types::InferenceResult;

/// Records resolved input as span attribute
pub fn record_resolved_input(input: &ResolvedInput) {
    let span = Span::current();
    if let Ok(input_json) = serde_json::to_string(input) {
        span.record("chat_inference.input", input_json.as_str());
    }
}

/// Records inference result as span attributes (id, output, inference_params)
pub fn record_inference_result(result: &InferenceResult) {
    let span = Span::current();

    match result {
        InferenceResult::Chat(chat_result) => {
            span.record(
                "chat_inference.id",
                chat_result.inference_id.to_string().as_str(),
            );
            if let Ok(output_json) = serde_json::to_string(&chat_result.content) {
                span.record("chat_inference.output", output_json.as_str());
            }
            if let Ok(params_json) = serde_json::to_string(&chat_result.inference_params) {
                span.record("chat_inference.inference_params", params_json.as_str());
            }
        }
        _ => {}
    }
}

/// Records metadata as span attributes
pub fn record_metadata(metadata: &InferenceDatabaseInsertMetadata) {
    let span = Span::current();

    span.record(
        "chat_inference.function_name",
        metadata.function_name.as_str(),
    );
    span.record(
        "chat_inference.variant_name",
        metadata.variant_name.as_str(),
    );
    span.record(
        "chat_inference.episode_id",
        metadata.episode_id.to_string().as_str(),
    );

    if let Ok(tags_json) = serde_json::to_string(&metadata.tags) {
        span.record("chat_inference.tags", tags_json.as_str());
    }
    if let Ok(extra_body_json) = serde_json::to_string(&metadata.extra_body) {
        span.record("chat_inference.extra_body", extra_body_json.as_str());
    }
    if let Some(ref tool_config) = metadata.tool_config {
        if let Ok(tool_json) = serde_json::to_string(tool_config) {
            span.record("chat_inference.tool_params", tool_json.as_str());
        }
    }
    if let Some(processing_time) = metadata.processing_time {
        span.record(
            "chat_inference.processing_time_ms",
            processing_time.as_millis() as i64,
        );
    }
}
