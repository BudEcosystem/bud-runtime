use std::collections::HashMap;
use std::sync::Mutex;
use std::time::Duration;

use base64::prelude::*;
use lazy_static::lazy_static;
use secrecy::{ExposeSecret, SecretString};
use serde_json::{json, Value};
use tokio_stream::StreamExt;
use uuid::Uuid;

use super::provider_trait::InferenceProvider;

use crate::cache::ModelProviderRequest;
use crate::completions::{
    CompletionChoice, CompletionChoiceChunk, CompletionChunk, CompletionProvider,
    CompletionProviderResponse, CompletionRequest, CompletionStream,
};
use crate::embeddings::{EmbeddingProvider, EmbeddingProviderResponse, EmbeddingRequest};
use crate::endpoints::inference::InferenceCredentials;
use crate::error::{Error, ErrorDetails};
use crate::inference::types::batch::PollBatchInferenceResponse;
use crate::inference::types::batch::{BatchRequestRow, BatchStatus};
use crate::inference::types::{
    batch::StartBatchProviderInferenceResponse, current_timestamp, ContentBlockChunk,
    ContentBlockOutput, Latency, ModelInferenceRequest, PeekableProviderInferenceResponseStream,
    ProviderInferenceResponse, ProviderInferenceResponseChunk, Usage,
};
use crate::inference::types::{
    ContentBlock, FileKind, FinishReason, ProviderInferenceResponseStreamInner,
};
use crate::inference::types::{Text, TextChunk, Thought, ThoughtChunk};
use crate::model::{CredentialLocation, ModelProvider};
use crate::moderation::{
    ModerationCategories, ModerationCategoryScores, ModerationProvider, ModerationProviderResponse,
    ModerationRequest, ModerationResult,
};
use crate::responses::{
    OpenAIResponse, OpenAIResponseCreateParams, ResponseError, ResponseInputItemsList,
    ResponseProvider, ResponseStatus, ResponseStreamEvent, ResponseUsage,
};
use crate::tool::{ToolCall, ToolCallChunk};

const PROVIDER_NAME: &str = "Dummy";
const PROVIDER_TYPE: &str = "dummy";

// 1x1 transparent PNG for dummy image responses
const DUMMY_PNG_BYTES: &[u8] = &[
    137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 13, 73, 72, 68, 82, 0, 0, 0, 1, 0, 0, 0, 1, 8, 6, 0,
    0, 0, 31, 21, 196, 137, 0, 0, 0, 11, 73, 68, 65, 84, 120, 156, 99, 248, 15, 0, 1, 1, 1, 0, 24,
    221, 142, 175, 0, 0, 0, 0, 73, 69, 78, 68, 174, 66, 96, 130,
];

#[derive(Debug, Default)]
pub struct DummyProvider {
    pub model_name: String,
    pub credentials: DummyCredentials,
}

impl DummyProvider {
    pub fn new(
        model_name: String,
        api_key_location: Option<CredentialLocation>,
    ) -> Result<Self, Error> {
        let api_key_location = api_key_location.unwrap_or(default_api_key_location());
        match api_key_location {
            CredentialLocation::Dynamic(key_name) => Ok(DummyProvider {
                model_name,
                credentials: DummyCredentials::Dynamic(key_name),
            }),
            CredentialLocation::None => Ok(DummyProvider {
                model_name,
                credentials: DummyCredentials::None,
            }),
            _ => Err(Error::new(ErrorDetails::Config {
                message: "Invalid api_key_location for Dummy provider".to_string(),
            })),
        }
    }

    pub fn model_name(&self) -> &str {
        &self.model_name
    }

    /// Helper function to generate dummy image data based on response format
    fn generate_dummy_image_data(
        &self,
        response_format: Option<&crate::images::ImageResponseFormat>,
        url_type: &str,
        request_id: &Uuid,
        index: Option<usize>,
    ) -> crate::images::ImageData {
        match response_format {
            Some(crate::images::ImageResponseFormat::B64Json) => {
                let base64_data = base64::prelude::BASE64_STANDARD.encode(DUMMY_PNG_BYTES);
                crate::images::ImageData {
                    url: None,
                    b64_json: Some(base64_data),
                    revised_prompt: None,
                }
            }
            _ => {
                let url = match index {
                    Some(i) => format!("https://example.com/dummy-{url_type}-{request_id}-{i}.png"),
                    None => format!("https://example.com/dummy-{url_type}-{request_id}.png"),
                };
                crate::images::ImageData {
                    url: Some(url),
                    b64_json: None,
                    revised_prompt: None,
                }
            }
        }
    }
}

fn default_api_key_location() -> CredentialLocation {
    CredentialLocation::None
}

#[derive(Debug, Default)]
pub enum DummyCredentials {
    #[default]
    None,
    Dynamic(String),
}

impl DummyCredentials {
    pub fn get_api_key<'a>(
        &'a self,
        dynamic_api_keys: &'a InferenceCredentials,
    ) -> Result<Option<&'a SecretString>, Error> {
        match self {
            DummyCredentials::None => Ok(None),
            DummyCredentials::Dynamic(key_name) => {
                Some(dynamic_api_keys.get(key_name).ok_or_else(|| {
                    ErrorDetails::ApiKeyMissing {
                        provider_name: PROVIDER_NAME.to_string(),
                    }
                    .into()
                }))
                .transpose()
            }
        }
    }
}

pub static DUMMY_INFER_RESPONSE_CONTENT: &str = "Megumin gleefully chanted her spell, unleashing a thunderous explosion that lit up the sky and left a massive crater in its wake.";
pub static DUMMY_INFER_RESPONSE_RAW: &str = r#"{
  "id": "id",
  "object": "text.completion",
  "created": 1618870400,
  "model": "text-davinci-002",
  "choices": [
    {
      "text": "Megumin gleefully chanted her spell, unleashing a thunderous explosion that lit up the sky and left a massive crater in its wake.",
      "index": 0,
      "logprobs": null,
      "finish_reason": null
    }
  ]
}"#;

pub static ALTERNATE_INFER_RESPONSE_CONTENT: &str =
    "Megumin chanted her spell, but instead of an explosion, a gentle rain began to fall.";

lazy_static! {
    pub static ref DUMMY_TOOL_RESPONSE: Value = json!({"location": "Brooklyn", "units": "celsius"});
    // This is the same as DUMMY_TOOL_RESPONSE, but with the units capitalized
    // Since that field is an enum, this should fail validation
    pub static ref DUMMY_BAD_TOOL_RESPONSE: Value = json!({"location": "Brooklyn", "units": "Celsius"});
    static ref FLAKY_COUNTERS: Mutex<HashMap<String, u16>> = Mutex::new(HashMap::new());
}
pub static DUMMY_JSON_RESPONSE_RAW: &str = r#"{"answer":"Hello"}"#;
pub static DUMMY_JSON_GOODBYE_RESPONSE_RAW: &str = r#"{"answer":"Goodbye"}"#;
pub static DUMMY_JSON_RESPONSE_RAW_DIFF_SCHEMA: &str = r#"{"response":"Hello"}"#;
pub static DUMMY_JSON_COT_RESPONSE_RAW: &str =
    r#"{"thinking":"hmmm", "response": {"answer":"tokyo!"}}"#;
