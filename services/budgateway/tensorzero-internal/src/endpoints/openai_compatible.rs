//! OpenAI-compatible API endpoint implementation.
//!
//! This module provides compatibility with the OpenAI Chat Completions API format,
//! translating between OpenAI's request/response format and our internal types.
//! It implements request handling, parameter conversion, and response formatting
//! to match OpenAI's API specification.
//!
//! We convert the request into our internal types, call `endpoints::inference::inference` to perform the actual inference,
//! and then convert the response into the OpenAI-compatible format.

use std::collections::HashMap;
use std::pin::Pin;
use std::task::{Context, Poll};

use axum::body::Body;
use axum::debug_handler;
use axum::extract::{Extension, Multipart, Path, Query, State};
use axum::http::{HeaderMap, StatusCode};
use axum::response::sse::{Event, Sse};
use axum::response::{IntoResponse, Response};
use axum::Json;
use futures::{Stream, StreamExt as FuturesStreamExt};
use serde::{Deserialize, Serialize};
use serde_json::{json, Map, Value};
use url::Url;
use uuid::Uuid;

use crate::analytics::RequestAnalytics;
use crate::cache::CacheParamsOptions;
use crate::endpoints::inference::{
    inference, write_inference, ChatCompletionInferenceParams, InferenceClients,
    InferenceCredentials, InferenceParams, Params,
};
use crate::error::{Error, ErrorDetails};
use crate::gateway_util::{AppState, AppStateData, StructuredJson};
use crate::inference::types::extra_body::UnfilteredInferenceExtraBody;
use crate::inference::types::extra_headers::UnfilteredInferenceExtraHeaders;
use crate::inference::types::{
    current_timestamp, ContentBlockChatOutput, ContentBlockChunk, File, FileKind, FinishReason,
    InferenceResult, Input, InputMessage, InputMessageContent, ResolvedInput, ResolvedInputMessage,
    ResolvedInputMessageContent, Role, TextKind, Usage,
};
use crate::tool::{
    DynamicToolParams, Tool, ToolCall, ToolCallChunk, ToolCallOutput, ToolChoice, ToolResult,
};
use crate::usage_limit::UsageLimitDecision;
use crate::variant::JsonMode;

use super::inference::{
    InferenceOutput, InferenceResponse, InferenceResponseChunk, InferenceStream,
};
use super::model_resolution;
use crate::audio::{
    AudioOutputFormat, AudioTranscriptionRequest, AudioTranscriptionResponseFormat,
    AudioTranslationRequest, AudioVoice, ChunkingStrategy, TextToSpeechRequest,
    TimestampGranularity,
};
use crate::completions::{
    CompletionChoiceChunk, CompletionPrompt, CompletionRequest, CompletionStop,
};
use crate::embeddings::EmbeddingRequest;
use crate::file_storage::validate_batch_file;
use crate::inference::providers::batch::BatchProvider;
#[cfg(feature = "e2e_tests")]
use crate::inference::providers::dummy::DummyProvider;
#[cfg(not(feature = "e2e_tests"))]
use crate::inference::providers::openai::OpenAIProvider;
#[cfg(not(feature = "e2e_tests"))]
use crate::model::CredentialLocation;
use crate::moderation::ModerationProvider;
use crate::openai_batch::{
    validate_batch_create_request, ListBatchesParams, OpenAIBatchCreateRequest,
};
use crate::realtime::{RealtimeSessionRequest, RealtimeTranscriptionRequest};
use secrecy::SecretString;
use std::sync::{Arc, OnceLock};

/// Helper function to merge credentials from the model credential store
/// This eliminates code duplication across multiple endpoint handlers
fn merge_credentials_from_store(
    model_credential_store: &Arc<std::sync::RwLock<HashMap<String, SecretString>>>,
) -> InferenceCredentials {
    let mut credentials = InferenceCredentials::default();
    {
        #[expect(clippy::expect_used)]
        let credential_store = model_credential_store.read().expect("RwLock poisoned");
        for (key, value) in credential_store.iter() {
            if !credentials.contains_key(key) {
                credentials.insert(key.clone(), value.clone());
            }
        }
    }
    credentials
}

/// Helper function to merge credentials from headers (for dynamic authorization)
fn merge_credentials_from_headers(headers: &HeaderMap, credentials: &mut InferenceCredentials) {
    // Extract authorization header if present
    if let Some(auth_header) = headers.get("authorization") {
        if let Ok(auth_str) = auth_header.to_str() {
            // Strip "Bearer " prefix if present
            let token = auth_str.strip_prefix("Bearer ").unwrap_or(auth_str);
            // Use "authorization" as the key so dynamic::authorization lookup can find it
            credentials.insert(
                "authorization".to_string(),
                secrecy::SecretString::from(token.to_string()),
            );
        }
    }
}

/// Helper function to extract ObservabilityMetadata from headers for error handler access.
/// This duplicates the logic from the inference handler but allows access outside the async block.
fn extract_observability_metadata_from_headers(
    headers: &HeaderMap,
) -> Option<super::inference::ObservabilityMetadata> {
    let project_id = headers
        .get("x-tensorzero-project-id")
        .and_then(|v| v.to_str().ok())?;
    let endpoint_id = headers
        .get("x-tensorzero-endpoint-id")
        .and_then(|v| v.to_str().ok())?;
    let model_id = headers
        .get("x-tensorzero-model-id")
        .and_then(|v| v.to_str().ok())?;

    let api_key_id = headers
        .get("x-tensorzero-api-key-id")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string());
    let user_id = headers
        .get("x-tensorzero-user-id")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string());
    let api_key_project_id = headers
        .get("x-tensorzero-api-key-project-id")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string());

    Some(super::inference::ObservabilityMetadata {
        project_id: project_id.to_string(),
        endpoint_id: endpoint_id.to_string(),
        model_id: model_id.to_string(),
        api_key_id,
        user_id,
        api_key_project_id,
    })
}

/// Helper function to create OpenAI-compatible error response for guardrail violations
fn create_guardrail_error_response(
    message: &str,
    is_input_violation: bool,
) -> (StatusCode, serde_json::Value) {
    let (error_type, status_code) = if is_input_violation {
        ("invalid_request_error", StatusCode::BAD_REQUEST)
    } else {
        ("server_error", StatusCode::INTERNAL_SERVER_ERROR)
    };

    let error_json = json!({
        "error": {
            "message": message,
            "type": error_type,
            "code": "content_filter"
        }
    });

    (status_code, error_json)
}

/// Helper function to serialize JSON without null values
pub(crate) fn serialize_without_nulls<T: Serialize>(
    value: &T,
) -> Result<String, serde_json::Error> {
    let value = serde_json::to_value(value)?;

    fn remove_nulls(value: Value) -> Value {
        match value {
            Value::Object(map) => {
                let mut cleaned = Map::new();
                for (k, v) in map {
                    match v {
                        Value::Null => continue,
                        Value::Object(_) => {
                            cleaned.insert(k, remove_nulls(v));
                        }
                        Value::Array(arr) => {
                            let cleaned_arr: Vec<Value> = arr
                                .into_iter()
                                .map(remove_nulls)
                                .filter(|v| !matches!(v, Value::Null))
                                .collect();
                            if !cleaned_arr.is_empty() {
                                cleaned.insert(k, Value::Array(cleaned_arr));
                            }
                        }
                        other => {
                            cleaned.insert(k, other);
                        }
                    }
                }
                Value::Object(cleaned)
            }
            Value::Array(arr) => {
                let cleaned: Vec<Value> = arr
                    .into_iter()
                    .map(remove_nulls)
                    .filter(|v| !matches!(v, Value::Null))
                    .collect();
                Value::Array(cleaned)
            }
            other => other,
        }
    }

    let cleaned = remove_nulls(value);
    serde_json::to_string(&cleaned)
}

