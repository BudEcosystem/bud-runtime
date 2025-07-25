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

use axum::body::Body;
use axum::debug_handler;
use axum::extract::{Multipart, Path, Query, State};
use axum::http::{HeaderMap, StatusCode};
use axum::response::sse::{Event, Sse};
use axum::response::{IntoResponse, Response};
use axum::Json;
use futures::Stream;
use serde::{Deserialize, Serialize};
use serde_json::{json, Map, Value};
use tokio_stream::StreamExt;
use url::Url;
use uuid::Uuid;

use crate::cache::CacheParamsOptions;
use crate::endpoints::inference::{
    inference, ChatCompletionInferenceParams, InferenceClients, InferenceCredentials,
    InferenceParams, Params,
};
use crate::error::{Error, ErrorDetails};
use crate::gateway_util::{AppState, AppStateData, StructuredJson};
use crate::inference::types::extra_body::UnfilteredInferenceExtraBody;
use crate::inference::types::extra_headers::UnfilteredInferenceExtraHeaders;
use crate::inference::types::{
    current_timestamp, ContentBlockChatOutput, ContentBlockChunk, File, FileKind, FinishReason,
    Input, InputMessage, InputMessageContent, Role, TextKind, Usage,
};
use crate::tool::{
    DynamicToolParams, Tool, ToolCall, ToolCallChunk, ToolCallOutput, ToolChoice, ToolResult,
};
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
use std::sync::Arc;

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

/// A handler for the OpenAI-compatible inference endpoint
#[debug_handler(state = AppStateData)]
pub async fn inference_handler(
    State(AppStateData {
        config,
        http_client,
        clickhouse_connection_info,
        kafka_connection_info,
        authentication_info: _,
        model_credential_store,
        ..
    }): AppState,
    headers: HeaderMap,
    StructuredJson(openai_compatible_params): StructuredJson<OpenAICompatibleParams>,
) -> Result<Response<Body>, Error> {
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
        &openai_compatible_params.model,
        &headers,
        false, // not for embedding
    )?;

    let original_model_name = model_resolution.original_model_name.to_string();

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
        params.observability_metadata = Some(super::inference::ObservabilityMetadata {
            project_id: project_id.to_string(),
            endpoint_id: endpoint_id.to_string(),
            model_id: model_id.to_string(),
        });
    }

    let response = inference(
        config,
        &http_client,
        clickhouse_connection_info,
        kafka_connection_info,
        model_credential_store,
        params,
    )
    .await?;

    match response {
        InferenceOutput::NonStreaming(response) => {
            let mut openai_compatible_response =
                OpenAICompatibleResponse::from((response.clone(), original_model_name.clone()));

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
            Ok(Json(openai_compatible_response).into_response())
        }
        InferenceOutput::Streaming(stream) => {
            let openai_compatible_stream = prepare_serialized_openai_compatible_events(
                stream,
                original_model_name,
                stream_options,
            );
            Ok(Sse::new(openai_compatible_stream)
                .keep_alive(axum::response::sse::KeepAlive::new())
                .into_response())
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize, Default)]
pub struct OpenAICompatibleFunctionCall {
    pub name: String,
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

#[derive(Clone, Debug, Deserialize, PartialEq)]
struct OpenAICompatibleSystemMessage {
    content: Value,
}

#[derive(Clone, Debug, Deserialize, PartialEq)]
struct OpenAICompatibleUserMessage {
    content: Value,
}

#[derive(Clone, Debug, Deserialize, PartialEq)]
struct OpenAICompatibleAssistantMessage {
    content: Option<Value>,
    tool_calls: Option<Vec<OpenAICompatibleToolCall>>,
}

#[derive(Clone, Debug, Deserialize, PartialEq)]
struct OpenAICompatibleToolMessage {
    content: Option<Value>,
    tool_call_id: String,
}

#[derive(Clone, Debug, Deserialize, PartialEq)]
#[serde(tag = "role")]
#[serde(rename_all = "lowercase")]
enum OpenAICompatibleMessage {
    #[serde(alias = "developer")]
    System(OpenAICompatibleSystemMessage),
    User(OpenAICompatibleUserMessage),
    Assistant(OpenAICompatibleAssistantMessage),
    Tool(OpenAICompatibleToolMessage),
}

#[derive(Clone, Debug, Deserialize, PartialEq)]
#[serde(tag = "type")]
#[serde(rename_all = "snake_case")]
enum OpenAICompatibleResponseFormat {
    Text,
    JsonSchema { json_schema: JsonSchemaInfoOption },
    JsonObject,
}

#[derive(Clone, Debug, Deserialize, PartialEq)]
#[serde(untagged)]
enum JsonSchemaInfoOption {
    JsonSchema(JsonSchemaInfo),
    DeprecatedJsonSchema(Value),
}

#[derive(Clone, Debug, Deserialize, PartialEq)]
struct JsonSchemaInfo {
    name: String,
    description: Option<String>,
    schema: Option<Value>,
    #[serde(default)]
    strict: bool,
}

#[derive(Clone, Debug, Deserialize, PartialEq)]
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

#[derive(Clone, Debug, Deserialize, PartialEq)]
struct FunctionName {
    name: String,
}

/// Specifies a tool the model should use. Use to force the model to call a specific function.
#[derive(Clone, Debug, Deserialize, PartialEq)]
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
#[derive(Clone, Debug, Default, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
enum ChatCompletionToolChoiceOption {
    #[default]
    None,
    Auto,
    Required,
    #[serde(untagged)]
    Named(OpenAICompatibleNamedToolChoice),
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq)]
struct OpenAICompatibleStreamOptions {
    #[serde(default)]
    include_usage: bool,
}

