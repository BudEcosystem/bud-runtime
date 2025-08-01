use std::sync::OnceLock;

use futures::{StreamExt, TryStreamExt};
use lazy_static::lazy_static;
use reqwest_eventsource::RequestBuilderExt;
use secrecy::{ExposeSecret, SecretString};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tokio::time::Instant;
use url::Url;

use crate::cache::ModelProviderRequest;
use crate::endpoints::inference::InferenceCredentials;
use crate::error::{DisplayOrDebugGateway, Error, ErrorDetails};
use crate::images::{
    ImageData, ImageGenerationProvider, ImageGenerationProviderResponse, ImageGenerationRequest,
};
use crate::inference::providers::provider_trait::InferenceProvider;
use crate::inference::types::batch::{BatchRequestRow, PollBatchInferenceResponse};
use crate::inference::types::{
    batch::StartBatchProviderInferenceResponse, ContentBlockOutput, Latency, ModelInferenceRequest,
    ModelInferenceRequestJsonMode, PeekableProviderInferenceResponseStream,
    ProviderInferenceResponse, ProviderInferenceResponseArgs, Usage,
};
use crate::model::{build_creds_caching_default, Credential, CredentialLocation, ModelProvider};

use super::helpers::inject_extra_request_data;
use super::openai::{
    get_chat_url, handle_openai_error, prepare_openai_messages, prepare_openai_tools,
    stream_openai, OpenAIRequestMessage, OpenAIResponse, OpenAIResponseChoice, OpenAITool,
    OpenAIToolChoice, StreamOptions,
};
use super::provider_trait::TensorZeroEventError;

lazy_static! {
    static ref XAI_DEFAULT_BASE_URL: Url = {
        #[expect(clippy::expect_used)]
        Url::parse("https://api.x.ai/v1").expect("Failed to parse XAI_DEFAULT_BASE_URL")
    };
}

fn default_api_key_location() -> CredentialLocation {
    CredentialLocation::Env("XAI_API_KEY".to_string())
}

const PROVIDER_NAME: &str = "xAI";
const PROVIDER_TYPE: &str = "xai";

#[derive(Debug)]
pub struct XAIProvider {
    model_name: String,
    credentials: XAICredentials,
}

static DEFAULT_CREDENTIALS: OnceLock<XAICredentials> = OnceLock::new();

impl XAIProvider {
    pub fn new(
        model_name: String,
        api_key_location: Option<CredentialLocation>,
    ) -> Result<Self, Error> {
        let credentials = build_creds_caching_default(
            api_key_location,
            default_api_key_location(),
            PROVIDER_TYPE,
            &DEFAULT_CREDENTIALS,
        )?;

        Ok(XAIProvider {
            model_name,
            credentials,
        })
    }

    pub fn model_name(&self) -> &str {
        &self.model_name
    }
}

#[derive(Clone, Debug)]
pub enum XAICredentials {
    Static(SecretString),
    Dynamic(String),
    None,
}

impl TryFrom<Credential> for XAICredentials {
    type Error = Error;

    fn try_from(credentials: Credential) -> Result<Self, Error> {
        match credentials {
            Credential::Static(key) => Ok(XAICredentials::Static(key)),
            Credential::Dynamic(key_name) => Ok(XAICredentials::Dynamic(key_name)),
            Credential::None => Ok(XAICredentials::None),
            Credential::Missing => Ok(XAICredentials::None),
            _ => Err(Error::new(ErrorDetails::Config {
                message: "Invalid api_key_location for xAI provider".to_string(),
            })),
        }
    }
}

impl XAICredentials {
    pub fn get_api_key<'a>(
        &'a self,
        dynamic_api_keys: &'a InferenceCredentials,
    ) -> Result<&'a SecretString, Error> {
        match self {
            XAICredentials::Static(api_key) => Ok(api_key),
            XAICredentials::Dynamic(key_name) => dynamic_api_keys.get(key_name).ok_or_else(|| {
                ErrorDetails::ApiKeyMissing {
                    provider_name: PROVIDER_NAME.to_string(),
                }
                .into()
            }),
            XAICredentials::None => Err(ErrorDetails::ApiKeyMissing {
                provider_name: PROVIDER_NAME.to_string(),
            }
            .into()),
        }
    }
}