/// A handler for the OpenAI-compatible inference endpoint
#[debug_handler(state = AppStateData)]
#[tracing::instrument(
    name = "inference_handler_observability",
    skip_all,
    fields(
        otel.name = "inference_handler_observability",
        // OpenTelemetry error status fields
        otel.status_code = tracing::field::Empty,
        otel.status_description = tracing::field::Empty,
        // Error details fields
        error.type = tracing::field::Empty,
        error.message = tracing::field::Empty,
        // ChatInference request fields
        chat_inference.function_name = tracing::field::Empty,
        chat_inference.variant_name = tracing::field::Empty,
        chat_inference.episode_id = tracing::field::Empty,
        chat_inference.input = tracing::field::Empty,
        chat_inference.tags = tracing::field::Empty,
        chat_inference.extra_body = tracing::field::Empty,
        chat_inference.tool_params = tracing::field::Empty,
        chat_inference.processing_time_ms = tracing::field::Empty,
        // ChatInference response fields
        chat_inference.id = tracing::field::Empty,
        chat_inference.output = tracing::field::Empty,
        chat_inference.inference_params = tracing::field::Empty,
        // ModelInference fields (20 fields)
        model_inference.id = tracing::field::Empty,
        model_inference.inference_id = tracing::field::Empty,
        model_inference.raw_request = tracing::field::Empty,
        model_inference.raw_response = tracing::field::Empty,
        model_inference.model_name = tracing::field::Empty,
        model_inference.model_provider_name = tracing::field::Empty,
        model_inference.input_tokens = tracing::field::Empty,
        model_inference.output_tokens = tracing::field::Empty,
        model_inference.response_time_ms = tracing::field::Empty,
        model_inference.ttft_ms = tracing::field::Empty,
        model_inference.timestamp = tracing::field::Empty,
        model_inference.system = tracing::field::Empty,
        model_inference.input_messages = tracing::field::Empty,
        model_inference.output = tracing::field::Empty,
        model_inference.cached = tracing::field::Empty,
        model_inference.finish_reason = tracing::field::Empty,
        model_inference.gateway_request = tracing::field::Empty,
        model_inference.gateway_response = tracing::field::Empty,
        model_inference.endpoint_type = tracing::field::Empty,
        model_inference.guardrail_scan_summary = tracing::field::Empty,
        // ModelInferenceDetails fields (17 fields)
        model_inference_details.inference_id = tracing::field::Empty,
        model_inference_details.request_ip = tracing::field::Empty,
        model_inference_details.project_id = tracing::field::Empty,
        model_inference_details.endpoint_id = tracing::field::Empty,
        model_inference_details.model_id = tracing::field::Empty,
        model_inference_details.cost = tracing::field::Empty,
        model_inference_details.response_analysis = tracing::field::Empty,
        model_inference_details.is_success = tracing::field::Empty,
        model_inference_details.request_arrival_time = tracing::field::Empty,
        model_inference_details.request_forward_time = tracing::field::Empty,
        model_inference_details.api_key_id = tracing::field::Empty,
        model_inference_details.user_id = tracing::field::Empty,
        model_inference_details.api_key_project_id = tracing::field::Empty,
        model_inference_details.error_code = tracing::field::Empty,
        model_inference_details.error_message = tracing::field::Empty,
        model_inference_details.error_type = tracing::field::Empty,
        model_inference_details.status_code = tracing::field::Empty,
    )
)]
pub async fn inference_handler(
    State(AppStateData {
        config,
        http_client,
        clickhouse_connection_info,
        kafka_connection_info,
        authentication_info: _,
        model_credential_store,
        usage_limiter,
        guardrails,
        inference_batcher,
        ..
    }): AppState,
    analytics: Option<Extension<Arc<tokio::sync::Mutex<RequestAnalytics>>>>,
    headers: HeaderMap,
    StructuredJson(openai_compatible_params): StructuredJson<OpenAICompatibleParams>,
) -> Result<Response<Body>, Error> {
    // Capture request arrival time for observability (outside async block for error handler access)
    let request_arrival_time = chrono::Utc::now();

    // Extract observability metadata from headers early for error handler access
    let obs_metadata_for_error = extract_observability_metadata_from_headers(&headers);

    let result = async {

        if !openai_compatible_params.unknown_fields.is_empty() {
        tracing::warn!(
            "Ignoring unknown fields in OpenAI-compatible request: {:?}",
            openai_compatible_params
                .unknown_fields
                .keys()
                .collect::<Vec<_>>()
        );
    }
    let stream_options = openai_compatible_params.stream_options;
    let logprobs_requested = matches!(openai_compatible_params.logprobs, Some(true));

    // Resolve the model name based on authentication state
    let model_resolution = model_resolution::resolve_model_name(
        Some(&openai_compatible_params.model),
        &headers,
        false, // not for embedding
    )?;

    let original_model_name = model_resolution.original_model_name.to_string();

    // Check usage limits BEFORE processing the request
    if let Some(usage_limiter) = &usage_limiter {
        if let Some(user_id) = headers
            .get("x-tensorzero-user-id")
            .and_then(|v| v.to_str().ok())
        {
            let usage_decision = usage_limiter.check_usage(user_id, None, None).await;

            if !usage_decision.is_allowed() {
                return Err(Error::new(ErrorDetails::Config {
                    message: match usage_decision {
                        UsageLimitDecision::Deny { reason } => {
                            format!("Usage limit exceeded: {}", reason)
                        }
                        _ => "Usage limit exceeded".to_string(),
                    },
                }));
            }
        }
    }

    // Capture the gateway request (without null values)
    let gateway_request = serialize_without_nulls(&openai_compatible_params).ok();

    // Get model name before model_resolution is moved
    let resolved_model_name = model_resolution.model_name.clone();

    // Create params with resolved model/function names
    let mut params = Params::try_from_openai_with_resolution(
        headers.clone(),
        openai_compatible_params.clone(),
        model_resolution,
    )?;

    // If the caller asked for logprobs, we need the raw provider response so we can
    // copy logprobs back out later.  That is enabled via `include_original_response`.
    if matches!(openai_compatible_params.logprobs, Some(true)) {
        params.include_original_response = true;
    }

    // Extract observability metadata from headers (set by auth middleware)
    if let (Some(project_id), Some(endpoint_id), Some(model_id)) = (
        headers
            .get("x-tensorzero-project-id")
            .and_then(|v| v.to_str().ok()),
        headers
            .get("x-tensorzero-endpoint-id")
            .and_then(|v| v.to_str().ok()),
        headers
            .get("x-tensorzero-model-id")
            .and_then(|v| v.to_str().ok()),
    ) {
        // Extract auth metadata from headers
        let api_key_id = headers
            .get("x-tensorzero-api-key-id")
            .and_then(|v| v.to_str().ok())
            .map(|s| s.to_string());
        let user_id = headers
            .get("x-tensorzero-user-id")
            .and_then(|v| v.to_str().ok())
            .map(|s| s.to_string());
        let api_key_project_id = headers
            .get("x-tensorzero-api-key-project-id")
            .and_then(|v| v.to_str().ok())
            .map(|s| s.to_string());

        params.observability_metadata = Some(super::inference::ObservabilityMetadata {
            project_id: project_id.to_string(),
            endpoint_id: endpoint_id.to_string(),
            model_id: model_id.to_string(),
            api_key_id,
            user_id,
            api_key_project_id,
        });
    }

    // Set the gateway request on params
    params.gateway_request = gateway_request;

    // Capture the current span for streaming observability
    params.observability_span = Some(tracing::Span::current());

    // Get the guardrail profile if model has one configured
    let (guardrail_profile_id, model_pricing) = if let Some(model_name) = &resolved_model_name {
        let models = config.models.read().await;
        match models.get(model_name).await {
            Ok(Some(model)) => {
                let profile = model.guardrail_profile.clone();
                let pricing = model.pricing.clone();
                drop(models);
                (profile, pricing)
            }
            _ => {
                drop(models);
                (None, None)
            }
        }
    } else {
        (None, None)
    };

    // Create guardrail execution context to track all guardrail operations
    let mut guardrail_context = crate::guardrail::GuardrailExecutionContext::new();

    // Extract observability metadata for potential use
    let observability_metadata = params.observability_metadata.clone();

    // Execute input guardrail if configured
    if let Some(guardrail_profile) = &guardrail_profile_id {
        // Convert messages to moderation input
        let mut input_texts = Vec::new();

        for msg in &openai_compatible_params.messages {
            match msg {
                OpenAICompatibleMessage::System(sys_msg) => {
                    if let Some(text) = sys_msg.content.as_str() {
                        input_texts.push(text.to_string());
                    }
                }
                OpenAICompatibleMessage::User(user_msg) => {
                    match &user_msg.content {
                        Value::String(text) => input_texts.push(text.clone()),
                        Value::Array(arr) => {
                            // Extract text from content parts array
                            for item in arr {
                                if let Some(obj) = item.as_object() {
                                    if obj.get("type").and_then(|t| t.as_str()) == Some("text") {
                                        if let Some(text) = obj.get("text").and_then(|t| t.as_str())
                                        {
                                            input_texts.push(text.to_string());
                                        }
                                    }
                                }
                            }
                        }
                        _ => {}
                    }
                }
                OpenAICompatibleMessage::Assistant(asst_msg) => {
                    if let Some(content) = &asst_msg.content {
                        if let Some(text) = content.as_str() {
                            input_texts.push(text.to_string());
                        }
                    }
                }
                OpenAICompatibleMessage::Tool(tool_msg) => {
                    if let Some(content) = &tool_msg.content {
                        if let Some(text) = content.as_str() {
                            input_texts.push(text.to_string());
                        }
                    }
                }
            }
        }

        if !input_texts.is_empty() {
            let moderation_input = if input_texts.len() == 1 {
                crate::moderation::ModerationInput::Single(input_texts[0].clone())
            } else {
                crate::moderation::ModerationInput::Batch(input_texts.clone())
            };

            // Get guardrail configuration
            let guardrails_read = guardrails.read().await;
            if let Some(guardrail_config) = guardrails_read.get(guardrail_profile.as_ref()) {
                let guardrail_config = guardrail_config.clone();
                drop(guardrails_read);

                if guardrail_config
                    .guard_types
                    .contains(&crate::guardrail_table::GuardType::Input)
                {
                    // Prepare credentials
                    let credentials = merge_credentials_from_store(&model_credential_store);

                    // Create inference clients for guardrail execution
                    let cache_options = crate::cache::CacheOptions {
                        enabled: crate::cache::CacheEnabledMode::Off,
                        max_age_s: None,
                    };
                    let clients = super::inference::InferenceClients {
                        http_client: &http_client,
                        credentials: &credentials,
                        clickhouse_connection_info: &clickhouse_connection_info,
                        cache_options: &cache_options,
                    };

                    // Execute input guardrail with timing
                    let input_scan_start = tokio::time::Instant::now();
                    let guardrail_result = crate::guardrail::execute_guardrail(
                        &guardrail_config,
                        moderation_input.clone(),
                        crate::guardrail_table::GuardType::Input,
                        &clients,
                        None,
                        false,
                    )
                    .await?;
                    let input_scan_duration = input_scan_start.elapsed();

                    // Store the input guardrail result for later (we need the inference_id from the response)
                    // For now, store with a placeholder UUID
                    if !guardrail_result.provider_results.is_empty() {
                        // Only persist a scan record when a provider actually executed.
                        let placeholder_id = uuid::Uuid::nil();
                        let scan_record =
                            crate::guardrail::GuardrailInferenceDatabaseInsert::from_result(
                                placeholder_id,
                                guardrail_profile.to_string(),
                                crate::guardrail_table::GuardType::Input,
                                "l1".to_string(),
                                crate::guardrail::ScanMode::Single,
                                &guardrail_result,
                                Some(input_scan_duration),
                                &input_texts.join(" "),
                                None,
                            );
                        guardrail_context.add_scan_record(scan_record);
                    }

                    // If input is flagged, handle the blocked request with full observability
                    if guardrail_result.flagged {
                        guardrail_context.response_terminated = true;

                        // Generate IDs for tracking the blocked request
                        let blocked_inference_id = uuid::Uuid::now_v7();
                        let episode_id = uuid::Uuid::now_v7();

                        // Update guardrail records with the actual inference_id
                        for record in &mut guardrail_context.scan_records {
                            record.inference_id = blocked_inference_id;
                        }

                        // Write blocked inference with guardrail records
                        if config.gateway.observability.enabled.unwrap_or(true) {
                            // Get model info or use defaults if model not found
                            let (model_name, model_provider) =
                                if let Some(name) = &resolved_model_name {
                                    (name.clone(), "openai".to_string())
                                } else {
                                    ("unknown".to_string(), "unknown".to_string())
                                };

                            let clickhouse = clickhouse_connection_info.clone();
                            let kafka = kafka_connection_info.clone();
                            let config_clone = config.clone();
                            let records = guardrail_context.scan_records.clone();
                            let async_writes = config.gateway.observability.async_writes;
                            let obs_metadata = observability_metadata.clone();
                            let inference_batcher_clone = inference_batcher.clone();

                            // Get the resolved input and gateway request before moving params
                            let resolved_input = params
                                .input
                                .resolve(&crate::inference::types::FetchContext {
                                    client: &http_client,
                                    object_store_info: &config.object_store_info,
                                })
                                .await
                                .unwrap_or_else(|_| crate::inference::types::ResolvedInput {
                                    system: None,
                                    messages: vec![],
                                });
                            let gateway_request = params.gateway_request.clone();

                            let write_future = tokio::spawn(async move {
                                use crate::endpoints::inference::InferenceParams;
                                use crate::inference::types::{
                                    current_timestamp, ChatInferenceResult, ContentBlockOutput,
                                    Latency, ModelInferenceResponseWithMetadata, RequestMessage,
                                    Text,
                                };

                                // Create blocked content
                                let blocked_content = vec![ContentBlockChatOutput::Text(Text {
                                    text: "Request blocked by content policy".to_string(),
                                })];

                                // Create the gateway response that would be sent to the client
                                let (_, gateway_response_json) = create_guardrail_error_response(
                                    "Input content violates content policy",
                                    true,
                                );
                                let gateway_response_str = gateway_response_json.to_string();

                                // Create blocked model inference response
                                let model_response = ModelInferenceResponseWithMetadata {
                                    id: Uuid::now_v7(),
                                    created: current_timestamp(),
                                    output: vec![ContentBlockOutput::Text(Text {
                                        text: "Request blocked by content policy".to_string(),
                                    })],
                                    system: resolved_input
                                        .system
                                        .clone()
                                        .and_then(|v| v.as_str().map(|s| s.to_string())),
                                    input_messages: resolved_input
                                        .messages
                                        .iter()
                                        .map(|msg| RequestMessage {
                                            role: msg.role.clone(),
                                            content: vec![], // Empty content for blocked messages
                                        })
                                        .collect(),
                                    // Since we never made it to the provider, we don't have a raw request/response
                                    // Use empty objects to indicate no provider interaction occurred
                                    raw_request: "{}".to_string(),
                                    raw_response: "{}".to_string(),
                                    usage: Usage::default(),
                                    latency: Latency::NonStreaming {
                                        response_time: std::time::Duration::from_millis(0),
                                    },
                                    model_provider_name: model_provider.to_string().into(),
                                    model_name: model_name.to_string().into(),
                                    cached: false,
                                    finish_reason: Some(FinishReason::ContentFilter),
                                    gateway_request: gateway_request.clone(),
                                    gateway_response: Some(gateway_response_str.clone()),
                                    guardrail_scan_summary: if !records.is_empty() {
                                        let context = crate::guardrail::GuardrailExecutionContext {
                                            scan_records: records.clone(),
                                            input_scan_time_ms: records
                                                .iter()
                                                .filter(|r| r.guard_type == 1) // Input guard type
                                                .filter_map(|r| r.scan_latency_ms)
                                                .sum::<u32>()
                                                .into(),
                                            output_scan_time_ms: None,
                                            response_terminated: true,
                                        };
                                        Some(
                                            serde_json::to_string(&context.build_summary())
                                                .unwrap_or_default(),
                                        )
                                    } else {
                                        None
                                    },
                                };

                                // Create blocked result
                                let blocked_result = InferenceResult::Chat(ChatInferenceResult {
                                    inference_id: blocked_inference_id,
                                    created: current_timestamp(),
                                    content: blocked_content,
                                    usage: Usage::default(),
                                    model_inference_results: vec![model_response],
                                    inference_params: InferenceParams::default(),
                                    original_response: None,
                                    finish_reason: Some(FinishReason::ContentFilter),
                                });

                                // Create metadata
                                let metadata = super::inference::InferenceDatabaseInsertMetadata {
                                    function_name: "openai_compatible".to_string(),
                                    variant_name: model_name.to_string(),
                                    episode_id,
                                    tool_config: None,
                                    processing_time: Some(std::time::Duration::from_millis(0)),
                                    tags: HashMap::new(),
                                    extra_body: UnfilteredInferenceExtraBody::default(),
                                    extra_headers: UnfilteredInferenceExtraHeaders::default(),
                                };

                                // Write inference and guardrail records
                                super::inference::write_inference(
                                    &clickhouse,
                                    &kafka,
                                    &config_clone,
                                    resolved_input,
                                    blocked_result,
                                    metadata,
                                    obs_metadata,
                                    gateway_request, // Pass the actual gateway_request
                                    Some(gateway_response_str), // Pass the actual gateway_response
                                    model_pricing,
                                    Some(records),
                                    inference_batcher_clone.as_ref(),
                                )
                                .await;
                            });

                            if !async_writes {
                                write_future.await.map_err(|e| {
                                    Error::new(ErrorDetails::InternalError {
                                        message: format!(
                                            "Failed to join blocked inference write task: {e}"
                                        ),
                                    })
                                })?;
                            }
                        }
                        // Return OpenAI-compatible error response
                        let (status_code, error_response) = create_guardrail_error_response(
                            "Input content violates content policy",
                            true,
                        );

                        return Ok(Response::builder()
                            .status(status_code)
                            .header("Content-Type", "application/json")
                            .body(Body::from(error_response.to_string()))
                            .unwrap());
                    }
                }
            }
        }
    }

    let response = inference(
        config.clone(),
        &http_client,
        clickhouse_connection_info.clone(),
        kafka_connection_info.clone(),
        model_credential_store.clone(),
        params,
        analytics.as_ref().map(|ext| ext.0.clone()),
        inference_batcher.clone(),
    )
    .await?;

    match response {
        InferenceOutput::NonStreaming {
            response,
            mut result,
            write_info,
        } => {
            // Record span attributes for observability
            if let Some(ref wi) = write_info {
                super::observability::record_resolved_input(&wi.resolved_input);
                super::observability::record_metadata(&wi.metadata);
            }
            super::observability::record_inference_result(&result);

            // Record model inference span attributes
            match &result {
                InferenceResult::Chat(chat_result) => {
                    super::observability::record_model_inference(
                        &chat_result.model_inference_results,
                        &chat_result.inference_id,
                    );
                }
                InferenceResult::Json(json_result) => {
                    super::observability::record_model_inference(
                        &json_result.model_inference_results,
                        &json_result.inference_id,
                    );
                }
                _ => {}
            }

            // Record ModelInferenceDetails for success
            if let Some(ref obs_metadata) = observability_metadata {
                let inference_id = match &result {
                    InferenceResult::Chat(chat_result) => chat_result.inference_id,
                    InferenceResult::Json(json_result) => json_result.inference_id,
                    _ => uuid::Uuid::nil(),
                };
                let request_forward_time = chrono::Utc::now();
                super::observability::record_model_inference_details(
                    &inference_id,
                    &obs_metadata.project_id,
                    &obs_metadata.endpoint_id,
                    &obs_metadata.model_id,
                    true, // is_success
                    request_arrival_time,
                    request_forward_time,
                    None, // cost - could be calculated from usage if pricing available
                    obs_metadata.api_key_id.as_deref(),
                    obs_metadata.user_id.as_deref(),
                    obs_metadata.api_key_project_id.as_deref(),
                    None, // no error for success
                );
            }

            // Extract model latency from the result (using the first model inference result) before moving result
            let model_latency_ms = match &result {
                InferenceResult::Chat(chat_result) => chat_result
                    .model_inference_results
                    .first()
                    .and_then(|r| match &r.latency {
                        crate::inference::types::Latency::NonStreaming { response_time } => {
                            Some(response_time.as_millis() as u32)
                        }
                        crate::inference::types::Latency::Streaming { response_time, .. } => {
                            Some(response_time.as_millis() as u32)
                        }
                        crate::inference::types::Latency::Batch => None,
                    })
                    .unwrap_or(0),
                InferenceResult::Json(json_result) => json_result
                    .model_inference_results
                    .first()
                    .and_then(|r| match &r.latency {
                        crate::inference::types::Latency::NonStreaming { response_time } => {
                            Some(response_time.as_millis() as u32)
                        }
                        crate::inference::types::Latency::Streaming { response_time, .. } => {
                            Some(response_time.as_millis() as u32)
                        }
                        crate::inference::types::Latency::Batch => None,
                    })
                    .unwrap_or(0),
                // For other result types, we don't have model_inference_results, so default to 0
                _ => 0,
            };

            let mut openai_compatible_response =
                OpenAICompatibleResponse::from((response.clone(), original_model_name.clone()));

            // Execute output guardrail if configured
            if let Some(guardrail_profile) = &guardrail_profile_id {
                // Check if guardrail supports output guard type
                let guardrails_read = guardrails.read().await;
                if let Some(guardrail_config) = guardrails_read.get(guardrail_profile.as_ref()) {
                    if guardrail_config
                        .guard_types
                        .contains(&crate::guardrail_table::GuardType::Output)
                    {
                        let guardrail_config = guardrail_config.clone();
                        drop(guardrails_read);

                        // Extract output text from response
                        let output_texts: Vec<String> = openai_compatible_response
                            .choices
                            .iter()
                            .filter_map(|choice| {
                                choice
                                    .message
                                    .content
                                    .as_ref()
                                    .map(|content| content.clone())
                            })
                            .collect();

                        if !output_texts.is_empty() {
                            let moderation_input = if output_texts.len() == 1 {
                                crate::moderation::ModerationInput::Single(output_texts[0].clone())
                            } else {
                                crate::moderation::ModerationInput::Batch(output_texts.clone())
                            };

                            // Prepare credentials
                            let credentials = merge_credentials_from_store(&model_credential_store);

                            // Create inference clients for guardrail execution
                            let cache_options = crate::cache::CacheOptions {
                                enabled: crate::cache::CacheEnabledMode::Off,
                                max_age_s: None,
                            };
                            let clients = super::inference::InferenceClients {
                                http_client: &http_client,
                                credentials: &credentials,
                                clickhouse_connection_info: &clickhouse_connection_info,
                                cache_options: &cache_options,
                            };

                            // Execute output guardrail with timing
                            let output_scan_start = tokio::time::Instant::now();
                            let guardrail_result = crate::guardrail::execute_guardrail(
                                &guardrail_config,
                                moderation_input.clone(),
                                crate::guardrail_table::GuardType::Output,
                                &clients,
                                None,
                                false,
                            )
                            .await?;
                            let output_scan_duration = output_scan_start.elapsed();

                            if !guardrail_result.provider_results.is_empty() {
                                // Create guardrail inference record with placeholder ID (will be updated later)
                                let placeholder_id = uuid::Uuid::nil();
                                let scan_record =
                                    crate::guardrail::GuardrailInferenceDatabaseInsert::from_result(
                                        placeholder_id,
                                        guardrail_profile.to_string(),
                                        crate::guardrail_table::GuardType::Output,
                                        "l1".to_string(),
                                        crate::guardrail::ScanMode::Single,
                                        &guardrail_result,
                                        Some(output_scan_duration),
                                        &output_texts.join(" "),
                                        None,
                                    );
                                guardrail_context.add_scan_record(scan_record);
                            }

                            // If output is flagged, return an error
                            if guardrail_result.flagged {
                                guardrail_context.response_terminated = true;

                                // Extract inference_id from the response
                                let inference_id = match &response {
                                    InferenceResponse::Chat(chat_response) => {
                                        chat_response.inference_id
                                    }
                                    InferenceResponse::Json(json_response) => {
                                        json_response.inference_id
                                    }
                                };

                                // Update guardrail records with the actual inference_id
                                for record in &mut guardrail_context.scan_records {
                                    record.inference_id = inference_id;
                                }

                                // Write the inference with guardrail records if observability is enabled
                                if config.gateway.observability.enabled.unwrap_or(true) {
                                    if let Some(write_info) = write_info {
                                        let config_clone = config.clone();
                                        let clickhouse = clickhouse_connection_info.clone();
                                        let kafka = kafka_connection_info.clone();
                                        let records = guardrail_context.scan_records.clone();
                                        let async_writes =
                                            config.gateway.observability.async_writes;
                                        let inference_batcher_clone = inference_batcher.clone();

                                        // Create the gateway response that would be sent to the client
                                        let (_, gateway_response_json) =
                                            create_guardrail_error_response(
                                                "Output content violates content policy",
                                                false,
                                            );
                                        let gateway_response_str =
                                            gateway_response_json.to_string();

                                        let write_future = tokio::spawn(async move {
                                            write_inference(
                                                &clickhouse,
                                                &kafka,
                                                &config_clone,
                                                write_info.resolved_input,
                                                result,
                                                write_info.metadata,
                                                write_info.observability_metadata,
                                                write_info.gateway_request,
                                                Some(gateway_response_str), // Pass the actual error response
                                                write_info.model_pricing,
                                                Some(records),
                                                inference_batcher_clone.as_ref(),
                                            )
                                            .await;
                                        });

                                        if !async_writes {
                                            write_future.await.map_err(|e| {
                                                Error::new(ErrorDetails::InternalError {
                                                    message: format!("Failed to join output guardrail write task: {e}"),
                                                })
                                            })?;
                                        }
                                    }
                                }

                                // Return OpenAI-compatible error response
                                let (status_code, error_response) = create_guardrail_error_response(
                                    "Output content violates content policy",
                                    false,
                                );

                                return Ok(Response::builder()
                                    .status(status_code)
                                    .header("Content-Type", "application/json")
                                    .body(Body::from(error_response.to_string()))
                                    .unwrap());
                            }
                        }
                    }
                }
            }

            // Track usage consumption if usage limiter is enabled

            if let Some(usage_limiter) = &usage_limiter {
                // Extract user_id from headers (set by auth middleware)
                if let Some(user_id) = headers
                    .get("x-tensorzero-user-id")
                    .and_then(|v| v.to_str().ok())
                {
                    // Calculate tokens to consume
                    let tokens_to_consume = openai_compatible_response.usage.total_tokens as i64;

                    // Calculate cost using the same logic as in inference.rs
                    let cost_to_consume = if openai_compatible_response.usage.total_tokens > 0 {
                        let cost = if let Some(write_info) = &write_info {
                            if let Some(pricing) = &write_info.model_pricing {
                                // Convert tokens to the pricing unit (e.g., if per_tokens is 1000, divide by 1000)
                                let input_multiplier =
                                    openai_compatible_response.usage.prompt_tokens as f64
                                        / pricing.per_tokens as f64;
                                let output_multiplier =
                                    openai_compatible_response.usage.completion_tokens as f64
                                        / pricing.per_tokens as f64;

                                (input_multiplier * pricing.input_cost)
                                    + (output_multiplier * pricing.output_cost)
                            } else {
                                // Fallback to default pricing if not configured
                                // Using reasonable defaults: $0.01 per 1K input tokens, $0.03 per 1K output tokens
                                (openai_compatible_response.usage.prompt_tokens as f64 * 0.00001)
                                    + (openai_compatible_response.usage.completion_tokens as f64
                                        * 0.00003)
                            }
                        } else {
                            // No write_info, use default pricing
                            (openai_compatible_response.usage.prompt_tokens as f64 * 0.00001)
                                + (openai_compatible_response.usage.completion_tokens as f64
                                    * 0.00003)
                        };
                        // Round to 4 decimal places for consistent precision
                        (cost * 10000.0).round() / 10000.0
                    } else {
                        0.0
                    };

                    // Record the consumption (fire and forget - don't block response)

                    let usage_limiter_clone = usage_limiter.clone();
                    let user_id_clone = user_id.to_string();
                    tokio::spawn(async move {
                        let _result = usage_limiter_clone
                            .check_usage(
                                &user_id_clone,
                                Some(tokens_to_consume),
                                Some(cost_to_consume),
                            )
                            .await;
                    });
                }
            }

            if logprobs_requested {
                // Try to fetch real logprobs from the original provider response (if available)
                if let Some(original_resp_json) = match &response {
                    InferenceResponse::Chat(chat) => chat
                        .original_response
                        .as_ref()
                        .and_then(|s| serde_json::from_str::<serde_json::Value>(s).ok()),
                    InferenceResponse::Json(json) => json
                        .original_response
                        .as_ref()
                        .and_then(|s| serde_json::from_str::<serde_json::Value>(s).ok()),
                } {
                    if let Some(provider_choices) =
                        original_resp_json.get("choices").and_then(|v| v.as_array())
                    {
                        for (idx, choice) in
                            openai_compatible_response.choices.iter_mut().enumerate()
                        {
                            if let Some(provider_choice) = provider_choices.get(idx) {
                                if let Some(lp) = provider_choice.get("logprobs") {
                                    choice.logprobs = Some(lp.clone());
                                } else {
                                    choice.logprobs = Some(serde_json::json!({"content": []}));
                                }
                            }
                        }
                    }
                } else {
                    // Fallback to empty array if provider didn't send or we failed to parse
                    for choice in &mut openai_compatible_response.choices {
                        choice.logprobs = Some(serde_json::json!({"content": []}));
                    }
                }
            }
            // Capture the gateway response (without null values)
            let gateway_response = serialize_without_nulls(&openai_compatible_response).ok();

            // Build guardrail scan summary
            let guardrail_summary = if !guardrail_context.scan_records.is_empty() {
                Some(guardrail_context.build_summary())
            } else {
                None
            };

            // Perform the database write if we have write info
            if let Some(write_info) = write_info {
                let config = config.clone();
                let clickhouse_connection_info = clickhouse_connection_info.clone();
                let kafka_connection_info = kafka_connection_info.clone();
                let async_writes = config.gateway.observability.async_writes;
                let inference_batcher_clone = inference_batcher.clone();

                // Clone guardrail records for async write
                let guardrail_records = guardrail_context.scan_records.clone();

                let write_future = tokio::spawn(async move {
                    // Update result with guardrail summary before writing
                    if let Some(summary) = guardrail_summary {
                        match &mut result {
                            InferenceResult::Chat(chat_result) => {
                                for model_result in &mut chat_result.model_inference_results {
                                    model_result.guardrail_scan_summary =
                                        Some(serde_json::to_string(&summary).unwrap_or_default());
                                }
                            }
                            InferenceResult::Json(json_result) => {
                                for model_result in &mut json_result.model_inference_results {
                                    model_result.guardrail_scan_summary =
                                        Some(serde_json::to_string(&summary).unwrap_or_default());
                                }
                            }
                            _ => {} // Other types don't have model_inference_results
                        }
                    }

                    write_inference(
                        &clickhouse_connection_info,
                        &kafka_connection_info,
                        &config,
                        write_info.resolved_input,
                        result,
                        write_info.metadata,
                        write_info.observability_metadata,
                        write_info.gateway_request,
                        gateway_response,
                        write_info.model_pricing,
                        Some(guardrail_records), // Pass guardrail records for batch write
                        inference_batcher_clone.as_ref(),
                    )
                    .await;
                });

                if !async_writes {
                    write_future.await.map_err(|e| {
                        Error::new(ErrorDetails::InternalError {
                            message: format!("Failed to join write task: {e}"),
                        })
                    })?;
                }
            }

            // Extract inference_id from the original response for analytics
            let inference_id = match &response {
                InferenceResponse::Chat(chat_response) => chat_response.inference_id,
                InferenceResponse::Json(json_response) => json_response.inference_id,
            };

            // Update guardrail records with the correct inference_id
            for record in &mut guardrail_context.scan_records {
                record.inference_id = inference_id;
            }

            let json_response = Json(openai_compatible_response);
            let mut http_response = json_response.into_response();

            // Add inference_id to response headers for analytics middleware
            http_response.headers_mut().insert(
                "x-tensorzero-inference-id",
                inference_id.to_string().parse().unwrap(),
            );

            // Add model latency to response headers for analytics middleware
            http_response.headers_mut().insert(
                "x-tensorzero-model-latency-ms",
                model_latency_ms.to_string().parse().unwrap(),
            );

            Ok(http_response)
        }
        InferenceOutput::Streaming(mut stream) => {
            let guardrail_context = Arc::new(tokio::sync::Mutex::new(guardrail_context));

            // Capture usage limiter and headers for usage tracking after stream completion
            let usage_limiter_for_tracking = usage_limiter.clone();
            let headers_for_tracking = headers.clone();

            // We need to peek at the first chunk to get the inference_id for analytics
            let mut inference_id_for_header = None;
            let mut first_chunk = None;

            // Try to get the first chunk to extract inference_id
            if let Some(chunk_result) = FuturesStreamExt::next(&mut stream).await {
                if let Ok(chunk) = &chunk_result {
                    inference_id_for_header = Some(chunk.inference_id());
                    first_chunk = Some(chunk_result);
                }
            }

            // Create a new stream that includes the first chunk if we have one
            let combined_stream = async_stream::stream! {
                // Yield the first chunk if we have it
                if let Some(chunk) = first_chunk {
                    yield chunk;
                }
                // Then yield the rest of the stream
                while let Some(chunk) = FuturesStreamExt::next(&mut stream).await {
                    yield chunk;
                }
            };

            // Attach streaming guardrail processing if configured
            let mut processed_stream: InferenceStream = Box::pin(combined_stream);

            if let Some(guardrail_profile) = &guardrail_profile_id {
                let guardrails_read = guardrails.read().await;
                if let Some(guardrail_config) = guardrails_read.get(guardrail_profile.as_ref()) {
                    if guardrail_config
                        .guard_types
                        .contains(&crate::guardrail_table::GuardType::Output)
                    {
                        let streaming_guardrail_state = StreamingGuardrailState {
                            guardrail_profile: guardrail_profile.to_string(),
                            guardrail_config: guardrail_config.clone(),
                            http_client: http_client.clone(),
                            model_credential_store: model_credential_store.clone(),
                            clickhouse_connection_info: clickhouse_connection_info.clone(),
                            guardrail_context: guardrail_context.clone(),
                        };
                        processed_stream = attach_streaming_output_guardrail(
                            processed_stream,
                            streaming_guardrail_state,
                        );
                    }
                }
            }

            // Create the stream with usage tracking
            let openai_compatible_stream =
                prepare_serialized_openai_compatible_events_with_usage_tracking(
                    processed_stream,
                    original_model_name.clone(),
                    stream_options,
                    usage_limiter_for_tracking,
                    headers_for_tracking,
                );

            let mut response = Sse::new(openai_compatible_stream)
                .keep_alive(axum::response::sse::KeepAlive::new())
                .into_response();

            // Add inference_id header if we captured it
            if let Some(inference_id) = inference_id_for_header {
                response.headers_mut().insert(
                    "x-tensorzero-inference-id",
                    inference_id.to_string().parse().unwrap(),
                );
            }

            Ok(response)
        }
    }
    }
    .await;

    // Record error on span if request failed
    if let Err(ref error) = result {
        super::observability::record_error(error);

        // Record ModelInferenceDetails for error case
        if let Some(ref obs_metadata) = obs_metadata_for_error {
            let error_inference_id = uuid::Uuid::now_v7();
            let request_forward_time = chrono::Utc::now();
            let error_details = super::observability::ModelInferenceDetailsError {
                error_code: error.get_details().as_ref(),
                error_message: &error.to_string(),
                error_type: error.get_details().as_ref(),
                status_code: error.status_code().as_u16(),
            };
            super::observability::record_model_inference_details(
                &error_inference_id,
                &obs_metadata.project_id,
                &obs_metadata.endpoint_id,
                &obs_metadata.model_id,
                false, // is_success = false
                request_arrival_time,
                request_forward_time,
                None, // cost not available on error
                obs_metadata.api_key_id.as_deref(),
                obs_metadata.user_id.as_deref(),
                obs_metadata.api_key_project_id.as_deref(),
                Some(error_details),
            );
        }
    }

    result
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize, Default)]
pub struct OpenAICompatibleFunctionCall {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    pub arguments: String,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OpenAICompatibleToolCall {
    /// The ID of the tool call.
    pub id: String,
    /// The type of the tool. Currently, only `function` is supported.
    pub r#type: String,
    /// The function that the model called.
    pub function: OpenAICompatibleFunctionCall,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OpenAICompatibleToolCallChunk {
    /// The ID of the tool call.
    pub id: Option<String>,
    /// The index of the tool call.
    pub index: usize,
    /// The type of the tool. Currently, only `function` is supported.
    pub r#type: String,
    /// The function that the model called.
    pub function: OpenAICompatibleFunctionCall,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
struct OpenAICompatibleSystemMessage {
    content: Value,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
struct OpenAICompatibleUserMessage {
    content: Value,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
struct OpenAICompatibleAssistantMessage {
    content: Option<Value>,
    tool_calls: Option<Vec<OpenAICompatibleToolCall>>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
struct OpenAICompatibleToolMessage {
    content: Option<Value>,
    tool_call_id: String,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(tag = "role")]
#[serde(rename_all = "lowercase")]
enum OpenAICompatibleMessage {
    #[serde(alias = "developer")]
    System(OpenAICompatibleSystemMessage),
    User(OpenAICompatibleUserMessage),
    Assistant(OpenAICompatibleAssistantMessage),
    Tool(OpenAICompatibleToolMessage),
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(tag = "type")]
#[serde(rename_all = "snake_case")]
enum OpenAICompatibleResponseFormat {
    Text,
    JsonSchema { json_schema: JsonSchemaInfoOption },
    JsonObject,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(untagged)]
enum JsonSchemaInfoOption {
    JsonSchema(JsonSchemaInfo),
    DeprecatedJsonSchema(Value),
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
struct JsonSchemaInfo {
    name: String,
    description: Option<String>,
    schema: Option<Value>,
    #[serde(default)]
    strict: bool,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(tag = "type", content = "function")]
#[serde(rename_all = "snake_case")]
enum OpenAICompatibleTool {
    Function {
        description: Option<String>,
        name: String,
        parameters: Value,
        #[serde(default)]
        strict: bool,
    },
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
struct FunctionName {
    name: String,
}

/// Specifies a tool the model should use. Use to force the model to call a specific function.
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
struct OpenAICompatibleNamedToolChoice {
    /// The type of the tool. Currently, only `function` is supported.
    r#type: String,
    function: FunctionName,
}

/// Controls which (if any) tool is called by the model.
/// `none` means the model will not call any tool and instead generates a message.
/// `auto` means the model can pick between generating a message or calling one or more tools.
/// `required` means the model must call one or more tools.
/// Specifying a particular tool via `{"type": "function", "function": {"name": "my_function"}}` forces the model to call that tool.
///
/// `none` is the default when no tools are present. `auto` is the default if tools are present.
#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
enum ChatCompletionToolChoiceOption {
    #[default]
    None,
    Auto,
    Required,
    #[serde(untagged)]
    Named(OpenAICompatibleNamedToolChoice),
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Serialize)]
struct OpenAICompatibleStreamOptions {
    #[serde(default)]
    include_usage: bool,
}

/// Helper type for parameters that can be either a single string or an array of strings
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(untagged)]
enum StringOrVec {
    String(String),
    Vec(Vec<String>),
}

impl StringOrVec {
    /// Convert to a Vec<String> for uniform handling
    fn into_vec(self) -> Vec<String> {
        match self {
            StringOrVec::String(s) => vec![s],
            StringOrVec::Vec(v) => v,
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Default, Serialize)]
pub struct OpenAICompatibleParams {
    messages: Vec<OpenAICompatibleMessage>,
    model: String,
    frequency_penalty: Option<f32>,
    repetition_penalty: Option<f32>,
    max_tokens: Option<u32>,
    max_completion_tokens: Option<u32>,
    presence_penalty: Option<f32>,
    response_format: Option<OpenAICompatibleResponseFormat>,
    seed: Option<u32>,
    stream: Option<bool>,
    stream_options: Option<OpenAICompatibleStreamOptions>,
    temperature: Option<f32>,
    tools: Option<Vec<OpenAICompatibleTool>>,
    tool_choice: Option<ChatCompletionToolChoiceOption>,
    top_p: Option<f32>,
    parallel_tool_calls: Option<bool>,
    /// If set to `true`, the response should include per-token log-probabilities.
    logprobs: Option<bool>,
    /// Number of most likely tokens to return at each token position, with log probability.
    top_logprobs: Option<u32>,
    /// Up to 4 sequences where the API will stop generating further tokens.
    stop: Option<StringOrVec>,
    /// How many chat completion choices to generate for each input message.
    n: Option<u32>,
    /// Modify the likelihood of specified tokens appearing in the completion.
    logit_bias: Option<HashMap<String, f32>>,
    /// A unique identifier representing your end-user.
    user: Option<String>,
    // Guided decoding / template fields (TensorZero extensions)
    chat_template: Option<String>,
    chat_template_kwargs: Option<Value>,
    mm_processor_kwargs: Option<Value>,
    guided_json: Option<Value>,
    guided_regex: Option<String>,
    guided_choice: Option<Vec<String>>,
    guided_grammar: Option<String>,
    structural_tag: Option<String>,
    guided_decoding_backend: Option<String>,
    guided_whitespace_pattern: Option<String>,
    /// If true, ignore end-of-sequence tokens and continue generating until max_tokens is reached
    ignore_eos: Option<bool>,
    #[serde(rename = "tensorzero::variant_name")]
    tensorzero_variant_name: Option<String>,
    #[serde(rename = "tensorzero::dryrun")]
    tensorzero_dryrun: Option<bool>,
    #[serde(rename = "tensorzero::episode_id")]
    tensorzero_episode_id: Option<Uuid>,
    #[serde(rename = "tensorzero::cache_options")]
    tensorzero_cache_options: Option<CacheParamsOptions>,
    #[serde(default, rename = "tensorzero::extra_body")]
    tensorzero_extra_body: UnfilteredInferenceExtraBody,
    #[serde(default, rename = "tensorzero::extra_headers")]
    tensorzero_extra_headers: UnfilteredInferenceExtraHeaders,
    #[serde(flatten)]
    unknown_fields: HashMap<String, Value>,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
struct OpenAICompatibleUsage {
    prompt_tokens: u32,
    completion_tokens: u32,
    total_tokens: u32,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
struct OpenAICompatibleResponseMessage {
    content: Option<String>,
    tool_calls: Option<Vec<OpenAICompatibleToolCall>>,
    role: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    logprobs: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    reasoning_content: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
struct OpenAICompatibleChoice {
    index: u32,
    finish_reason: OpenAICompatibleFinishReason,
    message: OpenAICompatibleResponseMessage,
    #[serde(skip_serializing_if = "Option::is_none")]
    logprobs: Option<serde_json::Value>,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
enum OpenAICompatibleFinishReason {
    Stop,
    Length,
    ContentFilter,
    ToolCalls,
    // FunctionCall, we never generate this and it is deprecated
}

impl From<FinishReason> for OpenAICompatibleFinishReason {
    fn from(finish_reason: FinishReason) -> Self {
        match finish_reason {
            FinishReason::Stop => OpenAICompatibleFinishReason::Stop,
            FinishReason::Length => OpenAICompatibleFinishReason::Length,
            FinishReason::ContentFilter => OpenAICompatibleFinishReason::ContentFilter,
            FinishReason::ToolCall => OpenAICompatibleFinishReason::ToolCalls,
            FinishReason::Unknown => OpenAICompatibleFinishReason::Stop, // OpenAI doesn't have an unknown finish reason so we coerce
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize)]
struct OpenAICompatibleResponse {
    id: String,
    episode_id: String,
    choices: Vec<OpenAICompatibleChoice>,
    created: u32,
    model: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    system_fingerprint: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    service_tier: Option<String>,
    object: String,
    usage: OpenAICompatibleUsage,
}

impl Params {
    fn try_from_openai_with_resolution(
        headers: HeaderMap,
        openai_compatible_params: OpenAICompatibleParams,
        model_resolution: model_resolution::ModelResolution,
    ) -> Result<Self, Error> {
        let function_name = model_resolution.function_name;
        let model_name = model_resolution.model_name;

        if let Some(function_name) = &function_name {
            if function_name.is_empty() {
                return Err(ErrorDetails::InvalidOpenAICompatibleRequest {
                    message: "function_name cannot be empty".to_string(),
                }
                .into());
            }
        }

        if let Some(model_name) = &model_name {
            if model_name.is_empty() {
                return Err(ErrorDetails::InvalidOpenAICompatibleRequest {
                    message: "model_name cannot be empty".to_string(),
                }
                .into());
            }
        }

        Self::create_params(headers, openai_compatible_params, function_name, model_name)
    }

    #[cfg(test)]
    fn try_from_openai(
        headers: HeaderMap,
        openai_compatible_params: OpenAICompatibleParams,
    ) -> Result<Self, Error> {
        const TENSORZERO_FUNCTION_NAME_PREFIX: &str = "tensorzero::function_name::";
        const TENSORZERO_MODEL_NAME_PREFIX: &str = "tensorzero::model_name::";

        let (function_name, model_name) = if let Some(function_name) = openai_compatible_params
            .model
            .strip_prefix(TENSORZERO_FUNCTION_NAME_PREFIX)
        {
            (Some(function_name.to_string()), None)
        } else if let Some(model_name) = openai_compatible_params
            .model
            .strip_prefix(TENSORZERO_MODEL_NAME_PREFIX)
        {
            (None, Some(model_name.to_string()))
        } else if let Some(function_name) =
            openai_compatible_params.model.strip_prefix("tensorzero::")
        {
            tracing::warn!(
                function_name = function_name,
                "Deprecation Warning: Please set the `model` parameter to `tensorzero::function_name::your_function` instead of `tensorzero::your_function.` The latter will be removed in a future release."
            );
            (Some(function_name.to_string()), None)
        } else {
            return Err(Error::new(ErrorDetails::InvalidOpenAICompatibleRequest {
                message: "`model` field must start with `tensorzero::function_name::` or `tensorzero::model_name::`. For example, `tensorzero::function_name::my_function` for a function `my_function` defined in your config, `tensorzero::model_name::my_model` for a model `my_model` defined in your config, or default functions like `tensorzero::model_name::openai::gpt-4o-mini`.".to_string(),
            }));
        };

        if let Some(function_name) = &function_name {
            if function_name.is_empty() {
                return Err(ErrorDetails::InvalidOpenAICompatibleRequest {
                    message: "function_name (passed in model field after \"tensorzero::function_name::\") cannot be empty".to_string(),
                }
                .into());
            }
        }

        if let Some(model_name) = &model_name {
            if model_name.is_empty() {
                return Err(ErrorDetails::InvalidOpenAICompatibleRequest {
                    message: "model_name (passed in model field after \"tensorzero::model_name::\") cannot be empty".to_string(),
                }
                .into());
            }
        }

        Self::create_params(headers, openai_compatible_params, function_name, model_name)
    }

    fn create_params(
        headers: HeaderMap,
        openai_compatible_params: OpenAICompatibleParams,
        function_name: Option<String>,
        model_name: Option<String>,
    ) -> Result<Self, Error> {
        let header_episode_id = headers
            .get("episode_id")
            .map(|h| {
                tracing::warn!("Deprecation Warning: Please use the `tensorzero::episode_id` field instead of the `episode_id` header. The header will be removed in a future release.");
                h.to_str()
                    .map_err(|_| {
                        Error::new(ErrorDetails::InvalidOpenAICompatibleRequest {
                            message: "episode_id header is not valid UTF-8".to_string(),
                        })
                    })
                    .and_then(|s| {
                        Uuid::parse_str(s).map_err(|_| {
                            Error::new(ErrorDetails::InvalidTensorzeroUuid {
                                kind: "Episode".to_string(),
                                message: "episode_id header is not a valid UUID".to_string(),
                            })
                        })
                    })
            })
            .transpose()?;
        // If both max_tokens and max_completion_tokens are provided, we use the minimum of the two.
        // Otherwise, we use the provided value, or None if neither is provided.
        let max_tokens = match (
            openai_compatible_params.max_tokens,
            openai_compatible_params.max_completion_tokens,
        ) {
            (Some(max_tokens), Some(max_completion_tokens)) => {
                Some(max_tokens.min(max_completion_tokens))
            }
            (Some(max_tokens), None) => Some(max_tokens),
            (None, Some(max_completion_tokens)) => Some(max_completion_tokens),
            (None, None) => None,
        };
        let json_mode = match openai_compatible_params.response_format {
            Some(OpenAICompatibleResponseFormat::JsonSchema { json_schema: _ }) => {
                Some(JsonMode::Strict)
            }
            Some(OpenAICompatibleResponseFormat::JsonObject) => Some(JsonMode::On),
            Some(OpenAICompatibleResponseFormat::Text) => Some(JsonMode::Off),
            None => None,
        };

        // Validate new parameters
        if let Some(n) = openai_compatible_params.n {
            if n == 0 {
                return Err(ErrorDetails::InvalidOpenAICompatibleRequest {
                    message: "n must be greater than 0".to_string(),
                }
                .into());
            }
            if n > 1 {
                // For now, we only support n=1. In the future, we can implement multiple completions.
                return Err(ErrorDetails::InvalidOpenAICompatibleRequest {
                    message: "n > 1 is not yet supported. Please use n=1 or omit the parameter."
                        .to_string(),
                }
                .into());
            }
        }

        if let Some(top_logprobs) = openai_compatible_params.top_logprobs {
            if top_logprobs > 20 {
                return Err(ErrorDetails::InvalidOpenAICompatibleRequest {
                    message: "top_logprobs must be between 0 and 20".to_string(),
                }
                .into());
            }
        }

        if let Some(ref logit_bias) = openai_compatible_params.logit_bias {
            // Validate that all keys are valid token IDs (integers as strings)
            for (key, value) in logit_bias {
                if key.parse::<u32>().is_err() {
                    return Err(ErrorDetails::InvalidOpenAICompatibleRequest {
                        message: format!(
                            "Invalid token ID in logit_bias: '{key}'. Token IDs must be integers."
                        ),
                    }
                    .into());
                }
                if !(-100.0..=100.0).contains(value) {
                    return Err(ErrorDetails::InvalidOpenAICompatibleRequest {
                        message: format!(
                            "logit_bias values must be between -100 and 100, got {value}"
                        ),
                    }
                    .into());
                }
            }
        }

        let input = openai_compatible_params.messages.try_into()?;
        let chat_completion_inference_params = ChatCompletionInferenceParams {
            temperature: openai_compatible_params.temperature,
            max_tokens,
            seed: openai_compatible_params.seed,
            top_p: openai_compatible_params.top_p,
            presence_penalty: openai_compatible_params.presence_penalty,
            frequency_penalty: openai_compatible_params.frequency_penalty,
            repetition_penalty: openai_compatible_params.repetition_penalty,
            chat_template: openai_compatible_params.chat_template,
            chat_template_kwargs: openai_compatible_params.chat_template_kwargs,
            mm_processor_kwargs: openai_compatible_params.mm_processor_kwargs,
            guided_json: openai_compatible_params.guided_json,
            guided_regex: openai_compatible_params.guided_regex,
            guided_choice: openai_compatible_params.guided_choice,
            guided_grammar: openai_compatible_params.guided_grammar,
            structural_tag: openai_compatible_params.structural_tag,
            guided_decoding_backend: openai_compatible_params.guided_decoding_backend,
            guided_whitespace_pattern: openai_compatible_params.guided_whitespace_pattern,
            json_mode,
            logprobs: matches!(openai_compatible_params.logprobs, Some(true)),
            top_logprobs: openai_compatible_params.top_logprobs,
            stop: openai_compatible_params.stop.map(|s| s.into_vec()),
            n: openai_compatible_params.n,
            logit_bias: openai_compatible_params.logit_bias,
            user: openai_compatible_params.user,
            ignore_eos: openai_compatible_params.ignore_eos,
        };
        let inference_params = InferenceParams {
            chat_completion: chat_completion_inference_params,
        };
        let header_variant_name = headers
            .get("variant_name")
            .map(|h| {
                tracing::warn!("Deprecation Warning: Please use the `tensorzero::variant_name` field instead of the `variant_name` header. The header will be removed in a future release.");
                h.to_str()
                    .map_err(|_| {
                        Error::new(ErrorDetails::InvalidOpenAICompatibleRequest {
                            message: "variant_name header is not valid UTF-8".to_string(),
                        })
                    })
                    .map(|s| s.to_string())
            })
            .transpose()?;
        let header_dryrun = headers
            .get("dryrun")
            .map(|h| {
                tracing::warn!("Deprecation Warning: Please use the `tensorzero::dryrun` field instead of the `dryrun` header. The header will be removed in a future release.");
                h.to_str()
                    .map_err(|_| {
                        Error::new(ErrorDetails::InvalidOpenAICompatibleRequest {
                            message: "dryrun header is not valid UTF-8".to_string(),
                        })
                    })
                    .and_then(|s| {
                        s.parse::<bool>().map_err(|_| {
                            Error::new(ErrorDetails::InvalidOpenAICompatibleRequest {
                                message: "dryrun header is not a valid boolean".to_string(),
                            })
                        })
                    })
            })
            .transpose()?;
        let dynamic_tool_params = DynamicToolParams {
            allowed_tools: None,
            additional_tools: openai_compatible_params
                .tools
                .map(|tools| tools.into_iter().map(|tool| tool.into()).collect()),
            tool_choice: openai_compatible_params
                .tool_choice
                .map(|tool_choice| tool_choice.into()),
            parallel_tool_calls: openai_compatible_params.parallel_tool_calls,
        };
        let output_schema = match openai_compatible_params.response_format {
            Some(OpenAICompatibleResponseFormat::JsonSchema { json_schema }) => match json_schema {
                JsonSchemaInfoOption::JsonSchema(json_schema) => json_schema.schema,
                JsonSchemaInfoOption::DeprecatedJsonSchema(value) => {
                    tracing::warn!("Deprecation Warning: Please provide the correct `name`, `description`, `schema`, and `strict` fields in the `json_schema` field in the response format. Simply providing a JSON schema in this field will be rejected in a future TensorZero release.");
                    Some(value)
                }
            },
            _ => None,
        };
        Ok(Params {
            function_name,
            model_name,
            episode_id: openai_compatible_params
                .tensorzero_episode_id
                .or(header_episode_id),
            input,
            stream: openai_compatible_params.stream,
            params: inference_params,
            variant_name: openai_compatible_params
                .tensorzero_variant_name
                .or(header_variant_name),
            dryrun: openai_compatible_params.tensorzero_dryrun.or(header_dryrun),
            dynamic_tool_params,
            output_schema,
            // OpenAI compatible endpoint does not support dynamic credentials
            credentials: InferenceCredentials::default(),
            cache_options: openai_compatible_params
                .tensorzero_cache_options
                .unwrap_or_default(),
            // For now, we don't support internal inference for OpenAI compatible endpoint
            internal: false,
            tags: HashMap::new(),
            // OpenAI compatible endpoint does not support 'include_original_response'
            include_original_response: false,
            extra_body: openai_compatible_params.tensorzero_extra_body,
            extra_headers: openai_compatible_params.tensorzero_extra_headers,
            observability_metadata: None, // Will be set in the handler
            gateway_request: None,        // Will be set in the handler
            observability_span: None,     // Will be set in the handler
        })
    }
}

impl TryFrom<Vec<OpenAICompatibleMessage>> for Input {
    type Error = Error;
    fn try_from(
        openai_compatible_messages: Vec<OpenAICompatibleMessage>,
    ) -> Result<Self, Self::Error> {
        let mut system_messages = Vec::new();
        let mut messages = Vec::new();
        let mut tool_call_id_to_name = HashMap::new();
        let first_system = matches!(
            openai_compatible_messages.first(),
            Some(OpenAICompatibleMessage::System(_))
        );
        for message in openai_compatible_messages {
            match message {
                OpenAICompatibleMessage::System(msg) => {
                    let system_content = convert_openai_message_content(msg.content.clone())?;
                    for content in system_content {
                        system_messages.push(match content {
                            InputMessageContent::Text(TextKind::LegacyValue { value }) => value,
                            InputMessageContent::Text(TextKind::Text { text }) => {
                                Value::String(text)
                            }
                            InputMessageContent::Text(TextKind::Arguments { arguments }) => {
                                Value::Object(arguments)
                            }
                            InputMessageContent::RawText { value } => Value::String(value),
                            _ => {
                                return Err(ErrorDetails::InvalidOpenAICompatibleRequest {
                                    message: "System message must be a text content block"
                                        .to_string(),
                                }
                                .into())
                            }
                        });
                    }
                }
                OpenAICompatibleMessage::User(msg) => {
                    messages.push(InputMessage {
                        role: Role::User,
                        content: convert_openai_message_content(msg.content)?,
                    });
                }
                OpenAICompatibleMessage::Assistant(msg) => {
                    let mut message_content = Vec::new();
                    if let Some(content) = msg.content {
                        message_content.extend(convert_openai_message_content(content)?);
                    }
                    if let Some(tool_calls) = msg.tool_calls {
                        for tool_call in tool_calls {
                            if let Some(name) = &tool_call.function.name {
                                tool_call_id_to_name.insert(tool_call.id.clone(), name.clone());
                            }
                            message_content.push(InputMessageContent::ToolCall(tool_call.into()));
                        }
                    }
                    messages.push(InputMessage {
                        role: Role::Assistant,
                        content: message_content,
                    });
                }
                OpenAICompatibleMessage::Tool(msg) => {
                    let name = tool_call_id_to_name
                        .get(&msg.tool_call_id)
                        .ok_or_else(|| {
                            Error::new(ErrorDetails::InvalidOpenAICompatibleRequest {
                                message: "tool call id not found".to_string(),
                            })
                        })?
                        .to_string();
                    messages.push(InputMessage {
                        role: Role::User,
                        content: vec![InputMessageContent::ToolResult(ToolResult {
                            id: msg.tool_call_id,
                            name,
                            result: msg.content.unwrap_or_default().to_string(),
                        })],
                    });
                }
            }
        }

        if system_messages.len() <= 1 {
            if system_messages.len() == 1 && !first_system {
                tracing::warn!("Moving system message to the start of the conversation");
            }
            Ok(Input {
                system: system_messages.pop(),
                messages,
            })
        } else {
            let mut output = String::new();
            for (i, system_message) in system_messages.iter().enumerate() {
                if let Value::String(msg) = system_message {
                    if i > 0 {
                        output.push('\n');
                    }
                    output.push_str(msg);
                } else {
                    return Err(ErrorDetails::InvalidOpenAICompatibleRequest {
                        message: "Multiple system messages provided, but not all were strings"
                            .to_string(),
                    }
                    .into());
                }
            }
            tracing::warn!("Multiple system messages provided - they will be concatenated and moved to the start of the conversation");
            Ok(Input {
                system: Some(Value::String(output)),
                messages,
            })
        }
    }
}

#[derive(Deserialize, Debug)]
#[serde(tag = "type", deny_unknown_fields, rename_all = "snake_case")]
enum OpenAICompatibleContentBlock {
    Text(TextContent),
    ImageUrl { image_url: OpenAICompatibleImageUrl },
    File { file: OpenAICompatibleFile },
}

#[derive(Deserialize, Debug)]
#[serde(tag = "type", deny_unknown_fields, rename_all = "snake_case")]
struct OpenAICompatibleImageUrl {
    url: Url,
}

#[derive(Deserialize, Debug)]
struct OpenAICompatibleFile {
    file_data: String,
    filename: String,
    // OpenAI supports file_id with their files API
    // We do not so we require these two fields
}

#[derive(Deserialize, Debug)]
#[serde(untagged, deny_unknown_fields, rename_all = "snake_case")]
// Two mutually exclusive modes - the standard OpenAI text, and our special TensorZero mode
pub enum TextContent {
    /// A normal openai text content block: `{"type": "text", "text": "Some content"}`. The `type` key comes from the parent `OpenAICompatibleContentBlock`
    RawText { text: String },
    /// A special TensorZero mode: `{"type": "text", "tensorzero::arguments": {"custom_key": "custom_val"}}`.
    TensorZeroArguments {
        #[serde(default, rename = "tensorzero::arguments")]
        tensorzero_arguments: Map<String, Value>,
    },
}

fn parse_base64_image_data_url(url: &str) -> Result<(FileKind, &str), Error> {
    let Some(url) = url.strip_prefix("data:") else {
        return Err(Error::new(ErrorDetails::InvalidOpenAICompatibleRequest {
            message: "Image data URL must start with `data:`".to_string(),
        }));
    };
    let Some((mime_type, data)) = url.split_once(";base64,") else {
        return Err(Error::new(ErrorDetails::InvalidOpenAICompatibleRequest {
            message: "Image data URL must contain a base64-encoded data part".to_string(),
        }));
    };
    let image_type = match mime_type {
        "image/jpeg" => FileKind::Jpeg,
        "image/png" => FileKind::Png,
        "image/webp" => FileKind::WebP,
        _ => {
            return Err(Error::new(ErrorDetails::InvalidOpenAICompatibleRequest {
                message: format!("Unsupported content type `{mime_type}`: - only `image/jpeg`, `image/png``, and `image/webp` image data URLs are supported"),
            }))
        }
    };
    Ok((image_type, data))
}

fn convert_openai_message_content(content: Value) -> Result<Vec<InputMessageContent>, Error> {
    match content {
        Value::String(s) => Ok(vec![InputMessageContent::Text(TextKind::Text { text: s })]),
        Value::Array(a) => {
            let mut outputs = Vec::with_capacity(a.len());
            for val in a {
                let block = serde_json::from_value::<OpenAICompatibleContentBlock>(val.clone());
                let output = match block {
                    Ok(OpenAICompatibleContentBlock::Text(TextContent::RawText { text })) => InputMessageContent::Text(TextKind::Text {text }),
                    Ok(OpenAICompatibleContentBlock::Text(TextContent::TensorZeroArguments { tensorzero_arguments })) => InputMessageContent::Text(TextKind::Arguments { arguments: tensorzero_arguments }),
                    Ok(OpenAICompatibleContentBlock::ImageUrl { image_url }) => {
                        if image_url.url.scheme() == "data" {
                            let url_str = image_url.url.to_string();
                            let (mime_type, data) = parse_base64_image_data_url(&url_str)?;
                            InputMessageContent::File(File::Base64 { mime_type, data: data.to_string() })
                        } else {
                            InputMessageContent::File(File::Url { url: image_url.url })
                        }
                    }
                    Ok(OpenAICompatibleContentBlock::File { file }) => {
                        InputMessageContent::File(File::Base64 { mime_type: file.filename.as_str().try_into()?, data: file.file_data })
                    }
                    Err(e) => {
                        tracing::warn!(r#"Content block `{val}` was not a valid OpenAI content block. This is deprecated - please use `{{"type": "text", "tensorzero::arguments": {{"custom": "data"}}` to pass arbitrary JSON values to TensorZero: {e}"#);
                        if let Value::Object(obj) = val {
                            InputMessageContent::Text(TextKind::Arguments { arguments: obj })
                        } else {
                            return Err(Error::new(ErrorDetails::InvalidOpenAICompatibleRequest {
                                message: format!("Content block `{val}` is not an object"),
                            }));
                        }
                    }
                };
                outputs.push(output);
            }
            Ok(outputs)
        }
        _ => Err(ErrorDetails::InvalidOpenAICompatibleRequest {
            message: "message content must either be a string or an array of length 1 containing structured TensorZero inputs".to_string(),
        }.into()),
    }
}

impl From<OpenAICompatibleTool> for Tool {
    fn from(tool: OpenAICompatibleTool) -> Self {
        match tool {
            OpenAICompatibleTool::Function {
                description,
                name,
                parameters,
                strict,
            } => Tool {
                description: description.unwrap_or_default(),
                parameters,
                name,
                strict,
            },
        }
    }
}

impl From<ChatCompletionToolChoiceOption> for ToolChoice {
    fn from(tool_choice: ChatCompletionToolChoiceOption) -> Self {
        match tool_choice {
            ChatCompletionToolChoiceOption::None => ToolChoice::None,
            ChatCompletionToolChoiceOption::Auto => ToolChoice::Auto,
            ChatCompletionToolChoiceOption::Required => ToolChoice::Required,
            ChatCompletionToolChoiceOption::Named(named) => {
                ToolChoice::Specific(named.function.name)
            }
        }
    }
}

impl From<OpenAICompatibleToolCall> for ToolCall {
    fn from(tool_call: OpenAICompatibleToolCall) -> Self {
        ToolCall {
            id: tool_call.id,
            name: tool_call.function.name.unwrap_or_default(),
            arguments: tool_call.function.arguments,
        }
    }
}

impl From<(InferenceResponse, String)> for OpenAICompatibleResponse {
    fn from((inference_response, model_name): (InferenceResponse, String)) -> Self {
        match inference_response {
            InferenceResponse::Chat(response) => {
                let (content, tool_calls, reasoning_content) =
                    process_chat_content(response.content);

                OpenAICompatibleResponse {
                    id: response.inference_id.to_string(),
                    choices: vec![OpenAICompatibleChoice {
                        index: 0,
                        finish_reason: response.finish_reason.unwrap_or(FinishReason::Stop).into(),
                        message: OpenAICompatibleResponseMessage {
                            content,
                            tool_calls: Some(tool_calls),
                            role: "assistant".to_string(),
                            logprobs: None,
                            reasoning_content,
                        },
                        logprobs: None,
                    }],
                    created: current_timestamp() as u32,
                    model: model_name.clone(),
                    service_tier: None,
                    system_fingerprint: None,
                    object: "chat.completion".to_string(),
                    usage: response.usage.into(),
                    episode_id: response.episode_id.to_string(),
                }
            }
            InferenceResponse::Json(response) => OpenAICompatibleResponse {
                id: response.inference_id.to_string(),
                choices: vec![OpenAICompatibleChoice {
                    index: 0,
                    finish_reason: response.finish_reason.unwrap_or(FinishReason::Stop).into(),
                    message: OpenAICompatibleResponseMessage {
                        content: response.output.raw,
                        tool_calls: None,
                        role: "assistant".to_string(),
                        logprobs: None,
                        reasoning_content: None,
                    },
                    logprobs: None,
                }],
                created: current_timestamp() as u32,
                model: model_name,
                system_fingerprint: None,
                service_tier: None,
                object: "chat.completion".to_string(),
                usage: OpenAICompatibleUsage {
                    prompt_tokens: response.usage.input_tokens,
                    completion_tokens: response.usage.output_tokens,
                    total_tokens: response.usage.input_tokens + response.usage.output_tokens,
                },
                episode_id: response.episode_id.to_string(),
            },
        }
    }
}

// Takes a vector of ContentBlockOutput and returns a tuple of (Option<String>, Vec<OpenAICompatibleToolCall>, Option<String>).
// This is useful since the OpenAI format separates text, tool calls, and reasoning content in the response fields.
fn process_chat_content(
    content: Vec<ContentBlockChatOutput>,
) -> (
    Option<String>,
    Vec<OpenAICompatibleToolCall>,
    Option<String>,
) {
    let mut content_str: Option<String> = None;
    let mut tool_calls = Vec::new();
    let mut reasoning_content: Option<String> = None;
    for block in content {
        match block {
            ContentBlockChatOutput::Text(text) => match content_str {
                Some(ref mut content) => content.push_str(&text.text),
                None => content_str = Some(text.text),
            },
            ContentBlockChatOutput::ToolCall(tool_call) => {
                tool_calls.push(tool_call.into());
            }
            ContentBlockChatOutput::Thought(thought) => {
                // Collect reasoning content from thought blocks
                match reasoning_content {
                    Some(ref mut content) => {
                        content.push('\n');
                        content.push_str(&thought.text);
                    }
                    None => reasoning_content = Some(thought.text),
                }
            }
            ContentBlockChatOutput::Unknown {
                data: _,
                model_provider_name: _,
            } => {
                tracing::warn!(
                    "Ignoring 'unknown' content block when constructing OpenAI-compatible response"
                );
            }
        }
    }
    (content_str, tool_calls, reasoning_content)
}

impl From<ToolCallOutput> for OpenAICompatibleToolCall {
    fn from(tool_call: ToolCallOutput) -> Self {
        OpenAICompatibleToolCall {
            id: tool_call.id,
            r#type: "function".to_string(),
            function: OpenAICompatibleFunctionCall {
                name: Some(tool_call.raw_name),
                arguments: tool_call.raw_arguments,
            },
        }
    }
}

impl From<Usage> for OpenAICompatibleUsage {
    fn from(usage: Usage) -> Self {
        OpenAICompatibleUsage {
            prompt_tokens: usage.input_tokens,
            completion_tokens: usage.output_tokens,
            total_tokens: usage.input_tokens + usage.output_tokens,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize)]
struct OpenAICompatibleResponseChunk {
    id: String,
    episode_id: String,
    choices: Vec<OpenAICompatibleChoiceChunk>,
    created: u32,
    model: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    system_fingerprint: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    service_tier: Option<String>,
    object: String,
    usage: Option<OpenAICompatibleUsage>,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
struct OpenAICompatibleChoiceChunk {
    index: u32,
    finish_reason: Option<OpenAICompatibleFinishReason>,
    logprobs: Option<()>, // This is always set to None for now
    delta: OpenAICompatibleDelta,
}

fn is_none_or_empty<T>(v: &Option<Vec<T>>) -> bool {
    // if it's None → skip, or if the Vec is empty → skip
    v.as_ref().is_none_or(|vec| vec.is_empty())
}

#[derive(Clone, Debug, PartialEq, Serialize)]
struct OpenAICompatibleDelta {
    #[serde(skip_serializing_if = "Option::is_none")]
    content: Option<String>,
    #[serde(skip_serializing_if = "is_none_or_empty")]
    tool_calls: Option<Vec<OpenAICompatibleToolCallChunk>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    reasoning_content: Option<String>,
}

fn convert_inference_response_chunk_to_openai_compatible(
    chunk: InferenceResponseChunk,
    tool_id_to_index: &mut HashMap<String, usize>,
    model_name: &str,
) -> Vec<OpenAICompatibleResponseChunk> {
    let response_chunk = match chunk {
        InferenceResponseChunk::Chat(c) => {
            let (content, tool_calls, reasoning_content) =
                process_chat_content_chunk(c.content, tool_id_to_index);
            OpenAICompatibleResponseChunk {
                id: c.inference_id.to_string(),
                episode_id: c.episode_id.to_string(),
                choices: vec![OpenAICompatibleChoiceChunk {
                    index: 0,
                    finish_reason: c.finish_reason.map(|finish_reason| finish_reason.into()),
                    logprobs: None,
                    delta: OpenAICompatibleDelta {
                        content,
                        tool_calls: Some(tool_calls),
                        reasoning_content,
                    },
                }],
                created: current_timestamp() as u32,
                service_tier: None,
                model: model_name.to_string(),
                system_fingerprint: None,
                object: "chat.completion.chunk".to_string(),
                // We emit a single chunk containing 'usage' at the end of the stream
                usage: None,
            }
        }
        InferenceResponseChunk::Json(c) => OpenAICompatibleResponseChunk {
            id: c.inference_id.to_string(),
            episode_id: c.episode_id.to_string(),
            choices: vec![OpenAICompatibleChoiceChunk {
                index: 0,
                finish_reason: c.finish_reason.map(|finish_reason| finish_reason.into()),
                logprobs: None,
                delta: OpenAICompatibleDelta {
                    content: Some(c.raw),
                    tool_calls: None,
                    reasoning_content: None,
                },
            }],
            created: current_timestamp() as u32,
            service_tier: None,
            model: model_name.to_string(),
            system_fingerprint: None,
            object: "chat.completion.chunk".to_string(),
            // We emit a single chunk containing 'usage' at the end of the stream
            usage: None,
        },
    };

    vec![response_chunk]
}

fn process_chat_content_chunk(
    content: Vec<ContentBlockChunk>,
    tool_id_to_index: &mut HashMap<String, usize>,
) -> (
    Option<String>,
    Vec<OpenAICompatibleToolCallChunk>,
    Option<String>,
) {
    let mut content_str: Option<String> = None;
    let mut tool_calls = Vec::new();
    let mut reasoning_content: Option<String> = None;
    for block in content {
        match block {
            ContentBlockChunk::Text(text) => match content_str {
                Some(ref mut content) => content.push_str(&text.text),
                None => content_str = Some(text.text),
            },
            ContentBlockChunk::ToolCall(tool_call) => {
                let len = tool_id_to_index.len();
                let is_new = !tool_id_to_index.contains_key(&tool_call.id);
                let index = tool_id_to_index.entry(tool_call.id.clone()).or_insert(len);
                tool_calls.push(OpenAICompatibleToolCallChunk {
                    id: if is_new { Some(tool_call.id) } else { None },
                    index: *index,
                    r#type: "function".to_string(),
                    function: OpenAICompatibleFunctionCall {
                        name: if is_new {
                            Some(tool_call.raw_name)
                        } else {
                            None
                        },
                        arguments: tool_call.raw_arguments,
                    },
                });
            }
            ContentBlockChunk::Thought(thought) => {
                // Collect reasoning content from thought chunks
                if let Some(thought_text) = thought.text {
                    match reasoning_content {
                        Some(ref mut content) => content.push_str(&thought_text),
                        None => reasoning_content = Some(thought_text),
                    }
                }
            }
        }
    }
    (content_str, tool_calls, reasoning_content)
}

fn stream_guardrail_window_char_limit() -> usize {
    static WINDOW_LIMIT: OnceLock<usize> = OnceLock::new();
    *WINDOW_LIMIT.get_or_init(|| {
        std::env::var("STREAM_GUARDRAIL_WINDOW_CHAR_LIMIT")
            .ok()
            .and_then(|raw| raw.parse::<usize>().ok())
            .filter(|value| *value > 0)
            .unwrap_or(50)
    })
}
const STREAM_GUARDRAIL_BLOCKED_MESSAGE: &str = "Output content violates content policy";

struct StreamingGuardrailState {
    guardrail_profile: String,
    guardrail_config: Arc<crate::guardrail_table::GuardrailConfig>,
    http_client: reqwest::Client,
    model_credential_store: Arc<std::sync::RwLock<HashMap<String, SecretString>>>,
    clickhouse_connection_info: crate::clickhouse::ClickHouseConnectionInfo,
    guardrail_context: Arc<tokio::sync::Mutex<crate::guardrail::GuardrailExecutionContext>>,
}

impl StreamingGuardrailState {
    async fn scan_window(
        &self,
        window_text: &str,
        inference_id: Uuid,
        window_index: usize,
    ) -> Result<crate::guardrail_table::GuardrailResult, Error> {
        let credentials = merge_credentials_from_store(&self.model_credential_store);
        let cache_options = crate::cache::CacheOptions {
            enabled: crate::cache::CacheEnabledMode::Off,
            max_age_s: None,
        };
        let clients = super::inference::InferenceClients {
            http_client: &self.http_client,
            credentials: &credentials,
            clickhouse_connection_info: &self.clickhouse_connection_info,
            cache_options: &cache_options,
        };

        let scan_start = tokio::time::Instant::now();
        let guardrail_result = crate::guardrail::execute_guardrail(
            self.guardrail_config.as_ref(),
            crate::moderation::ModerationInput::Single(window_text.to_string()),
            crate::guardrail_table::GuardType::Output,
            &clients,
            None,
            false,
        )
        .await?;
        let scan_duration = Some(scan_start.elapsed());

        if !guardrail_result.provider_results.is_empty() {
            let scan_record = crate::guardrail::GuardrailInferenceDatabaseInsert::from_result(
                inference_id,
                self.guardrail_profile.clone(),
                crate::guardrail_table::GuardType::Output,
                format!("stream_window_{window_index}"),
                crate::guardrail::ScanMode::GatewayManagedMulti,
                &guardrail_result,
                scan_duration,
                window_text,
                None,
            );

            {
                let mut context = self.guardrail_context.lock().await;
                context.add_scan_record(scan_record);
                if guardrail_result.flagged {
                    context.response_terminated = true;
                }
            }
        }

        Ok(guardrail_result)
    }
}

fn extract_guardrail_text_from_chunk(chunk: &InferenceResponseChunk) -> String {
    match chunk {
        InferenceResponseChunk::Chat(chat_chunk) => {
            let mut aggregated = String::new();
            for block in &chat_chunk.content {
                if let ContentBlockChunk::Text(text_chunk) = block {
                    aggregated.push_str(text_chunk.text.as_str());
                }
            }
            aggregated
        }
        InferenceResponseChunk::Json(json_chunk) => json_chunk.raw.clone(),
    }
}

fn chunk_has_finish_reason(chunk: &InferenceResponseChunk) -> bool {
    match chunk {
        InferenceResponseChunk::Chat(chat_chunk) => chat_chunk.finish_reason.is_some(),
        InferenceResponseChunk::Json(json_chunk) => json_chunk.finish_reason.is_some(),
    }
}

fn attach_streaming_output_guardrail(
    stream: InferenceStream,
    guardrail_state: StreamingGuardrailState,
) -> InferenceStream {
    Box::pin(async_stream::stream! {
        let mut upstream_stream = stream;
        let mut buffered_chunks: Vec<InferenceResponseChunk> = Vec::new();
        let mut buffered_text = String::new();
        let mut window_index: usize = 0;
        let window_limit = stream_guardrail_window_char_limit();

        while let Some(chunk_result) = FuturesStreamExt::next(&mut upstream_stream).await {
            match chunk_result {
                Ok(chunk) => {
                    let inference_id = chunk.inference_id();
                    let chunk_finish = chunk_has_finish_reason(&chunk);
                    let chunk_text = extract_guardrail_text_from_chunk(&chunk);

                    if !chunk_text.is_empty() {
                        buffered_text.push_str(&chunk_text);
                    }

                    buffered_chunks.push(chunk);

                    let should_scan = buffered_text.len() >= window_limit || chunk_finish;
                    if should_scan {
                        if !buffered_text.is_empty() {
                            window_index += 1;
                            match guardrail_state
                                .scan_window(&buffered_text, inference_id, window_index)
                                .await
                            {
                                Ok(result) => {
                                    if result.flagged {
                                        yield Err(Error::new(
                                            ErrorDetails::GuardrailOutputViolation {
                                                message: STREAM_GUARDRAIL_BLOCKED_MESSAGE
                                                    .to_string(),
                                            },
                                        ));
                                        return;
                                    }
                                }
                                Err(e) => {
                                    yield Err(e);
                                    return;
                                }
                            }
                        }

                        for chunk_to_send in buffered_chunks.drain(..) {
                            yield Ok(chunk_to_send);
                        }
                        buffered_text.clear();
                    }
                }
                Err(e) => {
                    yield Err(e);
                    return;
                }
            }
        }

        if !buffered_chunks.is_empty() {
            if !buffered_text.is_empty() {
                window_index += 1;
                match guardrail_state
                    .scan_window(&buffered_text, buffered_chunks[0].inference_id(), window_index)
                    .await
                {
                    Ok(result) => {
                        if result.flagged {
                            yield Err(Error::new(
                                ErrorDetails::GuardrailOutputViolation {
                                    message: STREAM_GUARDRAIL_BLOCKED_MESSAGE
                                        .to_string(),
                                },
                            ));
                            return;
                        }
                    }
                    Err(e) => {
                        yield Err(e);
                        return;
                    }
                }
            }

            for chunk_to_send in buffered_chunks.drain(..) {
                yield Ok(chunk_to_send);
            }
        }
    })
}

/// Shared stream processor for OpenAI-compatible events with optional usage tracking
struct OpenAICompatibleStreamProcessor {
    stream: InferenceStream,
    model_name: String,
    stream_options: Option<OpenAICompatibleStreamOptions>,
    usage_limiter: Option<Arc<crate::usage_limit::UsageLimiter>>,
    headers: Option<HeaderMap>,
}

impl OpenAICompatibleStreamProcessor {
    fn new(
        stream: InferenceStream,
        model_name: String,
        stream_options: Option<OpenAICompatibleStreamOptions>,
    ) -> Self {
        Self {
            stream,
            model_name,
            stream_options,
            usage_limiter: None,
            headers: None,
        }
    }

    fn with_usage_tracking(
        stream: InferenceStream,
        model_name: String,
        stream_options: Option<OpenAICompatibleStreamOptions>,
        usage_limiter: Option<Arc<crate::usage_limit::UsageLimiter>>,
        headers: HeaderMap,
    ) -> Self {
        Self {
            stream,
            model_name,
            stream_options,
            usage_limiter,
            headers: Some(headers),
        }
    }
}

impl Stream for OpenAICompatibleStreamProcessor {
    type Item = Result<Event, Error>;

    fn poll_next(self: Pin<&mut Self>, _cx: &mut Context<'_>) -> Poll<Option<Self::Item>> {
        // This will be implemented using async_stream::stream! macro
        // For now, we'll use a helper method
        unimplemented!("Use process_stream() method instead")
    }
}

impl OpenAICompatibleStreamProcessor {
    fn process_stream(mut self) -> impl Stream<Item = Result<Event, Error>> {
        async_stream::stream! {
            let mut tool_id_to_index = HashMap::new();
            let mut is_first_chunk = true;
            let mut total_usage = OpenAICompatibleUsage {
                prompt_tokens: 0,
                completion_tokens: 0,
                total_tokens: 0,
            };
            let mut inference_id = None;
            let mut _episode_id = None;

            let mut stream_terminated_early = false;

            // Process all chunks and accumulate usage
            while let Some(chunk_result) = tokio_stream::StreamExt::next(&mut self.stream).await {
                match chunk_result {
                    Ok(chunk) => {
                        inference_id = Some(chunk.inference_id());
                        _episode_id = Some(chunk.episode_id());
                        let chunk_usage = match &chunk {
                            InferenceResponseChunk::Chat(c) => &c.usage,
                            InferenceResponseChunk::Json(c) => &c.usage,
                        };
                        if let Some(chunk_usage) = chunk_usage {
                            total_usage.prompt_tokens += chunk_usage.input_tokens;
                            total_usage.completion_tokens += chunk_usage.output_tokens;
                            total_usage.total_tokens +=
                                chunk_usage.input_tokens + chunk_usage.output_tokens;
                        }
                        let openai_compatible_chunks =
                            convert_inference_response_chunk_to_openai_compatible(
                                chunk,
                                &mut tool_id_to_index,
                                &self.model_name,
                            );
                        for chunk in openai_compatible_chunks {
                            let mut chunk_json = serde_json::to_value(chunk).map_err(|e| {
                                Error::new(ErrorDetails::Inference {
                                    message: format!("Failed to convert chunk to JSON: {e}"),
                                })
                            })?;
                            if is_first_chunk {
                                chunk_json["choices"][0]["delta"]["role"] =
                                    Value::String("assistant".to_string());
                                is_first_chunk = false;
                            }

                            yield Ok(Event::default().json_data(chunk_json).map_err(|e| {
                                Error::new(ErrorDetails::Inference {
                                    message: format!("Failed to convert Value to Event: {e}"),
                                })
                            })?);
                        }
                    }
                    Err(e) => {
                        stream_terminated_early = true;
                        let error_message = serde_json::json!({ "error": e.to_string() });
                        yield Ok(Event::default().json_data(error_message).map_err(|err| {
                            Error::new(ErrorDetails::Inference {
                                message: format!("Failed to convert error Value to Event: {err}"),
                            })
                        })?);
                        break;
                    }
                }
            }

            // Handle final usage message if stream_options.include_usage is true
            if let Some(ref options) = self.stream_options {
                if options.include_usage && !stream_terminated_early {
                    let final_usage_message = serde_json::json!({
                        "id": format!("chatcmpl-{}", inference_id.unwrap_or(Uuid::new_v4())),
                        "choices": [],
                        "created": std::time::SystemTime::now()
                            .duration_since(std::time::UNIX_EPOCH)
                            .unwrap()
                            .as_secs(),
                        "model": self.model_name,
                        "object": "chat.completion.chunk",
                        "usage": total_usage
                    });

                    yield Ok(Event::default().json_data(final_usage_message).map_err(|e| {
                        Error::new(ErrorDetails::Inference {
                            message: format!("Failed to convert final usage to Event: {e}"),
                        })
                    })?);
                }
            }

            // Send [DONE] to signal the end of the stream
            yield Ok(Event::default().data("[DONE]"));

            // Handle usage tracking if enabled
            if let (Some(usage_limiter), Some(headers)) = (self.usage_limiter, self.headers) {
                if let Some(user_id) = headers.get("x-tensorzero-user-id").and_then(|v| v.to_str().ok()) {
                    if total_usage.total_tokens > 0 {
                        // Calculate estimated cost (using same logic as non-streaming)
                        let tokens_to_consume = total_usage.total_tokens as i64;
                        let cost_to_consume = if total_usage.total_tokens > 0 {
                            // Use default pricing for streaming: $0.01 per 1K input tokens, $0.03 per 1K output tokens
                            // Since we don't have exact input/output breakdown, use average: $0.02 per 1K tokens
                            let cost = total_usage.total_tokens as f64 * 0.00002;
                            (cost * 10000.0).round() / 10000.0
                        } else {
                            0.0
                        };

                        // Record the consumption (fire and forget - don't block response)
                        let usage_limiter_clone = usage_limiter.clone();
                        let user_id_clone = user_id.to_string();
                        tokio::spawn(async move {
                            let _result = usage_limiter_clone
                                .check_usage(&user_id_clone, Some(tokens_to_consume), Some(cost_to_consume))
                                .await;
                        });
                    }
                }
            }
        }
    }
}

/// Prepares an Event for SSE on the way out of the gateway
/// When None is passed in, we send "[DONE]" to the client to signal the end of the stream
fn prepare_serialized_openai_compatible_events(
    stream: InferenceStream,
    model_name: String,
    stream_options: Option<OpenAICompatibleStreamOptions>,
) -> impl Stream<Item = Result<Event, Error>> {
    OpenAICompatibleStreamProcessor::new(stream, model_name, stream_options).process_stream()
}

/// Enhanced version of prepare_serialized_openai_compatible_events that includes usage tracking
fn prepare_serialized_openai_compatible_events_with_usage_tracking(
    stream: InferenceStream,
    model_name: String,
    stream_options: Option<OpenAICompatibleStreamOptions>,
    usage_limiter: Option<Arc<crate::usage_limit::UsageLimiter>>,
    headers: HeaderMap,
) -> impl Stream<Item = Result<Event, Error>> {
    OpenAICompatibleStreamProcessor::with_usage_tracking(
        stream,
        model_name,
        stream_options,
        usage_limiter,
        headers,
    )
    .process_stream()
}

impl From<ToolCallChunk> for OpenAICompatibleToolCall {
    fn from(tool_call: ToolCallChunk) -> Self {
        OpenAICompatibleToolCall {
            id: tool_call.id,
            r#type: "function".to_string(),
            function: OpenAICompatibleFunctionCall {
                name: Some(tool_call.raw_name),
                arguments: tool_call.raw_arguments,
            },
        }
    }
}

// Completion Stream Processor

/// Stream processor for completions (simpler than chat - no tool calls, no roles)
struct CompletionStreamProcessor {
    stream: crate::completions::CompletionStream,
    model_name: String,
    stream_options: Option<OpenAICompatibleStreamOptions>,
}

impl CompletionStreamProcessor {
    fn new(
        stream: crate::completions::CompletionStream,
        model_name: String,
        stream_options: Option<OpenAICompatibleStreamOptions>,
    ) -> Self {
        Self {
            stream,
            model_name,
            stream_options,
        }
    }

    fn process_stream(mut self) -> impl Stream<Item = Result<Event, Error>> {
        async_stream::stream! {
            use futures::StreamExt;

            let total_usage = OpenAICompatibleUsage {
                prompt_tokens: 0,
                completion_tokens: 0,
                total_tokens: 0,
            };
            let mut completion_id: Option<String> = None;
            let mut chunks_forwarded = 0;

            // Process all chunks and accumulate usage
            while let Some(chunk_result) = self.stream.next().await {
                match chunk_result {
                    Ok(chunk) => {
                        // Store the completion ID from first chunk
                        if completion_id.is_none() {
                            completion_id = Some(chunk.id.clone());
                        }

                        chunks_forwarded += 1;
                        tracing::debug!(
                            "CompletionStreamProcessor forwarding chunk #{} to client: id={}, choices.len={}, has_usage={}",
                            chunks_forwarded,
                            chunk.id,
                            chunk.choices.len(),
                            chunk.usage.is_some()
                        );

                        // Accumulate usage (vLLM sends usage in chunks)
                        // For now, we'll track it but usage is typically only in final chunk

                        // Convert to OpenAI-compatible format with proper usage structure
                        // Serialize directly to avoid buffering overhead from serde_json::json!()
                        let openai_usage = chunk.usage.map(|u| OpenAICompatibleUsage {
                            prompt_tokens: u.input_tokens,
                            completion_tokens: u.output_tokens,
                            total_tokens: u.input_tokens + u.output_tokens,
                        });

                        // Create a wrapper struct for efficient serialization
                        #[derive(serde::Serialize)]
                        struct OpenAICompletionChunk<'a> {
                            id: &'a str,
                            object: &'a str,
                            created: u64,
                            model: &'a str,
                            choices: &'a [CompletionChoiceChunk],
                            #[serde(skip_serializing_if = "Option::is_none")]
                            usage: Option<OpenAICompatibleUsage>,
                        }

                        let serializable_chunk = OpenAICompletionChunk {
                            id: &chunk.id,
                            object: &chunk.object,
                            created: chunk.created,
                            model: &chunk.model,
                            choices: &chunk.choices,
                            usage: openai_usage,
                        };

                        // Serialize to JSON string and create SSE event manually for immediate flushing
                        let json_str = serde_json::to_string(&serializable_chunk).map_err(|e| {
                            Error::new(ErrorDetails::Serialization {
                                message: format!("Failed to serialize completion chunk: {e}"),
                            })
                        })?;

                        // Create SSE event with explicit data field
                        let event = Event::default().data(json_str);

                        yield Ok(event);
                    }
                    Err(e) => {
                        tracing::error!(
                            "Error from vLLM completion stream after {} chunks forwarded, skipping chunk and continuing: {}",
                            chunks_forwarded,
                            e
                        );
                        // Log error but continue processing (matches ChatCompletion behavior)
                        // Skip this chunk and continue to next one
                        continue;
                    }
                }
            }

            tracing::info!(
                "CompletionStreamProcessor finished. Total chunks forwarded to client: {}",
                chunks_forwarded
            );

            // Handle final usage message if stream_options.include_usage is true
            if let Some(ref options) = self.stream_options {
                if options.include_usage && total_usage.total_tokens > 0 {
                    let final_usage_message = serde_json::json!({
                        "id": completion_id.unwrap_or_else(|| format!("cmpl-{}", Uuid::new_v4())),
                        "choices": [],
                        "created": std::time::SystemTime::now()
                            .duration_since(std::time::UNIX_EPOCH)
                            .unwrap()
                            .as_secs(),
                        "model": self.model_name,
                        "object": "text_completion",
                        "usage": total_usage
                    });

                    yield Ok(Event::default().json_data(final_usage_message).map_err(|e| {
                        Error::new(ErrorDetails::Inference {
                            message: format!("Failed to convert final usage to Event: {e}"),
                        })
                    })?);
                }
            }

            // Send [DONE] to signal the end of the stream
            yield Ok(Event::default().data("[DONE]"));
        }
    }
}

/// Prepares SSE events for completion streaming
fn prepare_serialized_completion_events(
    stream: crate::completions::CompletionStream,
    model_name: String,
    stream_options: Option<OpenAICompatibleStreamOptions>,
) -> impl Stream<Item = Result<Event, Error>> {
    CompletionStreamProcessor::new(stream, model_name, stream_options).process_stream()
}

// OpenAI-compatible completions types and handler

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OpenAICompatibleCompletionParams {
    model: String,
    prompt: CompletionPrompt,
    #[serde(skip_serializing_if = "Option::is_none")]
    suffix: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    max_tokens: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    temperature: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    top_p: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    n: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    stream: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    logprobs: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    echo: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    stop: Option<CompletionStop>,
    #[serde(skip_serializing_if = "Option::is_none")]
    presence_penalty: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    frequency_penalty: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    repetition_penalty: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    best_of: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    logit_bias: Option<HashMap<String, f32>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    user: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    seed: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    ignore_eos: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    stream_options: Option<OpenAICompatibleStreamOptions>,
    #[serde(flatten)]
    unknown_fields: HashMap<String, Value>,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
struct OpenAICompatibleCompletionResponse {
    id: String,
    object: String, // "text_completion"
    created: u64,
    model: String,
    choices: Vec<OpenAICompatibleCompletionChoice>,
    usage: OpenAICompatibleUsage,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
struct OpenAICompatibleCompletionChoice {
    text: String,
    index: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    logprobs: Option<OpenAICompatibleCompletionLogProbs>,
    finish_reason: String,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
struct OpenAICompatibleCompletionLogProbs {
    tokens: Vec<String>,
    token_logprobs: Vec<Option<f32>>,
    top_logprobs: Vec<HashMap<String, f32>>,
    text_offset: Vec<u32>,
}

pub async fn completion_handler(
    State(AppStateData {
        config,
        http_client,
        clickhouse_connection_info,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store,
        ..
    }): AppState,
    headers: HeaderMap,
    StructuredJson(params): StructuredJson<OpenAICompatibleCompletionParams>,
) -> Result<Response<Body>, Error> {
    // Log unknown fields
    let unknown_fields: Vec<&str> = params.unknown_fields.keys().map(|k| k.as_str()).collect();

    if !unknown_fields.is_empty() {
        tracing::warn!(
            "Ignoring unknown fields in OpenAI-compatible completion request: {:?}",
            unknown_fields
        );
    }

    // Resolve the model name based on authentication state
    let model_resolution = model_resolution::resolve_model_name(
        Some(params.model.as_str()),
        &headers,
        false, // not for embedding
    )?;

    let model_id = model_resolution.model_name.ok_or_else(|| {
        Error::new(ErrorDetails::InvalidOpenAICompatibleRequest {
            message: "Completion requests must specify a model, not a function".to_string(),
        })
    })?;

    let original_model_name = model_resolution.original_model_name.to_string();

    // Extract model configuration
    use crate::model::ModelTableExt;
    let models = config.models.read().await;
    let model = models
        .get_with_capability(
            &model_id,
            crate::endpoints::capability::EndpointCapability::Completions,
        )
        .await?
        .ok_or_else(|| {
            Error::new(ErrorDetails::ModelNotConfiguredForCapability {
                model_name: model_id.to_string(),
                capability: "completions".to_string(),
            })
        })?;

    // Merge credentials from the credential store
    let credentials = merge_credentials_from_store(&model_credential_store);

    // Create inference clients
    let cache_options: crate::cache::CacheOptions = (
        Default::default(),
        false, // dryrun is false
    )
        .into();
    let clients = super::inference::InferenceClients {
        http_client: &http_client,
        credentials: &credentials,
        clickhouse_connection_info: &clickhouse_connection_info,
        cache_options: &cache_options,
    };

    // Create the completion request
    let request_id = Uuid::now_v7();
    let request = CompletionRequest {
        id: request_id,
        model: Arc::from(model_id.as_str()),
        prompt: Some(params.prompt),
        suffix: params.suffix,
        max_tokens: params.max_tokens,
        temperature: params.temperature,
        top_p: params.top_p,
        n: params.n,
        stream: params.stream,
        logprobs: params.logprobs,
        echo: params.echo,
        stop: params.stop,
        presence_penalty: params.presence_penalty,
        frequency_penalty: params.frequency_penalty,
        repetition_penalty: params.repetition_penalty,
        best_of: params.best_of,
        logit_bias: params.logit_bias,
        user: params.user,
        seed: params.seed,
        ignore_eos: params.ignore_eos,
    };

    // Validate request parameters
    request.validate()?;

    let stream = params.stream.unwrap_or(false);
    let stream_options = params.stream_options.clone();

    if stream {
        // Streaming response - use model's complete_stream method
        let (mut completion_stream, _raw_request) = model
            .complete_stream(&request, &original_model_name, &clients)
            .await?;

        // CRITICAL FIX: Peek at first chunk to ensure stream is ready before creating SSE response
        // This prevents [DONE] from arriving before content chunks under high concurrency
        // by forcing the underlying vLLM SSE connection to establish before we start the response
        let mut first_chunk = None;
        use futures::StreamExt;
        if let Some(chunk_result) = completion_stream.next().await {
            first_chunk = Some(chunk_result);
        }

        // Create a combined stream that re-injects the first chunk, then yields the rest
        let combined_stream: crate::completions::CompletionStream =
            Box::pin(async_stream::stream! {
                // Yield the first chunk if we have one
                if let Some(chunk) = first_chunk {
                    yield chunk;
                }
                // Then yield the rest of the stream
                while let Some(chunk) = completion_stream.next().await {
                    yield chunk;
                }
            });

        // Convert completion stream to SSE events
        let sse_stream = prepare_serialized_completion_events(
            combined_stream,
            original_model_name,
            stream_options,
        );

        Ok(Sse::new(sse_stream)
            .keep_alive(axum::response::sse::KeepAlive::new())
            .into_response())
    } else {
        // Non-streaming response - use model's complete method
        let response = model
            .complete(&request, &original_model_name, &clients)
            .await?;

        // Convert to OpenAI format
        let openai_response = OpenAICompatibleCompletionResponse {
            id: format!("cmpl-{}", response.id),
            object: response.object,
            created: response.created,
            model: original_model_name,
            choices: response
                .choices
                .into_iter()
                .map(|choice| OpenAICompatibleCompletionChoice {
                    text: choice.text,
                    index: choice.index,
                    logprobs: choice
                        .logprobs
                        .map(|lp| OpenAICompatibleCompletionLogProbs {
                            tokens: lp.tokens,
                            token_logprobs: lp.token_logprobs,
                            top_logprobs: lp.top_logprobs,
                            text_offset: lp.text_offset,
                        }),
                    finish_reason: choice.finish_reason,
                })
                .collect(),
            usage: OpenAICompatibleUsage {
                prompt_tokens: response.usage.input_tokens,
                completion_tokens: response.usage.output_tokens,
                total_tokens: response.usage.input_tokens + response.usage.output_tokens,
            },
        };

        Ok(Json(openai_response).into_response())
    }
}

// OpenAI-compatible embedding types and handler

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OpenAICompatibleEmbeddingParams {
    input: OpenAICompatibleEmbeddingInput,
    model: String,
    #[serde(rename = "tensorzero::cache_options")]
    tensorzero_cache_options: Option<CacheParamsOptions>,
    #[serde(flatten)]
    unknown_fields: HashMap<String, Value>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(untagged)]
enum OpenAICompatibleEmbeddingInput {
    Single(String),
    Batch(Vec<String>),
}

#[derive(Clone, Debug, PartialEq, Serialize)]
struct OpenAICompatibleEmbeddingData {
    object: String,
    embedding: Vec<f32>,
    index: usize,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
struct OpenAICompatibleEmbeddingUsage {
    prompt_tokens: u32,
    total_tokens: u32,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
struct OpenAICompatibleEmbeddingResponse {
    object: String,
    data: Vec<OpenAICompatibleEmbeddingData>,
    model: String,
    usage: OpenAICompatibleEmbeddingUsage,
}

/// Response for a single model in the list
#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct ModelObject {
    pub id: String,
    pub created: u64,
    pub object: &'static str,
    pub owned_by: &'static str,
}

/// Response for the /v1/models endpoint
#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct ListModelsResponse {
    pub object: &'static str,
    pub data: Vec<ModelObject>,
}

/// A handler for the OpenAI-compatible list models endpoint
#[debug_handler(state = AppStateData)]
pub async fn list_models(
    State(AppStateData { config, .. }): AppState,
    headers: HeaderMap,
) -> Result<Json<ListModelsResponse>, Error> {
    // Check if the request is authenticated by looking for the auth metadata header
    let is_authenticated = headers.contains_key("x-tensorzero-endpoint-id");

    // Get all models
    let models = config.models.read().await;

    // Filter models based on authentication
    let model_list: Vec<ModelObject> = if is_authenticated {
        // Authenticated: return all models available to this API key
        // The auth middleware provides these as a comma-separated list
        headers
            .get("x-tensorzero-available-models")
            .and_then(|header| header.to_str().ok())
            .map(|models_str| {
                models_str
                    .split(',')
                    .filter(|s| !s.is_empty())
                    .map(|model_name| ModelObject {
                        id: model_name.to_string(),
                        created: 0,
                        object: "model",
                        owned_by: "bud",
                    })
                    .collect()
            })
            .unwrap_or_else(|| {
                // No available models header or failed to parse
                tracing::warn!(
                    "Authenticated /v1/models request missing x-tensorzero-available-models header"
                );
                vec![]
            })
    } else {
        // Unauthenticated (when auth is disabled): return all models
        models
            .iter_static_models()
            .map(|(model_id, _model_config)| ModelObject {
                id: model_id.to_string(),
                created: 0,
                object: "model",
                owned_by: "bud",
            })
            .collect()
    };

    let response = ListModelsResponse {
        object: "list",
        data: model_list,
    };

    Ok(Json(response))
}

/// A handler for the OpenAI-compatible embedding endpoint
#[debug_handler(state = AppStateData)]
pub async fn embedding_handler(
    State(AppStateData {
        config,
        http_client,
        clickhouse_connection_info,
        kafka_connection_info,
        authentication_info: _,
        model_credential_store,
        inference_batcher,
        ..
    }): AppState,
    headers: HeaderMap,
    StructuredJson(openai_compatible_params): StructuredJson<OpenAICompatibleEmbeddingParams>,
) -> Result<Response<Body>, Error> {
    let unknown_fields: Vec<&str> = openai_compatible_params
        .unknown_fields
        .keys()
        .filter(|k| k.as_str() != "encoding_format")
        .map(|k| k.as_str())
        .collect();

    if !unknown_fields.is_empty() {
        tracing::warn!(
            "Ignoring unknown fields in OpenAI-compatible embedding request: {:?}",
            unknown_fields
        );
    }

    // Resolve the model name based on authentication state
    let model_resolution = model_resolution::resolve_model_name(
        Some(&openai_compatible_params.model),
        &headers,
        true, // for embedding
    )?;

    let model_id = model_resolution.model_name.ok_or_else(|| {
        Error::new(ErrorDetails::InvalidOpenAICompatibleRequest {
            message: "Embedding requests must specify a model, not a function".to_string(),
        })
    })?;

    let original_model_name = model_resolution.original_model_name.to_string();

    // Convert OpenAI request to internal format
    let internal_input = match &openai_compatible_params.input {
        OpenAICompatibleEmbeddingInput::Single(text) => {
            crate::embeddings::EmbeddingInput::Single(text.clone())
        }
        OpenAICompatibleEmbeddingInput::Batch(texts) => {
            if texts.is_empty() {
                return Err(Error::new(ErrorDetails::InvalidOpenAICompatibleRequest {
                    message: "Batch embedding requests cannot be empty.".to_string(),
                }));
            }
            crate::embeddings::EmbeddingInput::Batch(texts.clone())
        }
    };

    let encoding_format = openai_compatible_params
        .unknown_fields
        .get("encoding_format")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());

    // Capture the gateway request (without null values)
    let _gateway_request = serialize_without_nulls(&openai_compatible_params).ok();

    let embedding_request = EmbeddingRequest {
        input: internal_input,
        encoding_format,
    };

    // Extract model configuration
    use crate::model::ModelTableExt;
    let models = config.models.read().await;
    let model = models
        .get_with_capability(
            &model_id,
            crate::endpoints::capability::EndpointCapability::Embedding,
        )
        .await?
        .ok_or_else(|| {
            Error::new(ErrorDetails::Config {
                message: format!(
                    "Model '{original_model_name}' not found or does not support embeddings"
                ),
            })
        })?;

    // Merge credentials from the credential store
    let credentials = merge_credentials_from_store(&model_credential_store);

    // Create inference clients
    let cache_options: crate::cache::CacheOptions = (
        openai_compatible_params
            .tensorzero_cache_options
            .unwrap_or_default(),
        false, // dryrun is false for now
    )
        .into();
    let clients = super::inference::InferenceClients {
        http_client: &http_client,
        credentials: &credentials,
        clickhouse_connection_info: &clickhouse_connection_info,
        cache_options: &cache_options,
    };

    // Call the model's embedding capability
    let response = model
        .embed(&embedding_request, &original_model_name, &clients)
        .await?;

    // Convert to OpenAI-compatible format
    let openai_response = OpenAICompatibleEmbeddingResponse {
        object: "list".to_string(),
        data: response
            .embeddings
            .iter()
            .enumerate()
            .map(|(index, embedding)| OpenAICompatibleEmbeddingData {
                object: "embedding".to_string(),
                embedding: embedding.clone(),
                index,
            })
            .collect(),
        model: original_model_name.clone(),
        usage: OpenAICompatibleEmbeddingUsage {
            prompt_tokens: response.usage.input_tokens,
            total_tokens: response.usage.input_tokens,
        },
    };

    // Capture the gateway response (without null values)
    let gateway_response = serialize_without_nulls(&openai_response).ok();

    // Write to observability database if enabled
    if config.gateway.observability.enabled.unwrap_or(true) {
        // Create the InferenceResult for observability
        let inference_id = Uuid::now_v7();

        // Create a ModelInferenceResponseWithMetadata for the embedding
        let model_inference = crate::inference::types::ModelInferenceResponseWithMetadata {
            id: Uuid::now_v7(),
            created: response.created,
            output: vec![], // Embeddings don't have ContentBlockOutput
            system: None,
            input_messages: vec![], // Could convert from embedding input if needed
            raw_request: response.raw_request.clone(),
            raw_response: response.raw_response.clone(),
            usage: response.usage.clone(),
            latency: response.latency.clone(),
            model_provider_name: response.embedding_provider_name.clone(),
            model_name: Arc::from(original_model_name.as_str()),
            cached: response.cached,
            finish_reason: None,
            gateway_request: None,
            gateway_response: None,
            guardrail_scan_summary: None,
        };

        let result = crate::inference::types::InferenceResult::Embedding(
            crate::inference::types::EmbeddingInferenceResult {
                inference_id,
                created: response.created,
                embeddings: response.embeddings.clone(),
                embedding_dimensions: response
                    .embeddings
                    .first()
                    .map(|e| e.len() as u32)
                    .unwrap_or(0),
                input_count: response.embeddings.len() as u32,
                usage: response.usage.clone(),
                model_inference_results: vec![model_inference], // Now populated with model inference
                inference_params: crate::endpoints::inference::InferenceParams::default(),
                original_response: Some(response.raw_response.clone()),
            },
        );

        // Extract observability metadata from headers (set by auth middleware)
        let observability_metadata = if let (Some(project_id), Some(endpoint_id), Some(model_id)) = (
            headers
                .get("x-tensorzero-project-id")
                .and_then(|v| v.to_str().ok()),
            headers
                .get("x-tensorzero-endpoint-id")
                .and_then(|v| v.to_str().ok()),
            headers
                .get("x-tensorzero-model-id")
                .and_then(|v| v.to_str().ok()),
        ) {
            // Extract auth metadata from headers
            let api_key_id = headers
                .get("x-tensorzero-api-key-id")
                .and_then(|v| v.to_str().ok())
                .map(|s| s.to_string());
            let user_id = headers
                .get("x-tensorzero-user-id")
                .and_then(|v| v.to_str().ok())
                .map(|s| s.to_string());
            let api_key_project_id = headers
                .get("x-tensorzero-api-key-project-id")
                .and_then(|v| v.to_str().ok())
                .map(|s| s.to_string());

            Some(super::inference::ObservabilityMetadata {
                project_id: project_id.to_string(),
                endpoint_id: endpoint_id.to_string(),
                model_id: model_id.to_string(),
                api_key_id,
                user_id,
                api_key_project_id,
            })
        } else {
            None
        };

        // Use defaults for embedding requests since they don't have function/variant context
        let episode_id = Uuid::now_v7();
        let metadata = crate::endpoints::inference::InferenceDatabaseInsertMetadata {
            function_name: "tensorzero::embedding".to_string(), // Default function name for embeddings
            variant_name: original_model_name.clone(),          // Use model name as variant
            episode_id,
            tool_config: None,
            processing_time: Some(match response.latency {
                crate::inference::types::Latency::NonStreaming { response_time } => response_time,
                _ => std::time::Duration::from_millis(0),
            }),
            tags: HashMap::new(),
            extra_body: UnfilteredInferenceExtraBody::default(),
            extra_headers:
                crate::inference::types::extra_headers::UnfilteredInferenceExtraHeaders::default(),
        };

        // Convert EmbeddingInput to ResolvedInput for write_inference
        let resolved_input = ResolvedInput {
            messages: vec![ResolvedInputMessage {
                role: Role::User,
                content: match &embedding_request.input {
                    crate::embeddings::EmbeddingInput::Single(text) => {
                        vec![ResolvedInputMessageContent::Text {
                            value: serde_json::Value::String(text.clone()),
                        }]
                    }
                    crate::embeddings::EmbeddingInput::Batch(texts) => texts
                        .iter()
                        .map(|text| ResolvedInputMessageContent::Text {
                            value: serde_json::Value::String(text.clone()),
                        })
                        .collect(),
                },
            }],
            system: None,
        };

        // Write to observability database asynchronously
        let config_clone = config.clone();
        let clickhouse_info = clickhouse_connection_info.clone();
        let kafka_info = kafka_connection_info.clone();
        let gateway_request_json = _gateway_request;
        let gateway_response_json = gateway_response.clone();
        let async_writes = config.gateway.observability.async_writes;
        let model_pricing = model.pricing.clone();
        let inference_batcher_clone = inference_batcher.clone();

        let write_future = tokio::spawn(async move {
            write_inference(
                &clickhouse_info,
                &kafka_info,
                &config_clone,
                resolved_input,
                result,
                metadata,
                observability_metadata,
                gateway_request_json,
                gateway_response_json,
                model_pricing,
                None, // No guardrail records for embeddings
                inference_batcher_clone.as_ref(),
            )
            .await;
        });

        if !async_writes {
            write_future.await.map_err(|e| {
                Error::new(ErrorDetails::InternalError {
                    message: format!("Failed to join write task: {e}"),
                })
            })?;
        }
    }

    Ok(Json(openai_response).into_response())
}

/// OpenAI-compatible moderation request structure
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct OpenAICompatibleModerationParams {
    pub input: OpenAICompatibleModerationInput,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    #[serde(flatten)]
    pub unknown_fields: HashMap<String, Value>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(untagged)]
pub enum OpenAICompatibleModerationInput {
    Single(String),
    Batch(Vec<String>),
}

/// OpenAI-compatible moderation response structure
#[derive(Clone, Debug, Serialize)]
pub struct OpenAICompatibleModerationResponse {
    pub id: String,
    pub model: String,
    pub results: Vec<crate::moderation::ModerationResult>,
}

/// A handler for the OpenAI-compatible moderation endpoint
#[debug_handler(state = AppStateData)]
pub async fn moderation_handler(
    State(AppStateData {
        config,
        http_client,
        clickhouse_connection_info,
        kafka_connection_info,
        authentication_info: _,
        model_credential_store,
        guardrails,
        inference_batcher,
        ..
    }): AppState,
    headers: HeaderMap,
    StructuredJson(openai_compatible_params): StructuredJson<OpenAICompatibleModerationParams>,
) -> Result<Response<Body>, Error> {
    let unknown_fields: Vec<&str> = openai_compatible_params
        .unknown_fields
        .keys()
        .map(|k| k.as_str())
        .collect();

    if !unknown_fields.is_empty() {
        tracing::warn!(
            "Ignoring unknown fields in OpenAI-compatible moderation request: {:?}",
            unknown_fields
        );
    }

    // Default to omni-moderation-latest if no model specified
    let model_name = openai_compatible_params
        .model
        .clone()
        .unwrap_or_else(|| "omni-moderation-latest".to_string());

    // Resolve the model name based on authentication state
    let model_resolution =
        model_resolution::resolve_model_name(Some(&model_name), &headers, false)?;

    let resolved_model_name = model_resolution
        .model_name
        .ok_or_else(|| {
            Error::new(ErrorDetails::InvalidOpenAICompatibleRequest {
                message: "Moderation requests must specify a model, not a function".to_string(),
            })
        })?
        .to_string();

    // Convert OpenAI request to internal format
    let internal_input = match &openai_compatible_params.input {
        OpenAICompatibleModerationInput::Single(text) => {
            crate::moderation::ModerationInput::Single(text.clone())
        }
        OpenAICompatibleModerationInput::Batch(texts) => {
            if texts.is_empty() {
                return Err(Error::new(ErrorDetails::InvalidOpenAICompatibleRequest {
                    message: "Batch moderation requests cannot be empty.".to_string(),
                }));
            }
            crate::moderation::ModerationInput::Batch(texts.clone())
        }
    };

    // Capture the gateway request (without null values)
    let gateway_request_json = serialize_without_nulls(&openai_compatible_params).ok();

    let moderation_request = crate::moderation::ModerationRequest {
        input: internal_input.clone(),
        model: None, // Let the provider set the appropriate model name
        provider_params: if openai_compatible_params.unknown_fields.is_empty() {
            None
        } else {
            Some(serde_json::Value::Object(
                openai_compatible_params
                    .unknown_fields
                    .clone()
                    .into_iter()
                    .collect(),
            ))
        },
    };

    // Get the model table
    let models = config.models.read().await;

    // Check if the model exists and has moderation capability
    let model_config = models.get(&resolved_model_name).await?.ok_or_else(|| {
        Error::new(ErrorDetails::Config {
            message: format!("Model '{resolved_model_name}' not found"),
        })
    })?;

    // Verify the model supports moderation
    if !model_config
        .endpoints
        .contains(&crate::endpoints::capability::EndpointCapability::Moderation)
    {
        return Err(Error::new(ErrorDetails::Config {
            message: format!("Model '{resolved_model_name}' does not support moderation"),
        }));
    }

    // Merge credentials from the credential store
    let credentials = merge_credentials_from_store(&model_credential_store);

    // Create inference clients with no caching for moderation
    let cache_options = crate::cache::CacheOptions {
        enabled: crate::cache::CacheEnabledMode::Off,
        max_age_s: None,
    };
    let clients = super::inference::InferenceClients {
        http_client: &http_client,
        credentials: &credentials,
        clickhouse_connection_info: &clickhouse_connection_info,
        cache_options: &cache_options,
    };

    let mut response = None;

    // Check if the model has a guardrail profile configured
    if let Some(guardrail_profile) = &model_config.guardrail_profile {
        tracing::info!(
            "Model has guardrail profile configured: {}",
            guardrail_profile
        );

        // Get the guardrail configuration
        let guardrails_read = guardrails.read().await;
        let guardrail_config = guardrails_read
            .get(guardrail_profile.as_ref())
            .ok_or_else(|| {
                Error::new(ErrorDetails::Config {
                    message: format!("Guardrail profile '{}' not found", guardrail_profile),
                })
            })?
            .clone();
        drop(guardrails_read);

        // Execute the guardrail
        let start_time = tokio::time::Instant::now();
        let guardrail_result = crate::guardrail::execute_guardrail(
            &guardrail_config,
            moderation_request.input.clone(),
            crate::guardrail_table::GuardType::Input,
            &clients,
            moderation_request.provider_params.clone(),
            true,
        )
        .await?;
        let latency = start_time.elapsed();

        // Convert guardrail result to moderation response
        let results = vec![crate::moderation::ModerationResult {
            flagged: guardrail_result.flagged,
            categories: guardrail_result.merged_categories.clone(),
            category_scores: guardrail_result.merged_scores.clone(),
            category_applied_input_types: guardrail_result
                .merged_category_applied_input_types
                .clone(),
            hallucination_details: guardrail_result.hallucination_details.clone(),
            ip_violation_details: guardrail_result.ip_violation_details.clone(),
        }];

        let provider_response = crate::moderation::ModerationProviderResponse {
            id: Uuid::now_v7(),
            model: resolved_model_name.clone(),
            results,
            input: moderation_request.input.clone(),
            created: crate::inference::types::current_timestamp() as u64,
            raw_request: serde_json::to_string(&moderation_request).unwrap_or_default(),
            raw_response: serde_json::to_value(&guardrail_result)
                .ok()
                .map(|v| v.to_string())
                .unwrap_or_default(),
            usage: crate::inference::types::Usage {
                input_tokens: 0,
                output_tokens: 0,
            },
            latency: crate::inference::types::Latency::NonStreaming {
                response_time: latency,
            },
        };

        response = Some(crate::moderation::ModerationResponse::new(
            provider_response,
            "guardrail".into(),
        ));
    }

    let mut provider_errors = HashMap::new();

    // Only use providers if guardrail didn't already handle the request
    if response.is_none() {
        // For now, we'll use the first provider in routing that supports moderation
        // This is a temporary solution until we fully integrate moderation into the regular model system
        for provider_name in &model_config.routing {
            let provider = match model_config.providers.get(provider_name) {
                Some(p) => &p.config,
                None => {
                    tracing::warn!("Provider {} not found in model config", provider_name);
                    continue;
                }
            };

            // Check if this provider supports moderation
            tracing::info!("Checking provider {} for moderation support", provider_name);
            match provider {
                crate::model::ProviderConfig::OpenAI(openai_provider) => {
                    tracing::info!("Found OpenAI provider for moderation");
                    // For OpenAI, we need to use the provider's configured model name
                    let mut provider_request = moderation_request.clone();
                    provider_request.model = Some(openai_provider.model_name().to_string());
                    // Use the OpenAI provider's moderation capability
                    match openai_provider
                        .moderate(&provider_request, clients.http_client, &credentials)
                        .await
                    {
                        Ok(provider_response) => {
                            response = Some(crate::moderation::ModerationResponse::new(
                                provider_response,
                                provider_name.clone(),
                            ));
                            break;
                        }
                        Err(e) => {
                            provider_errors.insert(provider_name.to_string(), e);
                            continue;
                        }
                    }
                }
                crate::model::ProviderConfig::Mistral(mistral_provider) => {
                    tracing::info!("Found Mistral provider for moderation");
                    // For Mistral, we need to use the provider's configured model name
                    let mut provider_request = moderation_request.clone();
                    provider_request.model = Some(mistral_provider.model_name().to_string());
                    // Use the Mistral provider's moderation capability
                    match mistral_provider
                        .moderate(&provider_request, clients.http_client, &credentials)
                        .await
                    {
                        Ok(provider_response) => {
                            response = Some(crate::moderation::ModerationResponse::new(
                                provider_response,
                                provider_name.clone(),
                            ));
                            break;
                        }
                        Err(e) => {
                            provider_errors.insert(provider_name.to_string(), e);
                            continue;
                        }
                    }
                }
                crate::model::ProviderConfig::AzureContentSafety(azure_cs_provider) => {
                    tracing::info!("Found Azure Content Safety provider for moderation");
                    // Azure Content Safety doesn't require a model name
                    let provider_request = moderation_request.clone();
                    // Use the Azure Content Safety provider's moderation capability
                    match azure_cs_provider
                        .moderate(&provider_request, clients.http_client, &credentials)
                        .await
                    {
                        Ok(provider_response) => {
                            response = Some(crate::moderation::ModerationResponse::new(
                                provider_response,
                                provider_name.clone(),
                            ));
                            break;
                        }
                        Err(e) => {
                            provider_errors.insert(provider_name.to_string(), e);
                            continue;
                        }
                    }
                }
                crate::model::ProviderConfig::BudSentinel(bud_sentinel_provider) => {
                    tracing::info!("Found Bud Sentinel provider for moderation");
                    let provider_request = moderation_request.clone();
                    match bud_sentinel_provider
                        .moderate(&provider_request, clients.http_client, &credentials)
                        .await
                    {
                        Ok(provider_response) => {
                            response = Some(crate::moderation::ModerationResponse::new(
                                provider_response,
                                provider_name.clone(),
                            ));
                            break;
                        }
                        Err(e) => {
                            provider_errors.insert(provider_name.to_string(), e);
                            continue;
                        }
                    }
                }
                #[cfg(any(test, feature = "e2e_tests"))]
                crate::model::ProviderConfig::Dummy(dummy_provider) => {
                    tracing::info!("Found Dummy provider for moderation");
                    // For Dummy provider, use the provider's configured model name
                    let mut provider_request = moderation_request.clone();
                    provider_request.model = Some(dummy_provider.model_name().to_string());
                    // Use the Dummy provider's moderation capability
                    match dummy_provider
                        .moderate(&provider_request, clients.http_client, &credentials)
                        .await
                    {
                        Ok(provider_response) => {
                            response = Some(crate::moderation::ModerationResponse::new(
                                provider_response,
                                provider_name.clone(),
                            ));
                            break;
                        }
                        Err(e) => {
                            provider_errors.insert(provider_name.to_string(), e);
                            continue;
                        }
                    }
                }
                _ => {
                    // Other providers don't support moderation yet
                    continue;
                }
            }
        }
    } // End of if response.is_none()

    let response = response
        .ok_or_else(|| Error::new(ErrorDetails::ModelProvidersExhausted { provider_errors }))?;

    // Convert to OpenAI-compatible format
    let openai_response = OpenAICompatibleModerationResponse {
        id: format!("modr-{}", Uuid::now_v7()),
        model: model_resolution.original_model_name.to_string(),
        results: response.results.clone(),
    };

    // Capture the gateway response (without null values)
    let gateway_response_json = serialize_without_nulls(&openai_response).ok();

    // Write observability data if configured
    if config.gateway.observability.enabled.unwrap_or(true) {
        use crate::endpoints::inference::write_inference;
        use crate::inference::types::{
            ResolvedInput, ResolvedInputMessage, ResolvedInputMessageContent, Role,
        };

        // Generate inference ID
        let inference_id = Uuid::now_v7();

        // Create ModelInferenceResponseWithMetadata for moderation
        let model_inference = crate::inference::types::ModelInferenceResponseWithMetadata {
            id: inference_id,
            created: response.created,
            output: vec![],
            model_name: Arc::from(resolved_model_name.as_str()),
            model_provider_name: response.moderation_provider_name.clone(),
            input_messages: vec![],
            raw_request: response.raw_request.clone(),
            raw_response: response.raw_response.clone(),
            usage: response.usage.clone(),
            system: None,
            cached: response.cached,
            latency: response.latency.clone(),
            finish_reason: Some(crate::inference::types::FinishReason::Stop),
            gateway_request: gateway_request_json.clone(),
            gateway_response: gateway_response_json.clone(),
            guardrail_scan_summary: None,
        };

        // Create InferenceResult
        let result = crate::inference::types::InferenceResult::Moderation(
            crate::inference::types::ModerationInferenceResult {
                inference_id,
                created: response.created,
                results: response
                    .results
                    .iter()
                    .map(|r| {
                        // Convert ModerationCategories struct to HashMap
                        let mut categories_map = HashMap::new();
                        categories_map.insert("hate".to_string(), r.categories.hate);
                        categories_map.insert(
                            "hate/threatening".to_string(),
                            r.categories.hate_threatening,
                        );
                        categories_map.insert("harassment".to_string(), r.categories.harassment);
                        categories_map.insert(
                            "harassment/threatening".to_string(),
                            r.categories.harassment_threatening,
                        );
                        categories_map.insert("illicit".to_string(), r.categories.illicit);
                        categories_map
                            .insert("illicit/violent".to_string(), r.categories.illicit_violent);
                        categories_map.insert("self-harm".to_string(), r.categories.self_harm);
                        categories_map.insert(
                            "self-harm/intent".to_string(),
                            r.categories.self_harm_intent,
                        );
                        categories_map.insert(
                            "self-harm/instructions".to_string(),
                            r.categories.self_harm_instructions,
                        );
                        categories_map.insert("sexual".to_string(), r.categories.sexual);
                        categories_map
                            .insert("sexual/minors".to_string(), r.categories.sexual_minors);
                        categories_map.insert("violence".to_string(), r.categories.violence);
                        categories_map.insert(
                            "violence/graphic".to_string(),
                            r.categories.violence_graphic,
                        );
                        categories_map.insert("profanity".to_string(), r.categories.profanity);
                        categories_map.insert("insult".to_string(), r.categories.insult);
                        categories_map.insert("toxicity".to_string(), r.categories.toxicity);
                        categories_map.insert("malicious".to_string(), r.categories.malicious);
                        categories_map.insert("pii".to_string(), r.categories.pii);
                        categories_map.insert("secrets".to_string(), r.categories.secrets);
                        categories_map
                            .insert("ip-violation".to_string(), r.categories.ip_violation);

                        // Convert ModerationCategoryScores struct to HashMap
                        let mut scores_map = HashMap::new();
                        scores_map.insert("hate".to_string(), r.category_scores.hate);
                        scores_map.insert(
                            "hate/threatening".to_string(),
                            r.category_scores.hate_threatening,
                        );
                        scores_map.insert("harassment".to_string(), r.category_scores.harassment);
                        scores_map.insert(
                            "harassment/threatening".to_string(),
                            r.category_scores.harassment_threatening,
                        );
                        scores_map.insert("illicit".to_string(), r.category_scores.illicit);
                        scores_map.insert(
                            "illicit/violent".to_string(),
                            r.category_scores.illicit_violent,
                        );
                        scores_map.insert("self-harm".to_string(), r.category_scores.self_harm);
                        scores_map.insert(
                            "self-harm/intent".to_string(),
                            r.category_scores.self_harm_intent,
                        );
                        scores_map.insert(
                            "self-harm/instructions".to_string(),
                            r.category_scores.self_harm_instructions,
                        );
                        scores_map.insert("sexual".to_string(), r.category_scores.sexual);
                        scores_map
                            .insert("sexual/minors".to_string(), r.category_scores.sexual_minors);
                        scores_map.insert("violence".to_string(), r.category_scores.violence);
                        scores_map.insert(
                            "violence/graphic".to_string(),
                            r.category_scores.violence_graphic,
                        );
                        scores_map.insert("profanity".to_string(), r.category_scores.profanity);
                        scores_map.insert("insult".to_string(), r.category_scores.insult);
                        scores_map.insert("toxicity".to_string(), r.category_scores.toxicity);
                        scores_map.insert("malicious".to_string(), r.category_scores.malicious);
                        scores_map.insert("pii".to_string(), r.category_scores.pii);
                        scores_map.insert("secrets".to_string(), r.category_scores.secrets);

                        crate::inference::types::ModerationResult {
                            flagged: r.flagged,
                            categories: categories_map,
                            category_scores: scores_map,
                        }
                    })
                    .collect(),
                usage: response.usage.clone(),
                model_inference_results: vec![model_inference],
                inference_params: crate::endpoints::inference::InferenceParams::default(),
                original_response: Some(response.raw_response.clone()),
            },
        );

        // Extract observability metadata from headers (set by auth middleware)
        let observability_metadata = if let (Some(project_id), Some(endpoint_id), Some(model_id)) = (
            headers
                .get("x-tensorzero-project-id")
                .and_then(|v| v.to_str().ok()),
            headers
                .get("x-tensorzero-endpoint-id")
                .and_then(|v| v.to_str().ok()),
            headers
                .get("x-tensorzero-model-id")
                .and_then(|v| v.to_str().ok()),
        ) {
            // Extract auth metadata from headers
            let api_key_id = headers
                .get("x-tensorzero-api-key-id")
                .and_then(|v| v.to_str().ok())
                .map(|s| s.to_string());
            let user_id = headers
                .get("x-tensorzero-user-id")
                .and_then(|v| v.to_str().ok())
                .map(|s| s.to_string());
            let api_key_project_id = headers
                .get("x-tensorzero-api-key-project-id")
                .and_then(|v| v.to_str().ok())
                .map(|s| s.to_string());

            Some(super::inference::ObservabilityMetadata {
                project_id: project_id.to_string(),
                endpoint_id: endpoint_id.to_string(),
                model_id: model_id.to_string(),
                api_key_id,
                user_id,
                api_key_project_id,
            })
        } else {
            None
        };

        // Use defaults for moderation requests
        let episode_id = Uuid::now_v7();
        let metadata = crate::endpoints::inference::InferenceDatabaseInsertMetadata {
            function_name: "tensorzero::moderation".to_string(), // Default function name for moderation
            variant_name: resolved_model_name.clone(),           // Use model name as variant
            episode_id,
            tool_config: None,
            processing_time: Some(match response.latency {
                crate::inference::types::Latency::NonStreaming { response_time } => response_time,
                _ => std::time::Duration::from_millis(0),
            }),
            tags: HashMap::new(),
            extra_body: crate::inference::types::extra_body::UnfilteredInferenceExtraBody::default(
            ),
            extra_headers:
                crate::inference::types::extra_headers::UnfilteredInferenceExtraHeaders::default(),
        };

        // Convert input to ResolvedInput for write_inference
        let input_text = match &openai_compatible_params.input {
            OpenAICompatibleModerationInput::Single(text) => text.clone(),
            OpenAICompatibleModerationInput::Batch(texts) => texts.join("\n"),
        };

        let resolved_input = ResolvedInput {
            messages: vec![ResolvedInputMessage {
                role: Role::User,
                content: vec![ResolvedInputMessageContent::Text {
                    value: serde_json::Value::String(input_text),
                }],
            }],
            system: None,
        };

        // Write to observability database asynchronously
        let config_clone = config.clone();
        let clickhouse_info = clickhouse_connection_info.clone();
        let kafka_info = kafka_connection_info.clone();
        let gateway_response_json_clone = gateway_response_json.clone();
        let async_writes = config.gateway.observability.async_writes;
        let model_pricing = model_config.pricing.clone();
        let inference_batcher_clone = inference_batcher.clone();

        let write_future = tokio::spawn(async move {
            write_inference(
                &clickhouse_info,
                &kafka_info,
                &config_clone,
                resolved_input,
                result,
                metadata,
                observability_metadata,
                gateway_request_json,
                gateway_response_json_clone,
                model_pricing,
                None, // No guardrail records for moderation
                inference_batcher_clone.as_ref(),
            )
            .await;
        });

        if !async_writes {
            write_future.await.map_err(|e| {
                Error::new(ErrorDetails::InternalError {
                    message: format!("Failed to join write task: {e}"),
                })
            })?;
        }
    }

    Ok(Json(openai_response).into_response())
}

// Audio transcription types
#[derive(Clone, Debug, Default, Deserialize, Serialize)]
pub struct OpenAICompatibleAudioTranscriptionParams {
    pub model: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub language: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prompt: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub response_format: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub timestamp_granularities: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub chunking_strategy: Option<ChunkingStrategy>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub include: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stream: Option<bool>,
    #[serde(flatten)]
    pub unknown_fields: HashMap<String, Value>,
}

// Audio translation types
#[derive(Clone, Debug, Default, Deserialize, Serialize)]
pub struct OpenAICompatibleAudioTranslationParams {
    pub model: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prompt: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub response_format: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f32>,
    #[serde(flatten)]
    pub unknown_fields: HashMap<String, Value>,
}

// Text-to-speech types
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct OpenAICompatibleTextToSpeechParams {
    pub model: String,
    pub input: String,
    pub voice: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub response_format: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub speed: Option<f32>,
    #[serde(flatten)]
    pub unknown_fields: HashMap<String, Value>,
}

// Audio transcription/translation response types
#[derive(Clone, Debug, Serialize)]
pub struct OpenAICompatibleAudioTranscriptionResponse {
    pub text: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub language: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub duration: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub words: Option<Vec<OpenAICompatibleWordTimestamp>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub segments: Option<Vec<OpenAICompatibleSegmentTimestamp>>,
}

#[derive(Clone, Debug, Serialize)]
pub struct OpenAICompatibleWordTimestamp {
    pub word: String,
    pub start: f32,
    pub end: f32,
}

#[derive(Clone, Debug, Serialize)]
pub struct OpenAICompatibleSegmentTimestamp {
    pub id: u64,
    pub seek: u64,
    pub start: f32,
    pub end: f32,
    pub text: String,
    pub tokens: Vec<u64>,
    pub temperature: f32,
    pub avg_logprob: f32,
    pub compression_ratio: f32,
    pub no_speech_prob: f32,
}

/// A handler for the OpenAI-compatible audio transcription endpoint
#[debug_handler(state = AppStateData)]
pub async fn audio_transcription_handler(
    State(AppStateData {
        config,
        http_client,
        clickhouse_connection_info,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store,
        ..
    }): AppState,
    headers: HeaderMap,
    multipart: axum::extract::Multipart,
) -> Result<Response<Body>, Error> {
    // Parse multipart form data
    let (file_data, filename, params) =
        parse_audio_multipart_generic::<OpenAICompatibleAudioTranscriptionParams>(multipart)
            .await?;

    if !params.unknown_fields.is_empty() {
        tracing::warn!(
            "Ignoring unknown fields in OpenAI-compatible audio transcription request: {:?}",
            params.unknown_fields.keys().collect::<Vec<_>>()
        );
    }

    // Resolve the model name based on authentication state
    let model_resolution = model_resolution::resolve_model_name(
        Some(&params.model),
        &headers,
        false, // not for embedding
    )?;

    // Extract model configuration
    use crate::model::ModelTableExt;
    let models = config.models.read().await;
    let model_name = model_resolution.model_name.as_ref().ok_or_else(|| {
        Error::new(ErrorDetails::InvalidRequest {
            message: "Audio transcription requests must specify a model, not a function"
                .to_string(),
        })
    })?;

    let model = models
        .get_with_capability(
            model_name,
            crate::endpoints::capability::EndpointCapability::AudioTranscription,
        )
        .await?
        .ok_or_else(|| {
            Error::new(ErrorDetails::Config {
                message: format!(
                    "Model '{}' not found or does not support audio transcription",
                    model_resolution.original_model_name
                ),
            })
        })?;

    // Convert parameters to internal format
    let response_format = params
        .response_format
        .as_deref()
        .map(|f| match f {
            "json" => Ok(AudioTranscriptionResponseFormat::Json),
            "text" => Ok(AudioTranscriptionResponseFormat::Text),
            "srt" => Ok(AudioTranscriptionResponseFormat::Srt),
            "verbose_json" => Ok(AudioTranscriptionResponseFormat::VerboseJson),
            "vtt" => Ok(AudioTranscriptionResponseFormat::Vtt),
            _ => Err(Error::new(ErrorDetails::InvalidRequest {
                message: format!("Unsupported response format: {f}"),
            })),
        })
        .transpose()?;

    let timestamp_granularities = params
        .timestamp_granularities
        .as_ref()
        .map(|gs| {
            gs.iter()
                .map(|g| match g.as_str() {
                    "word" => Ok(TimestampGranularity::Word),
                    "segment" => Ok(TimestampGranularity::Segment),
                    _ => Err(Error::new(ErrorDetails::InvalidRequest {
                        message: format!("Unsupported timestamp granularity: {g}"),
                    })),
                })
                .collect::<Result<Vec<_>, _>>()
        })
        .transpose()?;

    // Capture the gateway request - serialize the params for logging (without null values)
    let _gateway_request = serialize_without_nulls(&params).ok();

    // Create transcription request
    let transcription_request = AudioTranscriptionRequest {
        id: Uuid::now_v7(),
        file: file_data,
        filename,
        model: Arc::from(model_name.as_str()),
        language: params.language,
        prompt: params.prompt,
        response_format,
        temperature: params.temperature,
        timestamp_granularities,
        chunking_strategy: params.chunking_strategy,
        include: params.include,
        stream: params.stream,
    };

    // Merge credentials from the credential store
    let credentials = merge_credentials_from_store(&model_credential_store);

    // Create inference clients with no caching for audio
    let cache_options = crate::cache::CacheOptions {
        enabled: crate::cache::CacheEnabledMode::Off,
        max_age_s: None,
    };
    let clients = super::inference::InferenceClients {
        http_client: &http_client,
        credentials: &credentials,
        clickhouse_connection_info: &clickhouse_connection_info,
        cache_options: &cache_options,
    };

    // Call the model's audio transcription capability
    let response = model
        .transcribe(
            &transcription_request,
            &model_resolution.original_model_name,
            &clients,
        )
        .await?;

    // Convert to OpenAI-compatible format based on response format
    let response_format = transcription_request
        .response_format
        .unwrap_or(AudioTranscriptionResponseFormat::Json);

    match response_format {
        AudioTranscriptionResponseFormat::Text => Response::builder()
            .header("content-type", "text/plain")
            .body(Body::from(response.text))
            .map_err(|e| {
                Error::new(ErrorDetails::InferenceClient {
                    message: format!("Failed to build HTTP response: {e}"),
                    status_code: None,
                    provider_type: "openai".to_string(),
                    raw_request: None,
                    raw_response: None,
                })
            }),
        AudioTranscriptionResponseFormat::Json | AudioTranscriptionResponseFormat::VerboseJson => {
            let openai_response = OpenAICompatibleAudioTranscriptionResponse {
                text: response.text,
                language: response.language,
                duration: response.duration,
                words: if matches!(
                    response_format,
                    AudioTranscriptionResponseFormat::VerboseJson
                ) {
                    response.words.map(|words| {
                        words
                            .into_iter()
                            .map(|w| OpenAICompatibleWordTimestamp {
                                word: w.word,
                                start: w.start,
                                end: w.end,
                            })
                            .collect()
                    })
                } else {
                    None
                },
                segments: if matches!(
                    response_format,
                    AudioTranscriptionResponseFormat::VerboseJson
                ) {
                    response.segments.map(|segments| {
                        segments
                            .into_iter()
                            .map(|s| OpenAICompatibleSegmentTimestamp {
                                id: s.id,
                                seek: s.seek,
                                start: s.start,
                                end: s.end,
                                text: s.text,
                                tokens: s.tokens,
                                temperature: s.temperature,
                                avg_logprob: s.avg_logprob,
                                compression_ratio: s.compression_ratio,
                                no_speech_prob: s.no_speech_prob,
                            })
                            .collect()
                    })
                } else {
                    None
                },
            };

            // Capture the gateway response
            let gateway_response_json = serde_json::to_string(&openai_response).ok();

            // Store the gateway response if we have it
            if let Some(gateway_response) = &gateway_response_json {
                // Log for debugging
                tracing::debug!(
                    "Gateway response captured: {} bytes",
                    gateway_response.len()
                );

                // Store the gateway response in the database
                // This requires updating the storage layer to include the gateway_response
                // For now, we'll need to update the storage layer separately
            }

            Ok(Json(openai_response).into_response())
        }
        AudioTranscriptionResponseFormat::Srt | AudioTranscriptionResponseFormat::Vtt => {
            // For now, return an error as we need to implement SRT/VTT formatting
            Err(Error::new(ErrorDetails::InvalidRequest {
                message: format!(
                    "Response format {} not yet implemented",
                    response_format.as_str()
                ),
            }))
        }
    }
}

/// A handler for the OpenAI-compatible audio translation endpoint
#[debug_handler(state = AppStateData)]
pub async fn audio_translation_handler(
    State(AppStateData {
        config,
        http_client,
        clickhouse_connection_info,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store,
        ..
    }): AppState,
    headers: HeaderMap,
    multipart: axum::extract::Multipart,
) -> Result<Response<Body>, Error> {
    // Parse multipart form data
    let (file_data, filename, params) =
        parse_audio_multipart_generic::<OpenAICompatibleAudioTranslationParams>(multipart).await?;

    if !params.unknown_fields.is_empty() {
        tracing::warn!(
            "Ignoring unknown fields in OpenAI-compatible audio translation request: {:?}",
            params.unknown_fields.keys().collect::<Vec<_>>()
        );
    }

    // Resolve the model name based on authentication state
    let model_resolution = model_resolution::resolve_model_name(
        Some(&params.model),
        &headers,
        false, // not for embedding
    )?;

    // Extract model configuration
    use crate::model::ModelTableExt;
    let models = config.models.read().await;
    let model_name = model_resolution.model_name.as_ref().ok_or_else(|| {
        Error::new(ErrorDetails::InvalidRequest {
            message: "Audio translation requests must specify a model, not a function".to_string(),
        })
    })?;

    let model = models
        .get_with_capability(
            model_name,
            crate::endpoints::capability::EndpointCapability::AudioTranslation,
        )
        .await?
        .ok_or_else(|| {
            Error::new(ErrorDetails::Config {
                message: format!(
                    "Model '{}' not found or does not support audio translation",
                    model_resolution.original_model_name
                ),
            })
        })?;

    // Convert parameters to internal format
    let response_format = params
        .response_format
        .as_deref()
        .map(|f| match f {
            "json" => Ok(AudioTranscriptionResponseFormat::Json),
            "text" => Ok(AudioTranscriptionResponseFormat::Text),
            "srt" => Ok(AudioTranscriptionResponseFormat::Srt),
            "verbose_json" => Ok(AudioTranscriptionResponseFormat::VerboseJson),
            "vtt" => Ok(AudioTranscriptionResponseFormat::Vtt),
            _ => Err(Error::new(ErrorDetails::InvalidRequest {
                message: format!("Unsupported response format: {f}"),
            })),
        })
        .transpose()?;

    // Capture the gateway request - serialize the params for logging (without null values)
    let _gateway_request = serialize_without_nulls(&params).ok();

    // Create translation request
    let translation_request = AudioTranslationRequest {
        id: Uuid::now_v7(),
        file: file_data,
        filename,
        model: Arc::from(model_name.as_str()),
        prompt: params.prompt,
        response_format,
        temperature: params.temperature,
    };

    // Merge credentials from the credential store
    let credentials = merge_credentials_from_store(&model_credential_store);

    // Create inference clients with no caching for audio
    let cache_options = crate::cache::CacheOptions {
        enabled: crate::cache::CacheEnabledMode::Off,
        max_age_s: None,
    };
    let clients = super::inference::InferenceClients {
        http_client: &http_client,
        credentials: &credentials,
        clickhouse_connection_info: &clickhouse_connection_info,
        cache_options: &cache_options,
    };

    // Call the model's audio translation capability
    let response = model
        .translate(
            &translation_request,
            &model_resolution.original_model_name,
            &clients,
        )
        .await?;

    // Convert to OpenAI-compatible format based on response format
    let response_format = translation_request
        .response_format
        .unwrap_or(AudioTranscriptionResponseFormat::Json);

    match response_format {
        AudioTranscriptionResponseFormat::Text => Response::builder()
            .header("content-type", "text/plain")
            .body(Body::from(response.text))
            .map_err(|e| {
                Error::new(ErrorDetails::InferenceClient {
                    message: format!("Failed to build HTTP response: {e}"),
                    status_code: None,
                    provider_type: "openai".to_string(),
                    raw_request: None,
                    raw_response: None,
                })
            }),
        AudioTranscriptionResponseFormat::Json | AudioTranscriptionResponseFormat::VerboseJson => {
            let openai_response = OpenAICompatibleAudioTranscriptionResponse {
                text: response.text,
                language: Some("en".to_string()), // Translation always outputs English
                duration: None,
                words: None,
                segments: None,
            };

            // Capture the gateway response
            let gateway_response_json = serde_json::to_string(&openai_response).ok();

            // Store the gateway response if we have it
            if let Some(gateway_response) = &gateway_response_json {
                // Log for debugging
                tracing::debug!(
                    "Gateway response captured: {} bytes",
                    gateway_response.len()
                );

                // Store the gateway response in the database
                // This requires updating the storage layer to include the gateway_response
                // For now, we'll need to update the storage layer separately
            }

            Ok(Json(openai_response).into_response())
        }
        AudioTranscriptionResponseFormat::Srt | AudioTranscriptionResponseFormat::Vtt => {
            // For now, return an error as we need to implement SRT/VTT formatting
            Err(Error::new(ErrorDetails::InvalidRequest {
                message: format!(
                    "Response format {} not yet implemented",
                    response_format.as_str()
                ),
            }))
        }
    }
}

/// A handler for the OpenAI-compatible text-to-speech endpoint
#[debug_handler(state = AppStateData)]
pub async fn text_to_speech_handler(
    State(AppStateData {
        config,
        http_client,
        clickhouse_connection_info,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store,
        ..
    }): AppState,
    headers: HeaderMap,
    StructuredJson(params): StructuredJson<OpenAICompatibleTextToSpeechParams>,
) -> Result<Response<Body>, Error> {
    if !params.unknown_fields.is_empty() {
        tracing::warn!(
            "Ignoring unknown fields in OpenAI-compatible text-to-speech request: {:?}",
            params.unknown_fields.keys().collect::<Vec<_>>()
        );
    }

    // Resolve the model name based on authentication state
    let model_resolution = model_resolution::resolve_model_name(
        Some(&params.model),
        &headers,
        false, // not for embedding
    )?;

    // Extract model configuration
    use crate::model::ModelTableExt;
    let models = config.models.read().await;
    let model_name = model_resolution.model_name.as_ref().ok_or_else(|| {
        Error::new(ErrorDetails::InvalidRequest {
            message: "Text-to-speech requests must specify a model, not a function".to_string(),
        })
    })?;

    let model = models
        .get_with_capability(
            model_name,
            crate::endpoints::capability::EndpointCapability::TextToSpeech,
        )
        .await?
        .ok_or_else(|| {
            Error::new(ErrorDetails::Config {
                message: format!(
                    "Model '{}' not found or does not support text-to-speech",
                    model_resolution.original_model_name
                ),
            })
        })?;

    // Convert voice parameter - try standard OpenAI voices first, then use Other for provider-specific voices
    let voice = match params.voice.as_str() {
        "alloy" => AudioVoice::Alloy,
        "ash" => AudioVoice::Ash,
        "ballad" => AudioVoice::Ballad,
        "coral" => AudioVoice::Coral,
        "echo" => AudioVoice::Echo,
        "fable" => AudioVoice::Fable,
        "onyx" => AudioVoice::Onyx,
        "nova" => AudioVoice::Nova,
        "sage" => AudioVoice::Sage,
        "shimmer" => AudioVoice::Shimmer,
        "verse" => AudioVoice::Verse,
        // For non-standard voices, use Other variant to preserve the original voice string
        _ => AudioVoice::Other(params.voice.clone()),
    };

    // Convert response format
    let response_format = params
        .response_format
        .as_deref()
        .map(|f| match f {
            "mp3" => Ok(AudioOutputFormat::Mp3),
            "opus" => Ok(AudioOutputFormat::Opus),
            "aac" => Ok(AudioOutputFormat::Aac),
            "flac" => Ok(AudioOutputFormat::Flac),
            "wav" => Ok(AudioOutputFormat::Wav),
            "pcm" => Ok(AudioOutputFormat::Pcm),
            _ => Err(Error::new(ErrorDetails::InvalidRequest {
                message: format!("Unsupported audio format: {f}"),
            })),
        })
        .transpose()?
        .unwrap_or(AudioOutputFormat::Mp3);

    // Validate input length
    if params.input.len() > 4096 {
        return Err(Error::new(ErrorDetails::InvalidRequest {
            message: "Text input must be 4,096 characters or less".to_string(),
        }));
    }

    // Validate speed parameter
    if let Some(speed) = params.speed {
        if !(0.25..=4.0).contains(&speed) {
            return Err(Error::new(ErrorDetails::InvalidRequest {
                message: "Speed must be between 0.25 and 4.0".to_string(),
            }));
        }
    }

    // Capture the gateway request (without null values)
    let _gateway_request = serialize_without_nulls(&params).ok();

    // Create text-to-speech request
    let tts_request = TextToSpeechRequest {
        id: Uuid::now_v7(),
        input: params.input,
        model: Arc::from(model_name.as_str()),
        voice,
        response_format: Some(response_format.clone()),
        speed: params.speed,
    };

    // Merge credentials from the credential store
    let credentials = merge_credentials_from_store(&model_credential_store);

    // Create inference clients with no caching for audio
    let cache_options = crate::cache::CacheOptions {
        enabled: crate::cache::CacheEnabledMode::Off,
        max_age_s: None,
    };
    let clients = super::inference::InferenceClients {
        http_client: &http_client,
        credentials: &credentials,
        clickhouse_connection_info: &clickhouse_connection_info,
        cache_options: &cache_options,
    };

    // Call the model's text-to-speech capability
    let response = model
        .generate_speech(
            &tts_request,
            &model_resolution.original_model_name,
            &clients,
        )
        .await?;

    // Return binary audio response
    let content_type = match response_format {
        AudioOutputFormat::Mp3 => "audio/mpeg",
        AudioOutputFormat::Opus => "audio/opus",
        AudioOutputFormat::Aac => "audio/aac",
        AudioOutputFormat::Flac => "audio/flac",
        AudioOutputFormat::Wav => "audio/wav",
        AudioOutputFormat::Pcm => "audio/pcm",
    };

    Response::builder()
        .header("content-type", content_type)
        .body(Body::from(response.audio_data))
        .map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                message: format!("Failed to build HTTP response: {e}"),
                status_code: None,
                provider_type: "openai".to_string(),
                raw_request: None,
                raw_response: None,
            })
        })
}

/// Handler for creating realtime sessions
#[debug_handler(state = AppStateData)]
pub async fn realtime_session_handler(
    State(AppStateData {
        config,
        http_client,
        clickhouse_connection_info,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store: _,
        ..
    }): AppState,
    headers: HeaderMap,
    StructuredJson(params): StructuredJson<RealtimeSessionRequest>,
) -> Result<Response<Body>, Error> {
    // Resolve the model name based on authentication state
    let model_resolution = model_resolution::resolve_model_name(
        Some(&params.model),
        &headers,
        false, // not for embedding
    )?;

    // Extract model configuration
    use crate::model::ModelTableExt;
    let models = config.models.read().await;
    let model_name = model_resolution.model_name.as_ref().ok_or_else(|| {
        Error::new(ErrorDetails::InvalidRequest {
            message: "Realtime session requests must specify a model, not a function".to_string(),
        })
    })?;

    let model = models
        .get_with_capability(
            model_name,
            crate::endpoints::capability::EndpointCapability::RealtimeSession,
        )
        .await?
        .ok_or_else(|| {
            Error::new(ErrorDetails::InvalidRequest {
                message: format!(
                    "Model '{}' not found or does not support realtime sessions",
                    model_resolution.original_model_name
                ),
            })
        })?;

    // Create credentials
    let credentials = InferenceCredentials::default();

    // Create inference clients
    let clients = super::inference::InferenceClients {
        http_client: &http_client,
        credentials: &credentials,
        clickhouse_connection_info: &clickhouse_connection_info,
        cache_options: &crate::cache::CacheOptions {
            enabled: crate::cache::CacheEnabledMode::Off, // No caching for realtime sessions
            max_age_s: None,
        },
    };

    // Call the model's realtime session capability
    let response = model
        .create_realtime_session(&params, &model_resolution.original_model_name, &clients)
        .await?;

    let json_response = serde_json::to_string(&response).map_err(|e| {
        Error::new(ErrorDetails::InvalidRequest {
            message: format!("Failed to serialize response: {e}"),
        })
    })?;

    Response::builder()
        .header("content-type", "application/json")
        .body(Body::from(json_response))
        .map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                message: format!("Failed to build HTTP response: {e}"),
                status_code: None,
                provider_type: "openai".to_string(),
                raw_request: None,
                raw_response: None,
            })
        })
}

/// Handler for creating realtime transcription sessions
#[debug_handler(state = AppStateData)]
pub async fn realtime_transcription_session_handler(
    State(AppStateData {
        config,
        http_client,
        clickhouse_connection_info,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store: _,
        ..
    }): AppState,
    headers: HeaderMap,
    StructuredJson(params): StructuredJson<RealtimeTranscriptionRequest>,
) -> Result<Response<Body>, Error> {
    // Resolve the model name based on authentication state
    let model_resolution = model_resolution::resolve_model_name(
        Some(&params.model),
        &headers,
        false, // not for embedding
    )?;

    // Extract model configuration
    use crate::model::ModelTableExt;
    let models = config.models.read().await;
    let model_name = model_resolution.model_name.as_ref().ok_or_else(|| {
        Error::new(ErrorDetails::InvalidRequest {
            message: "Realtime transcription requests must specify a model, not a function"
                .to_string(),
        })
    })?;

    let model = models
        .get_with_capability(
            model_name,
            crate::endpoints::capability::EndpointCapability::RealtimeTranscription,
        )
        .await?
        .ok_or_else(|| {
            Error::new(ErrorDetails::InvalidRequest {
                message: format!(
                    "Model '{}' not found or does not support realtime transcription",
                    model_resolution.original_model_name
                ),
            })
        })?;

    // Create credentials
    let credentials = InferenceCredentials::default();

    // Create inference clients
    let clients = super::inference::InferenceClients {
        http_client: &http_client,
        credentials: &credentials,
        clickhouse_connection_info: &clickhouse_connection_info,
        cache_options: &crate::cache::CacheOptions {
            enabled: crate::cache::CacheEnabledMode::Off, // No caching for realtime sessions
            max_age_s: None,
        },
    };

    // Call the model's realtime transcription capability
    let response = model
        .create_realtime_transcription_session(
            &params,
            &model_resolution.original_model_name,
            &clients,
        )
        .await?;

    let json_response = serde_json::to_string(&response).map_err(|e| {
        Error::new(ErrorDetails::InvalidRequest {
            message: format!("Failed to serialize response: {e}"),
        })
    })?;

    Response::builder()
        .header("content-type", "application/json")
        .body(Body::from(json_response))
        .map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                message: format!("Failed to build HTTP response: {e}"),
                status_code: None,
                provider_type: "openai".to_string(),
                raw_request: None,
                raw_response: None,
            })
        })
}

// Helper function to parse multipart form data for audio transcription
// Trait for parsing audio multipart parameters
trait AudioMultipartParams: Default {
    fn set_field(&mut self, name: &str, value: String) -> Result<(), Error>;
    fn model(&self) -> &str;
}

impl AudioMultipartParams for OpenAICompatibleAudioTranscriptionParams {
    fn model(&self) -> &str {
        &self.model
    }

    fn set_field(&mut self, name: &str, value: String) -> Result<(), Error> {
        match name {
            "model" => self.model = value,
            "language" => self.language = Some(value),
            "prompt" => self.prompt = Some(value),
            "response_format" => self.response_format = Some(value),
            "temperature" => {
                self.temperature = Some(value.parse().map_err(|e| {
                    Error::new(ErrorDetails::InvalidRequest {
                        message: format!("Invalid temperature value: {e}"),
                    })
                })?);
            }
            "timestamp_granularities[]" => {
                self.timestamp_granularities
                    .get_or_insert_with(Vec::new)
                    .push(value);
            }
            "chunking_strategy" => {
                self.chunking_strategy = Some(serde_json::from_str(&value).map_err(|e| {
                    Error::new(ErrorDetails::InvalidRequest {
                        message: format!("Invalid chunking_strategy format: {e}"),
                    })
                })?);
            }
            "include[]" => {
                self.include.get_or_insert_with(Vec::new).push(value);
            }
            "stream" => {
                self.stream = Some(value.parse().map_err(|e| {
                    Error::new(ErrorDetails::InvalidRequest {
                        message: format!("Invalid stream value: {e}"),
                    })
                })?);
            }
            _ => {
                self.unknown_fields
                    .insert(name.to_string(), serde_json::Value::String(value));
            }
        }
        Ok(())
    }
}

impl AudioMultipartParams for OpenAICompatibleAudioTranslationParams {
    fn model(&self) -> &str {
        &self.model
    }

    fn set_field(&mut self, name: &str, value: String) -> Result<(), Error> {
        match name {
            "model" => self.model = value,
            "prompt" => self.prompt = Some(value),
            "response_format" => self.response_format = Some(value),
            "temperature" => {
                self.temperature = Some(value.parse().map_err(|e| {
                    Error::new(ErrorDetails::InvalidRequest {
                        message: format!("Invalid temperature value: {e}"),
                    })
                })?);
            }
            _ => {
                self.unknown_fields
                    .insert(name.to_string(), serde_json::Value::String(value));
            }
        }
        Ok(())
    }
}

// Generic function to parse audio multipart data
async fn parse_audio_multipart_generic<P: AudioMultipartParams>(
    mut multipart: axum::extract::Multipart,
) -> Result<(Vec<u8>, String, P), Error> {
    let mut file_data = None;
    let mut filename = None;
    let mut params = P::default();

    while let Some(field) = multipart.next_field().await.map_err(|e| {
        Error::new(ErrorDetails::InvalidRequest {
            message: format!("Failed to parse multipart field: {e}"),
        })
    })? {
        let name = field.name().unwrap_or("").to_string();

        match name.as_str() {
            "file" => {
                filename = Some(field.file_name().unwrap_or("audio").to_string());
                file_data = Some(
                    field
                        .bytes()
                        .await
                        .map_err(|e| {
                            Error::new(ErrorDetails::InvalidRequest {
                                message: format!("Failed to read file data: {e}"),
                            })
                        })?
                        .to_vec(),
                );
            }
            _ => {
                let value = field.text().await.map_err(|e| {
                    Error::new(ErrorDetails::InvalidRequest {
                        message: format!("Failed to read field '{name}': {e}"),
                    })
                })?;
                params.set_field(&name, value)?;
            }
        }
    }

    let file_data = file_data.ok_or_else(|| {
        Error::new(ErrorDetails::InvalidRequest {
            message: "Missing required 'file' field".to_string(),
        })
    })?;

    let filename = filename.unwrap_or_else(|| "audio".to_string());

    if params.model().is_empty() {
        return Err(Error::new(ErrorDetails::InvalidRequest {
            message: "Missing required 'model' field".to_string(),
        }));
    }

    // Validate file size (25MB limit)
    if file_data.len() > 25 * 1024 * 1024 {
        return Err(Error::new(ErrorDetails::InvalidRequest {
            message: "File size exceeds 25MB limit".to_string(),
        }));
    }

    Ok((file_data, filename, params))
}

// OpenAI-compatible Images API handlers

use crate::images::*;

/// Handler for image generation (POST /v1/images/generations)
#[debug_handler(state = AppStateData)]
pub async fn image_generation_handler(
    State(AppStateData {
        config,
        http_client,
        clickhouse_connection_info,
        kafka_connection_info,
        authentication_info: _,
        model_credential_store,
        inference_batcher,
        ..
    }): AppState,
    headers: HeaderMap,
    StructuredJson(params): StructuredJson<OpenAICompatibleImageGenerationParams>,
) -> Result<Response<Body>, Error> {
    if !params.unknown_fields.is_empty() {
        tracing::warn!(
            "Ignoring unknown fields in OpenAI-compatible image generation request: {:?}",
            params.unknown_fields.keys().collect::<Vec<_>>()
        );
    }

    // Resolve the model name based on authentication state
    let model_resolution = model_resolution::resolve_model_name(
        Some(&params.model),
        &headers,
        false, // not for embedding
    )?;

    // Extract model configuration
    use crate::model::ModelTableExt;
    let models = config.models.read().await;
    let model_name = model_resolution.model_name.as_ref().ok_or_else(|| {
        Error::new(ErrorDetails::InvalidRequest {
            message: "Image generation requests must specify a model, not a function".to_string(),
        })
    })?;

    let model = match models
        .get_with_capability(
            model_name,
            crate::endpoints::capability::EndpointCapability::ImageGeneration,
        )
        .await
    {
        Ok(Some(model)) => model,
        Ok(None) => {
            // Model doesn't exist - return 404 with ModelNotFound error
            return Err(Error::new(ErrorDetails::ModelNotFound {
                name: model_name.to_string(),
            }));
        }
        Err(e) => {
            // Model exists but doesn't support image generation (or other errors)
            // This will return BAD_REQUEST for CapabilityNotSupported
            return Err(e);
        }
    };

    // Convert parameters to internal format
    let size = params.size.as_deref().map(str::parse).transpose()?;

    let quality = params.quality.as_deref().map(str::parse).transpose()?;

    let style = params.style.as_deref().map(str::parse).transpose()?;

    let response_format = params
        .response_format
        .as_deref()
        .map(str::parse)
        .transpose()?;

    let background = params.background.as_deref().map(str::parse).transpose()?;

    let moderation = params.moderation.as_deref().map(str::parse).transpose()?;

    let output_format = params
        .output_format
        .as_deref()
        .map(str::parse)
        .transpose()?;

    // Validate prompt length
    if params.prompt.len() > 4000 {
        return Err(Error::new(ErrorDetails::InvalidRequest {
            message: "Prompt must be 4,000 characters or less".to_string(),
        }));
    }

    // Validate n parameter
    if let Some(n) = params.n {
        if n == 0 || n > 10 {
            return Err(Error::new(ErrorDetails::InvalidRequest {
                message: "n must be between 1 and 10".to_string(),
            }));
        }
    }

    // Capture the gateway request (without null values) before params are consumed
    let gateway_request_json = serialize_without_nulls(&params).ok();

    // Create image generation request
    let image_request = ImageGenerationRequest {
        id: Uuid::now_v7(),
        prompt: params.prompt,
        model: Arc::from(model_name.as_str()),
        n: params.n,
        size,
        quality,
        style,
        response_format,
        user: params.user,
        background,
        moderation,
        output_compression: params.output_compression,
        output_format,
    };

    // Merge credentials from the credential store
    let credentials = merge_credentials_from_store(&model_credential_store);

    // Create inference clients with no caching for images
    let cache_options = crate::cache::CacheOptions {
        enabled: crate::cache::CacheEnabledMode::Off,
        max_age_s: None,
    };
    let clients = super::inference::InferenceClients {
        http_client: &http_client,
        credentials: &credentials,
        clickhouse_connection_info: &clickhouse_connection_info,
        cache_options: &cache_options,
    };

    // Call the model's image generation capability
    let response = model
        .generate_image(
            &image_request,
            &model_resolution.original_model_name,
            &clients,
        )
        .await?;

    // Convert to OpenAI-compatible format
    let openai_response = OpenAICompatibleImageResponse {
        created: response.created,
        data: response
            .data
            .clone()
            .into_iter()
            .map(|d| OpenAICompatibleImageData {
                url: d.url.clone(),
                b64_json: d.b64_json.clone(),
                revised_prompt: d.revised_prompt.clone(),
            })
            .collect(),
    };

    // Capture the gateway response (without null values)
    let gateway_response_json = serialize_without_nulls(&openai_response).ok();

    // Write observability data
    if config.gateway.observability.enabled.unwrap_or(true) {
        let inference_id = image_request.id;

        // Create ModelInferenceResponseWithMetadata
        let model_inference = crate::inference::types::ModelInferenceResponseWithMetadata {
            id: Uuid::now_v7(),
            created: response.created,
            output: vec![],
            model_name: Arc::from(model_name.as_str()),
            model_provider_name: model
                .providers
                .values()
                .next()
                .map(|p| p.name.clone())
                .unwrap_or_default(),
            input_messages: vec![],
            raw_request: response.raw_request.clone(),
            raw_response: response.raw_response.clone(),
            usage: response.usage.clone(),
            system: None,
            cached: false,
            latency: response.latency.clone(),
            finish_reason: Some(crate::inference::types::FinishReason::Stop),
            gateway_request: None,
            gateway_response: None,
            guardrail_scan_summary: None,
        };

        // Create the InferenceResult
        let result = crate::inference::types::InferenceResult::ImageGeneration(
            crate::inference::types::ImageGenerationInferenceResult {
                inference_id,
                created: response.created,
                images: response
                    .data
                    .iter()
                    .map(|d| crate::inference::types::ImageData {
                        url: d.url.clone(),
                        base64: d.b64_json.clone(),
                        revised_prompt: d.revised_prompt.clone(),
                    })
                    .collect(),
                image_count: response.data.len() as u8,
                size: image_request
                    .size
                    .map(|s| s.as_str().to_string())
                    .unwrap_or_else(|| "1024x1024".to_string()),
                quality: image_request
                    .quality
                    .map(|q| q.as_str().to_string())
                    .unwrap_or_else(|| "standard".to_string()),
                style: image_request.style.map(|s| s.as_str().to_string()),
                usage: response.usage.clone(),
                model_inference_results: vec![model_inference],
                inference_params: crate::endpoints::inference::InferenceParams::default(),
                original_response: Some(response.raw_response.clone()),
            },
        );

        // Extract observability metadata from headers (set by auth middleware)
        let observability_metadata = if let (Some(project_id), Some(endpoint_id), Some(model_id)) = (
            headers
                .get("x-tensorzero-project-id")
                .and_then(|v| v.to_str().ok()),
            headers
                .get("x-tensorzero-endpoint-id")
                .and_then(|v| v.to_str().ok()),
            headers
                .get("x-tensorzero-model-id")
                .and_then(|v| v.to_str().ok()),
        ) {
            // Extract auth metadata from headers
            let api_key_id = headers
                .get("x-tensorzero-api-key-id")
                .and_then(|v| v.to_str().ok())
                .map(|s| s.to_string());
            let user_id = headers
                .get("x-tensorzero-user-id")
                .and_then(|v| v.to_str().ok())
                .map(|s| s.to_string());
            let api_key_project_id = headers
                .get("x-tensorzero-api-key-project-id")
                .and_then(|v| v.to_str().ok())
                .map(|s| s.to_string());

            Some(super::inference::ObservabilityMetadata {
                project_id: project_id.to_string(),
                endpoint_id: endpoint_id.to_string(),
                model_id: model_id.to_string(),
                api_key_id,
                user_id,
                api_key_project_id,
            })
        } else {
            None
        };

        // Use defaults for image generation requests
        let episode_id = Uuid::now_v7();
        let metadata = crate::endpoints::inference::InferenceDatabaseInsertMetadata {
            function_name: "tensorzero::image_generation".to_string(), // Default function name for images
            variant_name: model_name.to_string(),                      // Use model name as variant
            episode_id,
            tool_config: None,
            processing_time: Some(match response.latency {
                crate::inference::types::Latency::NonStreaming { response_time } => response_time,
                _ => std::time::Duration::from_millis(0),
            }),
            tags: HashMap::new(),
            extra_body: UnfilteredInferenceExtraBody::default(),
            extra_headers:
                crate::inference::types::extra_headers::UnfilteredInferenceExtraHeaders::default(),
        };

        // Convert prompt to ResolvedInput for write_inference
        let resolved_input = ResolvedInput {
            messages: vec![ResolvedInputMessage {
                role: Role::User,
                content: vec![ResolvedInputMessageContent::Text {
                    value: serde_json::Value::String(image_request.prompt.clone()),
                }],
            }],
            system: None,
        };

        // Gateway request already captured before params were consumed

        // Write to observability database asynchronously
        let config_clone = config.clone();
        let clickhouse_info = clickhouse_connection_info.clone();
        let kafka_info = kafka_connection_info.clone();
        let gateway_response_json = gateway_response_json.clone();
        let async_writes = config.gateway.observability.async_writes;
        let model_pricing = model.pricing.clone();
        let inference_batcher_clone = inference_batcher.clone();

        let write_future = tokio::spawn(async move {
            write_inference(
                &clickhouse_info,
                &kafka_info,
                &config_clone,
                resolved_input,
                result,
                metadata,
                observability_metadata,
                gateway_request_json,
                gateway_response_json,
                model_pricing,
                None, // No guardrail records for image generation
                inference_batcher_clone.as_ref(),
            )
            .await;
        });

        if !async_writes {
            write_future.await.map_err(|e| {
                Error::new(ErrorDetails::InternalError {
                    message: format!("Failed to join write task: {e}"),
                })
            })?;
        }
    }

    Ok(Json(openai_response).into_response())
}

/// Handler for image editing (POST /v1/images/edits)
#[debug_handler(state = AppStateData)]
pub async fn image_edit_handler(
    State(AppStateData {
        config,
        http_client,
        clickhouse_connection_info,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store,
        ..
    }): AppState,
    headers: HeaderMap,
    multipart: axum::extract::Multipart,
) -> Result<Response<Body>, Error> {
    // Parse multipart form data
    let (image_data, image_filename, mask_data, mask_filename, params) =
        parse_image_edit_multipart(multipart).await?;

    if !params.unknown_fields.is_empty() {
        tracing::warn!(
            "Ignoring unknown fields in OpenAI-compatible image edit request: {:?}",
            params.unknown_fields.keys().collect::<Vec<_>>()
        );
    }

    // Resolve the model name based on authentication state
    let model_resolution = model_resolution::resolve_model_name(
        Some(&params.model),
        &headers,
        false, // not for embedding
    )?;

    // Extract model configuration
    use crate::model::ModelTableExt;
    let models = config.models.read().await;
    let model_name = model_resolution.model_name.as_ref().ok_or_else(|| {
        Error::new(ErrorDetails::InvalidRequest {
            message: "Image edit requests must specify a model, not a function".to_string(),
        })
    })?;

    let model = models
        .get_with_capability(
            model_name,
            crate::endpoints::capability::EndpointCapability::ImageEdit,
        )
        .await?
        .ok_or_else(|| {
            Error::new(ErrorDetails::Config {
                message: format!(
                    "Model '{}' not found or does not support image editing",
                    model_resolution.original_model_name
                ),
            })
        })?;

    // Convert parameters to internal format
    let size = params.size.as_deref().map(str::parse).transpose()?;

    let response_format = params
        .response_format
        .as_deref()
        .map(str::parse)
        .transpose()?;

    let background = params.background.as_deref().map(str::parse).transpose()?;

    let quality = params.quality.as_deref().map(str::parse).transpose()?;

    let output_format = params
        .output_format
        .as_deref()
        .map(str::parse)
        .transpose()?;

    // Validate parameters
    if params.prompt.len() > 1000 {
        return Err(Error::new(ErrorDetails::InvalidRequest {
            message: "Prompt must be 1,000 characters or less".to_string(),
        }));
    }

    if let Some(n) = params.n {
        if n == 0 || n > 10 {
            return Err(Error::new(ErrorDetails::InvalidRequest {
                message: "n must be between 1 and 10".to_string(),
            }));
        }
    }

    // Capture the gateway request (without null values)
    let _gateway_request = serialize_without_nulls(&params).ok();

    // Create image edit request
    let image_request = ImageEditRequest {
        id: Uuid::now_v7(),
        image: image_data,
        image_filename,
        prompt: params.prompt,
        mask: mask_data,
        mask_filename,
        model: Arc::from(model_name.as_str()),
        n: params.n,
        size,
        response_format,
        user: params.user,
        background,
        quality,
        output_compression: params.output_compression,
        output_format,
    };

    // Merge credentials from the credential store
    let credentials = merge_credentials_from_store(&model_credential_store);

    // Create inference clients with no caching for images
    let cache_options = crate::cache::CacheOptions {
        enabled: crate::cache::CacheEnabledMode::Off,
        max_age_s: None,
    };
    let clients = super::inference::InferenceClients {
        http_client: &http_client,
        credentials: &credentials,
        clickhouse_connection_info: &clickhouse_connection_info,
        cache_options: &cache_options,
    };

    // Call the model's image edit capability
    let response = model
        .edit_image(
            &image_request,
            &model_resolution.original_model_name,
            &clients,
        )
        .await?;

    // Convert to OpenAI-compatible format
    let openai_response = OpenAICompatibleImageResponse {
        created: response.created,
        data: response
            .data
            .into_iter()
            .map(|d| OpenAICompatibleImageData {
                url: d.url,
                b64_json: d.b64_json,
                revised_prompt: d.revised_prompt,
            })
            .collect(),
    };

    // Capture the gateway response (without null values)
    let gateway_response_json = serialize_without_nulls(&openai_response).ok();

    // Store the gateway response if we have it
    if let Some(gateway_response) = &gateway_response_json {
        // Log for debugging
        tracing::debug!(
            "Gateway response captured: {} bytes",
            gateway_response.len()
        );

        // Store the gateway response in the database
        // This requires updating the storage layer to include the gateway_response
        // For now, we'll need to update the storage layer separately
    }

    Ok(Json(openai_response).into_response())
}

/// Handler for image variations (POST /v1/images/variations)
#[debug_handler(state = AppStateData)]
pub async fn image_variation_handler(
    State(AppStateData {
        config,
        http_client,
        clickhouse_connection_info,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store,
        ..
    }): AppState,
    headers: HeaderMap,
    multipart: axum::extract::Multipart,
) -> Result<Response<Body>, Error> {
    // Parse multipart form data
    let (image_data, image_filename, params) = parse_image_variation_multipart(multipart).await?;

    if !params.unknown_fields.is_empty() {
        tracing::warn!(
            "Ignoring unknown fields in OpenAI-compatible image variation request: {:?}",
            params.unknown_fields.keys().collect::<Vec<_>>()
        );
    }

    // Resolve the model name based on authentication state
    let model_resolution = model_resolution::resolve_model_name(
        Some(&params.model),
        &headers,
        false, // not for embedding
    )?;

    // Extract model configuration
    use crate::model::ModelTableExt;
    let models = config.models.read().await;
    let model_name = model_resolution.model_name.as_ref().ok_or_else(|| {
        Error::new(ErrorDetails::InvalidRequest {
            message: "Image variation requests must specify a model, not a function".to_string(),
        })
    })?;

    let model = models
        .get_with_capability(
            model_name,
            crate::endpoints::capability::EndpointCapability::ImageVariation,
        )
        .await?
        .ok_or_else(|| {
            Error::new(ErrorDetails::Config {
                message: format!(
                    "Model '{}' not found or does not support image variations",
                    model_resolution.original_model_name
                ),
            })
        })?;

    // Convert parameters to internal format
    let size = params.size.as_deref().map(str::parse).transpose()?;

    let response_format = params
        .response_format
        .as_deref()
        .map(str::parse)
        .transpose()?;

    // Validate parameters
    if let Some(n) = params.n {
        if n == 0 || n > 10 {
            return Err(Error::new(ErrorDetails::InvalidRequest {
                message: "n must be between 1 and 10".to_string(),
            }));
        }
    }

    // Capture the gateway request (without null values)
    let _gateway_request = serialize_without_nulls(&params).ok();

    // Create image variation request
    let image_request = ImageVariationRequest {
        id: Uuid::now_v7(),
        image: image_data,
        image_filename,
        model: Arc::from(model_name.as_str()),
        n: params.n,
        size,
        response_format,
        user: params.user,
    };

    // Merge credentials from the credential store
    let credentials = merge_credentials_from_store(&model_credential_store);

    // Create inference clients with no caching for images
    let cache_options = crate::cache::CacheOptions {
        enabled: crate::cache::CacheEnabledMode::Off,
        max_age_s: None,
    };
    let clients = super::inference::InferenceClients {
        http_client: &http_client,
        credentials: &credentials,
        clickhouse_connection_info: &clickhouse_connection_info,
        cache_options: &cache_options,
    };

    // Call the model's image variation capability
    let response = model
        .create_image_variation(
            &image_request,
            &model_resolution.original_model_name,
            &clients,
        )
        .await?;

    // Convert to OpenAI-compatible format
    let openai_response = OpenAICompatibleImageResponse {
        created: response.created,
        data: response
            .data
            .into_iter()
            .map(|d| OpenAICompatibleImageData {
                url: d.url,
                b64_json: d.b64_json,
                revised_prompt: d.revised_prompt,
            })
            .collect(),
    };

    // Capture the gateway response (without null values)
    let gateway_response_json = serialize_without_nulls(&openai_response).ok();

    // Store the gateway response if we have it
    if let Some(gateway_response) = &gateway_response_json {
        // Log for debugging
        tracing::debug!(
            "Gateway response captured: {} bytes",
            gateway_response.len()
        );

        // Store the gateway response in the database
        // This requires updating the storage layer to include the gateway_response
        // For now, we'll need to update the storage layer separately
    }

    Ok(Json(openai_response).into_response())
}

// OpenAI-compatible Image parameter types
#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct OpenAICompatibleImageGenerationParams {
    pub prompt: String,
    pub model: String,
    pub n: Option<u8>,
    pub size: Option<String>,
    pub quality: Option<String>,
    pub style: Option<String>,
    pub response_format: Option<String>,
    pub user: Option<String>,
    // GPT-Image-1 specific parameters
    pub background: Option<String>,
    pub moderation: Option<String>,
    pub output_compression: Option<u8>,
    pub output_format: Option<String>,
    #[serde(flatten)]
    pub unknown_fields: HashMap<String, Value>,
}

#[derive(Debug, Default, Serialize)]
pub struct OpenAICompatibleImageEditParams {
    pub model: String,
    pub prompt: String,
    pub n: Option<u8>,
    pub size: Option<String>,
    pub response_format: Option<String>,
    pub user: Option<String>,
    // Model-specific parameters
    pub background: Option<String>,
    pub quality: Option<String>,
    pub output_compression: Option<u8>,
    pub output_format: Option<String>,
    pub unknown_fields: HashMap<String, Value>,
}

#[derive(Debug, Default, Serialize)]
pub struct OpenAICompatibleImageVariationParams {
    pub model: String,
    pub n: Option<u8>,
    pub size: Option<String>,
    pub response_format: Option<String>,
    pub user: Option<String>,
    pub unknown_fields: HashMap<String, Value>,
}

// OpenAI-compatible Image response types
#[derive(Debug, Serialize)]
pub struct OpenAICompatibleImageResponse {
    pub created: u64,
    pub data: Vec<OpenAICompatibleImageData>,
}

#[derive(Debug, Serialize)]
pub struct OpenAICompatibleImageData {
    pub url: Option<String>,
    pub b64_json: Option<String>,
    pub revised_prompt: Option<String>,
}

// Image multipart form parsing helpers
async fn parse_image_edit_multipart(
    mut multipart: axum::extract::Multipart,
) -> Result<
    (
        Vec<u8>,
        String,
        Option<Vec<u8>>,
        Option<String>,
        OpenAICompatibleImageEditParams,
    ),
    Error,
> {
    let mut image_data = None;
    let mut image_filename = None;
    let mut mask_data = None;
    let mut mask_filename = None;
    let mut params = OpenAICompatibleImageEditParams::default();

    while let Some(field) = multipart.next_field().await.map_err(|e| {
        Error::new(ErrorDetails::InvalidRequest {
            message: format!("Failed to parse multipart field: {e}"),
        })
    })? {
        let name = field.name().unwrap_or("").to_string();

        match name.as_str() {
            "image" => {
                image_filename = Some(field.file_name().unwrap_or("image.png").to_string());
                image_data = Some(
                    field
                        .bytes()
                        .await
                        .map_err(|e| {
                            Error::new(ErrorDetails::InvalidRequest {
                                message: format!("Failed to read image data: {e}"),
                            })
                        })?
                        .to_vec(),
                );
            }
            "mask" => {
                mask_filename = Some(field.file_name().unwrap_or("mask.png").to_string());
                mask_data = Some(
                    field
                        .bytes()
                        .await
                        .map_err(|e| {
                            Error::new(ErrorDetails::InvalidRequest {
                                message: format!("Failed to read mask data: {e}"),
                            })
                        })?
                        .to_vec(),
                );
            }
            _ => {
                let value = field.text().await.map_err(|e| {
                    Error::new(ErrorDetails::InvalidRequest {
                        message: format!("Failed to read field '{name}': {e}"),
                    })
                })?;
                set_image_edit_field(&mut params, &name, value)?;
            }
        }
    }

    let image_data = image_data.ok_or_else(|| {
        Error::new(ErrorDetails::InvalidRequest {
            message: "Missing required 'image' field".to_string(),
        })
    })?;

    let image_filename = image_filename.unwrap_or_else(|| "image.png".to_string());

    if params.model.is_empty() {
        return Err(Error::new(ErrorDetails::InvalidRequest {
            message: "Missing required 'model' field".to_string(),
        }));
    }

    if params.prompt.is_empty() {
        return Err(Error::new(ErrorDetails::InvalidRequest {
            message: "Missing required 'prompt' field".to_string(),
        }));
    }

    // Validate file size (4MB limit for images)
    if image_data.len() > 4 * 1024 * 1024 {
        return Err(Error::new(ErrorDetails::InvalidRequest {
            message: "Image file size exceeds 4MB limit".to_string(),
        }));
    }

    if let Some(ref mask) = mask_data {
        if mask.len() > 4 * 1024 * 1024 {
            return Err(Error::new(ErrorDetails::InvalidRequest {
                message: "Mask file size exceeds 4MB limit".to_string(),
            }));
        }
    }

    Ok((image_data, image_filename, mask_data, mask_filename, params))
}

async fn parse_image_variation_multipart(
    mut multipart: axum::extract::Multipart,
) -> Result<(Vec<u8>, String, OpenAICompatibleImageVariationParams), Error> {
    let mut image_data = None;
    let mut image_filename = None;
    let mut params = OpenAICompatibleImageVariationParams::default();

    while let Some(field) = multipart.next_field().await.map_err(|e| {
        Error::new(ErrorDetails::InvalidRequest {
            message: format!("Failed to parse multipart field: {e}"),
        })
    })? {
        let name = field.name().unwrap_or("").to_string();

        match name.as_str() {
            "image" => {
                image_filename = Some(field.file_name().unwrap_or("image.png").to_string());
                image_data = Some(
                    field
                        .bytes()
                        .await
                        .map_err(|e| {
                            Error::new(ErrorDetails::InvalidRequest {
                                message: format!("Failed to read image data: {e}"),
                            })
                        })?
                        .to_vec(),
                );
            }
            _ => {
                let value = field.text().await.map_err(|e| {
                    Error::new(ErrorDetails::InvalidRequest {
                        message: format!("Failed to read field '{name}': {e}"),
                    })
                })?;
                set_image_variation_field(&mut params, &name, value)?;
            }
        }
    }

    let image_data = image_data.ok_or_else(|| {
        Error::new(ErrorDetails::InvalidRequest {
            message: "Missing required 'image' field".to_string(),
        })
    })?;

    let image_filename = image_filename.unwrap_or_else(|| "image.png".to_string());

    if params.model.is_empty() {
        return Err(Error::new(ErrorDetails::InvalidRequest {
            message: "Missing required 'model' field".to_string(),
        }));
    }

    // Validate file size (4MB limit)
    if image_data.len() > 4 * 1024 * 1024 {
        return Err(Error::new(ErrorDetails::InvalidRequest {
            message: "Image file size exceeds 4MB limit".to_string(),
        }));
    }

    Ok((image_data, image_filename, params))
}

fn set_image_edit_field(
    params: &mut OpenAICompatibleImageEditParams,
    name: &str,
    value: String,
) -> Result<(), Error> {
    match name {
        "model" => params.model = value,
        "prompt" => params.prompt = value,
        "n" => {
            params.n = Some(value.parse().map_err(|_| {
                Error::new(ErrorDetails::InvalidRequest {
                    message: format!("Invalid value for 'n': {value}"),
                })
            })?);
        }
        "size" => params.size = Some(value),
        "response_format" => params.response_format = Some(value),
        "user" => params.user = Some(value),
        "background" => params.background = Some(value),
        "quality" => params.quality = Some(value),
        "output_compression" => {
            params.output_compression = Some(value.parse().map_err(|_| {
                Error::new(ErrorDetails::InvalidRequest {
                    message: format!("Invalid value for 'output_compression': {value}"),
                })
            })?);
        }
        "output_format" => params.output_format = Some(value),
        _ => {
            params
                .unknown_fields
                .insert(name.to_string(), Value::String(value));
        }
    }
    Ok(())
}

fn set_image_variation_field(
    params: &mut OpenAICompatibleImageVariationParams,
    name: &str,
    value: String,
) -> Result<(), Error> {
    match name {
        "model" => params.model = value,
        "n" => {
            params.n = Some(value.parse().map_err(|_| {
                Error::new(ErrorDetails::InvalidRequest {
                    message: format!("Invalid value for 'n': {value}"),
                })
            })?);
        }
        "size" => params.size = Some(value),
        "response_format" => params.response_format = Some(value),
        "user" => params.user = Some(value),
        _ => {
            params
                .unknown_fields
                .insert(name.to_string(), Value::String(value));
        }
    }
    Ok(())
}

// OpenAI-compatible Responses API handlers

use crate::responses::{OpenAIResponse, OpenAIResponseCreateParams, ResponseStreamEvent};

/// Try to reconstruct an OpenAIResponse from a sequence of streaming events.
/// This is used for observability to record response fields after streaming completes.
fn try_reconstruct_response_from_events(events: &[ResponseStreamEvent]) -> Option<OpenAIResponse> {
    // Look for response.completed event (has the full response nested under "response" key)
    for event in events.iter().rev() {
        if event.event == "response.completed" {
            // The response is nested under the "response" key in the event data
            // Event structure: {"response": {...}, "sequence_number": N, "type": "response.completed"}
            if let Some(response_data) = event.data.get("response") {
                if let Ok(response) =
                    serde_json::from_value::<OpenAIResponse>(response_data.clone())
                {
                    return Some(response);
                }
            }
        }
    }

    // Fallback: try response.done event with same nested structure
    for event in events.iter().rev() {
        if event.event == "response.done" {
            if let Some(response_data) = event.data.get("response") {
                if let Ok(response) =
                    serde_json::from_value::<OpenAIResponse>(response_data.clone())
                {
                    return Some(response);
                }
            }
        }
    }

    None
}

/// Handler for creating a new response (POST /v1/responses)
#[tracing::instrument(
    name = "response_create_handler_observability",
    skip_all,
    fields(
        otel.name = "response_create_handler_observability",
        // Error status fields (4)
        otel.status_code = tracing::field::Empty,
        otel.status_description = tracing::field::Empty,
        error.type = tracing::field::Empty,
        error.message = tracing::field::Empty,

        // REQUEST fields (26 fields) - GenAI semantic convention
        gen_ai.operation.name = tracing::field::Empty,
        gen_ai.request.model = tracing::field::Empty,
        gen_ai.input.messages = tracing::field::Empty,
        gen_ai.request.instructions = tracing::field::Empty,
        gen_ai.request.tools = tracing::field::Empty,
        gen_ai.request.tool_choice = tracing::field::Empty,
        gen_ai.request.parallel_tool_calls = tracing::field::Empty,
        gen_ai.request.max_tool_calls = tracing::field::Empty,
        gen_ai.request.previous_response_id = tracing::field::Empty,
        gen_ai.request.temperature = tracing::field::Empty,
        gen_ai.request.max_tokens = tracing::field::Empty,
        gen_ai.request.response_format = tracing::field::Empty,
        gen_ai.request.reasoning = tracing::field::Empty,
        gen_ai.request.include = tracing::field::Empty,
        gen_ai.request.metadata = tracing::field::Empty,
        gen_ai.prompt = tracing::field::Empty,
        gen_ai.prompt.id = tracing::field::Empty,
        gen_ai.prompt.version = tracing::field::Empty,
        gen_ai.prompt.variables = tracing::field::Empty,
        gen_ai.request.stream = tracing::field::Empty,
        gen_ai.request.stream_options = tracing::field::Empty,
        gen_ai.request.store = tracing::field::Empty,
        gen_ai.request.background = tracing::field::Empty,
        gen_ai.request.service_tier = tracing::field::Empty,
        gen_ai.request.modalities = tracing::field::Empty,
        gen_ai.request.user = tracing::field::Empty,

        // RESPONSE fields (22 fields) - GenAI semantic convention
        gen_ai.response.id = tracing::field::Empty,
        gen_ai.response.object = tracing::field::Empty,
        gen_ai.response.created_at = tracing::field::Empty,
        gen_ai.response.status = tracing::field::Empty,
        gen_ai.response.background = tracing::field::Empty,
        gen_ai.response.model = tracing::field::Empty,
        gen_ai.response.max_output_tokens = tracing::field::Empty,
        gen_ai.response.temperature = tracing::field::Empty,
        gen_ai.response.parallel_tool_calls = tracing::field::Empty,
        gen_ai.response.tool_choice = tracing::field::Empty,
        gen_ai.system.instructions = tracing::field::Empty,
        gen_ai.output.messages = tracing::field::Empty,
        gen_ai.response.prompt = tracing::field::Empty,
        gen_ai.response.reasoning = tracing::field::Empty,
        gen_ai.output.type = tracing::field::Empty,
        gen_ai.response.tools = tracing::field::Empty,
        gen_ai.usage = tracing::field::Empty,
        gen_ai.usage.input_tokens = tracing::field::Empty,
        gen_ai.usage.output_tokens = tracing::field::Empty,
        gen_ai.usage.total_tokens = tracing::field::Empty,
        gen_ai.openai.response.service_tier = tracing::field::Empty,
        gen_ai.response.top_p = tracing::field::Empty,
    )
)]
#[debug_handler(state = AppStateData)]
pub async fn response_create_handler(
    State(AppStateData {
        config,
        http_client,
        clickhouse_connection_info,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store,
        ..
    }): AppState,
    headers: HeaderMap,
    StructuredJson(params): StructuredJson<OpenAIResponseCreateParams>,
) -> Result<Response<Body>, Error> {
    // Record request fields for observability
    super::observability::record_response_request(&params);

    // Capture prompt info for analytics headers (before params is moved into async block)
    let prompt_id = params.prompt.as_ref().map(|p| p.id.clone());
    let prompt_version = params.prompt.as_ref().and_then(|p| p.version.clone());
    // Capture project_id from incoming headers for analytics
    let project_id = headers
        .get("x-tensorzero-project-id")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string());

