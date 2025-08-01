use std::borrow::Cow;
use std::sync::OnceLock;

use futures::{StreamExt, TryStreamExt};
use reqwest_eventsource::RequestBuilderExt;
use secrecy::{ExposeSecret, SecretString};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::time::Instant;
use url::Url;

use super::helpers::inject_extra_request_data;
use super::openai::{
    get_chat_url, handle_openai_error, stream_openai, tensorzero_to_openai_messages,
    OpenAIRequestMessage, OpenAIResponse, OpenAIResponseChoice, OpenAISystemRequestMessage,
    StreamOptions,
};
use super::provider_trait::{InferenceProvider, TensorZeroEventError};
use crate::cache::ModelProviderRequest;
use crate::embeddings::{EmbeddingProvider, EmbeddingProviderResponse, EmbeddingRequest};
use crate::endpoints::inference::InferenceCredentials;
use crate::error::{DisplayOrDebugGateway, Error, ErrorDetails};
use crate::inference::providers::openai::check_api_base_suffix;
use crate::inference::types::batch::{BatchRequestRow, PollBatchInferenceResponse};
use crate::inference::types::{
    batch::StartBatchProviderInferenceResponse, ContentBlockOutput, Latency, ModelInferenceRequest,
    ModelInferenceRequestJsonMode, PeekableProviderInferenceResponseStream,
    ProviderInferenceResponse, ProviderInferenceResponseArgs, Usage,
};
use crate::model::{build_creds_caching_default, Credential, CredentialLocation, ModelProvider};

const PROVIDER_NAME: &str = "vLLM";
const PROVIDER_TYPE: &str = "vllm";

#[derive(Debug)]
pub struct VLLMProvider {
    model_name: String,
    api_base: Url,
    credentials: VLLMCredentials,
}

static DEFAULT_CREDENTIALS: OnceLock<VLLMCredentials> = OnceLock::new();

impl VLLMProvider {
    pub fn new(
        model_name: String,
        api_base: Url,
        api_key_location: Option<CredentialLocation>,
    ) -> Result<Self, Error> {
        let credentials = build_creds_caching_default(
            api_key_location,
            default_api_key_location(),
            PROVIDER_TYPE,
            &DEFAULT_CREDENTIALS,
        )?;

        // Check if the api_base has the `/chat/completions` suffix and warn if it does
        check_api_base_suffix(&api_base);

        Ok(VLLMProvider {
            model_name,
            api_base,
            credentials,
        })
    }

    pub fn model_name(&self) -> &str {
        &self.model_name
    }
}

fn default_api_key_location() -> CredentialLocation {
    CredentialLocation::Env("VLLM_API_KEY".to_string())
}

#[derive(Clone, Debug)]
pub enum VLLMCredentials {
    Static(SecretString),
    Dynamic(String),
    None,
}

impl TryFrom<Credential> for VLLMCredentials {
    type Error = Error;

    fn try_from(credentials: Credential) -> Result<Self, Error> {
        match credentials {
            Credential::Static(key) => Ok(VLLMCredentials::Static(key)),
            Credential::Dynamic(key_name) => Ok(VLLMCredentials::Dynamic(key_name)),
            Credential::None => Ok(VLLMCredentials::None),
            #[cfg(any(test, feature = "e2e_tests"))]
            Credential::Missing => Ok(VLLMCredentials::None),
            _ => Err(Error::new(ErrorDetails::Config {
                message: "Invalid api_key_location for vLLM provider".to_string(),
            })),
        }
    }
}

impl VLLMCredentials {
    fn get_api_key<'a>(
        &'a self,
        dynamic_api_keys: &'a InferenceCredentials,
    ) -> Result<Option<&'a SecretString>, Error> {
        match self {
            VLLMCredentials::Static(api_key) => Ok(Some(api_key)),
            VLLMCredentials::Dynamic(key_name) => {
                Ok(Some(dynamic_api_keys.get(key_name).ok_or_else(|| {
                    Error::new(ErrorDetails::ApiKeyMissing {
                        provider_name: PROVIDER_NAME.to_string(),
                    })
                })?))
            }
            VLLMCredentials::None => Ok(None),
        }
    }
}

