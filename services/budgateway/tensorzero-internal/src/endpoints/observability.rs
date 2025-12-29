//! Gateway observability utilities for tracing and span management.

use chrono::{DateTime, Utc};
use tracing::Span;

use uuid::Uuid;

use crate::endpoints::inference::InferenceDatabaseInsertMetadata;
use crate::error::Error;
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

/// Records error information on the current span using OpenTelemetry conventions.
/// Sets otel.status_code to "Error" and records error type and message.
pub fn record_error(error: &Error) {
    let span = Span::current();

    // Set OpenTelemetry span status to Error
    span.record("otel.status_code", "Error");
    span.record("otel.status_description", error.to_string().as_str());

    // Record structured error details using strum's AsRefStr derive
    span.record("error.type", error.get_details().as_ref());
    span.record("error.message", error.to_string().as_str());
}

/// Struct to hold error information for ModelInferenceDetails recording
pub struct ModelInferenceDetailsError<'a> {
    pub error_code: &'a str,
    pub error_message: &'a str,
    pub error_type: &'a str,
    pub status_code: u16,
}

/// Records ModelInferenceDetails as span attributes (17 fields)
#[allow(clippy::too_many_arguments)]
pub fn record_model_inference_details(
    inference_id: &Uuid,
    project_id: &str,
    endpoint_id: &str,
    model_id: &str,
    is_success: bool,
    request_arrival_time: DateTime<Utc>,
    request_forward_time: DateTime<Utc>,
    cost: Option<f64>,
    api_key_id: Option<&str>,
    user_id: Option<&str>,
    api_key_project_id: Option<&str>,
    error_info: Option<ModelInferenceDetailsError>,
) {
    let span = Span::current();

    // Core identification fields
    span.record(
        "model_inference_details.inference_id",
        inference_id.to_string().as_str(),
    );
    span.record("model_inference_details.project_id", project_id);
    span.record("model_inference_details.endpoint_id", endpoint_id);
    span.record("model_inference_details.model_id", model_id);

    // Status and timing
    span.record("model_inference_details.is_success", is_success);
    span.record(
        "model_inference_details.request_arrival_time",
        request_arrival_time.to_rfc3339().as_str(),
    );
    span.record(
        "model_inference_details.request_forward_time",
        request_forward_time.to_rfc3339().as_str(),
    );

    // Optional fields
    if let Some(cost_val) = cost {
        span.record("model_inference_details.cost", cost_val);
    }
    if let Some(api_key) = api_key_id {
        span.record("model_inference_details.api_key_id", api_key);
    }
    if let Some(user) = user_id {
        span.record("model_inference_details.user_id", user);
    }
    if let Some(api_key_proj) = api_key_project_id {
        span.record("model_inference_details.api_key_project_id", api_key_proj);
    }

    // Error fields (only for failures)
    if let Some(err) = error_info {
        span.record("model_inference_details.error_code", err.error_code);
        span.record("model_inference_details.error_message", err.error_message);
        span.record("model_inference_details.error_type", err.error_type);
        span.record("model_inference_details.status_code", err.status_code as i64);
    }
}