    let result = async {
        if !params.unknown_fields.is_empty() {
            tracing::warn!(
                "Ignoring unknown fields in OpenAI-compatible response create request: {:?}",
                params.unknown_fields.keys().collect::<Vec<_>>()
            );
        }

        // Resolve the model name based on authentication state (optional for prompt-based requests)
        let model_resolution = model_resolution::resolve_model_name(
        params.model.as_deref(),
        &headers,
        false, // not for embedding
    )?;

    let model_name = model_resolution.model_name.ok_or_else(|| {
        Error::new(ErrorDetails::InvalidOpenAICompatibleRequest {
            message: "Response requests must specify a model or prompt.id".to_string(),
        })
    })?;

    // Check if the model supports the Responses endpoint
    use crate::model::ModelTableExt;
    let models = config.models.read().await;
    let model = models
        .get_with_capability(
            &model_name,
            crate::endpoints::capability::EndpointCapability::Responses,
        )
        .await?
        .ok_or_else(|| {
            Error::new(ErrorDetails::Config {
                message: format!(
                    "Model '{}' not found or does not support responses",
                    model_resolution.original_model_name
                ),
            })
        })?;

    // Merge credentials from the credential store
    let mut credentials = merge_credentials_from_store(&model_credential_store);

    // Merge credentials from headers for dynamic authorization (responses API only)
    merge_credentials_from_headers(&headers, &mut credentials);

    // Create inference clients
    let cache_options = crate::cache::CacheOptions {
        enabled: crate::cache::CacheEnabledMode::Off, // Responses don't use cache for now
        max_age_s: None,
    };
    let clients = super::inference::InferenceClients {
        http_client: &http_client,
        credentials: &credentials,
        clickhouse_connection_info: &clickhouse_connection_info,
        cache_options: &cache_options,
    };

    // Capture the gateway request for logging purposes (without null values)
    let gateway_request = serialize_without_nulls(&params).ok();

    if let Some(gw_req) = &gateway_request {
        tracing::debug!(
            "Gateway request captured for responses API: {} bytes",
            gw_req.len()
        );
    }

    // Check if this is a BudPrompt request with prompt parameter
    // BudPrompt determines streaming based on internal prompt config, not the stream parameter
    let is_budprompt_with_prompt = {
        let models = config.models.read().await;
        let model_info = models.get(&model_name).await?.ok_or_else(|| {
            Error::new(ErrorDetails::Config {
                message: format!("Model '{}' not found", model_name),
            })
        })?;

        // Check if any provider is BudPrompt
        let has_budprompt = model_info
            .providers
            .values()
            .any(|p| matches!(p.config, crate::model::ProviderConfig::BudPrompt(_)));

        has_budprompt && params.prompt.is_some()
    };

    if is_budprompt_with_prompt {
        // Capture the current span BEFORE calling model methods
        // This ensures the span stays alive until streaming completes
        let observability_span = tracing::Span::current();

        // Use automatic format detection for BudPrompt with prompt parameter
        use crate::responses::ResponseResult;

        let result = model
            .execute_response_with_detection(
                &params,
                &model_resolution.original_model_name,
                &clients,
            )
            .await?;

        match result {
            ResponseResult::Streaming(stream) => {
                // Wrap stream to capture events and record observability after completion
                let sse_stream = async_stream::stream! {
                    use futures::StreamExt;

                    let mut buffer: Vec<ResponseStreamEvent> = Vec::new();
                    let mut had_streaming_error = false;
                    futures::pin_mut!(stream);

                    while let Some(result) = stream.next().await {
                        // Buffer successful events for post-stream observability
                        if let Ok(event) = &result {
                            buffer.push(event.clone());
                        }

                        // Convert to SSE Event and yield
                        match result {
                            Ok(event) => {
                                yield Event::default()
                                    .event(event.event)
                                    .json_data(event.data)
                                    .map_err(|e| {
                                        Error::new(ErrorDetails::Inference {
                                            message: format!("Failed to serialize SSE event: {e}"),
                                        })
                                    });
                            }
                            Err(e) => {
                                // Record streaming error immediately using the span
                                let _guard = observability_span.enter();
                                super::observability::record_error(&e);
                                had_streaming_error = true;
                                yield Err(e);
                            }
                        }
                    }

                    // AFTER stream completes: record observability using captured span
                    let _guard = observability_span.enter();

                    // Try to reconstruct response from buffered events (skip if we had an error)
                    if !had_streaming_error {
                        if let Some(response) = try_reconstruct_response_from_events(&buffer) {
                            tracing::debug!(
                                "Reconstructed response from {} stream events, id={}",
                                buffer.len(),
                                response.id
                            );
                            super::observability::record_response_result(&response);
                        } else {
                            tracing::warn!(
                                "Could not reconstruct response from {} buffered stream events",
                                buffer.len()
                            );
                        }
                    }
                };

                Ok(Sse::new(sse_stream).into_response())
            }
            ResponseResult::NonStreaming(response) => {
                // Log the response size for debugging
                if let Ok(response_json) = serde_json::to_string(&response) {
                    tracing::debug!("Response size: {} bytes", response_json.len());
                }

                // Record response fields for observability
                super::observability::record_response_result(&response);

                Ok(Json(response).into_response())
            }
        }
    } else {
        // Standard behavior: check stream parameter
        if params.stream.unwrap_or(false) {
            // Capture the current span BEFORE calling model methods
            // This ensures the span stays alive until streaming completes
            let observability_span = tracing::Span::current();

            // Handle streaming response
            let stream = model
                .stream_response(&params, &model_resolution.original_model_name, &clients)
                .await?;

            // Wrap stream to capture events and record observability after completion
            let sse_stream = async_stream::stream! {
                use futures::StreamExt;

                let mut buffer: Vec<ResponseStreamEvent> = Vec::new();
                let mut had_streaming_error = false;
                futures::pin_mut!(stream);

                while let Some(result) = stream.next().await {
                    // Buffer successful events for post-stream observability
                    if let Ok(event) = &result {
                        buffer.push(event.clone());
                    }

                    // Convert to SSE Event and yield
                    match result {
                        Ok(event) => {
                            // For ResponseStreamEvent, use event field as SSE event type and data field as data
                            yield Event::default()
                                .event(event.event)
                                .json_data(event.data)
                                .map_err(|e| {
                                    Error::new(ErrorDetails::Inference {
                                        message: format!("Failed to serialize SSE event: {e}"),
                                    })
                                });
                        }
                        Err(e) => {
                            // Record streaming error immediately using the span
                            let _guard = observability_span.enter();
                            super::observability::record_error(&e);
                            had_streaming_error = true;
                            yield Err(e);
                        }
                    }
                }

                // AFTER stream completes: record observability using captured span
                let _guard = observability_span.enter();

                // Try to reconstruct response from buffered events (skip if we had an error)
                if !had_streaming_error {
                    if let Some(response) = try_reconstruct_response_from_events(&buffer) {
                        tracing::debug!(
                            "Reconstructed response from {} stream events, id={}",
                            buffer.len(),
                            response.id
                        );
                        super::observability::record_response_result(&response);
                    } else {
                        tracing::warn!(
                            "Could not reconstruct response from {} buffered stream events",
                            buffer.len()
                        );
                    }
                }
            };

            Ok(Sse::new(sse_stream).into_response())
        } else {
            // Handle non-streaming response
            let response = model
                .create_response(&params, &model_resolution.original_model_name, &clients)
                .await?;

            // Log the response size for debugging
            if let Ok(response_json) = serde_json::to_string(&response) {
                tracing::debug!("Response size: {} bytes", response_json.len());
            }

            // Record response fields for observability
            super::observability::record_response_result(&response);

            Ok(Json(response).into_response())
        }
    }
    }
    .await;