/// Key differences between vLLM and OpenAI inference:
/// - vLLM supports guided decoding
/// - vLLM only supports a specific tool and nothing else (and the implementation varies among LLMs)
///   **Today, we can't support tools** so we are leaving it as an open issue (#169).
impl InferenceProvider for VLLMProvider {
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
        let mut request_body = serde_json::to_value(VLLMRequest::new(&self.model_name, request)?)
            .map_err(|e| {
            Error::new(ErrorDetails::Serialization {
                message: format!(
                    "Error serializing VLLM request: {}",
                    DisplayOrDebugGateway::new(e)
                ),
            })
        })?;
        let headers = inject_extra_request_data(
            &request.extra_body,
            &request.extra_headers,
            model_provider,
            model_name,
            &mut request_body,
        )?;
        let request_url = get_chat_url(&self.api_base)?;
        let start_time = Instant::now();
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let mut request_builder = http_client
            .post(request_url)
            .header("Content-Type", "application/json");
        if let Some(key) = api_key {
            request_builder = request_builder.bearer_auth(key.expose_secret());
        }
        let res = request_builder
            .json(&request_body)
            .headers(headers)
            .send()
            .await
            .map_err(|e| {
                Error::new(ErrorDetails::InferenceClient {
                    status_code: e.status(),
                    message: format!(
                        "Error sending request to vLLM: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;
        let latency = Latency::NonStreaming {
            response_time: start_time.elapsed(),
        };
        if res.status().is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!("Error parsing response: {}", DisplayOrDebugGateway::new(e)),
                    raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;
            let response_body = serde_json::from_str(&raw_response).map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!("Error parsing response: {}", DisplayOrDebugGateway::new(e)),
                    raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                    raw_response: Some(raw_response.clone()),
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;
            Ok(VLLMResponseWithMetadata {
                response: response_body,
                latency,
                raw_response,
                request: request_body,
                generic_request: request,
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
        let mut request_body = serde_json::to_value(VLLMRequest::new(&self.model_name, request)?)
            .map_err(|e| {
            Error::new(ErrorDetails::Serialization {
                message: format!(
                    "Error serializing VLLM request: {}",
                    DisplayOrDebugGateway::new(e)
                ),
            })
        })?;
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
        let request_url = get_chat_url(&self.api_base)?;
        let start_time = Instant::now();
        let mut request_builder = http_client
            .post(request_url)
            .header("Content-Type", "application/json");
        if let Some(key) = api_key {
            request_builder = request_builder.bearer_auth(key.expose_secret());
        }
        let event_source = request_builder
            .json(&request_body)
            .headers(headers)
            .eventsource()
            .map_err(|e| {
                Error::new(ErrorDetails::InferenceClient {
                    message: format!(
                        "Error sending request to vLLM: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    status_code: None,
                    raw_request: Some(raw_request.clone()),
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;
        let stream = stream_openai(
            PROVIDER_TYPE.to_string(),
            event_source.map_err(TensorZeroEventError::EventSource),
            start_time,
        )
        .peekable();
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

/// This struct defines the supported parameters for the vLLM inference API
/// See the [vLLM API documentation](https://docs.vllm.ai/en/stable/index.html)
/// for more details.
/// We are not handling many features of the API here.
#[derive(Debug, Serialize)]
struct VLLMRequest<'a> {
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
    stream: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    stream_options: Option<StreamOptions>,
    #[serde(skip_serializing_if = "Option::is_none")]
    chat_template: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    chat_template_kwargs: Option<&'a Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    mm_processor_kwargs: Option<&'a Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    guided_json: Option<&'a Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    guided_regex: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    guided_choice: Option<&'a Vec<Cow<'a, str>>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    guided_grammar: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    structural_tag: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    guided_decoding_backend: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    guided_whitespace_pattern: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    logprobs: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    seed: Option<u32>,
}

impl<'a> VLLMRequest<'a> {
    pub fn new(
        model: &'a str,
        request: &'a ModelInferenceRequest<'_>,
    ) -> Result<VLLMRequest<'a>, Error> {
        let stream_options = match request.stream {
            true => Some(StreamOptions {
                include_usage: true,
            }),
            false => None,
        };
        let messages = prepare_vllm_messages(request)?;
        // TODO (#169): Implement tool calling.
        if request.tool_config.is_some() {
            return Err(ErrorDetails::InferenceClient {
                message: "TensorZero does not support tool use with vLLM. Please use a different provider.".to_string(),
                status_code: Some(reqwest::StatusCode::BAD_REQUEST),
                raw_request: None,
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            }.into());
        }

        // Determine guided_json field: prefer explicit request.guided_json; otherwise derive from json_mode/output_schema
        let guided_json_field = if request.guided_json.is_some() {
            request.guided_json
        } else {
            match (&request.json_mode, request.output_schema) {
                (
                    ModelInferenceRequestJsonMode::On | ModelInferenceRequestJsonMode::Strict,
                    Some(schema),
                ) => Some(schema),
                _ => None,
            }
        };

        Ok(VLLMRequest {
            messages,
            model,
            temperature: request.temperature,
            top_p: request.top_p,
            presence_penalty: request.presence_penalty,
            frequency_penalty: request.frequency_penalty,
            max_tokens: request.max_tokens,
            stream: request.stream,
            stream_options,
            chat_template: request.chat_template,
            chat_template_kwargs: request.chat_template_kwargs,
            mm_processor_kwargs: request.mm_processor_kwargs,
            guided_json: guided_json_field,
            guided_regex: request.guided_regex,
            guided_choice: request.guided_choice.as_ref(),
            guided_grammar: request.guided_grammar,
            structural_tag: request.structural_tag,
            guided_decoding_backend: request.guided_decoding_backend,
            guided_whitespace_pattern: request.guided_whitespace_pattern,
            logprobs: match request.logprobs {
                true => Some(true),   // client asked for log-probs
                false => Some(false), // client explicitly disabled it
            },
            seed: request.seed,
        })
    }
}

struct VLLMResponseWithMetadata<'a> {
    response: OpenAIResponse,
    latency: Latency,
    raw_response: String,
    request: serde_json::Value,
    generic_request: &'a ModelInferenceRequest<'a>,
}

impl<'a> TryFrom<VLLMResponseWithMetadata<'a>> for ProviderInferenceResponse {
    type Error = Error;
    fn try_from(value: VLLMResponseWithMetadata<'a>) -> Result<Self, Self::Error> {
        let VLLMResponseWithMetadata {
            mut response,
            latency,
            raw_response,
            request: request_body,
            generic_request,
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
        let OpenAIResponseChoice {
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
        // Handle reasoning_content if present (for vLLM with enable_thinking)
        if let Some(reasoning_text) = message.reasoning_content {
            content.push(ContentBlockOutput::Thought(
                crate::inference::types::Thought {
                    text: reasoning_text,
                    signature: None,
                },
            ));
        }
        if let Some(text) = message.content {
            content.push(text.into());
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
                finish_reason: Some(finish_reason.into()),
            },
        ))
    }
}

pub(super) fn prepare_vllm_messages<'a>(
    request: &'a ModelInferenceRequest<'_>,
) -> Result<Vec<OpenAIRequestMessage<'a>>, Error> {
    let mut messages = Vec::with_capacity(request.messages.len());
    for message in request.messages.iter() {
        messages.extend(tensorzero_to_openai_messages(message)?);
    }
    if let Some(system_msg) = tensorzero_to_vllm_system_message(request.system.as_deref()) {
        messages.insert(0, system_msg);
    }
    Ok(messages)
}

fn tensorzero_to_vllm_system_message(system: Option<&str>) -> Option<OpenAIRequestMessage<'_>> {
    system.map(|instructions| {
        OpenAIRequestMessage::System(OpenAISystemRequestMessage {
            content: Cow::Borrowed(instructions),
        })
    })
}

// vLLM Embedding Support

/// Get the embedding endpoint URL for vLLM
fn get_embedding_url(base_url: &Url) -> Result<Url, Error> {
    let mut url = base_url.clone();
    if !url.path().ends_with('/') {
        url.set_path(&format!("{}/", url.path()));
    }
    url.join("embeddings").map_err(|e| {
        Error::new(ErrorDetails::InvalidBaseUrl {
            message: e.to_string(),
        })
    })
}

#[derive(Debug, Serialize)]
struct VLLMEmbeddingRequest<'a> {
    model: &'a str,
    input: VLLMEmbeddingRequestInput<'a>,
    #[serde(skip_serializing_if = "Option::is_none")]
    encoding_format: Option<&'a str>,
}

#[derive(Debug, Serialize)]
#[serde(untagged)]
enum VLLMEmbeddingRequestInput<'a> {
    Single(&'a str),
    Batch(Vec<&'a str>),
}

#[derive(Debug, Deserialize)]
struct VLLMEmbeddingResponse {
    data: Vec<VLLMEmbeddingData>,
    usage: VLLMEmbeddingUsage,
}

#[derive(Debug, Deserialize)]
struct VLLMEmbeddingData {
    embedding: Vec<f32>,
}

#[derive(Debug, Deserialize)]
struct VLLMEmbeddingUsage {
    prompt_tokens: u32,
    #[expect(dead_code)]
    total_tokens: u32,
}

impl EmbeddingProvider for VLLMProvider {
    async fn embed(
        &self,
        request: &EmbeddingRequest,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<EmbeddingProviderResponse, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let input = match &request.input {
            crate::embeddings::EmbeddingInput::Single(text) => {
                VLLMEmbeddingRequestInput::Single(text)
            }
            crate::embeddings::EmbeddingInput::Batch(texts) => {
                VLLMEmbeddingRequestInput::Batch(texts.iter().map(|s| s.as_str()).collect())
            }
        };
        let request_body = VLLMEmbeddingRequest {
            model: &self.model_name,
            input,
            encoding_format: request.encoding_format.as_deref(),
        };
        let request_url = get_embedding_url(&self.api_base)?;
        let start_time = Instant::now();
        let mut request_builder = client
            .post(request_url)
            .header("Content-Type", "application/json");
        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }
        let res = request_builder
            .json(&request_body)
            .send()
            .await
            .map_err(|e| {
                Error::new(ErrorDetails::InferenceClient {
                    status_code: e.status(),
                    message: format!(
                        "Error sending request to vLLM: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    provider_type: PROVIDER_TYPE.to_string(),
                    raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                    raw_response: None,
                })
            })?;
        let latency = Latency::NonStreaming {
            response_time: start_time.elapsed(),
        };
        if res.status().is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!("Error parsing response: {}", DisplayOrDebugGateway::new(e)),
                    raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;
            let response_body: VLLMEmbeddingResponse = serde_json::from_str(&raw_response)
                .map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                        raw_response: Some(raw_response.clone()),
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?;
            if response_body.data.is_empty() {
                return Err(Error::new(ErrorDetails::InferenceServer {
                    message: "vLLM returned no embedding data".to_string(),
                    raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                    raw_response: Some(raw_response.clone()),
                    provider_type: PROVIDER_TYPE.to_string(),
                }));
            }
            let embeddings: Vec<Vec<f32>> = response_body
                .data
                .into_iter()
                .map(|d| d.embedding)
                .collect();
            let raw_request = serde_json::to_string(&request_body).map_err(|e| {
                Error::new(ErrorDetails::Serialization {
                    message: format!(
                        "Error serializing request body: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                })
            })?;
            let usage = Usage {
                input_tokens: response_body.usage.prompt_tokens,
                output_tokens: 0, // Embeddings don't have output tokens
            };
            Ok(EmbeddingProviderResponse::new(
                embeddings,
                request.input.clone(),
                raw_request,
                raw_response,
                usage,
                latency,
            ))
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
}

#[cfg(test)]
mod tests {
    use std::{borrow::Cow, time::Duration};

    use serde_json::json;
    use tracing_test::traced_test;
    use uuid::Uuid;

    use super::*;

    use crate::inference::{
        providers::{
            openai::{
                OpenAIFinishReason, OpenAIResponseChoice, OpenAIResponseMessage, OpenAIUsage,
            },
            test_helpers::WEATHER_TOOL_CONFIG,
        },
        types::{FunctionType, RequestMessage, Role},
    };

    #[test]
    fn test_vllm_request_new() {
        let output_schema = json!({
            "type": "object",
            "properties": {
                "temperature": {"type": "number"},
                "location": {"type": "string"}
            }
        });
        let request_with_tools = ModelInferenceRequest {
            inference_id: Uuid::now_v7(),
            messages: vec![RequestMessage {
                role: Role::User,
                content: vec!["What's the weather?".to_string().into()],
            }],
            system: None,
            temperature: Some(0.5),
            top_p: None,
            presence_penalty: None,
            frequency_penalty: None,
            max_tokens: Some(100),
            seed: Some(69),
            stream: false,
            json_mode: ModelInferenceRequestJsonMode::On,
            tool_config: None,
            function_type: FunctionType::Chat,
            output_schema: Some(&output_schema),
            extra_body: Default::default(),
            ..Default::default()
        };

        let vllm_request = VLLMRequest::new("llama-v3-8b", &request_with_tools).unwrap();

        assert_eq!(vllm_request.model, "llama-v3-8b");
        assert_eq!(vllm_request.messages.len(), 1);
        assert_eq!(vllm_request.temperature, Some(0.5));
        assert_eq!(vllm_request.max_tokens, Some(100));
        assert!(!vllm_request.stream);
        assert_eq!(vllm_request.guided_json, Some(&output_schema));

        let output_schema = json!({
            "type": "object",
            "properties": {
                "temperature": {"type": "number"},
                "location": {"type": "string"},
            }
        });
        let request_with_tools = ModelInferenceRequest {
            inference_id: Uuid::now_v7(),
            messages: vec![RequestMessage {
                role: Role::User,
                content: vec!["What's the weather?".to_string().into()],
            }],
            system: None,
            temperature: Some(0.5),
            top_p: None,
            presence_penalty: None,
            frequency_penalty: None,
            max_tokens: Some(100),
            seed: Some(69),
            stream: false,
            json_mode: ModelInferenceRequestJsonMode::On,
            tool_config: Some(Cow::Borrowed(&WEATHER_TOOL_CONFIG)),
            function_type: FunctionType::Chat,
            output_schema: Some(&output_schema),
            extra_body: Default::default(),
            ..Default::default()
        };

        let err = VLLMRequest::new("llama-v3-8b", &request_with_tools).unwrap_err();
        assert!(err
            .to_string()
            .contains("TensorZero does not support tool use with vLLM"));
    }

    #[test]
    fn test_credential_to_vllm_credentials() {
        // Test Static credential
        let generic = Credential::Static(SecretString::from("test_key"));
        let creds: VLLMCredentials = VLLMCredentials::try_from(generic).unwrap();
        assert!(matches!(creds, VLLMCredentials::Static(_)));

        // Test Dynamic credential
        let generic = Credential::Dynamic("key_name".to_string());
        let creds = VLLMCredentials::try_from(generic).unwrap();
        assert!(matches!(creds, VLLMCredentials::Dynamic(_)));

        // Test Missing credential
        let generic = Credential::Missing;
        let creds = VLLMCredentials::try_from(generic).unwrap();
        assert!(matches!(creds, VLLMCredentials::None));

        // Test invalid type
        let generic = Credential::FileContents(SecretString::from("test"));
        let result = VLLMCredentials::try_from(generic);
        assert!(result.is_err());
        assert!(matches!(
            result.unwrap_err().get_owned_details(),
            ErrorDetails::Config { message } if message.contains("Invalid api_key_location")
        ));
    }

    #[test]
    fn test_vllm_response_with_metadata_try_into() {
        let valid_response = OpenAIResponse {
            choices: vec![OpenAIResponseChoice {
                index: 0,
                message: OpenAIResponseMessage {
                    content: Some("Hello, world!".to_string()),
                    tool_calls: None,
                    reasoning_content: None,
                },
                finish_reason: OpenAIFinishReason::Stop,
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
        let vllm_response_with_metadata = VLLMResponseWithMetadata {
            response: valid_response,
            raw_response: "test_response".to_string(),
            latency: Latency::NonStreaming {
                response_time: Duration::from_secs(0),
            },
            request: serde_json::to_value(
                VLLMRequest::new("test-model", &generic_request).unwrap(),
            )
            .unwrap(),
            generic_request: &generic_request,
        };
        let inference_response: ProviderInferenceResponse =
            vllm_response_with_metadata.try_into().unwrap();

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
    }

    #[test]
    #[traced_test]
    fn test_vllm_provider_new_api_base_check() {
        let model_name = "test-model".to_string();
        let api_key_location = Some(CredentialLocation::None);

        // Valid cases (should not warn)
        let _ = VLLMProvider::new(
            model_name.clone(),
            Url::parse("http://localhost:1234/v1/").unwrap(),
            api_key_location.clone(),
        )
        .unwrap();

        let _ = VLLMProvider::new(
            model_name.clone(),
            Url::parse("http://localhost:1234/v1").unwrap(),
            api_key_location.clone(),
        )
        .unwrap();

        // Invalid cases (should warn)
        let invalid_url_1 = Url::parse("http://localhost:1234/chat/completions").unwrap();
        let _ = VLLMProvider::new(
            model_name.clone(),
            invalid_url_1.clone(),
            api_key_location.clone(),
        )
        .unwrap();
        assert!(logs_contain("automatically appends `/chat/completions`"));
        assert!(logs_contain(invalid_url_1.as_ref()));

        let invalid_url_2 = Url::parse("http://localhost:1234/v1/chat/completions/").unwrap();
        let _ = VLLMProvider::new(
            model_name.clone(),
            invalid_url_2.clone(),
            api_key_location.clone(),
        )
        .unwrap();
        assert!(logs_contain("automatically appends `/chat/completions`"));
        assert!(logs_contain(invalid_url_2.as_ref()));
    }
}
