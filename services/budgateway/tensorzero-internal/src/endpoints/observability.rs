//! Gateway observability utilities for tracing and span management.

use chrono::{DateTime, Utc};
use opentelemetry::trace::Status as OtelStatus;
use tracing::Span;
use tracing_opentelemetry::OpenTelemetrySpanExt;
use uuid::Uuid;

use crate::endpoints::inference::InferenceDatabaseInsertMetadata;
use crate::error::Error;
use crate::inference::types::resolved_input::ResolvedInput;
use crate::inference::types::{
    FinishReason, InferenceResult, Latency, ModelInferenceResponseWithMetadata, Usage,
};
use crate::model::ModelPricing;

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
        "budgateway::default",
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

/// Records model inference span attributes for error scenarios
/// Provides complete parity with ClickHouse ModelInference table
pub fn record_error_model_inference(
    model_inference: &crate::inference::types::ModelInferenceDatabaseInsert,
) {
    let span = Span::current();

    // Record all 20 fields (matching record_model_inference() structure)
    span.record("model_inference.id", model_inference.id.to_string().as_str());
    span.record(
        "model_inference.inference_id",
        model_inference.inference_id.to_string().as_str(),
    );
    span.record(
        "model_inference.raw_request",
        model_inference.raw_request.as_str(),
    );
    span.record(
        "model_inference.raw_response",
        model_inference.raw_response.as_str(),
    );
    span.record(
        "model_inference.model_name",
        model_inference.model_name.as_str(),
    );
    span.record(
        "model_inference.model_provider_name",
        model_inference.model_provider_name.as_str(),
    );

    // Optional fields - only record if present (Empty/null if not)
    if let Some(input_tokens) = model_inference.input_tokens {
        span.record("model_inference.input_tokens", input_tokens as i64);
    }
    if let Some(output_tokens) = model_inference.output_tokens {
        span.record("model_inference.output_tokens", output_tokens as i64);
    }
    if let Some(response_time_ms) = model_inference.response_time_ms {
        span.record("model_inference.response_time_ms", response_time_ms as i64);
    }
    if let Some(ttft_ms) = model_inference.ttft_ms {
        span.record("model_inference.ttft_ms", ttft_ms as i64);
    }

    // Timestamp
    span.record("model_inference.timestamp", chrono::Utc::now().timestamp());

    if let Some(ref system) = model_inference.system {
        span.record("model_inference.system", system.as_str());
    }

    span.record(
        "model_inference.input_messages",
        model_inference.input_messages.as_str(),
    );
    span.record("model_inference.output", model_inference.output.as_str());
    span.record("model_inference.cached", model_inference.cached);

    if let Some(ref finish_reason) = model_inference.finish_reason {
        let fr_str = match finish_reason {
            crate::inference::types::FinishReason::Stop => "stop",
            crate::inference::types::FinishReason::Length => "length",
            crate::inference::types::FinishReason::ToolCall => "tool_call",
            crate::inference::types::FinishReason::ContentFilter => "content_filter",
            crate::inference::types::FinishReason::Unknown => "unknown",
        };
        span.record("model_inference.finish_reason", fr_str);
    }

    if let Some(ref gateway_req) = model_inference.gateway_request {
        span.record("model_inference.gateway_request", gateway_req.as_str());
    }
    if let Some(ref gateway_resp) = model_inference.gateway_response {
        span.record("model_inference.gateway_response", gateway_resp.as_str());
    }

    span.record(
        "model_inference.endpoint_type",
        model_inference.endpoint_type.as_str(),
    );

    if let Some(ref guardrail_summary) = model_inference.guardrail_scan_summary {
        span.record(
            "model_inference.guardrail_scan_summary",
            guardrail_summary.as_str(),
        );
    }
}

