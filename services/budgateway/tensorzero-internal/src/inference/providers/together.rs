#![allow(clippy::allow_attributes)]

use std::{borrow::Cow, collections::HashMap, sync::OnceLock, time::Duration};

use futures::StreamExt;
use lazy_static::lazy_static;
use reqwest::StatusCode;
use reqwest_eventsource::{Event, EventSource, RequestBuilderExt};
use secrecy::{ExposeSecret, SecretString};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::time::Instant;
use url::Url;

use crate::cache::ModelProviderRequest;
use crate::embeddings::{
    EmbeddingInput, EmbeddingProvider, EmbeddingProviderResponse, EmbeddingRequest,
};
use crate::error::DisplayOrDebugGateway;
use crate::inference::types::{
    FinishReason, Latency, ModelInferenceRequest, ModelInferenceRequestJsonMode,
    PeekableProviderInferenceResponseStream, ProviderInferenceResponse,
    ProviderInferenceResponseArgs,
};
use crate::model::{build_creds_caching_default, Credential, CredentialLocation, ModelProvider};
use crate::tool::ToolChoice;
use crate::{
    audio::{
        AudioOutputFormat, AudioVoice, TextToSpeechProvider, TextToSpeechProviderResponse,
        TextToSpeechRequest,
    },
    endpoints::inference::InferenceCredentials,
    error::{Error, ErrorDetails},
    images::{
        ImageData, ImageGenerationProvider, ImageGenerationProviderResponse, ImageGenerationRequest,
    },
    inference::types::{
        batch::{BatchRequestRow, PollBatchInferenceResponse, StartBatchProviderInferenceResponse},
        ContentBlockChunk, ContentBlockOutput, ProviderInferenceResponseChunk,
        ProviderInferenceResponseStreamInner, Text, TextChunk, Thought, ThoughtChunk, Usage,
    },
    tool::{ToolCall, ToolCallChunk},
};

use super::helpers::{handle_reqwest_error, inject_extra_request_data};
use super::helpers_thinking_block::{process_think_blocks, ThinkingState};
use super::{
    openai::{
        get_chat_url, handle_openai_error, prepare_openai_tools, tensorzero_to_openai_messages,
        OpenAIRequestMessage, OpenAISystemRequestMessage, OpenAITool, OpenAIToolChoice,
        OpenAIToolType, OpenAIUsage,
    },
    provider_trait::InferenceProvider,
};

lazy_static! {
    static ref TOGETHER_API_BASE: Url = {
        #[expect(clippy::expect_used)]
        Url::parse("https://api.together.xyz/v1").expect("Failed to parse TOGETHER_API_BASE")
    };
}

const PROVIDER_NAME: &str = "Together";
const PROVIDER_TYPE: &str = "together";

#[derive(Debug)]
pub struct TogetherProvider {
    model_name: String,
    credentials: TogetherCredentials,
    parse_think_blocks: bool,
}

pub fn default_parse_think_blocks() -> bool {
    true
}

static DEFAULT_CREDENTIALS: OnceLock<TogetherCredentials> = OnceLock::new();

impl TogetherProvider {
    pub fn new(
        model_name: String,
        api_key_location: Option<CredentialLocation>,
        parse_think_blocks: bool,
    ) -> Result<Self, Error> {
        let credentials = build_creds_caching_default(
            api_key_location,
            default_api_key_location(),
            PROVIDER_TYPE,
            &DEFAULT_CREDENTIALS,
        )?;
        Ok(TogetherProvider {
            model_name,
            credentials,
            parse_think_blocks,
        })
    }

    pub fn model_name(&self) -> &str {
        &self.model_name
    }
}

fn default_api_key_location() -> CredentialLocation {
    CredentialLocation::Env("TOGETHER_API_KEY".to_string())
}

#[derive(Clone, Debug)]
pub enum TogetherCredentials {
    Static(SecretString),
    Dynamic(String),
    None,
}

impl TryFrom<Credential> for TogetherCredentials {
    type Error = Error;

    fn try_from(credentials: Credential) -> Result<Self, Error> {
        match credentials {
            Credential::Static(key) => Ok(TogetherCredentials::Static(key)),
            Credential::Dynamic(key_name) => Ok(TogetherCredentials::Dynamic(key_name)),
            Credential::Missing => Ok(TogetherCredentials::None),
            _ => Err(Error::new(ErrorDetails::Config {
                message: "Invalid api_key_location for Together provider".to_string(),
            })),
        }
    }
}

impl TogetherCredentials {
    pub fn get_api_key<'a>(
        &'a self,
        dynamic_api_keys: &'a InferenceCredentials,
    ) -> Result<Cow<'a, SecretString>, Error> {
        match self {
            TogetherCredentials::Static(api_key) => Ok(Cow::Owned(api_key.clone())),
            TogetherCredentials::Dynamic(key_name) => {
                Ok(Cow::Borrowed(dynamic_api_keys.get(key_name).ok_or_else(
                    || ErrorDetails::ApiKeyMissing {
                        provider_name: PROVIDER_NAME.to_string(),
                    },
                )?))
            }
            TogetherCredentials::None => Err(ErrorDetails::ApiKeyMissing {
                provider_name: PROVIDER_NAME.to_string(),
            })?,
        }
    }
}