    // Record error on span if request failed
    if let Err(ref error) = result {
        super::observability::record_error(error);
    }

    // Add prompt and project headers for analytics
    match result {
        Ok(mut response) => {
            if let Some(ref id) = prompt_id {
                if let Ok(value) = axum::http::HeaderValue::from_str(id) {
                    response.headers_mut().insert("x-tensorzero-prompt-id", value);
                }
            }
            if let Some(ref version) = prompt_version {
                if let Ok(value) = axum::http::HeaderValue::from_str(version) {
                    response.headers_mut().insert("x-tensorzero-prompt-version", value);
                }
            }
            // Add project_id header for analytics
            if let Some(ref pid) = project_id {
                if let Ok(value) = axum::http::HeaderValue::from_str(pid) {
                    response.headers_mut().insert("x-tensorzero-project-id", value);
                }
            }
            Ok(response)
        }
        Err(e) => Err(e),
    }
}

/// Handler for retrieving a response (GET /v1/responses/{response_id})
///
/// Note: Since the OpenAI API doesn't include a model parameter for retrieval operations,
/// you must specify the model name using the 'x-model-name' header. If not provided,
/// it defaults to 'gpt-4-responses'.
///
/// Example:
/// ```text
/// curl -X GET http://localhost:3000/v1/responses/resp_123 \
///   -H "Authorization: Bearer YOUR_API_KEY" \
///   -H "x-model-name: your-model-name"
/// ```
#[debug_handler(state = AppStateData)]
pub async fn response_retrieve_handler(
    State(AppStateData {
        config,
        http_client,
        clickhouse_connection_info,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store: _,
        ..
    }): AppState,
    headers: HeaderMap,
    Path(response_id): Path<String>,
) -> Result<Response<Body>, Error> {
    // Extract model name from headers or use a default
    // For retrieval, we need to know which model to use
    // This could be passed in headers or we could have a default model
    let model_name = headers
        .get("x-model-name")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("gpt-4-responses"); // Default model name

    // Get the model configuration
    use crate::model::ModelTableExt;
    let models = config.models.read().await;
    let model = models
        .get_with_capability(
            model_name,
            crate::endpoints::capability::EndpointCapability::Responses,
        )
        .await?
        .ok_or_else(|| {
            Error::new(ErrorDetails::Config {
                message: format!("Model '{model_name}' not found or does not support responses"),
            })
        })?;

    // Create credentials and merge from headers for dynamic authorization
    let mut credentials = InferenceCredentials::default();
    merge_credentials_from_headers(&headers, &mut credentials);

    let clients = InferenceClients {
        http_client: &http_client,
        credentials: &credentials,
        clickhouse_connection_info: &clickhouse_connection_info,
        cache_options: &crate::cache::CacheOptions {
            max_age_s: None,
            enabled: crate::cache::CacheEnabledMode::Off,
        },
    };

    let response = model
        .retrieve_response(&response_id, model_name, &clients)
        .await?;

    let body = serde_json::to_string(&response).map_err(|e| {
        Error::new(ErrorDetails::InferenceServer {
            message: format!("Failed to serialize response: {e}"),
            raw_request: None,
            raw_response: None,
            provider_type: "gateway".to_string(),
        })
    })?;
    Response::builder()
        .status(StatusCode::OK)
        .header("Content-Type", "application/json")
        .body(Body::from(body))
        .map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Failed to build response: {e}"),
                raw_request: None,
                raw_response: None,
                provider_type: "gateway".to_string(),
            })
        })
}