/// Helper type for parameters that can be either a single string or an array of strings
#[derive(Clone, Debug, Deserialize, PartialEq)]
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

#[derive(Clone, Debug, Deserialize, PartialEq, Default)]
pub struct OpenAICompatibleParams {
    messages: Vec<OpenAICompatibleMessage>,
    model: String,
    frequency_penalty: Option<f32>,
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
    system_fingerprint: String,
    service_tier: String,
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
                            tool_call_id_to_name
                                .insert(tool_call.id.clone(), tool_call.function.name.clone());
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
            name: tool_call.function.name,
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
                    service_tier: "".to_string(),
                    system_fingerprint: "".to_string(),
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
                system_fingerprint: "".to_string(),
                service_tier: "".to_string(),
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
                name: tool_call.raw_name,
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
    system_fingerprint: String,
    service_tier: String,
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
                service_tier: "".to_string(),
                model: model_name.to_string(),
                system_fingerprint: "".to_string(),
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
            service_tier: "".to_string(),
            model: model_name.to_string(),
            system_fingerprint: "".to_string(),
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
                        name: tool_call.raw_name,
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

/// Prepares an Event for SSE on the way out of the gateway
/// When None is passed in, we send "[DONE]" to the client to signal the end of the stream
fn prepare_serialized_openai_compatible_events(
    mut stream: InferenceStream,
    model_name: String,
    stream_options: Option<OpenAICompatibleStreamOptions>,
) -> impl Stream<Item = Result<Event, Error>> {
    async_stream::stream! {
        let mut tool_id_to_index = HashMap::new();
        let mut is_first_chunk = true;
        let mut total_usage = OpenAICompatibleUsage {
            prompt_tokens: 0,
            completion_tokens: 0,
            total_tokens: 0,
        };
        let mut inference_id = None;
        let mut episode_id = None;
        while let Some(chunk) = stream.next().await {
            // NOTE - in the future, we may want to end the stream early if we get an error
            // For now, we just ignore the error and try to get more chunks
            let Ok(chunk) = chunk else {
                continue;
            };
            inference_id = Some(chunk.inference_id());
            episode_id = Some(chunk.episode_id());
            let chunk_usage = match &chunk {
                InferenceResponseChunk::Chat(c) => {
                    &c.usage
                }
                InferenceResponseChunk::Json(c) => {
                    &c.usage
                }
            };
            if let Some(chunk_usage) = chunk_usage {
                total_usage.prompt_tokens += chunk_usage.input_tokens;
                total_usage.completion_tokens += chunk_usage.output_tokens;
                total_usage.total_tokens += chunk_usage.input_tokens + chunk_usage.output_tokens;
            }
            let openai_compatible_chunks = convert_inference_response_chunk_to_openai_compatible(chunk, &mut tool_id_to_index, &model_name);
            for chunk in openai_compatible_chunks {
                let mut chunk_json = serde_json::to_value(chunk).map_err(|e| {
                    Error::new(ErrorDetails::Inference {
                        message: format!("Failed to convert chunk to JSON: {e}"),
                    })
                })?;
                if is_first_chunk {
                    // OpenAI includes "assistant" role in the first chunk but not in the subsequent chunks
                    chunk_json["choices"][0]["delta"]["role"] = Value::String("assistant".to_string());
                    is_first_chunk = false;
                }

                yield Event::default().json_data(chunk_json).map_err(|e| {
                    Error::new(ErrorDetails::Inference {
                        message: format!("Failed to convert Value to Event: {e}"),
                    })
                })
            }
        }
        if stream_options.map(|s| s.include_usage).unwrap_or(false) {
            let episode_id = episode_id.ok_or_else(|| {
                Error::new(ErrorDetails::Inference {
                    message: "Cannot find episode_id - no chunks were produced by TensorZero".to_string(),
                })
            })?;
            let inference_id = inference_id.ok_or_else(|| {
                Error::new(ErrorDetails::Inference {
                    message: "Cannot find inference_id - no chunks were produced by TensorZero".to_string(),
                })
            })?;
            let usage_chunk = OpenAICompatibleResponseChunk {
                id: inference_id.to_string(),
                episode_id: episode_id.to_string(),
                choices: vec![],
                created: current_timestamp() as u32,
                model: model_name.clone(),
                system_fingerprint: "".to_string(),
                object: "chat.completion.chunk".to_string(),
                service_tier: "".to_string(),
                usage: Some(OpenAICompatibleUsage {
                    prompt_tokens: total_usage.prompt_tokens,
                    completion_tokens: total_usage.completion_tokens,
                    total_tokens: total_usage.total_tokens,
                }),
            };
            yield Event::default().json_data(
                usage_chunk)
                .map_err(|e| {
                    Error::new(ErrorDetails::Inference {
                        message: format!("Failed to convert usage chunk to JSON: {e}"),
                    })
                });
        }
        yield Ok(Event::default().data("[DONE]"));
    }
}

impl From<ToolCallChunk> for OpenAICompatibleToolCall {
    fn from(tool_call: ToolCallChunk) -> Self {
        OpenAICompatibleToolCall {
            id: tool_call.id,
            r#type: "function".to_string(),
            function: OpenAICompatibleFunctionCall {
                name: tool_call.raw_name,
                arguments: tool_call.raw_arguments,
            },
        }
    }
}

// OpenAI-compatible embedding types and handler

#[derive(Clone, Debug, Deserialize, PartialEq)]
pub struct OpenAICompatibleEmbeddingParams {
    input: OpenAICompatibleEmbeddingInput,
    model: String,
    #[serde(rename = "tensorzero::cache_options")]
    tensorzero_cache_options: Option<CacheParamsOptions>,
    #[serde(flatten)]
    unknown_fields: HashMap<String, Value>,
}

#[derive(Clone, Debug, Deserialize, PartialEq)]
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

/// A handler for the OpenAI-compatible embedding endpoint
#[debug_handler(state = AppStateData)]
pub async fn embedding_handler(
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
        &openai_compatible_params.model,
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
            .into_iter()
            .enumerate()
            .map(|(index, embedding)| OpenAICompatibleEmbeddingData {
                object: "embedding".to_string(),
                embedding,
                index,
            })
            .collect(),
        model: original_model_name,
        usage: OpenAICompatibleEmbeddingUsage {
            prompt_tokens: response.usage.input_tokens,
            total_tokens: response.usage.input_tokens,
        },
    };

