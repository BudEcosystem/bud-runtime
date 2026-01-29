use std::future::Future;
use std::time::Duration;
use std::{collections::HashMap, sync::Arc};

use crate::cache::{
    embedding_cache_lookup, start_cache_write, CacheData, EmbeddingCacheData,
    EmbeddingModelProviderRequest,
};
use crate::config_parser::ProviderTypesConfig;
use crate::endpoints::inference::InferenceClients;
use crate::model::UninitializedProviderConfig;
use crate::model_table::BaseModelTable;
use crate::model_table::ShorthandModelConfig;
use crate::{
    endpoints::inference::InferenceCredentials,
    error::{Error, ErrorDetails},
    inference::{
        providers::{
            azure::AzureProvider, fireworks::FireworksProvider, openai::OpenAIProvider,
            together::TogetherProvider, vllm::VLLMProvider,
        },
        types::{
            current_timestamp, Latency, ModelInferenceResponseWithMetadata, RequestMessage, Role,
            Usage,
        },
    },
    model::ProviderConfig,
};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tracing::instrument;
use uuid::Uuid;

#[cfg(any(test, feature = "e2e_tests"))]
use crate::inference::providers::dummy::DummyProvider;

pub type EmbeddingModelTable = BaseModelTable<EmbeddingModelConfig>;

impl ShorthandModelConfig for EmbeddingModelConfig {
    const SHORTHAND_MODEL_PREFIXES: &[&str] = &[
        "openai::",
        "vllm::",
        "together::",
        "mistral::",
        "fireworks::",
    ];
    const MODEL_TYPE: &str = "Embedding model";
    async fn from_shorthand(provider_type: &str, model_name: &str) -> Result<Self, Error> {
        let model_name = model_name.to_string();
        let provider_config = match provider_type {
            "openai" => {
                EmbeddingProviderConfig::OpenAI(OpenAIProvider::new(model_name, None, None)?)
            }
            "vllm" => {
                // For shorthand, we'll use a default localhost URL
                let default_url = url::Url::parse("http://localhost:8000").map_err(|e| {
                    Error::new(ErrorDetails::Config {
                        message: format!("Failed to parse default vLLM URL: {e}"),
                    })
                })?;
                EmbeddingProviderConfig::VLLM(VLLMProvider::new(model_name, default_url, None)?)
            }
            "together" => {
                EmbeddingProviderConfig::Together(TogetherProvider::new(model_name, None, false)?)
            }
            "fireworks" => {
                EmbeddingProviderConfig::Fireworks(FireworksProvider::new(model_name, None, false)?)
            }
            "mistral" => EmbeddingProviderConfig::Mistral(
                crate::inference::providers::mistral::MistralProvider::new(model_name, None)?,
            ),
            #[cfg(any(test, feature = "e2e_tests"))]
            "dummy" => EmbeddingProviderConfig::Dummy(DummyProvider::new(model_name, None)?),
            _ => {
                return Err(Error::new(ErrorDetails::Config {
                    message: format!("Invalid provider type: {provider_type}"),
                }));
            }
        };
        Ok(EmbeddingModelConfig {
            routing: vec![provider_type.to_string().into()],
            providers: HashMap::from([(provider_type.to_string().into(), provider_config)]),
        })
    }