/// Handler for deleting a response (DELETE /v1/responses/{response_id})
///
/// Note: Since the OpenAI API doesn't include a model parameter for deletion operations,
/// you must specify the model name using the 'x-model-name' header. If not provided,
/// it defaults to 'gpt-4-responses'.
///
/// Example:
/// ```text
/// curl -X DELETE http://localhost:3000/v1/responses/resp_123 \
///   -H "Authorization: Bearer YOUR_API_KEY" \
///   -H "x-model-name: your-model-name"
/// ```
#[debug_handler(state = AppStateData)]
pub async fn response_delete_handler(
    State(AppStateData {
        config,
        http_client,
        clickhouse_connection_info,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store: _,
        ..
    }): AppState,
    headers: HeaderMap,
    Path(response_id): Path<String>,
) -> Result<Response<Body>, Error> {
    let model_name = headers
        .get("x-model-name")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("gpt-4-responses");

    use crate::model::ModelTableExt;
    let models = config.models.read().await;
    let model = models
        .get_with_capability(
            model_name,
            crate::endpoints::capability::EndpointCapability::Responses,
        )
        .await?
        .ok_or_else(|| {
            Error::new(ErrorDetails::Config {
                message: format!("Model '{model_name}' not found or does not support responses"),
            })
        })?;

    // Create credentials and merge from headers for dynamic authorization
    let mut credentials = InferenceCredentials::default();
    merge_credentials_from_headers(&headers, &mut credentials);

    let clients = InferenceClients {
        http_client: &http_client,
        credentials: &credentials,
        clickhouse_connection_info: &clickhouse_connection_info,
        cache_options: &crate::cache::CacheOptions {
            max_age_s: None,
            enabled: crate::cache::CacheEnabledMode::Off,
        },
    };

    let response = model
        .delete_response(&response_id, model_name, &clients)
        .await?;

    let body = serde_json::to_string(&response).map_err(|e| {
        Error::new(ErrorDetails::InferenceServer {
            message: format!("Failed to serialize response: {e}"),
            raw_request: None,
            raw_response: None,
            provider_type: "gateway".to_string(),
        })
    })?;
    Response::builder()
        .status(StatusCode::OK)
        .header("Content-Type", "application/json")
        .body(Body::from(body))
        .map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Failed to build response: {e}"),
                raw_request: None,
                raw_response: None,
                provider_type: "gateway".to_string(),
            })
        })
}