    Ok(Json(openai_response).into_response())
}

/// OpenAI-compatible moderation request structure
#[derive(Clone, Debug, Deserialize)]
pub struct OpenAICompatibleModerationParams {
    pub input: OpenAICompatibleModerationInput,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    #[serde(flatten)]
    pub unknown_fields: HashMap<String, Value>,
}

#[derive(Clone, Debug, Deserialize)]
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
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store,
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
    let model_resolution = model_resolution::resolve_model_name(&model_name, &headers, false)?;

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

    let moderation_request = crate::moderation::ModerationRequest {
        input: internal_input,
        model: None, // Let the provider set the appropriate model name
    };

    // Get the regular model table
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

    // For now, we'll use the first provider in routing that supports moderation
    // This is a temporary solution until we fully integrate moderation into the regular model system
    let mut provider_errors = HashMap::new();
    let mut response = None;

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

    let response = response
        .ok_or_else(|| Error::new(ErrorDetails::ModelProvidersExhausted { provider_errors }))?;

    // Convert to OpenAI-compatible format
    let openai_response = OpenAICompatibleModerationResponse {
        id: format!("modr-{}", Uuid::now_v7()),
        model: model_resolution.original_model_name.to_string(),
        results: response.results,
    };

    Ok(Json(openai_response).into_response())
}