impl InferenceProvider for XAIProvider {
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
        let mut request_body = serde_json::to_value(XAIRequest::new(&self.model_name, request)?)
            .map_err(|e| {
                Error::new(ErrorDetails::Serialization {
                    message: format!(
                        "Error serializing xAI request: {}",
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
        let request_url = get_chat_url(&XAI_DEFAULT_BASE_URL)?;
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let start_time = Instant::now();
        let request_builder = http_client
            .post(request_url)
            .header("Content-Type", "application/json")
            .bearer_auth(api_key.expose_secret());

        let res = request_builder
            .json(&request_body)
            .headers(headers)
            .send()
            .await
            .map_err(|e| {
                Error::new(ErrorDetails::InferenceClient {
                    status_code: e.status(),
                    message: format!(
                        "Error sending request to xAI: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
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

            let latency = Latency::NonStreaming {
                response_time: start_time.elapsed(),
            };
            Ok(XAIResponseWithMetadata {
                response,
                raw_response,
                latency,
                request: request_body,
                generic_request: request,
            }
            .try_into()?)
        } else {
            let status = res.status();

            let response = res.text().await.map_err(|e| {
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
                &response,
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
        let mut request_body = serde_json::to_value(XAIRequest::new(&self.model_name, request)?)
            .map_err(|e| {
                Error::new(ErrorDetails::Serialization {
                    message: format!(
                        "Error serializing xAI request: {}",
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
            Error::new(ErrorDetails::InferenceServer {
                message: format!(
                    "Error serializing request: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;
        let request_url = get_chat_url(&XAI_DEFAULT_BASE_URL)?;
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
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
                        "Error sending request to xAI: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    status_code: None,
                    raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
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
            provider_type: "xAI".to_string(),
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
            provider_type: PROVIDER_TYPE.to_string(),
        }
        .into())
    }
}

/// This struct defines the supported parameters for the xAI API
/// See the [xAI API documentation](https://docs.x.ai/api/endpoints#chat-completions)
/// for more details.
/// We are not handling logprobs, top_logprobs, n,
/// logit_bias, seed, service_tier, stop, user or response_format.
/// or the deprecated function_call and functions arguments.
#[derive(Debug, Serialize)]
struct XAIRequest<'a> {
    messages: Vec<OpenAIRequestMessage<'a>>,
    model: &'a str,

    #[serde(skip_serializing_if = "Option::is_none")]
    temperature: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    max_tokens: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    seed: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    top_p: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    presence_penalty: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    frequency_penalty: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    response_format: Option<XAIResponseFormat>,
    stream: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    stream_options: Option<StreamOptions>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tools: Option<Vec<OpenAITool<'a>>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool_choice: Option<OpenAIToolChoice<'a>>,
}

impl<'a> XAIRequest<'a> {
    pub fn new(
        model: &'a str,
        request: &'a ModelInferenceRequest<'_>,
    ) -> Result<XAIRequest<'a>, Error> {
        let ModelInferenceRequest {
            temperature,
            max_tokens,
            seed,
            top_p,
            presence_penalty,
            frequency_penalty,
            stream,
            ..
        } = *request;

        let stream_options = match request.stream {
            true => Some(StreamOptions {
                include_usage: true,
            }),
            false => None,
        };

        let response_format = XAIResponseFormat::new(&request.json_mode, request.output_schema);

        let messages = prepare_openai_messages(request)?;

        let (tools, tool_choice, _) = prepare_openai_tools(request);
        Ok(XAIRequest {
            messages,
            model,
            temperature,
            max_tokens,
            seed,
            top_p,
            response_format,
            presence_penalty,
            frequency_penalty,
            stream,
            stream_options,
            tools,
            tool_choice,
        })
    }
}

#[derive(Clone, Debug, Default, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
#[serde(tag = "type")]
enum XAIResponseFormat {
    #[default]
    Text,
    JsonObject,
    JsonSchema {
        json_schema: Value,
    },
}

impl XAIResponseFormat {
    fn new(
        json_mode: &ModelInferenceRequestJsonMode,
        output_schema: Option<&Value>,
    ) -> Option<Self> {
        match json_mode {
            ModelInferenceRequestJsonMode::On => Some(XAIResponseFormat::JsonObject),
            // For now, we never explicitly send `XAIResponseFormat::Text`
            ModelInferenceRequestJsonMode::Off => None,
            ModelInferenceRequestJsonMode::Strict => match output_schema {
                Some(schema) => {
                    let json_schema = json!({"name": "response", "strict": true, "schema": schema});
                    Some(XAIResponseFormat::JsonSchema { json_schema })
                }
                None => Some(XAIResponseFormat::JsonObject),
            },
        }
    }
}

struct XAIResponseWithMetadata<'a> {
    response: OpenAIResponse,
    raw_response: String,
    latency: Latency,
    request: serde_json::Value,
    generic_request: &'a ModelInferenceRequest<'a>,
}

impl<'a> TryFrom<XAIResponseWithMetadata<'a>> for ProviderInferenceResponse {
    type Error = Error;
    fn try_from(value: XAIResponseWithMetadata<'a>) -> Result<Self, Self::Error> {
        let XAIResponseWithMetadata {
            mut response,
            latency,
            request: request_body,
            generic_request,
            raw_response,
        } = value;

        if response.choices.len() != 1 {
            return Err(ErrorDetails::InferenceServer {
                message: format!(
                    "Response has invalid number of choices {}, Expected 1",
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

// Image generation types
#[derive(Debug, Serialize)]
struct XAIImageGenerationRequest {
    model: String,
    prompt: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    n: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    response_format: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    user: Option<String>,
}

#[derive(Debug, Deserialize)]
struct XAIImageResponse {
    data: Vec<XAIImageData>,
    #[serde(skip_serializing_if = "Option::is_none")]
    created: Option<u64>,
}

#[derive(Debug, Deserialize)]
struct XAIImageData {
    #[serde(skip_serializing_if = "Option::is_none")]
    url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    b64_json: Option<String>,
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

// Image generation implementation
impl ImageGenerationProvider for XAIProvider {
    async fn generate_image(
        &self,
        request: &ImageGenerationRequest,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<ImageGenerationProviderResponse, Error> {
        let start_time = Instant::now();
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let url = get_image_generation_url(&XAI_DEFAULT_BASE_URL)?;

        // Build xAI-specific request
        let xai_request = XAIImageGenerationRequest {
            model: self.model_name.clone(),
            prompt: request.prompt.clone(),
            n: request.n,
            response_format: request
                .response_format
                .as_ref()
                .map(|f| f.as_str().to_string()),
            user: request.user.clone(),
        };

        let request_json = serde_json::to_string(&xai_request).map_err(|e| {
            Error::new(ErrorDetails::Serialization {
                message: format!("Failed to serialize xAI image generation request: {e}"),
            })
        })?;

        let request_builder = client
            .post(url)
            .header("Content-Type", "application/json")
            .bearer_auth(api_key.expose_secret())
            .body(request_json.clone());

        let res = request_builder.send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                message: format!("Failed to send xAI image generation request: {e}"),
                status_code: None,
                raw_request: Some(request_json.clone()),
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;

        let latency = Latency::NonStreaming {
            response_time: start_time.elapsed(),
        };

        // Handle error response first to avoid any confusion about ownership
        if !res.status().is_success() {
            return Err(handle_openai_error(
                &request_json,
                res.status(),
                &res.text().await.unwrap_or_default(),
                PROVIDER_TYPE,
            ));
        }

        // Process successful response
        let response_body = res.text().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                message: format!("Failed to read xAI image generation response: {e}"),
                status_code: None,
                raw_request: Some(request_json.clone()),
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;

        let response: XAIImageResponse = serde_json::from_str(&response_body).map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                message: format!("Failed to parse xAI image generation response: {e}"),
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
                    revised_prompt: None, // xAI doesn't provide revised prompts
                })
                .collect(),
            raw_request: request_json,
            raw_response: response_body,
            usage: Usage {
                input_tokens: 0, // xAI doesn't provide token usage for images
                output_tokens: 0,
            },
            latency,
        })
    }
}

#[cfg(test)]
mod tests {
    use std::borrow::Cow;
    use std::time::Duration;

    use uuid::Uuid;

    use super::*;

    use crate::inference::providers::openai::{
        OpenAIFinishReason, OpenAIResponseChoice, OpenAIResponseMessage, OpenAIToolType,
        OpenAIUsage, SpecificToolChoice, SpecificToolFunction,
    };
    use crate::inference::providers::test_helpers::{WEATHER_TOOL, WEATHER_TOOL_CONFIG};
    use crate::inference::types::{
        FinishReason, FunctionType, ModelInferenceRequestJsonMode, RequestMessage, Role,
    };

    #[test]
    fn test_xai_request_new() {
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
            stream: false,
            seed: Some(69),
            json_mode: ModelInferenceRequestJsonMode::Off,
            tool_config: Some(Cow::Borrowed(&WEATHER_TOOL_CONFIG)),
            function_type: FunctionType::Chat,
            output_schema: None,
            extra_body: Default::default(),
            ..Default::default()
        };

        let xai_request = XAIRequest::new("grok-beta", &request_with_tools)
            .expect("failed to create xAI Request during test");

        assert_eq!(xai_request.messages.len(), 1);
        assert_eq!(xai_request.temperature, Some(0.5));
        assert_eq!(xai_request.max_tokens, Some(100));
        assert!(!xai_request.stream);
        assert_eq!(xai_request.seed, Some(69));
        assert!(xai_request.tools.is_some());
        let tools = xai_request.tools.as_ref().unwrap();
        assert_eq!(tools.len(), 1);

        assert_eq!(tools[0].function.name, WEATHER_TOOL.name());
        assert_eq!(tools[0].function.parameters, WEATHER_TOOL.parameters());
        assert_eq!(
            xai_request.tool_choice,
            Some(OpenAIToolChoice::Specific(SpecificToolChoice {
                r#type: OpenAIToolType::Function,
                function: SpecificToolFunction {
                    name: WEATHER_TOOL.name(),
                }
            }))
        );

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
            frequency_penalty: Some(0.2),
            max_tokens: Some(100),
            stream: false,
            seed: Some(69),
            json_mode: ModelInferenceRequestJsonMode::On,
            tool_config: Some(Cow::Borrowed(&WEATHER_TOOL_CONFIG)),
            function_type: FunctionType::Json,
            output_schema: None,
            extra_body: Default::default(),
            ..Default::default()
        };

        let xai_request = XAIRequest::new("grok-beta", &request_with_tools)
            .expect("failed to create xAI Request");

        assert_eq!(xai_request.messages.len(), 2);
        assert_eq!(xai_request.temperature, Some(0.5));
        assert_eq!(xai_request.max_tokens, Some(100));
        assert_eq!(xai_request.top_p, Some(0.9));
        assert_eq!(xai_request.presence_penalty, Some(0.1));
        assert_eq!(xai_request.frequency_penalty, Some(0.2));
        assert!(!xai_request.stream);
        assert_eq!(xai_request.seed, Some(69));

        assert!(xai_request.tools.is_some());
        let tools = xai_request.tools.as_ref().unwrap();
        assert_eq!(tools.len(), 1);

        assert_eq!(tools[0].function.name, WEATHER_TOOL.name());
        assert_eq!(tools[0].function.parameters, WEATHER_TOOL.parameters());
        assert_eq!(
            xai_request.tool_choice,
            Some(OpenAIToolChoice::Specific(SpecificToolChoice {
                r#type: OpenAIToolType::Function,
                function: SpecificToolFunction {
                    name: WEATHER_TOOL.name(),
                }
            }))
        );
    }

    #[test]
    fn test_xai_api_base() {
        assert_eq!(XAI_DEFAULT_BASE_URL.as_str(), "https://api.x.ai/v1");
    }

    #[test]
    fn test_credential_to_xai_credentials() {
        // Test Static credential
        let generic = Credential::Static(SecretString::from("test_key"));
        let creds: XAICredentials = XAICredentials::try_from(generic).unwrap();
        assert!(matches!(creds, XAICredentials::Static(_)));

        // Test Dynamic credential
        let generic = Credential::Dynamic("key_name".to_string());
        let creds = XAICredentials::try_from(generic).unwrap();
        assert!(matches!(creds, XAICredentials::Dynamic(_)));

        // Test Missing credential
        let generic = Credential::Missing;
        let creds = XAICredentials::try_from(generic).unwrap();
        assert!(matches!(creds, XAICredentials::None));

        // Test invalid type
        let generic = Credential::FileContents(SecretString::from("test"));
        let result = XAICredentials::try_from(generic);
        assert!(result.is_err());
        assert!(matches!(
            result.unwrap_err().get_owned_details(),
            ErrorDetails::Config { message } if message.contains("Invalid api_key_location")
        ));
    }
    #[test]
    fn test_xai_response_with_metadata_try_into() {
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
        let xai_response_with_metadata = XAIResponseWithMetadata {
            response: valid_response,
            raw_response: "test_response".to_string(),
            latency: Latency::NonStreaming {
                response_time: Duration::from_secs(0),
            },
            request: serde_json::to_value(XAIRequest::new("grok-beta", &generic_request).unwrap())
                .unwrap(),
            generic_request: &generic_request,
        };
        let inference_response: ProviderInferenceResponse =
            xai_response_with_metadata.try_into().unwrap();

        assert_eq!(inference_response.output.len(), 1);
        assert_eq!(
            inference_response.output[0],
            "Hello, world!".to_string().into()
        );
        assert_eq!(inference_response.finish_reason, Some(FinishReason::Stop));
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

    // Image generation tests

    #[test]
    fn test_xai_image_generation_request_serialization() {
        let request = XAIImageGenerationRequest {
            model: "grok-2-image".to_string(),
            prompt: "A beautiful sunset over mountains".to_string(),
            n: Some(1),
            response_format: Some("url".to_string()),
            user: Some("test_user".to_string()),
        };

        let serialized = serde_json::to_string(&request).unwrap();
        let parsed: serde_json::Value = serde_json::from_str(&serialized).unwrap();

        assert_eq!(parsed["model"], "grok-2-image");
        assert_eq!(parsed["prompt"], "A beautiful sunset over mountains");
        assert_eq!(parsed["n"], 1);
        assert_eq!(parsed["response_format"], "url");
        assert_eq!(parsed["user"], "test_user");
    }

    #[test]
    fn test_xai_image_generation_request_minimal() {
        let request = XAIImageGenerationRequest {
            model: "grok-2-image".to_string(),
            prompt: "Test prompt".to_string(),
            n: None,
            response_format: None,
            user: None,
        };

        let serialized = serde_json::to_string(&request).unwrap();
        let parsed: serde_json::Value = serde_json::from_str(&serialized).unwrap();

        assert_eq!(parsed["model"], "grok-2-image");
        assert_eq!(parsed["prompt"], "Test prompt");
        assert!(!parsed.as_object().unwrap().contains_key("n"));
        assert!(!parsed.as_object().unwrap().contains_key("response_format"));
        assert!(!parsed.as_object().unwrap().contains_key("user"));
    }

    #[test]
    fn test_xai_image_response_deserialization() {
        let response_json = r#"
        {
            "data": [
                {
                    "url": "https://example.com/image1.png"
                },
                {
                    "b64_json": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
                }
            ],
            "created": 1234567890
        }
        "#;

        let response: XAIImageResponse = serde_json::from_str(response_json).unwrap();

        assert_eq!(response.data.len(), 2);
        assert_eq!(
            response.data[0].url.as_ref().unwrap(),
            "https://example.com/image1.png"
        );
        assert!(response.data[0].b64_json.is_none());
        assert!(response.data[1].url.is_none());
        assert!(response.data[1].b64_json.is_some());
        assert_eq!(response.created.unwrap(), 1234567890);
    }

    #[test]
    fn test_xai_image_response_minimal() {
        let response_json = r#"
        {
            "data": [
                {
                    "url": "https://example.com/image.png"
                }
            ]
        }
        "#;

        let response: XAIImageResponse = serde_json::from_str(response_json).unwrap();

        assert_eq!(response.data.len(), 1);
        assert_eq!(
            response.data[0].url.as_ref().unwrap(),
            "https://example.com/image.png"
        );
        assert!(response.created.is_none());
    }

    #[test]
    fn test_get_image_generation_url() {
        let base_url = Url::parse("https://api.x.ai/v1").unwrap();
        let url = get_image_generation_url(&base_url).unwrap();
        assert_eq!(url.as_str(), "https://api.x.ai/v1/images/generations");

        let base_url_with_slash = Url::parse("https://api.x.ai/v1/").unwrap();
        let url = get_image_generation_url(&base_url_with_slash).unwrap();
        assert_eq!(url.as_str(), "https://api.x.ai/v1/images/generations");
    }

    #[test]
    fn test_xai_image_generation_request_to_response_conversion() {
        // Test request serialization with all fields
        let request = XAIImageGenerationRequest {
            model: "grok-2-image".to_string(),
            prompt: "A test prompt".to_string(),
            n: Some(2),
            response_format: Some("b64_json".to_string()),
            user: Some("test-user".to_string()),
        };

        let serialized = serde_json::to_string(&request).unwrap();
        assert!(serialized.contains("\"model\":\"grok-2-image\""));
        assert!(serialized.contains("\"prompt\":\"A test prompt\""));
        assert!(serialized.contains("\"n\":2"));
        assert!(serialized.contains("\"response_format\":\"b64_json\""));
        assert!(serialized.contains("\"user\":\"test-user\""));

        // Test response data conversion logic
        let xai_response = XAIImageResponse {
            created: Some(1234567890),
            data: vec![
                XAIImageData {
                    url: Some("https://example.com/image1.png".to_string()),
                    b64_json: None,
                },
                XAIImageData {
                    url: None,
                    b64_json: Some("base64data".to_string()),
                },
            ],
        };

        // Verify the response structure
        assert_eq!(xai_response.created, Some(1234567890));
        assert_eq!(xai_response.data.len(), 2);
        assert_eq!(
            xai_response.data[0].url,
            Some("https://example.com/image1.png".to_string())
        );
        assert!(xai_response.data[0].b64_json.is_none());
        assert!(xai_response.data[1].url.is_none());
        assert_eq!(
            xai_response.data[1].b64_json,
            Some("base64data".to_string())
        );
    }

    #[test]
    fn test_xai_image_error_handling() {
        // Test error response structure parsing
        let error_json = r#"{
            "error": {
                "type": "invalid_request_error",
                "message": "Invalid prompt"
            }
        }"#;

        // Just verify the JSON can be parsed into expected structure
        let error_value: serde_json::Value = serde_json::from_str(error_json).unwrap();
        assert_eq!(
            error_value["error"]["type"].as_str().unwrap(),
            "invalid_request_error"
        );
        assert_eq!(
            error_value["error"]["message"].as_str().unwrap(),
            "Invalid prompt"
        );

        // Test rate limit error
        let rate_limit_json = r#"{
            "error": {
                "type": "rate_limit_error",
                "message": "Rate limit exceeded. Please try again later."
            }
        }"#;

        let rate_limit_value: serde_json::Value = serde_json::from_str(rate_limit_json).unwrap();
        assert_eq!(
            rate_limit_value["error"]["type"].as_str().unwrap(),
            "rate_limit_error"
        );
        assert!(rate_limit_value["error"]["message"]
            .as_str()
            .unwrap()
            .contains("Rate limit"));
    }
}
