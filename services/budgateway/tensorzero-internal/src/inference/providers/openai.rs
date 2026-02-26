use futures::{Stream, StreamExt, TryStreamExt};
use lazy_static::lazy_static;
use reqwest::multipart::{Form, Part};
use reqwest::{Client, StatusCode};
use reqwest_eventsource::{Event, RequestBuilderExt};
use secrecy::{ExposeSecret, SecretString};
use serde::de::IntoDeserializer;
use serde::{Deserialize, Deserializer, Serialize};
use serde_json::{json, Value};
use std::borrow::Cow;
use std::collections::HashMap;
use std::io::Write;
use std::pin::Pin;
use std::sync::OnceLock;
use std::time::Duration;
use tokio::time::Instant;
use tracing::instrument;
use url::Url;
use uuid::Uuid;

use crate::audio::{
    AudioOutputFormat, AudioTranscriptionProvider, AudioTranscriptionProviderResponse,
    AudioTranscriptionRequest, AudioTranscriptionResponseFormat, AudioTranslationProvider,
    AudioTranslationProviderResponse, AudioTranslationRequest, AudioVoice, SegmentTimestamp,
    TextToSpeechProvider, TextToSpeechProviderResponse, TextToSpeechRequest, TimestampGranularity,
    WordTimestamp,
};
use crate::cache::ModelProviderRequest;
use crate::embeddings::{EmbeddingProvider, EmbeddingProviderResponse, EmbeddingRequest};
use crate::endpoints::inference::InferenceCredentials;
use crate::error::{DisplayOrDebugGateway, Error, ErrorDetails};
use crate::images::{
    ImageData, ImageEditProvider, ImageEditProviderResponse, ImageEditRequest,
    ImageGenerationProvider, ImageGenerationProviderResponse, ImageGenerationRequest,
    ImageVariationProvider, ImageVariationProviderResponse, ImageVariationRequest,
};
use crate::inference::providers::batch::BatchProvider;
use crate::inference::providers::provider_trait::InferenceProvider;
use crate::inference::types::batch::{BatchRequestRow, PollBatchInferenceResponse};
use crate::inference::types::batch::{
    ProviderBatchInferenceOutput, ProviderBatchInferenceResponse,
};
use crate::inference::types::resolved_input::FileWithPath;
use crate::inference::types::{
    batch::{BatchStatus, StartBatchProviderInferenceResponse},
    ContentBlock, ContentBlockChunk, ContentBlockOutput, Latency, ModelInferenceRequest,
    ModelInferenceRequestJsonMode, PeekableProviderInferenceResponseStream,
    ProviderInferenceResponse, ProviderInferenceResponseChunk, RequestMessage, Role, Text,
    TextChunk, Usage,
};
use crate::inference::types::{
    FileKind, FinishReason, ProviderInferenceResponseArgs, ProviderInferenceResponseStreamInner,
};
use crate::model::{build_creds_caching_default, Credential, CredentialLocation, ModelProvider};
use crate::moderation::{
    CategoryAppliedInputTypes, ModerationCategories, ModerationCategoryScores, ModerationInput,
    ModerationProvider, ModerationProviderResponse, ModerationRequest, ModerationResult,
};
use crate::openai_batch::{
    ListBatchesParams, ListBatchesResponse, OpenAIBatchObject, OpenAIFileObject,
};
use crate::tool::{ToolCall, ToolCallChunk, ToolChoice, ToolConfig};

use crate::inference::providers::helpers::inject_extra_request_data;

use super::helpers::{handle_reqwest_error, parse_jsonl_batch_file, JsonlBatchFileInfo};
use super::provider_trait::{TensorZeroEventError, WrappedProvider};

lazy_static! {
    static ref OPENAI_DEFAULT_BASE_URL: Url = {
        #[expect(clippy::expect_used)]
        Url::parse("https://api.openai.com/v1/").expect("Failed to parse OPENAI_DEFAULT_BASE_URL")
    };
}

fn default_api_key_location() -> CredentialLocation {
    CredentialLocation::Env("OPENAI_API_KEY".to_string())
}

const PROVIDER_NAME: &str = "OpenAI";
const PROVIDER_TYPE: &str = "openai";

#[derive(Debug)]
pub struct OpenAIProvider {
    model_name: String,
    api_base: Option<Url>,
    credentials: OpenAICredentials,
}

static DEFAULT_CREDENTIALS: OnceLock<OpenAICredentials> = OnceLock::new();

impl OpenAIProvider {
    pub fn new(
        model_name: String,
        api_base: Option<Url>,
        api_key_location: Option<CredentialLocation>,
    ) -> Result<Self, Error> {
        let credentials = build_creds_caching_default(
            api_key_location,
            default_api_key_location(),
            PROVIDER_TYPE,
            &DEFAULT_CREDENTIALS,
        )?;

        // Check if the api_base has the `/chat/completions` suffix and warn if it does
        if let Some(api_base) = &api_base {
            check_api_base_suffix(api_base);
        }

        Ok(OpenAIProvider {
            model_name,
            api_base,
            credentials,
        })
    }

    pub fn model_name(&self) -> &str {
        &self.model_name
    }
}

/// Checks if the provided OpenAI API base URL has `/chat/completions` suffix and warns if it does.
///
/// This check exists because a common mistake when configuring OpenAI API endpoints is to include
/// `/chat/completions` in the base URL. The gateway automatically appends this path when making requests,
/// so including it in the base URL results in an invalid endpoint like:
/// `http://localhost:1234/v1/chat/completions/chat/completions`
///
/// For example:
/// - Correct: `http://localhost:1234/v1` or `http://localhost:1234/openai/v1/`
/// - Incorrect: `http://localhost:1234/v1/chat/completions`
pub fn check_api_base_suffix(api_base: &Url) {
    let path = api_base.path();
    if path.ends_with("/chat/completions") || path.ends_with("/chat/completions/") {
        tracing::warn!(
            "The gateway automatically appends `/chat/completions` to the `api_base`. You provided `{api_base}` which is likely incorrect. Please remove the `/chat/completions` suffix from `api_base`.",
        );
    }
}

#[derive(Clone, Debug)]
pub enum OpenAICredentials {
    Static(SecretString),
    Dynamic(String),
    None,
}

impl TryFrom<Credential> for OpenAICredentials {
    type Error = Error;

    fn try_from(credentials: Credential) -> Result<Self, Error> {
        match credentials {
            Credential::Static(key) => Ok(OpenAICredentials::Static(key)),
            Credential::Dynamic(key_name) => Ok(OpenAICredentials::Dynamic(key_name)),
            Credential::None => Ok(OpenAICredentials::None),
            Credential::Missing => Ok(OpenAICredentials::None),
            _ => Err(Error::new(ErrorDetails::Config {
                message: "Invalid api_key_location for OpenAI provider".to_string(),
            })),
        }
    }
}

impl OpenAICredentials {
    pub fn get_api_key<'a>(
        &'a self,
        dynamic_api_keys: &'a InferenceCredentials,
    ) -> Result<Option<&'a SecretString>, Error> {
        match self {
            OpenAICredentials::Static(api_key) => Ok(Some(api_key)),
            OpenAICredentials::Dynamic(key_name) => {
                Some(dynamic_api_keys.get(key_name).ok_or_else(|| {
                    ErrorDetails::ApiKeyMissing {
                        provider_name: PROVIDER_NAME.to_string(),
                    }
                    .into()
                }))
                .transpose()
            }
            OpenAICredentials::None => Ok(None),
        }
    }
}