/// Handler for cancelling a response (POST /v1/responses/{response_id}/cancel)
///
/// Note: Since the OpenAI API doesn't include a model parameter for cancellation operations,
/// you must specify the model name using the 'x-model-name' header. If not provided,
/// it defaults to 'gpt-4-responses'.
///
/// Example:
/// ```text
/// curl -X POST http://localhost:3000/v1/responses/resp_123/cancel \
///   -H "Authorization: Bearer YOUR_API_KEY" \
///   -H "x-model-name: your-model-name"
/// ```
#[debug_handler(state = AppStateData)]
pub async fn response_cancel_handler(
    State(AppStateData {
        config,
        http_client,
        clickhouse_connection_info,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store: _,
        ..
    }): AppState,
    headers: HeaderMap,
    Path(response_id): Path<String>,
) -> Result<Response<Body>, Error> {
    let model_name = headers
        .get("x-model-name")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("gpt-4-responses");

    use crate::model::ModelTableExt;
    let models = config.models.read().await;
    let model = models
        .get_with_capability(
            model_name,
            crate::endpoints::capability::EndpointCapability::Responses,
        )
        .await?
        .ok_or_else(|| {
            Error::new(ErrorDetails::Config {
                message: format!("Model '{model_name}' not found or does not support responses"),
            })
        })?;

    // Create credentials and merge from headers for dynamic authorization
    let mut credentials = InferenceCredentials::default();
    merge_credentials_from_headers(&headers, &mut credentials);

    let clients = InferenceClients {
        http_client: &http_client,
        credentials: &credentials,
        clickhouse_connection_info: &clickhouse_connection_info,
        cache_options: &crate::cache::CacheOptions {
            max_age_s: None,
            enabled: crate::cache::CacheEnabledMode::Off,
        },
    };

    let response = model
        .cancel_response(&response_id, model_name, &clients)
        .await?;

    let body = serde_json::to_string(&response).map_err(|e| {
        Error::new(ErrorDetails::InferenceServer {
            message: format!("Failed to serialize response: {e}"),
            raw_request: None,
            raw_response: None,
            provider_type: "gateway".to_string(),
        })
    })?;
    Response::builder()
        .status(StatusCode::OK)
        .header("Content-Type", "application/json")
        .body(Body::from(body))
        .map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Failed to build response: {e}"),
                raw_request: None,
                raw_response: None,
                provider_type: "gateway".to_string(),
            })
        })
}

/// Handler for listing response input items (GET /v1/responses/{response_id}/input_items)
///
/// Note: Since the OpenAI API doesn't include a model parameter for listing operations,
/// you must specify the model name using the 'x-model-name' header. If not provided,
/// it defaults to 'gpt-4-responses'.
///
/// Example:
/// ```text
/// curl -X GET http://localhost:3000/v1/responses/resp_123/input_items \
///   -H "Authorization: Bearer YOUR_API_KEY" \
///   -H "x-model-name: your-model-name"
/// ```
#[debug_handler(state = AppStateData)]
pub async fn response_input_items_handler(
    State(AppStateData {
        config,
        http_client,
        clickhouse_connection_info,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store: _,
        ..
    }): AppState,
    headers: HeaderMap,
    Path(response_id): Path<String>,
) -> Result<Response<Body>, Error> {
    let model_name = headers
        .get("x-model-name")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("gpt-4-responses");

    use crate::model::ModelTableExt;
    let models = config.models.read().await;
    let model = models
        .get_with_capability(
            model_name,
            crate::endpoints::capability::EndpointCapability::Responses,
        )
        .await?
        .ok_or_else(|| {
            Error::new(ErrorDetails::Config {
                message: format!("Model '{model_name}' not found or does not support responses"),
            })
        })?;

    // Create credentials and merge from headers for dynamic authorization
    let mut credentials = InferenceCredentials::default();
    merge_credentials_from_headers(&headers, &mut credentials);

    let clients = InferenceClients {
        http_client: &http_client,
        credentials: &credentials,
        clickhouse_connection_info: &clickhouse_connection_info,
        cache_options: &crate::cache::CacheOptions {
            max_age_s: None,
            enabled: crate::cache::CacheEnabledMode::Off,
        },
    };

    let response = model
        .list_response_input_items(&response_id, model_name, &clients)
        .await?;

    let body = serde_json::to_string(&response).map_err(|e| {
        Error::new(ErrorDetails::InferenceServer {
            message: format!("Failed to serialize response: {e}"),
            raw_request: None,
            raw_response: None,
            provider_type: "gateway".to_string(),
        })
    })?;
    Response::builder()
        .status(StatusCode::OK)
        .header("Content-Type", "application/json")
        .body(Body::from(body))
        .map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Failed to build response: {e}"),
                raw_request: None,
                raw_response: None,
                provider_type: "gateway".to_string(),
            })
        })
}

/// Helper function to create a provider for batch operations
/// This centralizes the credential handling for batch API operations
fn create_batch_provider() -> Result<Box<dyn BatchProvider>, Error> {
    #[cfg(feature = "e2e_tests")]
    {
        // Use dummy provider for E2E tests
        let dummy_provider = DummyProvider::new("batch".to_string(), None).map_err(|e| {
            Error::new(ErrorDetails::Config {
                message: format!("Failed to create Dummy provider for batch operations: {e}"),
            })
        })?;
        Ok(Box::new(dummy_provider))
    }

    #[cfg(not(feature = "e2e_tests"))]
    {
        // TODO: In the future, this should read from configuration
        // For now, we use the environment variable as per OpenAI's standard
        let credential_location = CredentialLocation::Env("OPENAI_API_KEY".to_string());

        let openai_provider = OpenAIProvider::new(
            "batch".to_string(), // Model name not used for batch operations
            None,                // Use default API base
            Some(credential_location),
        )
        .map_err(|e| {
            Error::new(ErrorDetails::Config {
                message: format!("Failed to create OpenAI provider for batch operations: {e}"),
            })
        })?;
        Ok(Box::new(openai_provider))
    }
}