    fn validate(&self, _key: &str) -> Result<(), Error> {
        // Credentials are validated during deserialization
        // We may add additional validation here in the future
        Ok(())
    }
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UninitializedEmbeddingModelConfig {
    pub routing: Vec<Arc<str>>,
    pub providers: HashMap<Arc<str>, UninitializedEmbeddingProviderConfig>,
}

impl UninitializedEmbeddingModelConfig {
    pub fn load(self, provider_types: &ProviderTypesConfig) -> Result<EmbeddingModelConfig, Error> {
        let providers = self
            .providers
            .into_iter()
            .map(|(name, config)| {
                let provider_config = config.load(provider_types)?;
                Ok((name, provider_config))
            })
            .collect::<Result<HashMap<_, _>, Error>>()?;
        Ok(EmbeddingModelConfig {
            routing: self.routing,
            providers,
        })
    }
}

#[derive(Debug)]
pub struct EmbeddingModelConfig {
    pub routing: Vec<Arc<str>>,
    pub providers: HashMap<Arc<str>, EmbeddingProviderConfig>,
}

impl EmbeddingModelConfig {
    #[instrument(skip_all)]
    pub async fn embed(
        &self,
        request: &EmbeddingRequest,
        model_name: &str,
        clients: &InferenceClients<'_>,
    ) -> Result<EmbeddingResponse, Error> {
        let mut provider_errors: HashMap<String, Error> = HashMap::new();
        for provider_name in &self.routing {
            let provider_config = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::ProviderNotFound {
                    provider_name: provider_name.to_string(),
                })
            })?;
            let provider_request = EmbeddingModelProviderRequest {
                request,
                provider_name,
                model_name,
            };
            // TODO: think about how to best handle errors here
            if clients.cache_options.enabled.read() {
                let cache_lookup = embedding_cache_lookup(
                    clients.clickhouse_connection_info,
                    &provider_request,
                    clients.cache_options.max_age_s,
                )
                .await
                .ok()
                .flatten();
                if let Some(cache_lookup) = cache_lookup {
                    return Ok(cache_lookup);
                }
            }
            let response = provider_config
                .embed(request, clients.http_client, clients.credentials)
                .await;
            match response {
                Ok(response) => {
                    if clients.cache_options.enabled.write() {
                        let _ = start_cache_write(
                            clients.clickhouse_connection_info,
                            provider_request.get_cache_key()?,
                            EmbeddingCacheData {
                                embeddings: response.embeddings.clone(),
                            },
                            &response.raw_request,
                            &response.raw_response,
                            &response.usage,
                            None,
                        );
                    }
                    let embedding_response =
                        EmbeddingResponse::new(response, provider_name.clone());
                    return Ok(embedding_response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(ErrorDetails::ModelProvidersExhausted { provider_errors }.into())
    }
}

/// Represents a single embedding input item which can be text, URL, or base64 data URI.
/// This enables multimodal embedding support for image and audio inputs.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(untagged)]
pub enum EmbeddingInputItem {
    /// Plain text input
    Text(String),
}

impl EmbeddingInputItem {
    /// Parse a string into an EmbeddingInputItem, detecting URLs and data URIs
    pub fn from_string(s: String, modality: Option<&str>) -> Self {
        // For text modality or no modality specified, always treat as text
        if modality.is_none() || modality == Some("text") {
            return EmbeddingInputItem::Text(s);
        }

        // For image/audio modality, check if it's a URL or data URI
        // Data URIs and URLs are passed through as text - the provider handles them
        EmbeddingInputItem::Text(s)
    }

    /// Get the content as a string reference
    pub fn as_str(&self) -> &str {
        match self {
            EmbeddingInputItem::Text(s) => s,
        }
    }

    /// Check if this is a URL (starts with http:// or https://)
    pub fn is_url(&self) -> bool {
        match self {
            EmbeddingInputItem::Text(s) => s.starts_with("http://") || s.starts_with("https://"),
        }
    }

    /// Check if this is a data URI (starts with data:)
    pub fn is_data_uri(&self) -> bool {
        match self {
            EmbeddingInputItem::Text(s) => s.starts_with("data:"),
        }
    }

    /// Parse a data URI and return (mime_type, base64_data)
    /// Returns None if not a valid data URI
    pub fn parse_data_uri(&self) -> Option<(&str, &str)> {
        match self {
            EmbeddingInputItem::Text(s) => {
                if !s.starts_with("data:") {
                    return None;
                }
                // Format: data:<mime>;base64,<data>
                let without_prefix = s.strip_prefix("data:")?;
                let (mime_and_encoding, data) = without_prefix.split_once(',')?;
                let mime_type = mime_and_encoding.strip_suffix(";base64")?;
                Some((mime_type, data))
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(untagged)]
pub enum EmbeddingInput {
    Single(String),
    Batch(Vec<String>),
}

impl EmbeddingInput {
    /// Get all input strings as a vector
    pub fn as_vec(&self) -> Vec<&str> {
        match self {
            EmbeddingInput::Single(text) => vec![text],
            EmbeddingInput::Batch(texts) => texts.iter().map(|s| s.as_str()).collect(),
        }
    }

    /// Get the number of inputs
    pub fn len(&self) -> usize {
        match self {
            EmbeddingInput::Single(_) => 1,
            EmbeddingInput::Batch(texts) => texts.len(),
        }
    }

    /// Check if empty
    pub fn is_empty(&self) -> bool {
        match self {
            EmbeddingInput::Single(text) => text.is_empty(),
            EmbeddingInput::Batch(texts) => texts.is_empty() || texts.iter().all(|t| t.is_empty()),
        }
    }

    /// Check if any input is a URL
    pub fn has_urls(&self) -> bool {
        match self {
            EmbeddingInput::Single(text) => {
                text.starts_with("http://") || text.starts_with("https://")
            }
            EmbeddingInput::Batch(texts) => texts
                .iter()
                .any(|t| t.starts_with("http://") || t.starts_with("https://")),
        }
    }

    /// Check if any input is a data URI
    pub fn has_data_uris(&self) -> bool {
        match self {
            EmbeddingInput::Single(text) => text.starts_with("data:"),
            EmbeddingInput::Batch(texts) => texts.iter().any(|t| t.starts_with("data:")),
        }
    }

    /// Validate inputs for the given modality
    /// Returns an error message if validation fails
    pub fn validate_for_modality(&self, modality: Option<&str>) -> Result<(), String> {
        let modality = modality.unwrap_or("text");

        match modality {
            "text" => {
                // Text modality: URLs and data URIs should not be used
                // (but we allow them and pass through for flexibility)
                Ok(())
            }
            "image" | "audio" => {
                // Image/audio modality: inputs should be URLs or data URIs
                // Plain text is also allowed (some models may support text descriptions)
                Ok(())
            }
            _ => Err(format!("Unsupported modality: {}", modality)),
        }
    }
}

/// Configuration for text chunking - passed through to provider.
/// See docs/dev/embedding-model-support.md for full API documentation.
#[derive(Debug, Clone, Default, PartialEq, Deserialize, Serialize)]
pub struct ChunkingConfig {
    /// Enable chunking (default: false)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub enabled: Option<bool>,
    /// Strategy: "token" | "sentence" | "recursive" | "semantic" | "code" | "table" (default: "token")
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub strategy: Option<String>,
    /// Max tokens per chunk, 1-8192 (default: 512)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub chunk_size: Option<u32>,
    /// Token overlap between chunks (default: 0)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub chunk_overlap: Option<u32>,
    /// Tokenizer: "cl100k_base" | "p50k_base" | "r50k_base" | "gpt2" (default: "cl100k_base")
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tokenizer: Option<String>,
    /// [sentence] Min sentences per chunk (default: 1)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub min_sentences: Option<u32>,
    /// [sentence] Custom delimiters, e.g. [". ", "! ", "? "]
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub delimiters: Option<Vec<String>>,
    /// [recursive] Recipe: "markdown" | null
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub recipe: Option<String>,
    /// [semantic] Similarity threshold 0.0-1.0 (default: 0.8)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub semantic_threshold: Option<f32>,
    /// [semantic] Embedding model (default: "minishlab/potion-base-32M")
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub semantic_model: Option<String>,
    /// [semantic] Similarity window (default: 3)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub semantic_window: Option<u32>,
    /// [code] Language: "python" | "javascript" | "rust" | etc. (default: auto)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub language: Option<String>,
    /// Preprocessing: "text" | "markdown" | "table" | null
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub chef: Option<String>,
    /// Chain strategies: ["sentence", "token"], overrides strategy
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub pipeline: Option<Vec<String>>,
    /// Enable overlap refinery (default: false)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub add_overlap_context: Option<bool>,
    /// Overlap size: int (tokens) or float (fraction 0-1) (default: 0.25)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub overlap_size: Option<serde_json::Value>,
    /// Overlap method: "prefix" | "suffix" (default: "suffix")
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub overlap_method: Option<String>,
    /// Include chunk text in response (default: true)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub return_chunk_text: Option<bool>,
}

#[derive(Debug, PartialEq, Serialize)]
pub struct EmbeddingRequest {
    pub input: EmbeddingInput,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub encoding_format: Option<String>,
    /// Matryoshka dimensions - forwarded to provider
    #[serde(skip_serializing_if = "Option::is_none")]
    pub dimensions: Option<u32>,
    /// Modality type (text/image/audio) - forwarded to provider
    #[serde(skip_serializing_if = "Option::is_none")]
    pub modality: Option<String>,
    /// Priority level (high/normal/low) - forwarded to provider
    #[serde(skip_serializing_if = "Option::is_none")]
    pub priority: Option<String>,
    /// Include original input text in response - forwarded to provider
    #[serde(skip_serializing_if = "Option::is_none")]
    pub include_input: Option<bool>,
    /// Chunking configuration - forwarded to provider
    #[serde(skip_serializing_if = "Option::is_none")]
    pub chunking: Option<ChunkingConfig>,
    /// Extra fields to pass through to providers
    #[serde(flatten, skip_serializing_if = "HashMap::is_empty")]
    pub extra: HashMap<String, Value>,
}

#[derive(Debug, Clone, Copy)]
pub struct EmbeddingProviderRequest<'request> {
    pub request: &'request EmbeddingRequest,
    pub model_name: &'request str,
    pub provider_name: &'request str,
}

#[derive(Debug, PartialEq)]
pub struct EmbeddingProviderResponse {
    pub id: Uuid,
    pub input: EmbeddingInput,
    pub embeddings: Vec<Vec<f32>>,
    pub created: u64,
    pub raw_request: String,
    pub raw_response: String,
    pub usage: Usage,
    pub latency: Latency,
}

#[derive(Debug, PartialEq)]
pub struct EmbeddingResponse {
    pub id: Uuid,
    pub input: EmbeddingInput,
    pub embeddings: Vec<Vec<f32>>,
    pub created: u64,
    pub raw_request: String,
    pub raw_response: String,
    pub usage: Usage,
    pub latency: Latency,
    pub embedding_provider_name: Arc<str>,
    pub cached: bool,
}

impl EmbeddingResponse {
    pub fn from_cache(
        cache_lookup: CacheData<EmbeddingCacheData>,
        request: &EmbeddingModelProviderRequest,
    ) -> Self {
        Self {
            id: Uuid::now_v7(),
            created: current_timestamp(),
            input: request.request.input.clone(),
            embeddings: cache_lookup.output.embeddings,
            raw_request: cache_lookup.raw_request,
            raw_response: cache_lookup.raw_response,
            usage: Usage {
                input_tokens: cache_lookup.input_tokens,
                output_tokens: cache_lookup.output_tokens,
            },
            latency: Latency::NonStreaming {
                response_time: Duration::from_secs(0),
            },
            embedding_provider_name: Arc::from(request.provider_name),
            cached: true,
        }
    }
}

pub struct EmbeddingResponseWithMetadata {
    pub id: Uuid,
    pub input: String,
    pub embedding: Vec<f32>,
    pub created: u64,
    pub raw_request: String,
    pub raw_response: String,
    pub usage: Usage,
    pub latency: Latency,
    pub embedding_provider_name: Arc<str>,
    pub embedding_model_name: Arc<str>,
}

impl EmbeddingResponse {
    pub fn new(
        embedding_provider_response: EmbeddingProviderResponse,
        embedding_provider_name: Arc<str>,
    ) -> Self {
        Self {
            id: embedding_provider_response.id,
            input: embedding_provider_response.input,
            embeddings: embedding_provider_response.embeddings,
            created: embedding_provider_response.created,
            raw_request: embedding_provider_response.raw_request,
            raw_response: embedding_provider_response.raw_response,
            usage: embedding_provider_response.usage,
            latency: embedding_provider_response.latency,
            embedding_provider_name,
            cached: false,
        }
    }
}

impl EmbeddingResponseWithMetadata {
    pub fn new(embedding_response: EmbeddingResponse, embedding_model_name: Arc<str>) -> Self {
        // For backward compatibility, take the first embedding and convert input to string
        let input_string = match &embedding_response.input {
            EmbeddingInput::Single(text) => text.clone(),
            EmbeddingInput::Batch(texts) => texts.first().unwrap_or(&String::new()).clone(),
        };
        let embedding = embedding_response
            .embeddings
            .into_iter()
            .next()
            .unwrap_or_default();

        Self {
            id: embedding_response.id,
            input: input_string,
            embedding,
            created: embedding_response.created,
            raw_request: embedding_response.raw_request,
            raw_response: embedding_response.raw_response,
            usage: embedding_response.usage,
            latency: embedding_response.latency,
            embedding_provider_name: embedding_response.embedding_provider_name,
            embedding_model_name,
        }
    }
}

impl From<EmbeddingResponseWithMetadata> for ModelInferenceResponseWithMetadata {
    fn from(response: EmbeddingResponseWithMetadata) -> Self {
        Self {
            id: response.id,
            output: vec![],
            created: response.created,
            system: None,
            input_messages: vec![RequestMessage {
                role: Role::User,
                content: vec![response.input.into()],
            }], // TODO (#399): Store this information in a more appropriate way for this kind of request
            raw_request: response.raw_request,
            raw_response: response.raw_response,
            usage: response.usage,
            latency: response.latency,
            model_provider_name: response.embedding_provider_name,
            model_name: response.embedding_model_name,
            cached: false,
            finish_reason: None,
            gateway_request: None,
            gateway_response: None,
            guardrail_scan_summary: None,
        }
    }
}

pub trait EmbeddingProvider {
    fn embed(
        &self,
        request: &EmbeddingRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> impl Future<Output = Result<EmbeddingProviderResponse, Error>> + Send;
}

#[derive(Debug)]
pub enum EmbeddingProviderConfig {
    Azure(AzureProvider),
    OpenAI(OpenAIProvider),
    VLLM(VLLMProvider),
    Together(TogetherProvider),
    Fireworks(FireworksProvider),
    Mistral(crate::inference::providers::mistral::MistralProvider),
    #[cfg(any(test, feature = "e2e_tests"))]
    Dummy(DummyProvider),
}

#[derive(Debug, Deserialize)]
pub struct UninitializedEmbeddingProviderConfig {
    #[serde(flatten)]
    config: UninitializedProviderConfig,
}

impl UninitializedEmbeddingProviderConfig {
    pub fn load(
        self,
        provider_types: &ProviderTypesConfig,
    ) -> Result<EmbeddingProviderConfig, Error> {
        let provider_config = self.config.load(provider_types)?;
        Ok(match provider_config {
            ProviderConfig::Azure(provider) => EmbeddingProviderConfig::Azure(provider),
            ProviderConfig::OpenAI(provider) => EmbeddingProviderConfig::OpenAI(provider),
            ProviderConfig::VLLM(provider) => EmbeddingProviderConfig::VLLM(provider),
            ProviderConfig::Together(provider) => EmbeddingProviderConfig::Together(provider),
            ProviderConfig::Fireworks(provider) => EmbeddingProviderConfig::Fireworks(provider),
            ProviderConfig::Mistral(provider) => EmbeddingProviderConfig::Mistral(provider),
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => EmbeddingProviderConfig::Dummy(provider),
            _ => {
                return Err(Error::new(ErrorDetails::Config {
                    message: format!(
                        "Unsupported provider config for embedding: {provider_config:?}"
                    ),
                }));
            }
        })
    }
}

impl EmbeddingProvider for EmbeddingProviderConfig {
    async fn embed(
        &self,
        request: &EmbeddingRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<EmbeddingProviderResponse, Error> {
        match self {
            EmbeddingProviderConfig::Azure(provider) => {
                provider.embed(request, client, dynamic_api_keys).await
            }
            EmbeddingProviderConfig::OpenAI(provider) => {
                provider.embed(request, client, dynamic_api_keys).await
            }
            EmbeddingProviderConfig::VLLM(provider) => {
                provider.embed(request, client, dynamic_api_keys).await
            }
            EmbeddingProviderConfig::Together(provider) => {
                provider.embed(request, client, dynamic_api_keys).await
            }
            EmbeddingProviderConfig::Fireworks(provider) => {
                provider.embed(request, client, dynamic_api_keys).await
            }
            EmbeddingProviderConfig::Mistral(provider) => {
                provider.embed(request, client, dynamic_api_keys).await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            EmbeddingProviderConfig::Dummy(provider) => {
                provider.embed(request, client, dynamic_api_keys).await
            }
        }
    }
}

impl EmbeddingProviderResponse {
    pub fn new(
        embeddings: Vec<Vec<f32>>,
        input: EmbeddingInput,
        raw_request: String,
        raw_response: String,
        usage: Usage,
        latency: Latency,
    ) -> Self {
        Self {
            id: Uuid::now_v7(),
            input,
            embeddings,
            created: current_timestamp(),
            raw_request,
            raw_response,
            usage,
            latency,
        }
    }

    /// Create a response from a single embedding (for backward compatibility)
    pub fn new_single(
        embedding: Vec<f32>,
        input: String,
        raw_request: String,
        raw_response: String,
        usage: Usage,
        latency: Latency,
    ) -> Self {
        Self::new(
            vec![embedding],
            EmbeddingInput::Single(input),
            raw_request,
            raw_response,
            usage,
            latency,
        )
    }
}

/// Utility functions for processing multimodal embedding inputs
pub mod multimodal {
    use super::*;
    use base64::{engine::general_purpose::STANDARD as BASE64_STANDARD, Engine};

    /// Supported media types for image inputs
    pub const IMAGE_MEDIA_TYPES: &[&str] = &[
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/gif",
        "image/webp",
        "image/bmp",
    ];

    /// Supported media types for audio inputs
    pub const AUDIO_MEDIA_TYPES: &[&str] = &[
        "audio/mpeg",
        "audio/mp3",
        "audio/wav",
        "audio/ogg",
        "audio/flac",
        "audio/webm",
    ];

    /// Fetch content from a URL and return as base64-encoded data URI
    pub async fn fetch_url_as_data_uri(
        client: &Client,
        url: &str,
    ) -> Result<String, Error> {
        let response = client.get(url).send().await.map_err(|e| {
            Error::new(ErrorDetails::InvalidRequest {
                message: format!("Failed to fetch URL {}: {}", url, e),
            })
        })?;

        if !response.status().is_success() {
            return Err(Error::new(ErrorDetails::InvalidRequest {
                message: format!(
                    "Failed to fetch URL {}: HTTP {}",
                    url,
                    response.status()
                ),
            }));
        }

        // Get content type from response headers (convert to owned String before consuming response)
        let content_type = response
            .headers()
            .get("content-type")
            .and_then(|ct| ct.to_str().ok())
            .map(|ct| ct.split(';').next().unwrap_or(ct).trim())
            .unwrap_or("application/octet-stream")
            .to_string();

        let bytes = response.bytes().await.map_err(|e| {
            Error::new(ErrorDetails::InvalidRequest {
                message: format!("Failed to read response body from {}: {}", url, e),
            })
        })?;

        // Encode as base64
        let base64_data = BASE64_STANDARD.encode(&bytes);

        // Return as data URI
        Ok(format!("data:{};base64,{}", content_type, base64_data))
    }

    /// Validate a data URI format and return the mime type
    pub fn validate_data_uri(data_uri: &str) -> Result<&str, Error> {
        if !data_uri.starts_with("data:") {
            return Err(Error::new(ErrorDetails::InvalidRequest {
                message: "Invalid data URI: must start with 'data:'".to_string(),
            }));
        }

        let without_prefix = data_uri.strip_prefix("data:").unwrap();
        let (mime_and_encoding, _data) = without_prefix.split_once(',').ok_or_else(|| {
            Error::new(ErrorDetails::InvalidRequest {
                message: "Invalid data URI: missing comma separator".to_string(),
            })
        })?;

        if !mime_and_encoding.ends_with(";base64") {
            return Err(Error::new(ErrorDetails::InvalidRequest {
                message: "Invalid data URI: must be base64 encoded".to_string(),
            }));
        }

        let mime_type = mime_and_encoding.strip_suffix(";base64").unwrap();
        Ok(mime_type)
    }

    /// Validate that the media type is appropriate for the modality
    pub fn validate_media_type_for_modality(
        media_type: &str,
        modality: &str,
    ) -> Result<(), Error> {
        match modality {
            "image" => {
                if !IMAGE_MEDIA_TYPES.contains(&media_type) {
                    return Err(Error::new(ErrorDetails::InvalidRequest {
                        message: format!(
                            "Unsupported image media type '{}'. Supported types: {:?}",
                            media_type, IMAGE_MEDIA_TYPES
                        ),
                    }));
                }
            }
            "audio" => {
                if !AUDIO_MEDIA_TYPES.contains(&media_type) {
                    return Err(Error::new(ErrorDetails::InvalidRequest {
                        message: format!(
                            "Unsupported audio media type '{}'. Supported types: {:?}",
                            media_type, AUDIO_MEDIA_TYPES
                        ),
                    }));
                }
            }
            "text" => {
                // Text modality doesn't need media type validation
            }
            _ => {
                return Err(Error::new(ErrorDetails::InvalidRequest {
                    message: format!("Unsupported modality: {}", modality),
                }));
            }
        }
        Ok(())
    }

    /// Process embedding inputs, fetching URLs if necessary for non-text modalities
    pub async fn process_inputs_for_modality(
        client: &Client,
        input: &EmbeddingInput,
        modality: Option<&str>,
    ) -> Result<EmbeddingInput, Error> {
        let modality = modality.unwrap_or("text");

        // For text modality, return as-is
        if modality == "text" {
            return Ok(input.clone());
        }

        // For image/audio modality, process URLs to data URIs
        match input {
            EmbeddingInput::Single(text) => {
                let processed = process_single_input(client, text, modality).await?;
                Ok(EmbeddingInput::Single(processed))
            }
            EmbeddingInput::Batch(texts) => {
                let mut processed = Vec::with_capacity(texts.len());
                for text in texts {
                    processed.push(process_single_input(client, text, modality).await?);
                }
                Ok(EmbeddingInput::Batch(processed))
            }
        }
    }

    async fn process_single_input(
        client: &Client,
        input: &str,
        modality: &str,
    ) -> Result<String, Error> {
        // Check if it's a URL
        if input.starts_with("http://") || input.starts_with("https://") {
            // Fetch and convert to data URI
            let data_uri = fetch_url_as_data_uri(client, input).await?;
            // Validate the fetched content type
            let mime_type = validate_data_uri(&data_uri)?;
            validate_media_type_for_modality(mime_type, modality)?;
            Ok(data_uri)
        } else if input.starts_with("data:") {
            // Validate existing data URI
            let mime_type = validate_data_uri(input)?;
            validate_media_type_for_modality(mime_type, modality)?;
            Ok(input.to_string())
        } else {
            // Plain text - pass through (some models may support text descriptions)
            Ok(input.to_string())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_embedding_input_variants() {
        // Test Single variant
        let single = EmbeddingInput::Single("Hello, world!".to_string());
        assert_eq!(single.len(), 1);
        assert!(!single.is_empty());
        assert_eq!(single.as_vec(), vec!["Hello, world!"]);

        // Test Batch variant
        let batch = EmbeddingInput::Batch(vec![
            "First text".to_string(),
            "Second text".to_string(),
            "Third text".to_string(),
        ]);
        assert_eq!(batch.len(), 3);
        assert!(!batch.is_empty());
        assert_eq!(
            batch.as_vec(),
            vec!["First text", "Second text", "Third text"]
        );

        // Test empty cases
        let empty_single = EmbeddingInput::Single("".to_string());
        assert!(empty_single.is_empty());

        let empty_batch = EmbeddingInput::Batch(vec![]);
        assert!(empty_batch.is_empty());

        let batch_with_empty = EmbeddingInput::Batch(vec!["".to_string(), "".to_string()]);
        assert!(batch_with_empty.is_empty());
    }

    #[test]
    fn test_embedding_input_serialization() {
        // Test Single serialization
        let single = EmbeddingInput::Single("Hello".to_string());
        let serialized = serde_json::to_value(&single).unwrap();
        assert_eq!(serialized, serde_json::Value::String("Hello".to_string()));

        // Test Batch serialization
        let batch = EmbeddingInput::Batch(vec!["Hello".to_string(), "World".to_string()]);
        let serialized = serde_json::to_value(&batch).unwrap();
        assert_eq!(
            serialized,
            serde_json::Value::Array(vec![
                serde_json::Value::String("Hello".to_string()),
                serde_json::Value::String("World".to_string())
            ])
        );
    }

    #[test]
    fn test_embedding_request_with_batch_input() {
        let request = EmbeddingRequest {
            input: EmbeddingInput::Batch(vec!["Text 1".to_string(), "Text 2".to_string()]),
            encoding_format: None,
            dimensions: None,
            modality: None,
            priority: None,
            include_input: None,
            chunking: None,
            extra: HashMap::new(),
        };

        assert_eq!(request.input.len(), 2);
        assert_eq!(request.input.as_vec(), vec!["Text 1", "Text 2"]);
    }

    #[test]
    fn test_embedding_provider_response_batch() {
        let embeddings = vec![vec![0.1, 0.2, 0.3], vec![0.4, 0.5, 0.6]];
        let input = EmbeddingInput::Batch(vec!["Text 1".to_string(), "Text 2".to_string()]);

        let response = EmbeddingProviderResponse::new(
            embeddings.clone(),
            input.clone(),
            "raw_request".to_string(),
            "raw_response".to_string(),
            Usage {
                input_tokens: 10,
                output_tokens: 0,
            },
            Latency::NonStreaming {
                response_time: std::time::Duration::from_millis(100),
            },
        );

        assert_eq!(response.embeddings, embeddings);
        assert_eq!(response.input, input);
    }

    #[test]
    fn test_embedding_provider_response_new_single_compatibility() {
        // Test backward compatibility method
        let embedding = vec![0.1, 0.2, 0.3];
        let input = "Test input".to_string();

        let response = EmbeddingProviderResponse::new_single(
            embedding.clone(),
            input.clone(),
            "raw_request".to_string(),
            "raw_response".to_string(),
            Usage {
                input_tokens: 5,
                output_tokens: 0,
            },
            Latency::NonStreaming {
                response_time: std::time::Duration::from_millis(50),
            },
        );

        assert_eq!(response.embeddings, vec![embedding]);
        assert_eq!(response.input, EmbeddingInput::Single(input));
    }
    use tracing_test::traced_test;

    use crate::{
        cache::{CacheEnabledMode, CacheOptions},
        clickhouse::ClickHouseConnectionInfo,
    };

    #[traced_test]
    #[tokio::test]
    async fn test_embedding_fallbacks() {
        let bad_provider = EmbeddingProviderConfig::Dummy(DummyProvider {
            model_name: "error".into(),
            ..Default::default()
        });
        let good_provider = EmbeddingProviderConfig::Dummy(DummyProvider {
            model_name: "good".into(),
            ..Default::default()
        });
        let fallback_embedding_model = EmbeddingModelConfig {
            routing: vec!["error".to_string().into(), "good".to_string().into()],
            providers: HashMap::from([
                ("error".to_string().into(), bad_provider),
                ("good".to_string().into(), good_provider),
            ]),
        };
        let request = EmbeddingRequest {
            input: EmbeddingInput::Single("Hello, world!".to_string()),
            encoding_format: None,
            dimensions: None,
            modality: None,
            priority: None,
            include_input: None,
            chunking: None,
            extra: HashMap::new(),
        };
        let response = fallback_embedding_model
            .embed(
                &request,
                "fallback",
                &InferenceClients {
                    http_client: &Client::new(),
                    credentials: &InferenceCredentials::default(),
                    cache_options: &CacheOptions {
                        max_age_s: None,
                        enabled: CacheEnabledMode::Off,
                    },
                    clickhouse_connection_info: &ClickHouseConnectionInfo::new_disabled(),
                },
            )
            .await;
        assert!(response.is_ok());
        assert!(logs_contain(
            "Error sending request to Dummy provider for model 'error'"
        ))
    }

    #[test]
    fn test_embedding_input_url_detection() {
        // Test URL detection
        let url_input = EmbeddingInput::Single("https://example.com/image.png".to_string());
        assert!(url_input.has_urls());
        assert!(!url_input.has_data_uris());

        let http_url = EmbeddingInput::Single("http://example.com/image.png".to_string());
        assert!(http_url.has_urls());

        // Test data URI detection
        let data_uri =
            EmbeddingInput::Single("data:image/png;base64,iVBORw0KGgoAAAANS".to_string());
        assert!(!data_uri.has_urls());
        assert!(data_uri.has_data_uris());

        // Test plain text
        let text = EmbeddingInput::Single("Hello, world!".to_string());
        assert!(!text.has_urls());
        assert!(!text.has_data_uris());

        // Test batch with mixed inputs
        let batch = EmbeddingInput::Batch(vec![
            "Hello".to_string(),
            "https://example.com/image.png".to_string(),
            "data:image/jpeg;base64,/9j/4AAQ".to_string(),
        ]);
        assert!(batch.has_urls());
        assert!(batch.has_data_uris());
    }

    #[test]
    fn test_embedding_input_item_data_uri_parsing() {
        // Valid data URI
        let item = EmbeddingInputItem::Text(
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB".to_string(),
        );
        assert!(item.is_data_uri());
        assert!(!item.is_url());

        let parsed = item.parse_data_uri();
        assert!(parsed.is_some());
        let (mime, data) = parsed.unwrap();
        assert_eq!(mime, "image/png");
        assert_eq!(data, "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB");

        // Invalid data URI (no base64)
        let invalid =
            EmbeddingInputItem::Text("data:image/png,raw_data_without_base64".to_string());
        assert!(invalid.parse_data_uri().is_none());

        // Not a data URI
        let text = EmbeddingInputItem::Text("Hello, world!".to_string());
        assert!(text.parse_data_uri().is_none());
    }

    #[test]
    fn test_multimodal_validate_data_uri() {
        use super::multimodal::validate_data_uri;

        // Valid data URI
        let valid = "data:image/png;base64,iVBORw0KGgoAAAANS";
        let result = validate_data_uri(valid);
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), "image/png");

        // Missing data: prefix
        let no_prefix = "image/png;base64,iVBORw0KGgoAAAANS";
        assert!(validate_data_uri(no_prefix).is_err());

        // Missing comma
        let no_comma = "data:image/png;base64iVBORw0KGgoAAAANS";
        assert!(validate_data_uri(no_comma).is_err());

        // Missing base64 encoding
        let no_base64 = "data:image/png,raw_data";
        assert!(validate_data_uri(no_base64).is_err());
    }

    #[test]
    fn test_multimodal_validate_media_type() {
        use super::multimodal::validate_media_type_for_modality;

        // Valid image types
        assert!(validate_media_type_for_modality("image/png", "image").is_ok());
        assert!(validate_media_type_for_modality("image/jpeg", "image").is_ok());
        assert!(validate_media_type_for_modality("image/webp", "image").is_ok());

        // Invalid image type
        assert!(validate_media_type_for_modality("image/tiff", "image").is_err());

        // Valid audio types
        assert!(validate_media_type_for_modality("audio/mpeg", "audio").is_ok());
        assert!(validate_media_type_for_modality("audio/wav", "audio").is_ok());

        // Invalid audio type
        assert!(validate_media_type_for_modality("audio/midi", "audio").is_err());

        // Text modality accepts anything
        assert!(validate_media_type_for_modality("anything", "text").is_ok());

        // Invalid modality
        assert!(validate_media_type_for_modality("image/png", "video").is_err());
    }

    #[test]
    fn test_embedding_input_validate_for_modality() {
        let text_input = EmbeddingInput::Single("Hello, world!".to_string());

        // Text modality should accept anything
        assert!(text_input.validate_for_modality(Some("text")).is_ok());
        assert!(text_input.validate_for_modality(None).is_ok());

        // Image and audio modalities should work
        assert!(text_input.validate_for_modality(Some("image")).is_ok());
        assert!(text_input.validate_for_modality(Some("audio")).is_ok());

        // Invalid modality
        assert!(text_input.validate_for_modality(Some("video")).is_err());
    }
}