impl WrappedProvider for OpenAIProvider {
    fn make_body<'a>(
        &'a self,
        ModelProviderRequest {
            request,
            provider_name: _,
            model_name: _,
        }: ModelProviderRequest<'a>,
    ) -> Result<serde_json::Value, Error> {
        let request_body = serde_json::to_value(OpenAIRequest::new(&self.model_name, request)?)
            .map_err(|e| {
                Error::new(ErrorDetails::Serialization {
                    message: format!(
                        "Error serializing OpenAI request: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                })
            })?;
        Ok(request_body)
    }
    fn parse_response(
        &self,
        request: &ModelInferenceRequest,
        raw_request: String,
        raw_response: String,
        latency: Latency,
    ) -> Result<ProviderInferenceResponse, Error> {
        let response = serde_json::from_str(&raw_response).map_err(|e| {
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

        OpenAIResponseWithMetadata {
            response,
            raw_response,
            latency,
            raw_request,
            generic_request: request,
        }
        .try_into()
    }

    fn stream_events(
        &self,
        event_source: Pin<
            Box<dyn Stream<Item = Result<Event, TensorZeroEventError>> + Send + 'static>,
        >,
        start_time: Instant,
    ) -> ProviderInferenceResponseStreamInner {
        stream_openai(PROVIDER_TYPE.to_string(), event_source, start_time)
    }
}

impl InferenceProvider for OpenAIProvider {
    async fn infer<'a>(
        &'a self,
        request: ModelProviderRequest<'a>,
        http_client: &'a reqwest::Client,
        dynamic_api_keys: &'a InferenceCredentials,
        model_provider: &'a ModelProvider,
    ) -> Result<ProviderInferenceResponse, Error> {
        let request_url = get_chat_url(self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL))?;
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let start_time = Instant::now();
        let mut request_body = self.make_body(request)?;
        let headers = inject_extra_request_data(
            &request.request.extra_body,
            &request.request.extra_headers,
            model_provider,
            request.model_name,
            &mut request_body,
        )?;

        let mut request_builder = http_client.post(request_url);

        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let raw_request = serde_json::to_string(&request_body).map_err(|e| {
            Error::new(ErrorDetails::Serialization {
                message: format!(
                    "Error serializing request: {}",
                    DisplayOrDebugGateway::new(e)
                ),
            })
        })?;

        let res = request_builder
            .body(raw_request.clone())
            .header(reqwest::header::CONTENT_TYPE, "application/json")
            .headers(headers)
            .send()
            .await
            .map_err(|e| {
                Error::new(ErrorDetails::InferenceClient {
                    status_code: e.status(),
                    message: format!(
                        "Error sending request to OpenAI: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    provider_type: PROVIDER_TYPE.to_string(),
                    raw_request: Some(raw_request.clone()),
                    raw_response: None,
                })
            })?;

        if res.status().is_success() {
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

            let response = serde_json::from_str(&raw_response).map_err(|e| {
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
            Ok(OpenAIResponseWithMetadata {
                response,
                raw_response,
                latency,
                raw_request: raw_request.clone(),
                generic_request: request.request,
            }
            .try_into()?)
        } else {
            Err(handle_openai_error(
                &raw_request.clone(),
                res.status(),
                &res.text().await.map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing error response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: Some(raw_request),
                        raw_response: None,
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?,
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
        let mut request_body = serde_json::to_value(OpenAIRequest::new(&self.model_name, request)?)
            .map_err(|e| {
                Error::new(ErrorDetails::Serialization {
                    message: format!(
                        "Error serializing OpenAI request: {}",
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
        let request_url = get_chat_url(self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL))?;
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let start_time = Instant::now();
        let mut request_builder = http_client
            .post(request_url)
            .header("Content-Type", "application/json");
        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }
        let event_source = request_builder
            .json(&request_body)
            // Important - the 'headers' call should come just before we sent the request with '.eventsource()',
            // so that users can override any of the headers that we set.
            .headers(headers)
            .eventsource()
            .map_err(|e| {
                Error::new(ErrorDetails::InferenceClient {
                    message: format!(
                        "Error sending request to OpenAI: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    status_code: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                    raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                    raw_response: None,
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

    // Get a single chunk from the stream and make sure it is OK then send to client.
    // We want to do this here so that we can tell that the request is working.
    /// 1. Upload the requests to OpenAI as a File
    /// 2. Start the batch inference
    ///    We do them in sequence here.
    async fn start_batch_inference<'a>(
        &'a self,
        requests: &'a [ModelInferenceRequest<'_>],
        client: &'a reqwest::Client,
        dynamic_api_keys: &'a InferenceCredentials,
    ) -> Result<StartBatchProviderInferenceResponse, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let request_url = get_file_url(
            self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL),
            None,
        )?;
        let mut batch_requests = Vec::with_capacity(requests.len());
        for request in requests {
            batch_requests.push(
                OpenAIBatchFileInput::new(request.inference_id, &self.model_name, request).await?,
            );
        }
        let raw_requests: Result<Vec<String>, serde_json::Error> = batch_requests
            .iter()
            .map(|b| serde_json::to_string(&b.body))
            .collect();
        let raw_requests = raw_requests.map_err(|e| {
            Error::new(ErrorDetails::Serialization {
                message: e.to_string(),
            })
        })?;
        let mut jsonl_data = Vec::new();
        for item in batch_requests {
            serde_json::to_writer(&mut jsonl_data, &item).map_err(|e| {
                Error::new(ErrorDetails::Serialization {
                    message: format!(
                        "Error serializing request: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                })
            })?;
            jsonl_data.write_all(b"\n").map_err(|e| {
                Error::new(ErrorDetails::Serialization {
                    message: format!("Error writing to JSONL: {}", DisplayOrDebugGateway::new(e)),
                })
            })?;
        }
        // Create the multipart form
        let form = Form::new().text("purpose", "batch").part(
            "file",
            Part::bytes(jsonl_data)
                .file_name("data.jsonl")
                .mime_str("application/json")
                .map_err(|e| {
                    Error::new(ErrorDetails::Serialization {
                        message: format!(
                            "Error setting MIME type: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                    })
                })?,
        );
        let mut request_builder = client.post(request_url);
        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }
        // Actually upload the file to OpenAI
        let res = request_builder
            .multipart(form)
            .send()
            .await
            .map_err(|e| handle_reqwest_error(e, PROVIDER_TYPE, None))?;
        let text = res.text().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!(
                    "Error retrieving text response: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?;
        let response: OpenAIFileResponse = serde_json::from_str(&text).map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Error parsing JSON response: {e}, text: {text}"),
                raw_request: None,
                raw_response: Some(text.clone()),
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;
        let file_id = response.id;
        let batch_request = OpenAIBatchRequest::new(&file_id);
        let raw_request = serde_json::to_string(&batch_request).map_err(|_| Error::new(ErrorDetails::Serialization { message: "Error serializing OpenAI batch request. This should never happen. Please file a bug report: https://github.com/tensorzero/tensorzero/issues/new".to_string() }))?;
        let request_url =
            get_batch_url(self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL))?;
        let mut request_builder = client.post(request_url);
        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }
        // Now let's actually start the batch inference
        let res = request_builder
            .json(&batch_request)
            .send()
            .await
            .map_err(|e| {
                Error::new(ErrorDetails::InferenceClient {
                    status_code: e.status(),
                    message: format!(
                        "Error sending request to OpenAI: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    provider_type: PROVIDER_TYPE.to_string(),
                    raw_request: Some(serde_json::to_string(&batch_request).unwrap_or_default()),
                    raw_response: None,
                })
            })?;
        let text = res.text().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!(
                    "Error retrieving batch response: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                raw_request: Some(serde_json::to_string(&batch_request).unwrap_or_default()),
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;
        let response: OpenAIBatchResponse = serde_json::from_str(&text).map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Error parsing JSON response: {e}, text: {text}"),
                raw_request: Some(serde_json::to_string(&batch_request).unwrap_or_default()),
                raw_response: Some(text.clone()),
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;
        let batch_params = OpenAIBatchParams {
            file_id: Cow::Owned(file_id),
            batch_id: Cow::Owned(response.id),
        };
        let batch_params = serde_json::to_value(batch_params).map_err(|e| {
            Error::new(ErrorDetails::Serialization {
                message: format!(
                    "Error serializing OpenAI batch params: {}",
                    DisplayOrDebugGateway::new(e)
                ),
            })
        })?;
        let errors = match response.errors {
            Some(errors) => errors
                .data
                .into_iter()
                .map(|error| {
                    serde_json::to_value(&error).map_err(|e| {
                        Error::new(ErrorDetails::Serialization {
                            message: format!(
                                "Error serializing batch error: {}",
                                DisplayOrDebugGateway::new(e)
                            ),
                        })
                    })
                })
                .collect::<Result<Vec<_>, _>>()?,
            None => vec![],
        };
        Ok(StartBatchProviderInferenceResponse {
            batch_id: Uuid::now_v7(),
            batch_params,
            raw_requests,
            raw_request,
            raw_response: text,
            status: BatchStatus::Pending,
            errors,
        })
    }

    #[instrument(skip_all, fields(batch_request = ?batch_request))]
    async fn poll_batch_inference<'a>(
        &'a self,
        batch_request: &'a BatchRequestRow<'a>,
        http_client: &'a reqwest::Client,
        dynamic_api_keys: &'a InferenceCredentials,
    ) -> Result<PollBatchInferenceResponse, Error> {
        let batch_params = OpenAIBatchParams::from_ref(&batch_request.batch_params)?;
        let mut request_url =
            get_batch_url(self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL))?;
        request_url
            .path_segments_mut()
            .map_err(|_| {
                Error::new(ErrorDetails::Inference {
                    message: "Failed to get mutable path segments".to_string(),
                })
            })?
            .push(&batch_params.batch_id);
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let raw_request = request_url.to_string();
        let mut request_builder = http_client
            .get(request_url)
            .header("Content-Type", "application/json");
        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }
        let res = request_builder.send().await.map_err(|e| {
            handle_reqwest_error(
                e,
                PROVIDER_TYPE,
                Some(serde_json::to_string(&batch_request).unwrap_or_default()),
            )
        })?;
        let text = res.text().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!(
                    "Error parsing JSON response: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                raw_request: Some(serde_json::to_string(&batch_request).unwrap_or_default()),
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;
        let response: OpenAIBatchResponse = serde_json::from_str(&text).map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Error parsing JSON response: {e}."),
                raw_request: Some(serde_json::to_string(&batch_request).unwrap_or_default()),
                raw_response: Some(text.clone()),
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;
        let status: BatchStatus = response.status.into();
        let raw_response = text;
        match status {
            BatchStatus::Pending
            | BatchStatus::Validating
            | BatchStatus::InProgress
            | BatchStatus::Finalizing
            | BatchStatus::Cancelling => Ok(PollBatchInferenceResponse::Pending {
                raw_request,
                raw_response,
            }),
            BatchStatus::Completed => {
                let output_file_id = response.output_file_id.as_ref().ok_or_else(|| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: "Output file ID is missing".to_string(),
                        raw_request: Some(
                            serde_json::to_string(&batch_request).unwrap_or_default(),
                        ),
                        raw_response: Some(raw_response.clone()),
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?;
                let response = self
                    .collect_finished_batch(
                        output_file_id,
                        http_client,
                        dynamic_api_keys,
                        raw_request,
                        raw_response,
                    )
                    .await?;
                Ok(PollBatchInferenceResponse::Completed(response))
            }
            BatchStatus::Failed | BatchStatus::Expired | BatchStatus::Cancelled => {
                Ok(PollBatchInferenceResponse::Failed {
                    raw_request,
                    raw_response,
                })
            }
        }
    }
}

impl EmbeddingProvider for OpenAIProvider {
    async fn embed(
        &self,
        request: &EmbeddingRequest,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<EmbeddingProviderResponse, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let request_body = OpenAIEmbeddingRequest::new(&self.model_name, request);
        let request_url =
            get_embedding_url(self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL))?;
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
                        "Error sending request to OpenAI: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    provider_type: PROVIDER_TYPE.to_string(),
                    raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                    raw_response: None,
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

            let response: OpenAIEmbeddingResponse =
                serde_json::from_str(&raw_response).map_err(|e| {
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

            Ok(OpenAIEmbeddingResponseWithMetadata {
                response,
                latency,
                request: request_body,
                raw_response,
            }
            .try_into()?)
        } else {
            Err(handle_openai_error(
                &serde_json::to_string(&request_body).unwrap_or_default(),
                res.status(),
                &res.text().await.map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing error response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                        raw_response: None,
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?,
                PROVIDER_TYPE,
            ))
        }
    }
}

impl ModerationProvider for OpenAIProvider {
    async fn moderate(
        &self,
        request: &ModerationRequest,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<ModerationProviderResponse, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let request_body = OpenAIModerationRequest::new(&request.input, request.model.as_deref());
        let request_url =
            get_moderation_url(self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL))?;
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
                        "Error sending request to OpenAI: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    provider_type: PROVIDER_TYPE.to_string(),
                    raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                    raw_response: None,
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

            let response: OpenAIModerationResponse =
                serde_json::from_str(&raw_response).map_err(|e| {
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

            Ok(OpenAIModerationResponseWithMetadata {
                response,
                latency,
                request: request_body,
                raw_response,
                input: request.input.clone(),
                moderation_request: request,
            }
            .try_into()?)
        } else {
            Err(handle_openai_error(
                &serde_json::to_string(&request_body).unwrap_or_default(),
                res.status(),
                &res.text().await.map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing error response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                        raw_response: None,
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?,
                PROVIDER_TYPE,
            ))
        }
    }
}

impl AudioTranscriptionProvider for OpenAIProvider {
    async fn transcribe(
        &self,
        request: &AudioTranscriptionRequest,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<AudioTranscriptionProviderResponse, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let url = get_audio_transcription_url(
            self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL),
        )?;

        let start_time = Instant::now();

        // Create multipart form
        let mut form = Form::new().text("model", self.model_name.clone()).part(
            "file",
            Part::bytes(request.file.clone())
                .file_name(request.filename.clone())
                .mime_str("audio/mpeg")
                .map_err(|e| {
                    Error::new(ErrorDetails::InferenceClient {
                        status_code: None,
                        message: format!("Failed to set MIME type: {e}"),
                        provider_type: PROVIDER_TYPE.to_string(),
                        raw_request: None,
                        raw_response: None,
                    })
                })?,
        );

        if let Some(language) = &request.language {
            form = form.text("language", language.clone());
        }
        if let Some(prompt) = &request.prompt {
            form = form.text("prompt", prompt.clone());
        }
        if let Some(response_format) = &request.response_format {
            form = form.text("response_format", response_format.as_str());
        }
        if let Some(temperature) = request.temperature {
            form = form.text("temperature", temperature.to_string());
        }
        if let Some(granularities) = &request.timestamp_granularities {
            for g in granularities {
                form = form.text(
                    "timestamp_granularities[]",
                    match g {
                        TimestampGranularity::Word => "word",
                        TimestampGranularity::Segment => "segment",
                    },
                );
            }
        }

        let mut request_builder = client.post(url);
        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let res = request_builder.multipart(form).send().await.map_err(|e| {
            handle_reqwest_error(
                e,
                PROVIDER_TYPE,
                Some(format!("Audio file: {}", request.filename)),
            )
        })?;

        if res.status().is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing text response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: Some(format!("Audio file: {}", request.filename)),
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            // Parse response based on format
            let latency = Latency::NonStreaming {
                response_time: start_time.elapsed(),
            };

            // For text format, the response is just the text
            if matches!(
                request.response_format,
                Some(AudioTranscriptionResponseFormat::Text)
            ) {
                return Ok(AudioTranscriptionProviderResponse {
                    id: request.id,
                    text: raw_response.clone(),
                    language: None,
                    duration: None,
                    words: None,
                    segments: None,
                    created: crate::inference::types::current_timestamp(),
                    raw_request: format!("Audio file: {}", request.filename),
                    raw_response,
                    usage: Usage {
                        input_tokens: 0,
                        output_tokens: 0,
                    },
                    latency,
                });
            }

            // For JSON formats, parse the response
            #[derive(Deserialize)]
            struct OpenAITranscriptionResponse {
                text: String,
                #[serde(skip_serializing_if = "Option::is_none")]
                language: Option<String>,
                #[serde(skip_serializing_if = "Option::is_none")]
                duration: Option<f32>,
                #[serde(skip_serializing_if = "Option::is_none")]
                words: Option<Vec<OpenAIWordTimestamp>>,
                #[serde(skip_serializing_if = "Option::is_none")]
                segments: Option<Vec<OpenAISegmentTimestamp>>,
            }

            #[derive(Deserialize)]
            struct OpenAIWordTimestamp {
                word: String,
                start: f32,
                end: f32,
            }

            #[derive(Deserialize)]
            struct OpenAISegmentTimestamp {
                id: u64,
                seek: u64,
                start: f32,
                end: f32,
                text: String,
                tokens: Vec<u64>,
                temperature: f32,
                avg_logprob: f32,
                compression_ratio: f32,
                no_speech_prob: f32,
            }

            let response: OpenAITranscriptionResponse = serde_json::from_str(&raw_response)
                .map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing JSON response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: Some(format!("Audio file: {}", request.filename)),
                        raw_response: Some(raw_response.clone()),
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?;

            Ok(AudioTranscriptionProviderResponse {
                id: request.id,
                text: response.text,
                language: response.language,
                duration: response.duration,
                words: response.words.map(|words| {
                    words
                        .into_iter()
                        .map(|w| WordTimestamp {
                            word: w.word,
                            start: w.start,
                            end: w.end,
                        })
                        .collect()
                }),
                segments: response.segments.map(|segments| {
                    segments
                        .into_iter()
                        .map(|s| SegmentTimestamp {
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
                }),
                created: crate::inference::types::current_timestamp(),
                raw_request: format!("Audio file: {}", request.filename),
                raw_response,
                usage: Usage {
                    input_tokens: 0,
                    output_tokens: 0,
                },
                latency,
            })
        } else {
            Err(handle_openai_error(
                &format!("Audio file: {}", request.filename),
                res.status(),
                &res.text().await.map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing error response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: Some(format!("Audio file: {}", request.filename)),
                        raw_response: None,
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?,
                PROVIDER_TYPE,
            ))
        }
    }
}

impl AudioTranslationProvider for OpenAIProvider {
    async fn translate(
        &self,
        request: &AudioTranslationRequest,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<AudioTranslationProviderResponse, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let url =
            get_audio_translation_url(self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL))?;

        let start_time = Instant::now();

        // Create multipart form
        let mut form = Form::new().text("model", self.model_name.clone()).part(
            "file",
            Part::bytes(request.file.clone())
                .file_name(request.filename.clone())
                .mime_str("audio/mpeg")
                .map_err(|e| {
                    Error::new(ErrorDetails::InferenceClient {
                        status_code: None,
                        message: format!("Failed to set MIME type: {e}"),
                        provider_type: PROVIDER_TYPE.to_string(),
                        raw_request: None,
                        raw_response: None,
                    })
                })?,
        );

        if let Some(prompt) = &request.prompt {
            form = form.text("prompt", prompt.clone());
        }
        if let Some(response_format) = &request.response_format {
            form = form.text("response_format", response_format.as_str());
        }
        if let Some(temperature) = request.temperature {
            form = form.text("temperature", temperature.to_string());
        }

        let mut request_builder = client.post(url);
        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let res = request_builder.multipart(form).send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                status_code: e.status(),
                message: format!(
                    "Error sending audio translation request to OpenAI: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: Some(format!("Audio file: {}", request.filename)),
                raw_response: None,
            })
        })?;

        if res.status().is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing text response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: Some(format!("Audio file: {}", request.filename)),
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            let latency = Latency::NonStreaming {
                response_time: start_time.elapsed(),
            };

            // For text format, the response is just the text
            if matches!(
                request.response_format,
                Some(AudioTranscriptionResponseFormat::Text)
            ) {
                return Ok(AudioTranslationProviderResponse {
                    id: request.id,
                    text: raw_response.clone(),
                    created: crate::inference::types::current_timestamp(),
                    raw_request: format!("Audio file: {}", request.filename),
                    raw_response,
                    usage: Usage {
                        input_tokens: 0,
                        output_tokens: 0,
                    },
                    latency,
                });
            }

            // For JSON formats, parse the response
            #[derive(Deserialize)]
            struct OpenAITranslationResponse {
                text: String,
            }

            let response: OpenAITranslationResponse =
                serde_json::from_str(&raw_response).map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing JSON response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: Some(format!("Audio file: {}", request.filename)),
                        raw_response: Some(raw_response.clone()),
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?;

            Ok(AudioTranslationProviderResponse {
                id: request.id,
                text: response.text,
                created: crate::inference::types::current_timestamp(),
                raw_request: format!("Audio file: {}", request.filename),
                raw_response,
                usage: Usage {
                    input_tokens: 0,
                    output_tokens: 0,
                },
                latency,
            })
        } else {
            Err(handle_openai_error(
                &format!("Audio file: {}", request.filename),
                res.status(),
                &res.text().await.map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing error response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: Some(format!("Audio file: {}", request.filename)),
                        raw_response: None,
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?,
                PROVIDER_TYPE,
            ))
        }
    }
}

impl TextToSpeechProvider for OpenAIProvider {
    async fn generate_speech(
        &self,
        request: &TextToSpeechRequest,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<TextToSpeechProviderResponse, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let url =
            get_text_to_speech_url(self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL))?;

        let start_time = Instant::now();

        #[derive(Serialize)]
        struct OpenAITextToSpeechRequest {
            model: String,
            input: String,
            voice: String,
            #[serde(skip_serializing_if = "Option::is_none")]
            response_format: Option<String>,
            #[serde(skip_serializing_if = "Option::is_none")]
            speed: Option<f32>,
        }

        let voice_str = match &request.voice {
            AudioVoice::Alloy => "alloy",
            AudioVoice::Ash => "ash",
            AudioVoice::Ballad => "ballad",
            AudioVoice::Coral => "coral",
            AudioVoice::Echo => "echo",
            AudioVoice::Fable => "fable",
            AudioVoice::Onyx => "onyx",
            AudioVoice::Nova => "nova",
            AudioVoice::Sage => "sage",
            AudioVoice::Shimmer => "shimmer",
            AudioVoice::Verse => "verse",
            AudioVoice::Other(voice_name) => {
                return Err(Error::new(ErrorDetails::InvalidRequest {
                    message: format!(
                        "OpenAI TTS does not support voice: '{voice_name}'. Supported voices: alloy, ash, ballad, coral, echo, fable, onyx, nova, sage, shimmer, verse"
                    ),
                }));
            }
        };

        let format_str = request.response_format.as_ref().map(|f| match f {
            AudioOutputFormat::Mp3 => "mp3",
            AudioOutputFormat::Opus => "opus",
            AudioOutputFormat::Aac => "aac",
            AudioOutputFormat::Flac => "flac",
            AudioOutputFormat::Wav => "wav",
            AudioOutputFormat::Pcm => "pcm",
        });

        let request_body = OpenAITextToSpeechRequest {
            model: self.model_name.clone(),
            input: request.input.clone(),
            voice: voice_str.to_string(),
            response_format: format_str.map(|s| s.to_string()),
            speed: request.speed,
        };

        let mut request_builder = client.post(url).header("Content-Type", "application/json");
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
                        "Error sending TTS request to OpenAI: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    provider_type: PROVIDER_TYPE.to_string(),
                    raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                    raw_response: None,
                })
            })?;

        if res.status().is_success() {
            let audio_data = res
                .bytes()
                .await
                .map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error reading audio response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                        raw_response: None,
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?
                .to_vec();

            let latency = Latency::NonStreaming {
                response_time: start_time.elapsed(),
            };

            Ok(TextToSpeechProviderResponse {
                id: request.id,
                audio_data,
                format: request
                    .response_format
                    .clone()
                    .unwrap_or(AudioOutputFormat::Mp3),
                created: crate::inference::types::current_timestamp(),
                raw_request: serde_json::to_string(&request_body).unwrap_or_default(),
                usage: Usage {
                    input_tokens: 0,
                    output_tokens: 0,
                },
                latency,
            })
        } else {
            Err(handle_openai_error(
                &serde_json::to_string(&request_body).unwrap_or_default(),
                res.status(),
                &res.text().await.map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing error response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: Some(serde_json::to_string(&request_body).unwrap_or_default()),
                        raw_response: None,
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?,
                PROVIDER_TYPE,
            ))
        }
    }
}

// Image generation implementation
impl ImageGenerationProvider for OpenAIProvider {
    async fn generate_image(
        &self,
        request: &ImageGenerationRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<ImageGenerationProviderResponse, Error> {
        let start_time = Instant::now();
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let url =
            get_image_generation_url(self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL))?;

        // Build request body with model-specific parameters
        let mut request_body = json!({
            "model": self.model_name,
            "prompt": request.prompt,
        });

        // Add optional parameters
        if let Some(n) = request.n {
            request_body["n"] = json!(n);
        }
        if let Some(size) = &request.size {
            request_body["size"] = json!(size.as_str());
        }
        if let Some(quality) = &request.quality {
            request_body["quality"] = json!(quality.as_str());
        }
        if let Some(style) = &request.style {
            request_body["style"] = json!(style.as_str());
        }
        if let Some(response_format) = &request.response_format {
            request_body["response_format"] = json!(response_format.as_str());
        }
        if let Some(user) = &request.user {
            request_body["user"] = json!(user);
        }

        // GPT-Image-1 specific parameters
        if let Some(background) = &request.background {
            request_body["background"] = json!(background.as_str());
        }
        if let Some(moderation) = &request.moderation {
            request_body["moderation"] = json!(moderation.as_str());
        }
        if let Some(output_compression) = request.output_compression {
            request_body["output_compression"] = json!(output_compression);
        }
        if let Some(output_format) = &request.output_format {
            request_body["output_format"] = json!(output_format.as_str());
        }

        let request_json = serde_json::to_string(&request_body).map_err(|e| {
            Error::new(ErrorDetails::Serialization {
                message: format!("Failed to serialize image generation request: {e}"),
            })
        })?;

        let mut request_builder = client
            .post(url)
            .header("Content-Type", "application/json")
            .body(request_json.clone());

        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let res = request_builder.send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                message: format!("Failed to send image generation request: {e}"),
                status_code: None,
                raw_request: Some(request_json.clone()),
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;

        let latency = Latency::NonStreaming {
            response_time: start_time.elapsed(),
        };

        if res.status().is_success() {
            let response_body = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceClient {
                    message: format!("Failed to read image generation response: {e}"),
                    status_code: None,
                    raw_request: Some(request_json.clone()),
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            let response: OpenAIImageResponse =
                serde_json::from_str(&response_body).map_err(|e| {
                    Error::new(ErrorDetails::InferenceClient {
                        message: format!("Failed to parse image generation response: {e}"),
                        status_code: None,
                        raw_request: Some(request_json.clone()),
                        raw_response: Some(response_body.clone()),
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?;

            Ok(ImageGenerationProviderResponse {
                id: request.id,
                created: response.created,
                data: response
                    .data
                    .into_iter()
                    .map(|d| ImageData {
                        url: d.url,
                        b64_json: d.b64_json,
                        revised_prompt: d.revised_prompt,
                    })
                    .collect(),
                raw_request: request_json.clone(),
                raw_response: response_body,
                usage: Usage {
                    input_tokens: 0, // Images don't have token-based usage
                    output_tokens: 0,
                },
                latency,
            })
        } else {
            Err(handle_openai_error(
                &request_json,
                res.status(),
                &res.text().await.unwrap_or_default(),
                PROVIDER_TYPE,
            ))
        }
    }
}

// Image edit implementation
impl ImageEditProvider for OpenAIProvider {
    async fn edit_image(
        &self,
        request: &ImageEditRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<ImageEditProviderResponse, Error> {
        let start_time = Instant::now();
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let url = get_image_edit_url(self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL))?;

        // Create multipart form
        let mut form = Form::new()
            .text("model", self.model_name.clone())
            .text("prompt", request.prompt.clone())
            .part(
                "image",
                Part::bytes(request.image.clone())
                    .file_name(request.image_filename.clone())
                    .mime_str("image/png")
                    .map_err(|e| {
                        Error::new(ErrorDetails::InferenceClient {
                            message: format!("Failed to set image MIME type: {e}"),
                            status_code: None,
                            raw_request: None,
                            raw_response: None,
                            provider_type: PROVIDER_TYPE.to_string(),
                        })
                    })?,
            );

        // Add mask if provided
        if let Some(mask_data) = &request.mask {
            if let Some(mask_filename) = &request.mask_filename {
                form = form.part(
                    "mask",
                    Part::bytes(mask_data.clone())
                        .file_name(mask_filename.clone())
                        .mime_str("image/png")
                        .map_err(|e| {
                            Error::new(ErrorDetails::InferenceClient {
                                message: format!("Failed to set mask MIME type: {e}"),
                                status_code: None,
                                raw_request: None,
                                raw_response: None,
                                provider_type: PROVIDER_TYPE.to_string(),
                            })
                        })?,
                );
            }
        }

        // Add optional parameters
        if let Some(n) = request.n {
            form = form.text("n", n.to_string());
        }
        if let Some(size) = &request.size {
            form = form.text("size", size.as_str());
        }
        if let Some(response_format) = &request.response_format {
            form = form.text("response_format", response_format.as_str());
        }
        if let Some(user) = &request.user {
            form = form.text("user", user.clone());
        }

        // Model-specific parameters
        if let Some(background) = &request.background {
            form = form.text("background", background.as_str());
        }
        if let Some(quality) = &request.quality {
            form = form.text("quality", quality.as_str());
        }
        if let Some(output_compression) = request.output_compression {
            form = form.text("output_compression", output_compression.to_string());
        }
        if let Some(output_format) = &request.output_format {
            form = form.text("output_format", output_format.as_str());
        }

        let mut request_builder = client.post(url).multipart(form);

        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let res = request_builder.send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                message: format!("Failed to send image edit request: {e}"),
                status_code: None,
                raw_request: None,
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;

        let latency = Latency::NonStreaming {
            response_time: start_time.elapsed(),
        };

        if res.status().is_success() {
            let response_body = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceClient {
                    message: format!("Failed to read image edit response: {e}"),
                    status_code: None,
                    raw_request: None,
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            let response: OpenAIImageResponse =
                serde_json::from_str(&response_body).map_err(|e| {
                    Error::new(ErrorDetails::InferenceClient {
                        message: format!("Failed to parse image edit response: {e}"),
                        status_code: None,
                        raw_request: None,
                        raw_response: Some(response_body.clone()),
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?;

            Ok(ImageEditProviderResponse {
                id: request.id,
                created: response.created,
                data: response
                    .data
                    .into_iter()
                    .map(|d| ImageData {
                        url: d.url,
                        b64_json: d.b64_json,
                        revised_prompt: d.revised_prompt,
                    })
                    .collect(),
                raw_request: "multipart form data".to_string(), // Can't easily serialize multipart
                raw_response: response_body,
                usage: Usage {
                    input_tokens: 0,
                    output_tokens: 0,
                },
                latency,
            })
        } else {
            Err(handle_openai_error(
                "multipart form data",
                res.status(),
                &res.text().await.unwrap_or_default(),
                PROVIDER_TYPE,
            ))
        }
    }
}

// Image variation implementation
impl ImageVariationProvider for OpenAIProvider {
    async fn create_image_variation(
        &self,
        request: &ImageVariationRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<ImageVariationProviderResponse, Error> {
        let start_time = Instant::now();
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let url =
            get_image_variation_url(self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL))?;

        // Create multipart form
        let mut form = Form::new().text("model", self.model_name.clone()).part(
            "image",
            Part::bytes(request.image.clone())
                .file_name(request.image_filename.clone())
                .mime_str("image/png")
                .map_err(|e| {
                    Error::new(ErrorDetails::InferenceClient {
                        message: format!("Failed to set image MIME type: {e}"),
                        status_code: None,
                        raw_request: None,
                        raw_response: None,
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?,
        );

        // Add optional parameters
        if let Some(n) = request.n {
            form = form.text("n", n.to_string());
        }
        if let Some(size) = &request.size {
            form = form.text("size", size.as_str());
        }
        if let Some(response_format) = &request.response_format {
            form = form.text("response_format", response_format.as_str());
        }
        if let Some(user) = &request.user {
            form = form.text("user", user.clone());
        }

        let mut request_builder = client.post(url).multipart(form);

        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let res = request_builder.send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                message: format!("Failed to send image variation request: {e}"),
                status_code: None,
                raw_request: None,
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;

        let latency = Latency::NonStreaming {
            response_time: start_time.elapsed(),
        };

        if res.status().is_success() {
            let response_body = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceClient {
                    message: format!("Failed to read image variation response: {e}"),
                    status_code: None,
                    raw_request: None,
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            let response: OpenAIImageResponse =
                serde_json::from_str(&response_body).map_err(|e| {
                    Error::new(ErrorDetails::InferenceClient {
                        message: format!("Failed to parse image variation response: {e}"),
                        status_code: None,
                        raw_request: None,
                        raw_response: Some(response_body.clone()),
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?;

            Ok(ImageVariationProviderResponse {
                id: request.id,
                created: response.created,
                data: response
                    .data
                    .into_iter()
                    .map(|d| ImageData {
                        url: d.url,
                        b64_json: d.b64_json,
                        revised_prompt: d.revised_prompt,
                    })
                    .collect(),
                raw_request: "multipart form data".to_string(),
                raw_response: response_body,
                usage: Usage {
                    input_tokens: 0,
                    output_tokens: 0,
                },
                latency,
            })
        } else {
            Err(handle_openai_error(
                "multipart form data",
                res.status(),
                &res.text().await.unwrap_or_default(),
                PROVIDER_TYPE,
            ))
        }
    }
}

pub async fn convert_stream_error(provider_type: String, e: reqwest_eventsource::Error) -> Error {
    let message = e.to_string();
    let mut raw_response = None;
    if let reqwest_eventsource::Error::InvalidStatusCode(_, resp) = e {
        raw_response = resp.text().await.ok();
    }
    ErrorDetails::InferenceServer {
        message,
        raw_request: None,
        raw_response,
        provider_type,
    }
    .into()
}

pub fn stream_openai(
    provider_type: String,
    event_source: impl Stream<Item = Result<Event, TensorZeroEventError>> + Send + 'static,
    start_time: Instant,
) -> ProviderInferenceResponseStreamInner {
    let mut tool_call_ids = Vec::new();
    let mut tool_call_names = Vec::new();
    Box::pin(async_stream::stream! {
        futures::pin_mut!(event_source);
        while let Some(ev) = event_source.next().await {
            match ev {
                Err(e) => {
                    match e {
                        TensorZeroEventError::TensorZero(e) => {
                            yield Err(e);
                        }
                        TensorZeroEventError::EventSource(e) => {
                            yield Err(convert_stream_error(provider_type.clone(), e).await);
                        }
                    }
                }
                Ok(event) => match event {
                    Event::Open => continue,
                    Event::Message(message) => {
                        if message.data == "[DONE]" {
                            break;
                        }
                        let data: Result<OpenAIChatChunk, Error> =
                            serde_json::from_str(&message.data).map_err(|e| Error::new(ErrorDetails::InferenceServer {
                                message: format!(
                                    "Error parsing chunk. Error: {e}",
                                ),
                                raw_request: None,
                                raw_response: Some(message.data.clone()),
                                provider_type: provider_type.clone(),
                            }));

                        let latency = start_time.elapsed();
                        let stream_message = data.and_then(|d| {
                            openai_to_tensorzero_chunk(message.data, d, latency, &mut tool_call_ids, &mut tool_call_names)
                        });
                        yield stream_message;
                    }
                },
            }
        }
    })
}

impl OpenAIProvider {
    // Once a batch has been completed we need to retrieve the results from OpenAI using the files API
    #[instrument(skip_all, fields(file_id = file_id))]
    async fn collect_finished_batch(
        &self,
        file_id: &str,
        client: &reqwest::Client,
        credentials: &InferenceCredentials,
        raw_request: String,
        raw_response: String,
    ) -> Result<ProviderBatchInferenceResponse, Error> {
        let file_url = get_file_url(
            self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL),
            Some(file_id),
        )?;
        let api_key = self.credentials.get_api_key(credentials)?;
        let mut request_builder = client.get(file_url);
        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }
        let res = request_builder.send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!(
                    "Error downloading batch results from OpenAI for file {file_id}: {e}"
                ),
                raw_request: None,
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;

        if res.status() != StatusCode::OK {
            return Err(handle_openai_error(
                &raw_request,
                res.status(),
                &res.text().await.map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing error response for file {file_id}: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: None,
                        raw_response: None,
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?,
                PROVIDER_TYPE,
            ));
        }

        parse_jsonl_batch_file::<OpenAIBatchFileRow, _>(
            res.bytes().await,
            JsonlBatchFileInfo {
                file_id: file_id.to_string(),
                raw_request,
                raw_response,
                provider_type: PROVIDER_TYPE.to_string(),
            },
            |r| r.try_into(),
        )
        .await
    }
}

// Generic helper function to join URL paths
fn join_url(base_url: &Url, path: &str) -> Result<Url, Error> {
    let mut url = base_url.clone();
    if !url.path().ends_with('/') {
        url.set_path(&format!("{}/", url.path()));
    }
    url.join(path).map_err(|e| {
        Error::new(ErrorDetails::InvalidBaseUrl {
            message: e.to_string(),
        })
    })
}

pub(super) fn get_chat_url(base_url: &Url) -> Result<Url, Error> {
    join_url(base_url, "chat/completions")
}

fn get_file_url(base_url: &Url, file_id: Option<&str>) -> Result<Url, Error> {
    let path = if let Some(id) = file_id {
        format!("files/{id}/content")
    } else {
        "files".to_string()
    };
    join_url(base_url, &path)
}

fn get_batch_url(base_url: &Url) -> Result<Url, Error> {
    join_url(base_url, "batches")
}

fn get_embedding_url(base_url: &Url) -> Result<Url, Error> {
    join_url(base_url, "embeddings")
}

fn get_moderation_url(base_url: &Url) -> Result<Url, Error> {
    join_url(base_url, "moderations")
}

fn get_audio_transcription_url(base_url: &Url) -> Result<Url, Error> {
    join_url(base_url, "audio/transcriptions")
}

fn get_audio_translation_url(base_url: &Url) -> Result<Url, Error> {
    join_url(base_url, "audio/translations")
}

fn get_text_to_speech_url(base_url: &Url) -> Result<Url, Error> {
    join_url(base_url, "audio/speech")
}

fn get_image_generation_url(base_url: &Url) -> Result<Url, Error> {
    join_url(base_url, "images/generations")
}

fn get_image_edit_url(base_url: &Url) -> Result<Url, Error> {
    join_url(base_url, "images/edits")
}

fn get_image_variation_url(base_url: &Url) -> Result<Url, Error> {
    join_url(base_url, "images/variations")
}

// OpenAI Image API response types
#[derive(Debug, Deserialize)]
struct OpenAIImageResponse {
    created: u64,
    data: Vec<OpenAIImageData>,
}

#[derive(Debug, Deserialize)]
struct OpenAIImageData {
    url: Option<String>,
    b64_json: Option<String>,
    revised_prompt: Option<String>,
}

pub(super) fn handle_openai_error(
    raw_request: &str,
    response_code: StatusCode,
    response_body: &str,
    provider_type: &str,
) -> Error {
    match response_code {
        StatusCode::BAD_REQUEST
        | StatusCode::UNAUTHORIZED
        | StatusCode::FORBIDDEN
        | StatusCode::TOO_MANY_REQUESTS => ErrorDetails::InferenceClient {
            status_code: Some(response_code),
            message: response_body.to_string(),
            raw_request: Some(raw_request.to_string()),
            raw_response: Some(response_body.to_string()),
            provider_type: provider_type.to_string(),
        }
        .into(),
        _ => ErrorDetails::InferenceServer {
            message: response_body.to_string(),
            raw_request: Some(raw_request.to_string()),
            raw_response: Some(response_body.to_string()),
            provider_type: provider_type.to_string(),
        }
        .into(),
    }
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub(super) struct OpenAISystemRequestMessage<'a> {
    pub content: Cow<'a, str>,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub(super) struct OpenAIUserRequestMessage<'a> {
    #[serde(serialize_with = "serialize_text_content_vec")]
    pub(super) content: Vec<OpenAIContentBlock<'a>>,
}

fn serialize_text_content_vec<S>(
    content: &Vec<OpenAIContentBlock<'_>>,
    serializer: S,
) -> Result<S::Ok, S::Error>
where
    S: serde::Serializer,
{
    // If we have a single text block, serialize it as a string
    // to stay compatible with older providers which may not support content blocks
    if let [OpenAIContentBlock::Text { text }] = &content.as_slice() {
        text.serialize(serializer)
    } else {
        content.serialize(serializer)
    }
}

fn serialize_optional_text_content_vec<S>(
    content: &Option<Vec<OpenAIContentBlock<'_>>>,
    serializer: S,
) -> Result<S::Ok, S::Error>
where
    S: serde::Serializer,
{
    match content {
        Some(vec) => serialize_text_content_vec(vec, serializer),
        None => serializer.serialize_none(),
    }
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct OpenAIFile<'a> {
    file_data: Cow<'a, str>,
    filename: Cow<'a, str>,
}

#[derive(Clone, Debug, PartialEq)]
pub enum OpenAIContentBlock<'a> {
    Text { text: Cow<'a, str> },
    ImageUrl { image_url: OpenAIImageUrl },
    File { file: OpenAIFile<'a> },
    Unknown { data: Cow<'a, Value> },
}

impl Serialize for OpenAIContentBlock<'_> {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        #[derive(Serialize)]
        #[serde(tag = "type", rename_all = "snake_case")]
        enum Helper<'a> {
            Text { text: &'a str },
            ImageUrl { image_url: &'a OpenAIImageUrl },
            File { file: &'a OpenAIFile<'a> },
        }
        match self {
            OpenAIContentBlock::Text { text } => Helper::Text { text }.serialize(serializer),
            OpenAIContentBlock::ImageUrl { image_url } => {
                Helper::ImageUrl { image_url }.serialize(serializer)
            }
            OpenAIContentBlock::File { file } => Helper::File { file }.serialize(serializer),
            OpenAIContentBlock::Unknown { data } => data.serialize(serializer),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub struct OpenAIImageUrl {
    pub url: String,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OpenAIRequestFunctionCall<'a> {
    pub name: &'a str,
    pub arguments: &'a str,
}

#[derive(Serialize, Debug, Clone, PartialEq, Deserialize)]
pub struct OpenAIRequestToolCall<'a> {
    pub id: &'a str,
    pub r#type: OpenAIToolType,
    pub function: OpenAIRequestFunctionCall<'a>,
}

impl<'a> From<&'a ToolCall> for OpenAIRequestToolCall<'a> {
    fn from(tool_call: &'a ToolCall) -> Self {
        OpenAIRequestToolCall {
            id: &tool_call.id,
            r#type: OpenAIToolType::Function,
            function: OpenAIRequestFunctionCall {
                name: &tool_call.name,
                arguments: &tool_call.arguments,
            },
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub(super) struct OpenAIAssistantRequestMessage<'a> {
    #[serde(
        skip_serializing_if = "Option::is_none",
        serialize_with = "serialize_optional_text_content_vec"
    )]
    pub content: Option<Vec<OpenAIContentBlock<'a>>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tool_calls: Option<Vec<OpenAIRequestToolCall<'a>>>,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub(super) struct OpenAIToolRequestMessage<'a> {
    pub content: &'a str,
    pub tool_call_id: &'a str,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(tag = "role")]
#[serde(rename_all = "lowercase")]
pub(super) enum OpenAIRequestMessage<'a> {
    System(OpenAISystemRequestMessage<'a>),
    User(OpenAIUserRequestMessage<'a>),
    Assistant(OpenAIAssistantRequestMessage<'a>),
    Tool(OpenAIToolRequestMessage<'a>),
}

impl OpenAIRequestMessage<'_> {
    pub fn content_contains_case_insensitive(&self, value: &str) -> bool {
        match self {
            OpenAIRequestMessage::System(msg) => msg.content.to_lowercase().contains(value),
            OpenAIRequestMessage::User(msg) => msg.content.iter().any(|c| match c {
                OpenAIContentBlock::Text { text } => text.to_lowercase().contains(value),
                OpenAIContentBlock::ImageUrl { .. } | OpenAIContentBlock::File { .. } => false,
                // Don't inspect the contents of 'unknown' blocks
                OpenAIContentBlock::Unknown { data: _ } => false,
            }),
            OpenAIRequestMessage::Assistant(msg) => {
                if let Some(content) = &msg.content {
                    content.iter().any(|c| match c {
                        OpenAIContentBlock::Text { text } => text.to_lowercase().contains(value),
                        OpenAIContentBlock::ImageUrl { .. } | OpenAIContentBlock::File { .. } => {
                            false
                        }
                        // Don't inspect the contents of 'unknown' blocks
                        OpenAIContentBlock::Unknown { data: _ } => false,
                    })
                } else {
                    false
                }
            }
            OpenAIRequestMessage::Tool(msg) => msg.content.to_lowercase().contains(value),
        }
    }
}

pub(super) fn prepare_openai_messages<'a>(
    request: &'a ModelInferenceRequest<'_>,
) -> Result<Vec<OpenAIRequestMessage<'a>>, Error> {
    let mut messages = Vec::with_capacity(request.messages.len());
    for message in request.messages.iter() {
        messages.extend(tensorzero_to_openai_messages(message)?);
    }
    if let Some(system_msg) = tensorzero_to_openai_system_message(
        request.system.as_deref(),
        &request.json_mode,
        &messages,
    ) {
        messages.insert(0, system_msg);
    }
    Ok(messages)
}

/// If there are no tools passed or the tools are empty, return None for both tools and tool_choice
/// Otherwise convert the tool choice and tools to OpenAI format
pub(super) fn prepare_openai_tools<'a>(
    request: &'a ModelInferenceRequest,
) -> (
    Option<Vec<OpenAITool<'a>>>,
    Option<OpenAIToolChoice<'a>>,
    Option<bool>,
) {
    match &request.tool_config {
        None => (None, None, None),
        Some(tool_config) => {
            if tool_config.tools_available.is_empty() {
                return (None, None, None);
            }
            let tools = Some(
                tool_config
                    .tools_available
                    .iter()
                    .map(|tool| tool.into())
                    .collect(),
            );
            let tool_choice = Some((&tool_config.tool_choice).into());
            let parallel_tool_calls = tool_config.parallel_tool_calls;
            (tools, tool_choice, parallel_tool_calls)
        }
    }
}

/// This function is complicated only by the fact that OpenAI and Azure require
/// different instructions depending on the json mode and the content of the messages.
///
/// If ModelInferenceRequestJsonMode::On and the system message or instructions does not contain "JSON"
/// the request will return an error.
/// So, we need to format the instructions to include "Respond using JSON." if it doesn't already.
pub(super) fn tensorzero_to_openai_system_message<'a>(
    system: Option<&'a str>,
    json_mode: &ModelInferenceRequestJsonMode,
    messages: &[OpenAIRequestMessage<'a>],
) -> Option<OpenAIRequestMessage<'a>> {
    match system {
        Some(system) => {
            match json_mode {
                ModelInferenceRequestJsonMode::On => {
                    if messages
                        .iter()
                        .any(|msg| msg.content_contains_case_insensitive("json"))
                        || system.to_lowercase().contains("json")
                    {
                        OpenAIRequestMessage::System(OpenAISystemRequestMessage {
                            content: Cow::Borrowed(system),
                        })
                    } else {
                        let formatted_instructions = format!("Respond using JSON.\n\n{system}");
                        OpenAIRequestMessage::System(OpenAISystemRequestMessage {
                            content: Cow::Owned(formatted_instructions),
                        })
                    }
                }

                // If JSON mode is either off or strict, we don't need to do anything special
                _ => OpenAIRequestMessage::System(OpenAISystemRequestMessage {
                    content: Cow::Borrowed(system),
                }),
            }
            .into()
        }
        None => match *json_mode {
            ModelInferenceRequestJsonMode::On => {
                Some(OpenAIRequestMessage::System(OpenAISystemRequestMessage {
                    content: Cow::Owned("Respond using JSON.".to_string()),
                }))
            }
            _ => None,
        },
    }
}

pub(super) fn tensorzero_to_openai_messages(
    message: &RequestMessage,
) -> Result<Vec<OpenAIRequestMessage<'_>>, Error> {
    match message.role {
        Role::User => tensorzero_to_openai_user_messages(&message.content),
        Role::Assistant => tensorzero_to_openai_assistant_messages(&message.content),
    }
}

fn tensorzero_to_openai_user_messages(
    content_blocks: &[ContentBlock],
) -> Result<Vec<OpenAIRequestMessage<'_>>, Error> {
    // We need to separate the tool result messages from the user content blocks.

    let mut messages = Vec::new();
    let mut user_content_blocks = Vec::new();

    for block in content_blocks.iter() {
        match block {
            ContentBlock::Text(Text { text }) => {
                user_content_blocks.push(OpenAIContentBlock::Text {
                    text: Cow::Borrowed(text),
                });
            }
            ContentBlock::ToolCall(_) => {
                return Err(Error::new(ErrorDetails::InvalidMessage {
                    message: "Tool calls are not supported in user messages".to_string(),
                }));
            }
            ContentBlock::ToolResult(tool_result) => {
                messages.push(OpenAIRequestMessage::Tool(OpenAIToolRequestMessage {
                    content: &tool_result.result,
                    tool_call_id: &tool_result.id,
                }));
            }
            ContentBlock::File(FileWithPath {
                file,
                storage_path: _,
            }) => {
                let data = format!("data:{};base64,{}", file.mime_type, file.data()?);
                match file.mime_type {
                    FileKind::Jpeg | FileKind::Png | FileKind::WebP => {
                        user_content_blocks.push(OpenAIContentBlock::ImageUrl {
                            image_url: OpenAIImageUrl {
                                // This will only produce an error if we pass in a bad
                                // `Base64File` (with missing file data)
                                url: data,
                            },
                        });
                    }
                    FileKind::Pdf => {
                        user_content_blocks.push(OpenAIContentBlock::File {
                            file: OpenAIFile {
                                file_data: Cow::Owned(data),
                                // TODO - should we allow the user to specify the file name?
                                filename: Cow::Borrowed("input.pdf"),
                            },
                        });
                    }
                }
            }
            ContentBlock::Thought(_) => {
                // OpenAI doesn't support thought blocks.
                // This can only happen if the thought block was generated by another model provider.
                // At this point, we can either convert the thought blocks to text or drop them.
                // We chose to drop them, because it's more consistent with the behavior that OpenAI expects.

                // TODO (#1361): test that this warning is logged when we drop thought blocks
                tracing::warn!(
                    "Dropping `thought` content block from user message. OpenAI does not support them."
                );
            }
            ContentBlock::Unknown {
                data,
                model_provider_name: _,
            } => {
                user_content_blocks.push(OpenAIContentBlock::Unknown {
                    data: Cow::Borrowed(data),
                });
            }
        };
    }

    // If there are any user content blocks, combine them into a single user message.
    if !user_content_blocks.is_empty() {
        messages.push(OpenAIRequestMessage::User(OpenAIUserRequestMessage {
            content: user_content_blocks,
        }));
    }

    Ok(messages)
}

fn tensorzero_to_openai_assistant_messages(
    content_blocks: &[ContentBlock],
) -> Result<Vec<OpenAIRequestMessage<'_>>, Error> {
    // We need to separate the tool result messages from the assistant content blocks.
    let mut assistant_content_blocks = Vec::new();
    let mut assistant_tool_calls = Vec::new();

    for block in content_blocks.iter() {
        match block {
            ContentBlock::Text(Text { text }) => {
                assistant_content_blocks.push(OpenAIContentBlock::Text {
                    text: Cow::Borrowed(text),
                });
            }
            ContentBlock::ToolCall(tool_call) => {
                let tool_call = OpenAIRequestToolCall {
                    id: &tool_call.id,
                    r#type: OpenAIToolType::Function,
                    function: OpenAIRequestFunctionCall {
                        name: &tool_call.name,
                        arguments: &tool_call.arguments,
                    },
                };

                assistant_tool_calls.push(tool_call);
            }
            ContentBlock::ToolResult(_) => {
                return Err(Error::new(ErrorDetails::InvalidMessage {
                    message: "Tool results are not supported in assistant messages".to_string(),
                }));
            }
            ContentBlock::File(FileWithPath {
                file,
                storage_path: _,
            }) => {
                file.mime_type.require_image(PROVIDER_TYPE)?;
                assistant_content_blocks.push(OpenAIContentBlock::ImageUrl {
                    image_url: OpenAIImageUrl {
                        // This will only produce an error if we pass in a bad
                        // `Base64File` (with missing file data)
                        url: format!("data:{};base64,{}", file.mime_type, file.data()?),
                    },
                });
            }
            ContentBlock::Thought(_) => {
                // OpenAI doesn't support thought blocks.
                // This can only happen if the thought block was generated by another model provider.
                // At this point, we can either convert the thought blocks to text or drop them.
                // We chose to drop them, because it's more consistent with the behavior that OpenAI expects.

                // TODO (#1361): test that this warning is logged when we drop thought blocks
                tracing::warn!(
                    "Dropping `thought` content block from assistant message. OpenAI does not support them."
                );
            }
            ContentBlock::Unknown {
                data,
                model_provider_name: _,
            } => {
                assistant_content_blocks.push(OpenAIContentBlock::Unknown {
                    data: Cow::Borrowed(data),
                });
            }
        }
    }

    let content = match assistant_content_blocks.len() {
        0 => None,
        _ => Some(assistant_content_blocks),
    };

    let tool_calls = match assistant_tool_calls.len() {
        0 => None,
        _ => Some(assistant_tool_calls),
    };

    let message = OpenAIRequestMessage::Assistant(OpenAIAssistantRequestMessage {
        content,
        tool_calls,
    });

    Ok(vec![message])
}

#[derive(Clone, Debug, Default, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
#[serde(tag = "type")]
enum OpenAIResponseFormat {
    #[default]
    Text,
    JsonObject,
    JsonSchema {
        json_schema: Value,
    },
}

impl OpenAIResponseFormat {
    fn new(
        json_mode: &ModelInferenceRequestJsonMode,
        output_schema: Option<&Value>,
        model: &str,
    ) -> Option<Self> {
        if model.contains("3.5") && *json_mode == ModelInferenceRequestJsonMode::Strict {
            return Some(OpenAIResponseFormat::JsonObject);
        }

        match json_mode {
            ModelInferenceRequestJsonMode::On => Some(OpenAIResponseFormat::JsonObject),
            // For now, we never explicitly send `OpenAIResponseFormat::Text`
            ModelInferenceRequestJsonMode::Off => None,
            ModelInferenceRequestJsonMode::Strict => match output_schema {
                Some(schema) => {
                    let json_schema = json!({"name": "response", "strict": true, "schema": schema});
                    Some(OpenAIResponseFormat::JsonSchema { json_schema })
                }
                None => Some(OpenAIResponseFormat::JsonObject),
            },
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum OpenAIToolType {
    Function,
}

#[derive(Debug, PartialEq, Serialize)]
pub(super) struct OpenAIFunction<'a> {
    pub(super) name: &'a str,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(super) description: Option<&'a str>,
    pub parameters: &'a Value,
}

#[derive(Debug, PartialEq, Serialize)]
pub(super) struct OpenAITool<'a> {
    pub(super) r#type: OpenAIToolType,
    pub(super) function: OpenAIFunction<'a>,
    pub(super) strict: bool,
}

impl<'a> From<&'a ToolConfig> for OpenAITool<'a> {
    fn from(tool: &'a ToolConfig) -> Self {
        OpenAITool {
            r#type: OpenAIToolType::Function,
            function: OpenAIFunction {
                name: tool.name(),
                description: Some(tool.description()),
                parameters: tool.parameters(),
            },
            strict: tool.strict(),
        }
    }
}

#[derive(Debug, Deserialize, Serialize)]
struct OpenAIBatchParams<'a> {
    file_id: Cow<'a, str>,
    batch_id: Cow<'a, str>,
}

impl<'a> OpenAIBatchParams<'a> {
    #[instrument(name = "OpenAIBatchParams::from_ref", skip_all, fields(%value))]
    fn from_ref(value: &'a Value) -> Result<Self, Error> {
        let file_id = value
            .get("file_id")
            .ok_or_else(|| {
                Error::new(ErrorDetails::InvalidBatchParams {
                    message: "Missing file_id in batch params".to_string(),
                })
            })?
            .as_str()
            .ok_or_else(|| {
                Error::new(ErrorDetails::InvalidBatchParams {
                    message: "file_id must be a string".to_string(),
                })
            })?;
        let batch_id = value
            .get("batch_id")
            .ok_or_else(|| {
                Error::new(ErrorDetails::InvalidBatchParams {
                    message: "Missing batch_id in batch params".to_string(),
                })
            })?
            .as_str()
            .ok_or_else(|| {
                Error::new(ErrorDetails::InvalidBatchParams {
                    message: "batch_id must be a string".to_string(),
                })
            })?;
        Ok(Self {
            file_id: Cow::Borrowed(file_id),
            batch_id: Cow::Borrowed(batch_id),
        })
    }
}

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(untagged)]
pub(super) enum OpenAIToolChoice<'a> {
    String(OpenAIToolChoiceString),
    Specific(SpecificToolChoice<'a>),
}

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
pub(super) enum OpenAIToolChoiceString {
    None,
    Auto,
    Required,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub(super) struct SpecificToolChoice<'a> {
    pub(super) r#type: OpenAIToolType,
    pub(super) function: SpecificToolFunction<'a>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub(super) struct SpecificToolFunction<'a> {
    pub(super) name: &'a str,
}

impl Default for OpenAIToolChoice<'_> {
    fn default() -> Self {
        OpenAIToolChoice::String(OpenAIToolChoiceString::None)
    }
}

impl<'a> From<&'a ToolChoice> for OpenAIToolChoice<'a> {
    fn from(tool_choice: &'a ToolChoice) -> Self {
        match tool_choice {
            ToolChoice::None => OpenAIToolChoice::String(OpenAIToolChoiceString::None),
            ToolChoice::Auto => OpenAIToolChoice::String(OpenAIToolChoiceString::Auto),
            ToolChoice::Required => OpenAIToolChoice::String(OpenAIToolChoiceString::Required),
            ToolChoice::Specific(tool_name) => OpenAIToolChoice::Specific(SpecificToolChoice {
                r#type: OpenAIToolType::Function,
                function: SpecificToolFunction { name: tool_name },
            }),
        }
    }
}

#[derive(Debug, Serialize)]
pub(super) struct StreamOptions {
    pub(super) include_usage: bool,
}

/// This struct defines the supported parameters for the OpenAI API
/// See the [OpenAI API documentation](https://platform.openai.com/docs/api-reference/chat/create)
/// for more details.
/// Note: n > 1 is not yet fully supported by TensorZero.
/// Legacy parameters function_call and functions are not supported.
#[derive(Debug, Serialize)]
struct OpenAIRequest<'a> {
    messages: Vec<OpenAIRequestMessage<'a>>,
    model: &'a str,
    #[serde(skip_serializing_if = "Option::is_none")]
    temperature: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    max_completion_tokens: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    seed: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    top_p: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    presence_penalty: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    frequency_penalty: Option<f32>,
    stream: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    stream_options: Option<StreamOptions>,
    #[serde(skip_serializing_if = "Option::is_none")]
    response_format: Option<OpenAIResponseFormat>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tools: Option<Vec<OpenAITool<'a>>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool_choice: Option<OpenAIToolChoice<'a>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    parallel_tool_calls: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    logprobs: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    top_logprobs: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    stop: Option<Vec<&'a str>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    n: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    logit_bias: Option<HashMap<String, f32>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    user: Option<&'a str>,
}

impl<'a> OpenAIRequest<'a> {
    pub fn new(
        model: &'a str,
        request: &'a ModelInferenceRequest<'_>,
    ) -> Result<OpenAIRequest<'a>, Error> {
        let response_format =
            OpenAIResponseFormat::new(&request.json_mode, request.output_schema, model);
        let stream_options = match request.stream {
            true => Some(StreamOptions {
                include_usage: true,
            }),
            false => None,
        };
        let mut messages = prepare_openai_messages(request)?;

        let (tools, tool_choice, mut parallel_tool_calls) = prepare_openai_tools(request);
        if model.to_lowercase().starts_with("o1") && parallel_tool_calls == Some(false) {
            parallel_tool_calls = None;
        }

        if model.to_lowercase().starts_with("o1-mini") {
            if let Some(OpenAIRequestMessage::System(_)) = messages.first() {
                if let OpenAIRequestMessage::System(system_msg) = messages.remove(0) {
                    let user_msg = OpenAIRequestMessage::User(OpenAIUserRequestMessage {
                        content: vec![OpenAIContentBlock::Text {
                            text: system_msg.content,
                        }],
                    });
                    messages.insert(0, user_msg);
                }
            }
        }

        Ok(OpenAIRequest {
            messages,
            model,
            temperature: request.temperature,
            max_completion_tokens: request.max_tokens,
            seed: request.seed,
            top_p: request.top_p,
            presence_penalty: request.presence_penalty,
            frequency_penalty: request.frequency_penalty,
            stream: request.stream,
            stream_options,
            response_format,
            tools,
            tool_choice,
            parallel_tool_calls,
            logprobs: if request.logprobs { Some(true) } else { None },
            top_logprobs: request.top_logprobs,
            stop: request
                .stop
                .as_ref()
                .map(|stops| stops.iter().map(|s| s.as_ref()).collect()),
            n: request.n,
            logit_bias: request.logit_bias.clone(),
            user: request.user.as_deref(),
        })
    }
}

#[derive(Debug, Serialize)]
struct OpenAIBatchFileInput<'a> {
    custom_id: String,
    method: String,
    url: String,
    body: OpenAIRequest<'a>,
}

impl<'a> OpenAIBatchFileInput<'a> {
    async fn new(
        inference_id: Uuid,
        model: &'a str,
        request: &'a ModelInferenceRequest<'_>,
    ) -> Result<Self, Error> {
        let body = OpenAIRequest::new(model, request)?;
        Ok(Self {
            custom_id: inference_id.to_string(),
            method: "POST".to_string(),
            url: "/v1/chat/completions".to_string(),
            body,
        })
    }
}

#[derive(Debug, Serialize)]
struct OpenAIBatchRequest<'a> {
    input_file_id: &'a str,
    endpoint: &'a str,
    completion_window: &'a str,
    // metadata: HashMap<String, String>
}

impl<'a> OpenAIBatchRequest<'a> {
    fn new(input_file_id: &'a str) -> Self {
        Self {
            input_file_id,
            endpoint: "/v1/chat/completions",
            completion_window: "24h",
        }
    }
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub(super) struct OpenAIUsage {
    pub prompt_tokens: u32,
    #[serde(default)]
    pub completion_tokens: u32,
    pub total_tokens: u32,
}

impl From<OpenAIUsage> for Usage {
    fn from(usage: OpenAIUsage) -> Self {
        Usage {
            input_tokens: usage.prompt_tokens,
            output_tokens: usage.completion_tokens,
        }
    }
}

#[derive(Serialize, Debug, Clone, PartialEq, Deserialize)]
struct OpenAIResponseFunctionCall {
    name: String,
    arguments: String,
}

#[derive(Serialize, Debug, Clone, PartialEq, Deserialize)]
pub(super) struct OpenAIResponseToolCall {
    id: String,
    r#type: OpenAIToolType,
    function: OpenAIResponseFunctionCall,
}

impl From<OpenAIResponseToolCall> for ToolCall {
    fn from(openai_tool_call: OpenAIResponseToolCall) -> Self {
        ToolCall {
            id: openai_tool_call.id,
            name: openai_tool_call.function.name,
            arguments: openai_tool_call.function.arguments,
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub(super) struct OpenAIResponseMessage {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(super) content: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(super) tool_calls: Option<Vec<OpenAIResponseToolCall>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(super) reasoning_content: Option<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
#[serde(rename_all = "snake_case")]
pub(super) enum OpenAIFinishReason {
    Stop,
    Length,
    ContentFilter,
    ToolCalls,
    FunctionCall,
    #[serde(other)]
    Unknown,
}

impl From<OpenAIFinishReason> for FinishReason {
    fn from(finish_reason: OpenAIFinishReason) -> Self {
        match finish_reason {
            OpenAIFinishReason::Stop => FinishReason::Stop,
            OpenAIFinishReason::Length => FinishReason::Length,
            OpenAIFinishReason::ContentFilter => FinishReason::ContentFilter,
            OpenAIFinishReason::ToolCalls => FinishReason::ToolCall,
            OpenAIFinishReason::FunctionCall => FinishReason::ToolCall,
            OpenAIFinishReason::Unknown => FinishReason::Unknown,
        }
    }
}

// Leaving out logprobs and finish_reason for now
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub(super) struct OpenAIResponseChoice {
    pub(super) index: u8,
    pub(super) message: OpenAIResponseMessage,
    pub(super) finish_reason: OpenAIFinishReason,
}

// Leaving out id, created, model, service_tier, system_fingerprint, object for now
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub(super) struct OpenAIResponse {
    pub(super) choices: Vec<OpenAIResponseChoice>,
    pub(super) usage: OpenAIUsage,
}

struct OpenAIResponseWithMetadata<'a> {
    response: OpenAIResponse,
    latency: Latency,
    raw_request: String,
    generic_request: &'a ModelInferenceRequest<'a>,
    raw_response: String,
}

impl<'a> TryFrom<OpenAIResponseWithMetadata<'a>> for ProviderInferenceResponse {
    type Error = Error;
    fn try_from(value: OpenAIResponseWithMetadata<'a>) -> Result<Self, Self::Error> {
        let OpenAIResponseWithMetadata {
            mut response,
            latency,
            raw_request,
            raw_response,
            generic_request,
        } = value;
        if response.choices.len() != 1 {
            return Err(ErrorDetails::InferenceServer {
                message: format!(
                    "Response has invalid number of choices: {}. Expected 1.",
                    response.choices.len()
                ),
                raw_request: Some(raw_request),
                raw_response: Some(serde_json::to_string(&response).unwrap_or_default()),
                provider_type: PROVIDER_TYPE.to_string(),
            }
            .into());
        }
        let OpenAIResponseChoice {
            message,
            finish_reason,
            ..
        } = response
            .choices
            .pop()
            .ok_or_else(|| Error::new(ErrorDetails::InferenceServer {
                message: "Response has no choices (this should never happen). Please file a bug report: https://github.com/tensorzero/tensorzero/issues/new".to_string(),
                raw_request: Some(raw_request.clone()),
                raw_response: Some(serde_json::to_string(&response).unwrap_or_default()),
                provider_type: PROVIDER_TYPE.to_string(),
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
        };
        let usage = response.usage.into();
        let system = generic_request.system.clone();
        let messages = generic_request.messages.clone();
        Ok(ProviderInferenceResponse::new(
            ProviderInferenceResponseArgs {
                output: content,
                system,
                input_messages: messages,
                raw_request,
                raw_response: raw_response.clone(),
                usage,
                latency,
                finish_reason: Some(finish_reason.into()),
            },
        ))
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
struct OpenAIFunctionCallChunk {
    #[serde(skip_serializing_if = "Option::is_none")]
    name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    arguments: Option<String>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
struct OpenAIToolCallChunk {
    index: u8,
    #[serde(skip_serializing_if = "Option::is_none")]
    id: Option<String>,
    // NOTE: these are externally tagged enums, for now we're gonna just keep this hardcoded as there's only one option
    // If we were to do this better, we would need to check the `type` field
    function: OpenAIFunctionCallChunk,
}

// This doesn't include role
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
struct OpenAIDelta {
    #[serde(skip_serializing_if = "Option::is_none")]
    content: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool_calls: Option<Vec<OpenAIToolCallChunk>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    reasoning_content: Option<String>,
}

// Custom deserializer function for empty string to None
// This is required because SGLang (which depends on this code) returns "" in streaming chunks instead of null
fn empty_string_as_none<'de, D, T>(deserializer: D) -> Result<Option<T>, D::Error>
where
    D: Deserializer<'de>,
    T: Deserialize<'de>,
{
    let opt = Option::<String>::deserialize(deserializer)?;
    if let Some(s) = opt {
        if s.is_empty() {
            return Ok(None);
        }
        // Convert serde_json::Error to D::Error
        Ok(Some(
            T::deserialize(serde_json::Value::String(s).into_deserializer())
                .map_err(|e| serde::de::Error::custom(e.to_string()))?,
        ))
    } else {
        Ok(None)
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
struct OpenAIChatChunkChoice {
    delta: OpenAIDelta,
    #[serde(default)]
    #[serde(deserialize_with = "empty_string_as_none")]
    finish_reason: Option<OpenAIFinishReason>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
struct OpenAIChatChunk {
    choices: Vec<OpenAIChatChunkChoice>,
    #[serde(skip_serializing_if = "Option::is_none")]
    usage: Option<OpenAIUsage>,
}

/// Maps an OpenAI chunk to a TensorZero chunk for streaming inferences
fn openai_to_tensorzero_chunk(
    raw_message: String,
    mut chunk: OpenAIChatChunk,
    latency: Duration,
    tool_call_ids: &mut Vec<String>,
    tool_names: &mut Vec<String>,
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
    let mut content = vec![];
    let mut finish_reason = None;
    if let Some(choice) = chunk.choices.pop() {
        if let Some(choice_finish_reason) = choice.finish_reason {
            finish_reason = Some(choice_finish_reason.into());
        }
        // Handle reasoning_content if present (for vLLM with enable_thinking)
        if let Some(reasoning_text) = choice.delta.reasoning_content {
            content.push(ContentBlockChunk::Thought(
                crate::inference::types::ThoughtChunk {
                    id: "reasoning".to_string(),
                    text: Some(reasoning_text),
                    signature: None,
                },
            ));
        }
        if let Some(text) = choice.delta.content {
            content.push(ContentBlockChunk::Text(TextChunk {
                text,
                id: "0".to_string(),
            }));
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
                        tool_names.push(name.clone());
                        name
                    }
                    None => {
                        tool_names
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

#[derive(Debug, Serialize)]
struct OpenAIEmbeddingRequest<'a> {
    model: &'a str,
    input: OpenAIEmbeddingRequestInput<'a>,
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
enum OpenAIEmbeddingRequestInput<'a> {
    Single(&'a str),
    Batch(Vec<&'a str>),
}

impl<'a> OpenAIEmbeddingRequest<'a> {
    fn new(model: &'a str, request: &'a EmbeddingRequest) -> Self {
        let input = match &request.input {
            crate::embeddings::EmbeddingInput::Single(text) => {
                OpenAIEmbeddingRequestInput::Single(text)
            }
            crate::embeddings::EmbeddingInput::Batch(texts) => {
                OpenAIEmbeddingRequestInput::Batch(texts.iter().map(|s| s.as_str()).collect())
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

#[derive(Debug, Deserialize, Serialize)]
struct OpenAIEmbeddingResponse {
    data: Vec<OpenAIEmbeddingData>,
    usage: OpenAIUsage,
}

struct OpenAIEmbeddingResponseWithMetadata<'a> {
    response: OpenAIEmbeddingResponse,
    latency: Latency,
    request: OpenAIEmbeddingRequest<'a>,
    raw_response: String,
}

#[derive(Debug, Deserialize, Serialize)]
struct OpenAIEmbeddingData {
    embedding: Vec<f32>,
}

// Moderation structures

#[derive(Debug, Serialize)]
struct OpenAIModerationRequest<'a> {
    input: OpenAIModerationRequestInput<'a>,
    #[serde(skip_serializing_if = "Option::is_none")]
    model: Option<&'a str>,
}

#[derive(Debug, Serialize)]
#[serde(untagged)]
enum OpenAIModerationRequestInput<'a> {
    Single(&'a str),
    Batch(Vec<&'a str>),
}

impl<'a> OpenAIModerationRequest<'a> {
    fn new(input: &'a ModerationInput, model: Option<&'a str>) -> Self {
        let input = match input {
            ModerationInput::Single(text) => OpenAIModerationRequestInput::Single(text),
            ModerationInput::Batch(texts) => {
                OpenAIModerationRequestInput::Batch(texts.iter().map(|s| s.as_str()).collect())
            }
        };
        Self { input, model }
    }
}

#[derive(Debug, Deserialize)]
struct OpenAIModerationResponse {
    #[serde(rename = "id")]
    _id: String,
    model: String,
    results: Vec<OpenAIModerationResult>,
}

#[derive(Debug, Deserialize)]
struct OpenAIModerationResult {
    flagged: bool,
    categories: ModerationCategories,
    category_scores: ModerationCategoryScores,
    #[serde(skip_serializing_if = "Option::is_none")]
    category_applied_input_types: Option<CategoryAppliedInputTypes>,
}

struct OpenAIModerationResponseWithMetadata<'a> {
    response: OpenAIModerationResponse,
    latency: Latency,
    request: OpenAIModerationRequest<'a>,
    raw_response: String,
    input: ModerationInput,
    moderation_request: &'a ModerationRequest,
}

impl<'a> TryFrom<OpenAIEmbeddingResponseWithMetadata<'a>> for EmbeddingProviderResponse {
    type Error = Error;
    fn try_from(response: OpenAIEmbeddingResponseWithMetadata<'a>) -> Result<Self, Self::Error> {
        let OpenAIEmbeddingResponseWithMetadata {
            response,
            latency,
            request,
            raw_response,
        } = response;
        let raw_request = serde_json::to_string(&request).map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!(
                    "Error serializing request body as JSON: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                raw_request: Some(serde_json::to_string(&request).unwrap_or_default()),
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;

        if response.data.is_empty() {
            return Err(Error::new(ErrorDetails::InferenceServer {
                message: "Expected at least one embedding in response".to_string(),
                raw_request: Some(raw_request.clone()),
                raw_response: Some(raw_response.clone()),
                provider_type: PROVIDER_TYPE.to_string(),
            }));
        }

        let embeddings: Vec<Vec<f32>> = response
            .data
            .into_iter()
            .map(|data| data.embedding)
            .collect();

        // Convert the request input back to EmbeddingInput
        let input = match &request.input {
            OpenAIEmbeddingRequestInput::Single(text) => {
                crate::embeddings::EmbeddingInput::Single(text.to_string())
            }
            OpenAIEmbeddingRequestInput::Batch(texts) => crate::embeddings::EmbeddingInput::Batch(
                texts.iter().map(|s| s.to_string()).collect(),
            ),
        };

        Ok(EmbeddingProviderResponse::new(
            embeddings,
            input,
            raw_request,
            raw_response,
            response.usage.into(),
            latency,
        ))
    }
}

impl<'a> TryFrom<OpenAIModerationResponseWithMetadata<'a>> for ModerationProviderResponse {
    type Error = Error;
    fn try_from(response: OpenAIModerationResponseWithMetadata<'a>) -> Result<Self, Self::Error> {
        let OpenAIModerationResponseWithMetadata {
            response,
            latency,
            request,
            raw_response,
            input,
            moderation_request: _,
        } = response;
        let raw_request = serde_json::to_string(&request).map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!(
                    "Error serializing request body as JSON: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                raw_request: Some(serde_json::to_string(&request).unwrap_or_default()),
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;

        // Convert OpenAI results to our ModerationResult format
        let results: Vec<ModerationResult> = response
            .results
            .into_iter()
            .map(|r| ModerationResult {
                flagged: r.flagged,
                categories: r.categories,
                category_scores: r.category_scores,
                category_applied_input_types: r.category_applied_input_types,
                hallucination_details: None,
                ip_violation_details: None,
                other_categories: Default::default(),
            })
            .collect();

        // Create usage data (OpenAI moderation API doesn't return token counts)
        let usage = Usage {
            input_tokens: 0,
            output_tokens: 0,
        };

        Ok(ModerationProviderResponse {
            id: Uuid::now_v7(),
            input,
            results,
            created: crate::inference::types::current_timestamp(),
            model: response.model,
            raw_request,
            raw_response,
            usage,
            latency,
        })
    }
}

#[derive(Debug, Deserialize)]
struct OpenAIFileResponse {
    id: String,
}

#[derive(Debug, Deserialize)]
struct OpenAIBatchResponse {
    id: String,
    // object: String,
    // endpoint: String,
    errors: Option<OpenAIBatchErrors>,
    // input_file_id: String,
    // completion_window: String,
    status: OpenAIBatchStatus,
    output_file_id: Option<String>,
    // error_file_id: String,
    // created_at: i64,
    // in_progress_at: Option<i64>,
    // expires_at: i64,
    // finalizing_at: Option<i64>,
    // completed_at: Option<i64>,
    // failed_at: Option<i64>,
    // expired_at: Option<i64>,
    // cancelling_at: Option<i64>,
    // cancelled_at: Option<i64>,
    // request_counts: OpenAIBatchRequestCounts,
    // metadata: HashMap<String, String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "snake_case")]
enum OpenAIBatchStatus {
    Validating,
    Failed,
    InProgress,
    Finalizing,
    Completed,
    Expired,
    Cancelling,
    Cancelled,
}

impl From<OpenAIBatchStatus> for BatchStatus {
    fn from(status: OpenAIBatchStatus) -> Self {
        match status {
            OpenAIBatchStatus::Completed => BatchStatus::Completed,
            OpenAIBatchStatus::Validating
            | OpenAIBatchStatus::InProgress
            | OpenAIBatchStatus::Finalizing => BatchStatus::Pending,
            OpenAIBatchStatus::Failed
            | OpenAIBatchStatus::Expired
            | OpenAIBatchStatus::Cancelling
            | OpenAIBatchStatus::Cancelled => BatchStatus::Failed,
        }
    }
}

impl TryFrom<OpenAIBatchFileRow> for ProviderBatchInferenceOutput {
    type Error = Error;

    fn try_from(row: OpenAIBatchFileRow) -> Result<Self, Self::Error> {
        let mut response = row.response.body;
        // Validate we have exactly one choice
        if response.choices.len() != 1 {
            return Err(ErrorDetails::InferenceServer {
                message: format!(
                    "Response has invalid number of choices: {}. Expected 1.",
                    response.choices.len()
                ),
                raw_request: None,
                raw_response: Some(serde_json::to_string(&response).unwrap_or_default()),
                provider_type: PROVIDER_TYPE.to_string(),
            }
            .into());
        }

        // Convert response to raw string for storage
        let raw_response = serde_json::to_string(&response).map_err(|e| {
            Error::new(ErrorDetails::Serialization {
                message: format!("Error parsing response: {}", DisplayOrDebugGateway::new(e)),
            })
        })?;

        // Extract the message from choices
        let OpenAIResponseChoice {
            message,
            finish_reason,
            ..
        } = response
            .choices
            .pop()
            .ok_or_else(|| Error::new(ErrorDetails::InferenceServer {
                message: "Response has no choices (this should never happen). Please file a bug report: https://github.com/tensorzero/tensorzero/issues/new".to_string(),
                raw_request: None,
                raw_response: Some(raw_response.clone()),
                provider_type: PROVIDER_TYPE.to_string(),
            }))?;

        // Convert message content to ContentBlocks
        let mut content: Vec<ContentBlockOutput> = Vec::new();
        if let Some(text) = message.content {
            content.push(text.into());
        }
        if let Some(tool_calls) = message.tool_calls {
            for tool_call in tool_calls {
                content.push(ContentBlockOutput::ToolCall(tool_call.into()));
            }
        }

        Ok(Self {
            id: row.inference_id,
            output: content,
            raw_response,
            usage: response.usage.into(),
            finish_reason: Some(finish_reason.into()),
        })
    }
}

#[derive(Debug, Deserialize)]
struct OpenAIBatchErrors {
    // object: String,
    data: Vec<OpenAIBatchError>,
}

#[derive(Debug, Serialize, Deserialize)]
struct OpenAIBatchError {
    code: String,
    message: String,
    param: Option<String>,
    line: Option<i32>,
}

#[derive(Debug, Deserialize)]
struct OpenAIBatchRequestCounts {
    // total: u32,
    // completed: u32,
    // failed: u32,
}

#[derive(Debug, Deserialize)]
struct OpenAIBatchFileRow {
    #[serde(rename = "custom_id")]
    inference_id: Uuid,
    response: OpenAIBatchFileResponse,
}

#[derive(Debug, Deserialize)]
struct OpenAIBatchFileResponse {
    // status_code: u16,
    // request_id: String,
    body: OpenAIResponse,
}

use crate::realtime::{
    RealtimeSessionProvider, RealtimeSessionRequest, RealtimeSessionResponse,
    RealtimeTranscriptionProvider, RealtimeTranscriptionRequest, RealtimeTranscriptionResponse,
};
use crate::responses::{
    OpenAIResponse as ResponsesOpenAIResponse, OpenAIResponseCreateParams, ResponseInputItemsList,
    ResponseProvider, ResponseStreamEvent, ResponseWithRawData,
};

#[async_trait::async_trait]
impl ResponseProvider for OpenAIProvider {
    async fn create_response(
        &self,
        request: &OpenAIResponseCreateParams,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
        _baggage: Option<&crate::baggage::BaggageData>,
    ) -> Result<ResponseWithRawData, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let request_url =
            get_responses_url(self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL))?;
        let _start_time = Instant::now();

        // Serialize the request for raw_request capture (before sending)
        let raw_request = serde_json::to_string(&request).unwrap_or_default();

        let mut request_builder = client
            .post(request_url)
            .header("Content-Type", "application/json");
        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let res = request_builder.json(&request).send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                status_code: e.status(),
                message: format!(
                    "Error sending request to OpenAI Responses API: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: Some(raw_request.clone()),
                raw_response: None,
            })
        })?;

        if res.status().is_success() {
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

            let response: ResponsesOpenAIResponse =
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

            Ok(ResponseWithRawData {
                response,
                raw_request,
                raw_response,
            })
        } else {
            Err(handle_openai_error(
                &raw_request,
                res.status(),
                &res.text().await.map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing error response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: Some(raw_request.clone()),
                        raw_response: None,
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?,
                PROVIDER_TYPE,
            ))
        }
    }

    async fn stream_response(
        &self,
        request: &OpenAIResponseCreateParams,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
        _baggage: Option<&crate::baggage::BaggageData>,
    ) -> Result<
        Box<dyn futures::Stream<Item = Result<ResponseStreamEvent, Error>> + Send + Unpin>,
        Error,
    > {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let request_url =
            get_responses_url(self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL))?;
        let _start_time = Instant::now();

        let mut request_builder = client
            .post(request_url)
            .header("Content-Type", "application/json");
        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        // Make sure stream is enabled
        let mut request_with_stream = request.clone();
        request_with_stream.stream = Some(true);

        let event_source = request_builder
            .json(&request_with_stream)
            .eventsource()
            .map_err(|e| {
                Error::new(ErrorDetails::InferenceClient {
                    status_code: None,
                    message: format!(
                        "Error creating event source for OpenAI Responses API: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    provider_type: PROVIDER_TYPE.to_string(),
                    raw_request: Some(
                        serde_json::to_string(&request_with_stream).unwrap_or_default(),
                    ),
                    raw_response: None,
                })
            })?;

        let inner_stream = async_stream::stream! {
            futures::pin_mut!(event_source);
            while let Some(ev) = event_source.next().await {
                match ev {
                    Err(e) => {
                        yield Err(convert_stream_error(PROVIDER_TYPE.to_string(), e).await);
                    }
                    Ok(event) => match event {
                        Event::Open => continue,
                        Event::Message(message) => {
                            if message.data == "[DONE]" {
                                break;
                            }

                            let stream_event: Result<ResponseStreamEvent, Error> =
                                serde_json::from_str(&message.data).map_err(|e| {
                                    Error::new(ErrorDetails::InferenceServer {
                                        message: format!("Error parsing stream event: {e}"),
                                        raw_request: None,
                                        raw_response: Some(message.data.clone()),
                                        provider_type: PROVIDER_TYPE.to_string(),
                                    })
                                });

                            match stream_event {
                                Ok(event) => yield Ok(event),
                                Err(e) => yield Err(e),
                            }
                        }
                    },
                }
            }
        };

        // Use Box::pin to create a pinned box that implements Stream + Send but not necessarily Unpin
        // Then convert it to the required type
        use futures::stream::StreamExt;
        let pinned_stream = Box::pin(inner_stream);

        // Convert to a type that implements Unpin
        struct UnpinStream<S>(Pin<Box<S>>);

        impl<S: Stream> Stream for UnpinStream<S> {
            type Item = S::Item;

            fn poll_next(
                mut self: Pin<&mut Self>,
                cx: &mut std::task::Context<'_>,
            ) -> std::task::Poll<Option<Self::Item>> {
                self.0.as_mut().poll_next(cx)
            }
        }

        // UnpinStream implements Unpin regardless of whether S does
        impl<S> Unpin for UnpinStream<S> {}

        let unpin_stream = UnpinStream(pinned_stream);

        Ok(Box::new(unpin_stream))
    }

    async fn retrieve_response(
        &self,
        response_id: &str,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<ResponsesOpenAIResponse, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let url = self
            .api_base
            .as_ref()
            .unwrap_or(&OPENAI_DEFAULT_BASE_URL)
            .join(&format!("responses/{response_id}"))
            .map_err(|e| {
                Error::new(ErrorDetails::Config {
                    message: format!("Failed to construct response URL: {e}"),
                })
            })?;

        let mut request_builder = client.get(url);
        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let res = request_builder.send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                status_code: e.status(),
                message: format!(
                    "Error retrieving response: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?;

        if res.status().is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing text response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: None,
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            let response: ResponsesOpenAIResponse =
                serde_json::from_str(&raw_response).map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing JSON response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: None,
                        raw_response: Some(raw_response.clone()),
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?;

            Ok(response)
        } else {
            Err(handle_openai_error(
                "",
                res.status(),
                &res.text().await.unwrap_or_default(),
                PROVIDER_TYPE,
            ))
        }
    }

    async fn delete_response(
        &self,
        response_id: &str,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<serde_json::Value, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let url = self
            .api_base
            .as_ref()
            .unwrap_or(&OPENAI_DEFAULT_BASE_URL)
            .join(&format!("responses/{response_id}"))
            .map_err(|e| {
                Error::new(ErrorDetails::Config {
                    message: format!("Failed to construct response URL: {e}"),
                })
            })?;

        let mut request_builder = client.delete(url);
        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let res = request_builder.send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                status_code: e.status(),
                message: format!("Error deleting response: {}", DisplayOrDebugGateway::new(e)),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?;

        if res.status().is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing text response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: None,
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            let response: serde_json::Value = serde_json::from_str(&raw_response).map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing JSON response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: None,
                    raw_response: Some(raw_response.clone()),
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            Ok(response)
        } else {
            Err(handle_openai_error(
                "",
                res.status(),
                &res.text().await.unwrap_or_default(),
                PROVIDER_TYPE,
            ))
        }
    }

    async fn cancel_response(
        &self,
        response_id: &str,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<ResponsesOpenAIResponse, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let url = self
            .api_base
            .as_ref()
            .unwrap_or(&OPENAI_DEFAULT_BASE_URL)
            .join(&format!("responses/{response_id}/cancel"))
            .map_err(|e| {
                Error::new(ErrorDetails::Config {
                    message: format!("Failed to construct response cancel URL: {e}"),
                })
            })?;

        let mut request_builder = client.post(url);
        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let res = request_builder.send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                status_code: e.status(),
                message: format!(
                    "Error cancelling response: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?;

        if res.status().is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing text response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: None,
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            let response: ResponsesOpenAIResponse =
                serde_json::from_str(&raw_response).map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing JSON response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: None,
                        raw_response: Some(raw_response.clone()),
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?;

            Ok(response)
        } else {
            Err(handle_openai_error(
                "",
                res.status(),
                &res.text().await.unwrap_or_default(),
                PROVIDER_TYPE,
            ))
        }
    }

    async fn list_response_input_items(
        &self,
        response_id: &str,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<ResponseInputItemsList, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let url = self
            .api_base
            .as_ref()
            .unwrap_or(&OPENAI_DEFAULT_BASE_URL)
            .join(&format!("responses/{response_id}/input_items"))
            .map_err(|e| {
                Error::new(ErrorDetails::Config {
                    message: format!("Failed to construct response input items URL: {e}"),
                })
            })?;

        let mut request_builder = client.get(url);
        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let res = request_builder.send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                status_code: e.status(),
                message: format!(
                    "Error listing response input items: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?;

        if res.status().is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing text response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: None,
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            let response: ResponseInputItemsList =
                serde_json::from_str(&raw_response).map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing JSON response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: None,
                        raw_response: Some(raw_response.clone()),
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?;

            Ok(response)
        } else {
            Err(handle_openai_error(
                "",
                res.status(),
                &res.text().await.unwrap_or_default(),
                PROVIDER_TYPE,
            ))
        }
    }
}

// Helper function to construct responses API URL
fn get_responses_url(base_url: &Url) -> Result<Url, Error> {
    base_url.join("responses").map_err(|e| {
        Error::new(ErrorDetails::Config {
            message: format!("Failed to construct responses URL: {e}"),
        })
    })
}

// Helper function to construct realtime sessions API URL
fn get_realtime_sessions_url(base_url: &Url) -> Result<Url, Error> {
    base_url.join("realtime/sessions").map_err(|e| {
        Error::new(ErrorDetails::Config {
            message: format!("Failed to construct realtime sessions URL: {e}"),
        })
    })
}

// Helper function to construct realtime transcription sessions API URL
fn get_realtime_transcription_sessions_url(base_url: &Url) -> Result<Url, Error> {
    base_url
        .join("realtime/transcription_sessions")
        .map_err(|e| {
            Error::new(ErrorDetails::Config {
                message: format!("Failed to construct realtime transcription sessions URL: {e}"),
            })
        })
}

#[async_trait::async_trait]
impl RealtimeSessionProvider for OpenAIProvider {
    async fn create_session(
        &self,
        request: &RealtimeSessionRequest,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<RealtimeSessionResponse, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let request_url =
            get_realtime_sessions_url(self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL))?;

        let mut request_builder = client
            .post(request_url)
            .header("Content-Type", "application/json");

        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let res = request_builder.json(&request).send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                status_code: e.status(),
                message: format!(
                    "Error sending request to OpenAI Realtime Sessions API: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: Some(serde_json::to_string(&request).unwrap_or_default()),
                raw_response: None,
            })
        })?;

        if res.status().is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing text response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: Some(serde_json::to_string(&request).unwrap_or_default()),
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            let response: RealtimeSessionResponse =
                serde_json::from_str(&raw_response).map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing JSON response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: Some(serde_json::to_string(&request).unwrap_or_default()),
                        raw_response: Some(raw_response.clone()),
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?;

            Ok(response)
        } else {
            Err(handle_openai_error(
                &serde_json::to_string(&request).unwrap_or_default(),
                res.status(),
                &res.text().await.map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing error response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: Some(serde_json::to_string(&request).unwrap_or_default()),
                        raw_response: None,
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?,
                PROVIDER_TYPE,
            ))
        }
    }
}

#[async_trait::async_trait]
impl RealtimeTranscriptionProvider for OpenAIProvider {
    async fn create_transcription_session(
        &self,
        request: &RealtimeTranscriptionRequest,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<RealtimeTranscriptionResponse, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let request_url = get_realtime_transcription_sessions_url(
            self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL),
        )?;

        let mut request_builder = client
            .post(request_url)
            .header("Content-Type", "application/json");

        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let res = request_builder.json(&request).send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                status_code: e.status(),
                message: format!(
                    "Error sending request to OpenAI Realtime Transcription Sessions API: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: Some(serde_json::to_string(&request).unwrap_or_default()),
                raw_response: None,
            })
        })?;

        if res.status().is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing text response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: Some(serde_json::to_string(&request).unwrap_or_default()),
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            let response: RealtimeTranscriptionResponse = serde_json::from_str(&raw_response)
                .map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing JSON response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: Some(serde_json::to_string(&request).unwrap_or_default()),
                        raw_response: Some(raw_response.clone()),
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?;

            Ok(response)
        } else {
            Err(handle_openai_error(
                &serde_json::to_string(&request).unwrap_or_default(),
                res.status(),
                &res.text().await.map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing error response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: Some(serde_json::to_string(&request).unwrap_or_default()),
                        raw_response: None,
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?,
                PROVIDER_TYPE,
            ))
        }
    }
}

// BatchProvider implementation for OpenAI
#[async_trait::async_trait]
impl BatchProvider for OpenAIProvider {
    async fn upload_file(
        &self,
        content: Vec<u8>,
        filename: String,
        purpose: String,
        client: &reqwest::Client,
        api_keys: &InferenceCredentials,
    ) -> Result<OpenAIFileObject, Error> {
        let api_key = self.credentials.get_api_key(api_keys)?;
        let api_base = self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL);

        let form = Form::new()
            .text("purpose", purpose)
            .part("file", Part::bytes(content).file_name(filename));

        let mut request_builder = client.post(format!("{api_base}/files"));

        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let response = request_builder.multipart(form).send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                status_code: e.status(),
                message: format!("Error uploading file: {}", DisplayOrDebugGateway::new(e)),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?;

        let status = response.status();
        if !status.is_success() {
            let error_text = response.text().await.unwrap_or_default();
            return Err(handle_openai_error("", status, &error_text, PROVIDER_TYPE));
        }

        let file_object: OpenAIFileObject = response.json().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!(
                    "Error parsing file response: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                raw_request: None,
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;
        Ok(file_object)
    }

    async fn get_file(
        &self,
        file_id: &str,
        client: &reqwest::Client,
        api_keys: &InferenceCredentials,
    ) -> Result<OpenAIFileObject, Error> {
        let api_key = self.credentials.get_api_key(api_keys)?;
        let api_base = self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL);

        let mut request_builder = client.get(format!("{api_base}/files/{file_id}"));

        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let response = request_builder.send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                status_code: e.status(),
                message: format!("Error getting file: {}", DisplayOrDebugGateway::new(e)),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?;

        let status = response.status();
        if !status.is_success() {
            let error_text = response.text().await.unwrap_or_default();
            return Err(handle_openai_error("", status, &error_text, PROVIDER_TYPE));
        }

        let file_object: OpenAIFileObject = response.json().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!(
                    "Error parsing file response: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                raw_request: None,
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;
        Ok(file_object)
    }

    async fn get_file_content(
        &self,
        file_id: &str,
        client: &reqwest::Client,
        api_keys: &InferenceCredentials,
    ) -> Result<Vec<u8>, Error> {
        let api_key = self.credentials.get_api_key(api_keys)?;
        let api_base = self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL);

        let mut request_builder = client.get(format!("{api_base}/files/{file_id}/content"));

        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let response = request_builder.send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                status_code: e.status(),
                message: format!(
                    "Error getting file content: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?;

        let status = response.status();
        if !status.is_success() {
            let error_text = response.text().await.unwrap_or_default();
            return Err(handle_openai_error("", status, &error_text, PROVIDER_TYPE));
        }

        let content = response.bytes().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!(
                    "Error reading file content: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                raw_request: None,
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;
        Ok(content.to_vec())
    }

    async fn delete_file(
        &self,
        file_id: &str,
        client: &reqwest::Client,
        api_keys: &InferenceCredentials,
    ) -> Result<OpenAIFileObject, Error> {
        let api_key = self.credentials.get_api_key(api_keys)?;
        let api_base = self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL);

        let mut request_builder = client.delete(format!("{api_base}/files/{file_id}"));

        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let response = request_builder.send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                status_code: e.status(),
                message: format!("Error deleting file: {}", DisplayOrDebugGateway::new(e)),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?;

        let status = response.status();
        if !status.is_success() {
            let error_text = response.text().await.unwrap_or_default();
            return Err(handle_openai_error("", status, &error_text, PROVIDER_TYPE));
        }

        let file_object: OpenAIFileObject = response.json().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!(
                    "Error parsing file response: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                raw_request: None,
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;
        Ok(file_object)
    }

    async fn create_batch(
        &self,
        input_file_id: String,
        endpoint: String,
        completion_window: String,
        metadata: Option<std::collections::HashMap<String, String>>,
        client: &reqwest::Client,
        api_keys: &InferenceCredentials,
    ) -> Result<OpenAIBatchObject, Error> {
        let api_key = self.credentials.get_api_key(api_keys)?;
        let api_base = self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL);

        let mut body = json!({
            "input_file_id": input_file_id,
            "endpoint": endpoint,
            "completion_window": completion_window,
        });

        if let Some(metadata) = metadata {
            body["metadata"] = json!(metadata);
        }

        let mut request_builder = client.post(format!("{api_base}/batches"));

        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let response = request_builder.json(&body).send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                status_code: e.status(),
                message: format!("Error creating batch: {}", DisplayOrDebugGateway::new(e)),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: Some(serde_json::to_string(&body).unwrap_or_default()),
                raw_response: None,
            })
        })?;

        let status = response.status();
        if !status.is_success() {
            let error_text = response.text().await.unwrap_or_default();
            return Err(handle_openai_error(
                &serde_json::to_string(&body).unwrap_or_default(),
                status,
                &error_text,
                PROVIDER_TYPE,
            ));
        }

        let batch_object: OpenAIBatchObject = response.json().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!(
                    "Error parsing batch response: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                raw_request: Some(serde_json::to_string(&body).unwrap_or_default()),
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;
        Ok(batch_object)
    }

    async fn get_batch(
        &self,
        batch_id: &str,
        client: &reqwest::Client,
        api_keys: &InferenceCredentials,
    ) -> Result<OpenAIBatchObject, Error> {
        let api_key = self.credentials.get_api_key(api_keys)?;
        let api_base = self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL);

        let mut request_builder = client.get(format!("{api_base}/batches/{batch_id}"));

        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let response = request_builder.send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                status_code: e.status(),
                message: format!("Error getting batch: {}", DisplayOrDebugGateway::new(e)),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?;

        let status = response.status();
        if !status.is_success() {
            let error_text = response.text().await.unwrap_or_default();
            return Err(handle_openai_error("", status, &error_text, PROVIDER_TYPE));
        }

        let batch_object: OpenAIBatchObject = response.json().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!(
                    "Error parsing batch response: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                raw_request: None,
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;
        Ok(batch_object)
    }

    async fn list_batches(
        &self,
        params: ListBatchesParams,
        client: &reqwest::Client,
        api_keys: &InferenceCredentials,
    ) -> Result<ListBatchesResponse, Error> {
        let api_key = self.credentials.get_api_key(api_keys)?;
        let api_base = self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL);

        let mut query_params = vec![("limit", params.limit.to_string())];
        if let Some(after) = &params.after {
            query_params.push(("after", after.clone()));
        }

        let mut request_builder = client.get(format!("{api_base}/batches"));

        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let response = request_builder
            .query(&query_params)
            .send()
            .await
            .map_err(|e| {
                Error::new(ErrorDetails::InferenceClient {
                    status_code: e.status(),
                    message: format!("Error listing batches: {}", DisplayOrDebugGateway::new(e)),
                    provider_type: PROVIDER_TYPE.to_string(),
                    raw_request: None,
                    raw_response: None,
                })
            })?;

        let status = response.status();
        if !status.is_success() {
            let error_text = response.text().await.unwrap_or_default();
            return Err(handle_openai_error("", status, &error_text, PROVIDER_TYPE));
        }

        let list_response: ListBatchesResponse = response.json().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!(
                    "Error parsing list response: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                raw_request: None,
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;
        Ok(list_response)
    }

    async fn cancel_batch(
        &self,
        batch_id: &str,
        client: &reqwest::Client,
        api_keys: &InferenceCredentials,
    ) -> Result<OpenAIBatchObject, Error> {
        let api_key = self.credentials.get_api_key(api_keys)?;
        let api_base = self.api_base.as_ref().unwrap_or(&OPENAI_DEFAULT_BASE_URL);

        let mut request_builder = client.post(format!("{api_base}/batches/{batch_id}/cancel"));

        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        }

        let response = request_builder.send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                status_code: e.status(),
                message: format!("Error cancelling batch: {}", DisplayOrDebugGateway::new(e)),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?;

        let status = response.status();
        if !status.is_success() {
            let error_text = response.text().await.unwrap_or_default();
            return Err(handle_openai_error("", status, &error_text, PROVIDER_TYPE));
        }

        let batch_object: OpenAIBatchObject = response.json().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!(
                    "Error parsing batch response: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                raw_request: None,
                raw_response: None,
                provider_type: PROVIDER_TYPE.to_string(),
            })
        })?;
        Ok(batch_object)
    }
}

#[cfg(test)]
mod tests {
    use serde_json::json;
    use std::borrow::Cow;
    use std::collections::HashMap;
    use tracing_test::traced_test;

    use crate::inference::providers::test_helpers::{
        MULTI_TOOL_CONFIG, QUERY_TOOL, WEATHER_TOOL, WEATHER_TOOL_CONFIG,
    };
    use crate::inference::types::{FunctionType, RequestMessage};
    use crate::tool::ToolCallConfig;

    use super::*;

    #[test]
    fn test_get_chat_url() {
        // Test with custom base URL
        let custom_base = "https://custom.openai.com/api/";
        let custom_url = get_chat_url(&Url::parse(custom_base).unwrap()).unwrap();
        assert_eq!(
            custom_url.as_str(),
            "https://custom.openai.com/api/chat/completions"
        );

        // Test with URL without trailing slash
        let unjoinable_url = get_chat_url(&Url::parse("https://example.com").unwrap());
        assert!(unjoinable_url.is_ok());
        assert_eq!(
            unjoinable_url.unwrap().as_str(),
            "https://example.com/chat/completions"
        );
        // Test with URL that can't be joined
        let unjoinable_url = get_chat_url(&Url::parse("https://example.com/foo").unwrap());
        assert!(unjoinable_url.is_ok());
        assert_eq!(
            unjoinable_url.unwrap().as_str(),
            "https://example.com/foo/chat/completions"
        );
    }

    #[test]
    fn test_handle_openai_error() {
        use reqwest::StatusCode;

        // Test unauthorized error
        let unauthorized = handle_openai_error(
            "Request Body",
            StatusCode::UNAUTHORIZED,
            "Unauthorized access",
            PROVIDER_TYPE,
        );
        let details = unauthorized.get_details();
        assert!(matches!(details, ErrorDetails::InferenceClient { .. }));
        if let ErrorDetails::InferenceClient {
            status_code,
            message,
            raw_request,
            raw_response,
            provider_type: provider,
        } = details
        {
            assert_eq!(message, "Unauthorized access");
            assert_eq!(*status_code, Some(StatusCode::UNAUTHORIZED));
            assert_eq!(provider, PROVIDER_TYPE);
            assert_eq!(*raw_request, Some("Request Body".to_string()));
            assert_eq!(*raw_response, Some("Unauthorized access".to_string()));
        }

        // Test forbidden error
        let forbidden = handle_openai_error(
            "Request Body",
            StatusCode::FORBIDDEN,
            "Forbidden access",
            PROVIDER_TYPE,
        );
        let details = forbidden.get_details();
        assert!(matches!(details, ErrorDetails::InferenceClient { .. }));
        if let ErrorDetails::InferenceClient {
            message,
            status_code,
            raw_request,
            raw_response,
            provider_type: provider,
        } = details
        {
            assert_eq!(message, "Forbidden access");
            assert_eq!(*status_code, Some(StatusCode::FORBIDDEN));
            assert_eq!(provider, PROVIDER_TYPE);
            assert_eq!(*raw_request, Some("Request Body".to_string()));
            assert_eq!(*raw_response, Some("Forbidden access".to_string()));
        }

        // Test rate limit error
        let rate_limit = handle_openai_error(
            "Request Body",
            StatusCode::TOO_MANY_REQUESTS,
            "Rate limit exceeded",
            PROVIDER_TYPE,
        );
        let details = rate_limit.get_details();
        assert!(matches!(details, ErrorDetails::InferenceClient { .. }));
        if let ErrorDetails::InferenceClient {
            message,
            status_code,
            raw_request,
            raw_response,
            provider_type: provider,
        } = details
        {
            assert_eq!(message, "Rate limit exceeded");
            assert_eq!(*status_code, Some(StatusCode::TOO_MANY_REQUESTS));
            assert_eq!(provider, PROVIDER_TYPE);
            assert_eq!(*raw_request, Some("Request Body".to_string()));
            assert_eq!(*raw_response, Some("Rate limit exceeded".to_string()));
        }

        // Test server error
        let server_error = handle_openai_error(
            "Request Body",
            StatusCode::INTERNAL_SERVER_ERROR,
            "Server error",
            PROVIDER_TYPE,
        );
        let details = server_error.get_details();
        assert!(matches!(details, ErrorDetails::InferenceServer { .. }));
        if let ErrorDetails::InferenceServer {
            message,
            raw_request,
            raw_response,
            provider_type: provider,
        } = details
        {
            assert_eq!(message, "Server error");
            assert_eq!(provider, PROVIDER_TYPE);
            assert_eq!(*raw_request, Some("Request Body".to_string()));
            assert_eq!(*raw_response, Some("Server error".to_string()));
        }
    }

    #[test]
    fn test_openai_request_new() {
        // Test basic request
        let basic_request = ModelInferenceRequest {
            inference_id: Uuid::now_v7(),
            messages: vec![
                RequestMessage {
                    role: Role::User,
                    content: vec!["Hello".to_string().into()],
                },
                RequestMessage {
                    role: Role::Assistant,
                    content: vec!["Hi there!".to_string().into()],
                },
            ],
            system: None,
            tool_config: None,
            temperature: Some(0.7),
            max_tokens: Some(100),
            seed: Some(69),
            top_p: Some(0.9),
            presence_penalty: Some(0.1),
            frequency_penalty: Some(0.2),
            stream: true,
            json_mode: ModelInferenceRequestJsonMode::Off,
            function_type: FunctionType::Chat,
            output_schema: None,
            extra_body: Default::default(),
            ..Default::default()
        };

        let openai_request = OpenAIRequest::new("gpt-3.5-turbo", &basic_request).unwrap();

        assert_eq!(openai_request.model, "gpt-3.5-turbo");
        assert_eq!(openai_request.messages.len(), 2);
        assert_eq!(openai_request.temperature, Some(0.7));
        assert_eq!(openai_request.max_completion_tokens, Some(100));
        assert_eq!(openai_request.seed, Some(69));
        assert_eq!(openai_request.top_p, Some(0.9));
        assert_eq!(openai_request.presence_penalty, Some(0.1));
        assert_eq!(openai_request.frequency_penalty, Some(0.2));
        assert!(openai_request.stream);
        assert_eq!(openai_request.response_format, None);
        assert!(openai_request.tools.is_none());
        assert_eq!(openai_request.tool_choice, None);
        assert!(openai_request.parallel_tool_calls.is_none());

        // Test request with tools and JSON mode
        let request_with_tools = ModelInferenceRequest {
            inference_id: Uuid::now_v7(),
            messages: vec![RequestMessage {
                role: Role::User,
                content: vec!["What's the weather?".to_string().into()],
            }],
            system: None,
            temperature: None,
            top_p: None,
            presence_penalty: None,
            frequency_penalty: None,
            max_tokens: None,
            seed: None,
            stream: false,
            json_mode: ModelInferenceRequestJsonMode::On,
            tool_config: Some(Cow::Borrowed(&WEATHER_TOOL_CONFIG)),
            function_type: FunctionType::Chat,
            output_schema: None,
            extra_body: Default::default(),
            ..Default::default()
        };

        let openai_request = OpenAIRequest::new("gpt-4", &request_with_tools).unwrap();

        assert_eq!(openai_request.model, "gpt-4");
        assert_eq!(openai_request.messages.len(), 2); // We'll add a system message containing Json to fit OpenAI requirements
        assert_eq!(openai_request.temperature, None);
        assert_eq!(openai_request.max_completion_tokens, None);
        assert_eq!(openai_request.seed, None);
        assert_eq!(openai_request.top_p, None);
        assert_eq!(openai_request.presence_penalty, None);
        assert_eq!(openai_request.frequency_penalty, None);
        assert!(!openai_request.stream);
        assert_eq!(
            openai_request.response_format,
            Some(OpenAIResponseFormat::JsonObject)
        );
        assert!(openai_request.tools.is_some());
        let tools = openai_request.tools.as_ref().unwrap();
        assert_eq!(tools[0].function.name, WEATHER_TOOL.name());
        assert_eq!(tools[0].function.parameters, WEATHER_TOOL.parameters());
        assert_eq!(
            openai_request.tool_choice,
            Some(OpenAIToolChoice::Specific(SpecificToolChoice {
                r#type: OpenAIToolType::Function,
                function: SpecificToolFunction {
                    name: WEATHER_TOOL.name(),
                }
            }))
        );

        // Test request with strict JSON mode with no output schema
        let request_with_tools = ModelInferenceRequest {
            inference_id: Uuid::now_v7(),
            messages: vec![RequestMessage {
                role: Role::User,
                content: vec!["What's the weather?".to_string().into()],
            }],
            system: None,
            temperature: None,
            top_p: None,
            presence_penalty: None,
            frequency_penalty: None,
            max_tokens: None,
            seed: None,
            stream: false,
            json_mode: ModelInferenceRequestJsonMode::Strict,
            tool_config: None,
            function_type: FunctionType::Chat,
            output_schema: None,
            extra_body: Default::default(),
            ..Default::default()
        };

        let openai_request = OpenAIRequest::new("gpt-4", &request_with_tools).unwrap();

        assert_eq!(openai_request.model, "gpt-4");
        assert_eq!(openai_request.messages.len(), 1);
        assert_eq!(openai_request.temperature, None);
        assert_eq!(openai_request.max_completion_tokens, None);
        assert_eq!(openai_request.seed, None);
        assert!(!openai_request.stream);
        assert_eq!(openai_request.top_p, None);
        assert_eq!(openai_request.presence_penalty, None);
        assert_eq!(openai_request.frequency_penalty, None);
        // Resolves to normal JSON mode since no schema is provided (this shouldn't really happen in practice)
        assert_eq!(
            openai_request.response_format,
            Some(OpenAIResponseFormat::JsonObject)
        );

        // Test request with strict JSON mode with an output schema
        let output_schema = json!({});
        let request_with_tools = ModelInferenceRequest {
            inference_id: Uuid::now_v7(),
            messages: vec![RequestMessage {
                role: Role::User,
                content: vec!["What's the weather?".to_string().into()],
            }],
            system: None,
            temperature: None,
            top_p: None,
            presence_penalty: None,
            frequency_penalty: None,
            max_tokens: None,
            seed: None,
            stream: false,
            json_mode: ModelInferenceRequestJsonMode::Strict,
            tool_config: None,
            function_type: FunctionType::Chat,
            output_schema: Some(&output_schema),
            extra_body: Default::default(),
            ..Default::default()
        };

        let openai_request = OpenAIRequest::new("gpt-4", &request_with_tools).unwrap();

        assert_eq!(openai_request.model, "gpt-4");
        assert_eq!(openai_request.messages.len(), 1);
        assert_eq!(openai_request.temperature, None);
        assert_eq!(openai_request.max_completion_tokens, None);
        assert_eq!(openai_request.seed, None);
        assert!(!openai_request.stream);
        assert_eq!(openai_request.top_p, None);
        assert_eq!(openai_request.presence_penalty, None);
        assert_eq!(openai_request.frequency_penalty, None);
        let expected_schema = serde_json::json!({"name": "response", "strict": true, "schema": {}});
        assert_eq!(
            openai_request.response_format,
            Some(OpenAIResponseFormat::JsonSchema {
                json_schema: expected_schema,
            })
        );
    }

    #[test]
    fn test_openai_new_request_o1() {
        let request = ModelInferenceRequest {
            inference_id: Uuid::now_v7(),
            messages: vec![RequestMessage {
                role: Role::User,
                content: vec!["Hello".to_string().into()],
            }],
            system: None,
            temperature: Some(0.5),
            top_p: Some(0.9),
            presence_penalty: Some(0.1),
            frequency_penalty: Some(0.2),
            max_tokens: Some(100),
            seed: Some(69),
            stream: false,
            json_mode: ModelInferenceRequestJsonMode::Off,
            tool_config: None,
            function_type: FunctionType::Chat,
            output_schema: None,
            extra_body: Default::default(),
            ..Default::default()
        };

        let openai_request = OpenAIRequest::new("o1-preview", &request).unwrap();

        assert_eq!(openai_request.model, "o1-preview");
        assert_eq!(openai_request.messages.len(), 1);
        assert!(!openai_request.stream);
        assert_eq!(openai_request.response_format, None);
        assert_eq!(openai_request.temperature, Some(0.5));
        assert_eq!(openai_request.max_completion_tokens, Some(100));
        assert_eq!(openai_request.seed, Some(69));
        assert_eq!(openai_request.top_p, Some(0.9));
        assert_eq!(openai_request.presence_penalty, Some(0.1));
        assert_eq!(openai_request.frequency_penalty, Some(0.2));
        assert!(openai_request.tools.is_none());

        // Test case: System message is converted to User message
        let request_with_system = ModelInferenceRequest {
            inference_id: Uuid::now_v7(),
            messages: vec![RequestMessage {
                role: Role::User,
                content: vec!["Hello".to_string().into()],
            }],
            system: Some("This is the system message".to_string()),
            temperature: Some(0.5),
            top_p: Some(0.9),
            presence_penalty: Some(0.1),
            frequency_penalty: Some(0.2),
            max_tokens: Some(100),
            seed: Some(69),
            stream: false,
            json_mode: ModelInferenceRequestJsonMode::Off,
            tool_config: None,
            function_type: FunctionType::Chat,
            output_schema: None,
            extra_body: Default::default(),
            ..Default::default()
        };

        let openai_request_with_system =
            OpenAIRequest::new("o1-mini", &request_with_system).unwrap();

        // Check that the system message was converted to a user message
        assert_eq!(openai_request_with_system.messages.len(), 2);
        assert!(
            matches!(
                openai_request_with_system.messages[0],
                OpenAIRequestMessage::User(ref msg) if msg.content == [OpenAIContentBlock::Text { text: "This is the system message".into() }]
            ),
            "Unexpected messages: {:?}",
            openai_request_with_system.messages
        );

        assert_eq!(openai_request_with_system.model, "o1-mini");
        assert!(!openai_request_with_system.stream);
        assert_eq!(openai_request_with_system.response_format, None);
        assert_eq!(openai_request_with_system.temperature, Some(0.5));
        assert_eq!(openai_request_with_system.max_completion_tokens, Some(100));
        assert_eq!(openai_request_with_system.seed, Some(69));
        assert!(openai_request_with_system.tools.is_none());
        assert_eq!(openai_request_with_system.top_p, Some(0.9));
        assert_eq!(openai_request_with_system.presence_penalty, Some(0.1));
        assert_eq!(openai_request_with_system.frequency_penalty, Some(0.2));
    }

    #[test]
    fn test_try_from_openai_response() {
        // Test case 1: Valid response with content
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
            max_tokens: Some(100),
            seed: Some(69),
            top_p: Some(0.9),
            presence_penalty: Some(0.1),
            frequency_penalty: Some(0.2),
            stream: false,
            json_mode: ModelInferenceRequestJsonMode::On,
            tool_config: None,
            function_type: FunctionType::Chat,
            output_schema: None,
            extra_body: Default::default(),
            ..Default::default()
        };

        let request_body = OpenAIRequest {
            messages: vec![],
            model: "gpt-3.5-turbo",
            temperature: Some(0.5),
            top_p: Some(0.5),
            presence_penalty: Some(0.5),
            frequency_penalty: Some(0.5),
            max_completion_tokens: Some(100),
            seed: Some(69),
            stream: false,
            response_format: Some(OpenAIResponseFormat::Text),
            stream_options: None,
            tools: None,
            tool_choice: None,
            parallel_tool_calls: None,
            logprobs: None,
            top_logprobs: None,
            stop: None,
            n: None,
            logit_bias: None,
            user: None,
        };
        let raw_request = serde_json::to_string(&request_body).unwrap();
        let raw_response = "test_response".to_string();
        let result = ProviderInferenceResponse::try_from(OpenAIResponseWithMetadata {
            response: valid_response,
            latency: Latency::NonStreaming {
                response_time: Duration::from_millis(100),
            },
            raw_request: raw_request.clone(),
            generic_request: &generic_request,
            raw_response: raw_response.clone(),
        });
        assert!(result.is_ok());
        let inference_response = result.unwrap();
        assert_eq!(
            inference_response.output,
            vec!["Hello, world!".to_string().into()]
        );
        assert_eq!(inference_response.usage.input_tokens, 10);
        assert_eq!(inference_response.usage.output_tokens, 20);
        assert_eq!(inference_response.finish_reason, Some(FinishReason::Stop));
        assert_eq!(
            inference_response.latency,
            Latency::NonStreaming {
                response_time: Duration::from_millis(100)
            }
        );
        assert_eq!(inference_response.raw_request, raw_request);
        assert_eq!(inference_response.raw_response, raw_response);
        assert_eq!(inference_response.system, None);
        assert_eq!(
            inference_response.input_messages,
            vec![RequestMessage {
                role: Role::User,
                content: vec!["test_user".to_string().into()],
            }]
        );
        // Test case 2: Valid response with tool calls
        let valid_response_with_tools = OpenAIResponse {
            choices: vec![OpenAIResponseChoice {
                index: 0,
                finish_reason: OpenAIFinishReason::ToolCalls,
                message: OpenAIResponseMessage {
                    content: None,
                    tool_calls: Some(vec![OpenAIResponseToolCall {
                        id: "call1".to_string(),
                        r#type: OpenAIToolType::Function,
                        function: OpenAIResponseFunctionCall {
                            name: "test_function".to_string(),
                            arguments: "{}".to_string(),
                        },
                    }]),
                    reasoning_content: None,
                },
            }],
            usage: OpenAIUsage {
                prompt_tokens: 15,
                completion_tokens: 25,
                total_tokens: 40,
            },
        };
        let generic_request = ModelInferenceRequest {
            inference_id: Uuid::now_v7(),
            messages: vec![RequestMessage {
                role: Role::Assistant,
                content: vec!["test_assistant".to_string().into()],
            }],
            system: Some("test_system".to_string()),
            temperature: Some(0.5),
            top_p: Some(0.9),
            presence_penalty: Some(0.1),
            frequency_penalty: Some(0.2),
            max_tokens: Some(100),
            seed: Some(69),
            stream: false,
            json_mode: ModelInferenceRequestJsonMode::On,
            tool_config: None,
            function_type: FunctionType::Chat,
            output_schema: None,
            extra_body: Default::default(),
            ..Default::default()
        };

        let request_body = OpenAIRequest {
            messages: vec![],
            model: "gpt-3.5-turbo",
            temperature: Some(0.5),
            top_p: Some(0.5),
            presence_penalty: Some(0.5),
            frequency_penalty: Some(0.5),
            max_completion_tokens: Some(100),
            seed: Some(69),
            stream: false,
            response_format: Some(OpenAIResponseFormat::Text),
            stream_options: None,
            tools: None,
            tool_choice: None,
            parallel_tool_calls: None,
            logprobs: None,
            top_logprobs: None,
            stop: None,
            n: None,
            logit_bias: None,
            user: None,
        };
        let raw_request = serde_json::to_string(&request_body).unwrap();
        let result = ProviderInferenceResponse::try_from(OpenAIResponseWithMetadata {
            response: valid_response_with_tools,
            latency: Latency::NonStreaming {
                response_time: Duration::from_millis(110),
            },
            raw_request: raw_request.clone(),
            generic_request: &generic_request,
            raw_response: raw_response.clone(),
        });
        assert!(result.is_ok());
        let inference_response = result.unwrap();
        assert_eq!(
            inference_response.output,
            vec![ContentBlockOutput::ToolCall(ToolCall {
                id: "call1".to_string(),
                name: "test_function".to_string(),
                arguments: "{}".to_string(),
            })]
        );
        assert_eq!(inference_response.usage.input_tokens, 15);
        assert_eq!(inference_response.usage.output_tokens, 25);
        assert_eq!(
            inference_response.finish_reason,
            Some(FinishReason::ToolCall)
        );
        assert_eq!(
            inference_response.latency,
            Latency::NonStreaming {
                response_time: Duration::from_millis(110)
            }
        );
        assert_eq!(inference_response.raw_request, raw_request);
        assert_eq!(inference_response.raw_response, raw_response);
        assert_eq!(inference_response.system, Some("test_system".to_string()));
        assert_eq!(
            inference_response.input_messages,
            vec![RequestMessage {
                role: Role::Assistant,
                content: vec!["test_assistant".to_string().into()],
            }]
        );
        // Test case 3: Invalid response with no choices
        let invalid_response_no_choices = OpenAIResponse {
            choices: vec![],
            usage: OpenAIUsage {
                prompt_tokens: 5,
                completion_tokens: 0,
                total_tokens: 5,
            },
        };
        let request_body = OpenAIRequest {
            messages: vec![],
            model: "gpt-3.5-turbo",
            temperature: Some(0.5),
            top_p: Some(0.9),
            presence_penalty: Some(0.1),
            frequency_penalty: Some(0.2),
            max_completion_tokens: Some(100),
            seed: Some(69),
            stream: false,
            response_format: Some(OpenAIResponseFormat::Text),
            stream_options: None,
            tools: None,
            tool_choice: None,
            parallel_tool_calls: None,
            logprobs: None,
            top_logprobs: None,
            stop: None,
            n: None,
            logit_bias: None,
            user: None,
        };
        let result = ProviderInferenceResponse::try_from(OpenAIResponseWithMetadata {
            response: invalid_response_no_choices,
            latency: Latency::NonStreaming {
                response_time: Duration::from_millis(120),
            },
            raw_request: serde_json::to_string(&request_body).unwrap(),
            generic_request: &generic_request,
            raw_response: raw_response.clone(),
        });
        assert!(result.is_err());
        let err = result.unwrap_err();
        let details = err.get_details();
        assert!(matches!(details, ErrorDetails::InferenceServer { .. }));

        // Test case 4: Invalid response with multiple choices
        let invalid_response_multiple_choices = OpenAIResponse {
            choices: vec![
                OpenAIResponseChoice {
                    index: 0,
                    message: OpenAIResponseMessage {
                        content: Some("Choice 1".to_string()),
                        tool_calls: None,
                        reasoning_content: None,
                    },
                    finish_reason: OpenAIFinishReason::Stop,
                },
                OpenAIResponseChoice {
                    index: 1,
                    finish_reason: OpenAIFinishReason::Stop,
                    message: OpenAIResponseMessage {
                        content: Some("Choice 2".to_string()),
                        tool_calls: None,
                        reasoning_content: None,
                    },
                },
            ],
            usage: OpenAIUsage {
                prompt_tokens: 10,
                completion_tokens: 10,
                total_tokens: 20,
            },
        };

        let request_body = OpenAIRequest {
            messages: vec![],
            model: "gpt-3.5-turbo",
            temperature: Some(0.5),
            top_p: Some(0.9),
            presence_penalty: Some(0.1),
            frequency_penalty: Some(0.2),
            max_completion_tokens: Some(100),
            seed: Some(69),
            stream: false,
            response_format: Some(OpenAIResponseFormat::Text),
            stream_options: None,
            tools: None,
            tool_choice: None,
            parallel_tool_calls: None,
            logprobs: None,
            top_logprobs: None,
            stop: None,
            n: None,
            logit_bias: None,
            user: None,
        };
        let result = ProviderInferenceResponse::try_from(OpenAIResponseWithMetadata {
            response: invalid_response_multiple_choices,
            latency: Latency::NonStreaming {
                response_time: Duration::from_millis(130),
            },
            raw_request: serde_json::to_string(&request_body).unwrap(),
            generic_request: &generic_request,
            raw_response: raw_response.clone(),
        });
        assert!(result.is_err());
        let err = result.unwrap_err();
        let details = err.get_details();
        assert!(matches!(details, ErrorDetails::InferenceServer { .. }));
    }

    #[test]
    fn test_prepare_openai_tools() {
        let request_with_tools = ModelInferenceRequest {
            inference_id: Uuid::now_v7(),
            messages: vec![RequestMessage {
                role: Role::User,
                content: vec!["What's the weather?".to_string().into()],
            }],
            system: None,
            temperature: None,
            top_p: None,
            presence_penalty: None,
            frequency_penalty: None,
            max_tokens: None,
            seed: None,
            stream: false,
            json_mode: ModelInferenceRequestJsonMode::On,
            tool_config: Some(Cow::Borrowed(&MULTI_TOOL_CONFIG)),
            function_type: FunctionType::Chat,
            output_schema: None,
            extra_body: Default::default(),
            ..Default::default()
        };
        let (tools, tool_choice, parallel_tool_calls) = prepare_openai_tools(&request_with_tools);
        let tools = tools.unwrap();
        assert_eq!(tools.len(), 2);
        assert_eq!(tools[0].function.name, WEATHER_TOOL.name());
        assert_eq!(tools[0].function.parameters, WEATHER_TOOL.parameters());
        assert_eq!(tools[1].function.name, QUERY_TOOL.name());
        assert_eq!(tools[1].function.parameters, QUERY_TOOL.parameters());
        let tool_choice = tool_choice.unwrap();
        assert_eq!(
            tool_choice,
            OpenAIToolChoice::String(OpenAIToolChoiceString::Required)
        );
        let parallel_tool_calls = parallel_tool_calls.unwrap();
        assert!(parallel_tool_calls);
        let tool_config = ToolCallConfig {
            tools_available: vec![],
            tool_choice: ToolChoice::Required,
            parallel_tool_calls: Some(true),
        };

        // Test no tools but a tool choice and make sure tool choice output is None
        let request_without_tools = ModelInferenceRequest {
            inference_id: Uuid::now_v7(),
            messages: vec![RequestMessage {
                role: Role::User,
                content: vec!["What's the weather?".to_string().into()],
            }],
            system: None,
            temperature: None,
            top_p: None,
            presence_penalty: None,
            frequency_penalty: None,
            max_tokens: None,
            seed: None,
            stream: false,
            json_mode: ModelInferenceRequestJsonMode::On,
            tool_config: Some(Cow::Borrowed(&tool_config)),
            function_type: FunctionType::Chat,
            output_schema: None,
            extra_body: Default::default(),
            ..Default::default()
        };
        let (tools, tool_choice, parallel_tool_calls) =
            prepare_openai_tools(&request_without_tools);
        assert!(tools.is_none());
        assert!(tool_choice.is_none());
        assert!(parallel_tool_calls.is_none());
    }

    #[test]
    fn test_tensorzero_to_openai_messages() {
        let content_blocks = vec!["Hello".to_string().into()];
        let openai_messages = tensorzero_to_openai_user_messages(&content_blocks).unwrap();
        assert_eq!(openai_messages.len(), 1);
        match &openai_messages[0] {
            OpenAIRequestMessage::User(content) => {
                assert_eq!(
                    content.content,
                    &[OpenAIContentBlock::Text {
                        text: "Hello".into()
                    }]
                );
            }
            _ => panic!("Expected a user message"),
        }

        // Message with multiple blocks
        let content_blocks = vec![
            "Hello".to_string().into(),
            "How are you?".to_string().into(),
        ];
        let openai_messages = tensorzero_to_openai_user_messages(&content_blocks).unwrap();
        assert_eq!(openai_messages.len(), 1);
        match &openai_messages[0] {
            OpenAIRequestMessage::User(content) => {
                assert_eq!(
                    content.content,
                    vec![
                        OpenAIContentBlock::Text {
                            text: "Hello".into()
                        },
                        OpenAIContentBlock::Text {
                            text: "How are you?".into()
                        }
                    ]
                );
            }
            _ => panic!("Expected a user message"),
        }

        // User message with one string and one tool call block
        // Since user messages in OpenAI land can't contain tool calls (nor should they honestly),
        // We split the tool call out into a separate assistant message
        let tool_block = ContentBlock::ToolCall(ToolCall {
            id: "call1".to_string(),
            name: "test_function".to_string(),
            arguments: "{}".to_string(),
        });
        let content_blocks = vec!["Hello".to_string().into(), tool_block];
        let openai_messages = tensorzero_to_openai_assistant_messages(&content_blocks).unwrap();
        assert_eq!(openai_messages.len(), 1);
        match &openai_messages[0] {
            OpenAIRequestMessage::Assistant(content) => {
                assert_eq!(
                    content.content,
                    Some(vec![OpenAIContentBlock::Text {
                        text: "Hello".into()
                    }])
                );
                let tool_calls = content.tool_calls.as_ref().unwrap();
                assert_eq!(tool_calls.len(), 1);
                assert_eq!(tool_calls[0].id, "call1");
                assert_eq!(tool_calls[0].function.name, "test_function");
                assert_eq!(tool_calls[0].function.arguments, "{}");
            }
            _ => panic!("Expected an assistant message"),
        }
    }

    #[test]
    fn test_openai_to_tensorzero_chunk() {
        let chunk = OpenAIChatChunk {
            choices: vec![OpenAIChatChunkChoice {
                delta: OpenAIDelta {
                    content: Some("Hello".to_string()),
                    tool_calls: None,
                    reasoning_content: None,
                },
                finish_reason: Some(OpenAIFinishReason::Stop),
            }],
            usage: None,
        };
        let mut tool_call_ids = vec!["id1".to_string()];
        let mut tool_call_names = vec!["name1".to_string()];
        let message = openai_to_tensorzero_chunk(
            "my_raw_chunk".to_string(),
            chunk.clone(),
            Duration::from_millis(50),
            &mut tool_call_ids,
            &mut tool_call_names,
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
        let chunk = OpenAIChatChunk {
            choices: vec![OpenAIChatChunkChoice {
                finish_reason: Some(OpenAIFinishReason::ToolCalls),
                delta: OpenAIDelta {
                    content: None,
                    tool_calls: Some(vec![OpenAIToolCallChunk {
                        index: 0,
                        id: None,
                        function: OpenAIFunctionCallChunk {
                            name: None,
                            arguments: Some("{\"hello\":\"world\"}".to_string()),
                        },
                    }]),
                    reasoning_content: None,
                },
            }],
            usage: None,
        };
        let message = openai_to_tensorzero_chunk(
            "my_raw_chunk".to_string(),
            chunk.clone(),
            Duration::from_millis(50),
            &mut tool_call_ids,
            &mut tool_call_names,
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
        let chunk = OpenAIChatChunk {
            choices: vec![OpenAIChatChunkChoice {
                finish_reason: None,
                delta: OpenAIDelta {
                    content: None,
                    tool_calls: Some(vec![OpenAIToolCallChunk {
                        index: 1,
                        id: None,
                        function: OpenAIFunctionCallChunk {
                            name: None,
                            arguments: Some("{\"hello\":\"world\"}".to_string()),
                        },
                    }]),
                    reasoning_content: None,
                },
            }],
            usage: None,
        };
        let error = openai_to_tensorzero_chunk(
            "my_raw_chunk".to_string(),
            chunk.clone(),
            Duration::from_millis(50),
            &mut tool_call_ids,
            &mut tool_call_names,
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
        let chunk = OpenAIChatChunk {
            choices: vec![OpenAIChatChunkChoice {
                finish_reason: Some(OpenAIFinishReason::Stop),
                delta: OpenAIDelta {
                    content: None,
                    tool_calls: Some(vec![OpenAIToolCallChunk {
                        index: 1,
                        id: Some("id2".to_string()),
                        function: OpenAIFunctionCallChunk {
                            name: Some("name2".to_string()),
                            arguments: Some("{\"hello\":\"world\"}".to_string()),
                        },
                    }]),
                    reasoning_content: None,
                },
            }],
            usage: None,
        };
        let message = openai_to_tensorzero_chunk(
            "my_raw_chunk".to_string(),
            chunk.clone(),
            Duration::from_millis(50),
            &mut tool_call_ids,
            &mut tool_call_names,
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
        assert_eq!(message.finish_reason, Some(FinishReason::Stop));
        // Check that the lists were updated
        assert_eq!(tool_call_ids, vec!["id1".to_string(), "id2".to_string()]);
        assert_eq!(
            tool_call_names,
            vec!["name1".to_string(), "name2".to_string()]
        );

        // Check a chunk with no choices and only usage
        // Test a correct new tool chunk
        let chunk = OpenAIChatChunk {
            choices: vec![],
            usage: Some(OpenAIUsage {
                prompt_tokens: 10,
                completion_tokens: 20,
                total_tokens: 30,
            }),
        };
        let message = openai_to_tensorzero_chunk(
            "my_raw_chunk".to_string(),
            chunk.clone(),
            Duration::from_millis(50),
            &mut tool_call_ids,
            &mut tool_call_names,
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
    }

    #[test]
    fn test_new_openai_response_format() {
        // Test JSON mode On
        let json_mode = ModelInferenceRequestJsonMode::On;
        let output_schema = None;
        let format = OpenAIResponseFormat::new(&json_mode, output_schema, "gpt-4o");
        assert_eq!(format, Some(OpenAIResponseFormat::JsonObject));

        // Test JSON mode Off
        let json_mode = ModelInferenceRequestJsonMode::Off;
        let format = OpenAIResponseFormat::new(&json_mode, output_schema, "gpt-4o");
        assert_eq!(format, None);

        // Test JSON mode Strict with no schema
        let json_mode = ModelInferenceRequestJsonMode::Strict;
        let format = OpenAIResponseFormat::new(&json_mode, output_schema, "gpt-4o");
        assert_eq!(format, Some(OpenAIResponseFormat::JsonObject));

        // Test JSON mode Strict with schema
        let json_mode = ModelInferenceRequestJsonMode::Strict;
        let schema = serde_json::json!({
            "type": "object",
            "properties": {
                "foo": {"type": "string"}
            }
        });
        let output_schema = Some(&schema);
        let format = OpenAIResponseFormat::new(&json_mode, output_schema, "gpt-4o");
        match format {
            Some(OpenAIResponseFormat::JsonSchema { json_schema }) => {
                assert_eq!(json_schema["schema"], schema);
                assert_eq!(json_schema["name"], "response");
                assert_eq!(json_schema["strict"], true);
            }
            _ => panic!("Expected JsonSchema format"),
        }

        // Test JSON mode Strict with schema but gpt-3.5
        let json_mode = ModelInferenceRequestJsonMode::Strict;
        let schema = serde_json::json!({
            "type": "object",
            "properties": {
                "foo": {"type": "string"}
            }
        });
        let output_schema = Some(&schema);
        let format = OpenAIResponseFormat::new(&json_mode, output_schema, "gpt-3.5-turbo");
        assert_eq!(format, Some(OpenAIResponseFormat::JsonObject));
    }

    #[test]
    fn test_openai_api_base() {
        assert_eq!(
            OPENAI_DEFAULT_BASE_URL.as_str(),
            "https://api.openai.com/v1/"
        );
    }

    #[test]
    fn test_tensorzero_to_openai_system_message() {
        // Test Case 1: system is None, json_mode is Off
        let system = None;
        let json_mode = ModelInferenceRequestJsonMode::Off;
        let messages: Vec<OpenAIRequestMessage> = vec![];
        let result = tensorzero_to_openai_system_message(system, &json_mode, &messages);
        assert_eq!(result, None);

        // Test Case 2: system is Some, json_mode is On, messages contain "json"
        let system = Some("System instructions");
        let json_mode = ModelInferenceRequestJsonMode::On;
        let messages = vec![
            OpenAIRequestMessage::User(OpenAIUserRequestMessage {
                content: vec![OpenAIContentBlock::Text {
                    text: "Please respond in JSON format.".into(),
                }],
            }),
            OpenAIRequestMessage::Assistant(OpenAIAssistantRequestMessage {
                content: Some(vec![OpenAIContentBlock::Text {
                    text: "Sure, here is the data.".into(),
                }]),
                tool_calls: None,
            }),
        ];
        let expected = Some(OpenAIRequestMessage::System(OpenAISystemRequestMessage {
            content: Cow::Borrowed("System instructions"),
        }));
        let result = tensorzero_to_openai_system_message(system, &json_mode, &messages);
        assert_eq!(result, expected);

        // Test Case 3: system is Some, json_mode is On, messages do not contain "json"
        let system = Some("System instructions");
        let json_mode = ModelInferenceRequestJsonMode::On;
        let messages = vec![
            OpenAIRequestMessage::User(OpenAIUserRequestMessage {
                content: vec![OpenAIContentBlock::Text {
                    text: "Hello, how are you?".into(),
                }],
            }),
            OpenAIRequestMessage::Assistant(OpenAIAssistantRequestMessage {
                content: Some(vec![OpenAIContentBlock::Text {
                    text: "I am fine, thank you!".into(),
                }]),
                tool_calls: None,
            }),
        ];
        let expected_content = "Respond using JSON.\n\nSystem instructions".to_string();
        let expected = Some(OpenAIRequestMessage::System(OpenAISystemRequestMessage {
            content: Cow::Owned(expected_content),
        }));
        let result = tensorzero_to_openai_system_message(system, &json_mode, &messages);
        assert_eq!(result, expected);

        // Test Case 4: system is Some, json_mode is Off
        let system = Some("System instructions");
        let json_mode = ModelInferenceRequestJsonMode::Off;
        let messages = vec![
            OpenAIRequestMessage::User(OpenAIUserRequestMessage {
                content: vec![OpenAIContentBlock::Text {
                    text: "Hello, how are you?".into(),
                }],
            }),
            OpenAIRequestMessage::Assistant(OpenAIAssistantRequestMessage {
                content: Some(vec![OpenAIContentBlock::Text {
                    text: "I am fine, thank you!".into(),
                }]),
                tool_calls: None,
            }),
        ];
        let expected = Some(OpenAIRequestMessage::System(OpenAISystemRequestMessage {
            content: Cow::Borrowed("System instructions"),
        }));
        let result = tensorzero_to_openai_system_message(system, &json_mode, &messages);
        assert_eq!(result, expected);

        // Test Case 5: system is Some, json_mode is Strict
        let system = Some("System instructions");
        let json_mode = ModelInferenceRequestJsonMode::Strict;
        let messages = vec![
            OpenAIRequestMessage::User(OpenAIUserRequestMessage {
                content: vec![OpenAIContentBlock::Text {
                    text: "Hello, how are you?".into(),
                }],
            }),
            OpenAIRequestMessage::Assistant(OpenAIAssistantRequestMessage {
                content: Some(vec![OpenAIContentBlock::Text {
                    text: "I am fine, thank you!".into(),
                }]),
                tool_calls: None,
            }),
        ];
        let expected = Some(OpenAIRequestMessage::System(OpenAISystemRequestMessage {
            content: Cow::Borrowed("System instructions"),
        }));
        let result = tensorzero_to_openai_system_message(system, &json_mode, &messages);
        assert_eq!(result, expected);

        // Test Case 6: system contains "json", json_mode is On
        let system = Some("Respond using JSON.\n\nSystem instructions");
        let json_mode = ModelInferenceRequestJsonMode::On;
        let messages = vec![OpenAIRequestMessage::User(OpenAIUserRequestMessage {
            content: vec![OpenAIContentBlock::Text {
                text: "Hello, how are you?".into(),
            }],
        })];
        let expected = Some(OpenAIRequestMessage::System(OpenAISystemRequestMessage {
            content: Cow::Borrowed("Respond using JSON.\n\nSystem instructions"),
        }));
        let result = tensorzero_to_openai_system_message(system, &json_mode, &messages);
        assert_eq!(result, expected);

        // Test Case 7: system is None, json_mode is On
        let system = None;
        let json_mode = ModelInferenceRequestJsonMode::On;
        let messages = vec![
            OpenAIRequestMessage::User(OpenAIUserRequestMessage {
                content: vec![OpenAIContentBlock::Text {
                    text: "Tell me a joke.".into(),
                }],
            }),
            OpenAIRequestMessage::Assistant(OpenAIAssistantRequestMessage {
                content: Some(vec![OpenAIContentBlock::Text {
                    text: "Sure, here's one for you.".into(),
                }]),
                tool_calls: None,
            }),
        ];
        let expected = Some(OpenAIRequestMessage::System(OpenAISystemRequestMessage {
            content: Cow::Owned("Respond using JSON.".to_string()),
        }));
        let result = tensorzero_to_openai_system_message(system, &json_mode, &messages);
        assert_eq!(result, expected);

        // Test Case 8: system is None, json_mode is Strict
        let system = None;
        let json_mode = ModelInferenceRequestJsonMode::Strict;
        let messages = vec![
            OpenAIRequestMessage::User(OpenAIUserRequestMessage {
                content: vec![OpenAIContentBlock::Text {
                    text: "Provide a summary of the news.".into(),
                }],
            }),
            OpenAIRequestMessage::Assistant(OpenAIAssistantRequestMessage {
                content: Some(vec![OpenAIContentBlock::Text {
                    text: "Here's the summary.".into(),
                }]),
                tool_calls: None,
            }),
        ];

        let result = tensorzero_to_openai_system_message(system, &json_mode, &messages);
        assert!(result.is_none());

        // Test Case 9: system is None, json_mode is On, with empty messages
        let system = None;
        let json_mode = ModelInferenceRequestJsonMode::On;
        let messages: Vec<OpenAIRequestMessage> = vec![];
        let expected = Some(OpenAIRequestMessage::System(OpenAISystemRequestMessage {
            content: Cow::Owned("Respond using JSON.".to_string()),
        }));
        let result = tensorzero_to_openai_system_message(system, &json_mode, &messages);
        assert_eq!(result, expected);

        // Test Case 10: system is None, json_mode is Off, with messages containing "json"
        let system = None;
        let json_mode = ModelInferenceRequestJsonMode::Off;
        let messages = vec![OpenAIRequestMessage::User(OpenAIUserRequestMessage {
            content: vec![OpenAIContentBlock::Text {
                text: "Please include JSON in your response.".into(),
            }],
        })];
        let expected = None;
        let result = tensorzero_to_openai_system_message(system, &json_mode, &messages);
        assert_eq!(result, expected);
    }

    #[test]
    fn test_create_file_url() {
        use url::Url;

        // Test Case 1: Base URL without trailing slash
        let base_url = Url::parse("https://api.openai.com/v1").unwrap();
        let file_id = Some("file123");
        let result = get_file_url(&base_url, file_id).unwrap();
        assert_eq!(
            result.as_str(),
            "https://api.openai.com/v1/files/file123/content"
        );

        // Test Case 2: Base URL with trailing slash
        let base_url = Url::parse("https://api.openai.com/v1/").unwrap();
        let file_id = Some("file456");
        let result = get_file_url(&base_url, file_id).unwrap();
        assert_eq!(
            result.as_str(),
            "https://api.openai.com/v1/files/file456/content"
        );

        // Test Case 3: Base URL with custom domain
        let base_url = Url::parse("https://custom-openai.example.com").unwrap();
        let file_id = Some("file789");
        let result = get_file_url(&base_url, file_id).unwrap();
        assert_eq!(
            result.as_str(),
            "https://custom-openai.example.com/files/file789/content"
        );

        // Test Case 4: Base URL without trailing slash, no file ID
        let base_url = Url::parse("https://api.openai.com/v1").unwrap();
        let result = get_file_url(&base_url, None).unwrap();
        assert_eq!(result.as_str(), "https://api.openai.com/v1/files");

        // Test Case 5: Base URL with trailing slash, no file ID
        let base_url = Url::parse("https://api.openai.com/v1/").unwrap();
        let result = get_file_url(&base_url, None).unwrap();
        assert_eq!(result.as_str(), "https://api.openai.com/v1/files");

        // Test Case 6: Custom domain base URL, no file ID
        let base_url = Url::parse("https://custom-openai.example.com").unwrap();
        let result = get_file_url(&base_url, None).unwrap();
        assert_eq!(result.as_str(), "https://custom-openai.example.com/files");
    }

    #[test]
    fn test_try_from_openai_credentials() {
        // Test Static credentials
        let generic = Credential::Static(SecretString::from("test_key"));
        let creds = OpenAICredentials::try_from(generic).unwrap();
        assert!(matches!(creds, OpenAICredentials::Static(_)));

        // Test Dynamic credentials
        let generic = Credential::Dynamic("key_name".to_string());
        let creds = OpenAICredentials::try_from(generic).unwrap();
        assert!(matches!(creds, OpenAICredentials::Dynamic(_)));

        // Test None credentials
        let generic = Credential::None;
        let creds = OpenAICredentials::try_from(generic).unwrap();
        assert!(matches!(creds, OpenAICredentials::None));

        // Test Missing credentials
        let generic = Credential::Missing;
        let creds = OpenAICredentials::try_from(generic).unwrap();
        assert!(matches!(creds, OpenAICredentials::None));

        // Test invalid credential type
        let generic = Credential::FileContents(SecretString::from("test"));
        let result = OpenAICredentials::try_from(generic);
        assert!(result.is_err());
        assert!(matches!(
            result.unwrap_err().get_owned_details(),
            ErrorDetails::Config { message } if message.contains("Invalid api_key_location")
        ));
    }

    #[test]
    fn test_serialize_user_messages() {
        // Test that a single message is serialized as 'content: string'
        let message = OpenAIUserRequestMessage {
            content: vec![OpenAIContentBlock::Text {
                text: "My single message".into(),
            }],
        };
        let serialized = serde_json::to_string(&message).unwrap();
        assert_eq!(serialized, r#"{"content":"My single message"}"#);

        // Test that a multiple messages are serialized as an array of content blocks
        let message = OpenAIUserRequestMessage {
            content: vec![
                OpenAIContentBlock::Text {
                    text: "My first message".into(),
                },
                OpenAIContentBlock::Text {
                    text: "My second message".into(),
                },
            ],
        };
        let serialized = serde_json::to_string(&message).unwrap();
        assert_eq!(
            serialized,
            r#"{"content":[{"type":"text","text":"My first message"},{"type":"text","text":"My second message"}]}"#
        );
    }

    #[test]
    #[traced_test]
    fn test_check_api_base_suffix() {
        // Valid cases (should not warn)
        check_api_base_suffix(&Url::parse("http://localhost:1234/").unwrap());
        check_api_base_suffix(&Url::parse("http://localhost:1234/openai/").unwrap());
        check_api_base_suffix(&Url::parse("http://localhost:1234/openai/v1").unwrap());
        check_api_base_suffix(&Url::parse("http://localhost:1234/openai/v1/").unwrap());
        check_api_base_suffix(&Url::parse("http://localhost:1234/v1/").unwrap());
        check_api_base_suffix(&Url::parse("http://localhost:1234/v2").unwrap());
        check_api_base_suffix(&Url::parse("http://localhost:1234/v2/").unwrap());

        // Invalid cases (should warn)
        let url1 = Url::parse("http://localhost:1234/chat/completions").unwrap();
        check_api_base_suffix(&url1);
        assert!(logs_contain("automatically appends `/chat/completions`"));
        assert!(logs_contain(url1.as_ref()));

        let url2 = Url::parse("http://localhost:1234/chat/completions/").unwrap();
        check_api_base_suffix(&url2);
        assert!(logs_contain("automatically appends `/chat/completions`"));
        assert!(logs_contain(url2.as_ref()));

        let url3 = Url::parse("http://localhost:1234/v1/chat/completions").unwrap();
        check_api_base_suffix(&url3);
        assert!(logs_contain("automatically appends `/chat/completions`"));
        assert!(logs_contain(url3.as_ref()));

        let url4 = Url::parse("http://localhost:1234/v1/chat/completions/").unwrap();
        check_api_base_suffix(&url4);
        assert!(logs_contain("automatically appends `/chat/completions`"));
        assert!(logs_contain(url4.as_ref()));
    }

    #[test]
    #[traced_test]
    fn test_openai_provider_new_api_base_check() {
        let model_name = "test-model".to_string();
        let api_key_location = Some(CredentialLocation::None);

        // Valid cases (should not warn)
        let _ = OpenAIProvider::new(
            model_name.clone(),
            Some(Url::parse("http://localhost:1234/v1/").unwrap()),
            api_key_location.clone(),
        )
        .unwrap();

        let _ = OpenAIProvider::new(
            model_name.clone(),
            Some(Url::parse("http://localhost:1234/v1").unwrap()),
            api_key_location.clone(),
        )
        .unwrap();

        // Invalid cases (should warn)
        let invalid_url_1 = Url::parse("http://localhost:1234/chat/completions").unwrap();
        let _ = OpenAIProvider::new(
            model_name.clone(),
            Some(invalid_url_1.clone()),
            api_key_location.clone(),
        )
        .unwrap();
        assert!(logs_contain("automatically appends `/chat/completions`"));
        assert!(logs_contain(invalid_url_1.as_ref()));

        let invalid_url_2 = Url::parse("http://localhost:1234/v1/chat/completions/").unwrap();
        let _ = OpenAIProvider::new(
            model_name.clone(),
            Some(invalid_url_2.clone()),
            api_key_location.clone(),
        )
        .unwrap();
        assert!(logs_contain("automatically appends `/chat/completions`"));
        assert!(logs_contain(invalid_url_2.as_ref()));
    }

    #[test]
    fn test_get_moderation_url() {
        // Test with standard OpenAI base URL
        let base_url = Url::parse("https://api.openai.com/v1/").unwrap();
        let result = get_moderation_url(&base_url).unwrap();
        assert_eq!(result.as_str(), "https://api.openai.com/v1/moderations");

        // Test with URL without trailing slash
        let base_url = Url::parse("https://api.openai.com/v1").unwrap();
        let result = get_moderation_url(&base_url).unwrap();
        assert_eq!(result.as_str(), "https://api.openai.com/v1/moderations");

        // Test with custom base URL
        let custom_base = "https://custom.openai.com/api/";
        let custom_url = get_moderation_url(&Url::parse(custom_base).unwrap()).unwrap();
        assert_eq!(
            custom_url.as_str(),
            "https://custom.openai.com/api/moderations"
        );
    }

    #[test]
    fn test_openai_moderation_request_single() {
        let input = ModerationInput::Single("test text".to_string());
        let request = OpenAIModerationRequest::new(&input, Some("text-moderation-latest"));

        let json = serde_json::to_value(&request).unwrap();
        assert_eq!(json["input"], "test text");
        assert_eq!(json["model"], "text-moderation-latest");
    }

    #[test]
    fn test_openai_moderation_request_batch() {
        let input = ModerationInput::Batch(vec![
            "text1".to_string(),
            "text2".to_string(),
            "text3".to_string(),
        ]);
        let request = OpenAIModerationRequest::new(&input, None);

        let json = serde_json::to_value(&request).unwrap();
        assert!(json["input"].is_array());
        assert_eq!(json["input"].as_array().unwrap().len(), 3);
        assert_eq!(json["input"][0], "text1");
        assert_eq!(json["input"][1], "text2");
        assert_eq!(json["input"][2], "text3");
        assert!(json.get("model").is_none());
    }

    #[test]
    fn test_openai_moderation_response_parsing() {
        let response_json = r#"{
            "id": "modr-12345",
            "model": "text-moderation-stable",
            "results": [
                {
                    "flagged": true,
                    "categories": {
                        "hate": false,
                        "hate/threatening": false,
                        "harassment": true,
                        "harassment/threatening": false,
                        "self-harm": false,
                        "self-harm/intent": false,
                        "self-harm/instructions": false,
                        "sexual": false,
                        "sexual/minors": false,
                        "violence": false,
                        "violence/graphic": false
                    },
                    "category_scores": {
                        "hate": 0.001,
                        "hate/threatening": 0.0001,
                        "harassment": 0.95,
                        "harassment/threatening": 0.001,
                        "self-harm": 0.0001,
                        "self-harm/intent": 0.0001,
                        "self-harm/instructions": 0.0001,
                        "sexual": 0.001,
                        "sexual/minors": 0.0001,
                        "violence": 0.001,
                        "violence/graphic": 0.0001
                    }
                }
            ]
        }"#;

        let response: OpenAIModerationResponse = serde_json::from_str(response_json).unwrap();
        assert_eq!(response._id, "modr-12345");
        assert_eq!(response.model, "text-moderation-stable");
        assert_eq!(response.results.len(), 1);

        let result = &response.results[0];
        assert!(result.flagged);
        assert!(result.categories.harassment);
        assert!(!result.categories.hate);
        assert_eq!(result.category_scores.harassment, 0.95);
        assert_eq!(result.category_scores.hate, 0.001);
    }

    #[tokio::test]
    async fn test_response_provider_url_construction() {
        let provider =
            OpenAIProvider::new("gpt-4".to_string(), None, Some(CredentialLocation::None)).unwrap();

        // Verify the URL construction for responses endpoint
        let base_url = provider
            .api_base
            .as_ref()
            .unwrap_or(&OPENAI_DEFAULT_BASE_URL);
        let responses_url = base_url.join("responses").unwrap();
        assert_eq!(
            responses_url.as_str(),
            "https://api.openai.com/v1/responses"
        );
    }

    #[test]
    fn test_response_request_serialization() {
        use crate::responses::OpenAIResponseCreateParams;
        use serde_json::json;

        let params = OpenAIResponseCreateParams {
            model: Some("gpt-4".to_string()),
            input: Some(json!("Test input")),
            instructions: Some(json!("Be helpful")),
            tools: None,
            tool_choice: None,
            parallel_tool_calls: None,
            max_tool_calls: None,
            previous_response_id: None,
            prompt: None,
            temperature: Some(0.7),
            max_output_tokens: Some(1000),
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

        // Verify serialization doesn't include None fields
        let json = serde_json::to_value(&params).unwrap();
        assert_eq!(json["model"], "gpt-4");
        assert_eq!(json["input"], "Test input");
        assert_eq!(json["instructions"], "Be helpful");
        assert!((json["temperature"].as_f64().unwrap() - 0.7).abs() < 0.001);
        assert_eq!(json["max_output_tokens"], 1000);
        assert_eq!(json["stream"], false);

        // Verify None fields are not included
        assert!(!json.as_object().unwrap().contains_key("tools"));
        assert!(!json
            .as_object()
            .unwrap()
            .contains_key("previous_response_id"));
        assert!(!json.as_object().unwrap().contains_key("reasoning"));
    }

    #[test]
    fn test_response_streaming_params() {
        use crate::responses::OpenAIResponseCreateParams;
        use serde_json::json;

        let params = OpenAIResponseCreateParams {
            model: Some("gpt-4".to_string()),
            input: Some(json!("Test")),
            stream: Some(true),
            stream_options: Some(json!({
                "include_usage": true
            })),
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

        let json = serde_json::to_value(&params).unwrap();
        assert_eq!(json["stream"], true);
        assert_eq!(json["stream_options"]["include_usage"], true);
    }

    #[test]
    fn test_response_multimodal_input() {
        use crate::responses::OpenAIResponseCreateParams;
        use serde_json::json;

        // Test text input
        let text_params = OpenAIResponseCreateParams {
            model: Some("gpt-4".to_string()),
            input: Some(json!("Simple text input")),
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
            stream: None,
            stream_options: None,
            store: None,
            background: None,
            service_tier: None,
            modalities: None,
            user: None,
            unknown_fields: HashMap::new(),
        };

        let json = serde_json::to_value(&text_params).unwrap();
        assert_eq!(json["input"], "Simple text input");

        // Test array input with multimodal content
        let multimodal_params = OpenAIResponseCreateParams {
            model: Some("gpt-4o".to_string()),
            input: Some(json!([
                {
                    "type": "text",
                    "text": "What's in this image?"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64,iVBORw0KGgoAAAANS..."
                    }
                }
            ])),
            modalities: Some(vec!["text".to_string(), "image".to_string()]),
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
            stream: None,
            stream_options: None,
            store: None,
            background: None,
            service_tier: None,
            user: None,
            unknown_fields: HashMap::new(),
        };

        let json = serde_json::to_value(&multimodal_params).unwrap();
        assert!(json["input"].is_array());
        assert_eq!(json["input"][0]["type"], "text");
        assert_eq!(json["input"][1]["type"], "image_url");
        assert_eq!(json["modalities"][0], "text");
        assert_eq!(json["modalities"][1], "image");
    }

    #[test]
    fn test_openai_request_new_parameters() {
        // Test request with new parameters
        let logit_bias = HashMap::from([("123".to_string(), 50.0), ("456".to_string(), -100.0)]);

        let request_with_new_params = ModelInferenceRequest {
            inference_id: Uuid::now_v7(),
            messages: vec![RequestMessage {
                role: Role::User,
                content: vec!["Generate text".to_string().into()],
            }],
            system: Some("You are a helpful assistant".to_string()),
            tool_config: None,
            temperature: Some(0.8),
            max_tokens: Some(150),
            seed: Some(42),
            top_p: Some(0.95),
            presence_penalty: Some(0.0),
            frequency_penalty: Some(0.0),
            repetition_penalty: Some(1.0),
            stream: false,
            json_mode: ModelInferenceRequestJsonMode::Off,
            function_type: FunctionType::Chat,
            output_schema: None,
            logprobs: true,
            top_logprobs: Some(5),
            stop: Some(vec![Cow::Borrowed("END"), Cow::Borrowed("STOP")]),
            n: Some(1),
            logit_bias: Some(logit_bias.clone()),
            user: Some("test-user-123".to_string()),
            extra_body: Default::default(),
            extra_headers: Default::default(),
            extra_cache_key: None,
            chat_template: None,
            chat_template_kwargs: None,
            mm_processor_kwargs: None,
            guided_json: None,
            guided_regex: None,
            guided_choice: None,
            guided_grammar: None,
            structural_tag: None,
            guided_decoding_backend: None,
            guided_whitespace_pattern: None,
            gateway_request: None,
            ignore_eos: None,
        };

        let openai_request = OpenAIRequest::new("gpt-4", &request_with_new_params).unwrap();

        // Verify all new parameters are correctly set
        assert_eq!(openai_request.model, "gpt-4");
        assert_eq!(openai_request.logprobs, Some(true));
        assert_eq!(openai_request.top_logprobs, Some(5));
        assert_eq!(openai_request.stop, Some(vec!["END", "STOP"]));
        assert_eq!(openai_request.n, Some(1));
        assert_eq!(openai_request.logit_bias, Some(logit_bias));
        assert_eq!(openai_request.user, Some("test-user-123"));

        // Test that logprobs is None when false
        let request_no_logprobs = ModelInferenceRequest {
            logprobs: false,
            ..request_with_new_params.clone()
        };

        let openai_request_no_logprobs = OpenAIRequest::new("gpt-4", &request_no_logprobs).unwrap();
        assert_eq!(openai_request_no_logprobs.logprobs, None);
    }
}