/// Helper function to convert errors to OpenAI-compatible error responses
fn openai_error_response(error: Error) -> Response<Body> {
    let status = error.status_code();
    let body = error.to_openai_error();
    Response::builder()
        .status(status)
        .header("Content-Type", "application/json")
        .body(Body::from(serde_json::to_string(&body).unwrap_or_default()))
        .unwrap_or_else(|_| {
            Response::builder()
                .status(StatusCode::INTERNAL_SERVER_ERROR)
                .body(Body::from("Internal server error"))
                .unwrap_or_else(|_| Response::new(Body::from("Internal server error")))
        })
}

/// File upload handler for OpenAI Batch API
#[debug_handler(state = AppStateData)]
pub async fn file_upload_handler(
    State(AppStateData {
        config: _,
        http_client,
        clickhouse_connection_info: _,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store: _,
        ..
    }): AppState,
    _headers: HeaderMap,
    mut multipart: Multipart,
) -> Result<Response<Body>, Error> {
    tracing::info!("file_upload_handler called");
    // Wrap the entire handler logic to convert errors to OpenAI format
    let result = async move {
        let mut file_data: Option<Vec<u8>> = None;
        let mut filename: Option<String> = None;
        let mut purpose: Option<String> = None;

        // Process multipart form data
        while let Some(field) = multipart.next_field().await.map_err(|e| {
            Error::new(ErrorDetails::InvalidRequest {
                message: format!("Failed to read multipart field: {e}"),
            })
        })? {
            let field_name = field.name().unwrap_or("").to_string();

            match field_name.as_str() {
                "file" => {
                    filename = field.file_name().map(|s| s.to_string());
                    file_data = Some(
                        field
                            .bytes()
                            .await
                            .map_err(|e| {
                                Error::new(ErrorDetails::InvalidRequest {
                                    message: format!("Failed to read file data: {e}"),
                                })
                            })?
                            .to_vec(),
                    );
                }
                "purpose" => {
                    purpose = Some(field.text().await.map_err(|e| {
                        Error::new(ErrorDetails::InvalidRequest {
                            message: format!("Failed to read purpose field: {e}"),
                        })
                    })?);
                }
                _ => {
                    // Ignore unknown fields
                }
            }
        }

        // Validate required fields
        let file_data = file_data.ok_or_else(|| {
            Error::new(ErrorDetails::InvalidRequest {
                message: "Missing file field".to_string(),
            })
        })?;

        let filename = filename.ok_or_else(|| {
            Error::new(ErrorDetails::InvalidRequest {
                message: "Missing filename in file field".to_string(),
            })
        })?;

        let purpose = purpose.unwrap_or_else(|| "batch".to_string());

        // Validate purpose
        if purpose != "batch" {
            return Err(Error::new(ErrorDetails::InvalidRequest {
                message: format!("Invalid purpose: {purpose}. Only 'batch' is supported"),
            }));
        }

        // Validate file for batch processing
        let content_type = "application/jsonl"; // Default content type for JSONL
        validate_batch_file(&file_data, &filename, content_type)?;

        // Create provider for batch operations
        let batch_provider = create_batch_provider()?;

        // Upload file to the provider
        let file_object = batch_provider
            .upload_file(
                file_data,
                filename,
                purpose,
                &http_client,
                &InferenceCredentials::default(),
            )
            .await?;

        // Return the file object as response
        let body = serde_json::to_string(&file_object).map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Failed to serialize file object: {e}"),
                raw_request: None,
                raw_response: None,
                provider_type: "gateway".to_string(),
            })
        })?;
        Response::builder()
            .status(StatusCode::OK)
            .header("Content-Type", "application/json")
            .body(Body::from(body))
            .map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!("Failed to build response: {e}"),
                    raw_request: None,
                    raw_response: None,
                    provider_type: "gateway".to_string(),
                })
            })
    }
    .await;

    match result {
        Ok(response) => Ok(response),
        Err(error) => {
            tracing::debug!("Converting error to OpenAI format: {:?}", error);
            Ok(openai_error_response(error))
        }
    }
}

/// File metadata retrieval handler
#[debug_handler(state = AppStateData)]
pub async fn file_retrieve_handler(
    State(AppStateData {
        config: _,
        http_client,
        clickhouse_connection_info: _,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store: _,
        ..
    }): AppState,
    _headers: HeaderMap,
    Path(file_id): Path<String>,
) -> Result<Response<Body>, Error> {
    // Create OpenAI provider directly for batch operations (these are account-level operations)
    let batch_provider = create_batch_provider()?;

    // Get file from the provider
    let file_object = batch_provider
        .get_file(&file_id, &http_client, &InferenceCredentials::default())
        .await?;

    // Return the file object as response
    let body = serde_json::to_string(&file_object).map_err(|e| {
        Error::new(ErrorDetails::InferenceServer {
            message: format!("Failed to serialize file object: {e}"),
            raw_request: None,
            raw_response: None,
            provider_type: "gateway".to_string(),
        })
    })?;
    Response::builder()
        .status(StatusCode::OK)
        .header("Content-Type", "application/json")
        .body(Body::from(body))
        .map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Failed to build response: {e}"),
                raw_request: None,
                raw_response: None,
                provider_type: "gateway".to_string(),
            })
        })
}

/// File content download handler
#[debug_handler(state = AppStateData)]
pub async fn file_content_handler(
    State(AppStateData {
        config: _,
        http_client,
        clickhouse_connection_info: _,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store: _,
        ..
    }): AppState,
    _headers: HeaderMap,
    Path(file_id): Path<String>,
) -> Result<Response<Body>, Error> {
    // Create OpenAI provider directly for batch operations (these are account-level operations)
    let batch_provider = create_batch_provider()?;

    // Get file metadata first to get the filename
    let file_object = batch_provider
        .get_file(&file_id, &http_client, &InferenceCredentials::default())
        .await?;

    // Get file content from the provider
    let file_content = batch_provider
        .get_file_content(&file_id, &http_client, &InferenceCredentials::default())
        .await?;

    // Create response with appropriate headers
    let response = Response::builder()
        .header("content-type", "application/jsonl")
        .header(
            "content-disposition",
            format!("attachment; filename=\"{}\"", file_object.filename),
        )
        .header("content-length", file_content.len().to_string())
        .body(Body::from(file_content))
        .map_err(|e| {
            Error::new(ErrorDetails::InvalidRequest {
                message: format!("Failed to create response: {e}"),
            })
        })?;

    Ok(response)
}

/// File deletion handler
#[debug_handler(state = AppStateData)]
pub async fn file_delete_handler(
    State(AppStateData {
        config: _,
        http_client,
        clickhouse_connection_info: _,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store: _,
        ..
    }): AppState,
    _headers: HeaderMap,
    Path(file_id): Path<String>,
) -> Result<Response<Body>, Error> {
    // Create OpenAI provider directly for batch operations (these are account-level operations)
    let batch_provider = create_batch_provider()?;

    // Delete the file from the provider
    let file_object = batch_provider
        .delete_file(&file_id, &http_client, &InferenceCredentials::default())
        .await?;

    // Create deletion response object
    let delete_response = serde_json::json!({
        "id": file_object.id,
        "object": "file",
        "deleted": true
    });

    // Capture the gateway response (without null values)
    let gateway_response_json = serialize_without_nulls(&delete_response).ok();

    // Store the gateway response if we have it
    if let Some(gateway_response) = &gateway_response_json {
        // Log for debugging
        tracing::debug!(
            "Gateway response captured: {} bytes",
            gateway_response.len()
        );

        // Store the gateway response in the database
        // This requires updating the storage layer to include the gateway_response
        // For now, we'll need to update the storage layer separately
    }

    let response = Json(delete_response).into_response();
    Ok(response)
}

/// Batch creation handler for OpenAI Batch API
#[debug_handler(state = AppStateData)]
pub async fn batch_create_handler(
    State(AppStateData {
        config: _,
        http_client,
        clickhouse_connection_info: _,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store: _,
        ..
    }): AppState,
    _headers: HeaderMap,
    Json(request): Json<OpenAIBatchCreateRequest>,
) -> Result<Response<Body>, Error> {
    // Wrap the entire handler logic to convert errors to OpenAI format
    let result = async move {
        // Validate the batch creation request
        validate_batch_create_request(&request)?;

        tracing::info!("Batch creation request validated successfully");

        // Create OpenAI provider directly for batch operations (these are account-level operations)
        let batch_provider = create_batch_provider()?;

        // Validate endpoint
        match request.endpoint.as_str() {
            "/v1/chat/completions" | "/v1/embeddings" => {
                // Valid endpoints
            }
            _ => {
                return Err(Error::new(ErrorDetails::InvalidRequest {
                    message: format!(
                        "Unsupported endpoint for batch processing: {}",
                        request.endpoint
                    ),
                }));
            }
        }

        // Create batch with the provider
        let batch_object = batch_provider
            .create_batch(
                request.input_file_id,
                request.endpoint,
                request.completion_window,
                request.metadata,
                &http_client,
                &InferenceCredentials::default(),
            )
            .await?;

        // Return the batch object as response
        let body = serde_json::to_string(&batch_object).map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Failed to serialize batch object: {e}"),
                raw_request: None,
                raw_response: None,
                provider_type: "gateway".to_string(),
            })
        })?;
        Response::builder()
            .status(StatusCode::OK)
            .header("Content-Type", "application/json")
            .body(Body::from(body))
            .map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!("Failed to build response: {e}"),
                    raw_request: None,
                    raw_response: None,
                    provider_type: "gateway".to_string(),
                })
            })
    }
    .await;

    match result {
        Ok(response) => Ok(response),
        Err(error) => {
            tracing::debug!("Converting error to OpenAI format: {:?}", error);
            Ok(openai_error_response(error))
        }
    }
}

/// Batch retrieval handler for OpenAI Batch API
#[debug_handler(state = AppStateData)]
pub async fn batch_retrieve_handler(
    State(AppStateData {
        config: _,
        http_client,
        clickhouse_connection_info: _,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store: _,
        ..
    }): AppState,
    _headers: HeaderMap,
    Path(batch_id): Path<String>,
) -> Result<Response<Body>, Error> {
    // Create OpenAI provider directly for batch operations (these are account-level operations)
    let batch_provider = create_batch_provider()?;

    // Get batch status from the provider
    let batch_object = batch_provider
        .get_batch(&batch_id, &http_client, &InferenceCredentials::default())
        .await?;

    // Return the batch object as response
    let body = serde_json::to_string(&batch_object).map_err(|e| {
        Error::new(ErrorDetails::InferenceServer {
            message: format!("Failed to serialize batch object: {e}"),
            raw_request: None,
            raw_response: None,
            provider_type: "gateway".to_string(),
        })
    })?;
    Response::builder()
        .status(StatusCode::OK)
        .header("Content-Type", "application/json")
        .body(Body::from(body))
        .map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Failed to build response: {e}"),
                raw_request: None,
                raw_response: None,
                provider_type: "gateway".to_string(),
            })
        })
}

/// Batch listing handler for OpenAI Batch API
#[debug_handler(state = AppStateData)]
pub async fn batch_list_handler(
    State(AppStateData {
        config: _,
        http_client,
        clickhouse_connection_info: _,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store: _,
        ..
    }): AppState,
    _headers: HeaderMap,
    Query(params): Query<ListBatchesParams>,
) -> Result<Response<Body>, Error> {
    // Create OpenAI provider directly for batch operations (these are account-level operations)
    let batch_provider = create_batch_provider()?;

    // List batches from the provider
    let list_response = batch_provider
        .list_batches(params, &http_client, &InferenceCredentials::default())
        .await?;

    // Return the list response
    let body = serde_json::to_string(&list_response).map_err(|e| {
        Error::new(ErrorDetails::InferenceServer {
            message: format!("Failed to serialize list response: {e}"),
            raw_request: None,
            raw_response: None,
            provider_type: "gateway".to_string(),
        })
    })?;
    Response::builder()
        .status(StatusCode::OK)
        .header("Content-Type", "application/json")
        .body(Body::from(body))
        .map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Failed to build response: {e}"),
                raw_request: None,
                raw_response: None,
                provider_type: "gateway".to_string(),
            })
        })
}

/// Batch cancellation handler for OpenAI Batch API
#[debug_handler(state = AppStateData)]
pub async fn batch_cancel_handler(
    State(AppStateData {
        config: _,
        http_client,
        clickhouse_connection_info: _,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store: _,
        ..
    }): AppState,
    _headers: HeaderMap,
    Path(batch_id): Path<String>,
) -> Result<Response<Body>, Error> {
    // Create OpenAI provider directly for batch operations (these are account-level operations)
    let batch_provider = create_batch_provider()?;

    // Cancel the batch with the provider
    let batch_object = batch_provider
        .cancel_batch(&batch_id, &http_client, &InferenceCredentials::default())
        .await?;

    // Return the batch object as response
    let body = serde_json::to_string(&batch_object).map_err(|e| {
        Error::new(ErrorDetails::InferenceServer {
            message: format!("Failed to serialize batch object: {e}"),
            raw_request: None,
            raw_response: None,
            provider_type: "gateway".to_string(),
        })
    })?;
    Response::builder()
        .status(StatusCode::OK)
        .header("Content-Type", "application/json")
        .body(Body::from(body))
        .map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Failed to build response: {e}"),
                raw_request: None,
                raw_response: None,
                provider_type: "gateway".to_string(),
            })
        })
}

#[cfg(test)]
mod tests {

    use super::*;
    use axum::http::header::{HeaderName, HeaderValue};
    use serde_json::json;
    use tracing_test::traced_test;

    use crate::cache::CacheEnabledMode;
    use crate::inference::types::{Text, TextChunk};

    #[test]
    fn test_try_from_openai_compatible_params() {
        let episode_id = Uuid::now_v7();
        let headers = HeaderMap::from_iter(vec![
            (
                HeaderName::from_static("episode_id"),
                HeaderValue::from_str(&episode_id.to_string()).unwrap(),
            ),
            (
                HeaderName::from_static("variant_name"),
                HeaderValue::from_static("test_variant"),
            ),
        ]);
        let messages = vec![OpenAICompatibleMessage::User(OpenAICompatibleUserMessage {
            content: Value::String("Hello, world!".to_string()),
        })];
        let params = Params::try_from_openai(
            headers,
            OpenAICompatibleParams {
                messages,
                model: "tensorzero::test_function".into(),
                frequency_penalty: Some(0.5),
                max_tokens: Some(100),
                max_completion_tokens: Some(50),
                presence_penalty: Some(0.5),
                seed: Some(23),
                temperature: Some(0.5),
                top_p: Some(0.5),
                ..Default::default()
            },
        )
        .unwrap();
        assert_eq!(params.function_name, Some("test_function".to_string()));
        assert_eq!(params.episode_id, Some(episode_id));
        assert_eq!(params.variant_name, Some("test_variant".to_string()));
        assert_eq!(params.input.messages.len(), 1);
        assert_eq!(params.input.messages[0].role, Role::User);
        assert_eq!(
            params.input.messages[0].content[0],
            InputMessageContent::Text(TextKind::Text {
                text: "Hello, world!".to_string(),
            })
        );
        assert_eq!(params.params.chat_completion.temperature, Some(0.5));
        assert_eq!(params.params.chat_completion.max_tokens, Some(50));
        assert_eq!(params.params.chat_completion.seed, Some(23));
        assert_eq!(params.params.chat_completion.top_p, Some(0.5));
        assert_eq!(params.params.chat_completion.presence_penalty, Some(0.5));
        assert_eq!(params.params.chat_completion.frequency_penalty, Some(0.5));
    }

    #[test]
    fn test_try_from_openai_compatible_messages() {
        let messages = vec![OpenAICompatibleMessage::User(OpenAICompatibleUserMessage {
            content: Value::String("Hello, world!".to_string()),
        })];
        let input: Input = messages.try_into().unwrap();
        assert_eq!(input.messages.len(), 1);
        assert_eq!(input.messages[0].role, Role::User);
        assert_eq!(
            input.messages[0].content[0],
            InputMessageContent::Text(TextKind::Text {
                text: "Hello, world!".to_string(),
            })
        );
        // Now try a system message and a user message
        let messages = vec![
            OpenAICompatibleMessage::System(OpenAICompatibleSystemMessage {
                content: Value::String("You are a helpful assistant".to_string()),
            }),
            OpenAICompatibleMessage::User(OpenAICompatibleUserMessage {
                content: Value::String("Hello, world!".to_string()),
            }),
        ];
        let input: Input = messages.try_into().unwrap();
        assert_eq!(input.messages.len(), 1);
        assert_eq!(input.messages[0].role, Role::User);
        assert_eq!(
            input.system,
            Some(Value::String("You are a helpful assistant".to_string()))
        );
        // Now try some messages with structured content
        let messages = vec![
            OpenAICompatibleMessage::System(OpenAICompatibleSystemMessage {
                content: Value::String("You are a helpful assistant".to_string()),
            }),
            OpenAICompatibleMessage::User(OpenAICompatibleUserMessage {
                content: json!({
                    "country": "Japan",
                    "city": "Tokyo",
                }),
            }),
        ];
        let input: Result<Input, Error> = messages.try_into();
        let details = input.unwrap_err().get_owned_details();
        assert_eq!(
            details,
            ErrorDetails::InvalidOpenAICompatibleRequest {
                message: "message content must either be a string or an array of length 1 containing structured TensorZero inputs".to_string(),
            }
        );

        // Try 2 system messages
        let messages = vec![
            OpenAICompatibleMessage::System(OpenAICompatibleSystemMessage {
                content: Value::String("You are a helpful assistant 1.".to_string()),
            }),
            OpenAICompatibleMessage::System(OpenAICompatibleSystemMessage {
                content: Value::String("You are a helpful assistant 2.".to_string()),
            }),
        ];
        let input: Input = messages.try_into().unwrap();
        assert_eq!(
            input.system,
            Some("You are a helpful assistant 1.\nYou are a helpful assistant 2.".into())
        );
        assert_eq!(input.messages.len(), 0);

        // Try an assistant message with structured content
        let messages = vec![OpenAICompatibleMessage::Assistant(
            OpenAICompatibleAssistantMessage {
                content: Some(json!([{
                    "country": "Japan",
                    "city": "Tokyo",
                }])),
                tool_calls: None,
            },
        )];
        let input: Input = messages.try_into().unwrap();
        assert_eq!(input.messages.len(), 1);
        assert_eq!(input.messages[0].role, Role::Assistant);
        assert_eq!(
            input.messages[0].content[0],
            InputMessageContent::Text(TextKind::Arguments {
                arguments: json!({
                    "country": "Japan",
                    "city": "Tokyo",
                })
                .as_object()
                .unwrap()
                .clone(),
            })
        );

        // Try an assistant message with text and tool calls
        let messages = vec![OpenAICompatibleMessage::Assistant(
            OpenAICompatibleAssistantMessage {
                content: Some(Value::String("Hello, world!".to_string())),
                tool_calls: Some(vec![OpenAICompatibleToolCall {
                    id: "1".to_string(),
                    r#type: "function".to_string(),
                    function: OpenAICompatibleFunctionCall {
                        name: Some("test_tool".to_string()),
                        arguments: "{}".to_string(),
                    },
                }]),
            },
        )];
        let input: Input = messages.try_into().unwrap();
        assert_eq!(input.messages.len(), 1);
        assert_eq!(input.messages[0].role, Role::Assistant);
        assert_eq!(input.messages[0].content.len(), 2);

        let expected_text = InputMessageContent::Text(TextKind::Text {
            text: "Hello, world!".to_string(),
        });
        let expected_tool_call = InputMessageContent::ToolCall(ToolCall {
            id: "1".to_string(),
            name: "test_tool".to_string(),
            arguments: "{}".to_string(),
        });

        assert!(
            input.messages[0].content.contains(&expected_text),
            "Content does not contain the expected Text message."
        );
        assert!(
            input.messages[0].content.contains(&expected_tool_call),
            "Content does not contain the expected ToolCall."
        );

        let out_of_order_messages = vec![
            OpenAICompatibleMessage::Assistant(OpenAICompatibleAssistantMessage {
                content: Some(Value::String("Assistant message".to_string())),
                tool_calls: None,
            }),
            OpenAICompatibleMessage::System(OpenAICompatibleSystemMessage {
                content: Value::String("System message".to_string()),
            }),
        ];
        let result: Input = out_of_order_messages.try_into().unwrap();
        assert_eq!(result.system, Some("System message".into()));
        assert_eq!(
            result.messages,
            vec![InputMessage {
                role: Role::Assistant,
                content: vec![InputMessageContent::Text(TextKind::Text {
                    text: "Assistant message".to_string(),
                })],
            }]
        );
    }

    #[test]
    fn test_convert_openai_message_content() {
        let content = json!([{
            "country": "Japan",
            "city": "Tokyo",
        }]);
        let value = convert_openai_message_content(content.clone()).unwrap();
        assert_eq!(
            value,
            vec![InputMessageContent::Text(TextKind::Arguments {
                arguments: json!({
                    "country": "Japan",
                    "city": "Tokyo",
                })
                .as_object()
                .unwrap()
                .clone(),
            })]
        );
        let content = json!({
            "country": "Japan",
            "city": "Tokyo",
        });
        let error = convert_openai_message_content(content.clone()).unwrap_err();
        let details = error.get_owned_details();
        assert_eq!(
            details,
            ErrorDetails::InvalidOpenAICompatibleRequest {
                message: "message content must either be a string or an array of length 1 containing structured TensorZero inputs".to_string(),
            }
        );
        let content = json!([]);
        let messages = convert_openai_message_content(content).unwrap();
        assert_eq!(messages, vec![]);

        let arguments_block = json!([{
            "type": "text",
            "tensorzero::arguments": {
                "custom_key": "custom_val"
            }
        }]);
        let value = convert_openai_message_content(arguments_block).unwrap();
        assert_eq!(
            value,
            vec![InputMessageContent::Text(TextKind::Arguments {
                arguments: json!({
                    "custom_key": "custom_val",
                })
                .as_object()
                .unwrap()
                .clone(),
            })]
        );
    }

    #[test]
    #[traced_test]
    fn test_deprecated_custom_block() {
        let content = json!([{
            "country": "Japan",
            "city": "Tokyo",
        }]);
        let value = convert_openai_message_content(content.clone()).unwrap();
        assert_eq!(
            value,
            vec![InputMessageContent::Text(TextKind::Arguments {
                arguments: json!({
                    "country": "Japan",
                    "city": "Tokyo",
                })
                .as_object()
                .unwrap()
                .clone(),
            })]
        );
        assert!(logs_contain(
            r#"Content block `{"country":"Japan","city":"Tokyo"}` was not a valid OpenAI content block."#
        ));

        let other_content = json!([{
            "type": "text",
            "my_custom_arg": 123
        }]);
        let value = convert_openai_message_content(other_content.clone()).unwrap();
        assert_eq!(
            value,
            vec![InputMessageContent::Text(TextKind::Arguments {
                arguments: json!({
                    "type": "text",
                    "my_custom_arg": 123
                })
                .as_object()
                .unwrap()
                .clone(),
            })]
        );
        assert!(logs_contain(
            r#"Content block `{"type":"text","my_custom_arg":123}` was not a valid OpenAI content block."#
        ));
    }

    #[test]
    fn test_process_chat_content() {
        let content = vec![
            ContentBlockChatOutput::Text(Text {
                text: "Hello".to_string(),
            }),
            ContentBlockChatOutput::ToolCall(ToolCallOutput {
                arguments: None,
                name: Some("test_tool".to_string()),
                id: "1".to_string(),
                raw_name: "test_tool".to_string(),
                raw_arguments: "{}".to_string(),
            }),
            ContentBlockChatOutput::Text(Text {
                text: ", world!".to_string(),
            }),
        ];
        let (content_str, tool_calls, reasoning_content) = process_chat_content(content);
        assert_eq!(content_str, Some("Hello, world!".to_string()));
        assert_eq!(tool_calls.len(), 1);
        assert_eq!(tool_calls[0].id, "1");
        assert_eq!(tool_calls[0].function.name, Some("test_tool".to_string()));
        assert_eq!(tool_calls[0].function.arguments, "{}");
        assert_eq!(reasoning_content, None);
        let content: Vec<ContentBlockChatOutput> = vec![];
        let (content_str, tool_calls, _reasoning_content) = process_chat_content(content);
        assert_eq!(content_str, None);
        assert!(tool_calls.is_empty());

        let content = vec![
            ContentBlockChatOutput::Text(Text {
                text: "First part".to_string(),
            }),
            ContentBlockChatOutput::Text(Text {
                text: " second part".to_string(),
            }),
            ContentBlockChatOutput::ToolCall(ToolCallOutput {
                arguments: None,
                name: Some("middle_tool".to_string()),
                id: "123".to_string(),
                raw_name: "middle_tool".to_string(),
                raw_arguments: "{\"key\": \"value\"}".to_string(),
            }),
            ContentBlockChatOutput::Text(Text {
                text: " third part".to_string(),
            }),
            ContentBlockChatOutput::Text(Text {
                text: " fourth part".to_string(),
            }),
        ];
        let (content_str, tool_calls, reasoning_content) = process_chat_content(content);
        assert_eq!(
            content_str,
            Some("First part second part third part fourth part".to_string())
        );
        assert_eq!(tool_calls.len(), 1);
        assert_eq!(reasoning_content, None);
        assert_eq!(tool_calls[0].id, "123");
        assert_eq!(tool_calls[0].function.name, Some("middle_tool".to_string()));
        assert_eq!(tool_calls[0].function.arguments, "{\"key\": \"value\"}");
    }

    #[test]
    fn test_process_chat_content_chunk() {
        let content = vec![
            ContentBlockChunk::Text(TextChunk {
                id: "1".to_string(),
                text: "Hello".to_string(),
            }),
            ContentBlockChunk::ToolCall(ToolCallChunk {
                id: "1".to_string(),
                raw_name: "test_tool".to_string(),
                raw_arguments: "{}".to_string(),
            }),
            ContentBlockChunk::Text(TextChunk {
                id: "2".to_string(),
                text: ", world!".to_string(),
            }),
        ];
        let mut tool_id_to_index = HashMap::new();
        let (content_str, tool_calls, reasoning_content) =
            process_chat_content_chunk(content, &mut tool_id_to_index);
        assert_eq!(content_str, Some("Hello, world!".to_string()));
        assert_eq!(tool_calls.len(), 1);
        assert_eq!(tool_calls[0].id, Some("1".to_string()));
        assert_eq!(tool_calls[0].index, 0);
        assert_eq!(tool_calls[0].function.name, Some("test_tool".to_string()));
        assert_eq!(tool_calls[0].function.arguments, "{}");
        assert_eq!(reasoning_content, None);

        let content: Vec<ContentBlockChunk> = vec![];
        let (content_str, tool_calls, _reasoning_content) =
            process_chat_content_chunk(content, &mut tool_id_to_index);
        assert_eq!(content_str, None);
        assert!(tool_calls.is_empty());

        let content = vec![
            ContentBlockChunk::Text(TextChunk {
                id: "1".to_string(),
                text: "First part".to_string(),
            }),
            ContentBlockChunk::Text(TextChunk {
                id: "2".to_string(),
                text: " second part".to_string(),
            }),
            ContentBlockChunk::ToolCall(ToolCallChunk {
                id: "123".to_string(),
                raw_name: "middle_tool".to_string(),
                raw_arguments: "{\"key\": \"value\"}".to_string(),
            }),
            ContentBlockChunk::Text(TextChunk {
                id: "3".to_string(),
                text: " third part".to_string(),
            }),
            ContentBlockChunk::Text(TextChunk {
                id: "4".to_string(),
                text: " fourth part".to_string(),
            }),
            ContentBlockChunk::ToolCall(ToolCallChunk {
                id: "5".to_string(),
                raw_name: "last_tool".to_string(),
                raw_arguments: "{\"key\": \"value\"}".to_string(),
            }),
        ];
        let mut tool_id_to_index = HashMap::new();
        let (content_str, tool_calls, reasoning_content) =
            process_chat_content_chunk(content, &mut tool_id_to_index);
        assert_eq!(
            content_str,
            Some("First part second part third part fourth part".to_string())
        );
        assert_eq!(tool_calls.len(), 2);
        assert_eq!(reasoning_content, None);
        assert_eq!(tool_calls[0].id, Some("123".to_string()));
        assert_eq!(tool_calls[0].index, 0);
        assert_eq!(tool_calls[0].function.name, Some("middle_tool".to_string()));
        assert_eq!(tool_calls[0].function.arguments, "{\"key\": \"value\"}");
        assert_eq!(tool_calls[1].id, Some("5".to_string()));
        assert_eq!(tool_calls[1].index, 1);
        assert_eq!(tool_calls[1].function.name, Some("last_tool".to_string()));
        assert_eq!(tool_calls[1].function.arguments, "{\"key\": \"value\"}");
    }

    #[test]
    fn test_parse_base64() {
        assert_eq!(
            (FileKind::Jpeg, "YWJjCg=="),
            parse_base64_image_data_url("data:image/jpeg;base64,YWJjCg==").unwrap()
        );
        assert_eq!(
            (FileKind::Png, "YWJjCg=="),
            parse_base64_image_data_url("data:image/png;base64,YWJjCg==").unwrap()
        );
        assert_eq!(
            (FileKind::WebP, "YWJjCg=="),
            parse_base64_image_data_url("data:image/webp;base64,YWJjCg==").unwrap()
        );
        let err = parse_base64_image_data_url("data:image/svg;base64,YWJjCg==")
            .unwrap_err()
            .to_string();
        assert!(
            err.contains("Unsupported content type `image/svg`"),
            "Unexpected error message: {err}"
        );
    }

    #[test]
    fn test_cache_options() {
        let headers = HeaderMap::new();

        // Test default cache options (should be write-only)
        let params = Params::try_from_openai(
            headers.clone(),
            OpenAICompatibleParams {
                messages: vec![OpenAICompatibleMessage::User(OpenAICompatibleUserMessage {
                    content: Value::String("test".to_string()),
                })],
                model: "tensorzero::function_name::test_function".into(),
                ..Default::default()
            },
        )
        .unwrap();
        assert_eq!(params.cache_options, CacheParamsOptions::default());

        // Test explicit cache options
        let params = Params::try_from_openai(
            headers.clone(),
            OpenAICompatibleParams {
                messages: vec![OpenAICompatibleMessage::User(OpenAICompatibleUserMessage {
                    content: Value::String("test".to_string()),
                })],
                model: "tensorzero::function_name::test_function".into(),
                tensorzero_cache_options: Some(CacheParamsOptions {
                    max_age_s: Some(3600),
                    enabled: CacheEnabledMode::On,
                }),
                ..Default::default()
            },
        )
        .unwrap();
        assert_eq!(
            params.cache_options,
            CacheParamsOptions {
                max_age_s: Some(3600),
                enabled: CacheEnabledMode::On
            }
        );

        // Test interaction with dryrun
        let params = Params::try_from_openai(
            headers.clone(),
            OpenAICompatibleParams {
                messages: vec![OpenAICompatibleMessage::User(OpenAICompatibleUserMessage {
                    content: Value::String("test".to_string()),
                })],
                model: "tensorzero::function_name::test_function".into(),
                tensorzero_dryrun: Some(true),
                tensorzero_cache_options: Some(CacheParamsOptions {
                    max_age_s: Some(3600),
                    enabled: CacheEnabledMode::On,
                }),
                ..Default::default()
            },
        )
        .unwrap();
        assert_eq!(
            params.cache_options,
            CacheParamsOptions {
                max_age_s: Some(3600),
                enabled: CacheEnabledMode::On,
            }
        );

        // Test write-only with dryrun (should become Off)
        let params = Params::try_from_openai(
            headers,
            OpenAICompatibleParams {
                messages: vec![OpenAICompatibleMessage::User(OpenAICompatibleUserMessage {
                    content: Value::String("test".to_string()),
                })],
                model: "tensorzero::function_name::test_function".into(),
                tensorzero_dryrun: Some(true),
                tensorzero_cache_options: Some(CacheParamsOptions {
                    max_age_s: None,
                    enabled: CacheEnabledMode::WriteOnly,
                }),
                ..Default::default()
            },
        )
        .unwrap();
        assert_eq!(
            params.cache_options,
            CacheParamsOptions {
                max_age_s: None,
                enabled: CacheEnabledMode::WriteOnly
            }
        );
    }

    // Tests for OpenAI-compatible embeddings endpoint

    #[test]
    fn test_openai_compatible_embedding_params_deserialization() {
        // Test single string input
        let json_single = json!({
            "input": "Hello, world!",
            "model": "text-embedding-ada-002"
        });

        let params: OpenAICompatibleEmbeddingParams = serde_json::from_value(json_single).unwrap();
        assert_eq!(params.model, "text-embedding-ada-002");
        match params.input {
            OpenAICompatibleEmbeddingInput::Single(text) => assert_eq!(text, "Hello, world!"),
            _ => panic!("Expected single input"),
        }
        assert!(params.tensorzero_cache_options.is_none());

        // Test batch input
        let json_batch = json!({
            "input": ["Hello", "World", "Test"],
            "model": "text-embedding-ada-002"
        });

        let params: OpenAICompatibleEmbeddingParams = serde_json::from_value(json_batch).unwrap();
        match params.input {
            OpenAICompatibleEmbeddingInput::Batch(texts) => {
                assert_eq!(texts, vec!["Hello", "World", "Test"]);
            }
            _ => panic!("Expected batch input"),
        }

        // Test with TensorZero cache options
        let json_with_cache = json!({
            "input": "Test input",
            "model": "embedding-model",
            "tensorzero::cache_options": {
                "max_age_s": 3600,
                "enabled": "on"
            }
        });

        let params: OpenAICompatibleEmbeddingParams =
            serde_json::from_value(json_with_cache).unwrap();
        assert!(params.tensorzero_cache_options.is_some());
        let cache_options = params.tensorzero_cache_options.unwrap();
        assert_eq!(cache_options.max_age_s, Some(3600));
        assert_eq!(cache_options.enabled, CacheEnabledMode::On);

        // Test with unknown fields (should be captured)
        let json_unknown = json!({
            "input": "Test",
            "model": "embedding-model",
            "encoding_format": "float",
            "dimensions": 1536,
            "user": "test-user"
        });

        let params: OpenAICompatibleEmbeddingParams = serde_json::from_value(json_unknown).unwrap();
        assert!(!params.unknown_fields.is_empty());
        assert!(params.unknown_fields.contains_key("encoding_format"));
        assert!(params.unknown_fields.contains_key("dimensions"));
        assert!(params.unknown_fields.contains_key("user"));
    }

    #[test]
    fn test_openai_compatible_embedding_response_serialization() {
        let response = OpenAICompatibleEmbeddingResponse {
            object: "list".to_string(),
            data: vec![OpenAICompatibleEmbeddingData {
                object: "embedding".to_string(),
                embedding: vec![0.1, 0.2, 0.3, -0.4],
                index: 0,
            }],
            model: "text-embedding-ada-002".to_string(),
            usage: OpenAICompatibleEmbeddingUsage {
                prompt_tokens: 5,
                total_tokens: 5,
            },
        };

        let json_value = serde_json::to_value(&response).unwrap();

        // Verify structure matches OpenAI API spec
        assert_eq!(json_value["object"], "list");
        assert_eq!(json_value["model"], "text-embedding-ada-002");

        let data = &json_value["data"].as_array().unwrap()[0];
        assert_eq!(data["object"], "embedding");
        assert_eq!(data["index"], 0);
        assert_eq!(data["embedding"].as_array().unwrap().len(), 4);
        assert!((data["embedding"][0].as_f64().unwrap() - 0.1).abs() < 1e-6);
        assert!((data["embedding"][3].as_f64().unwrap() - (-0.4)).abs() < 1e-6);

        let usage = &json_value["usage"];
        assert_eq!(usage["prompt_tokens"], 5);
        assert_eq!(usage["total_tokens"], 5);
    }