pub static DUMMY_INFER_USAGE: Usage = Usage {
    input_tokens: 10,
    output_tokens: 10,
};
pub static DUMMY_STREAMING_THINKING: [&str; 2] = ["hmmm", "hmmm"];
pub static DUMMY_STREAMING_RESPONSE: [&str; 16] = [
    "Wally,",
    " the",
    " golden",
    " retriever,",
    " wagged",
    " his",
    " tail",
    " excitedly",
    " as",
    " he",
    " devoured",
    " a",
    " slice",
    " of",
    " cheese",
    " pizza.",
];
pub static DUMMY_STREAMING_TOOL_RESPONSE: [&str; 5] = [
    r#"{"location""#,
    r#":"Brooklyn""#,
    r#","units""#,
    r#":"celsius"#,
    r#""}"#,
];

pub static DUMMY_STREAMING_JSON_RESPONSE: [&str; 5] =
    [r#"{"name""#, r#":"John""#, r#","age""#, r#":30"#, r#"}"#];

pub static DUMMY_RAW_REQUEST: &str = "raw request";

impl InferenceProvider for DummyProvider {
    async fn infer<'a>(
        &'a self,
        ModelProviderRequest {
            request,
            provider_name: _,
            model_name: _,
        }: ModelProviderRequest<'a>,
        _http_client: &'a reqwest::Client,
        dynamic_api_keys: &'a InferenceCredentials,
        _model_provider: &'a ModelProvider,
    ) -> Result<ProviderInferenceResponse, Error> {
        if self.model_name == "slow" {
            tokio::time::sleep(Duration::from_secs(5)).await;
        }

        // Check for flaky models
        if self.model_name.starts_with("flaky_") {
            #[expect(clippy::expect_used)]
            let mut counters = FLAKY_COUNTERS
                .lock()
                .expect("FLAKY_COUNTERS mutex is poisoned");
            let counter = counters.entry(self.model_name.clone()).or_insert(0);
            *counter += 1;

            // Fail on even-numbered calls
            if *counter % 2 == 0 {
                return Err(ErrorDetails::InferenceClient {
                    raw_request: Some("raw request".to_string()),
                    raw_response: None,
                    message: format!(
                        "Flaky model '{}' failed on call number {}",
                        self.model_name, *counter
                    ),
                    status_code: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                }
                .into());
            }
        }

        if self.model_name.starts_with("error") {
            return Err(ErrorDetails::InferenceClient {
                message: format!(
                    "Error sending request to Dummy provider for model '{}'.",
                    self.model_name
                ),
                raw_request: Some("raw request".to_string()),
                raw_response: None,
                status_code: None,
                provider_type: PROVIDER_TYPE.to_string(),
            }
            .into());
        }
        if self.model_name == "multiple-text-blocks" {
            // The first message must have 2 text blocks or we error
            let first_message = &request.messages[0];
            let first_message_text_content = first_message
                .content
                .iter()
                .filter(|block| matches!(block, ContentBlock::Text(_)))
                .collect::<Vec<_>>();
            if first_message_text_content.len() != 2 {
                return Err(ErrorDetails::InferenceClient {
                    message: "First message must have exactly two text blocks".to_string(),
                    raw_request: Some("raw request".to_string()),
                    raw_response: None,
                    status_code: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                }
                .into());
            }
        }

        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        if self.model_name == "test_key" {
            if let Some(api_key) = api_key {
                if api_key.expose_secret() != "good_key" {
                    return Err(ErrorDetails::InferenceClient {
                        message: "Invalid API key for Dummy provider".to_string(),
                        raw_request: Some("raw request".to_string()),
                        raw_response: None,
                        status_code: None,
                        provider_type: PROVIDER_TYPE.to_string(),
                    }
                    .into());
                }
            }
        }
        let id = Uuid::now_v7();
        let created = current_timestamp();
        let content = match self.model_name.as_str() {
            "null" => vec![],
            "tool" => vec![ContentBlockOutput::ToolCall(ToolCall {
                name: "get_temperature".to_string(),
                #[expect(clippy::unwrap_used)]
                arguments: serde_json::to_string(&*DUMMY_TOOL_RESPONSE).unwrap(),
                id: "0".to_string(),
            })],
            "reasoner" => vec![
                ContentBlockOutput::Thought(Thought {
                    text: "hmmm".to_string(),
                    signature: None,
                }),
                ContentBlockOutput::Text(Text {
                    text: DUMMY_INFER_RESPONSE_CONTENT.to_string(),
                }),
            ],
            "json_reasoner" => vec![
                ContentBlockOutput::Thought(Thought {
                    text: "hmmm".to_string(),
                    signature: None,
                }),
                ContentBlockOutput::Text(Text {
                    text: DUMMY_JSON_RESPONSE_RAW.to_string(),
                }),
            ],
            "bad_tool" => vec![ContentBlockOutput::ToolCall(ToolCall {
                name: "get_temperature".to_string(),
                #[expect(clippy::unwrap_used)]
                arguments: serde_json::to_string(&*DUMMY_BAD_TOOL_RESPONSE).unwrap(),
                id: "0".to_string(),
            })],
            "json" => vec![DUMMY_JSON_RESPONSE_RAW.to_string().into()],
            "json_goodbye" => vec![DUMMY_JSON_GOODBYE_RESPONSE_RAW.to_string().into()],
            "json_cot" => vec![DUMMY_JSON_COT_RESPONSE_RAW.to_string().into()],
            "json_diff_schema" => vec![DUMMY_JSON_RESPONSE_RAW_DIFF_SCHEMA.to_string().into()],
            "json_beatles_1" => vec![r#"{"names":["John", "George"]}"#.to_string().into()],
            "json_beatles_2" => vec![r#"{"names":["Paul", "Ringo"]}"#.to_string().into()],
            "best_of_n_0" => {
                vec![r#"{"thinking": "hmmm", "answer_choice": 0}"#.to_string().into()]
            }
            "best_of_n_1" => {
                vec![r#"{"thinking": "hmmm", "answer_choice": 1}"#.to_string().into()]
            }
            "best_of_n_big" => {
                vec![r#"{"thinking": "hmmm", "answer_choice": 100}"#.to_string().into()]
            }
            "flaky_best_of_n_judge" => {
                vec![r#"{"thinking": "hmmm", "answer_choice": 0}"#.to_string().into()]
            }
            "random_answer" => {
                vec![ContentBlockOutput::Text(Text {
                    text: serde_json::json!({
                        "answer": Uuid::now_v7().to_string()
                    })
                    .to_string(),
                })]
            }
            "alternate" => vec![ALTERNATE_INFER_RESPONSE_CONTENT.to_string().into()],
            "echo_extra_info" => {
                vec![ContentBlockOutput::Text(Text {
                    text: json!({
                        "extra_body": request.extra_body,
                        "extra_headers": request.extra_headers,
                    })
                    .to_string(),
                })]
            }
            "echo_request_messages" => vec![ContentBlockOutput::Text(Text {
                text: json!({
                    "system": request.system,
                    "messages": request.messages,
                })
                .to_string(),
            })],
            "extract_images" => {
                let images: Vec<_> = request
                    .messages
                    .iter()
                    .flat_map(|m| {
                        m.content.iter().flat_map(|block| {
                            if let ContentBlock::File(image) = block {
                                Some(image.clone())
                            } else {
                                None
                            }
                        })
                    })
                    .collect();
                vec![ContentBlockOutput::Text(Text {
                    text: serde_json::to_string(&images).map_err(|e| {
                        ErrorDetails::Serialization {
                            message: format!("Failed to serialize collected images: {e:?}"),
                        }
                    })?,
                })]
            }
            "require_pdf" => {
                let files: Vec<_> = request
                    .messages
                    .iter()
                    .flat_map(|m| {
                        m.content.iter().flat_map(|block| {
                            if let ContentBlock::File(file) = block {
                                Some(file.clone())
                            } else {
                                None
                            }
                        })
                    })
                    .collect();
                let mut found_pdf = false;
                for file in &files {
                    if file.file.mime_type == FileKind::Pdf {
                        found_pdf = true;
                    }
                }
                if found_pdf {
                    vec![ContentBlockOutput::Text(Text {
                        text: serde_json::to_string(&files).map_err(|e| {
                            ErrorDetails::Serialization {
                                message: format!("Failed to serialize collected files: {e:?}"),
                            }
                        })?,
                    })]
                } else {
                    return Err(ErrorDetails::InferenceClient {
                        message: "PDF must be provided for require_pdf model".to_string(),
                        raw_request: Some("raw request".to_string()),
                        raw_response: None,
                        status_code: None,
                        provider_type: PROVIDER_TYPE.to_string(),
                    }
                    .into());
                }
            }
            "llm_judge::true" => vec![r#"{"score": true}"#.to_string().into()],
            "llm_judge::false" => vec![r#"{"score": false}"#.to_string().into()],
            "llm_judge::zero" => vec![r#"{"score": 0}"#.to_string().into()],
            "llm_judge::one" => vec![r#"{"score": 1}"#.to_string().into()],
            "llm_judge::error" => {
                return Err(ErrorDetails::InferenceClient {
                    message: "Dummy error in inference".to_string(),
                    raw_request: Some("raw request".to_string()),
                    raw_response: None,
                    status_code: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                }
                .into());
            }
            _ => vec![DUMMY_INFER_RESPONSE_CONTENT.to_string().into()],
        };
        let raw_request = DUMMY_RAW_REQUEST.to_string();
        let raw_response = match self.model_name.as_str() {
            #[expect(clippy::unwrap_used)]
            "tool" => serde_json::to_string(&*DUMMY_TOOL_RESPONSE).unwrap(),
            "json" => DUMMY_JSON_RESPONSE_RAW.to_string(),
            "json_goodbye" => DUMMY_JSON_GOODBYE_RESPONSE_RAW.to_string(),
            "json_cot" => DUMMY_JSON_COT_RESPONSE_RAW.to_string(),
            #[expect(clippy::unwrap_used)]
            "bad_tool" => serde_json::to_string(&*DUMMY_BAD_TOOL_RESPONSE).unwrap(),
            "best_of_n_0" => r#"{"thinking": "hmmm", "answer_choice": 0}"#.to_string(),
            "best_of_n_1" => r#"{"thinking": "hmmm", "answer_choice": 1}"#.to_string(),
            "best_of_n_big" => r#"{"thinking": "hmmm", "answer_choice": 100}"#.to_string(),
            _ => DUMMY_INFER_RESPONSE_RAW.to_string(),
        };
        let usage = match self.model_name.as_str() {
            "input_tokens_zero" => Usage {
                input_tokens: 0,
                output_tokens: 10,
            },
            "output_tokens_zero" => Usage {
                input_tokens: 10,
                output_tokens: 0,
            },
            "input_tokens_output_tokens_zero" => Usage {
                input_tokens: 0,
                output_tokens: 0,
            },
            _ => DUMMY_INFER_USAGE.clone(),
        };
        let latency = Latency::NonStreaming {
            response_time: Duration::from_millis(100),
        };
        let system = request.system.clone();
        let input_messages = request.messages.clone();
        let finish_reason = match self.model_name.contains("tool") {
            true => Some(FinishReason::ToolCall),
            false => Some(FinishReason::Stop),
        };
        Ok(ProviderInferenceResponse {
            id,
            created,
            output: content,
            raw_request,
            raw_response,
            usage,
            latency,
            system,
            input_messages,
            finish_reason,
        })
    }

    async fn infer_stream<'a>(
        &'a self,
        ModelProviderRequest {
            request: _,
            provider_name: _,
            model_name: _,
        }: ModelProviderRequest<'a>,
        _http_client: &'a reqwest::Client,
        _dynamic_api_keys: &'a InferenceCredentials,
        _model_provider: &'a ModelProvider,
    ) -> Result<(PeekableProviderInferenceResponseStream, String), Error> {
        if self.model_name == "slow" {
            tokio::time::sleep(Duration::from_secs(5)).await;
        }
        // Check for flaky models
        if self.model_name.starts_with("flaky_") {
            #[expect(clippy::expect_used)]
            let mut counters = FLAKY_COUNTERS
                .lock()
                .expect("FLAKY_COUNTERS mutex is poisoned");
            let counter = counters.entry(self.model_name.clone()).or_insert(0);
            *counter += 1;

            // Fail on even-numbered calls
            if *counter % 2 == 0 {
                return Err(ErrorDetails::InferenceClient {
                    raw_request: Some("raw request".to_string()),
                    raw_response: None,
                    message: format!(
                        "Flaky model '{}' failed on call number {}",
                        self.model_name, *counter
                    ),
                    status_code: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                }
                .into());
            }
        }
        if self.model_name == "reasoner" {
            return create_streaming_reasoning_response(
                DUMMY_STREAMING_THINKING.to_vec(),
                DUMMY_STREAMING_RESPONSE.to_vec(),
            )
            .await;
        }
        if self.model_name == "json_reasoner" {
            return create_streaming_reasoning_response(
                DUMMY_STREAMING_THINKING.to_vec(),
                DUMMY_STREAMING_JSON_RESPONSE.to_vec(),
            )
            .await;
        }

        if self.model_name.starts_with("error") {
            return Err(ErrorDetails::InferenceClient {
                message: format!(
                    "Error sending request to Dummy provider for model '{}'.",
                    self.model_name
                ),
                raw_request: Some("raw request".to_string()),
                raw_response: None,
                status_code: None,
                provider_type: PROVIDER_TYPE.to_string(),
            }
            .into());
        }

        let err_in_stream = self.model_name == "err_in_stream";

        let created = current_timestamp();

        let (content_chunks, is_tool_call) = match self.model_name.as_str() {
            "tool" => (DUMMY_STREAMING_TOOL_RESPONSE.to_vec(), true),
            "reasoner" => (DUMMY_STREAMING_RESPONSE.to_vec(), false),
            _ => (DUMMY_STREAMING_RESPONSE.to_vec(), false),
        };

        let total_tokens = content_chunks.len() as u32;
        let content_chunk_len = content_chunks.len();
        let finish_reason = match is_tool_call {
            true => Some(FinishReason::ToolCall),
            false => Some(FinishReason::Stop),
        };
        let stream: ProviderInferenceResponseStreamInner = Box::pin(
            tokio_stream::iter(content_chunks.into_iter().enumerate())
                .map(move |(i, chunk)| {
                    if err_in_stream && i == 3 {
                        return Err(Error::new(ErrorDetails::InferenceClient {
                            message: "Dummy error in stream".to_string(),
                            raw_request: Some("raw request".to_string()),
                            raw_response: None,
                            status_code: None,
                            provider_type: PROVIDER_TYPE.to_string(),
                        }));
                    }
                    Ok(ProviderInferenceResponseChunk {
                        created,
                        content: vec![if is_tool_call {
                            ContentBlockChunk::ToolCall(ToolCallChunk {
                                id: "0".to_string(),
                                raw_name: "get_temperature".to_string(),
                                raw_arguments: chunk.to_string(),
                            })
                        } else {
                            ContentBlockChunk::Text(crate::inference::types::TextChunk {
                                text: chunk.to_string(),
                                id: "0".to_string(),
                            })
                        }],
                        usage: None,
                        finish_reason: None,
                        raw_response: chunk.to_string(),
                        latency: Duration::from_millis(50 + 10 * (i as u64 + 1)),
                    })
                })
                .chain(tokio_stream::once(Ok(ProviderInferenceResponseChunk {
                    created,
                    content: vec![],
                    usage: Some(crate::inference::types::Usage {
                        input_tokens: 10,
                        output_tokens: total_tokens,
                    }),
                    finish_reason,
                    raw_response: "".to_string(),
                    latency: Duration::from_millis(50 + 10 * (content_chunk_len as u64)),
                })))
                .throttle(std::time::Duration::from_millis(10)),
        );

        Ok((
            // We need this verbose path to avoid using `tokio_stream::StreamExt::peekable`,
            // which produces a different types
            futures::stream::StreamExt::peekable(stream),
            DUMMY_RAW_REQUEST.to_string(),
        ))
    }

    async fn start_batch_inference<'a>(
        &'a self,
        requests: &'a [ModelInferenceRequest<'_>],
        _client: &'a reqwest::Client,
        _dynamic_api_keys: &'a InferenceCredentials,
    ) -> Result<StartBatchProviderInferenceResponse, Error> {
        let file_id = Uuid::now_v7();
        let batch_id = Uuid::now_v7();
        let raw_requests: Vec<String> =
            requests.iter().map(|_| "raw_request".to_string()).collect();
        Ok(StartBatchProviderInferenceResponse {
            batch_id,
            batch_params: json!({"file_id": file_id, "batch_id": batch_id}),
            status: BatchStatus::Pending,
            raw_requests,
            raw_request: "raw request".to_string(),
            raw_response: "raw response".to_string(),
            errors: vec![],
        })
    }

    async fn poll_batch_inference<'a>(
        &'a self,
        _batch_request: &'a BatchRequestRow<'a>,
        _http_client: &'a reqwest::Client,
        _dynamic_api_keys: &'a InferenceCredentials,
    ) -> Result<PollBatchInferenceResponse, Error> {
        Err(ErrorDetails::UnsupportedModelProviderForBatchInference {
            provider_type: "Dummy".to_string(),
        }
        .into())
    }
}
lazy_static! {
    static ref EMPTY_SECRET: SecretString = SecretString::from(String::new());
}

impl EmbeddingProvider for DummyProvider {
    async fn embed(
        &self,
        request: &EmbeddingRequest,
        _http_client: &reqwest::Client,
        _dynamic_api_keys: &InferenceCredentials,
    ) -> Result<EmbeddingProviderResponse, Error> {
        if self.model_name.starts_with("error") {
            return Err(ErrorDetails::InferenceClient {
                message: format!(
                    "Error sending request to Dummy provider for model '{}'.",
                    self.model_name
                ),
                raw_request: Some("raw request".to_string()),
                raw_response: None,
                status_code: None,
                provider_type: PROVIDER_TYPE.to_string(),
            }
            .into());
        }
        // Generate embeddings for each input
        let embeddings: Vec<Vec<f32>> = match &request.input {
            crate::embeddings::EmbeddingInput::Single(_) => vec![vec![0.0; 1536]],
            crate::embeddings::EmbeddingInput::Batch(texts) => {
                texts.iter().map(|_| vec![0.0; 1536]).collect()
            }
        };

        let raw_request = DUMMY_RAW_REQUEST.to_string();
        let raw_response = DUMMY_RAW_REQUEST.to_string();
        let usage = DUMMY_INFER_USAGE.clone();
        let latency = Latency::NonStreaming {
            response_time: Duration::from_millis(100),
        };

        Ok(EmbeddingProviderResponse::new(
            embeddings,
            request.input.clone(),
            raw_request,
            raw_response,
            usage,
            latency,
        ))
    }
}

async fn create_streaming_reasoning_response(
    thinking_chunks: Vec<&'static str>,
    response_chunks: Vec<&'static str>,
) -> Result<(PeekableProviderInferenceResponseStream, String), Error> {
    let thinking_chunks = thinking_chunks.into_iter().map(|chunk| {
        ContentBlockChunk::Thought(ThoughtChunk {
            text: Some(chunk.to_string()),
            signature: None,
            id: "0".to_string(),
        })
    });
    let response_chunks = response_chunks.into_iter().map(|chunk| {
        ContentBlockChunk::Text(TextChunk {
            text: chunk.to_string(),
            id: "0".to_string(),
        })
    });
    let num_chunks = thinking_chunks.len() + response_chunks.len();
    let created = current_timestamp();
    let chained = thinking_chunks
        .into_iter()
        .chain(response_chunks.into_iter());
    let stream = tokio_stream::iter(chained.enumerate())
        .map(move |(i, chunk)| {
            Ok(ProviderInferenceResponseChunk {
                created,
                content: vec![chunk],
                usage: None,
                raw_response: "".to_string(),
                latency: Duration::from_millis(50 + 10 * (i as u64 + 1)),
                finish_reason: None,
            })
        })
        .chain(tokio_stream::once(Ok(ProviderInferenceResponseChunk {
            created,
            content: vec![],
            usage: Some(crate::inference::types::Usage {
                input_tokens: 10,
                output_tokens: 10,
            }),
            finish_reason: Some(FinishReason::Stop),
            raw_response: "".to_string(),
            latency: Duration::from_millis(50 + 10 * (num_chunks as u64)),
        })))
        .throttle(std::time::Duration::from_millis(10));

    Ok((
        futures::stream::StreamExt::peekable(Box::pin(stream)),
        DUMMY_RAW_REQUEST.to_string(),
    ))
}

impl ModerationProvider for DummyProvider {
    async fn moderate(
        &self,
        request: &ModerationRequest,
        _client: &reqwest::Client,
        _dynamic_api_keys: &InferenceCredentials,
    ) -> Result<ModerationProviderResponse, Error> {
        // Create dummy moderation results based on the input
        let num_inputs = request.input.len();
        let mut results = Vec::with_capacity(num_inputs);

        for i in 0..num_inputs {
            let text = request.input.as_vec()[i];

            // Flag content that contains certain test keywords
            let flagged =
                text.contains("harmful") || text.contains("violent") || text.contains("hate");

            // Create dummy scores
            let mut categories = ModerationCategories::default();
            let mut category_scores = ModerationCategoryScores::default();

            if text.contains("hate") {
                categories.hate = true;
                category_scores.hate = 0.95;
            }
            if text.contains("violent") {
                categories.violence = true;
                category_scores.violence = 0.85;
            }
            if text.contains("harmful") {
                categories.self_harm = true;
                category_scores.self_harm = 0.75;
            }

            results.push(ModerationResult {
                flagged,
                categories,
                category_scores,
                category_applied_input_types: None,
                hallucination_details: None,
                ip_violation_details: None,
            });
        }

        let raw_response = serde_json::to_string(&json!({
            "id": "dummy-moderation-id",
            "model": self.model_name,
            "results": &results,
        }))
        .unwrap_or_default();

        let response = ModerationProviderResponse {
            id: Uuid::now_v7(),
            input: request.input.clone(),
            results,
            created: current_timestamp(),
            model: self.model_name.clone(),
            raw_request: serde_json::to_string(&json!({
                "input": request.input,
                "model": request.model,
            }))
            .unwrap_or_default(),
            raw_response,
            usage: Usage {
                input_tokens: 10 * num_inputs as u32,
                output_tokens: 5 * num_inputs as u32,
            },
            latency: Latency::NonStreaming {
                response_time: Duration::from_millis(50),
            },
        };

        Ok(response)
    }
}

impl crate::audio::AudioTranscriptionProvider for DummyProvider {
    async fn transcribe(
        &self,
        request: &crate::audio::AudioTranscriptionRequest,
        _client: &reqwest::Client,
        _dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::audio::AudioTranscriptionProviderResponse, Error> {
        let response = crate::audio::AudioTranscriptionProviderResponse {
            id: request.id,
            text: "This is a dummy transcription".to_string(),
            language: Some("en".to_string()),
            duration: Some(5.0),
            words: None,
            segments: None,
            created: current_timestamp(),
            raw_request: "dummy transcription request".to_string(),
            raw_response: "dummy transcription response".to_string(),
            usage: Usage {
                input_tokens: 10,
                output_tokens: 5,
            },
            latency: Latency::NonStreaming {
                response_time: Duration::from_millis(100),
            },
        };
        Ok(response)
    }
}

impl crate::audio::AudioTranslationProvider for DummyProvider {
    async fn translate(
        &self,
        request: &crate::audio::AudioTranslationRequest,
        _client: &reqwest::Client,
        _dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::audio::AudioTranslationProviderResponse, Error> {
        let response = crate::audio::AudioTranslationProviderResponse {
            id: request.id,
            text: "This is a dummy translation".to_string(),
            created: current_timestamp(),
            raw_request: "dummy translation request".to_string(),
            raw_response: "dummy translation response".to_string(),
            usage: Usage {
                input_tokens: 10,
                output_tokens: 5,
            },
            latency: Latency::NonStreaming {
                response_time: Duration::from_millis(100),
            },
        };
        Ok(response)
    }
}

impl crate::audio::TextToSpeechProvider for DummyProvider {
    async fn generate_speech(
        &self,
        request: &crate::audio::TextToSpeechRequest,
        _client: &reqwest::Client,
        _dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::audio::TextToSpeechProviderResponse, Error> {
        // Generate dummy audio data - just a small byte array
        let dummy_audio = vec![0u8; 1024]; // 1KB of dummy audio data

        let response = crate::audio::TextToSpeechProviderResponse {
            id: request.id,
            audio_data: dummy_audio,
            format: request
                .response_format
                .clone()
                .unwrap_or(crate::audio::AudioOutputFormat::Mp3),
            created: current_timestamp(),
            raw_request: "dummy tts request".to_string(),
            usage: Usage {
                input_tokens: request.input.len() as u32,
                output_tokens: 0,
            },
            latency: Latency::NonStreaming {
                response_time: Duration::from_millis(100),
            },
        };
        Ok(response)
    }
}

impl CompletionProvider for DummyProvider {
    async fn complete(
        &self,
        request: &CompletionRequest,
        _client: &reqwest::Client,
        _dynamic_api_keys: &InferenceCredentials,
    ) -> Result<CompletionProviderResponse, Error> {
        // Handle error models
        if self.model_name.starts_with("error") {
            return Err(ErrorDetails::InferenceClient {
                message: format!(
                    "Error sending request to Dummy provider for model '{}'.",
                    self.model_name
                ),
                raw_request: Some("raw request".to_string()),
                raw_response: None,
                status_code: None,
                provider_type: PROVIDER_TYPE.to_string(),
            }
            .into());
        }

        // Generate dummy completion response
        let text = "This is a dummy completion response.";
        let choice = CompletionChoice {
            text: text.to_string(),
            index: 0,
            logprobs: None,
            finish_reason: "stop".to_string(),
        };

        Ok(CompletionProviderResponse {
            id: request.id,
            created: current_timestamp(),
            model: request.model.clone(),
            choices: vec![choice],
            usage: Usage {
                input_tokens: 10,
                output_tokens: 10,
            },
            raw_request: "dummy completion request".to_string(),
            raw_response: text.to_string(),
            latency: Latency::NonStreaming {
                response_time: Duration::from_millis(100),
            },
        })
    }

    async fn complete_stream(
        &self,
        request: &CompletionRequest,
        _client: &reqwest::Client,
        _dynamic_api_keys: &InferenceCredentials,
    ) -> Result<(CompletionStream, String), Error> {
        // Handle error models
        if self.model_name.starts_with("error") {
            return Err(ErrorDetails::InferenceClient {
                message: format!(
                    "Error sending request to Dummy provider for model '{}'.",
                    self.model_name
                ),
                raw_request: Some("raw request".to_string()),
                raw_response: None,
                status_code: None,
                provider_type: PROVIDER_TYPE.to_string(),
            }
            .into());
        }

        // Stream dummy chunks
        let chunks = vec!["This ", "is ", "a ", "dummy ", "completion ", "stream."];
        let created = current_timestamp();
        let request_id = request.id.to_string();
        let model = request.model.to_string();

        let stream = tokio_stream::iter(chunks.into_iter().enumerate())
            .map(move |(i, chunk)| {
                Ok(CompletionChunk {
                    id: request_id.clone(),
                    object: "text_completion".to_string(),
                    created,
                    model: model.clone(),
                    choices: vec![CompletionChoiceChunk {
                        text: chunk.to_string(),
                        index: 0,
                        logprobs: None,
                        finish_reason: if i == 5 {
                            Some("stop".to_string())
                        } else {
                            None
                        },
                        extra: HashMap::new(),
                    }],
                    usage: None,
                    extra: HashMap::new(),
                })
            })
            .throttle(Duration::from_millis(10));

        Ok((
            Box::pin(stream) as CompletionStream,
            "dummy completion request".to_string(),
        ))
    }
}

impl crate::images::ImageGenerationProvider for DummyProvider {
    async fn generate_image(
        &self,
        request: &crate::images::ImageGenerationRequest,
        _client: &reqwest::Client,
        _dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::images::ImageGenerationProviderResponse, Error> {
        // Generate dummy image data - return dummy URLs or base64 depending on request
        let num_images = request.n.unwrap_or(1) as usize;
        let mut images = Vec::new();

        for _i in 0..num_images {
            let mut image_data = self.generate_dummy_image_data(
                request.response_format.as_ref(),
                "image",
                &request.id,
                None,
            );
            // Add revised prompt for generation if style is specified
            if request.response_format != Some(crate::images::ImageResponseFormat::B64Json) {
                image_data.revised_prompt = request
                    .style
                    .as_ref()
                    .map(|_| format!("Enhanced prompt: {}", request.prompt));
            }
            images.push(image_data);
        }

        let response = crate::images::ImageGenerationProviderResponse {
            id: request.id,
            created: current_timestamp(),
            data: images,
            raw_request: "dummy image generation request".to_string(),
            raw_response: "dummy image generation response".to_string(),
            usage: Usage {
                input_tokens: 0, // Images don't have token usage
                output_tokens: 0,
            },
            latency: Latency::NonStreaming {
                response_time: Duration::from_millis(200),
            },
        };
        Ok(response)
    }
}

impl crate::images::ImageEditProvider for DummyProvider {
    async fn edit_image(
        &self,
        request: &crate::images::ImageEditRequest,
        _client: &reqwest::Client,
        _dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::images::ImageEditProviderResponse, Error> {
        let num_images = request.n.unwrap_or(1) as usize;
        let mut images = Vec::new();

        for _i in 0..num_images {
            let image_data = self.generate_dummy_image_data(
                request.response_format.as_ref(),
                "edited-image",
                &request.id,
                None,
            );
            images.push(image_data);
        }

        let response = crate::images::ImageEditProviderResponse {
            id: request.id,
            created: current_timestamp(),
            data: images,
            raw_request: "dummy image edit request".to_string(),
            raw_response: "dummy image edit response".to_string(),
            usage: Usage {
                input_tokens: 0,
                output_tokens: 0,
            },
            latency: Latency::NonStreaming {
                response_time: Duration::from_millis(200),
            },
        };
        Ok(response)
    }
}

impl crate::images::ImageVariationProvider for DummyProvider {
    async fn create_image_variation(
        &self,
        request: &crate::images::ImageVariationRequest,
        _client: &reqwest::Client,
        _dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::images::ImageVariationProviderResponse, Error> {
        let num_images = request.n.unwrap_or(1) as usize;
        let mut images = Vec::new();

        for i in 0..num_images {
            let image_data = self.generate_dummy_image_data(
                request.response_format.as_ref(),
                "variation",
                &request.id,
                Some(i),
            );
            images.push(image_data);
        }

        let response = crate::images::ImageVariationProviderResponse {
            id: request.id,
            created: current_timestamp(),
            data: images,
            raw_request: "dummy image variation request".to_string(),
            raw_response: "dummy image variation response".to_string(),
            usage: Usage {
                input_tokens: 0,
                output_tokens: 0,
            },
            latency: Latency::NonStreaming {
                response_time: Duration::from_millis(200),
            },
        };
        Ok(response)
    }
}

#[async_trait::async_trait]
impl ResponseProvider for DummyProvider {
    async fn create_response(
        &self,
        request: &OpenAIResponseCreateParams,
        _client: &reqwest::Client,
        _dynamic_api_keys: &InferenceCredentials,
    ) -> Result<OpenAIResponse, Error> {
        // Generate a dummy response matching the actual OpenAI format
        let response = OpenAIResponse {
            id: format!("resp_{}", Uuid::now_v7()),
            object: "response".to_string(),
            created_at: current_timestamp() as i64,
            status: ResponseStatus::Completed,
            background: Some(false),
            error: None,
            incomplete_details: None,
            instructions: request.instructions.clone(),
            max_output_tokens: request.max_output_tokens,
            max_tool_calls: request.max_tool_calls,
            model: request
                .model
                .clone()
                .unwrap_or_else(|| "dummy-model".to_string()),
            output: vec![json!({
                "id": format!("msg_{}", Uuid::now_v7()),
                "type": "message",
                "status": "completed",
                "content": [{
                    "type": "output_text",
                    "annotations": [],
                    "logprobs": [],
                    "text": "This is a dummy response from the Dummy provider."
                }],
                "role": "assistant"
            })],
            parallel_tool_calls: request.parallel_tool_calls,
            previous_response_id: request.previous_response_id.clone(),
            prompt: request.prompt.clone(),
            reasoning: Some(json!({
                "effort": null,
                "summary": null
            })),
            service_tier: request.service_tier.clone().or(Some("default".to_string())),
            store: request.store,
            temperature: request.temperature.or(Some(0.25)),
            text: Some(json!({
                "format": {
                    "type": "text"
                }
            })),
            tool_choice: request.tool_choice.clone().or(Some(json!("auto"))),
            tools: request.tools.clone().or(Some(vec![])),
            top_logprobs: Some(0),
            top_p: Some(1.0),
            truncation: Some(json!("disabled")),
            usage: Some(ResponseUsage {
                input_tokens: 10,
                input_tokens_details: Some(json!({
                    "cached_tokens": 0
                })),
                output_tokens: Some(15),
                output_tokens_details: Some(json!({
                    "reasoning_tokens": 0
                })),
                total_tokens: 25,
            }),
            user: request.user.clone(),
            metadata: request.metadata.clone().or(Some(HashMap::new())),
        };

        Ok(response)
    }

    async fn stream_response(
        &self,
        _request: &OpenAIResponseCreateParams,
        _client: &reqwest::Client,
        _dynamic_api_keys: &InferenceCredentials,
    ) -> Result<
        Box<dyn futures::Stream<Item = Result<ResponseStreamEvent, Error>> + Send + Unpin>,
        Error,
    > {
        let events = vec![
            ResponseStreamEvent {
                event: "response.created".to_string(),
                data: json!({
                    "id": format!("resp_{}", Uuid::now_v7()),
                    "status": "in_progress"
                }),
            },
            ResponseStreamEvent {
                event: "content_block.start".to_string(),
                data: json!({
                    "type": "text",
                    "text": ""
                }),
            },
            ResponseStreamEvent {
                event: "content_block.delta".to_string(),
                data: json!({
                    "text": "This is a "
                }),
            },
            ResponseStreamEvent {
                event: "content_block.delta".to_string(),
                data: json!({
                    "text": "dummy streaming response."
                }),
            },
            ResponseStreamEvent {
                event: "content_block.stop".to_string(),
                data: json!({}),
            },
            ResponseStreamEvent {
                event: "response.done".to_string(),
                data: json!({
                    "status": "completed",
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "total_tokens": 15
                    }
                }),
            },
        ];

        // Create a stream without throttle to avoid Unpin issues
        let stream = tokio_stream::iter(events.into_iter().map(Ok));

        Ok(Box::new(stream)
            as Box<
                dyn futures::Stream<Item = Result<ResponseStreamEvent, Error>> + Send + Unpin,
            >)
    }

    async fn retrieve_response(
        &self,
        response_id: &str,
        _client: &reqwest::Client,
        _dynamic_api_keys: &InferenceCredentials,
    ) -> Result<OpenAIResponse, Error> {
        // Return a dummy response for the given ID
        Ok(OpenAIResponse {
            id: response_id.to_string(),
            object: "response".to_string(),
            created_at: current_timestamp() as i64,
            status: ResponseStatus::Completed,
            background: Some(false),
            error: None,
            incomplete_details: None,
            instructions: Some(json!("You are a helpful assistant.")),
            max_output_tokens: Some(1000),
            max_tool_calls: None,
            model: "dummy-model".to_string(),
            output: vec![json!({
                "type": "text",
                "text": "This is a retrieved dummy response."
            })],
            parallel_tool_calls: None,
            previous_response_id: None,
            prompt: None,
            reasoning: None,
            service_tier: Some("default".to_string()),
            store: Some(true),
            temperature: Some(0.7),
            text: None,
            tool_choice: None,
            tools: None,
            top_logprobs: None,
            top_p: None,
            truncation: None,
            usage: Some(ResponseUsage {
                input_tokens: 10,
                input_tokens_details: None,
                output_tokens: Some(15),
                output_tokens_details: None,
                total_tokens: 25,
            }),
            user: None,
            metadata: Some(HashMap::new()),
        })
    }

    async fn delete_response(
        &self,
        response_id: &str,
        _client: &reqwest::Client,
        _dynamic_api_keys: &InferenceCredentials,
    ) -> Result<serde_json::Value, Error> {
        // Return a success message for deletion
        Ok(json!({
            "id": response_id,
            "object": "response.deleted",
            "deleted": true
        }))
    }

    async fn cancel_response(
        &self,
        response_id: &str,
        _client: &reqwest::Client,
        _dynamic_api_keys: &InferenceCredentials,
    ) -> Result<OpenAIResponse, Error> {
        // Return a cancelled response
        Ok(OpenAIResponse {
            id: response_id.to_string(),
            object: "response".to_string(),
            created_at: current_timestamp() as i64,
            status: ResponseStatus::Failed,
            background: Some(false),
            error: Some(ResponseError {
                code: "cancelled".to_string(),
                message: "Response was cancelled".to_string(),
            }),
            incomplete_details: None,
            instructions: Some(json!("You are a helpful assistant.")),
            max_output_tokens: Some(1000),
            max_tool_calls: None,
            model: "dummy-model".to_string(),
            output: vec![],
            parallel_tool_calls: None,
            previous_response_id: None,
            prompt: None,
            reasoning: None,
            service_tier: Some("default".to_string()),
            store: Some(true),
            temperature: Some(0.7),
            text: None,
            tool_choice: None,
            tools: None,
            top_logprobs: None,
            top_p: None,
            truncation: None,
            usage: Some(ResponseUsage {
                input_tokens: 10,
                input_tokens_details: None,
                output_tokens: Some(0),
                output_tokens_details: None,
                total_tokens: 10,
            }),
            user: None,
            metadata: Some(HashMap::new()),
        })
    }

    async fn list_response_input_items(
        &self,
        response_id: &str,
        _client: &reqwest::Client,
        _dynamic_api_keys: &InferenceCredentials,
    ) -> Result<ResponseInputItemsList, Error> {
        // Return dummy input items
        Ok(ResponseInputItemsList {
            data: vec![
                json!({
                    "id": format!("item_1_{response_id}"),
                    "type": "text",
                    "text": "First input item"
                }),
                json!({
                    "id": format!("item_2_{response_id}"),
                    "type": "text",
                    "text": "Second input item"
                }),
            ],
            has_more: false,
            first_id: Some(format!("item_1_{response_id}")),
            last_id: Some(format!("item_2_{response_id}")),
        })
    }
}

// Implement BatchProvider for testing purposes
#[async_trait::async_trait]
impl crate::inference::providers::batch::BatchProvider for DummyProvider {
    async fn upload_file(
        &self,
        content: Vec<u8>,
        filename: String,
        purpose: String,
        _client: &reqwest::Client,
        _api_keys: &InferenceCredentials,
    ) -> Result<crate::openai_batch::OpenAIFileObject, Error> {
        // Return a dummy file object
        Ok(crate::openai_batch::OpenAIFileObject {
            id: format!("file-{}", Uuid::now_v7()),
            object: "file".to_string(),
            bytes: content.len() as i64,
            created_at: current_timestamp() as i64,
            filename,
            purpose,
            status: Some("processed".to_string()),
            status_details: None,
        })
    }

    async fn get_file(
        &self,
        file_id: &str,
        _client: &reqwest::Client,
        _api_keys: &InferenceCredentials,
    ) -> Result<crate::openai_batch::OpenAIFileObject, Error> {
        // Return a dummy file object
        Ok(crate::openai_batch::OpenAIFileObject {
            id: file_id.to_string(),
            object: "file".to_string(),
            bytes: 1024,
            created_at: current_timestamp() as i64,
            filename: "dummy_file.jsonl".to_string(),
            purpose: "batch".to_string(),
            status: Some("processed".to_string()),
            status_details: None,
        })
    }

    async fn get_file_content(
        &self,
        _file_id: &str,
        _client: &reqwest::Client,
        _api_keys: &InferenceCredentials,
    ) -> Result<Vec<u8>, Error> {
        // Return dummy JSONL content for batch files
        let jsonl_content = r#"{"custom_id": "req-1", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Hello"}]}}
{"custom_id": "req-2", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "World"}]}}"#;
        Ok(jsonl_content.as_bytes().to_vec())
    }

    async fn delete_file(
        &self,
        file_id: &str,
        _client: &reqwest::Client,
        _api_keys: &InferenceCredentials,
    ) -> Result<crate::openai_batch::OpenAIFileObject, Error> {
        // Return a dummy deleted file object
        Ok(crate::openai_batch::OpenAIFileObject {
            id: file_id.to_string(),
            object: "file".to_string(),
            bytes: 0,
            created_at: current_timestamp() as i64,
            filename: "deleted_file.jsonl".to_string(),
            purpose: "batch".to_string(),
            status: Some("deleted".to_string()),
            status_details: None,
        })
    }

    async fn create_batch(
        &self,
        input_file_id: String,
        endpoint: String,
        completion_window: String,
        metadata: Option<std::collections::HashMap<String, String>>,
        _client: &reqwest::Client,
        _api_keys: &InferenceCredentials,
    ) -> Result<crate::openai_batch::OpenAIBatchObject, Error> {
        // Return a dummy batch object
        Ok(crate::openai_batch::OpenAIBatchObject {
            id: format!("batch_{}", Uuid::now_v7()),
            object: "batch".to_string(),
            endpoint,
            errors: None,
            input_file_id,
            completion_window,
            status: crate::openai_batch::OpenAIBatchStatus::Validating,
            output_file_id: None,
            error_file_id: None,
            created_at: current_timestamp() as i64,
            in_progress_at: None,
            expires_at: Some(current_timestamp() as i64 + 86400),
            finalizing_at: None,
            completed_at: None,
            failed_at: None,
            expired_at: None,
            cancelling_at: None,
            cancelled_at: None,
            request_counts: crate::openai_batch::RequestCounts {
                total: 0,
                completed: 0,
                failed: 0,
            },
            metadata,
        })
    }

    async fn get_batch(
        &self,
        batch_id: &str,
        _client: &reqwest::Client,
        _api_keys: &InferenceCredentials,
    ) -> Result<crate::openai_batch::OpenAIBatchObject, Error> {
        // Return a dummy batch object
        Ok(crate::openai_batch::OpenAIBatchObject {
            id: batch_id.to_string(),
            object: "batch".to_string(),
            endpoint: "/v1/chat/completions".to_string(),
            errors: None,
            input_file_id: "file-123".to_string(),
            completion_window: "24h".to_string(),
            status: crate::openai_batch::OpenAIBatchStatus::Completed,
            output_file_id: Some("file-456".to_string()),
            error_file_id: None,
            created_at: current_timestamp() as i64,
            in_progress_at: Some(current_timestamp() as i64),
            expires_at: Some(current_timestamp() as i64 + 86400),
            finalizing_at: Some(current_timestamp() as i64),
            completed_at: Some(current_timestamp() as i64),
            failed_at: None,
            expired_at: None,
            cancelling_at: None,
            cancelled_at: None,
            request_counts: crate::openai_batch::RequestCounts {
                total: 1,
                completed: 1,
                failed: 0,
            },
            metadata: None,
        })
    }

    async fn list_batches(
        &self,
        _params: crate::openai_batch::ListBatchesParams,
        _client: &reqwest::Client,
        _api_keys: &InferenceCredentials,
    ) -> Result<crate::openai_batch::ListBatchesResponse, Error> {
        // Return a dummy list response
        Ok(crate::openai_batch::ListBatchesResponse {
            object: "list".to_string(),
            data: vec![],
            first_id: None,
            last_id: None,
            has_more: false,
        })
    }

    async fn cancel_batch(
        &self,
        batch_id: &str,
        _client: &reqwest::Client,
        _api_keys: &InferenceCredentials,
    ) -> Result<crate::openai_batch::OpenAIBatchObject, Error> {
        // Return a dummy cancelled batch object
        Ok(crate::openai_batch::OpenAIBatchObject {
            id: batch_id.to_string(),
            object: "batch".to_string(),
            endpoint: "/v1/chat/completions".to_string(),
            errors: None,
            input_file_id: "file-123".to_string(),
            completion_window: "24h".to_string(),
            status: crate::openai_batch::OpenAIBatchStatus::Cancelled,
            output_file_id: None,
            error_file_id: None,
            created_at: current_timestamp() as i64,
            in_progress_at: Some(current_timestamp() as i64),
            expires_at: Some(current_timestamp() as i64 + 86400),
            finalizing_at: None,
            completed_at: None,
            failed_at: None,
            expired_at: None,
            cancelling_at: Some(current_timestamp() as i64),
            cancelled_at: Some(current_timestamp() as i64),
            request_counts: crate::openai_batch::RequestCounts {
                total: 1,
                completed: 0,
                failed: 0,
            },
            metadata: None,
        })
    }
}

#[async_trait::async_trait]
impl crate::realtime::RealtimeSessionProvider for DummyProvider {
    async fn create_session(
        &self,
        request: &crate::realtime::RealtimeSessionRequest,
        _client: &reqwest::Client,
        _dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::realtime::RealtimeSessionResponse, Error> {
        use crate::inference::types::current_timestamp;
        use uuid::Uuid;

        let session_id = format!("sess_{}", Uuid::now_v7().to_string().replace('-', ""));
        let now = current_timestamp() as i64;
        let expires_at = now + 60; // 1 minute expiration
        let client_secret = {
            use rand::Rng;
            let mut rng = rand::rng();
            let random_bytes: [u8; 16] = rng.random();
            format!("eph_dummy_{}", hex::encode(random_bytes))
        };

        let response = crate::realtime::RealtimeSessionResponse {
            id: session_id,
            object: "realtime.session".to_string(),
            model: request.model.clone(),
            expires_at,
            client_secret: crate::realtime::ClientSecret {
                value: client_secret,
                expires_at,
            },
            voice: request.voice.clone(),
            input_audio_format: request.input_audio_format.clone(),
            output_audio_format: request.output_audio_format.clone(),
            input_audio_noise_reduction: request.input_audio_noise_reduction,
            temperature: request.temperature,
            max_response_output_tokens: request.max_response_output_tokens.clone(),
            modalities: request.modalities.clone(),
            instructions: request.instructions.clone(),
            turn_detection: request.turn_detection.clone(),
            tools: request.tools.clone(),
            tool_choice: request.tool_choice.clone(),
            input_audio_transcription: request.input_audio_transcription.clone(),
            include: request.include.clone(),
            speed: request.speed,
            tracing: request.tracing.clone(),
        };
        Ok(response)
    }
}

#[async_trait::async_trait]
impl crate::realtime::RealtimeTranscriptionProvider for DummyProvider {
    async fn create_transcription_session(
        &self,
        request: &crate::realtime::RealtimeTranscriptionRequest,
        _client: &reqwest::Client,
        _dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::realtime::RealtimeTranscriptionResponse, Error> {
        use crate::inference::types::current_timestamp;
        use uuid::Uuid;

        let session_id = format!("sess_{}", Uuid::now_v7().to_string().replace('-', ""));
        let now = current_timestamp() as i64;
        let expires_at = now + 60; // 1 minute expiration
        let client_secret = {
            use rand::Rng;
            let mut rng = rand::rng();
            let random_bytes: [u8; 16] = rng.random();
            format!("eph_transcribe_dummy_{}", hex::encode(random_bytes))
        };

        let response = crate::realtime::RealtimeTranscriptionResponse {
            id: session_id,
            object: "realtime.transcription_session".to_string(),
            model: request.model.clone(),
            expires_at,
            client_secret: crate::realtime::ClientSecret {
                value: client_secret,
                expires_at,
            },
            input_audio_format: request.input_audio_format.clone(),
            input_audio_transcription: request.input_audio_transcription.clone(),
            turn_detection: request.turn_detection.clone(),
            modalities: vec!["text".to_string()], // Always text-only for transcription
        };
        Ok(response)
    }
}
