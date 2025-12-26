//! Gateway observability utilities for tracing and span management.

use tracing::Span;

use uuid::Uuid;

use crate::endpoints::inference::InferenceDatabaseInsertMetadata;
use crate::inference::types::resolved_input::ResolvedInput;
use crate::inference::types::{
    FinishReason, InferenceResult, Latency, ModelInferenceResponseWithMetadata,
};

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

/// Records model inference as span attributes (all 20 fields)
pub fn record_model_inference(
    model_inferences: &[ModelInferenceResponseWithMetadata],
    inference_id: &Uuid,
) {
    let span = Span::current();

    // Record first model inference (primary)
    if let Some(model_inf) = model_inferences.first() {
        // 1. id
        span.record("model_inference.id", model_inf.id.to_string().as_str());

        // 2. inference_id (from parent ChatInference)
        span.record(
            "model_inference.inference_id",
            inference_id.to_string().as_str(),
        );

        // 3. raw_request
        span.record("model_inference.raw_request", model_inf.raw_request.as_str());

        // 4. raw_response
        span.record(
            "model_inference.raw_response",
            model_inf.raw_response.as_str(),
        );

        // 5. model_name
        span.record("model_inference.model_name", model_inf.model_name.as_ref());

        // 6. model_provider_name
        span.record(
            "model_inference.model_provider_name",
            model_inf.model_provider_name.as_ref(),
        );

        // 7. input_tokens
        span.record(
            "model_inference.input_tokens",
            model_inf.usage.input_tokens as i64,
        );

        // 8. output_tokens
        span.record(
            "model_inference.output_tokens",
            model_inf.usage.output_tokens as i64,
        );

        // 9. response_time_ms (from latency)
        let response_time_ms = match &model_inf.latency {
            Latency::NonStreaming { response_time } => response_time.as_millis() as i64,
            Latency::Streaming { response_time, .. } => response_time.as_millis() as i64,
            Latency::Batch => 0,
        };
        span.record("model_inference.response_time_ms", response_time_ms);

        // 10. ttft_ms (only for streaming latency - leave Empty/null for non-streaming)
        if let Latency::Streaming { ttft, .. } = &model_inf.latency {
            span.record("model_inference.ttft_ms", ttft.as_millis() as i64);
        }

        // 11. timestamp (from created field - Unix timestamp)
        span.record("model_inference.timestamp", model_inf.created as i64);

        // 12. system
        if let Some(ref system) = model_inf.system {
            span.record("model_inference.system", system.as_str());
        }

        // 13. input_messages
        if let Ok(input_json) = serde_json::to_string(&model_inf.input_messages) {
            span.record("model_inference.input_messages", input_json.as_str());
        }

        // 14. output
        if let Ok(output_json) = serde_json::to_string(&model_inf.output) {
            span.record("model_inference.output", output_json.as_str());
        }

        // 15. cached
        span.record("model_inference.cached", model_inf.cached);

        // 16. finish_reason (convert enum to string directly, no JSON quotes)
        if let Some(ref finish_reason) = model_inf.finish_reason {
            let fr_str = match finish_reason {
                FinishReason::Stop => "stop",
                FinishReason::Length => "length",
                FinishReason::ToolCall => "tool_call",
                FinishReason::ContentFilter => "content_filter",
                FinishReason::Unknown => "unknown",
            };
            span.record("model_inference.finish_reason", fr_str);
        }

        // 17. gateway_request
        if let Some(ref gateway_req) = model_inf.gateway_request {
            span.record("model_inference.gateway_request", gateway_req.as_str());
        }

        // 18. gateway_response
        if let Some(ref gateway_resp) = model_inf.gateway_response {
            span.record("model_inference.gateway_response", gateway_resp.as_str());
        }

        // 19. endpoint_type - hardcoded as "chat" for non-streaming chat completions
        span.record("model_inference.endpoint_type", "chat");

        // 20. guardrail_scan_summary
        if let Some(ref guardrail_summary) = model_inf.guardrail_scan_summary {
            span.record(
                "model_inference.guardrail_scan_summary",
                guardrail_summary.as_str(),
            );
        }
    }
}