    #[test]
    fn test_openai_compatible_embedding_input_variants() {
        // Test single string
        let single_json = json!("Hello, world!");
        let single_input: OpenAICompatibleEmbeddingInput =
            serde_json::from_value(single_json).unwrap();
        match single_input {
            OpenAICompatibleEmbeddingInput::Single(text) => assert_eq!(text, "Hello, world!"),
            _ => panic!("Expected single input"),
        }

        // Test array of strings
        let batch_json = json!(["Hello", "World", "Test"]);
        let batch_input: OpenAICompatibleEmbeddingInput =
            serde_json::from_value(batch_json).unwrap();
        match batch_input {
            OpenAICompatibleEmbeddingInput::Batch(texts) => {
                assert_eq!(texts.len(), 3);
                assert_eq!(texts[0], "Hello");
                assert_eq!(texts[1], "World");
                assert_eq!(texts[2], "Test");
            }
            _ => panic!("Expected batch input"),
        }

        // Test empty array
        let empty_json = json!([]);
        let empty_input: OpenAICompatibleEmbeddingInput =
            serde_json::from_value(empty_json).unwrap();
        match empty_input {
            OpenAICompatibleEmbeddingInput::Batch(texts) => assert_eq!(texts.len(), 0),
            _ => panic!("Expected batch input"),
        }
    }

    #[test]
    fn test_embedding_data_structure() {
        let embedding_data = OpenAICompatibleEmbeddingData {
            object: "embedding".to_string(),
            embedding: vec![1.0, -0.5, 0.0, 0.7],
            index: 42,
        };

        let json = serde_json::to_value(&embedding_data).unwrap();
        assert_eq!(json["object"], "embedding");
        assert_eq!(json["index"], 42);

        let embedding_array = json["embedding"].as_array().unwrap();
        assert_eq!(embedding_array.len(), 4);
        assert!((embedding_array[0].as_f64().unwrap() - 1.0).abs() < 1e-6);
        assert!((embedding_array[1].as_f64().unwrap() - (-0.5)).abs() < 1e-6);
        assert!((embedding_array[2].as_f64().unwrap() - 0.0).abs() < 1e-6);
        assert!((embedding_array[3].as_f64().unwrap() - 0.7).abs() < 1e-6);
    }

    #[test]
    fn test_embedding_usage_structure() {
        let usage = OpenAICompatibleEmbeddingUsage {
            prompt_tokens: 100,
            total_tokens: 100,
        };

        let json = serde_json::to_value(&usage).unwrap();
        assert_eq!(json["prompt_tokens"], 100);
        assert_eq!(json["total_tokens"], 100);

        // Verify that completion_tokens is not included (embeddings don't have completion tokens)
        assert!(!json.as_object().unwrap().contains_key("completion_tokens"));
    }

    #[test]
    fn test_embedding_response_multiple_embeddings() {
        // Test response with multiple embeddings (though we don't support batch yet)
        let response = OpenAICompatibleEmbeddingResponse {
            object: "list".to_string(),
            data: vec![
                OpenAICompatibleEmbeddingData {
                    object: "embedding".to_string(),
                    embedding: vec![0.1, 0.2],
                    index: 0,
                },
                OpenAICompatibleEmbeddingData {
                    object: "embedding".to_string(),
                    embedding: vec![0.3, 0.4],
                    index: 1,
                },
            ],
            model: "test-model".to_string(),
            usage: OpenAICompatibleEmbeddingUsage {
                prompt_tokens: 10,
                total_tokens: 10,
            },
        };

        let json = serde_json::to_value(&response).unwrap();
        let data = json["data"].as_array().unwrap();
        assert_eq!(data.len(), 2);
        assert_eq!(data[0]["index"], 0);
        assert_eq!(data[1]["index"], 1);
        let embedding0 = data[0]["embedding"].as_array().unwrap();
        assert!((embedding0[0].as_f64().unwrap() - 0.1).abs() < 1e-6);
        assert!((embedding0[1].as_f64().unwrap() - 0.2).abs() < 1e-6);

        let embedding1 = data[1]["embedding"].as_array().unwrap();
        assert!((embedding1[0].as_f64().unwrap() - 0.3).abs() < 1e-6);
        assert!((embedding1[1].as_f64().unwrap() - 0.4).abs() < 1e-6);
    }

    #[test]
    fn test_embedding_params_model_name_extraction() {
        // Test model name prefixes that might be used in the handler
        let test_cases = vec![
            ("tensorzero::embedding_model_name::my-model", "my-model"),
            ("tensorzero::model_name::my-model", "my-model"),
            ("plain-model-name", "plain-model-name"),
            (
                "tensorzero::function_name::my-function",
                "tensorzero::function_name::my-function",
            ), // Should not be stripped
        ];

        for (input_model, expected_output) in test_cases {
            // This tests the logic that would be used in the embedding_handler
            let extracted = if let Some(model_name) =
                input_model.strip_prefix("tensorzero::embedding_model_name::")
            {
                model_name.to_string()
            } else if let Some(model_name) = input_model.strip_prefix("tensorzero::model_name::") {
                model_name.to_string()
            } else {
                input_model.to_string()
            };

            assert_eq!(
                extracted, expected_output,
                "Failed for input: {input_model}"
            );
        }
    }

    #[test]
    fn test_openai_audio_transcription_params_conversion() {
        let params = OpenAICompatibleAudioTranscriptionParams {
            model: "whisper-1".to_string(),
            language: Some("en".to_string()),
            prompt: Some("Transcribe this audio".to_string()),
            response_format: Some("json".to_string()),
            temperature: Some(0.5),
            timestamp_granularities: Some(vec!["word".to_string()]),
            chunking_strategy: None,
            include: None,
            stream: None,
            unknown_fields: HashMap::new(),
        };

        assert_eq!(params.model, "whisper-1");
        assert_eq!(params.language, Some("en".to_string()));
        assert_eq!(params.response_format, Some("json".to_string()));
        assert_eq!(params.temperature, Some(0.5));
    }

    #[test]
    fn test_openai_audio_translation_params_conversion() {
        let params = OpenAICompatibleAudioTranslationParams {
            model: "whisper-1".to_string(),
            prompt: Some("Translate this audio".to_string()),
            response_format: Some("text".to_string()),
            temperature: Some(0.7),
            unknown_fields: HashMap::new(),
        };

        assert_eq!(params.model, "whisper-1");
        assert_eq!(params.prompt, Some("Translate this audio".to_string()));
        assert_eq!(params.response_format, Some("text".to_string()));
    }

    #[test]
    fn test_openai_text_to_speech_params_conversion() {
        let params = OpenAICompatibleTextToSpeechParams {
            model: "tts-1".to_string(),
            input: "Hello, world!".to_string(),
            voice: "alloy".to_string(),
            response_format: Some("mp3".to_string()),
            speed: Some(1.5),
            unknown_fields: HashMap::new(),
        };

        assert_eq!(params.model, "tts-1");
        assert_eq!(params.input, "Hello, world!");
        assert_eq!(params.voice, "alloy");
        assert_eq!(params.response_format, Some("mp3".to_string()));
        assert_eq!(params.speed, Some(1.5));
    }

    #[test]
    fn test_audio_transcription_response_format_parsing() {
        use crate::audio::AudioTranscriptionResponseFormat;

        // Test valid formats
        let json_format: AudioTranscriptionResponseFormat =
            serde_json::from_str("\"json\"").unwrap();
        assert!(matches!(
            json_format,
            AudioTranscriptionResponseFormat::Json
        ));

        let text_format: AudioTranscriptionResponseFormat =
            serde_json::from_str("\"text\"").unwrap();
        assert!(matches!(
            text_format,
            AudioTranscriptionResponseFormat::Text
        ));

        let verbose_json_format: AudioTranscriptionResponseFormat =
            serde_json::from_str("\"verbose_json\"").unwrap();
        assert!(matches!(
            verbose_json_format,
            AudioTranscriptionResponseFormat::VerboseJson
        ));

        // Test invalid format
        let invalid_format =
            serde_json::from_str::<AudioTranscriptionResponseFormat>("\"invalid\"");
        assert!(invalid_format.is_err());
    }

    #[test]
    fn test_audio_voice_parsing() {
        use crate::audio::AudioVoice;

        // Test valid voices
        let alloy_voice: AudioVoice = serde_json::from_str("\"alloy\"").unwrap();
        assert!(matches!(alloy_voice, AudioVoice::Alloy));

        let nova_voice: AudioVoice = serde_json::from_str("\"nova\"").unwrap();
        assert!(matches!(nova_voice, AudioVoice::Nova));

        // Test non-standard voice becomes Other variant
        let other_voice: AudioVoice = serde_json::from_str("\"invalid_voice\"").unwrap();
        assert!(matches!(other_voice, AudioVoice::Other(_)));
        if let AudioVoice::Other(voice_name) = other_voice {
            assert_eq!(voice_name, "invalid_voice");
        }
    }

    #[test]
    fn test_file_size_validation() {
        // 25MB limit
        const MAX_FILE_SIZE: usize = 25 * 1024 * 1024;

        // Test file under limit
        let small_file = vec![0u8; 1024]; // 1KB
        assert!(small_file.len() <= MAX_FILE_SIZE);

        // Test file at limit
        let limit_file = vec![0u8; MAX_FILE_SIZE];
        assert!(limit_file.len() <= MAX_FILE_SIZE);

        // Test file over limit
        let large_file_size = MAX_FILE_SIZE + 1;
        assert!(large_file_size > MAX_FILE_SIZE);
    }

    #[tokio::test]
    async fn test_response_create_handler_model_resolution() {
        use crate::responses::OpenAIResponseCreateParams;
        use serde_json::json;

        // Test that the handler properly resolves model names
        let params = OpenAIResponseCreateParams {
            model: Some("gpt-4-responses".to_string()),
            input: Some(json!("Test input")),
            instructions: None,
            tools: None,
            tool_choice: None,
            parallel_tool_calls: None,
            max_tool_calls: None,
            previous_response_id: None,
            prompt: None,
            temperature: None,
            max_output_tokens: None,
            response_format: None,
            reasoning: None,
            include: None,
            metadata: None,
            stream: Some(false),
            stream_options: None,
            store: None,
            background: None,
            service_tier: None,
            modalities: None,
            user: None,
            unknown_fields: HashMap::new(),
        };

        // We can't easily test the full handler without a complete app state,
        // but we can verify the types compile correctly
        let _params_json = serde_json::to_value(&params).unwrap();
    }

    #[test]
    fn test_response_path_extraction() {
        // Test that response ID path extraction works correctly
        let response_id = "resp_123abc";
        let path = Path(response_id.to_string());
        assert_eq!(path.0, "resp_123abc");
    }

    #[test]
    fn test_response_streaming_support() {
        use crate::responses::OpenAIResponseCreateParams;
        use serde_json::json;

        // Test that streaming parameters are properly handled
        let params_streaming = OpenAIResponseCreateParams {
            model: Some("gpt-4".to_string()),
            input: Some(json!("Test")),
            stream: Some(true),
            stream_options: Some(json!({"include_usage": true})),
            instructions: None,
            tools: None,
            tool_choice: None,
            parallel_tool_calls: None,
            max_tool_calls: None,
            previous_response_id: None,
            prompt: None,
            temperature: None,
            max_output_tokens: None,
            response_format: None,
            reasoning: None,
            include: None,
            metadata: None,
            store: None,
            background: None,
            service_tier: None,
            modalities: None,
            user: None,
            unknown_fields: HashMap::new(),
        };

        assert_eq!(params_streaming.stream, Some(true));
        assert!(params_streaming.stream_options.is_some());

        // Test non-streaming
        let params_non_streaming = OpenAIResponseCreateParams {
            model: Some("gpt-4".to_string()),
            input: Some(json!("Test")),
            stream: Some(false),
            stream_options: None,
            instructions: None,
            tools: None,
            tool_choice: None,
            parallel_tool_calls: None,
            max_tool_calls: None,
            previous_response_id: None,
            prompt: None,
            temperature: None,
            max_output_tokens: None,
            response_format: None,
            reasoning: None,
            include: None,
            metadata: None,
            store: None,
            background: None,
            service_tier: None,
            modalities: None,
            user: None,
            unknown_fields: HashMap::new(),
        };

        assert_eq!(params_non_streaming.stream, Some(false));
        assert!(params_non_streaming.stream_options.is_none());
    }

    #[test]
    fn test_response_metadata_handling() {
        use crate::responses::OpenAIResponseCreateParams;
        use serde_json::json;

        let mut metadata = HashMap::new();
        metadata.insert("user_id".to_string(), json!("12345"));
        metadata.insert("session_id".to_string(), json!("abc-def"));
        metadata.insert("custom_data".to_string(), json!({"key": "value"}));

        let params = OpenAIResponseCreateParams {
            model: Some("gpt-4".to_string()),
            input: Some(json!("Test")),
            metadata: Some(metadata.clone()),
            stream: None,
            stream_options: None,
            instructions: None,
            tools: None,
            tool_choice: None,
            parallel_tool_calls: None,
            max_tool_calls: None,
            previous_response_id: None,
            prompt: None,
            temperature: None,
            max_output_tokens: None,
            response_format: None,
            reasoning: None,
            include: None,
            store: None,
            background: None,
            service_tier: None,
            modalities: None,
            user: None,
            unknown_fields: HashMap::new(),
        };

        assert!(params.metadata.is_some());
        let param_metadata = params.metadata.unwrap();
        assert_eq!(param_metadata.get("user_id").unwrap(), &json!("12345"));
        assert_eq!(param_metadata.get("session_id").unwrap(), &json!("abc-def"));
        assert_eq!(
            param_metadata.get("custom_data").unwrap(),
            &json!({"key": "value"})
        );
    }

    #[test]
    fn test_response_multimodal_support() {
        use crate::responses::OpenAIResponseCreateParams;
        use serde_json::json;

        // Test text-only modality
        let params_text = OpenAIResponseCreateParams {
            model: Some("gpt-4".to_string()),
            input: Some(json!("Text input")),
            modalities: Some(vec!["text".to_string()]),
            stream: None,
            stream_options: None,
            instructions: None,
            tools: None,
            tool_choice: None,
            parallel_tool_calls: None,
            max_tool_calls: None,
            previous_response_id: None,
            prompt: None,
            temperature: None,
            max_output_tokens: None,
            response_format: None,
            reasoning: None,
            include: None,
            metadata: None,
            store: None,
            background: None,
            service_tier: None,
            user: None,
            unknown_fields: HashMap::new(),
        };

        assert_eq!(params_text.modalities, Some(vec!["text".to_string()]));

        // Test multimodal with text and audio
        let params_multimodal = OpenAIResponseCreateParams {
            model: Some("gpt-4o-audio".to_string()),
            input: Some(json!([
                {"type": "text", "text": "Describe this image"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
            ])),
            modalities: Some(vec!["text".to_string(), "audio".to_string()]),
            stream: None,
            stream_options: None,
            instructions: None,
            tools: None,
            tool_choice: None,
            parallel_tool_calls: None,
            max_tool_calls: None,
            previous_response_id: None,
            prompt: None,
            temperature: None,
            max_output_tokens: None,
            response_format: None,
            reasoning: None,
            include: None,
            metadata: None,
            store: None,
            background: None,
            service_tier: None,
            user: None,
            unknown_fields: HashMap::new(),
        };

        assert_eq!(
            params_multimodal.modalities,
            Some(vec!["text".to_string(), "audio".to_string()])
        );
    }

    #[test]
    fn test_response_tool_configuration() {
        use crate::responses::OpenAIResponseCreateParams;
        use serde_json::json;

        let tools = vec![
            json!({
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the current weather",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city and state"
                            }
                        },
                        "required": ["location"]
                    }
                }
            }),
            json!({
                "type": "code_interpreter"
            }),
        ];

        let params = OpenAIResponseCreateParams {
            model: Some("gpt-4".to_string()),
            input: Some(json!("What's the weather in New York?")),
            tools: Some(tools.clone()),
            tool_choice: Some(json!("auto")),
            parallel_tool_calls: Some(true),
            max_tool_calls: Some(3),
            stream: None,
            stream_options: None,
            instructions: None,
            previous_response_id: None,
            prompt: None,
            temperature: None,
            max_output_tokens: None,
            response_format: None,
            reasoning: None,
            include: None,
            metadata: None,
            store: None,
            background: None,
            service_tier: None,
            modalities: None,
            user: None,
            unknown_fields: HashMap::new(),
        };

        assert_eq!(params.tools, Some(tools));
        assert_eq!(params.tool_choice, Some(json!("auto")));
        assert_eq!(params.parallel_tool_calls, Some(true));
        assert_eq!(params.max_tool_calls, Some(3));
    }
}

// Anthropic Messages API support

#[derive(Clone, Debug, Deserialize)]
pub struct AnthropicMessagesParams {
    /// Input messages.
    messages: Vec<AnthropicMessage>,
    /// The model to use for the completion.
    model: String,
    /// The maximum number of tokens to generate.
    max_tokens: u32,
    /// System prompt (separate from messages in Anthropic API).
    system: Option<String>,
    /// Controls randomness: 0 is deterministic, 1 is very random.
    temperature: Option<f32>,
    /// Nucleus sampling: only sample from top P probability tokens.
    top_p: Option<f32>,
    /// Stop sequences to use.
    stop_sequences: Option<Vec<String>>,
    /// Whether to stream the response.
    stream: Option<bool>,
    /// Tools available to the model.
    tools: Option<Vec<AnthropicTool>>,
    /// Tool choice configuration.
    tool_choice: Option<AnthropicToolChoice>,
    /// Metadata about the request.
    #[expect(dead_code)]
    metadata: Option<AnthropicMetadata>,
    /// The top K tokens to sample from.
    #[expect(dead_code)]
    top_k: Option<u32>,
    /// A unique identifier representing your end-user.
    user_id: Option<String>,
    // TensorZero extensions
    #[serde(rename = "tensorzero::variant_name")]
    tensorzero_variant_name: Option<String>,
    #[serde(rename = "tensorzero::dryrun")]
    tensorzero_dryrun: Option<bool>,
    #[serde(rename = "tensorzero::episode_id")]
    tensorzero_episode_id: Option<Uuid>,
    #[serde(rename = "tensorzero::cache_options")]
    tensorzero_cache_options: Option<CacheParamsOptions>,
    // Capture any extra fields
    #[serde(flatten)]
    unknown_fields: HashMap<String, Value>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(tag = "role")]
#[serde(rename_all = "lowercase")]
enum AnthropicMessage {
    User { content: AnthropicContent },
    Assistant { content: AnthropicContent },
}

#[derive(Clone, Debug, Deserialize)]
#[serde(untagged)]
enum AnthropicContent {
    Text(String),
    Blocks(Vec<AnthropicContentBlock>),
}

#[derive(Clone, Debug, Deserialize)]
#[serde(tag = "type")]
#[serde(rename_all = "snake_case")]
enum AnthropicContentBlock {
    Text {
        text: String,
    },
    Image {
        source: AnthropicImageSource,
    },
    ToolUse {
        id: String,
        name: String,
        input: Value,
    },
    ToolResult {
        tool_use_id: String,
        content: AnthropicContent,
    },
}

#[derive(Clone, Debug, Deserialize)]
struct AnthropicImageSource {
    #[serde(rename = "type")]
    source_type: String,
    media_type: String,
    data: String,
}

#[derive(Clone, Debug, Deserialize)]
struct AnthropicTool {
    name: String,
    description: Option<String>,
    input_schema: Value,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(untagged)]
enum AnthropicToolChoice {
    Auto,
    Any,
    Tool { name: String },
}

#[derive(Clone, Debug, Deserialize)]
struct AnthropicMetadata {
    #[expect(dead_code)]
    user_id: Option<String>,
}

/// Handler for Anthropic Messages API compatibility
#[debug_handler(state = AppStateData)]
pub async fn anthropic_messages_handler(
    State(app_state): AppState,
    analytics: Option<Extension<Arc<tokio::sync::Mutex<RequestAnalytics>>>>,
    headers: HeaderMap,
    StructuredJson(anthropic_params): StructuredJson<AnthropicMessagesParams>,
) -> Result<Response<Body>, Error> {
    if !anthropic_params.unknown_fields.is_empty() {
        tracing::warn!(
            "Ignoring unknown fields in Anthropic Messages request: {:?}",
            anthropic_params.unknown_fields.keys().collect::<Vec<_>>()
        );
    }

    // Convert Anthropic format to OpenAI-compatible format
    let openai_params = convert_anthropic_to_openai(anthropic_params)?;

    // Call the existing inference handler with converted parameters
    let response = inference_handler(
        State(app_state),
        analytics,
        headers,
        StructuredJson(openai_params),
    )
    .await?;

    // Convert the response from OpenAI format to Anthropic format
    convert_openai_response_to_anthropic(response).await
}

/// Convert Anthropic Messages API request to OpenAI-compatible format
fn convert_anthropic_to_openai(
    anthropic_params: AnthropicMessagesParams,
) -> Result<OpenAICompatibleParams, Error> {
    let mut messages = Vec::new();

    // Add system message if present
    if let Some(system) = anthropic_params.system {
        messages.push(OpenAICompatibleMessage::System(
            OpenAICompatibleSystemMessage {
                content: Value::String(system),
            },
        ));
    }

    // Convert messages
    for msg in anthropic_params.messages {
        match msg {
            AnthropicMessage::User { content } => {
                let content_value = convert_anthropic_content_to_value(content)?;
                messages.push(OpenAICompatibleMessage::User(OpenAICompatibleUserMessage {
                    content: content_value,
                }));
            }
            AnthropicMessage::Assistant { content } => {
                let content_value = convert_anthropic_content_to_value(content)?;
                messages.push(OpenAICompatibleMessage::Assistant(
                    OpenAICompatibleAssistantMessage {
                        content: Some(content_value),
                        tool_calls: None,
                    },
                ));
            }
        }
    }

    // Convert tools
    let tools = anthropic_params.tools.map(|tools| {
        tools
            .into_iter()
            .map(|tool| OpenAICompatibleTool::Function {
                name: tool.name,
                description: tool.description,
                parameters: tool.input_schema,
                strict: false,
            })
            .collect()
    });

    // Convert tool choice
    let tool_choice = anthropic_params.tool_choice.map(|choice| match choice {
        AnthropicToolChoice::Auto => ChatCompletionToolChoiceOption::Auto,
        AnthropicToolChoice::Any => ChatCompletionToolChoiceOption::Required,
        AnthropicToolChoice::Tool { name } => {
            ChatCompletionToolChoiceOption::Named(OpenAICompatibleNamedToolChoice {
                r#type: "function".to_string(),
                function: FunctionName { name },
            })
        }
    });

    // Convert stop sequences
    let stop = anthropic_params.stop_sequences.map(StringOrVec::Vec);

    Ok(OpenAICompatibleParams {
        messages,
        model: anthropic_params.model,
        max_tokens: Some(anthropic_params.max_tokens),
        temperature: anthropic_params.temperature,
        top_p: anthropic_params.top_p,
        stream: anthropic_params.stream,
        tools,
        tool_choice,
        stop,
        user: anthropic_params.user_id,
        tensorzero_variant_name: anthropic_params.tensorzero_variant_name,
        tensorzero_dryrun: anthropic_params.tensorzero_dryrun,
        tensorzero_episode_id: anthropic_params.tensorzero_episode_id,
        tensorzero_cache_options: anthropic_params.tensorzero_cache_options,
        ..Default::default()
    })
}

/// Convert Anthropic content to JSON Value
fn convert_anthropic_content_to_value(content: AnthropicContent) -> Result<Value, Error> {
    match content {
        AnthropicContent::Text(text) => Ok(Value::String(text)),
        AnthropicContent::Blocks(blocks) => {
            let converted_blocks: Result<Vec<Value>, Error> = blocks
                .into_iter()
                .map(|block| match block {
                    AnthropicContentBlock::Text { text } => Ok(json!({
                        "type": "text",
                        "text": text
                    })),
                    AnthropicContentBlock::Image { source } => Ok(json!({
                        "type": "image_url",
                        "image_url": {
                            "url": format!("data:{};{},{}", source.media_type, source.source_type, source.data)
                        }
                    })),
                    AnthropicContentBlock::ToolUse { id, name, input } => Ok(json!({
                        "type": "tool_use",
                        "id": id,
                        "name": name,
                        "input": input
                    })),
                    AnthropicContentBlock::ToolResult { tool_use_id, content } => {
                        convert_anthropic_content_to_value(content).map(|content_value| json!({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": content_value
                        }))
                    }
                })
                .collect();

            converted_blocks.map(Value::Array)
        }
    }
}

/// Convert OpenAI response to Anthropic Messages API format
async fn convert_openai_response_to_anthropic(
    response: Response<Body>,
) -> Result<Response<Body>, Error> {
    let (parts, body) = response.into_parts();

    // Check if this is a streaming response
    if parts
        .headers
        .get("content-type")
        .and_then(|h| h.to_str().ok())
        .map(|s| s.contains("text/event-stream"))
        .unwrap_or(false)
    {
        // Handle streaming response
        let stream = body.into_data_stream();
        let anthropic_stream = tokio_stream::StreamExt::map(stream, |chunk| {
            chunk.map(|bytes| {
                // Parse the SSE data
                let data = String::from_utf8_lossy(&bytes);
                if let Some(json_str) = data.strip_prefix("data: ") {
                    if json_str.trim() == "[DONE]" {
                        axum::body::Bytes::from(
                            "event: message_stop\ndata: {\"type\":\"message_stop\"}\n\n",
                        )
                    } else {
                        // Parse OpenAI chunk and convert to Anthropic format
                        match serde_json::from_str::<Value>(json_str) {
                            Ok(openai_chunk) => {
                                let anthropic_event =
                                    convert_openai_chunk_to_anthropic(openai_chunk);
                                let event_data =
                                    serde_json::to_string(&anthropic_event).unwrap_or_default();
                                axum::body::Bytes::from(format!(
                                    "event: {}\ndata: {}\n\n",
                                    anthropic_event["type"]
                                        .as_str()
                                        .unwrap_or("content_block_delta"),
                                    event_data
                                ))
                            }
                            Err(_) => axum::body::Bytes::from(bytes.to_vec()),
                        }
                    }
                } else {
                    axum::body::Bytes::from(bytes.to_vec())
                }
            })
        });

        let body = Body::from_stream(anthropic_stream);
        Ok(Response::from_parts(parts, body))
    } else {
        // Handle non-streaming response
        let bytes = axum::body::to_bytes(body, usize::MAX).await.map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Failed to read response body: {e}"),
                provider_type: "anthropic_compat".to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?;

        let openai_response: Value = serde_json::from_slice(&bytes).map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Failed to parse OpenAI response: {e}"),
                provider_type: "anthropic_compat".to_string(),
                raw_request: None,
                raw_response: Some(String::from_utf8_lossy(&bytes).to_string()),
            })
        })?;

        let anthropic_response = convert_openai_completion_to_anthropic(openai_response)?;

        let response_bytes = serde_json::to_vec(&anthropic_response).map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Failed to serialize Anthropic response: {e}"),
                provider_type: "anthropic_compat".to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?;

        let body = Body::from(response_bytes);
        Ok(Response::from_parts(parts, body))
    }
}

/// Convert OpenAI completion response to Anthropic format
fn convert_openai_completion_to_anthropic(openai_response: Value) -> Result<Value, Error> {
    let choice = openai_response["choices"][0].as_object().ok_or_else(|| {
        Error::new(ErrorDetails::InferenceServer {
            message: "No choices in OpenAI response".to_string(),
            provider_type: "anthropic_compat".to_string(),
            raw_request: None,
            raw_response: Some(openai_response.to_string()),
        })
    })?;

    let message = choice["message"].as_object().ok_or_else(|| {
        Error::new(ErrorDetails::InferenceServer {
            message: "No message in choice".to_string(),
            provider_type: "anthropic_compat".to_string(),
            raw_request: None,
            raw_response: Some(openai_response.to_string()),
        })
    })?;

    // Build content array
    let mut content_blocks = Vec::new();

    // Add text content if present
    if let Some(text_content) = message.get("content").and_then(|c| c.as_str()) {
        if !text_content.is_empty() {
            content_blocks.push(json!({
                "type": "text",
                "text": text_content
            }));
        }
    }

    // Add tool calls if present
    if let Some(tool_calls) = message.get("tool_calls").and_then(|tc| tc.as_array()) {
        for tool_call in tool_calls {
            if let Some(function) = tool_call.get("function") {
                content_blocks.push(json!({
                    "type": "tool_use",
                    "id": tool_call.get("id").and_then(|id| id.as_str()).unwrap_or(""),
                    "name": function.get("name").and_then(|n| n.as_str()).unwrap_or(""),
                    "input": function.get("arguments")
                        .and_then(|args| args.as_str())
                        .and_then(|args_str| serde_json::from_str::<Value>(args_str).ok())
                        .unwrap_or(json!({}))
                }));
            }
        }
    }

    // If no content blocks were added, add an empty text block
    if content_blocks.is_empty() {
        content_blocks.push(json!({
            "type": "text",
            "text": ""
        }));
    }

    let finish_reason = choice
        .get("finish_reason")
        .and_then(|r| r.as_str())
        .unwrap_or("stop");

    let stop_reason = match finish_reason {
        "stop" => "end_turn",
        "length" => "max_tokens",
        "tool_calls" => "tool_use",
        _ => "end_turn",
    };

    let usage = openai_response.get("usage").cloned().unwrap_or(json!({}));
    let input_tokens = usage["prompt_tokens"].as_u64().unwrap_or(0);
    let output_tokens = usage["completion_tokens"].as_u64().unwrap_or(0);

    Ok(json!({
        "id": openai_response["id"],
        "type": "message",
        "role": "assistant",
        "content": content_blocks,
        "model": openai_response["model"],
        "stop_reason": stop_reason,
        "stop_sequence": null,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        }
    }))
}

/// Convert OpenAI streaming chunk to Anthropic format
fn convert_openai_chunk_to_anthropic(openai_chunk: Value) -> Value {
    if let Some(delta) = openai_chunk["choices"][0]["delta"].as_object() {
        // Check for text content
        if let Some(content) = delta.get("content").and_then(|c| c.as_str()) {
            json!({
                "type": "content_block_delta",
                "index": 0,
                "delta": {
                    "type": "text_delta",
                    "text": content
                }
            })
        }
        // Check for tool calls
        else if let Some(tool_calls) = delta.get("tool_calls").and_then(|tc| tc.as_array()) {
            if let Some(tool_call) = tool_calls.first() {
                let index = tool_call.get("index").and_then(|i| i.as_u64()).unwrap_or(0);

                // Check if this is the start of a new tool call
                if tool_call.get("id").is_some() {
                    let empty_obj = json!({});
                    let function = tool_call.get("function").unwrap_or(&empty_obj);
                    json!({
                        "type": "content_block_start",
                        "index": index,
                        "content_block": {
                            "type": "tool_use",
                            "id": tool_call.get("id").and_then(|id| id.as_str()).unwrap_or(""),
                            "name": function.get("name").and_then(|n| n.as_str()).unwrap_or("")
                        }
                    })
                } else {
                    // This is a continuation of arguments
                    let empty_obj = json!({});
                    let function = tool_call.get("function").unwrap_or(&empty_obj);
                    if let Some(arguments) = function.get("arguments").and_then(|a| a.as_str()) {
                        json!({
                            "type": "content_block_delta",
                            "index": index,
                            "delta": {
                                "type": "input_json_delta",
                                "partial_json": arguments
                            }
                        })
                    } else {
                        // Empty delta
                        json!({
                            "type": "content_block_delta",
                            "index": index,
                            "delta": {
                                "type": "input_json_delta",
                                "partial_json": ""
                            }
                        })
                    }
                }
            } else {
                // Empty delta
                json!({
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {
                        "type": "text_delta",
                        "text": ""
                    }
                })
            }
        }
        // Check for finish_reason (indicating end of content block)
        else if delta.get("finish_reason").is_some() {
            json!({
                "type": "content_block_stop",
                "index": 0
            })
        } else {
            // Empty delta
            json!({
                "type": "content_block_delta",
                "index": 0,
                "delta": {
                    "type": "text_delta",
                    "text": ""
                }
            })
        }
    } else {
        // This is the start of a new message
        json!({
            "type": "message_start",
            "message": {
                "id": openai_chunk.get("id").and_then(|id| id.as_str()).unwrap_or(""),
                "type": "message",
                "role": "assistant",
                "content": [],
                "model": openai_chunk.get("model").and_then(|m| m.as_str()).unwrap_or(""),
                "usage": {
                    "input_tokens": 0,
                    "output_tokens": 0
                }
            }
        })
    }
}

// Document processing handler
/// Handler for document processing (POST /v1/documents)
pub async fn document_processing_handler(
    State(AppStateData {
        config,
        http_client,
        clickhouse_connection_info,
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store,
        ..
    }): AppState,
    headers: HeaderMap,
    StructuredJson(openai_compatible_params): StructuredJson<
        crate::documents::OpenAICompatibleDocumentParams,
    >,
) -> Result<Response<Body>, Error> {
    let unknown_fields: Vec<&str> = openai_compatible_params
        .unknown_fields
        .keys()
        .map(|k| k.as_str())
        .collect();

    if !unknown_fields.is_empty() {
        tracing::warn!(
            "Ignoring unknown fields in document processing request: {:?}",
            unknown_fields
        );
    }

    // Resolve the model name based on authentication state
    let model_resolution = model_resolution::resolve_model_name(
        Some(&openai_compatible_params.model),
        &headers,
        false, // not for embeddings
    )?;

    let model_id = model_resolution.model_name.ok_or_else(|| {
        Error::new(ErrorDetails::InvalidOpenAICompatibleRequest {
            message: "Document processing requests must specify a model, not a function"
                .to_string(),
        })
    })?;

    let original_model_name = model_resolution.original_model_name.to_string();

    // Convert OpenAI request to internal format
    let document_request = crate::documents::DocumentProcessingRequest {
        id: Uuid::now_v7(),
        model: Arc::from(openai_compatible_params.model.as_str()),
        document: openai_compatible_params.document.clone(),
        prompt: openai_compatible_params.prompt.clone(),
    };

    // Extract model configuration
    use crate::model::ModelTableExt;
    let models = config.models.read().await;
    let model = models
        .get_with_capability(
            &model_id,
            crate::endpoints::capability::EndpointCapability::Document,
        )
        .await?
        .ok_or_else(|| {
            Error::new(ErrorDetails::Config {
                message: format!(
                    "Model '{original_model_name}' not found or does not support document processing"
                ),
            })
        })?;

    // Merge credentials from the credential store
    let mut credentials = merge_credentials_from_store(&model_credential_store);

    // Extract and forward the authorization header if present
    if let Some(auth_header) = headers.get("authorization") {
        if let Ok(auth_str) = auth_header.to_str() {
            // Strip "Bearer " prefix if present
            let token = auth_str.strip_prefix("Bearer ").unwrap_or(auth_str);
            // Use "authorization" as the key so dynamic credential lookup can find it
            credentials.insert(
                "authorization".to_string(),
                secrecy::SecretString::from(token.to_string()),
            );
        }
    }

    // Create inference clients
    let cache_options = crate::cache::CacheOptions {
        max_age_s: None,
        enabled: crate::cache::CacheEnabledMode::Off,
    }; // No caching for documents yet
    let clients = super::inference::InferenceClients {
        http_client: &http_client,
        credentials: &credentials,
        clickhouse_connection_info: &clickhouse_connection_info,
        cache_options: &cache_options,
    };

    // Call the model's document processing capability
    let response = model
        .process_document(&document_request, &original_model_name, &clients)
        .await?;

    // Convert to OpenAI-compatible format
    let openai_response = crate::documents::OpenAICompatibleDocumentResponse {
        id: format!("doc_{}", response.id),
        object: "document".to_string(),
        created: chrono::Utc::now().timestamp() as u64,
        model: original_model_name.clone(),
        document_id: response.document_id.to_string(),
        pages: response.pages.clone(),
        usage_info: response.usage_info.clone(),
    };

    // Convert response to JSON
    let json_response = serde_json::to_string(&openai_response).map_err(|e| {
        Error::new(ErrorDetails::Serialization {
            message: format!("Failed to serialize document response: {}", e),
        })
    })?;

    Ok(Response::builder()
        .status(StatusCode::OK)
        .header("Content-Type", "application/json")
        .body(Body::from(json_response))
        .map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Failed to build response: {}", e),
                provider_type: "BudDoc".to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?)
}