/// Records error information on the current span using OpenTelemetry conventions.
/// Sets OTEL span status to Error with message, records error details, and emits exception event.
pub fn record_error(error: &Error) {
    let span = Span::current();

    let error_type = error.get_details().as_ref();
    let error_message = error.to_string();

    // Set OTEL span status with error message - populates StatusCode and StatusMessage columns
    span.set_status(OtelStatus::error(error_message.clone()));

    // Record structured error details as span attributes
    span.record("error.type", error_type);
    span.record("error.message", error_message.as_str());

    // Create OTEL exception event via tracing::error!
    // The OpenTelemetryLayer::on_event will convert this to an OTEL span event
    // Using target: "budgateway_internal::endpoints::openai_compatible" to avoid exposing internal module path
    span.in_scope(|| {
        tracing::error!(
            // otel.exception = true, Commenting out cannot use otel.exception with target: due to macro parsing
            target: "budgateway_internal::endpoints::openai_compatible",
            error_type = %error_type,
            error_message = %error_message,
            "Exception: {}", error_type
        );
    });
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

/// Calculate cost from usage and pricing information.
/// Uses the same formula as inference.rs Kafka path to ensure consistency.
pub fn calculate_cost(usage: &Usage, model_pricing: Option<&ModelPricing>) -> Option<f64> {
    if usage.input_tokens > 0 || usage.output_tokens > 0 {
        if let Some(pricing) = model_pricing {
            // Convert tokens to the pricing unit (e.g., if per_tokens is 1000, divide by 1000)
            let input_multiplier = usage.input_tokens as f64 / pricing.per_tokens as f64;
            let output_multiplier = usage.output_tokens as f64 / pricing.per_tokens as f64;
            let total_cost =
                (input_multiplier * pricing.input_cost) + (output_multiplier * pricing.output_cost);
            Some(total_cost)
        } else {
            // Fallback to default pricing if not configured
            // Using reasonable defaults: $0.01 per 1K input tokens, $0.03 per 1K output tokens
            Some((usage.input_tokens as f64 * 0.00001) + (usage.output_tokens as f64 * 0.00003))
        }
    } else {
        None
    }
}

/// Records OpenAI Response API request params as span attributes (GenAI semantic convention)
pub fn record_response_request(params: &crate::responses::OpenAIResponseCreateParams) {
    let span = Span::current();

    // Operation name (new field)
    span.record("gen_ai.operation.name", "response_create");

    // String fields
    if let Some(ref model) = params.model {
        span.record("gen_ai.request.model", model.as_str());
    }
    if let Some(ref previous_response_id) = params.previous_response_id {
        span.record("gen_ai.request.previous_response_id", previous_response_id.as_str());
    }
    if let Some(ref service_tier) = params.service_tier {
        span.record("gen_ai.request.service_tier", service_tier.as_str());
    }
    if let Some(ref user) = params.user {
        span.record("gen_ai.request.user", user.as_str());
    }

    // Boolean fields
    if let Some(parallel_tool_calls) = params.parallel_tool_calls {
        span.record("gen_ai.request.parallel_tool_calls", parallel_tool_calls);
    }
    if let Some(stream) = params.stream {
        span.record("gen_ai.request.stream", stream);
    }
    if let Some(store) = params.store {
        span.record("gen_ai.request.store", store);
    }
    if let Some(background) = params.background {
        span.record("gen_ai.request.background", background);
    }

    // Numeric fields
    if let Some(max_tool_calls) = params.max_tool_calls {
        span.record("gen_ai.request.max_tool_calls", max_tool_calls as i64);
    }
    if let Some(temperature) = params.temperature {
        span.record("gen_ai.request.temperature", temperature as f64);
    }
    if let Some(max_output_tokens) = params.max_output_tokens {
        span.record("gen_ai.request.max_tokens", max_output_tokens as i64);
    }

    // Prompt reference fields (extracted for convenience)
    if let Some(ref prompt) = params.prompt {
        span.record("gen_ai.prompt.id", prompt.id.as_str());
        if let Some(ref version) = prompt.version {
            span.record("gen_ai.prompt.version", version.as_str());
        }
        if let Ok(json) = serde_json::to_string(prompt) {
            span.record("gen_ai.prompt", json.as_str());
        }
        // New field: prompt variables
        if let Some(ref variables) = prompt.variables {
            if let Ok(json) = serde_json::to_string(variables) {
                span.record("gen_ai.prompt.variables", json.as_str());
            }
        }
    }

    // JSON serialized fields (check for simple strings first to avoid extra quotes)
    if let Some(ref input) = params.input {
        // If it's a simple string, record directly without extra quotes
        if let Some(s) = input.as_str() {
            span.record("gen_ai.input.messages", s);
        } else if let Ok(json) = serde_json::to_string(input) {
            span.record("gen_ai.input.messages", json.as_str());
        }
    }
    if let Some(ref instructions) = params.instructions {
        if let Ok(json) = serde_json::to_string(instructions) {
            span.record("gen_ai.request.instructions", json.as_str());
        }
    }
    if let Some(ref tools) = params.tools {
        if let Ok(json) = serde_json::to_string(tools) {
            span.record("gen_ai.request.tools", json.as_str());
        }
    }
    if let Some(ref tool_choice) = params.tool_choice {
        // If it's a simple string, record directly without extra quotes
        if let Some(s) = tool_choice.as_str() {
            span.record("gen_ai.request.tool_choice", s);
        } else if let Ok(json) = serde_json::to_string(tool_choice) {
            span.record("gen_ai.request.tool_choice", json.as_str());
        }
    }
    if let Some(ref response_format) = params.response_format {
        if let Ok(json) = serde_json::to_string(response_format) {
            span.record("gen_ai.request.response_format", json.as_str());
        }
    }
    if let Some(ref reasoning) = params.reasoning {
        if let Ok(json) = serde_json::to_string(reasoning) {
            span.record("gen_ai.request.reasoning", json.as_str());
        }
    }
    if let Some(ref include) = params.include {
        if let Ok(json) = serde_json::to_string(include) {
            span.record("gen_ai.request.include", json.as_str());
        }
    }
    if let Some(ref metadata) = params.metadata {
        if let Ok(json) = serde_json::to_string(metadata) {
            span.record("gen_ai.request.metadata", json.as_str());
        }
    }
    if let Some(ref stream_options) = params.stream_options {
        if let Ok(json) = serde_json::to_string(stream_options) {
            span.record("gen_ai.request.stream_options", json.as_str());
        }
    }
    if let Some(ref modalities) = params.modalities {
        if let Ok(json) = serde_json::to_string(modalities) {
            span.record("gen_ai.request.modalities", json.as_str());
        }
    }
}

/// Records OpenAI Response API result as span attributes (GenAI semantic convention)
pub fn record_response_result(response: &crate::responses::OpenAIResponse) {
    let span = Span::current();

    // Core response fields (always present)
    span.record("gen_ai.response.id", response.id.as_str());
    span.record("gen_ai.response.object", response.object.as_str());
    span.record("gen_ai.response.created_at", response.created_at);
    if let Ok(status_json) = serde_json::to_string(&response.status) {
        // Remove quotes from the JSON string (e.g., "\"completed\"" -> "completed")
        span.record("gen_ai.response.status", status_json.trim_matches('"'));
    }
    span.record("gen_ai.response.model", response.model.as_str());

    // Optional boolean fields
    if let Some(background) = response.background {
        span.record("gen_ai.response.background", background);
    }
    if let Some(parallel_tool_calls) = response.parallel_tool_calls {
        span.record("gen_ai.response.parallel_tool_calls", parallel_tool_calls);
    }

    // Optional numeric fields
    if let Some(max_output_tokens) = response.max_output_tokens {
        span.record("gen_ai.response.max_output_tokens", max_output_tokens as i64);
    }
    if let Some(temperature) = response.temperature {
        span.record("gen_ai.response.temperature", temperature as f64);
    }
    // New field: top_p
    if let Some(top_p) = response.top_p {
        span.record("gen_ai.response.top_p", top_p as f64);
    }

    // New field: service_tier
    if let Some(ref service_tier) = response.service_tier {
        span.record("gen_ai.openai.response.service_tier", service_tier.as_str());
    }

    // JSON serialized fields
    if let Some(ref instructions) = response.instructions {
        if let Ok(json) = serde_json::to_string(instructions) {
            span.record("gen_ai.system.instructions", json.as_str());
        }
    }
    if let Ok(json) = serde_json::to_string(&response.output) {
        span.record("gen_ai.output.messages", json.as_str());
    }
    if let Some(ref prompt) = response.prompt {
        if let Ok(json) = serde_json::to_string(prompt) {
            span.record("gen_ai.response.prompt", json.as_str());
        }
    }
    if let Some(ref reasoning) = response.reasoning {
        if let Ok(json) = serde_json::to_string(reasoning) {
            span.record("gen_ai.response.reasoning", json.as_str());
        }
    }
    if let Some(ref text) = response.text {
        if let Ok(json) = serde_json::to_string(text) {
            span.record("gen_ai.output.type", json.as_str());
        }
    }
    if let Some(ref tool_choice) = response.tool_choice {
        // If it's a simple string, record directly without extra quotes
        if let Some(s) = tool_choice.as_str() {
            span.record("gen_ai.response.tool_choice", s);
        } else if let Ok(json) = serde_json::to_string(tool_choice) {
            span.record("gen_ai.response.tool_choice", json.as_str());
        }
    }
    if let Some(ref tools) = response.tools {
        if let Ok(json) = serde_json::to_string(tools) {
            span.record("gen_ai.response.tools", json.as_str());
        }
    }

    // Usage fields (extracted for convenience)
    if let Some(ref usage) = response.usage {
        if let Ok(json) = serde_json::to_string(usage) {
            span.record("gen_ai.usage", json.as_str());
        }
        span.record("gen_ai.usage.input_tokens", usage.input_tokens as i64);
        if let Some(output_tokens) = usage.output_tokens {
            span.record("gen_ai.usage.output_tokens", output_tokens as i64);
        }
        span.record("gen_ai.usage.total_tokens", usage.total_tokens as i64);
    }
}

/// Records embedding inference request as span attributes
pub fn record_embedding_request(
    model: &str,
    input_count: usize,
    dimensions: Option<u32>,
    encoding_format: Option<&str>,
) {
    let span = Span::current();

    span.record("embedding_inference.model", model);
    span.record("embedding_inference.input_count", input_count as i64);

    if let Some(dims) = dimensions {
        span.record("embedding_inference.dimensions", dims as i64);
    }
    if let Some(format) = encoding_format {
        span.record("embedding_inference.encoding_format", format);
    }

    span.record("model_inference.endpoint_type", "embedding");
}

/// Records embedding inference response as span attributes
pub fn record_embedding_response(
    id: &str,
    embedding_count: usize,
    model_name: &str,
    input_tokens: u32,
    response_time_ms: u64,
) {
    let span = Span::current();

    span.record("embedding_inference.id", id);
    span.record("embedding_inference.embedding_count", embedding_count as i64);
    span.record("model_inference.model_name", model_name);
    span.record("model_inference.input_tokens", input_tokens as i64);
    span.record("model_inference.response_time_ms", response_time_ms as i64);
    span.record("model_inference.timestamp", chrono::Utc::now().timestamp());
}

/// Records embedding processing time as span attribute
pub fn record_embedding_processing_time(processing_time_ms: u64) {
    let span = Span::current();
    span.record("embedding_inference.processing_time_ms", processing_time_ms as i64);
}

/// Records classify inference request as span attributes
pub fn record_classify_request(model: &str, input_count: usize, raw_scores: bool) {
    let span = Span::current();

    span.record("classify_inference.model", model);
    span.record("classify_inference.input_count", input_count as i64);
    span.record("classify_inference.raw_scores", raw_scores);

    span.record("model_inference.endpoint_type", "classify");
}

/// Records classify inference response as span attributes
pub fn record_classify_response(
    id: &str,
    label_count: usize,
    model_name: &str,
    input_tokens: u32,
    output_tokens: u32,
    response_time_ms: u64,
) {
    let span = Span::current();

    span.record("classify_inference.id", id);
    span.record("classify_inference.label_count", label_count as i64);
    span.record("model_inference.model_name", model_name);
    span.record("model_inference.input_tokens", input_tokens as i64);
    span.record("model_inference.output_tokens", output_tokens as i64);
    span.record("model_inference.response_time_ms", response_time_ms as i64);
    span.record("model_inference.timestamp", chrono::Utc::now().timestamp());
}

/// Records classify processing time as span attribute
pub fn record_classify_processing_time(processing_time_ms: u64) {
    let span = Span::current();
    span.record("classify_inference.processing_time_ms", processing_time_ms as i64);
}