impl InferenceProvider for TogetherProvider {
    async fn infer<'a>(
        &'a self,
        ModelProviderRequest {
            request,
            provider_name: _,
            model_name,
        }: ModelProviderRequest<'a>,
        http_client: &'a reqwest::Client,
        dynamic_api_keys: &'a InferenceCredentials,
        model_provider: &'a ModelProvider,
    ) -> Result<ProviderInferenceResponse, Error> {
        let mut request_body =
            serde_json::to_value(TogetherRequest::new(&self.model_name, request)?).map_err(
                |e| {
                    Error::new(ErrorDetails::Serialization {
                        message: format!(
                            "Error serializing Together request: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                    })
                },
            )?;
        let headers = inject_extra_request_data(
            &request.extra_body,
            &request.extra_headers,
            model_provider,
            model_name,
            &mut request_body,
        )?;
        let request_url = get_chat_url(&TOGETHER_API_BASE)?;
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let start_time = Instant::now();
        let res = http_client
            .post(request_url)
            .header("Content-Type", "application/json")
            .bearer_auth(api_key.expose_secret())
            .json(&request_body)
            .headers(headers)
            .send()
            .await
            .map_err(|e| {
                Error::new(ErrorDetails::InferenceClient {
                    status_code: Some(e.status().unwrap_or(StatusCode::INTERNAL_SERVER_ERROR)),
                    message: format!("{}", DisplayOrDebugGateway::new(e)),
                    raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;
        if res.status().is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing text response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            let response = serde_json::from_str(&raw_response).map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing JSON response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                    raw_response: Some(raw_response.clone()),
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            Ok(TogetherResponseWithMetadata {
                response,
                raw_response,
                latency: Latency::NonStreaming {
                    response_time: start_time.elapsed(),
                },
                request: request_body,
                generic_request: request,
                parse_think_blocks: self.parse_think_blocks,
            }
            .try_into()?)
        } else {
            let status = res.status();
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing error response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;
            Err(handle_openai_error(
                &serde_json::to_string(&request_body).unwrap_or_default(),
                status,
                &raw_response,
                PROVIDER_TYPE,
            ))
        }
    }

    async fn infer_stream<'a>(
        &'a self,
        ModelProviderRequest {
            request,
            provider_name: _,
            model_name,
        }: ModelProviderRequest<'a>,
        http_client: &'a reqwest::Client,
        dynamic_api_keys: &'a InferenceCredentials,
        model_provider: &'a ModelProvider,
    ) -> Result<(PeekableProviderInferenceResponseStream, String), Error> {
        let mut request_body =
            serde_json::to_value(TogetherRequest::new(&self.model_name, request)?).map_err(
                |e| {
                    Error::new(ErrorDetails::Serialization {
                        message: format!(
                            "Error serializing request: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                    })
                },
            )?;
        let headers = inject_extra_request_data(
            &request.extra_body,
            &request.extra_headers,
            model_provider,
            model_name,
            &mut request_body,
        )?;
        let raw_request = serde_json::to_string(&request_body).map_err(|e| {
            Error::new(ErrorDetails::Serialization {
                message: format!(
                    "Error serializing request: {}",
                    DisplayOrDebugGateway::new(e)
                ),
            })
        })?;
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let request_url = get_chat_url(&TOGETHER_API_BASE)?;
        let start_time = Instant::now();
        let event_source = http_client
            .post(request_url)
            .header("Content-Type", "application/json")
            .bearer_auth(api_key.expose_secret())
            .json(&request_body)
            .headers(headers)
            .eventsource()
            .map_err(|e| {
                Error::new(ErrorDetails::InferenceClient {
                    message: format!(
                        "Error sending request to Together: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    status_code: None,
                    raw_request: Some(raw_request.clone()),
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;
        let stream = stream_together(event_source, start_time, self.parse_think_blocks).peekable();
        Ok((stream, raw_request))
    }

    async fn start_batch_inference<'a>(
        &'a self,
        _requests: &'a [ModelInferenceRequest<'_>],
        _client: &'a reqwest::Client,
        _dynamic_api_keys: &'a InferenceCredentials,
    ) -> Result<StartBatchProviderInferenceResponse, Error> {
        Err(ErrorDetails::UnsupportedModelProviderForBatchInference {
            provider_type: PROVIDER_TYPE.to_string(),
        }
        .into())
    }

    async fn poll_batch_inference<'a>(
        &'a self,
        _batch_request: &'a BatchRequestRow<'a>,
        _http_client: &'a reqwest::Client,
        _dynamic_api_keys: &'a InferenceCredentials,
    ) -> Result<PollBatchInferenceResponse, Error> {
        Err(ErrorDetails::UnsupportedModelProviderForBatchInference {
            provider_type: "GCP Vertex Gemini".to_string(),
        }
        .into())
    }
}

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
#[serde(tag = "type")]
enum TogetherResponseFormat<'a> {
    JsonObject {
        #[serde(skip_serializing_if = "Option::is_none")]
        schema: Option<&'a Value>, // the desired JSON schema
    },
}

/// This struct defines the supported parameters for the Together inference API
/// See the [Together API documentation](https://docs.together.ai/docs/chat-overview)
/// for more details.
/// We are not handling logprobs, top_logprobs, n, prompt_truncate_len
/// presence_penalty, frequency_penalty, seed, service_tier, stop, user,
/// or context_length_exceeded_behavior
#[derive(Debug, Serialize)]
struct TogetherRequest<'a> {
    messages: Vec<OpenAIRequestMessage<'a>>,
    model: &'a str,
    #[serde(skip_serializing_if = "Option::is_none")]
    temperature: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    top_p: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    presence_penalty: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    frequency_penalty: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    max_tokens: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    seed: Option<u32>,
    stream: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    response_format: Option<TogetherResponseFormat<'a>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tools: Option<Vec<OpenAITool<'a>>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool_choice: Option<OpenAIToolChoice<'a>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    parallel_tool_calls: Option<bool>,
}

impl<'a> TogetherRequest<'a> {
    pub fn new(
        model: &'a str,
        request: &'a ModelInferenceRequest<'_>,
    ) -> Result<TogetherRequest<'a>, Error> {
        let response_format = match request.json_mode {
            ModelInferenceRequestJsonMode::On | ModelInferenceRequestJsonMode::Strict => {
                Some(TogetherResponseFormat::JsonObject {
                    schema: request.output_schema,
                })
            }
            ModelInferenceRequestJsonMode::Off => None,
        };
        let messages = prepare_together_messages(request)?;

        // NOTE: Together AI doesn't seem to support `tool_choice="none"`, so we simply don't include the `tools` field if that's the case
        let tool_choice = request
            .tool_config
            .as_ref()
            .map(|config| &config.tool_choice);

        let (tools, tool_choice, parallel_tool_calls) = match tool_choice {
            Some(&ToolChoice::None) => (None, None, None),
            _ => prepare_openai_tools(request),
        };

        Ok(TogetherRequest {
            messages,
            model,
            temperature: request.temperature,
            top_p: request.top_p,
            presence_penalty: request.presence_penalty,
            frequency_penalty: request.frequency_penalty,
            max_tokens: request.max_tokens,
            seed: request.seed,
            stream: request.stream,
            response_format,
            tools,
            tool_choice,
            parallel_tool_calls,
        })
    }
}

pub(super) fn prepare_together_messages<'a>(
    request: &'a ModelInferenceRequest<'_>,
) -> Result<Vec<OpenAIRequestMessage<'a>>, Error> {
    let mut messages = Vec::with_capacity(request.messages.len());
    for message in request.messages.iter() {
        messages.extend(tensorzero_to_openai_messages(message)?);
    }

    if let Some(system_msg) = tensorzero_to_together_system_message(request.system.as_deref()) {
        messages.insert(0, system_msg);
    }
    Ok(messages)
}

fn tensorzero_to_together_system_message(system: Option<&str>) -> Option<OpenAIRequestMessage<'_>> {
    system.map(|instructions| {
        OpenAIRequestMessage::System(OpenAISystemRequestMessage {
            content: Cow::Borrowed(instructions),
        })
    })
}

#[derive(Serialize, Debug, Clone, PartialEq, Deserialize)]
struct TogetherResponseFunctionCall {
    name: String,
    arguments: String,
}

#[derive(Serialize, Debug, Clone, PartialEq, Deserialize)]
struct TogetherResponseToolCall {
    id: String,
    r#type: OpenAIToolType,
    function: TogetherResponseFunctionCall,
}

impl From<TogetherResponseToolCall> for ToolCall {
    fn from(together_tool_call: TogetherResponseToolCall) -> Self {
        ToolCall {
            id: together_tool_call.id,
            name: together_tool_call.function.name,
            arguments: together_tool_call.function.arguments,
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
struct TogetherResponseMessage {
    #[serde(skip_serializing_if = "Option::is_none")]
    content: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool_calls: Option<Vec<TogetherResponseToolCall>>,
}

// The thinking block processing has been moved to helpers_thinking_block.rs

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
#[serde(rename_all = "snake_case")]
enum TogetherFinishReason {
    Stop,
    Eos,
    Length,
    ToolCalls,
    FunctionCall,
    #[serde(other)]
    Unknown,
}

impl From<TogetherFinishReason> for FinishReason {
    fn from(finish_reason: TogetherFinishReason) -> Self {
        match finish_reason {
            TogetherFinishReason::Stop => FinishReason::Stop,
            TogetherFinishReason::Eos => FinishReason::Stop,
            TogetherFinishReason::Length => FinishReason::Length,
            TogetherFinishReason::ToolCalls => FinishReason::ToolCall,
            TogetherFinishReason::FunctionCall => FinishReason::ToolCall,
            TogetherFinishReason::Unknown => FinishReason::Unknown,
        }
    }
}

// Leaving out logprobs and finish_reason for now
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
struct TogetherResponseChoice {
    index: u8,
    message: TogetherResponseMessage,
    finish_reason: Option<TogetherFinishReason>,
}

// Leaving out id, created, model, service_tier, system_fingerprint, object for now
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
struct TogetherResponse {
    choices: Vec<TogetherResponseChoice>,
    usage: OpenAIUsage,
}

struct TogetherResponseWithMetadata<'a> {
    response: TogetherResponse,
    latency: Latency,
    raw_response: String,
    request: serde_json::Value,
    generic_request: &'a ModelInferenceRequest<'a>,
    parse_think_blocks: bool,
}

impl<'a> TryFrom<TogetherResponseWithMetadata<'a>> for ProviderInferenceResponse {
    type Error = Error;
    fn try_from(value: TogetherResponseWithMetadata<'a>) -> Result<Self, Self::Error> {
        let TogetherResponseWithMetadata {
            mut response,
            latency,
            raw_response,
            request: request_body,
            generic_request,
            parse_think_blocks,
        } = value;
        if response.choices.len() != 1 {
            return Err(ErrorDetails::InferenceServer {
                message: format!(
                    "Response has invalid number of choices: {}. Expected 1.",
                    response.choices.len()
                ),
                raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                raw_response: Some(raw_response.clone()),
                provider_type: PROVIDER_TYPE.to_string(),
            }
            .into());
        }
        let usage = response.usage.into();
        let TogetherResponseChoice {
            message,
            finish_reason,
            ..
        } = response
            .choices
            .pop()
            .ok_or_else(|| Error::new(ErrorDetails::InferenceServer {
                message: "Response has no choices (this should never happen). Please file a bug report: https://github.com/tensorzero/tensorzero/issues/new".to_string(),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                raw_response: Some(raw_response.clone()),
            }))?;
        let mut content: Vec<ContentBlockOutput> = Vec::new();
        if let Some(raw_text) = message.content {
            let (clean_text, extracted_reasoning) =
                process_think_blocks(&raw_text, parse_think_blocks, PROVIDER_TYPE)?;
            if let Some(reasoning) = extracted_reasoning {
                content.push(ContentBlockOutput::Thought(Thought {
                    text: reasoning,
                    signature: None,
                }));
            }
            if !clean_text.is_empty() {
                content.push(ContentBlockOutput::Text(Text { text: clean_text }));
            }
        }
        if let Some(tool_calls) = message.tool_calls {
            for tool_call in tool_calls {
                content.push(ContentBlockOutput::ToolCall(tool_call.into()));
            }
        }
        let raw_request = serde_json::to_string(&request_body).map_err(|e| {
            Error::new(ErrorDetails::Serialization {
                message: format!(
                    "Error serializing request body as JSON: {}",
                    DisplayOrDebugGateway::new(e)
                ),
            })
        })?;
        let system = generic_request.system.clone();
        let input_messages = generic_request.messages.clone();
        Ok(ProviderInferenceResponse::new(
            ProviderInferenceResponseArgs {
                output: content,
                system,
                input_messages,
                raw_request,
                raw_response: raw_response.clone(),
                usage,
                latency,
                finish_reason: finish_reason.map(|r| r.into()),
            },
        ))
    }
}

// ThinkingState has been moved to helpers_thinking_block.rs

fn stream_together(
    mut event_source: EventSource,
    start_time: Instant,
    parse_think_blocks: bool,
) -> ProviderInferenceResponseStreamInner {
    let mut tool_call_ids = Vec::new();
    let mut tool_call_names = Vec::new();
    let mut thinking_state = ThinkingState::Normal;
    Box::pin(async_stream::stream! {
        while let Some(ev) = event_source.next().await {
            match ev {
                Err(e) => {
                    let message = e.to_string();
                    let mut raw_response = None;
                    if let reqwest_eventsource::Error::InvalidStatusCode(_, resp) = e {
                        raw_response = resp.text().await.ok();
                    }
                    yield Err(ErrorDetails::InferenceServer {
                        message,
                        raw_request: None,
                        raw_response,
                        provider_type: PROVIDER_TYPE.to_string(),
                    }.into());
                }
                Ok(event) => match event {
                    Event::Open => continue,
                    Event::Message(message) => {
                        if message.data == "[DONE]" {
                            break;
                        }
                        let data: Result<TogetherChatChunk, Error> =
                            serde_json::from_str(&message.data).map_err(|e| Error::new(ErrorDetails::InferenceServer {
                                message: format!("Error parsing chunk. Error: {e}"),
                                raw_request: None,
                                raw_response: Some(message.data.clone()),
                                provider_type: PROVIDER_TYPE.to_string(),
                            }));

                        let latency = start_time.elapsed();
                        let stream_message = data.and_then(|d| {
                            together_to_tensorzero_chunk(message.data, d, latency, &mut tool_call_ids, &mut tool_call_names, &mut thinking_state, parse_think_blocks)
                        });
                        yield stream_message;
                    }
                },
            }
        }

        event_source.close();
    })
}

/// Maps a Together chunk to a TensorZero chunk for streaming inferences
///
/// This function handles the conversion of Together chat chunks into TensorZero chunks.
/// It processes the content and tool calls from the Together response, updating the tool call IDs and names.
/// If parsing think blocks is enabled, it also processes the thinking state and extracts reasoning.
fn together_to_tensorzero_chunk(
    raw_message: String,
    mut chunk: TogetherChatChunk,
    latency: Duration,
    tool_call_ids: &mut Vec<String>,
    tool_call_names: &mut Vec<String>,
    thinking_state: &mut ThinkingState,
    parse_think_blocks: bool,
) -> Result<ProviderInferenceResponseChunk, Error> {
    if chunk.choices.len() > 1 {
        return Err(ErrorDetails::InferenceServer {
            message: "Response has invalid number of choices: {}. Expected 1.".to_string(),
            raw_request: None,
            raw_response: Some(serde_json::to_string(&chunk).unwrap_or_default()),
            provider_type: PROVIDER_TYPE.to_string(),
        }
        .into());
    }
    let usage = chunk.usage.map(|u| u.into());
    let mut finish_reason = None;
    let mut content = vec![];
    if let Some(choice) = chunk.choices.pop() {
        if let Some(reason) = choice.finish_reason {
            finish_reason = Some(reason.into());
        }
        if let Some(text) = choice.delta.content {
            if parse_think_blocks {
                if !thinking_state.update(&text, PROVIDER_TYPE)? {
                    match thinking_state {
                        ThinkingState::Normal | ThinkingState::Finished => {
                            content.push(ContentBlockChunk::Text(TextChunk {
                                text,
                                id: thinking_state.get_id(),
                            }));
                        }
                        ThinkingState::Thinking => {
                            content.push(ContentBlockChunk::Thought(ThoughtChunk {
                                text: Some(text),
                                signature: None,
                                id: thinking_state.get_id(),
                            }));
                        }
                    }
                }
            } else {
                // Just add the text verbatim if we're not parsing think blocks.
                content.push(ContentBlockChunk::Text(TextChunk {
                    text,
                    id: "0".to_string(),
                }));
            }
        }
        if let Some(tool_calls) = choice.delta.tool_calls {
            for tool_call in tool_calls {
                let index = tool_call.index;
                let id = match tool_call.id {
                    Some(id) => {
                        tool_call_ids.push(id.clone());
                        id
                    }
                    None => {
                        tool_call_ids
                            .get(index as usize)
                            .ok_or_else(|| Error::new(ErrorDetails::InferenceServer {
                                message: "Tool call index out of bounds (meaning we haven't seen this many ids in the stream)".to_string(),
                                raw_request: None,
                                raw_response: None,
                                provider_type: PROVIDER_TYPE.to_string(),
                            }))?
                            .clone()
                    }
                };
                let name = match tool_call.function.name {
                    Some(name) => {
                        tool_call_names.push(name.clone());
                        name
                    }
                    None => {
                        tool_call_names
                            .get(index as usize)
                            .ok_or_else(|| Error::new(ErrorDetails::InferenceServer {
                                message: "Tool call index out of bounds (meaning we haven't seen this many names in the stream)".to_string(),
                                raw_request: None,
                                raw_response: None,
                                provider_type: PROVIDER_TYPE.to_string(),
                            }))?
                            .clone()
                    }
                };
                content.push(ContentBlockChunk::ToolCall(ToolCallChunk {
                    id,
                    raw_name: name,
                    raw_arguments: tool_call.function.arguments.unwrap_or_default(),
                }));
            }
        }
    }

    Ok(ProviderInferenceResponseChunk::new(
        content,
        usage,
        raw_message,
        latency,
        finish_reason,
    ))
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
struct TogetherFunctionCallChunk {
    #[serde(skip_serializing_if = "Option::is_none")]
    name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    arguments: Option<String>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
struct TogetherToolCallChunk {
    index: u8,
    #[serde(skip_serializing_if = "Option::is_none")]
    id: Option<String>,
    // NOTE: these are externally tagged enums, for now we're gonna just keep this hardcoded as there's only one option
    // If we were to do this better, we would need to check the type field
    function: TogetherFunctionCallChunk,
}

// This doesn't include role
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
struct TogetherDelta {
    #[serde(skip_serializing_if = "Option::is_none")]
    content: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool_calls: Option<Vec<TogetherToolCallChunk>>,
}

// This doesn't include logprobs, finish_reason, and index
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
struct TogetherChatChunkChoice {
    delta: TogetherDelta,
    finish_reason: Option<TogetherFinishReason>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
struct TogetherChatChunk {
    choices: Vec<TogetherChatChunkChoice>,
    #[serde(skip_serializing_if = "Option::is_none")]
    usage: Option<OpenAIUsage>,
}

// Together Embedding types
#[derive(Debug, Serialize)]
struct TogetherEmbeddingRequest<'a> {
    model: &'a str,
    input: TogetherEmbeddingInput<'a>,
    #[serde(skip_serializing_if = "Option::is_none")]
    encoding_format: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    dimensions: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    modality: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    priority: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    include_input: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    chunking: Option<&'a crate::embeddings::ChunkingConfig>,
    #[serde(flatten, skip_serializing_if = "HashMap::is_empty")]
    extra: HashMap<String, Value>,
}

#[derive(Debug, Serialize)]
#[serde(untagged)]
enum TogetherEmbeddingInput<'a> {
    Single(&'a str),
    Batch(Vec<&'a str>),
}

impl<'a> TogetherEmbeddingRequest<'a> {
    fn new(model: &'a str, request: &'a EmbeddingRequest) -> Self {
        let input = match &request.input {
            EmbeddingInput::Single(text) => TogetherEmbeddingInput::Single(text),
            EmbeddingInput::Batch(texts) => {
                TogetherEmbeddingInput::Batch(texts.iter().map(|s| s.as_str()).collect())
            }
        };
        Self {
            model,
            input,
            encoding_format: request.encoding_format.as_deref(),
            dimensions: request.dimensions,
            modality: request.modality.as_deref(),
            priority: request.priority.as_deref(),
            include_input: request.include_input,
            chunking: request.chunking.as_ref(),
            extra: request.extra.clone(),
        }
    }
}

#[derive(Debug, Deserialize)]
struct TogetherEmbeddingResponse {
    data: Vec<TogetherEmbeddingData>,
    usage: OpenAIUsage,
}

#[derive(Debug, Deserialize)]
struct TogetherEmbeddingData {
    embedding: Vec<f32>,
}

fn get_embedding_url(base_url: &Url) -> Result<Url, Error> {
    base_url.join("embeddings").map_err(|e| {
        Error::new(ErrorDetails::InvalidBaseUrl {
            message: e.to_string(),
        })
    })
}

// Audio TTS types
#[derive(Debug, Serialize)]
struct TogetherTextToSpeechRequest<'a> {
    model: Cow<'a, str>,
    input: Cow<'a, str>,
    voice: Cow<'a, str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    response_format: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    sample_rate: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    stream: Option<bool>,
}

fn map_audio_voice_to_together(voice: &AudioVoice) -> Cow<'static, str> {
    match voice {
        AudioVoice::Alloy => Cow::Borrowed("helpful woman"),
        AudioVoice::Echo => Cow::Borrowed("laidback woman"),
        AudioVoice::Fable => Cow::Borrowed("meditation lady"),
        AudioVoice::Onyx => Cow::Borrowed("newsman"),
        AudioVoice::Nova => Cow::Borrowed("friendly sidekick"),
        AudioVoice::Shimmer => Cow::Borrowed("british reading lady"),
        AudioVoice::Ash => Cow::Borrowed("barbershop man"),
        AudioVoice::Ballad => Cow::Borrowed("indian lady"),
        AudioVoice::Coral => Cow::Borrowed("german conversational woman"),
        AudioVoice::Sage => Cow::Borrowed("pilot over intercom"),
        AudioVoice::Verse => Cow::Borrowed("australian customer support man"),
        AudioVoice::Other(voice_name) => Cow::Owned(voice_name.clone()),
    }
}

fn get_audio_speech_url(base_url: &Url) -> Result<Url, Error> {
    let mut url = base_url.clone();
    if !url.path().ends_with('/') {
        url.set_path(&format!("{}/", url.path()));
    }
    url.join("audio/generations").map_err(|e| {
        Error::new(ErrorDetails::InvalidBaseUrl {
            message: e.to_string(),
        })
    })
}

// Image generation types
#[derive(Debug, Serialize)]
struct TogetherImageGenerationRequest {
    model: String,
    prompt: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    n: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    size: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    response_format: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    user: Option<String>,
    // Together-specific parameters
    #[serde(skip_serializing_if = "Option::is_none")]
    steps: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    disable_safety_checker: Option<bool>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
struct TogetherImageResponse {
    id: String,
    model: String,
    object: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    created: Option<u64>,
    data: Vec<TogetherImageData>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
struct TogetherImageData {
    index: u32,
    url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    b64_json: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    revised_prompt: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    timings: Option<TogetherImageTimings>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
struct TogetherImageTimings {
    inference: f64,
}

fn get_image_generation_url(base_url: &Url) -> Result<Url, Error> {
    let mut url = base_url.clone();
    if !url.path().ends_with('/') {
        url.set_path(&format!("{}/", url.path()));
    }
    url.join("images/generations").map_err(|e| {
        Error::new(ErrorDetails::InvalidBaseUrl {
            message: e.to_string(),
        })
    })
}

impl EmbeddingProvider for TogetherProvider {
    async fn embed(
        &self,
        request: &EmbeddingRequest,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<EmbeddingProviderResponse, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let request_body = TogetherEmbeddingRequest::new(&self.model_name, request);

        // Serialize request body once at the beginning
        let raw_request = serde_json::to_string(&request_body).map_err(|e| {
            Error::new(ErrorDetails::Serialization {
                message: format!(
                    "Error serializing request body as JSON: {}",
                    DisplayOrDebugGateway::new(e)
                ),
            })
        })?;

        let request_url = get_embedding_url(&TOGETHER_API_BASE)?;
        let start_time = Instant::now();

        let request_builder = client
            .post(request_url)
            .header("Content-Type", "application/json")
            .bearer_auth(api_key.expose_secret());

        let res = request_builder
            .body(raw_request.clone())
            .send()
            .await
            .map_err(|e| {
                Error::new(ErrorDetails::InferenceClient {
                    status_code: e.status(),
                    message: format!(
                        "Error sending request to Together: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    provider_type: PROVIDER_TYPE.to_string(),
                    raw_request: Some(raw_request.clone()),
                    raw_response: None,
                })
            })?;

        let status = res.status();
        if status.is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing text response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: Some(raw_request.clone()),
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            let response: TogetherEmbeddingResponse =
                serde_json::from_str(&raw_response).map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing JSON response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: Some(raw_request.clone()),
                        raw_response: Some(raw_response.clone()),
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?;

            let latency = Latency::NonStreaming {
                response_time: start_time.elapsed(),
            };

            let embeddings: Vec<Vec<f32>> = response
                .data
                .into_iter()
                .map(|data| data.embedding)
                .collect();

            let usage = Usage::from(response.usage);

            Ok(EmbeddingProviderResponse::new(
                embeddings,
                request.input.clone(),
                raw_request,
                raw_response,
                usage,
                latency,
            ))
        } else {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing error response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: Some(raw_request.clone()),
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;
            Err(handle_openai_error(
                &raw_request,
                status,
                &raw_response,
                PROVIDER_TYPE,
            ))
        }
    }
}

// Image generation implementation
impl ImageGenerationProvider for TogetherProvider {
    async fn generate_image(
        &self,
        request: &ImageGenerationRequest,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<ImageGenerationProviderResponse, Error> {
        let start_time = Instant::now();
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let url = get_image_generation_url(&TOGETHER_API_BASE)?;

        // Build Together-specific request
        let together_request = TogetherImageGenerationRequest {
            model: self.model_name.clone(),
            prompt: request.prompt.clone(),
            n: request.n,
            size: request.size.as_ref().map(|s| s.as_str().to_string()),
            response_format: request
                .response_format
                .as_ref()
                .map(|f| f.as_str().to_string()),
            user: request.user.clone(),
            // Together-specific defaults
            steps: None,                  // Let Together use default
            disable_safety_checker: None, // Let Together use default
        };

        let request_json = serde_json::to_string(&together_request).map_err(|e| {
            Error::new(ErrorDetails::Serialization {
                message: format!("Failed to serialize Together image generation request: {e}"),
            })
        })?;

        let request_builder = client
            .post(url)
            .header("Content-Type", "application/json")
            .bearer_auth(api_key.expose_secret())
            .body(request_json.clone());

        let res = request_builder
            .send()
            .await
            .map_err(|e| handle_reqwest_error(e, PROVIDER_TYPE, Some(request_json.clone())))?;

        let latency = Latency::NonStreaming {
            response_time: start_time.elapsed(),
        };

        if res.status().is_success() {
            let response_body = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceClient {
                    message: format!("Failed to read Together image generation response: {e}"),
                    status_code: None,
                    raw_request: Some(request_json.clone()),
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            let response: TogetherImageResponse =
                serde_json::from_str(&response_body).map_err(|e| {
                    Error::new(ErrorDetails::InferenceClient {
                        message: format!("Failed to parse Together image generation response: {e}"),
                        status_code: None,
                        raw_request: Some(request_json.clone()),
                        raw_response: Some(response_body.clone()),
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?;

            Ok(ImageGenerationProviderResponse {
                id: request.id,
                created: response.created.unwrap_or_else(|| {
                    // Use current timestamp if not provided
                    std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .unwrap_or_default()
                        .as_secs()
                }),
                data: response
                    .data
                    .into_iter()
                    .map(|d| ImageData {
                        url: d.url,
                        b64_json: d.b64_json,
                        revised_prompt: d.revised_prompt,
                    })
                    .collect(),
                raw_request: request_json,
                raw_response: response_body,
                usage: Usage {
                    input_tokens: 0, // Together doesn't provide token usage for images
                    output_tokens: 0,
                },
                latency,
            })
        } else {
            let status = res.status();
            let error_body = res.text().await.unwrap_or_else(|e| {
                tracing::error!("Failed to read error response body: {}", e);
                "Failed to read error response".to_string()
            });
            Err(handle_openai_error(
                &request_json,
                status,
                &error_body,
                PROVIDER_TYPE,
            ))
        }
    }
}

// Text-to-Speech implementation
impl TextToSpeechProvider for TogetherProvider {
    async fn generate_speech(
        &self,
        request: &TextToSpeechRequest,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<TextToSpeechProviderResponse, Error> {
        let start_time = Instant::now();
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let url = get_audio_speech_url(&TOGETHER_API_BASE)?;

        // Validate input
        if request.input.trim().is_empty() {
            return Err(Error::new(ErrorDetails::InvalidRequest {
                message: "Input text cannot be empty".to_string(),
            }));
        }

        // Validate input length (Together's limit is typically around 4096 characters)
        const MAX_INPUT_LENGTH: usize = 4096;
        if request.input.len() > MAX_INPUT_LENGTH {
            return Err(Error::new(ErrorDetails::InvalidRequest {
                message: format!(
                    "Input text is too long: {} characters. Maximum allowed: {} characters",
                    request.input.len(),
                    MAX_INPUT_LENGTH
                ),
            }));
        }

        // Map output format
        let response_format = match &request.response_format {
            Some(AudioOutputFormat::Mp3) | None => Some("mp3"),
            Some(AudioOutputFormat::Pcm) => Some("raw"),
            Some(format) => {
                return Err(Error::new(ErrorDetails::InvalidRequest {
                    message: format!(
                        "Together TTS does not support output format: {format:?}. Supported formats: mp3, raw (pcm)"
                    ),
                }));
            }
        };

        // Build Together-specific request
        let together_request = TogetherTextToSpeechRequest {
            model: Cow::Borrowed(&self.model_name),
            input: Cow::Borrowed(&request.input),
            voice: map_audio_voice_to_together(&request.voice),
            response_format,
            sample_rate: Some(44100), // Recommended sample rate
            stream: Some(false),      // TODO: Add streaming support in the future
        };

        let request_json = serde_json::to_string(&together_request).map_err(|e| {
            Error::new(ErrorDetails::Serialization {
                message: format!("Failed to serialize Together TTS request: {e}"),
            })
        })?;

        let request_builder = client
            .post(url)
            .header("Content-Type", "application/json")
            .bearer_auth(api_key.expose_secret())
            .body(request_json.clone());

        let res = request_builder
            .send()
            .await
            .map_err(|e| handle_reqwest_error(e, PROVIDER_TYPE, Some(request_json.clone())))?;

        let latency = Latency::NonStreaming {
            response_time: start_time.elapsed(),
        };

        if res.status().is_success() {
            let audio_data = res.bytes().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceClient {
                    message: format!("Failed to read Together TTS response: {e}"),
                    status_code: None,
                    raw_request: Some(request_json.clone()),
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            let output_format = request
                .response_format
                .clone()
                .unwrap_or(AudioOutputFormat::Mp3);

            Ok(TextToSpeechProviderResponse {
                id: request.id,
                audio_data: audio_data.to_vec(),
                format: output_format,
                created: std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_secs(),
                raw_request: request_json,
                usage: Usage {
                    input_tokens: 0, // Together doesn't provide token usage for TTS
                    output_tokens: 0,
                },
                latency,
            })
        } else {
            let status = res.status();
            let error_body = res.text().await.unwrap_or_else(|e| {
                tracing::error!("Failed to read error response body: {}", e);
                "Failed to read error response".to_string()
            });
            Err(handle_openai_error(
                &request_json,
                status,
                &error_body,
                PROVIDER_TYPE,
            ))
        }
    }
}

#[cfg(test)]
mod tests {
    use std::borrow::Cow;
    use std::time::Duration;

    use uuid::Uuid;

    use super::*;

    use crate::inference::providers::openai::{
        OpenAIToolType, OpenAIUsage, SpecificToolChoice, SpecificToolFunction,
    };
    use crate::inference::providers::test_helpers::{WEATHER_TOOL, WEATHER_TOOL_CONFIG};
    use crate::inference::types::{FunctionType, RequestMessage, Role, Usage};

    #[test]
    fn test_together_request_new() {
        let request_with_tools = ModelInferenceRequest {
            inference_id: Uuid::now_v7(),
            messages: vec![RequestMessage {
                role: Role::User,
                content: vec!["What's the weather?".to_string().into()],
            }],
            system: None,
            temperature: Some(0.5),
            top_p: Some(0.9),
            presence_penalty: Some(0.1),
            frequency_penalty: Some(0.1),
            max_tokens: Some(100),
            seed: Some(69),
            stream: false,
            json_mode: ModelInferenceRequestJsonMode::Off,
            tool_config: Some(Cow::Borrowed(&WEATHER_TOOL_CONFIG)),
            function_type: FunctionType::Chat,
            output_schema: None,
            extra_body: Default::default(),
            ..Default::default()
        };

        let together_request =
            TogetherRequest::new("togethercomputer/llama-v3-8b", &request_with_tools).unwrap();

        assert_eq!(together_request.model, "togethercomputer/llama-v3-8b");
        assert_eq!(together_request.messages.len(), 1);
        assert_eq!(together_request.temperature, Some(0.5));
        assert_eq!(together_request.top_p, Some(0.9));
        assert_eq!(together_request.presence_penalty, Some(0.1));
        assert_eq!(together_request.frequency_penalty, Some(0.1));
        assert_eq!(together_request.max_tokens, Some(100));
        assert_eq!(together_request.seed, Some(69));
        assert!(!together_request.stream);
        let tools = together_request.tools.as_ref().unwrap();
        assert_eq!(tools.len(), 1);
        assert_eq!(tools[0].function.name, WEATHER_TOOL.name());
        assert_eq!(tools[0].function.parameters, WEATHER_TOOL.parameters());
        assert_eq!(
            together_request.tool_choice,
            Some(OpenAIToolChoice::Specific(SpecificToolChoice {
                r#type: OpenAIToolType::Function,
                function: SpecificToolFunction {
                    name: WEATHER_TOOL.name(),
                }
            }))
        );
        assert_eq!(together_request.parallel_tool_calls, None);
    }

    #[test]
    fn test_together_api_base() {
        assert_eq!(TOGETHER_API_BASE.as_str(), "https://api.together.xyz/v1");
    }
    #[test]
    fn test_credential_to_together_credentials() {
        // Test Static credential
        let generic = Credential::Static(SecretString::from("test_key"));
        let creds: TogetherCredentials = TogetherCredentials::try_from(generic).unwrap();
        assert!(matches!(creds, TogetherCredentials::Static(_)));

        // Test Dynamic credential
        let generic = Credential::Dynamic("key_name".to_string());
        let creds = TogetherCredentials::try_from(generic).unwrap();
        assert!(matches!(creds, TogetherCredentials::Dynamic(_)));

        // Test Missing credential
        let generic = Credential::Missing;
        let creds = TogetherCredentials::try_from(generic).unwrap();
        assert!(matches!(creds, TogetherCredentials::None));

        // Test invalid type
        let generic = Credential::FileContents(SecretString::from("test"));
        let result = TogetherCredentials::try_from(generic);
        assert!(result.is_err());
        assert!(matches!(
            result.unwrap_err().get_owned_details(),
            ErrorDetails::Config { message } if message.contains("Invalid api_key_location")
        ));
    }

    #[test]
    fn test_together_response_with_metadata_try_into() {
        let valid_response = TogetherResponse {
            choices: vec![TogetherResponseChoice {
                index: 0,
                message: TogetherResponseMessage {
                    content: Some("Hello, world!".to_string()),
                    tool_calls: None,
                },
                finish_reason: None,
            }],
            usage: OpenAIUsage {
                prompt_tokens: 10,
                completion_tokens: 20,
                total_tokens: 30,
            },
        };
        let generic_request = ModelInferenceRequest {
            inference_id: Uuid::now_v7(),
            messages: vec![RequestMessage {
                role: Role::User,
                content: vec!["test_user".to_string().into()],
            }],
            system: None,
            temperature: Some(0.5),
            top_p: None,
            presence_penalty: None,
            frequency_penalty: None,
            max_tokens: Some(100),
            stream: false,
            seed: Some(69),
            json_mode: ModelInferenceRequestJsonMode::Off,
            tool_config: None,
            function_type: FunctionType::Chat,
            output_schema: None,
            extra_body: Default::default(),
            ..Default::default()
        };
        let together_response_with_metadata = TogetherResponseWithMetadata {
            response: valid_response,
            raw_response: "test_response".to_string(),
            latency: Latency::NonStreaming {
                response_time: Duration::from_secs(0),
            },
            request: serde_json::to_value(
                TogetherRequest::new("test-model", &generic_request).unwrap(),
            )
            .unwrap(),
            generic_request: &generic_request,
            parse_think_blocks: true,
        };
        let inference_response: ProviderInferenceResponse =
            together_response_with_metadata.try_into().unwrap();

        assert_eq!(inference_response.output.len(), 1);
        assert_eq!(
            inference_response.output[0],
            "Hello, world!".to_string().into()
        );
        assert_eq!(inference_response.raw_response, "test_response");
        assert_eq!(inference_response.usage.input_tokens, 10);
        assert_eq!(inference_response.usage.output_tokens, 20);
        assert_eq!(
            inference_response.latency,
            Latency::NonStreaming {
                response_time: Duration::from_secs(0)
            }
        );

        // Test case with thinking in the response
        let valid_response = TogetherResponse {
            choices: vec![TogetherResponseChoice {
                index: 0,
                message: TogetherResponseMessage {
                    content: Some("<think>hmmm</think>Hello, world!".to_string()),
                    tool_calls: None,
                },
                finish_reason: None,
            }],
            usage: OpenAIUsage {
                prompt_tokens: 10,
                completion_tokens: 20,
                total_tokens: 30,
            },
        };
        let together_response_with_metadata = TogetherResponseWithMetadata {
            response: valid_response,
            raw_response: "test_response".to_string(),
            latency: Latency::NonStreaming {
                response_time: Duration::from_secs(0),
            },
            request: serde_json::to_value(
                TogetherRequest::new("test-model", &generic_request).unwrap(),
            )
            .unwrap(),
            generic_request: &generic_request,
            parse_think_blocks: true,
        };
        let inference_response: ProviderInferenceResponse =
            together_response_with_metadata.try_into().unwrap();
        assert_eq!(inference_response.output.len(), 2);
        assert_eq!(
            inference_response.output[0],
            ContentBlockOutput::Thought(Thought {
                text: "hmmm".to_string(),
                signature: None,
            })
        );
        assert_eq!(
            inference_response.output[1],
            "Hello, world!".to_string().into()
        );
        assert_eq!(inference_response.raw_response, "test_response");

        // Test case with thinking in the middle of response
        let valid_response = TogetherResponse {
            choices: vec![TogetherResponseChoice {
                index: 0,
                message: TogetherResponseMessage {
                    content: Some("Hello <think>hmmm</think> world!".to_string()),
                    tool_calls: None,
                },
                finish_reason: None,
            }],
            usage: OpenAIUsage {
                prompt_tokens: 10,
                completion_tokens: 20,
                total_tokens: 30,
            },
        };
        let together_response_with_metadata = TogetherResponseWithMetadata {
            response: valid_response,
            raw_response: "test_response".to_string(),
            latency: Latency::NonStreaming {
                response_time: Duration::from_secs(0),
            },
            request: serde_json::to_value(
                TogetherRequest::new("test-model", &generic_request).unwrap(),
            )
            .unwrap(),
            generic_request: &generic_request,
            parse_think_blocks: true,
        };
        let inference_response: ProviderInferenceResponse =
            together_response_with_metadata.try_into().unwrap();
        assert_eq!(inference_response.output.len(), 2);
        assert_eq!(
            inference_response.output[0],
            ContentBlockOutput::Thought(Thought {
                text: "hmmm".to_string(),
                signature: None,
            })
        );
        assert_eq!(
            inference_response.output[1],
            "Hello  world!".to_string().into()
        );
        assert_eq!(inference_response.raw_response, "test_response");
    }

    #[test]
    fn test_together_think_block_parsing_in_response() {
        // Test how TogetherAI integration works with think blocks in response parsing
        let response_with_thinking = TogetherResponse {
            choices: vec![TogetherResponseChoice {
                index: 0,
                message: TogetherResponseMessage {
                    content: Some(
                        "<think>This is the reasoning process</think>This is the answer"
                            .to_string(),
                    ),
                    tool_calls: None,
                },
                finish_reason: None,
            }],
            usage: OpenAIUsage {
                prompt_tokens: 10,
                completion_tokens: 20,
                total_tokens: 30,
            },
        };

        let generic_request = ModelInferenceRequest {
            inference_id: Uuid::now_v7(),
            messages: vec![RequestMessage {
                role: Role::User,
                content: vec!["test_user".to_string().into()],
            }],
            system: None,
            temperature: Some(0.5),
            max_tokens: Some(100),
            stream: false,
            seed: Some(69),
            json_mode: ModelInferenceRequestJsonMode::Off,
            tool_config: None,
            function_type: FunctionType::Chat,
            output_schema: None,
            extra_body: Default::default(),
            ..Default::default()
        };

        // With parsing enabled
        let metadata = TogetherResponseWithMetadata {
            response: response_with_thinking.clone(),
            raw_response: "test_response".to_string(),
            latency: Latency::NonStreaming {
                response_time: Duration::from_secs(0),
            },
            request: serde_json::to_value(
                TogetherRequest::new("test-model", &generic_request).unwrap(),
            )
            .unwrap(),
            generic_request: &generic_request,
            parse_think_blocks: true,
        };

        let inference_response: ProviderInferenceResponse = metadata.try_into().unwrap();

        // We should have two content blocks - one thought and one text
        assert_eq!(inference_response.output.len(), 2);

        // First block should be the thought
        assert!(matches!(
            inference_response.output[0],
            ContentBlockOutput::Thought(_)
        ));
        if let ContentBlockOutput::Thought(thought) = &inference_response.output[0] {
            assert_eq!(thought.text, "This is the reasoning process");
            assert_eq!(thought.signature, None);
        }

        // Second block should be the text
        assert!(matches!(
            inference_response.output[1],
            ContentBlockOutput::Text(_)
        ));
        if let ContentBlockOutput::Text(text) = &inference_response.output[1] {
            assert_eq!(text.text, "This is the answer");
        }

        // With parsing disabled
        let metadata = TogetherResponseWithMetadata {
            response: response_with_thinking,
            raw_response: "test_response".to_string(),
            latency: Latency::NonStreaming {
                response_time: Duration::from_secs(0),
            },
            request: serde_json::to_value(
                TogetherRequest::new("test-model", &generic_request).unwrap(),
            )
            .unwrap(),
            generic_request: &generic_request,
            parse_think_blocks: false,
        };

        let inference_response: ProviderInferenceResponse = metadata.try_into().unwrap();

        // We should have one content block with the raw text
        assert_eq!(inference_response.output.len(), 1);
        assert!(matches!(
            inference_response.output[0],
            ContentBlockOutput::Text(_)
        ));
        if let ContentBlockOutput::Text(text) = &inference_response.output[0] {
            assert_eq!(
                text.text,
                "<think>This is the reasoning process</think>This is the answer"
            );
        }
    }

    #[test]
    fn test_together_to_tensorzero_chunk_thinking() {
        // Test that the streaming function correctly handles thinking blocks
        let chunk = TogetherChatChunk {
            choices: vec![TogetherChatChunkChoice {
                delta: TogetherDelta {
                    content: Some("<think>".to_string()),
                    tool_calls: None,
                },
                finish_reason: None,
            }],
            usage: None,
        };

        let mut tool_call_ids = Vec::new();
        let mut tool_call_names = Vec::new();
        let mut thinking_state = ThinkingState::Normal;

        // With parsing enabled
        let result = together_to_tensorzero_chunk(
            "my_raw_chunk".to_string(),
            chunk.clone(),
            Duration::from_millis(100),
            &mut tool_call_ids,
            &mut tool_call_names,
            &mut thinking_state,
            true,
        )
        .unwrap();

        // Should transition to Thinking state
        assert!(matches!(thinking_state, ThinkingState::Thinking));
        // No content should be added for the opening tag
        assert!(result.content.is_empty());

        // Now process some thinking content
        let chunk = TogetherChatChunk {
            choices: vec![TogetherChatChunkChoice {
                delta: TogetherDelta {
                    content: Some("reasoning".to_string()),
                    tool_calls: None,
                },
                finish_reason: None,
            }],
            usage: None,
        };

        let result = together_to_tensorzero_chunk(
            "my_raw_chunk".to_string(),
            chunk,
            Duration::from_millis(100),
            &mut tool_call_ids,
            &mut tool_call_names,
            &mut thinking_state,
            true,
        )
        .unwrap();

        // Should still be in Thinking state
        assert!(matches!(thinking_state, ThinkingState::Thinking));
        // Content should be added as thought
        assert_eq!(result.content.len(), 1);
        assert!(matches!(result.content[0], ContentBlockChunk::Thought(_)));
        if let ContentBlockChunk::Thought(thought) = &result.content[0] {
            assert_eq!(thought.text, Some("reasoning".to_string()));
            assert_eq!(thought.id, "1");
        }

        // Close the thinking block
        let chunk = TogetherChatChunk {
            choices: vec![TogetherChatChunkChoice {
                delta: TogetherDelta {
                    content: Some("</think>".to_string()),
                    tool_calls: None,
                },
                finish_reason: None,
            }],
            usage: None,
        };

        let result = together_to_tensorzero_chunk(
            "my_raw_chunk".to_string(),
            chunk,
            Duration::from_millis(100),
            &mut tool_call_ids,
            &mut tool_call_names,
            &mut thinking_state,
            true,
        )
        .unwrap();

        // Should transition to Finished state
        assert!(matches!(thinking_state, ThinkingState::Finished));
        // No content should be added for the closing tag
        assert!(result.content.is_empty());

        // After closing, regular text should be treated as text content
        let chunk = TogetherChatChunk {
            choices: vec![TogetherChatChunkChoice {
                delta: TogetherDelta {
                    content: Some("Final answer".to_string()),
                    tool_calls: None,
                },
                finish_reason: None,
            }],
            usage: None,
        };

        let result = together_to_tensorzero_chunk(
            "my_raw_chunk".to_string(),
            chunk,
            Duration::from_millis(100),
            &mut tool_call_ids,
            &mut tool_call_names,
            &mut thinking_state,
            true,
        )
        .unwrap();

        // Should remain in Finished state
        assert!(matches!(thinking_state, ThinkingState::Finished));
        // Content should be added as text
        assert_eq!(result.content.len(), 1);
        assert!(matches!(result.content[0], ContentBlockChunk::Text(_)));
        if let ContentBlockChunk::Text(text) = &result.content[0] {
            assert_eq!(text.text, "Final answer");
            assert_eq!(text.id, "2");
        }
    }

    #[test]
    fn test_together_to_tensorzero_chunk() {
        let chunk = TogetherChatChunk {
            choices: vec![TogetherChatChunkChoice {
                delta: TogetherDelta {
                    content: Some("Hello".to_string()),
                    tool_calls: None,
                },
                finish_reason: Some(TogetherFinishReason::Stop),
            }],
            usage: None,
        };
        let mut tool_call_ids = vec!["id1".to_string()];
        let mut tool_call_names = vec!["name1".to_string()];
        let mut thinking_state = ThinkingState::Normal;
        let message = together_to_tensorzero_chunk(
            "my_raw_chunk".to_string(),
            chunk.clone(),
            Duration::from_millis(50),
            &mut tool_call_ids,
            &mut tool_call_names,
            &mut thinking_state,
            true,
        )
        .unwrap();
        assert_eq!(
            message.content,
            vec![ContentBlockChunk::Text(TextChunk {
                text: "Hello".to_string(),
                id: "0".to_string(),
            })],
        );
        assert_eq!(message.finish_reason, Some(FinishReason::Stop));
        // Test what an intermediate tool chunk should look like
        let chunk = TogetherChatChunk {
            choices: vec![TogetherChatChunkChoice {
                delta: TogetherDelta {
                    content: None,
                    tool_calls: Some(vec![TogetherToolCallChunk {
                        index: 0,
                        id: None,
                        function: TogetherFunctionCallChunk {
                            name: None,
                            arguments: Some("{\"hello\":\"world\"}".to_string()),
                        },
                    }]),
                },
                finish_reason: Some(TogetherFinishReason::ToolCalls),
            }],
            usage: None,
        };
        let message = together_to_tensorzero_chunk(
            "my_raw_chunk".to_string(),
            chunk.clone(),
            Duration::from_millis(50),
            &mut tool_call_ids,
            &mut tool_call_names,
            &mut thinking_state,
            true,
        )
        .unwrap();
        assert_eq!(
            message.content,
            vec![ContentBlockChunk::ToolCall(ToolCallChunk {
                id: "id1".to_string(),
                raw_name: "name1".to_string(),
                raw_arguments: "{\"hello\":\"world\"}".to_string(),
            })]
        );
        assert_eq!(message.finish_reason, Some(FinishReason::ToolCall));
        // Test what a bad tool chunk would do (new ID but no names)
        let chunk = TogetherChatChunk {
            choices: vec![TogetherChatChunkChoice {
                delta: TogetherDelta {
                    content: None,
                    tool_calls: Some(vec![TogetherToolCallChunk {
                        index: 1,
                        id: None,
                        function: TogetherFunctionCallChunk {
                            name: None,
                            arguments: Some("{\"hello\":\"world\"}".to_string()),
                        },
                    }]),
                },
                finish_reason: Some(TogetherFinishReason::ToolCalls),
            }],
            usage: None,
        };
        let error = together_to_tensorzero_chunk(
            "my_raw_chunk".to_string(),
            chunk.clone(),
            Duration::from_millis(50),
            &mut tool_call_ids,
            &mut tool_call_names,
            &mut thinking_state,
            true,
        )
        .unwrap_err();
        let details = error.get_details();
        assert_eq!(
            *details,
            ErrorDetails::InferenceServer {
                message: "Tool call index out of bounds (meaning we haven't seen this many ids in the stream)".to_string(),
                raw_request: None,
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            }
        );
        // Test a correct new tool chunk
        let chunk = TogetherChatChunk {
            choices: vec![TogetherChatChunkChoice {
                delta: TogetherDelta {
                    content: None,
                    tool_calls: Some(vec![TogetherToolCallChunk {
                        index: 1,
                        id: Some("id2".to_string()),
                        function: TogetherFunctionCallChunk {
                            name: Some("name2".to_string()),
                            arguments: Some("{\"hello\":\"world\"}".to_string()),
                        },
                    }]),
                },
                finish_reason: Some(TogetherFinishReason::ToolCalls),
            }],
            usage: None,
        };
        let message = together_to_tensorzero_chunk(
            "my_raw_chunk".to_string(),
            chunk.clone(),
            Duration::from_millis(50),
            &mut tool_call_ids,
            &mut tool_call_names,
            &mut thinking_state,
            true,
        )
        .unwrap();
        assert_eq!(
            message.content,
            vec![ContentBlockChunk::ToolCall(ToolCallChunk {
                id: "id2".to_string(),
                raw_name: "name2".to_string(),
                raw_arguments: "{\"hello\":\"world\"}".to_string(),
            })]
        );
        // Check that the lists were updated
        assert_eq!(tool_call_ids, vec!["id1".to_string(), "id2".to_string()]);
        assert_eq!(
            tool_call_names,
            vec!["name1".to_string(), "name2".to_string()]
        );

        // Check a chunk with no choices and only usage
        let chunk = TogetherChatChunk {
            choices: vec![],
            usage: Some(OpenAIUsage {
                prompt_tokens: 10,
                completion_tokens: 20,
                total_tokens: 30,
            }),
        };
        let message = together_to_tensorzero_chunk(
            "my_raw_chunk".to_string(),
            chunk.clone(),
            Duration::from_millis(50),
            &mut tool_call_ids,
            &mut tool_call_names,
            &mut thinking_state,
            true,
        )
        .unwrap();
        assert_eq!(message.content, vec![]);
        assert_eq!(
            message.usage,
            Some(Usage {
                input_tokens: 10,
                output_tokens: 20,
            })
        );

        // Test a thinking chunk
        let chunk = TogetherChatChunk {
            choices: vec![TogetherChatChunkChoice {
                delta: TogetherDelta {
                    content: Some("<think>".to_string()),
                    tool_calls: None,
                },
                finish_reason: Some(TogetherFinishReason::Stop),
            }],
            usage: None,
        };
        let message = together_to_tensorzero_chunk(
            "my_raw_chunk".to_string(),
            chunk.clone(),
            Duration::from_millis(50),
            &mut tool_call_ids,
            &mut tool_call_names,
            &mut thinking_state,
            true,
        )
        .unwrap();
        assert!(message.content.is_empty());
        assert!(matches!(thinking_state, ThinkingState::Thinking));

        // Test a thinking middle chunk
        let chunk = TogetherChatChunk {
            choices: vec![TogetherChatChunkChoice {
                delta: TogetherDelta {
                    content: Some("some thinking content".to_string()),
                    tool_calls: None,
                },
                finish_reason: Some(TogetherFinishReason::Stop),
            }],
            usage: None,
        };
        let message = together_to_tensorzero_chunk(
            "my_raw_chunk".to_string(),
            chunk.clone(),
            Duration::from_millis(50),
            &mut tool_call_ids,
            &mut tool_call_names,
            &mut thinking_state,
            true,
        )
        .unwrap();
        assert_eq!(
            message.content,
            vec![ContentBlockChunk::Thought(ThoughtChunk {
                text: Some("some thinking content".to_string()),
                signature: None,
                id: "1".to_string(),
            })]
        );
        assert!(matches!(thinking_state, ThinkingState::Thinking));

        // Test a thinking chunk end
        let chunk = TogetherChatChunk {
            choices: vec![TogetherChatChunkChoice {
                delta: TogetherDelta {
                    content: Some("</think>".to_string()),
                    tool_calls: None,
                },
                finish_reason: Some(TogetherFinishReason::Stop),
            }],
            usage: None,
        };
        let message = together_to_tensorzero_chunk(
            "my_raw_chunk".to_string(),
            chunk.clone(),
            Duration::from_millis(50),
            &mut tool_call_ids,
            &mut tool_call_names,
            &mut thinking_state,
            true,
        )
        .unwrap();
        assert!(message.content.is_empty());
        assert!(matches!(thinking_state, ThinkingState::Finished));
    }

    #[test]
    fn test_together_to_tensorzero_chunk_without_think_parsing() {
        let chunk = TogetherChatChunk {
            choices: vec![TogetherChatChunkChoice {
                delta: TogetherDelta {
                    content: Some("Hello <think>should not parse</think>".to_string()),
                    tool_calls: None,
                },
                finish_reason: Some(TogetherFinishReason::Stop),
            }],
            usage: None,
        };
        let mut tool_call_ids = vec![];
        let mut tool_call_names = vec![];
        let mut thinking_state = ThinkingState::Normal;
        let message = together_to_tensorzero_chunk(
            "my_raw_chunk".to_string(),
            chunk,
            Duration::from_millis(50),
            &mut tool_call_ids,
            &mut tool_call_names,
            &mut thinking_state,
            false,
        )
        .unwrap();
        assert_eq!(
            message.content,
            vec![ContentBlockChunk::Text(TextChunk {
                text: "Hello <think>should not parse</think>".to_string(),
                id: "0".to_string(),
            })]
        );
    }

    #[test]
    fn test_together_embedding_request_new() {
        use crate::embeddings::{EmbeddingInput, EmbeddingRequest};

        // Test single input
        let single_input = EmbeddingInput::Single("Hello, world!".to_string());
        let request = EmbeddingRequest {
            input: single_input,
            encoding_format: None,
            dimensions: None,
            modality: None,
            priority: None,
            include_input: None,
            chunking: None,
            extra: HashMap::new(),
        };
        let together_request = TogetherEmbeddingRequest::new("BAAI/bge-base-en-v1.5", &request);

        assert_eq!(together_request.model, "BAAI/bge-base-en-v1.5");
        assert!(matches!(
            together_request.input,
            TogetherEmbeddingInput::Single("Hello, world!")
        ));

        // Test batch input
        let batch_input =
            EmbeddingInput::Batch(vec!["First text".to_string(), "Second text".to_string()]);
        let request = EmbeddingRequest {
            input: batch_input,
            encoding_format: Some("float".to_string()),
            dimensions: None,
            modality: None,
            priority: None,
            include_input: None,
            chunking: None,
            extra: HashMap::new(),
        };
        let together_request =
            TogetherEmbeddingRequest::new("togethercomputer/m2-bert-80M-8k-retrieval", &request);

        assert_eq!(
            together_request.model,
            "togethercomputer/m2-bert-80M-8k-retrieval"
        );
        match together_request.input {
            TogetherEmbeddingInput::Batch(texts) => {
                assert_eq!(texts.len(), 2);
                assert_eq!(texts[0], "First text");
                assert_eq!(texts[1], "Second text");
            }
            _ => panic!("Expected batch input"),
        }
    }

    #[test]
    fn test_together_embedding_response_parsing() {
        let json_response = r#"{
            "data": [
                {
                    "index": 0,
                    "object": "embedding",
                    "embedding": [0.1, 0.2, 0.3]
                },
                {
                    "index": 1,
                    "object": "embedding",
                    "embedding": [0.4, 0.5, 0.6]
                }
            ],
            "model": "BAAI/bge-base-en-v1.5",
            "object": "list",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 0,
                "total_tokens": 10
            }
        }"#;

        let response: TogetherEmbeddingResponse = serde_json::from_str(json_response).unwrap();
        assert_eq!(response.data.len(), 2);
        assert_eq!(response.data[0].embedding, vec![0.1, 0.2, 0.3]);
        assert_eq!(response.data[1].embedding, vec![0.4, 0.5, 0.6]);
        assert_eq!(response.usage.prompt_tokens, 10);
        assert_eq!(response.usage.total_tokens, 10);
    }

    #[tokio::test]
    async fn test_together_image_generation_request_serialization() {
        use crate::images::{ImageGenerationRequest, ImageResponseFormat, ImageSize};
        use std::sync::Arc;

        // Set up test environment variable
        std::env::set_var("TEST_TOGETHER_API_KEY", "test-api-key");

        let provider = TogetherProvider::new(
            "black-forest-labs/FLUX.1-schnell".to_string(),
            Some(CredentialLocation::Env("TEST_TOGETHER_API_KEY".to_string())),
            false,
        )
        .unwrap();

        let request = ImageGenerationRequest {
            id: Uuid::now_v7(),
            prompt: "A beautiful sunset over mountains".to_string(),
            model: Arc::from("flux-schnell"),
            n: Some(1),
            size: Some(ImageSize::Size1024x1024),
            quality: None,
            style: None,
            response_format: Some(ImageResponseFormat::Url),
            user: Some("test-user".to_string()),
            background: None,
            moderation: None,
            output_compression: None,
            output_format: None,
        };

        // Create the Together-specific request
        let together_request = TogetherImageGenerationRequest {
            model: provider.model_name().to_string(),
            prompt: request.prompt.clone(),
            n: request.n,
            size: request.size.as_ref().map(|s| s.as_str().to_string()),
            response_format: request
                .response_format
                .as_ref()
                .map(|f| f.as_str().to_string()),
            user: request.user.clone(),
            steps: None,
            disable_safety_checker: None,
        };

        // Test serialization
        let serialized = serde_json::to_string(&together_request).unwrap();
        let parsed: serde_json::Value = serde_json::from_str(&serialized).unwrap();

        assert_eq!(parsed["model"], "black-forest-labs/FLUX.1-schnell");
        assert_eq!(parsed["prompt"], "A beautiful sunset over mountains");
        assert_eq!(parsed["n"], 1);
        assert_eq!(parsed["size"], "1024x1024");
        assert_eq!(parsed["response_format"], "url");
        assert_eq!(parsed["user"], "test-user");
        assert!(parsed.get("steps").is_none());
        assert!(parsed.get("disable_safety_checker").is_none());
    }

    #[tokio::test]
    async fn test_together_image_response_parsing() {
        // Test with actual Together API response format
        let response_json = r#"{
            "id": "o1TnXqu-2kFHot-958e7e079b9d47e3-PDX",
            "model": "black-forest-labs/FLUX.1-schnell",
            "object": "list",
            "data": [
                {
                    "index": 0,
                    "url": "https://api.together.ai/shrt/vcu2cXNQebqphdfe",
                    "timings": {
                        "inference": 0.29318173974752426
                    }
                }
            ]
        }"#;

        let response: TogetherImageResponse = serde_json::from_str(response_json).unwrap();

        assert_eq!(response.id, "o1TnXqu-2kFHot-958e7e079b9d47e3-PDX");
        assert_eq!(response.model, "black-forest-labs/FLUX.1-schnell");
        assert_eq!(response.object, "list");
        assert_eq!(response.created, None);
        assert_eq!(response.data.len(), 1);
        assert_eq!(response.data[0].index, 0);
        assert_eq!(
            response.data[0].url,
            Some("https://api.together.ai/shrt/vcu2cXNQebqphdfe".to_string())
        );
        assert_eq!(response.data[0].b64_json, None);
        assert_eq!(response.data[0].revised_prompt, None);
        assert!(response.data[0].timings.is_some());
        assert_eq!(
            response.data[0].timings.as_ref().unwrap().inference,
            0.29318173974752426
        );

        // Test with created field present (backward compatibility)
        let response_with_created = r#"{
            "id": "test-id",
            "model": "black-forest-labs/FLUX.1-schnell",
            "object": "list",
            "created": 1234567890,
            "data": [
                {
                    "index": 0,
                    "url": "https://example.com/image.png"
                }
            ]
        }"#;

        let response2: TogetherImageResponse = serde_json::from_str(response_with_created).unwrap();
        assert_eq!(response2.created, Some(1234567890));
    }

    #[test]
    fn test_map_audio_voice_to_together() {
        // Test all voice mappings
        assert_eq!(
            map_audio_voice_to_together(&AudioVoice::Alloy),
            "helpful woman"
        );
        assert_eq!(
            map_audio_voice_to_together(&AudioVoice::Echo),
            "laidback woman"
        );
        assert_eq!(
            map_audio_voice_to_together(&AudioVoice::Fable),
            "meditation lady"
        );
        assert_eq!(map_audio_voice_to_together(&AudioVoice::Onyx), "newsman");
        assert_eq!(
            map_audio_voice_to_together(&AudioVoice::Nova),
            "friendly sidekick"
        );
        assert_eq!(
            map_audio_voice_to_together(&AudioVoice::Shimmer),
            "british reading lady"
        );
        assert_eq!(
            map_audio_voice_to_together(&AudioVoice::Ash),
            "barbershop man"
        );
        assert_eq!(
            map_audio_voice_to_together(&AudioVoice::Ballad),
            "indian lady"
        );
        assert_eq!(
            map_audio_voice_to_together(&AudioVoice::Coral),
            "german conversational woman"
        );
        assert_eq!(
            map_audio_voice_to_together(&AudioVoice::Sage),
            "pilot over intercom"
        );
        assert_eq!(
            map_audio_voice_to_together(&AudioVoice::Verse),
            "australian customer support man"
        );

        // Test Other variant
        assert_eq!(
            map_audio_voice_to_together(&AudioVoice::Other("custom voice".to_string())),
            "custom voice"
        );
    }

    #[test]
    fn test_together_tts_request_serialization() {
        let request = TogetherTextToSpeechRequest {
            model: Cow::Borrowed("cartesia/sonic"),
            input: Cow::Borrowed("Hello, world!"),
            voice: Cow::Borrowed("helpful woman"),
            response_format: Some("mp3"),
            sample_rate: Some(44100),
            stream: Some(false),
        };

        let serialized = serde_json::to_string(&request).unwrap();
        let parsed: serde_json::Value = serde_json::from_str(&serialized).unwrap();

        assert_eq!(parsed["model"], "cartesia/sonic");
        assert_eq!(parsed["input"], "Hello, world!");
        assert_eq!(parsed["voice"], "helpful woman");
        assert_eq!(parsed["response_format"], "mp3");
        assert_eq!(parsed["sample_rate"], 44100);
        assert_eq!(parsed["stream"], false);
    }

    #[test]
    fn test_together_tts_request_serialization_minimal() {
        let request = TogetherTextToSpeechRequest {
            model: Cow::Borrowed("cartesia/sonic"),
            input: Cow::Borrowed("Test"),
            voice: Cow::Borrowed("newsman"),
            response_format: None,
            sample_rate: None,
            stream: None,
        };

        let serialized = serde_json::to_string(&request).unwrap();
        let parsed: serde_json::Value = serde_json::from_str(&serialized).unwrap();

        assert_eq!(parsed["model"], "cartesia/sonic");
        assert_eq!(parsed["input"], "Test");
        assert_eq!(parsed["voice"], "newsman");
        assert!(parsed.get("response_format").is_none());
        assert!(parsed.get("sample_rate").is_none());
        assert!(parsed.get("stream").is_none());
    }

    #[test]
    fn test_get_audio_speech_url() {
        let base_url = Url::parse("https://api.together.xyz/v1").unwrap();
        let audio_url = get_audio_speech_url(&base_url).unwrap();
        assert_eq!(
            audio_url.as_str(),
            "https://api.together.xyz/v1/audio/generations"
        );

        // Test with base URL that has trailing slash
        let base_url_with_slash = Url::parse("https://api.together.xyz/v1/").unwrap();
        let audio_url_with_slash = get_audio_speech_url(&base_url_with_slash).unwrap();
        assert_eq!(
            audio_url_with_slash.as_str(),
            "https://api.together.xyz/v1/audio/generations"
        );
    }

    #[tokio::test]
    async fn test_together_tts_provider() {
        use crate::audio::{AudioOutputFormat, AudioVoice, TextToSpeechRequest};
        use std::sync::Arc;

        // Set up test environment variable
        std::env::set_var("TEST_TOGETHER_API_KEY", "test-api-key");

        let provider = TogetherProvider::new(
            "cartesia/sonic".to_string(),
            Some(CredentialLocation::Env("TEST_TOGETHER_API_KEY".to_string())),
            false,
        )
        .unwrap();

        let _request = TextToSpeechRequest {
            id: Uuid::now_v7(),
            input: "Hello, this is a test".to_string(),
            model: Arc::from("cartesia/sonic"),
            voice: AudioVoice::Alloy,
            response_format: Some(AudioOutputFormat::Mp3),
            speed: None,
        };

        // Test request building - we can't easily test the full provider without mocking
        // but we can test that the provider is set up correctly
        assert_eq!(provider.model_name(), "cartesia/sonic");
    }

    #[tokio::test]
    async fn test_together_tts_input_validation() {
        use crate::endpoints::inference::InferenceCredentials;
        use std::sync::Arc;

        // Set up test environment variable
        std::env::set_var("TEST_TOGETHER_API_KEY", "test-api-key");

        let provider = TogetherProvider::new(
            "cartesia/sonic".to_string(),
            Some(CredentialLocation::Env("TEST_TOGETHER_API_KEY".to_string())),
            false,
        )
        .unwrap();

        let client = reqwest::Client::new();
        let dynamic_api_keys = InferenceCredentials::default();

        // Test empty input
        let empty_request = TextToSpeechRequest {
            id: Uuid::now_v7(),
            input: "   ".to_string(), // Only whitespace
            model: Arc::from("cartesia/sonic"),
            voice: AudioVoice::Alloy,
            response_format: Some(AudioOutputFormat::Mp3),
            speed: None,
        };

        let result = provider
            .generate_speech(&empty_request, &client, &dynamic_api_keys)
            .await;

        assert!(result.is_err());
        let error = result.unwrap_err();
        assert!(matches!(
            error.get_details(),
            ErrorDetails::InvalidRequest { message } if message.contains("Input text cannot be empty")
        ));

        // Test input that's too long
        let long_input = "a".repeat(5000); // Exceeds 4096 character limit
        let long_request = TextToSpeechRequest {
            id: Uuid::now_v7(),
            input: long_input,
            model: Arc::from("cartesia/sonic"),
            voice: AudioVoice::Alloy,
            response_format: Some(AudioOutputFormat::Mp3),
            speed: None,
        };

        let result = provider
            .generate_speech(&long_request, &client, &dynamic_api_keys)
            .await;

        assert!(result.is_err());
        let error = result.unwrap_err();
        assert!(matches!(
            error.get_details(),
            ErrorDetails::InvalidRequest { message } if message.contains("Input text is too long")
        ));
    }
}