/// Records OpenAI Response API request params as span attributes
pub fn record_response_request(params: &crate::responses::OpenAIResponseCreateParams) {
    let span = Span::current();

    // String fields
    if let Some(ref model) = params.model {
        span.record("request.model", model.as_str());
    }
    if let Some(ref previous_response_id) = params.previous_response_id {
        span.record("request.previous_response_id", previous_response_id.as_str());
    }
    if let Some(ref service_tier) = params.service_tier {
        span.record("request.service_tier", service_tier.as_str());
    }
    if let Some(ref user) = params.user {
        span.record("request.user", user.as_str());
    }

    // Boolean fields
    if let Some(parallel_tool_calls) = params.parallel_tool_calls {
        span.record("request.parallel_tool_calls", parallel_tool_calls);
    }
    if let Some(stream) = params.stream {
        span.record("request.stream", stream);
    }
    if let Some(store) = params.store {
        span.record("request.store", store);
    }
    if let Some(background) = params.background {
        span.record("request.background", background);
    }

    // Numeric fields
    if let Some(max_tool_calls) = params.max_tool_calls {
        span.record("request.max_tool_calls", max_tool_calls as i64);
    }
    if let Some(temperature) = params.temperature {
        span.record("request.temperature", temperature as f64);
    }
    if let Some(max_output_tokens) = params.max_output_tokens {
        span.record("request.max_output_tokens", max_output_tokens as i64);
    }

    // Prompt reference fields (extracted for convenience)
    if let Some(ref prompt) = params.prompt {
        span.record("request.prompt_id", prompt.id.as_str());
        if let Some(ref version) = prompt.version {
            span.record("request.prompt_version", version.as_str());
        }
        if let Ok(json) = serde_json::to_string(prompt) {
            span.record("request.prompt", json.as_str());
        }
    }

    // JSON serialized fields
    if let Some(ref input) = params.input {
        if let Ok(json) = serde_json::to_string(input) {
            span.record("request.input", json.as_str());
        }
    }
    if let Some(ref instructions) = params.instructions {
        if let Ok(json) = serde_json::to_string(instructions) {
            span.record("request.instructions", json.as_str());
        }
    }
    if let Some(ref tools) = params.tools {
        if let Ok(json) = serde_json::to_string(tools) {
            span.record("request.tools", json.as_str());
        }
    }
    if let Some(ref tool_choice) = params.tool_choice {
        // If it's a simple string, record directly without extra quotes
        if let Some(s) = tool_choice.as_str() {
            span.record("request.tool_choice", s);
        } else if let Ok(json) = serde_json::to_string(tool_choice) {
            span.record("request.tool_choice", json.as_str());
        }
    }
    if let Some(ref response_format) = params.response_format {
        if let Ok(json) = serde_json::to_string(response_format) {
            span.record("request.response_format", json.as_str());
        }
    }
    if let Some(ref reasoning) = params.reasoning {
        if let Ok(json) = serde_json::to_string(reasoning) {
            span.record("request.reasoning", json.as_str());
        }
    }
    if let Some(ref include) = params.include {
        if let Ok(json) = serde_json::to_string(include) {
            span.record("request.include", json.as_str());
        }
    }
    if let Some(ref metadata) = params.metadata {
        if let Ok(json) = serde_json::to_string(metadata) {
            span.record("request.metadata", json.as_str());
        }
    }
    if let Some(ref stream_options) = params.stream_options {
        if let Ok(json) = serde_json::to_string(stream_options) {
            span.record("request.stream_options", json.as_str());
        }
    }
    if let Some(ref modalities) = params.modalities {
        if let Ok(json) = serde_json::to_string(modalities) {
            span.record("request.modalities", json.as_str());
        }
    }
}

/// Records OpenAI Response API result as span attributes
pub fn record_response_result(response: &crate::responses::OpenAIResponse) {
    let span = Span::current();

    // Core response fields (always present)
    span.record("response.id", response.id.as_str());
    span.record("response.object", response.object.as_str());
    span.record("response.created_at", response.created_at);
    if let Ok(status_json) = serde_json::to_string(&response.status) {
        // Remove quotes from the JSON string (e.g., "\"completed\"" -> "completed")
        span.record("response.status", status_json.trim_matches('"'));
    }
    span.record("response.model", response.model.as_str());

    // Optional boolean fields
    if let Some(background) = response.background {
        span.record("response.background", background);
    }
    if let Some(parallel_tool_calls) = response.parallel_tool_calls {
        span.record("response.parallel_tool_calls", parallel_tool_calls);
    }

    // Optional numeric fields
    if let Some(max_output_tokens) = response.max_output_tokens {
        span.record("response.max_output_tokens", max_output_tokens as i64);
    }
    if let Some(temperature) = response.temperature {
        span.record("response.temperature", temperature as f64);
    }

    // JSON serialized fields
    if let Some(ref instructions) = response.instructions {
        if let Ok(json) = serde_json::to_string(instructions) {
            span.record("response.instructions", json.as_str());
        }
    }
    if let Ok(json) = serde_json::to_string(&response.output) {
        span.record("response.output", json.as_str());
    }
    if let Some(ref prompt) = response.prompt {
        if let Ok(json) = serde_json::to_string(prompt) {
            span.record("response.prompt", json.as_str());
        }
    }
    if let Some(ref reasoning) = response.reasoning {
        if let Ok(json) = serde_json::to_string(reasoning) {
            span.record("response.reasoning", json.as_str());
        }
    }
    if let Some(ref text) = response.text {
        if let Ok(json) = serde_json::to_string(text) {
            span.record("response.text", json.as_str());
        }
    }
    if let Some(ref tool_choice) = response.tool_choice {
        // If it's a simple string, record directly without extra quotes
        if let Some(s) = tool_choice.as_str() {
            span.record("response.tool_choice", s);
        } else if let Ok(json) = serde_json::to_string(tool_choice) {
            span.record("response.tool_choice", json.as_str());
        }
    }
    if let Some(ref tools) = response.tools {
        if let Ok(json) = serde_json::to_string(tools) {
            span.record("response.tools", json.as_str());
        }
    }

    // Usage fields (extracted for convenience)
    if let Some(ref usage) = response.usage {
        if let Ok(json) = serde_json::to_string(usage) {
            span.record("response.usage", json.as_str());
        }
        span.record("response.usage.input_tokens", usage.input_tokens as i64);
        if let Some(output_tokens) = usage.output_tokens {
            span.record("response.usage.output_tokens", output_tokens as i64);
        }
        span.record("response.usage.total_tokens", usage.total_tokens as i64);
    }
}