// Audio transcription types
#[derive(Clone, Debug, Default, Deserialize)]
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
#[derive(Clone, Debug, Default, Deserialize)]
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
#[derive(Clone, Debug, Deserialize)]
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
        &params.model,
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
        &params.model,
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
        &params.model,
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
        &params.model,
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
        &params.model,
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
        kafka_connection_info: _,
        authentication_info: _,
        model_credential_store,
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
        &params.model,
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
            .into_iter()
            .map(|d| OpenAICompatibleImageData {
                url: d.url,
                b64_json: d.b64_json,
                revised_prompt: d.revised_prompt,
            })
            .collect(),
    };

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
        &params.model,
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
        &params.model,
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

    Ok(Json(openai_response).into_response())
}

// OpenAI-compatible Image parameter types
#[derive(Debug, Deserialize)]
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

#[derive(Debug, Default)]
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

#[derive(Debug, Default)]
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

use crate::responses::OpenAIResponseCreateParams;

/// Handler for creating a new response (POST /v1/responses)
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
    if !params.unknown_fields.is_empty() {
        tracing::warn!(
            "Ignoring unknown fields in OpenAI-compatible response create request: {:?}",
            params.unknown_fields.keys().collect::<Vec<_>>()
        );
    }

    // Resolve the model name based on authentication state
    let model_resolution = model_resolution::resolve_model_name(
        &params.model,
        &headers,
        false, // not for embedding
    )?;

    let model_name = model_resolution.model_name.ok_or_else(|| {
        Error::new(ErrorDetails::InvalidOpenAICompatibleRequest {
            message: "Response requests must specify a model, not a function".to_string(),
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
    let credentials = merge_credentials_from_store(&model_credential_store);

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

    // Check if streaming is requested
    if params.stream.unwrap_or(false) {
        // Handle streaming response
        let stream = model
            .stream_response(&params, &model_resolution.original_model_name, &clients)
            .await?;

        // Convert to SSE stream
        let sse_stream = stream.map(|result| match result {
            Ok(event) => Event::default().json_data(event).map_err(|e| {
                Error::new(ErrorDetails::Inference {
                    message: format!("Failed to serialize SSE event: {e}"),
                })
            }),
            Err(e) => Err(e),
        });

        Ok(Sse::new(sse_stream).into_response())
    } else {
        // Handle non-streaming response
        let response = model
            .create_response(&params, &model_resolution.original_model_name, &clients)
            .await?;

        Ok(Json(response).into_response())
    }
}

/// Handler for retrieving a response (GET /v1/responses/{response_id})
///
/// Note: Since the OpenAI API doesn't include a model parameter for retrieval operations,
/// you must specify the model name using the 'x-model-name' header. If not provided,
/// it defaults to 'gpt-4-responses'.
///
/// Example:
/// ```
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

    let clients = InferenceClients {
        http_client: &http_client,
        credentials: &InferenceCredentials::default(),
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
/// ```
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

    let clients = InferenceClients {
        http_client: &http_client,
        credentials: &InferenceCredentials::default(),
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
/// ```
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

    let clients = InferenceClients {
        http_client: &http_client,
        credentials: &InferenceCredentials::default(),
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
/// ```
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

    let clients = InferenceClients {
        http_client: &http_client,
        credentials: &InferenceCredentials::default(),
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
                        name: "test_tool".to_string(),
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
        assert_eq!(tool_calls[0].function.name, "test_tool");
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
        assert_eq!(tool_calls[0].function.name, "middle_tool");
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
        assert_eq!(tool_calls[0].function.name, "test_tool");
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
        assert_eq!(tool_calls[0].function.name, "middle_tool");
        assert_eq!(tool_calls[0].function.arguments, "{\"key\": \"value\"}");
        assert_eq!(tool_calls[1].id, Some("5".to_string()));
        assert_eq!(tool_calls[1].index, 1);
        assert_eq!(tool_calls[1].function.name, "last_tool");
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
            model: "gpt-4-responses".to_string(),
            input: json!("Test input"),
            instructions: None,
            tools: None,
            tool_choice: None,
            parallel_tool_calls: None,
            max_tool_calls: None,
            previous_response_id: None,
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
            model: "gpt-4".to_string(),
            input: json!("Test"),
            stream: Some(true),
            stream_options: Some(json!({"include_usage": true})),
            instructions: None,
            tools: None,
            tool_choice: None,
            parallel_tool_calls: None,
            max_tool_calls: None,
            previous_response_id: None,
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
            model: "gpt-4".to_string(),
            input: json!("Test"),
            stream: Some(false),
            stream_options: None,
            instructions: None,
            tools: None,
            tool_choice: None,
            parallel_tool_calls: None,
            max_tool_calls: None,
            previous_response_id: None,
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
            model: "gpt-4".to_string(),
            input: json!("Test"),
            metadata: Some(metadata.clone()),
            stream: None,
            stream_options: None,
            instructions: None,
            tools: None,
            tool_choice: None,
            parallel_tool_calls: None,
            max_tool_calls: None,
            previous_response_id: None,
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
            model: "gpt-4".to_string(),
            input: json!("Text input"),
            modalities: Some(vec!["text".to_string()]),
            stream: None,
            stream_options: None,
            instructions: None,
            tools: None,
            tool_choice: None,
            parallel_tool_calls: None,
            max_tool_calls: None,
            previous_response_id: None,
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
            model: "gpt-4o-audio".to_string(),
            input: json!([
                {"type": "text", "text": "Describe this image"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
            ]),
            modalities: Some(vec!["text".to_string(), "audio".to_string()]),
            stream: None,
            stream_options: None,
            instructions: None,
            tools: None,
            tool_choice: None,
            parallel_tool_calls: None,
            max_tool_calls: None,
            previous_response_id: None,
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
            model: "gpt-4".to_string(),
            input: json!("What's the weather in New York?"),
            tools: Some(tools.clone()),
            tool_choice: Some(json!("auto")),
            parallel_tool_calls: Some(true),
            max_tool_calls: Some(3),
            stream: None,
            stream_options: None,
            instructions: None,
            previous_response_id: None,
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
    let response =
        inference_handler(State(app_state), headers, StructuredJson(openai_params)).await?;

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
        let anthropic_stream = stream.map(|chunk| {
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
                            Err(_) => bytes,
                        }
                    }
                } else {
                    bytes
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
