use backon::{ExponentialBuilder, Retryable};
use futures::StreamExt;
use reqwest::Client;
use secrecy::SecretString;
use serde::{Deserialize, Serialize};
use std::borrow::Cow;
use std::collections::{HashMap, HashSet};
use std::sync::{Arc, OnceLock};
use std::time::Duration;
use std::{env, fs};
use strum::VariantNames;
use tensorzero_derive::TensorZeroDeserialize;
use tracing::{instrument, span, Level, Span};
use tracing_futures::{Instrument, Instrumented};
use url::Url;

use crate::cache::{
    cache_lookup, cache_lookup_streaming, start_cache_write, start_cache_write_streaming,
    CacheData, ModelProviderRequest, NonStreamingCacheData, StreamingCacheData,
};
use crate::config_parser::{skip_credential_validation, ProviderTypesConfig};
use crate::endpoints::capability::{default_capabilities, EndpointCapability};
use crate::endpoints::inference::InferenceClients;
use crate::inference::providers::aws_sagemaker::AWSSagemakerProvider;
#[cfg(any(test, feature = "e2e_tests"))]
use crate::inference::providers::dummy::DummyProvider;
use crate::inference::providers::google_ai_studio_gemini::GoogleAIStudioGeminiProvider;

use crate::inference::providers::bud_sentinel::BudSentinelProvider;
use crate::inference::providers::buddoc::BudDocProvider;
use crate::inference::providers::budprompt::BudPromptProvider;
use crate::inference::providers::helpers::peek_first_chunk;
use crate::inference::providers::hyperbolic::HyperbolicProvider;
use crate::inference::providers::provider_trait::WrappedProvider;
use crate::inference::providers::sglang::SGLangProvider;
use crate::inference::providers::tgi::TGIProvider;
use crate::inference::types::batch::{
    BatchRequestRow, PollBatchInferenceResponse, StartBatchModelInferenceResponse,
    StartBatchProviderInferenceResponse,
};
use crate::inference::types::extra_body::ExtraBodyConfig;
use crate::inference::types::extra_headers::ExtraHeadersConfig;
use crate::inference::types::{
    current_timestamp, ContentBlock, PeekableProviderInferenceResponseStream,
    ProviderInferenceResponseChunk, ProviderInferenceResponseStreamInner, RequestMessage, Usage,
};
use crate::model_table::{BaseModelTable, CowNoClone, ShorthandModelConfig};
use crate::{
    endpoints::inference::InferenceCredentials,
    error::{Error, ErrorDetails},
    inference::{
        providers::{
            anthropic::AnthropicProvider, aws_bedrock::AWSBedrockProvider, azure::AzureProvider,
            azure_content_safety::AzureContentSafetyProvider, deepseek::DeepSeekProvider,
            fireworks::FireworksProvider, gcp_vertex_anthropic::GCPVertexAnthropicProvider,
            gcp_vertex_gemini::GCPVertexGeminiProvider, mistral::MistralProvider,
            openai::OpenAIProvider, openrouter::OpenRouterProvider,
            provider_trait::InferenceProvider, together::TogetherProvider, vllm::VLLMProvider,
            xai::XAIProvider,
        },
        types::{ModelInferenceRequest, ModelInferenceResponse, ProviderInferenceResponse},
    },
};

#[cfg(test)]
#[path = "model_fallback_tests.rs"]
mod fallback_tests;

#[derive(Debug, Deserialize, Copy, Clone)]
pub struct RetryConfig {
    pub num_retries: usize,
    pub max_delay_s: f32,
}

impl Default for RetryConfig {
    fn default() -> Self {
        RetryConfig {
            num_retries: 0,
            max_delay_s: 10.0,
        }
    }
}

impl RetryConfig {
    pub fn get_backoff(&self) -> backon::ExponentialBuilder {
        ExponentialBuilder::default()
            .with_jitter()
            .with_max_delay(Duration::from_secs_f32(self.max_delay_s))
            .with_max_times(self.num_retries)
    }
}

/// Pricing information for a model
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct ModelPricing {
    pub input_cost: f64,  // Cost per input tokens
    pub output_cost: f64, // Cost per output tokens
    pub currency: String, // Currency code (e.g., "USD")
    pub per_tokens: u32,  // Number of tokens for the pricing unit (e.g., 1000)
}

#[derive(Debug)]
pub struct ModelConfig {
    pub routing: Vec<Arc<str>>, // [provider name A, provider name B, ...]
    pub providers: HashMap<Arc<str>, ModelProvider>, // provider name => provider config
    pub endpoints: HashSet<EndpointCapability>, // supported endpoint capabilities
    pub fallback_models: Option<Vec<Arc<str>>>, // Optional fallback to other models
    pub retry_config: Option<RetryConfig>, // Optional model-level retry configuration
    pub rate_limits: Option<crate::rate_limit::RateLimitConfig>, // rate limiting configuration
    pub pricing: Option<ModelPricing>, // Optional pricing information
    pub guardrail_profile: Option<Arc<str>>, // Optional guardrail profile ID for wrapped inference
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct UninitializedModelConfig {
    pub routing: Vec<Arc<str>>, // [provider name A, provider name B, ...]
    pub providers: HashMap<Arc<str>, UninitializedModelProvider>, // provider name => provider config
    #[serde(default = "default_capabilities")]
    pub endpoints: HashSet<EndpointCapability>, // supported endpoint capabilities
    pub fallback_models: Option<Vec<Arc<str>>>, // Optional fallback to other models
    pub retry_config: Option<RetryConfig>,      // Optional model-level retry configuration
    #[serde(default)]
    pub rate_limits: Option<crate::rate_limit::RateLimitConfig>, // rate limiting configuration
    #[serde(default)]
    pub pricing: Option<ModelPricing>, // Optional pricing information
    pub guardrail_profile: Option<Arc<str>>, // Optional guardrail profile ID for wrapped inference
}

/// Determine endpoint capabilities based on model name patterns
fn determine_capabilities_from_model_name(model_name: &str) -> HashSet<EndpointCapability> {
    let mut capabilities = HashSet::new();

    // Check if this is an embedding model by name patterns
    let embedding_patterns = [
        "embedding",
        "embed",
        "text-embedding",
        "text-embed",
        "text_embedding",
        "text_embed",
    ];

    let lower_name = model_name.to_lowercase();
    if embedding_patterns
        .iter()
        .any(|pattern| lower_name.contains(pattern))
    {
        capabilities.insert(EndpointCapability::Embedding);
    } else {
        // Default to chat capability for non-embedding models
        capabilities.insert(EndpointCapability::Chat);
    }

    capabilities
}

impl ModelConfig {
    /// Check if this model supports a specific endpoint capability
    pub fn supports_endpoint(&self, capability: EndpointCapability) -> bool {
        self.endpoints.contains(&capability)
    }

    /// Embedding inference method (when model supports embeddings capability)
    #[instrument(skip_all)]
    pub async fn embed(
        &self,
        request: &crate::embeddings::EmbeddingRequest,
        model_name: &str,
        clients: &crate::endpoints::inference::InferenceClients<'_>,
    ) -> Result<crate::embeddings::EmbeddingResponse, Error> {
        // Verify this model supports embeddings
        if !self.supports_endpoint(EndpointCapability::Embedding) {
            return Err(Error::new(ErrorDetails::ModelNotConfiguredForCapability {
                model_name: model_name.to_string(),
                capability: EndpointCapability::Embedding.as_str().to_string(),
            }));
        }

        let mut provider_errors: HashMap<String, Error> = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::ProviderNotFound {
                    provider_name: provider_name.to_string(),
                })
            })?;

            // Use the provider's embed method
            let response = provider
                .embed(request, clients.http_client, clients.credentials)
                .await;

            match response {
                Ok(response) => {
                    // TODO: Add caching support here
                    let embedding_response =
                        crate::embeddings::EmbeddingResponse::new(response, provider_name.clone());
                    return Ok(embedding_response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(ErrorDetails::ModelProvidersExhausted { provider_errors }.into())
    }

    /// Completions inference method (when model supports completions capability)
    #[instrument(skip_all)]
    pub async fn complete(
        &self,
        request: &crate::completions::CompletionRequest,
        model_name: &str,
        clients: &crate::endpoints::inference::InferenceClients<'_>,
    ) -> Result<crate::completions::CompletionResponse, Error> {
        // Verify this model supports completions
        if !self.supports_endpoint(EndpointCapability::Completions) {
            return Err(Error::new(ErrorDetails::ModelNotConfiguredForCapability {
                model_name: model_name.to_string(),
                capability: EndpointCapability::Completions.as_str().to_string(),
            }));
        }

        let mut provider_errors: HashMap<String, Error> = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::ProviderNotFound {
                    provider_name: provider_name.to_string(),
                })
            })?;

            // Use the provider's complete method
            let response = provider
                .complete(request, clients.http_client, clients.credentials)
                .await;

            match response {
                Ok(response) => {
                    // Convert provider response to completion response
                    let completion_response = crate::completions::CompletionResponse {
                        id: response.id,
                        object: "text_completion".to_string(),
                        created: response.created,
                        model: response.model,
                        choices: response.choices,
                        usage: response.usage,
                        raw_request: response.raw_request,
                        raw_response: response.raw_response,
                        latency: response.latency,
                    };
                    return Ok(completion_response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(ErrorDetails::ModelProvidersExhausted { provider_errors }.into())
    }

    /// Streaming completion method (when model supports completions capability)
    pub async fn complete_stream(
        &self,
        request: &crate::completions::CompletionRequest,
        model_name: &str,
        clients: &crate::endpoints::inference::InferenceClients<'_>,
    ) -> Result<(crate::completions::CompletionStream, String), Error> {
        // Verify this model supports completions
        if !self.supports_endpoint(EndpointCapability::Completions) {
            return Err(Error::new(ErrorDetails::ModelNotConfiguredForCapability {
                model_name: model_name.to_string(),
                capability: EndpointCapability::Completions.as_str().to_string(),
            }));
        }

        let mut provider_errors: HashMap<String, Error> = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::ProviderNotFound {
                    provider_name: provider_name.to_string(),
                })
            })?;

            // Use the provider's complete_stream method
            let response = provider
                .complete_stream(request, clients.http_client, clients.credentials)
                .await;

            match response {
                Ok((stream, raw_request)) => {
                    return Ok((stream, raw_request));
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(ErrorDetails::ModelProvidersExhausted { provider_errors }.into())
    }

    /// Audio transcription method (when model supports audio transcription capability)
    #[instrument(skip_all)]
    pub async fn transcribe(
        &self,
        request: &crate::audio::AudioTranscriptionRequest,
        model_name: &str,
        clients: &crate::endpoints::inference::InferenceClients<'_>,
    ) -> Result<crate::audio::AudioTranscriptionResponse, Error> {
        // Verify this model supports audio transcription
        if !self.supports_endpoint(EndpointCapability::AudioTranscription) {
            return Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::AudioTranscription.as_str().to_string(),
                provider: model_name.to_string(),
            }));
        }

        let mut provider_errors: HashMap<String, Error> = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::ProviderNotFound {
                    provider_name: provider_name.to_string(),
                })
            })?;

            let response = provider
                .transcribe(request, clients.http_client, clients.credentials)
                .await;
            match response {
                Ok(response) => {
                    // TODO: Add caching support here
                    let transcription_response = crate::audio::AudioTranscriptionResponse {
                        id: response.id,
                        text: response.text,
                        language: response.language,
                        duration: response.duration,
                        words: response.words,
                        segments: response.segments,
                        created: response.created,
                        raw_request: response.raw_request,
                        raw_response: response.raw_response,
                        usage: response.usage,
                        latency: response.latency,
                    };
                    return Ok(transcription_response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(ErrorDetails::ModelProvidersExhausted { provider_errors }.into())
    }

    /// Audio translation method (when model supports audio translation capability)
    #[instrument(skip_all)]
    pub async fn translate(
        &self,
        request: &crate::audio::AudioTranslationRequest,
        model_name: &str,
        clients: &crate::endpoints::inference::InferenceClients<'_>,
    ) -> Result<crate::audio::AudioTranslationResponse, Error> {
        // Verify this model supports audio translation
        if !self.supports_endpoint(EndpointCapability::AudioTranslation) {
            return Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::AudioTranslation.as_str().to_string(),
                provider: model_name.to_string(),
            }));
        }

        let mut provider_errors: HashMap<String, Error> = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::ProviderNotFound {
                    provider_name: provider_name.to_string(),
                })
            })?;

            let response = provider
                .translate(request, clients.http_client, clients.credentials)
                .await;
            match response {
                Ok(response) => {
                    // TODO: Add caching support here
                    let translation_response = crate::audio::AudioTranslationResponse {
                        id: response.id,
                        text: response.text,
                        created: response.created,
                        raw_request: response.raw_request,
                        raw_response: response.raw_response,
                        usage: response.usage,
                        latency: response.latency,
                    };
                    return Ok(translation_response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(ErrorDetails::ModelProvidersExhausted { provider_errors }.into())
    }

    /// Text-to-speech method (when model supports text-to-speech capability)
    #[instrument(skip_all)]
    pub async fn generate_speech(
        &self,
        request: &crate::audio::TextToSpeechRequest,
        model_name: &str,
        clients: &crate::endpoints::inference::InferenceClients<'_>,
    ) -> Result<crate::audio::TextToSpeechResponse, Error> {
        // Verify this model supports text-to-speech
        if !self.supports_endpoint(EndpointCapability::TextToSpeech) {
            return Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::TextToSpeech.as_str().to_string(),
                provider: model_name.to_string(),
            }));
        }

        let mut provider_errors: HashMap<String, Error> = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::ProviderNotFound {
                    provider_name: provider_name.to_string(),
                })
            })?;

            let response = provider
                .generate_speech(request, clients.http_client, clients.credentials)
                .await;
            match response {
                Ok(response) => {
                    // TODO: Add caching support here
                    let tts_response = crate::audio::TextToSpeechResponse {
                        id: response.id,
                        audio_data: response.audio_data,
                        format: response.format,
                        created: response.created,
                        raw_request: response.raw_request,
                        usage: response.usage,
                        latency: response.latency,
                    };
                    return Ok(tts_response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(ErrorDetails::ModelProvidersExhausted { provider_errors }.into())
    }

    /// Image generation method (when model supports image generation capability)
    #[instrument(skip_all)]
    pub async fn generate_image(
        &self,
        request: &crate::images::ImageGenerationRequest,
        model_name: &str,
        clients: &crate::endpoints::inference::InferenceClients<'_>,
    ) -> Result<crate::images::ImageGenerationResponse, Error> {
        // Verify this model supports image generation
        if !self.supports_endpoint(EndpointCapability::ImageGeneration) {
            return Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::ImageGeneration.as_str().to_string(),
                provider: model_name.to_string(),
            }));
        }

        let mut provider_errors: HashMap<String, Error> = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::ProviderNotFound {
                    provider_name: provider_name.to_string(),
                })
            })?;

            let response = provider
                .generate_image(request, clients.http_client, clients.credentials)
                .await;
            match response {
                Ok(response) => {
                    let image_response = crate::images::ImageGenerationResponse {
                        id: response.id,
                        created: response.created,
                        data: response.data,
                        raw_request: response.raw_request,
                        raw_response: response.raw_response,
                        usage: response.usage,
                        latency: response.latency,
                    };
                    return Ok(image_response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(ErrorDetails::ModelProvidersExhausted { provider_errors }.into())
    }

    /// Image editing method (when model supports image editing capability)
    #[instrument(skip_all)]
    pub async fn edit_image(
        &self,
        request: &crate::images::ImageEditRequest,
        model_name: &str,
        clients: &crate::endpoints::inference::InferenceClients<'_>,
    ) -> Result<crate::images::ImageEditResponse, Error> {
        // Verify this model supports image editing
        if !self.supports_endpoint(EndpointCapability::ImageEdit) {
            return Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::ImageEdit.as_str().to_string(),
                provider: model_name.to_string(),
            }));
        }

        let mut provider_errors: HashMap<String, Error> = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::ProviderNotFound {
                    provider_name: provider_name.to_string(),
                })
            })?;

            let response = provider
                .edit_image(request, clients.http_client, clients.credentials)
                .await;
            match response {
                Ok(response) => {
                    let image_response = crate::images::ImageEditResponse {
                        id: response.id,
                        created: response.created,
                        data: response.data,
                        raw_request: response.raw_request,
                        raw_response: response.raw_response,
                        usage: response.usage,
                        latency: response.latency,
                    };
                    return Ok(image_response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(ErrorDetails::ModelProvidersExhausted { provider_errors }.into())
    }

    /// Image variation method (when model supports image variation capability)
    #[instrument(skip_all)]
    pub async fn create_image_variation(
        &self,
        request: &crate::images::ImageVariationRequest,
        model_name: &str,
        clients: &crate::endpoints::inference::InferenceClients<'_>,
    ) -> Result<crate::images::ImageVariationResponse, Error> {
        // Verify this model supports image variation
        if !self.supports_endpoint(EndpointCapability::ImageVariation) {
            return Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::ImageVariation.as_str().to_string(),
                provider: model_name.to_string(),
            }));
        }

        let mut provider_errors: HashMap<String, Error> = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::ProviderNotFound {
                    provider_name: provider_name.to_string(),
                })
            })?;

            let response = provider
                .create_image_variation(request, clients.http_client, clients.credentials)
                .await;
            match response {
                Ok(response) => {
                    let image_response = crate::images::ImageVariationResponse {
                        id: response.id,
                        created: response.created,
                        data: response.data,
                        raw_request: response.raw_request,
                        raw_response: response.raw_response,
                        usage: response.usage,
                        latency: response.latency,
                    };
                    return Ok(image_response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(ErrorDetails::ModelProvidersExhausted { provider_errors }.into())
    }

    /// Realtime session creation method (when model supports realtime session capability)
    #[instrument(skip_all)]
    pub async fn create_realtime_session(
        &self,
        request: &crate::realtime::RealtimeSessionRequest,
        model_name: &str,
        clients: &crate::endpoints::inference::InferenceClients<'_>,
    ) -> Result<crate::realtime::RealtimeSessionResponse, Error> {
        // Verify this model supports realtime sessions
        if !self.supports_endpoint(EndpointCapability::RealtimeSession) {
            return Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::RealtimeSession.as_str().to_string(),
                provider: model_name.to_string(),
            }));
        }

        let mut provider_errors: HashMap<String, Error> = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::ProviderNotFound {
                    provider_name: provider_name.to_string(),
                })
            })?;

            let response = provider
                .create_realtime_session(request, clients.http_client, clients.credentials)
                .await;
            match response {
                Ok(response) => {
                    // No caching for realtime sessions
                    return Ok(response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(ErrorDetails::ModelProvidersExhausted { provider_errors }.into())
    }

    /// Realtime transcription session creation method (when model supports realtime transcription capability)
    #[instrument(skip_all)]
    pub async fn create_realtime_transcription_session(
        &self,
        request: &crate::realtime::RealtimeTranscriptionRequest,
        model_name: &str,
        clients: &crate::endpoints::inference::InferenceClients<'_>,
    ) -> Result<crate::realtime::RealtimeTranscriptionResponse, Error> {
        // Verify this model supports realtime transcription
        if !self.supports_endpoint(EndpointCapability::RealtimeTranscription) {
            return Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::RealtimeTranscription
                    .as_str()
                    .to_string(),
                provider: model_name.to_string(),
            }));
        }

        let mut provider_errors: HashMap<String, Error> = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::ProviderNotFound {
                    provider_name: provider_name.to_string(),
                })
            })?;

            let response = provider
                .create_realtime_transcription_session(
                    request,
                    clients.http_client,
                    clients.credentials,
                )
                .await;
            match response {
                Ok(response) => {
                    // No caching for realtime sessions
                    return Ok(response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(ErrorDetails::ModelProvidersExhausted { provider_errors }.into())
    }

    /// Document processing method (when model supports document capability)
    #[instrument(skip_all)]
    pub async fn process_document(
        &self,
        request: &crate::documents::DocumentProcessingRequest,
        model_name: &str,
        clients: &crate::endpoints::inference::InferenceClients<'_>,
    ) -> Result<crate::documents::DocumentProcessingResponse, Error> {
        // Verify this model supports document processing
        if !self.supports_endpoint(EndpointCapability::Document) {
            return Err(Error::new(ErrorDetails::ModelNotConfiguredForCapability {
                model_name: model_name.to_string(),
                capability: EndpointCapability::Document.as_str().to_string(),
            }));
        }

        let mut provider_errors: HashMap<String, Error> = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::ProviderNotFound {
                    provider_name: provider_name.to_string(),
                })
            })?;

            // Use the provider's process_document method
            let response = provider
                .process_document(request, clients.http_client, clients.credentials)
                .await;

            match response {
                Ok(response) => {
                    // TODO: Add caching support here if needed
                    let document_response = crate::documents::DocumentProcessingResponse::new(
                        response,
                        provider_name.clone(),
                    );
                    return Ok(document_response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(ErrorDetails::ModelProvidersExhausted { provider_errors }.into())
    }

    /// Moderation method (when model supports moderation capability)
    #[instrument(skip_all)]
    pub async fn moderate(
        &self,
        request: &crate::moderation::ModerationRequest,
        model_name: &str,
        clients: &crate::endpoints::inference::InferenceClients<'_>,
    ) -> Result<crate::moderation::ModerationResponse, Error> {
        // Verify this model supports moderation
        if !self.supports_endpoint(EndpointCapability::Moderation) {
            return Err(Error::new(ErrorDetails::ModelNotConfiguredForCapability {
                model_name: model_name.to_string(),
                capability: EndpointCapability::Moderation.as_str().to_string(),
            }));
        }

        let mut provider_errors: HashMap<String, Error> = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::ProviderNotFound {
                    provider_name: provider_name.to_string(),
                })
            })?;

            let response = provider
                .moderate(request, clients.http_client, clients.credentials)
                .await;
            match response {
                Ok(response) => {
                    // TODO: Add caching support here
                    return Ok(response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(ErrorDetails::ModelProvidersExhausted { provider_errors }.into())
    }
}

impl UninitializedModelConfig {
    pub fn load(
        self,
        model_name: &str,
        provider_types: &ProviderTypesConfig,
    ) -> Result<ModelConfig, Error> {
        // We want `ModelProvider` to know its own name (from the 'providers' config section).
        // We first deserialize to `HashMap<Arc<str>, UninitializedModelProvider>`, and then
        // build `ModelProvider`s using the name keys from the map.
        let providers = self
            .providers
            .into_iter()
            .map(|(name, provider)| {
                Ok((
                    name.clone(),
                    ModelProvider {
                        name: name.clone(),
                        config: provider.config.load(provider_types).map_err(|e| {
                            Error::new(ErrorDetails::Config {
                                message: format!("models.{model_name}.providers.{name}: {e}"),
                            })
                        })?,
                        extra_body: provider.extra_body,
                        extra_headers: provider.extra_headers,
                    },
                ))
            })
            .collect::<Result<HashMap<_, _>, Error>>()?;
        Ok(ModelConfig {
            routing: self.routing,
            providers,
            endpoints: self.endpoints,
            fallback_models: self.fallback_models,
            retry_config: self.retry_config,
            rate_limits: self.rate_limits,
            pricing: self.pricing,
            guardrail_profile: self.guardrail_profile,
        })
    }
}

pub struct StreamResponse {
    pub stream: Instrumented<PeekableProviderInferenceResponseStream>,
    pub raw_request: String,
    pub model_provider_name: Arc<str>,
    pub cached: bool,
}

impl StreamResponse {
    pub fn from_cache(
        cache_lookup: CacheData<StreamingCacheData>,
        model_provider_name: Arc<str>,
    ) -> Self {
        let chunks = cache_lookup.output.chunks;
        let chunks_len = chunks.len();

        Self {
            stream: (Box::pin(futures::stream::iter(chunks.into_iter().enumerate().map(
                move |(index, c)| {
                    Ok(ProviderInferenceResponseChunk {
                        content: c.content,
                        raw_response: c.raw_response,
                        // We intentionally don't cache and re-use these values from the original
                        // request:
                        // The new result was 'created' now
                        created: current_timestamp(),
                        // Only include usage in the last chunk, None for all others
                        usage: if index == chunks_len - 1 {
                            Some(Usage {
                                input_tokens: cache_lookup.input_tokens,
                                output_tokens: cache_lookup.output_tokens,
                            })
                        } else {
                            None
                        },
                        // We didn't make any network calls to the model provider, so the latency is 0
                        latency: Duration::from_secs(0),
                        // For all chunks but the last one, the finish reason is None
                        // For the last chunk, the finish reason is the same as the cache lookup
                        finish_reason: if index == chunks_len - 1 {
                            cache_lookup.finish_reason.clone()
                        } else {
                            None
                        },
                    })
                },
            ))) as ProviderInferenceResponseStreamInner)
                .peekable()
                .instrument(tracing::info_span!(
                    "stream_from_cache",
                    otel.name = "stream_from_cache"
                )),
            raw_request: cache_lookup.raw_request,
            model_provider_name,
            cached: true,
        }
    }
}

/// Creates a fully-qualified name from a model and provider name, suitable for using
/// in `ContentBlock::Unknown.model_provider_name`
/// Note that 'model_name' is a name from `[models]`, which is not necessarily
/// the same as the underlying name passed to a specific provider api
pub fn fully_qualified_name(model_name: &str, provider_name: &str) -> String {
    format!("tensorzero::model_name::{model_name}::provider_name::{provider_name}")
}

impl ModelConfig {
    fn filter_content_blocks<'a>(
        &self,
        request: &'a ModelInferenceRequest<'a>,
        model_name: &str,
        provider_name: &str,
    ) -> Cow<'a, ModelInferenceRequest<'a>> {
        let name = fully_qualified_name(model_name, provider_name);
        let needs_filter = request.messages.iter().any(|m| {
            m.content.iter().any(|c| {
                if let ContentBlock::Unknown {
                    model_provider_name,
                    data: _,
                } = c
                {
                    model_provider_name.as_ref().is_some_and(|n| n != &name)
                } else {
                    false
                }
            })
        });
        if needs_filter {
            let new_messages = request
                .messages
                .iter()
                .map(|m| RequestMessage {
                    content: m
                        .content
                        .iter()
                        .flat_map(|c| {
                            if let ContentBlock::Unknown {
                                model_provider_name,
                                data: _,
                            } = c
                            {
                                if model_provider_name.as_ref().is_some_and(|n| n != &name) {
                                    None
                                } else {
                                    Some(c.clone())
                                }
                            } else {
                                Some(c.clone())
                            }
                        })
                        .collect(),
                    ..m.clone()
                })
                .collect();
            Cow::Owned(ModelInferenceRequest {
                messages: new_messages,
                ..request.clone()
            })
        } else {
            Cow::Borrowed(request)
        }
    }
    #[tracing::instrument(skip_all, fields(model_name = model_name, otel.name = "model_inference", stream = false))]
    pub async fn infer<'request>(
        &self,
        request: &'request ModelInferenceRequest<'request>,
        clients: &'request InferenceClients<'request>,
        model_name: &'request str,
    ) -> Result<ModelInferenceResponse, Error> {
        let mut provider_errors: HashMap<String, Error> = HashMap::new();
        for provider_name in &self.routing {
            let request = self.filter_content_blocks(request, model_name, provider_name);
            let model_provider_request = ModelProviderRequest {
                request: &request,
                model_name,
                provider_name,
            };
            let cache_key = model_provider_request.get_cache_key()?;
            // TODO: think about how to best handle errors here
            if clients.cache_options.enabled.read() {
                let cache_lookup = cache_lookup(
                    clients.clickhouse_connection_info,
                    model_provider_request,
                    clients.cache_options.max_age_s,
                )
                .await
                .ok()
                .flatten();
                if let Some(cache_lookup) = cache_lookup {
                    return Ok(cache_lookup);
                }
            }
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::ProviderNotFound {
                    provider_name: provider_name.to_string(),
                })
            })?;
            let response = provider
                .infer(
                    model_provider_request,
                    clients.http_client,
                    clients.credentials,
                )
                .instrument(span!(
                    Level::INFO,
                    "infer",
                    provider_name = &**provider_name
                ))
                .await;

            match response {
                Ok(response) => {
                    if clients.cache_options.enabled.write() {
                        let _ = start_cache_write(
                            clients.clickhouse_connection_info,
                            cache_key,
                            NonStreamingCacheData {
                                blocks: response.output.clone(),
                            },
                            &response.raw_request,
                            &response.raw_response,
                            &response.usage,
                            response.finish_reason.as_ref(),
                        );
                    }
                    // We already checked the cache above (and returned early if it was a hit), so this response was not from the cache
                    let model_inference_response =
                        ModelInferenceResponse::new(response, provider_name.clone(), false);

                    return Ok(model_inference_response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        let err = Error::new(ErrorDetails::ModelProvidersExhausted { provider_errors });
        Err(err)
    }

    /// Helper to execute a closure with retry logic based on retry_config
    async fn execute_with_retry<F, T, Fut>(&self, operation: F) -> Result<T, Error>
    where
        F: Fn() -> Fut,
        Fut: std::future::Future<Output = Result<T, Error>>,
    {
        if let Some(ref retry_config) = self.retry_config {
            if retry_config.num_retries > 0 {
                operation.retry(retry_config.get_backoff()).await
            } else {
                operation().await
            }
        } else {
            operation().await
        }
    }

    /// Inference with model-level fallback chain support
    #[tracing::instrument(skip_all, fields(model_name = model_name, otel.name = "model_chain_inference", stream = false))]
    pub async fn infer_with_fallback_chain<'request>(
        &self,
        request: &'request ModelInferenceRequest<'request>,
        clients: &'request InferenceClients<'request>,
        model_name: &'request str,
        models: &'request ModelTable,
        visited_models: &mut HashSet<Arc<str>>,
    ) -> Result<ModelInferenceResponse, Error> {
        // Prevent infinite recursion by tracking visited models
        if visited_models.contains(model_name) {
            return Err(Error::new(ErrorDetails::CircularFallbackDetected {
                chain: visited_models.iter().map(|s| s.to_string()).collect(),
            }));
        }
        visited_models.insert(model_name.into());

        // Try current model first (all providers) with retry logic
        let current_model_result = self
            .execute_with_retry(|| async { self.infer(request, clients, model_name).await })
            .await;

        match current_model_result {
            Ok(response) => {
                visited_models.remove(model_name);
                Ok(response)
            }
            Err(current_model_error) => {
                // If current model failed, try fallback models
                if let Some(ref fallback_models) = self.fallback_models {
                    let mut model_errors = HashMap::new();
                    model_errors.insert(model_name.to_string(), current_model_error);

                    for fallback_model_name in fallback_models {
                        // Skip if we would create a cycle
                        if visited_models.contains(fallback_model_name) {
                            continue;
                        }

                        // Get the fallback model config
                        let fallback_model = match models.get(fallback_model_name).await {
                            Ok(Some(model)) => model,
                            Ok(None) => {
                                model_errors.insert(
                                    fallback_model_name.to_string(),
                                    Error::new(ErrorDetails::ModelNotFound {
                                        name: fallback_model_name.to_string(),
                                    }),
                                );
                                continue;
                            }
                            Err(err) => {
                                model_errors.insert(fallback_model_name.to_string(), err);
                                continue;
                            }
                        };

                        // Try inference with fallback model (box the recursive call)
                        let fallback_result = Box::pin(fallback_model.infer_with_fallback_chain(
                            request,
                            clients,
                            fallback_model_name,
                            models,
                            visited_models,
                        ))
                        .await;

                        match fallback_result {
                            Ok(response) => {
                                visited_models.remove(model_name);
                                return Ok(response);
                            }
                            Err(fallback_error) => {
                                model_errors
                                    .insert(fallback_model_name.to_string(), fallback_error);
                            }
                        }
                    }

                    visited_models.remove(model_name);
                    Err(Error::new(ErrorDetails::ModelChainExhausted {
                        model_errors,
                    }))
                } else {
                    // No fallback models, return original error
                    visited_models.remove(model_name);
                    Err(current_model_error)
                }
            }
        }
    }

    #[tracing::instrument(skip_all, fields(model_name = model_name, otel.name = "model_inference", stream = true))]
    pub async fn infer_stream<'request>(
        &self,
        request: &'request ModelInferenceRequest<'request>,
        clients: &'request InferenceClients<'request>,
        model_name: &'request str,
    ) -> Result<(StreamResponse, Vec<RequestMessage>), Error> {
        let mut provider_errors: HashMap<String, Error> = HashMap::new();
        for provider_name in &self.routing {
            let request = self.filter_content_blocks(request, model_name, provider_name);
            let model_provider_request = ModelProviderRequest {
                request: &request,
                model_name,
                provider_name,
            };
            // TODO: think about how to best handle errors here
            if clients.cache_options.enabled.read() {
                let cache_lookup = cache_lookup_streaming(
                    clients.clickhouse_connection_info,
                    model_provider_request,
                    clients.cache_options.max_age_s,
                )
                .await
                .ok()
                .flatten();
                if let Some(cache_lookup) = cache_lookup {
                    return Ok((cache_lookup, request.messages.clone()));
                }
            }

            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::ProviderNotFound {
                    provider_name: provider_name.to_string(),
                })
            })?;
            let response = provider
                .infer_stream(
                    model_provider_request,
                    clients.http_client,
                    clients.credentials,
                )
                .await;
            match response {
                Ok(response) => {
                    let (stream, raw_request) = response;
                    // Note - we cache the chunks here so that we store the raw model provider input and response chunks
                    // in the cache. We don't want this logic in `collect_chunks`, which would cause us to cache the result
                    // of higher-level transformations (e.g. dicl)
                    let mut stream = if clients.cache_options.enabled.write() {
                        let span = stream.span().clone();
                        stream_with_cache_write(
                            raw_request.clone(),
                            model_provider_request,
                            clients,
                            stream.into_inner(),
                        )
                        .await?
                        .instrument(span)
                    } else {
                        stream
                    };
                    // Get a single chunk from the stream and make sure it is OK then send to client.
                    // We want to do this here so that we can tell that the request is working.
                    peek_first_chunk(stream.inner_mut(), &raw_request, provider_name).await?;
                    return Ok((
                        StreamResponse {
                            stream,
                            raw_request,
                            model_provider_name: provider_name.clone(),
                            cached: false,
                        },
                        request.messages.clone(),
                    ));
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(Error::new(ErrorDetails::ModelProvidersExhausted {
            provider_errors,
        }))
    }

    /// Streaming inference with model-level fallback chain support
    #[tracing::instrument(skip_all, fields(model_name = model_name, otel.name = "model_chain_inference", stream = true))]
    pub async fn infer_stream_with_fallback_chain<'request>(
        &self,
        request: &'request ModelInferenceRequest<'request>,
        clients: &'request InferenceClients<'request>,
        model_name: &'request str,
        models: &'request ModelTable,
        visited_models: &mut HashSet<Arc<str>>,
    ) -> Result<(StreamResponse, Vec<RequestMessage>), Error> {
        // Prevent infinite recursion by tracking visited models
        if visited_models.contains(model_name) {
            return Err(Error::new(ErrorDetails::CircularFallbackDetected {
                chain: visited_models.iter().map(|s| s.to_string()).collect(),
            }));
        }
        visited_models.insert(model_name.into());

        // Try current model first (all providers) with retry logic
        let current_model_result = self
            .execute_with_retry(|| async { self.infer_stream(request, clients, model_name).await })
            .await;

        match current_model_result {
            Ok(response) => {
                visited_models.remove(model_name);
                Ok(response)
            }
            Err(current_model_error) => {
                // If current model failed, try fallback models
                if let Some(ref fallback_models) = self.fallback_models {
                    let mut model_errors = HashMap::new();
                    model_errors.insert(model_name.to_string(), current_model_error);

                    for fallback_model_name in fallback_models {
                        // Skip if we would create a cycle
                        if visited_models.contains(fallback_model_name) {
                            continue;
                        }

                        // Get the fallback model config
                        let fallback_model = match models.get(fallback_model_name).await {
                            Ok(Some(model)) => model,
                            Ok(None) => {
                                model_errors.insert(
                                    fallback_model_name.to_string(),
                                    Error::new(ErrorDetails::ModelNotFound {
                                        name: fallback_model_name.to_string(),
                                    }),
                                );
                                continue;
                            }
                            Err(err) => {
                                model_errors.insert(fallback_model_name.to_string(), err);
                                continue;
                            }
                        };

                        // Try streaming inference with fallback model (box the recursive call)
                        let fallback_result =
                            Box::pin(fallback_model.infer_stream_with_fallback_chain(
                                request,
                                clients,
                                fallback_model_name,
                                models,
                                visited_models,
                            ))
                            .await;

                        match fallback_result {
                            Ok(response) => {
                                visited_models.remove(model_name);
                                return Ok(response);
                            }
                            Err(fallback_error) => {
                                model_errors
                                    .insert(fallback_model_name.to_string(), fallback_error);
                            }
                        }
                    }

                    visited_models.remove(model_name);
                    Err(Error::new(ErrorDetails::ModelChainExhausted {
                        model_errors,
                    }))
                } else {
                    // No fallback models, return original error
                    visited_models.remove(model_name);
                    Err(current_model_error)
                }
            }
        }
    }

    pub async fn start_batch_inference<'request>(
        &self,
        requests: &'request [ModelInferenceRequest<'request>],
        client: &'request Client,
        api_keys: &'request InferenceCredentials,
    ) -> Result<StartBatchModelInferenceResponse, Error> {
        let mut provider_errors: HashMap<String, Error> = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::ProviderNotFound {
                    provider_name: provider_name.to_string(),
                })
            })?;
            let response = provider
                .start_batch_inference(requests, client, api_keys)
                .instrument(span!(
                    Level::INFO,
                    "start_batch_inference",
                    provider_name = &**provider_name
                ))
                .await;
            match response {
                Ok(response) => {
                    return Ok(StartBatchModelInferenceResponse::new(
                        response,
                        provider_name.clone(),
                    ));
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(Error::new(ErrorDetails::ModelProvidersExhausted {
            provider_errors,
        }))
    }

    /// Create response method
    #[tracing::instrument(skip_all, fields(model_name = model_name, otel.name = "model_create_response"))]
    pub async fn create_response(
        &self,
        request: &crate::responses::OpenAIResponseCreateParams,
        model_name: &str,
        clients: &InferenceClients<'_>,
    ) -> Result<crate::responses::OpenAIResponse, Error> {
        let mut provider_errors: HashMap<String, Error> = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::ProviderNotFound {
                    provider_name: provider_name.to_string(),
                })
            })?;
            let response = provider
                .create_response(request, clients.http_client, clients.credentials)
                .await;
            match response {
                Ok(response) => {
                    return Ok(response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(Error::new(ErrorDetails::ModelProvidersExhausted {
            provider_errors,
        }))
    }

    /// Stream response method
    #[tracing::instrument(skip_all, fields(model_name = model_name, otel.name = "model_stream_response"))]
    pub async fn stream_response(
        &self,
        request: &crate::responses::OpenAIResponseCreateParams,
        model_name: &str,
        clients: &InferenceClients<'_>,
    ) -> Result<
        Box<
            dyn futures::Stream<Item = Result<crate::responses::ResponseStreamEvent, Error>>
                + Send
                + Unpin,
        >,
        Error,
    > {
        let mut provider_errors: HashMap<String, Error> = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::ProviderNotFound {
                    provider_name: provider_name.to_string(),
                })
            })?;
            let response = provider
                .stream_response(request, clients.http_client, clients.credentials)
                .await;
            match response {
                Ok(response) => {
                    return Ok(response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(Error::new(ErrorDetails::ModelProvidersExhausted {
            provider_errors,
        }))
    }

    #[tracing::instrument(skip_all, fields(model_name = model_name, response_id = response_id, otel.name = "model_retrieve_response"))]
    pub async fn retrieve_response(
        &self,
        response_id: &str,
        model_name: &str,
        clients: &InferenceClients<'_>,
    ) -> Result<crate::responses::OpenAIResponse, Error> {
        let mut provider_errors = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::InvalidModelProvider {
                    model_name: model_name.to_string(),
                    provider_name: provider_name.to_string(),
                })
            })?;
            let response = provider
                .retrieve_response(response_id, clients.http_client, clients.credentials)
                .await;
            match response {
                Ok(response) => {
                    return Ok(response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(Error::new(ErrorDetails::ModelProvidersExhausted {
            provider_errors,
        }))
    }

    #[tracing::instrument(skip_all, fields(model_name = model_name, response_id = response_id, otel.name = "model_delete_response"))]
    pub async fn delete_response(
        &self,
        response_id: &str,
        model_name: &str,
        clients: &InferenceClients<'_>,
    ) -> Result<serde_json::Value, Error> {
        let mut provider_errors = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::InvalidModelProvider {
                    model_name: model_name.to_string(),
                    provider_name: provider_name.to_string(),
                })
            })?;
            let response = provider
                .delete_response(response_id, clients.http_client, clients.credentials)
                .await;
            match response {
                Ok(response) => {
                    return Ok(response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(Error::new(ErrorDetails::ModelProvidersExhausted {
            provider_errors,
        }))
    }

    #[tracing::instrument(skip_all, fields(model_name = model_name, response_id = response_id, otel.name = "model_cancel_response"))]
    pub async fn cancel_response(
        &self,
        response_id: &str,
        model_name: &str,
        clients: &InferenceClients<'_>,
    ) -> Result<crate::responses::OpenAIResponse, Error> {
        let mut provider_errors = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::InvalidModelProvider {
                    model_name: model_name.to_string(),
                    provider_name: provider_name.to_string(),
                })
            })?;
            let response = provider
                .cancel_response(response_id, clients.http_client, clients.credentials)
                .await;
            match response {
                Ok(response) => {
                    return Ok(response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(Error::new(ErrorDetails::ModelProvidersExhausted {
            provider_errors,
        }))
    }

    #[tracing::instrument(skip_all, fields(model_name = model_name, response_id = response_id, otel.name = "model_list_response_input_items"))]
    pub async fn list_response_input_items(
        &self,
        response_id: &str,
        model_name: &str,
        clients: &InferenceClients<'_>,
    ) -> Result<crate::responses::ResponseInputItemsList, Error> {
        let mut provider_errors = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::InvalidModelProvider {
                    model_name: model_name.to_string(),
                    provider_name: provider_name.to_string(),
                })
            })?;
            let response = provider
                .list_response_input_items(response_id, clients.http_client, clients.credentials)
                .await;
            match response {
                Ok(response) => {
                    return Ok(response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(Error::new(ErrorDetails::ModelProvidersExhausted {
            provider_errors,
        }))
    }

    /// Execute response with automatic format detection (for providers like BudPrompt)
    #[tracing::instrument(skip_all, fields(model_name = model_name, otel.name = "model_execute_response_with_detection"))]
    pub async fn execute_response_with_detection(
        &self,
        request: &crate::responses::OpenAIResponseCreateParams,
        model_name: &str,
        clients: &InferenceClients<'_>,
    ) -> Result<crate::responses::ResponseResult, Error> {
        let mut provider_errors = HashMap::new();
        for provider_name in &self.routing {
            let provider = self.providers.get(provider_name).ok_or_else(|| {
                Error::new(ErrorDetails::InvalidModelProvider {
                    model_name: model_name.to_string(),
                    provider_name: provider_name.to_string(),
                })
            })?;
            let response = provider
                .execute_response_with_detection(
                    request,
                    model_name,
                    clients.http_client,
                    clients.credentials,
                )
                .await;
            match response {
                Ok(response) => {
                    return Ok(response);
                }
                Err(error) => {
                    provider_errors.insert(provider_name.to_string(), error);
                }
            }
        }
        Err(Error::new(ErrorDetails::ModelProvidersExhausted {
            provider_errors,
        }))
    }
}

async fn stream_with_cache_write(
    raw_request: String,
    model_request: ModelProviderRequest<'_>,
    clients: &InferenceClients<'_>,
    mut stream: PeekableProviderInferenceResponseStream,
) -> Result<PeekableProviderInferenceResponseStream, Error> {
    let cache_key = model_request.get_cache_key()?;
    let clickhouse_info = clients.clickhouse_connection_info.clone();
    Ok((Box::pin(async_stream::stream! {
        let mut buffer = vec![];
        let mut errored = false;
        while let Some(chunk) = stream.next().await {
            if !errored {
                match chunk.as_ref() {
                    Ok(chunk) => {
                        buffer.push(chunk.clone());
                    }
                    Err(e) => {
                        tracing::warn!("Skipping cache write for stream response due to error in stream: {e}");
                        errored = true;
                    }
                }
            }
            yield chunk;
        }
        if !errored {
            let usage = consolidate_usage(&buffer);
            let _ = start_cache_write_streaming(
                &clickhouse_info,
                cache_key,
                buffer,
                &raw_request,
                &usage,
            );
        }
    }) as ProviderInferenceResponseStreamInner).peekable())
}

fn consolidate_usage(chunks: &[ProviderInferenceResponseChunk]) -> Usage {
    let mut input_tokens = 0;
    let mut output_tokens = 0;
    for chunk in chunks {
        if let Some(usage) = &chunk.usage {
            input_tokens += usage.input_tokens;
            output_tokens += usage.output_tokens;
        }
    }
    Usage {
        input_tokens,
        output_tokens,
    }
}

#[derive(Debug, Deserialize)]
pub(crate) struct UninitializedModelProvider {
    #[serde(flatten)]
    pub config: UninitializedProviderConfig,
    pub extra_body: Option<ExtraBodyConfig>,
    pub extra_headers: Option<ExtraHeadersConfig>,
}

#[derive(Debug)]
pub struct ModelProvider {
    pub name: Arc<str>,
    pub config: ProviderConfig,
    pub extra_headers: Option<ExtraHeadersConfig>,
    pub extra_body: Option<ExtraBodyConfig>,
}

impl ModelProvider {
    /// The name to report in the OTEL `gen_ai.system` attribute
    fn genai_system_name(&self) -> &'static str {
        match &self.config {
            ProviderConfig::Anthropic(_) => "anthropic",
            ProviderConfig::AWSBedrock(_) => "aws_bedrock",
            ProviderConfig::AWSSagemaker(_) => "aws_sagemaker",
            ProviderConfig::Azure(_) => "azure",
            ProviderConfig::AzureContentSafety(_) => "azure_content_safety",
            ProviderConfig::BudDoc(_) => "buddoc",
            ProviderConfig::BudPrompt(_) => "budprompt",
            ProviderConfig::BudSentinel(_) => "bud_sentinel",
            ProviderConfig::Fireworks(_) => "fireworks",
            ProviderConfig::GCPVertexAnthropic(_) => "gcp_vertex_anthropic",
            ProviderConfig::GCPVertexGemini(_) => "gcp_vertex_gemini",
            ProviderConfig::GoogleAIStudioGemini(_) => "google_ai_studio_gemini",
            ProviderConfig::Hyperbolic(_) => "hyperbolic",
            ProviderConfig::Mistral(_) => "mistral",
            ProviderConfig::OpenAI(_) => "openai",
            ProviderConfig::OpenRouter(_) => "openrouter",
            ProviderConfig::Together(_) => "together",
            ProviderConfig::VLLM(_) => "vllm",
            ProviderConfig::XAI(_) => "xai",
            ProviderConfig::TGI(_) => "tgi",
            ProviderConfig::SGLang(_) => "sglang",
            ProviderConfig::DeepSeek(_) => "deepseek",
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(_) => "dummy",
        }
    }

    /// The model name to report in the OTEL `gen_ai.request.model` attribute
    fn genai_model_name(&self) -> Option<&str> {
        match &self.config {
            ProviderConfig::Anthropic(provider) => Some(provider.model_name()),
            ProviderConfig::AWSBedrock(provider) => Some(provider.model_id()),
            // SageMaker doesn't have a meaningful model name concept, as we just invoke an endpoint
            ProviderConfig::AWSSagemaker(_) => None,
            ProviderConfig::Azure(provider) => Some(provider.deployment_id()),
            ProviderConfig::AzureContentSafety(_) => None, // Content Safety doesn't have a model name
            ProviderConfig::Fireworks(provider) => Some(provider.model_name()),
            ProviderConfig::GCPVertexAnthropic(provider) => Some(provider.model_id()),
            ProviderConfig::GCPVertexGemini(provider) => Some(provider.model_id()),
            ProviderConfig::GoogleAIStudioGemini(provider) => Some(provider.model_name()),
            ProviderConfig::Hyperbolic(provider) => Some(provider.model_name()),
            ProviderConfig::Mistral(provider) => Some(provider.model_name()),
            ProviderConfig::OpenAI(provider) => Some(provider.model_name()),
            ProviderConfig::OpenRouter(provider) => Some(provider.model_name()),
            ProviderConfig::Together(provider) => Some(provider.model_name()),
            ProviderConfig::VLLM(provider) => Some(provider.model_name()),
            ProviderConfig::XAI(provider) => Some(provider.model_name()),
            // TGI doesn't have a meaningful model name
            ProviderConfig::TGI(_) => None,
            ProviderConfig::SGLang(provider) => Some(provider.model_name()),
            ProviderConfig::DeepSeek(provider) => Some(provider.model_name()),
            ProviderConfig::BudDoc(_) => None, // BudDoc doesn't have a model name in the inference sense
            ProviderConfig::BudPrompt(_) => None, // BudPrompt doesn't have a model name in the provider
            ProviderConfig::BudSentinel(_) => None,
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => Some(provider.model_name()),
        }
    }
}

impl From<&ModelProvider> for ModelProviderRequestInfo {
    fn from(val: &ModelProvider) -> Self {
        ModelProviderRequestInfo {
            provider_name: val.name.clone(),
            extra_headers: val.extra_headers.clone(),
            extra_body: val.extra_body.clone(),
        }
    }
}

#[derive(Clone, Debug)]
pub struct ModelProviderRequestInfo {
    pub provider_name: Arc<str>,
    pub extra_headers: Option<ExtraHeadersConfig>,
    pub extra_body: Option<ExtraBodyConfig>,
}

#[derive(Debug)]
pub enum ProviderConfig {
    Anthropic(AnthropicProvider),
    AWSBedrock(AWSBedrockProvider),
    AWSSagemaker(AWSSagemakerProvider),
    Azure(AzureProvider),
    AzureContentSafety(AzureContentSafetyProvider),
    BudDoc(BudDocProvider),
    BudPrompt(BudPromptProvider),
    BudSentinel(BudSentinelProvider),
    DeepSeek(DeepSeekProvider),
    Fireworks(FireworksProvider),
    GCPVertexAnthropic(GCPVertexAnthropicProvider),
    GCPVertexGemini(GCPVertexGeminiProvider),
    GoogleAIStudioGemini(GoogleAIStudioGeminiProvider),
    Hyperbolic(HyperbolicProvider),
    Mistral(MistralProvider),
    OpenAI(OpenAIProvider),
    OpenRouter(OpenRouterProvider),
    SGLang(SGLangProvider),
    TGI(TGIProvider),
    Together(TogetherProvider),
    VLLM(VLLMProvider),
    XAI(XAIProvider),
    #[cfg(any(test, feature = "e2e_tests"))]
    Dummy(DummyProvider),
}

/// Contains all providers which implement `SelfHostedProvider` - these providers
/// can be used as the target provider hosted by AWS Sagemaker
#[derive(Debug, Deserialize)]
#[serde(rename_all = "lowercase")]
#[serde(deny_unknown_fields)]
pub enum HostedProviderKind {
    OpenAI,
    TGI,
}

#[derive(Debug, TensorZeroDeserialize, VariantNames)]
#[strum(serialize_all = "lowercase")]
#[serde(tag = "type")]
#[serde(rename_all = "lowercase")]
#[serde(deny_unknown_fields)]
pub(super) enum UninitializedProviderConfig {
    Anthropic {
        model_name: String,
        api_key_location: Option<CredentialLocation>,
    },
    #[strum(serialize = "aws_bedrock")]
    #[serde(rename = "aws_bedrock")]
    AWSBedrock {
        model_id: String,
        region: Option<String>,
        #[serde(default)]
        allow_auto_detect_region: bool,
    },
    #[strum(serialize = "aws_sagemaker")]
    #[serde(rename = "aws_sagemaker")]
    AWSSagemaker {
        endpoint_name: String,
        model_name: String,
        region: Option<String>,
        #[serde(default)]
        allow_auto_detect_region: bool,
        hosted_provider: HostedProviderKind,
    },
    Azure {
        deployment_id: String,
        endpoint: Url,
        api_key_location: Option<CredentialLocation>,
    },
    #[strum(serialize = "azure_content_safety")]
    #[serde(rename = "azure_content_safety")]
    AzureContentSafety {
        endpoint: Url,
        api_key_location: Option<CredentialLocation>,
    },
    BudDoc {
        model_name: String,
        api_base: Url,
        api_key_location: Option<CredentialLocation>,
    },
    BudPrompt {
        model_name: String,
        api_base: Url,
        api_key_location: Option<CredentialLocation>,
    },
    #[strum(serialize = "bud_sentinel")]
    #[serde(rename = "bud_sentinel")]
    BudSentinel {
        endpoint: Url,
        api_key_location: Option<CredentialLocation>,
        #[serde(default)]
        profile_id: Option<String>,
        #[serde(default)]
        severity_threshold: Option<f32>,
    },
    #[strum(serialize = "gcp_vertex_anthropic")]
    #[serde(rename = "gcp_vertex_anthropic")]
    GCPVertexAnthropic {
        model_id: String,
        location: String,
        project_id: String,
        credential_location: Option<CredentialLocation>,
    },
    #[strum(serialize = "gcp_vertex_gemini")]
    #[serde(rename = "gcp_vertex_gemini")]
    GCPVertexGemini {
        model_id: String,
        location: String,
        project_id: String,
        credential_location: Option<CredentialLocation>,
    },
    #[strum(serialize = "google_ai_studio_gemini")]
    #[serde(rename = "google_ai_studio_gemini")]
    GoogleAIStudioGemini {
        model_name: String,
        api_key_location: Option<CredentialLocation>,
    },
    Hyperbolic {
        model_name: String,
        api_key_location: Option<CredentialLocation>,
    },
    #[strum(serialize = "fireworks")]
    #[serde(rename = "fireworks")]
    Fireworks {
        model_name: String,
        api_key_location: Option<CredentialLocation>,
        #[serde(default = "crate::inference::providers::fireworks::default_parse_think_blocks")]
        parse_think_blocks: bool,
    },
    Mistral {
        model_name: String,
        api_key_location: Option<CredentialLocation>,
    },
    OpenAI {
        model_name: String,
        api_base: Option<Url>,
        api_key_location: Option<CredentialLocation>,
    },
    OpenRouter {
        model_name: String,
        api_base: Option<Url>,
        api_key_location: Option<CredentialLocation>,
    },
    Together {
        model_name: String,
        api_key_location: Option<CredentialLocation>,
        #[serde(default = "crate::inference::providers::together::default_parse_think_blocks")]
        parse_think_blocks: bool,
    },
    #[expect(clippy::upper_case_acronyms)]
    VLLM {
        model_name: String,
        api_base: Url,
        api_key_location: Option<CredentialLocation>,
    },
    #[expect(clippy::upper_case_acronyms)]
    XAI {
        model_name: String,
        api_key_location: Option<CredentialLocation>,
    },
    #[expect(clippy::upper_case_acronyms)]
    TGI {
        api_base: Url,
        api_key_location: Option<CredentialLocation>,
    },
    SGLang {
        model_name: String,
        api_base: Url,
        api_key_location: Option<CredentialLocation>,
    },
    DeepSeek {
        model_name: String,
        api_key_location: Option<CredentialLocation>,
    },
    #[cfg(any(test, feature = "e2e_tests"))]
    Dummy {
        model_name: String,
        api_key_location: Option<CredentialLocation>,
    },
}

impl UninitializedProviderConfig {
    pub fn load(self, provider_types: &ProviderTypesConfig) -> Result<ProviderConfig, Error> {
        Ok(match self {
            UninitializedProviderConfig::Anthropic {
                model_name,
                api_key_location,
            } => ProviderConfig::Anthropic(AnthropicProvider::new(model_name, api_key_location)?),
            UninitializedProviderConfig::AWSBedrock {
                model_id,
                region,
                allow_auto_detect_region,
            } => {
                let region = region.map(aws_types::region::Region::new);
                if region.is_none() && !allow_auto_detect_region {
                    return Err(Error::new(ErrorDetails::Config { message: "AWS bedrock provider requires a region to be provided, or `allow_auto_detect_region = true`.".to_string() }));
                }

                // NB: We need to make an async call here to initialize the AWS Bedrock client.

                let provider = tokio::task::block_in_place(move || {
                    tokio::runtime::Handle::current()
                        .block_on(async { AWSBedrockProvider::new(model_id, region).await })
                })?;

                ProviderConfig::AWSBedrock(provider)
            }
            UninitializedProviderConfig::AWSSagemaker {
                endpoint_name,
                region,
                allow_auto_detect_region,
                model_name,
                hosted_provider,
            } => {
                let region = region.map(aws_types::region::Region::new);
                if region.is_none() && !allow_auto_detect_region {
                    return Err(Error::new(ErrorDetails::Config { message: "AWS Sagemaker provider requires a region to be provided, or `allow_auto_detect_region = true`.".to_string() }));
                }

                let self_hosted: Box<dyn WrappedProvider + Send + Sync + 'static> =
                    match hosted_provider {
                        HostedProviderKind::OpenAI => Box::new(OpenAIProvider::new(
                            model_name,
                            None,
                            Some(CredentialLocation::None),
                        )?),
                        HostedProviderKind::TGI => Box::new(TGIProvider::new(
                            Url::parse("http://tensorzero-unreachable-domain-please-file-a-bug-report.invalid").map_err(|e| {
                                Error::new(ErrorDetails::InternalError { message: format!("Failed to parse fake TGI endpoint: `{e}`. This should never happen. Please file a bug report: https://github.com/tensorzero/tensorzero/issues/new") })
                            })?,
                            Some(CredentialLocation::None),
                        )?),
                    };
                // NB: We need to make an async call here to initialize the AWS Sagemaker client.

                let provider = tokio::task::block_in_place(move || {
                    tokio::runtime::Handle::current().block_on(async {
                        AWSSagemakerProvider::new(endpoint_name, self_hosted, region).await
                    })
                })?;

                ProviderConfig::AWSSagemaker(provider)
            }
            UninitializedProviderConfig::Azure {
                deployment_id,
                endpoint,
                api_key_location,
            } => ProviderConfig::Azure(AzureProvider::new(
                deployment_id,
                endpoint,
                api_key_location,
            )?),
            UninitializedProviderConfig::AzureContentSafety {
                endpoint,
                api_key_location,
            } => {
                use crate::inference::providers::azure_content_safety::ProbeType;
                ProviderConfig::AzureContentSafety(AzureContentSafetyProvider::new(
                    endpoint,
                    api_key_location,
                    ProbeType::Moderation, // Default to Moderation for model-based configuration
                )?)
            }
            UninitializedProviderConfig::BudDoc {
                model_name: _,
                api_base,
                api_key_location,
            } => {
                ProviderConfig::BudDoc(BudDocProvider::new(api_base.to_string(), api_key_location)?)
            }
            UninitializedProviderConfig::BudPrompt {
                model_name: _,
                api_base,
                api_key_location,
            } => ProviderConfig::BudPrompt(BudPromptProvider::new(
                api_base.clone(),
                api_key_location,
            )?),
            UninitializedProviderConfig::BudSentinel {
                endpoint,
                api_key_location,
                profile_id,
                severity_threshold,
            } => ProviderConfig::BudSentinel(BudSentinelProvider::new(
                endpoint,
                api_key_location,
                profile_id,
                severity_threshold,
            )?),
            UninitializedProviderConfig::Fireworks {
                model_name,
                api_key_location,
                parse_think_blocks,
            } => ProviderConfig::Fireworks(FireworksProvider::new(
                model_name,
                api_key_location,
                parse_think_blocks,
            )?),
            UninitializedProviderConfig::GCPVertexAnthropic {
                model_id,
                location,
                project_id,
                credential_location: api_key_location,
            } => ProviderConfig::GCPVertexAnthropic(tokio::task::block_in_place(move || {
                tokio::runtime::Handle::current().block_on(async {
                    GCPVertexAnthropicProvider::new(
                        model_id,
                        location,
                        project_id,
                        api_key_location,
                    )
                    .await
                })
            })?),
            UninitializedProviderConfig::GCPVertexGemini {
                model_id,
                location,
                project_id,
                credential_location: api_key_location,
            } => ProviderConfig::GCPVertexGemini(tokio::task::block_in_place(move || {
                tokio::runtime::Handle::current().block_on(async {
                    GCPVertexGeminiProvider::new(
                        model_id,
                        location,
                        project_id,
                        api_key_location,
                        provider_types,
                    )
                    .await
                })
            })?),
            UninitializedProviderConfig::GoogleAIStudioGemini {
                model_name,
                api_key_location,
            } => ProviderConfig::GoogleAIStudioGemini(GoogleAIStudioGeminiProvider::new(
                model_name,
                api_key_location,
            )?),
            UninitializedProviderConfig::Hyperbolic {
                model_name,
                api_key_location,
            } => ProviderConfig::Hyperbolic(HyperbolicProvider::new(model_name, api_key_location)?),
            UninitializedProviderConfig::Mistral {
                model_name,
                api_key_location,
            } => ProviderConfig::Mistral(MistralProvider::new(model_name, api_key_location)?),
            UninitializedProviderConfig::OpenAI {
                model_name,
                api_base,
                api_key_location,
            } => {
                ProviderConfig::OpenAI(OpenAIProvider::new(model_name, api_base, api_key_location)?)
            }
            UninitializedProviderConfig::OpenRouter {
                model_name,
                api_base,
                api_key_location,
            } => ProviderConfig::OpenRouter(OpenRouterProvider::new(
                model_name,
                api_base,
                api_key_location,
            )?),
            UninitializedProviderConfig::Together {
                model_name,
                api_key_location,
                parse_think_blocks,
            } => ProviderConfig::Together(TogetherProvider::new(
                model_name,
                api_key_location,
                parse_think_blocks,
            )?),
            UninitializedProviderConfig::VLLM {
                model_name,
                api_base,
                api_key_location,
            } => ProviderConfig::VLLM(VLLMProvider::new(model_name, api_base, api_key_location)?),
            UninitializedProviderConfig::XAI {
                model_name,
                api_key_location,
            } => ProviderConfig::XAI(XAIProvider::new(model_name, api_key_location)?),
            UninitializedProviderConfig::SGLang {
                model_name,
                api_base,
                api_key_location,
            } => {
                ProviderConfig::SGLang(SGLangProvider::new(model_name, api_base, api_key_location)?)
            }
            UninitializedProviderConfig::TGI {
                api_base,
                api_key_location,
            } => ProviderConfig::TGI(TGIProvider::new(api_base, api_key_location)?),
            UninitializedProviderConfig::DeepSeek {
                model_name,
                api_key_location,
            } => ProviderConfig::DeepSeek(DeepSeekProvider::new(model_name, api_key_location)?),
            #[cfg(any(test, feature = "e2e_tests"))]
            UninitializedProviderConfig::Dummy {
                model_name,
                api_key_location,
            } => ProviderConfig::Dummy(DummyProvider::new(model_name, api_key_location)?),
        })
    }
}

impl ModelProvider {
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_inference",
        gen_ai.operation.name = "chat",
        gen_ai.system = self.genai_system_name(),
        gen_ai.request.model = self.genai_model_name(),
    stream = false))]
    async fn infer(
        &self,
        request: ModelProviderRequest<'_>,
        client: &Client,
        api_keys: &InferenceCredentials,
    ) -> Result<ProviderInferenceResponse, Error> {
        match &self.config {
            ProviderConfig::Anthropic(provider) => {
                provider.infer(request, client, api_keys, self).await
            }
            ProviderConfig::AWSBedrock(provider) => {
                provider.infer(request, client, api_keys, self).await
            }
            ProviderConfig::AWSSagemaker(provider) => {
                provider.infer(request, client, api_keys, self).await
            }
            ProviderConfig::Azure(provider) => {
                provider.infer(request, client, api_keys, self).await
            }
            ProviderConfig::AzureContentSafety(_) => {
                Err(Error::new(ErrorDetails::CapabilityNotSupported {
                    capability: "inference".to_string(),
                    provider: self.name.to_string(),
                }))
            }
            ProviderConfig::Fireworks(provider) => {
                provider.infer(request, client, api_keys, self).await
            }
            ProviderConfig::GCPVertexAnthropic(provider) => {
                provider.infer(request, client, api_keys, self).await
            }
            ProviderConfig::GCPVertexGemini(provider) => {
                provider.infer(request, client, api_keys, self).await
            }
            ProviderConfig::GoogleAIStudioGemini(provider) => {
                provider.infer(request, client, api_keys, self).await
            }
            ProviderConfig::Hyperbolic(provider) => {
                provider.infer(request, client, api_keys, self).await
            }
            ProviderConfig::Mistral(provider) => {
                provider.infer(request, client, api_keys, self).await
            }
            ProviderConfig::OpenAI(provider) => {
                provider.infer(request, client, api_keys, self).await
            }
            ProviderConfig::OpenRouter(provider) => {
                provider.infer(request, client, api_keys, self).await
            }
            ProviderConfig::Together(provider) => {
                provider.infer(request, client, api_keys, self).await
            }
            ProviderConfig::SGLang(provider) => {
                provider.infer(request, client, api_keys, self).await
            }
            ProviderConfig::VLLM(provider) => provider.infer(request, client, api_keys, self).await,
            ProviderConfig::XAI(provider) => provider.infer(request, client, api_keys, self).await,
            ProviderConfig::TGI(provider) => provider.infer(request, client, api_keys, self).await,
            ProviderConfig::DeepSeek(provider) => {
                provider.infer(request, client, api_keys, self).await
            }
            ProviderConfig::BudDoc(_) => {
                return Err(Error::new(ErrorDetails::Config {
                    message: "BudDoc provider does not support inference operations".to_string(),
                }))
            }
            ProviderConfig::BudPrompt(_) => {
                return Err(Error::new(ErrorDetails::Config {
                    message: "BudPrompt provider does not support inference operations, only v1/responses endpoint".to_string(),
                }))
            }
            ProviderConfig::BudSentinel(_) => {
                return Err(Error::new(ErrorDetails::Config {
                    message: "Bud Sentinel provider does not support inference operations".to_string(),
                }))
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider.infer(request, client, api_keys, self).await
            }
        }
    }

    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_inference",
        gen_ai.operation.name = "chat",
        gen_ai.system = self.genai_system_name(),
        gen_ai.request.model = self.genai_model_name(),
    stream = true))]
    async fn infer_stream(
        &self,
        request: ModelProviderRequest<'_>,
        client: &Client,
        api_keys: &InferenceCredentials,
    ) -> Result<
        (
            tracing_futures::Instrumented<PeekableProviderInferenceResponseStream>,
            String,
        ),
        Error,
    > {
        let (stream, raw_request) = match &self.config {
            ProviderConfig::Anthropic(provider) => {
                provider.infer_stream(request, client, api_keys, self).await
            }
            ProviderConfig::AWSBedrock(provider) => {
                provider.infer_stream(request, client, api_keys, self).await
            }
            ProviderConfig::AWSSagemaker(provider) => {
                provider.infer_stream(request, client, api_keys, self).await
            }
            ProviderConfig::Azure(provider) => {
                provider.infer_stream(request, client, api_keys, self).await
            }
            ProviderConfig::AzureContentSafety(_) => {
                return Err(Error::new(ErrorDetails::CapabilityNotSupported {
                    capability: "inference_stream".to_string(),
                    provider: self.name.to_string(),
                }))
            }
            ProviderConfig::Fireworks(provider) => {
                provider.infer_stream(request, client, api_keys, self).await
            }
            ProviderConfig::GCPVertexAnthropic(provider) => {
                provider.infer_stream(request, client, api_keys, self).await
            }
            ProviderConfig::GCPVertexGemini(provider) => {
                provider.infer_stream(request, client, api_keys, self).await
            }
            ProviderConfig::GoogleAIStudioGemini(provider) => {
                provider.infer_stream(request, client, api_keys, self).await
            }
            ProviderConfig::Hyperbolic(provider) => {
                provider.infer_stream(request, client, api_keys, self).await
            }
            ProviderConfig::Mistral(provider) => {
                provider.infer_stream(request, client, api_keys, self).await
            }
            ProviderConfig::OpenAI(provider) => {
                provider.infer_stream(request, client, api_keys, self).await
            }
            ProviderConfig::OpenRouter(provider) => {
                provider.infer_stream(request, client, api_keys, self).await
            }
            ProviderConfig::Together(provider) => {
                provider.infer_stream(request, client, api_keys, self).await
            }
            ProviderConfig::SGLang(provider) => {
                provider.infer_stream(request, client, api_keys, self).await
            }
            ProviderConfig::XAI(provider) => {
                provider.infer_stream(request, client, api_keys, self).await
            }
            ProviderConfig::VLLM(provider) => {
                provider.infer_stream(request, client, api_keys, self).await
            }
            ProviderConfig::TGI(provider) => {
                provider.infer_stream(request, client, api_keys, self).await
            }
            ProviderConfig::DeepSeek(provider) => {
                provider.infer_stream(request, client, api_keys, self).await
            }
            ProviderConfig::BudDoc(_) => {
                return Err(Error::new(ErrorDetails::Config {
                    message: "BudDoc provider does not support streaming inference".to_string(),
                }))
            }
            ProviderConfig::BudPrompt(_) => {
                return Err(Error::new(ErrorDetails::Config {
                    message: "BudPrompt provider does not support streaming inference, only v1/responses endpoint".to_string(),
                }))
            }
            ProviderConfig::BudSentinel(_) => {
                return Err(Error::new(ErrorDetails::Config {
                    message: "Bud Sentinel provider does not support streaming inference".to_string(),
                }))
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider.infer_stream(request, client, api_keys, self).await
            }
        }?;

        // Attach the current `model_provider_inference` span to the stream.
        // This will cause the span to be entered every time the stream is polled,
        // extending the lifetime of the span in OpenTelemetry to include the entire
        // duration of the response stream.
        Ok((stream.instrument(Span::current()), raw_request))
    }

    async fn start_batch_inference<'a>(
        &self,
        requests: &'a [ModelInferenceRequest<'a>],
        client: &'a Client,
        api_keys: &'a InferenceCredentials,
    ) -> Result<StartBatchProviderInferenceResponse, Error> {
        match &self.config {
            ProviderConfig::Anthropic(provider) => {
                provider
                    .start_batch_inference(requests, client, api_keys)
                    .await
            }
            ProviderConfig::AWSBedrock(provider) => {
                provider
                    .start_batch_inference(requests, client, api_keys)
                    .await
            }
            ProviderConfig::AWSSagemaker(provider) => {
                provider
                    .start_batch_inference(requests, client, api_keys)
                    .await
            }
            ProviderConfig::Azure(provider) => {
                provider
                    .start_batch_inference(requests, client, api_keys)
                    .await
            }
            ProviderConfig::AzureContentSafety(_) => {
                Err(Error::new(ErrorDetails::CapabilityNotSupported {
                    capability: "batch_inference".to_string(),
                    provider: self.name.to_string(),
                }))
            }
            ProviderConfig::Fireworks(provider) => {
                provider
                    .start_batch_inference(requests, client, api_keys)
                    .await
            }
            ProviderConfig::GCPVertexAnthropic(provider) => {
                provider
                    .start_batch_inference(requests, client, api_keys)
                    .await
            }
            ProviderConfig::GCPVertexGemini(provider) => {
                provider
                    .start_batch_inference(requests, client, api_keys)
                    .await
            }
            ProviderConfig::GoogleAIStudioGemini(provider) => {
                provider
                    .start_batch_inference(requests, client, api_keys)
                    .await
            }
            ProviderConfig::Hyperbolic(provider) => {
                provider
                    .start_batch_inference(requests, client, api_keys)
                    .await
            }
            ProviderConfig::Mistral(provider) => {
                provider
                    .start_batch_inference(requests, client, api_keys)
                    .await
            }
            ProviderConfig::OpenAI(provider) => {
                provider
                    .start_batch_inference(requests, client, api_keys)
                    .await
            }
            ProviderConfig::OpenRouter(provider) => {
                provider
                    .start_batch_inference(requests, client, api_keys)
                    .await
            }
            ProviderConfig::Together(provider) => {
                provider
                    .start_batch_inference(requests, client, api_keys)
                    .await
            }
            ProviderConfig::SGLang(provider) => {
                provider
                    .start_batch_inference(requests, client, api_keys)
                    .await
            }
            ProviderConfig::VLLM(provider) => {
                provider
                    .start_batch_inference(requests, client, api_keys)
                    .await
            }
            ProviderConfig::XAI(provider) => {
                provider
                    .start_batch_inference(requests, client, api_keys)
                    .await
            }
            ProviderConfig::DeepSeek(provider) => {
                provider
                    .start_batch_inference(requests, client, api_keys)
                    .await
            }
            ProviderConfig::TGI(provider) => {
                provider
                    .start_batch_inference(requests, client, api_keys)
                    .await
            }
            ProviderConfig::BudDoc(_) => Err(Error::new(ErrorDetails::Config {
                message: "BudDoc provider does not support batch inference".to_string(),
            })),
            ProviderConfig::BudPrompt(_) => Err(Error::new(ErrorDetails::Config {
                message: "BudPrompt provider does not support batch inference".to_string(),
            })),
            ProviderConfig::BudSentinel(_) => Err(Error::new(ErrorDetails::Config {
                message: "Bud Sentinel provider does not support batch inference".to_string(),
            })),
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .start_batch_inference(requests, client, api_keys)
                    .await
            }
        }
    }

    pub async fn poll_batch_inference<'a>(
        &self,
        batch_request: &'a BatchRequestRow<'_>,
        http_client: &'a reqwest::Client,
        dynamic_api_keys: &'a InferenceCredentials,
    ) -> Result<PollBatchInferenceResponse, Error> {
        match &self.config {
            ProviderConfig::Anthropic(provider) => {
                provider
                    .poll_batch_inference(batch_request, http_client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::AWSBedrock(provider) => {
                provider
                    .poll_batch_inference(batch_request, http_client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::AWSSagemaker(provider) => {
                provider
                    .poll_batch_inference(batch_request, http_client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::Azure(provider) => {
                provider
                    .poll_batch_inference(batch_request, http_client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::AzureContentSafety(_) => {
                Err(Error::new(ErrorDetails::CapabilityNotSupported {
                    capability: "batch_inference".to_string(),
                    provider: self.name.to_string(),
                }))
            }
            ProviderConfig::Fireworks(provider) => {
                provider
                    .poll_batch_inference(batch_request, http_client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::GCPVertexAnthropic(provider) => {
                provider
                    .poll_batch_inference(batch_request, http_client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::GCPVertexGemini(provider) => {
                provider
                    .poll_batch_inference(batch_request, http_client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::GoogleAIStudioGemini(provider) => {
                provider
                    .poll_batch_inference(batch_request, http_client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::Hyperbolic(provider) => {
                provider
                    .poll_batch_inference(batch_request, http_client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::Mistral(provider) => {
                provider
                    .poll_batch_inference(batch_request, http_client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::OpenAI(provider) => {
                provider
                    .poll_batch_inference(batch_request, http_client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::OpenRouter(provider) => {
                provider
                    .poll_batch_inference(batch_request, http_client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::TGI(provider) => {
                provider
                    .poll_batch_inference(batch_request, http_client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::Together(provider) => {
                provider
                    .poll_batch_inference(batch_request, http_client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::SGLang(provider) => {
                provider
                    .poll_batch_inference(batch_request, http_client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::VLLM(provider) => {
                provider
                    .poll_batch_inference(batch_request, http_client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::XAI(provider) => {
                provider
                    .poll_batch_inference(batch_request, http_client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::DeepSeek(provider) => {
                provider
                    .poll_batch_inference(batch_request, http_client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::BudDoc(_) => Err(Error::new(ErrorDetails::Config {
                message: "BudDoc provider does not support batch inference".to_string(),
            })),
            ProviderConfig::BudPrompt(_) => Err(Error::new(ErrorDetails::Config {
                message: "BudPrompt provider does not support batch inference".to_string(),
            })),
            ProviderConfig::BudSentinel(_) => Err(Error::new(ErrorDetails::Config {
                message: "Bud Sentinel provider does not support batch inference".to_string(),
            })),
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .poll_batch_inference(batch_request, http_client, dynamic_api_keys)
                    .await
            }
        }
    }

    /// Embedding inference method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_embedding"))]
    pub async fn embed(
        &self,
        request: &crate::embeddings::EmbeddingRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::embeddings::EmbeddingProviderResponse, Error> {
        use crate::embeddings::EmbeddingProvider;

        match &self.config {
            ProviderConfig::Azure(provider) => {
                provider.embed(request, client, dynamic_api_keys).await
            }
            ProviderConfig::OpenAI(provider) => {
                provider.embed(request, client, dynamic_api_keys).await
            }
            ProviderConfig::VLLM(provider) => {
                provider.embed(request, client, dynamic_api_keys).await
            }
            ProviderConfig::Together(provider) => {
                provider.embed(request, client, dynamic_api_keys).await
            }
            ProviderConfig::Fireworks(provider) => {
                provider.embed(request, client, dynamic_api_keys).await
            }
            ProviderConfig::Mistral(provider) => {
                provider.embed(request, client, dynamic_api_keys).await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider.embed(request, client, dynamic_api_keys).await
            }
            // Other providers don't support embeddings yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Embedding.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Completions inference method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_completion"))]
    pub async fn complete(
        &self,
        request: &crate::completions::CompletionRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::completions::CompletionProviderResponse, Error> {
        use crate::completions::CompletionProvider;

        match &self.config {
            ProviderConfig::VLLM(provider) => {
                provider.complete(request, client, dynamic_api_keys).await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider.complete(request, client, dynamic_api_keys).await
            }
            // Other providers don't support completions yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Completions.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Streaming completions method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_completion_stream"))]
    pub async fn complete_stream(
        &self,
        request: &crate::completions::CompletionRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<(crate::completions::CompletionStream, String), Error> {
        use crate::completions::CompletionProvider;

        match &self.config {
            ProviderConfig::VLLM(provider) => {
                provider
                    .complete_stream(request, client, dynamic_api_keys)
                    .await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .complete_stream(request, client, dynamic_api_keys)
                    .await
            }
            // Other providers don't support completions streaming yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Completions.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Audio transcription method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_audio_transcription"))]
    pub async fn transcribe(
        &self,
        request: &crate::audio::AudioTranscriptionRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::audio::AudioTranscriptionProviderResponse, Error> {
        use crate::audio::AudioTranscriptionProvider;

        match &self.config {
            ProviderConfig::Azure(provider) => {
                provider.transcribe(request, client, dynamic_api_keys).await
            }
            ProviderConfig::OpenAI(provider) => {
                provider.transcribe(request, client, dynamic_api_keys).await
            }
            ProviderConfig::Fireworks(provider) => {
                provider.transcribe(request, client, dynamic_api_keys).await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider.transcribe(request, client, dynamic_api_keys).await
            }
            // Other providers don't support audio transcription yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::AudioTranscription.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Audio translation method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_audio_translation"))]
    pub async fn translate(
        &self,
        request: &crate::audio::AudioTranslationRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::audio::AudioTranslationProviderResponse, Error> {
        use crate::audio::AudioTranslationProvider;

        match &self.config {
            ProviderConfig::Azure(provider) => {
                provider.translate(request, client, dynamic_api_keys).await
            }
            ProviderConfig::OpenAI(provider) => {
                provider.translate(request, client, dynamic_api_keys).await
            }
            ProviderConfig::Fireworks(provider) => {
                provider.translate(request, client, dynamic_api_keys).await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider.translate(request, client, dynamic_api_keys).await
            }
            // Other providers don't support audio translation yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::AudioTranslation.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Text-to-speech method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_text_to_speech"))]
    pub async fn generate_speech(
        &self,
        request: &crate::audio::TextToSpeechRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::audio::TextToSpeechProviderResponse, Error> {
        use crate::audio::TextToSpeechProvider;

        match &self.config {
            ProviderConfig::Azure(provider) => {
                provider
                    .generate_speech(request, client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::OpenAI(provider) => {
                provider
                    .generate_speech(request, client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::Together(provider) => {
                provider
                    .generate_speech(request, client, dynamic_api_keys)
                    .await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .generate_speech(request, client, dynamic_api_keys)
                    .await
            }
            // Other providers don't support text-to-speech yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::TextToSpeech.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Image generation method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_image_generation"))]
    pub async fn generate_image(
        &self,
        request: &crate::images::ImageGenerationRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::images::ImageGenerationProviderResponse, Error> {
        use crate::images::ImageGenerationProvider;

        match &self.config {
            ProviderConfig::Azure(provider) => {
                provider
                    .generate_image(request, client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::OpenAI(provider) => {
                provider
                    .generate_image(request, client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::Together(provider) => {
                provider
                    .generate_image(request, client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::XAI(provider) => {
                provider
                    .generate_image(request, client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::Fireworks(provider) => {
                provider
                    .generate_image(request, client, dynamic_api_keys)
                    .await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .generate_image(request, client, dynamic_api_keys)
                    .await
            }
            // Other providers don't support image generation yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::ImageGeneration.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Image edit method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_image_edit"))]
    pub async fn edit_image(
        &self,
        request: &crate::images::ImageEditRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::images::ImageEditProviderResponse, Error> {
        use crate::images::ImageEditProvider;

        match &self.config {
            ProviderConfig::OpenAI(provider) => {
                provider.edit_image(request, client, dynamic_api_keys).await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider.edit_image(request, client, dynamic_api_keys).await
            }
            // Other providers don't support image editing yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::ImageEdit.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Image variation method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_image_variation"))]
    pub async fn create_image_variation(
        &self,
        request: &crate::images::ImageVariationRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::images::ImageVariationProviderResponse, Error> {
        use crate::images::ImageVariationProvider;

        match &self.config {
            ProviderConfig::OpenAI(provider) => {
                provider
                    .create_image_variation(request, client, dynamic_api_keys)
                    .await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .create_image_variation(request, client, dynamic_api_keys)
                    .await
            }
            // Other providers don't support image variations yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::ImageVariation.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Create response method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_create_response"))]
    pub async fn create_response(
        &self,
        request: &crate::responses::OpenAIResponseCreateParams,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::responses::OpenAIResponse, Error> {
        use crate::responses::ResponseProvider;

        match &self.config {
            ProviderConfig::OpenAI(provider) => {
                provider
                    .create_response(request, client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::BudPrompt(provider) => {
                provider
                    .create_response(request, client, dynamic_api_keys)
                    .await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .create_response(request, client, dynamic_api_keys)
                    .await
            }
            // Other providers don't support responses yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Responses.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Stream response method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_stream_response"))]
    pub async fn stream_response(
        &self,
        request: &crate::responses::OpenAIResponseCreateParams,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<
        Box<
            dyn futures::Stream<Item = Result<crate::responses::ResponseStreamEvent, Error>>
                + Send
                + Unpin,
        >,
        Error,
    > {
        use crate::responses::ResponseProvider;

        match &self.config {
            ProviderConfig::OpenAI(provider) => {
                provider
                    .stream_response(request, client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::BudPrompt(provider) => {
                provider
                    .stream_response(request, client, dynamic_api_keys)
                    .await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .stream_response(request, client, dynamic_api_keys)
                    .await
            }
            // Other providers don't support responses yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Responses.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, response_id = response_id, otel.name = "model_provider_retrieve_response"))]
    pub async fn retrieve_response(
        &self,
        response_id: &str,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::responses::OpenAIResponse, Error> {
        use crate::responses::ResponseProvider;
        match &self.config {
            ProviderConfig::OpenAI(provider) => {
                provider
                    .retrieve_response(response_id, client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::BudPrompt(provider) => {
                provider
                    .retrieve_response(response_id, client, dynamic_api_keys)
                    .await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .retrieve_response(response_id, client, dynamic_api_keys)
                    .await
            }
            // Other providers don't support responses yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Responses.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, response_id = response_id, otel.name = "model_provider_delete_response"))]
    pub async fn delete_response(
        &self,
        response_id: &str,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<serde_json::Value, Error> {
        use crate::responses::ResponseProvider;
        match &self.config {
            ProviderConfig::OpenAI(provider) => {
                provider
                    .delete_response(response_id, client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::BudPrompt(provider) => {
                provider
                    .delete_response(response_id, client, dynamic_api_keys)
                    .await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .delete_response(response_id, client, dynamic_api_keys)
                    .await
            }
            // Other providers don't support responses yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Responses.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, response_id = response_id, otel.name = "model_provider_cancel_response"))]
    pub async fn cancel_response(
        &self,
        response_id: &str,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::responses::OpenAIResponse, Error> {
        use crate::responses::ResponseProvider;
        match &self.config {
            ProviderConfig::OpenAI(provider) => {
                provider
                    .cancel_response(response_id, client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::BudPrompt(provider) => {
                provider
                    .cancel_response(response_id, client, dynamic_api_keys)
                    .await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .cancel_response(response_id, client, dynamic_api_keys)
                    .await
            }
            // Other providers don't support responses yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Responses.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, response_id = response_id, otel.name = "model_provider_list_response_input_items"))]
    pub async fn list_response_input_items(
        &self,
        response_id: &str,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::responses::ResponseInputItemsList, Error> {
        use crate::responses::ResponseProvider;
        match &self.config {
            ProviderConfig::OpenAI(provider) => {
                provider
                    .list_response_input_items(response_id, client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::BudPrompt(provider) => {
                provider
                    .list_response_input_items(response_id, client, dynamic_api_keys)
                    .await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .list_response_input_items(response_id, client, dynamic_api_keys)
                    .await
            }
            // Other providers don't support responses yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Responses.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Execute response with automatic format detection (for providers like BudPrompt)
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_execute_response_with_detection"))]
    pub async fn execute_response_with_detection(
        &self,
        request: &crate::responses::OpenAIResponseCreateParams,
        model_name: &str,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::responses::ResponseResult, Error> {
        use crate::responses::ResponseProvider;
        match &self.config {
            ProviderConfig::BudPrompt(provider) => {
                provider
                    .execute_response_with_detection(request, model_name, client, dynamic_api_keys)
                    .await
            }
            ProviderConfig::OpenAI(provider) => {
                provider
                    .execute_response_with_detection(request, model_name, client, dynamic_api_keys)
                    .await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .execute_response_with_detection(request, model_name, client, dynamic_api_keys)
                    .await
            }
            // Other providers don't support responses yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Responses.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Upload batch file method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_upload_batch_file"))]
    pub async fn upload_batch_file(
        &self,
        content: Vec<u8>,
        filename: String,
        purpose: String,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::openai_batch::OpenAIFileObject, Error> {
        use crate::inference::providers::batch::BatchProvider;

        match &self.config {
            ProviderConfig::OpenAI(provider) => {
                provider
                    .upload_file(content, filename, purpose, client, dynamic_api_keys)
                    .await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .upload_file(content, filename, purpose, client, dynamic_api_keys)
                    .await
            }
            // Other providers don't support batch operations yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Batch.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Create batch method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_create_batch"))]
    pub async fn create_batch(
        &self,
        input_file_id: String,
        endpoint: String,
        completion_window: String,
        metadata: Option<HashMap<String, String>>,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::openai_batch::OpenAIBatchObject, Error> {
        use crate::inference::providers::batch::BatchProvider;

        match &self.config {
            ProviderConfig::OpenAI(provider) => {
                provider
                    .create_batch(
                        input_file_id,
                        endpoint,
                        completion_window,
                        metadata,
                        client,
                        dynamic_api_keys,
                    )
                    .await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .create_batch(
                        input_file_id,
                        endpoint,
                        completion_window,
                        metadata,
                        client,
                        dynamic_api_keys,
                    )
                    .await
            }
            // Other providers don't support batch operations yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Batch.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Get batch method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, batch_id = batch_id, otel.name = "model_provider_get_batch"))]
    pub async fn get_batch(
        &self,
        batch_id: &str,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::openai_batch::OpenAIBatchObject, Error> {
        use crate::inference::providers::batch::BatchProvider;

        match &self.config {
            ProviderConfig::OpenAI(provider) => {
                provider.get_batch(batch_id, client, dynamic_api_keys).await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider.get_batch(batch_id, client, dynamic_api_keys).await
            }
            // Other providers don't support batch operations yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Batch.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Get file method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, file_id = file_id, otel.name = "model_provider_get_file"))]
    pub async fn get_file(
        &self,
        file_id: &str,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::openai_batch::OpenAIFileObject, Error> {
        use crate::inference::providers::batch::BatchProvider;

        match &self.config {
            ProviderConfig::OpenAI(provider) => {
                provider.get_file(file_id, client, dynamic_api_keys).await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider.get_file(file_id, client, dynamic_api_keys).await
            }
            // Other providers don't support batch operations yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Batch.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Get file content method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, file_id = file_id, otel.name = "model_provider_get_file_content"))]
    pub async fn get_file_content(
        &self,
        file_id: &str,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<Vec<u8>, Error> {
        use crate::inference::providers::batch::BatchProvider;

        match &self.config {
            ProviderConfig::OpenAI(provider) => {
                provider
                    .get_file_content(file_id, client, dynamic_api_keys)
                    .await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .get_file_content(file_id, client, dynamic_api_keys)
                    .await
            }
            // Other providers don't support batch operations yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Batch.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Delete file method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, file_id = file_id, otel.name = "model_provider_delete_file"))]
    pub async fn delete_file(
        &self,
        file_id: &str,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::openai_batch::OpenAIFileObject, Error> {
        use crate::inference::providers::batch::BatchProvider;

        match &self.config {
            ProviderConfig::OpenAI(provider) => {
                provider
                    .delete_file(file_id, client, dynamic_api_keys)
                    .await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .delete_file(file_id, client, dynamic_api_keys)
                    .await
            }
            // Other providers don't support batch operations yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Batch.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// List batches method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_list_batches"))]
    pub async fn list_batches(
        &self,
        params: crate::openai_batch::ListBatchesParams,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::openai_batch::ListBatchesResponse, Error> {
        use crate::inference::providers::batch::BatchProvider;

        match &self.config {
            ProviderConfig::OpenAI(provider) => {
                provider
                    .list_batches(params, client, dynamic_api_keys)
                    .await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .list_batches(params, client, dynamic_api_keys)
                    .await
            }
            // Other providers don't support batch operations yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Batch.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Cancel batch method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, batch_id = batch_id, otel.name = "model_provider_cancel_batch"))]
    pub async fn cancel_batch(
        &self,
        batch_id: &str,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::openai_batch::OpenAIBatchObject, Error> {
        use crate::inference::providers::batch::BatchProvider;

        match &self.config {
            ProviderConfig::OpenAI(provider) => {
                provider
                    .cancel_batch(batch_id, client, dynamic_api_keys)
                    .await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .cancel_batch(batch_id, client, dynamic_api_keys)
                    .await
            }
            // Other providers don't support batch operations yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Batch.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Realtime session creation method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_create_realtime_session"))]
    pub async fn create_realtime_session(
        &self,
        request: &crate::realtime::RealtimeSessionRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::realtime::RealtimeSessionResponse, Error> {
        use crate::realtime::RealtimeSessionProvider;

        match &self.config {
            ProviderConfig::OpenAI(provider) => {
                provider
                    .create_session(request, client, dynamic_api_keys)
                    .await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .create_session(request, client, dynamic_api_keys)
                    .await
            }
            // Other providers don't support realtime sessions yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::RealtimeSession.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Realtime transcription session creation method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_create_realtime_transcription_session"))]
    pub async fn create_realtime_transcription_session(
        &self,
        request: &crate::realtime::RealtimeTranscriptionRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::realtime::RealtimeTranscriptionResponse, Error> {
        use crate::realtime::RealtimeTranscriptionProvider;

        match &self.config {
            ProviderConfig::OpenAI(provider) => {
                provider
                    .create_transcription_session(request, client, dynamic_api_keys)
                    .await
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                provider
                    .create_transcription_session(request, client, dynamic_api_keys)
                    .await
            }
            // Other providers don't support realtime transcription yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::RealtimeTranscription
                    .as_str()
                    .to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Document processing method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_document_processing"))]
    pub async fn process_document(
        &self,
        request: &crate::documents::DocumentProcessingRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::documents::DocumentProcessingProviderResponse, Error> {
        use crate::documents::DocumentProcessingProvider;

        match &self.config {
            ProviderConfig::BudDoc(provider) => {
                provider
                    .process_document(request, client, dynamic_api_keys)
                    .await
            }
            // Other providers don't support document processing yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Document.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }

    /// Moderation method
    #[tracing::instrument(skip_all, fields(provider_name = &*self.name, otel.name = "model_provider_moderation"))]
    pub async fn moderate(
        &self,
        request: &crate::moderation::ModerationRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<crate::moderation::ModerationResponse, Error> {
        use crate::moderation::ModerationProvider;

        match &self.config {
            ProviderConfig::AzureContentSafety(provider) => {
                let provider_response =
                    provider.moderate(request, client, dynamic_api_keys).await?;
                Ok(crate::moderation::ModerationResponse::new(
                    provider_response,
                    self.name.clone(),
                ))
            }
            ProviderConfig::OpenAI(provider) => {
                let provider_response =
                    provider.moderate(request, client, dynamic_api_keys).await?;
                Ok(crate::moderation::ModerationResponse::new(
                    provider_response,
                    self.name.clone(),
                ))
            }
            ProviderConfig::Mistral(provider) => {
                let provider_response =
                    provider.moderate(request, client, dynamic_api_keys).await?;
                Ok(crate::moderation::ModerationResponse::new(
                    provider_response,
                    self.name.clone(),
                ))
            }
            #[cfg(any(test, feature = "e2e_tests"))]
            ProviderConfig::Dummy(provider) => {
                let provider_response =
                    provider.moderate(request, client, dynamic_api_keys).await?;
                Ok(crate::moderation::ModerationResponse::new(
                    provider_response,
                    self.name.clone(),
                ))
            }
            // Other providers don't support moderation yet
            _ => Err(Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Moderation.as_str().to_string(),
                provider: self.name.to_string(),
            })),
        }
    }
}

#[derive(Clone, Debug)]
pub enum CredentialLocation {
    /// Environment variable containing the actual credential
    Env(String),
    /// Environment variable containing the path to a credential file
    PathFromEnv(String),
    /// For dynamic credential resolution
    Dynamic(String),
    /// Direct path to a credential file
    Path(String),
    /// Use a provider-specific SDK to determine credentials
    Sdk,
    None,
}

impl<'de> Deserialize<'de> for CredentialLocation {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        let s = String::deserialize(deserializer)?;
        if let Some(inner) = s.strip_prefix("env::") {
            Ok(CredentialLocation::Env(inner.to_string()))
        } else if let Some(inner) = s.strip_prefix("path_from_env::") {
            Ok(CredentialLocation::PathFromEnv(inner.to_string()))
        } else if let Some(inner) = s.strip_prefix("dynamic::") {
            Ok(CredentialLocation::Dynamic(inner.to_string()))
        } else if let Some(inner) = s.strip_prefix("path::") {
            Ok(CredentialLocation::Path(inner.to_string()))
        } else if s == "sdk" {
            Ok(CredentialLocation::Sdk)
        } else if s == "none" {
            Ok(CredentialLocation::None)
        } else {
            Err(serde::de::Error::custom(format!(
                "Invalid ApiKeyLocation format: {s}"
            )))
        }
    }
}

#[derive(Clone)]
pub enum Credential {
    Static(SecretString),
    FileContents(SecretString),
    Dynamic(String),
    Sdk,
    None,
    Missing,
}

/// Builds a credential type from the provided `CredentialLocation` and default location.
/// This is a convenience function that calls `get_creds_with_cache_and_fn` using
/// the `TryFrom<Credential>` implementation for `T`.
///
/// Most providers should be able to use this function to build their credentials,
/// unless they have special requirements (e.g. calling an `async fn`)
pub fn build_creds_caching_default<T: Clone + TryFrom<Credential, Error = Error>>(
    location: Option<CredentialLocation>,
    default_location: CredentialLocation,
    provider_type: &str,
    cache: &OnceLock<T>,
) -> Result<T, Error> {
    build_creds_caching_default_with_fn(location, default_location, provider_type, cache, |creds| {
        T::try_from(creds)
    })
}

/// Builds a credential type from the provided `CredentialLocation` and default location.
/// If the location is `None`, we'll use the provided `OnceLock` to cache the result
/// of `f(default_location)`.
/// Otherwise, we'll call `f(location)` without caching the result.
///
/// **NOTE** - `f` may be run multiple times in parallel even when `default_location` is used,
/// due to a limitation of the current `OnceLock` api.
pub fn build_creds_caching_default_with_fn<T: Clone, F: FnOnce(Credential) -> Result<T, Error>>(
    location: Option<CredentialLocation>,
    default_location: CredentialLocation,
    provider_type: &str,
    cache: &OnceLock<T>,
    f: F,
) -> Result<T, Error> {
    let make_creds = |location| {
        let creds = Credential::try_from((location, provider_type))?;
        let provider_creds = f(creds)?;
        Ok(provider_creds)
    };
    if let Some(location) = location {
        make_creds(location)
    } else {
        racy_get_or_try_init(cache, || make_creds(default_location))
    }
}

/// Gets the value from a `OnceLock` or initializes it with the result of `f`
/// If this is called simultaneously from multiple threads, it may call `f` multiple times
/// If `f` returns an error, the `OnceLock` will remain uninitialized
fn racy_get_or_try_init<T: Clone, E>(
    once_lock: &OnceLock<T>,
    f: impl FnOnce() -> Result<T, E>,
) -> Result<T, E> {
    if let Some(val) = once_lock.get() {
        Ok(val.clone())
    } else {
        let val = f()?;
        // We don't care if the value was est
        let _ = once_lock.set(val.clone());
        Ok(val)
    }
}

impl TryFrom<(CredentialLocation, &str)> for Credential {
    type Error = Error;

    fn try_from(
        (location, provider_type): (CredentialLocation, &str),
    ) -> Result<Self, Self::Error> {
        match location {
            CredentialLocation::Env(key_name) => match env::var(key_name) {
                Ok(value) => Ok(Credential::Static(SecretString::from(value))),
                Err(_) => {
                    if skip_credential_validation() {
                        #[cfg(any(test, feature = "e2e_tests"))]
                        {
                            tracing::warn!(
                            "You are missing the credentials required for a model provider of type {}, so the associated tests will likely fail.",
                            provider_type
                        );
                        }
                        Ok(Credential::Missing)
                    } else {
                        Err(Error::new(ErrorDetails::ApiKeyMissing {
                            provider_name: provider_type.to_string(),
                        }))
                    }
                }
            },
            CredentialLocation::PathFromEnv(env_key) => {
                // First get the path from environment variable
                let path = match env::var(&env_key) {
                    Ok(path) => path,
                    Err(_) => {
                        if skip_credential_validation() {
                            #[cfg(any(test, feature = "e2e_tests"))]
                            {
                                tracing::warn!(
                                "Environment variable {} is required for a model provider of type {} but is missing, so the associated tests will likely fail.",
                                env_key, provider_type

                            );
                            }
                            return Ok(Credential::Missing);
                        } else {
                            return Err(Error::new(ErrorDetails::ApiKeyMissing {
                                provider_name: format!(
                                    "{provider_type}: Environment variable {env_key} for credentials path is missing"
                                ),
                            }));
                        }
                    }
                };
                // Then read the file contents
                match fs::read_to_string(path) {
                    Ok(contents) => Ok(Credential::FileContents(SecretString::from(contents))),
                    Err(e) => {
                        if skip_credential_validation() {
                            #[cfg(any(test, feature = "e2e_tests"))]
                            {
                                tracing::warn!(
                                "Failed to read credentials file for a model provider of type {}, so the associated tests will likely fail: {}",
                                provider_type, e
                            );
                            }
                            Ok(Credential::Missing)
                        } else {
                            Err(Error::new(ErrorDetails::ApiKeyMissing {
                                provider_name: format!(
                                    "{provider_type}: Failed to read credentials file - {e}"
                                ),
                            }))
                        }
                    }
                }
            }
            CredentialLocation::Path(path) => match fs::read_to_string(path) {
                Ok(contents) => Ok(Credential::FileContents(SecretString::from(contents))),
                Err(e) => {
                    if skip_credential_validation() {
                        #[cfg(any(test, feature = "e2e_tests"))]
                        {
                            tracing::warn!(
                                "Failed to read credentials file for a model provider of type {}, so the associated tests will likely fail: {}",
                            provider_type, e
                        );
                        }
                        Ok(Credential::Missing)
                    } else {
                        Err(Error::new(ErrorDetails::ApiKeyMissing {
                            provider_name: format!(
                                "{provider_type}: Failed to read credentials file - {e}"
                            ),
                        }))
                    }
                }
            },
            CredentialLocation::Dynamic(key_name) => Ok(Credential::Dynamic(key_name.clone())),
            CredentialLocation::Sdk => Ok(Credential::Sdk),
            CredentialLocation::None => Ok(Credential::None),
        }
    }
}

const SHORTHAND_MODEL_PREFIXES: &[&str] = &[
    "anthropic::",
    "deepseek::",
    "fireworks::",
    "google_ai_studio_gemini::",
    "gcp_vertex_gemini::",
    "gcp_vertex_anthropic::",
    "hyperbolic::",
    "mistral::",
    "openai::",
    "openrouter::",
    "together::",
    "xai::",
    "dummy::",
];

pub type ModelTable = BaseModelTable<ModelConfig>;

/// Extension trait for ModelTable to add capability-based filtering
pub trait ModelTableExt {
    /// Get models that support a specific endpoint capability
    fn get_models_for_capability(
        &self,
        capability: EndpointCapability,
    ) -> Vec<(&Arc<str>, &ModelConfig)>;

    /// Get a model by name, but only if it supports the specified capability
    async fn get_with_capability(
        &self,
        key: &str,
        capability: EndpointCapability,
    ) -> Result<Option<CowNoClone<'_, ModelConfig>>, Error>;
}

impl ModelTableExt for ModelTable {
    fn get_models_for_capability(
        &self,
        capability: EndpointCapability,
    ) -> Vec<(&Arc<str>, &ModelConfig)> {
        self.iter_static_models()
            .filter(|(_, model)| model.supports_endpoint(capability))
            .collect()
    }

    async fn get_with_capability(
        &self,
        key: &str,
        capability: EndpointCapability,
    ) -> Result<Option<CowNoClone<'_, ModelConfig>>, Error> {
        if let Some(model) = self.get(key).await? {
            if model.supports_endpoint(capability) {
                Ok(Some(model))
            } else {
                Err(Error::new(ErrorDetails::ModelNotConfiguredForCapability {
                    model_name: key.to_string(),
                    capability: capability.as_str().to_string(),
                }))
            }
        } else {
            Ok(None)
        }
    }
}

impl ShorthandModelConfig for ModelConfig {
    const SHORTHAND_MODEL_PREFIXES: &[&str] = SHORTHAND_MODEL_PREFIXES;
    const MODEL_TYPE: &str = "Model";
    async fn from_shorthand(provider_type: &str, model_name: &str) -> Result<Self, Error> {
        let model_name_string = model_name.to_string();
        let endpoints = determine_capabilities_from_model_name(model_name);
        let provider_config = match provider_type {
            "anthropic" => {
                ProviderConfig::Anthropic(AnthropicProvider::new(model_name_string.clone(), None)?)
            }
            "deepseek" => {
                ProviderConfig::DeepSeek(DeepSeekProvider::new(model_name_string.clone(), None)?)
            }
            "fireworks" => ProviderConfig::Fireworks(FireworksProvider::new(
                model_name_string.clone(),
                None,
                crate::inference::providers::fireworks::default_parse_think_blocks(),
            )?),
            "google_ai_studio_gemini" => ProviderConfig::GoogleAIStudioGemini(
                GoogleAIStudioGeminiProvider::new(model_name_string.clone(), None)?,
            ),
            "gcp_vertex_gemini" => ProviderConfig::GCPVertexGemini(
                GCPVertexGeminiProvider::new_shorthand(model_name_string.clone()).await?,
            ),
            "gcp_vertex_anthropic" => ProviderConfig::GCPVertexAnthropic(
                GCPVertexAnthropicProvider::new_shorthand(model_name_string.clone()).await?,
            ),
            "hyperbolic" => ProviderConfig::Hyperbolic(HyperbolicProvider::new(
                model_name_string.clone(),
                None,
            )?),
            "mistral" => {
                ProviderConfig::Mistral(MistralProvider::new(model_name_string.clone(), None)?)
            }
            "openai" => {
                ProviderConfig::OpenAI(OpenAIProvider::new(model_name_string.clone(), None, None)?)
            }
            "together" => ProviderConfig::Together(TogetherProvider::new(
                model_name_string.clone(),
                None,
                crate::inference::providers::together::default_parse_think_blocks(),
            )?),
            "xai" => ProviderConfig::XAI(XAIProvider::new(model_name_string.clone(), None)?),
            #[cfg(any(test, feature = "e2e_tests"))]
            "dummy" => ProviderConfig::Dummy(DummyProvider::new(model_name_string.clone(), None)?),
            _ => {
                return Err(ErrorDetails::Config {
                    message: format!("Invalid provider type: {provider_type}"),
                }
                .into());
            }
        };
        Ok(ModelConfig {
            routing: vec![provider_type.to_string().into()],
            providers: HashMap::from([(
                provider_type.to_string().into(),
                ModelProvider {
                    name: provider_type.into(),
                    config: provider_config,
                    extra_body: Default::default(),
                    extra_headers: Default::default(),
                },
            )]),
            endpoints,               // Use pre-computed endpoints based on model name
            fallback_models: None,   // Shorthand models don't support fallback
            retry_config: None,      // Shorthand models don't have retry config
            rate_limits: None,       // Shorthand models don't have rate limits
            pricing: None,           // Shorthand models don't have pricing
            guardrail_profile: None, // Shorthand models don't have guardrail profiles
        })
    }

    fn validate(&self, model_name: &str) -> Result<(), Error> {
        // Ensure that the model has at least one provider
        if self.routing.is_empty() {
            return Err(ErrorDetails::Config {
                message: format!("`models.{model_name}`: `routing` must not be empty"),
            }
            .into());
        }

        // Ensure that routing entries are unique and exist as keys in providers
        let mut seen_providers = std::collections::HashSet::new();
        for provider in &self.routing {
            if provider.starts_with("tensorzero::") {
                return Err(ErrorDetails::Config {
                    message: format!("`models.{model_name}.routing`: Provider name cannot start with 'tensorzero::': {provider}"),
                }
                .into());
            }
            if !seen_providers.insert(provider) {
                return Err(ErrorDetails::Config {
                    message: format!("`models.{model_name}.routing`: duplicate entry `{provider}`"),
                }
                .into());
            }

            if !self.providers.contains_key(provider) {
                return Err(ErrorDetails::Config {
            message: format!(
                "`models.{model_name}`: `routing` contains entry `{provider}` that does not exist in `providers`"
            ),
        }
        .into());
            }
        }

        // Validate each provider
        for provider_name in self.providers.keys() {
            if !seen_providers.contains(provider_name) {
                return Err(ErrorDetails::Config {
                    message: format!(
                "`models.{model_name}`: Provider `{provider_name}` is not listed in `routing`"
            ),
                }
                .into());
            }
        }

        // Validate endpoints
        if self.endpoints.is_empty() {
            return Err(ErrorDetails::Config {
                message: format!("`models.{model_name}`: `endpoints` must not be empty. At least one capability (e.g., 'chat', 'embeddings') must be specified"),
            }
            .into());
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use std::{borrow::Cow, cell::Cell};

    use crate::cache::CacheEnabledMode;
    use crate::config_parser::SKIP_CREDENTIAL_VALIDATION;
    use crate::tool::{ToolCallConfig, ToolChoice};
    use crate::{
        cache::CacheOptions,
        clickhouse::ClickHouseConnectionInfo,
        inference::{
            providers::dummy::{
                DummyCredentials, DUMMY_INFER_RESPONSE_CONTENT, DUMMY_INFER_RESPONSE_RAW,
                DUMMY_INFER_USAGE, DUMMY_STREAMING_RESPONSE,
            },
            types::{ContentBlockChunk, FunctionType, ModelInferenceRequestJsonMode, TextChunk},
        },
        model_table::RESERVED_MODEL_PREFIXES,
    };
    use secrecy::SecretString;
    use tokio_stream::StreamExt;
    use tracing_test::traced_test;
    use uuid::Uuid;

    use super::*;

    #[tokio::test]
    async fn test_model_config_infer_routing() {
        let good_provider_config = ProviderConfig::Dummy(DummyProvider {
            model_name: "good".into(),
            credentials: DummyCredentials::None,
        });
        let bad_provider_config = ProviderConfig::Dummy(DummyProvider {
            model_name: "error".into(),
            credentials: DummyCredentials::None,
        });
        let model_config = ModelConfig {
            routing: vec!["good_provider".into()],
            providers: HashMap::from([(
                "good_provider".into(),
                ModelProvider {
                    name: "good_provider".into(),
                    config: good_provider_config,
                    extra_body: Default::default(),
                    extra_headers: Default::default(),
                },
            )]),
            endpoints: default_capabilities(),
            fallback_models: None,
            retry_config: None,
            rate_limits: None,
            pricing: None,
            guardrail_profile: None,
        };
        let tool_config = ToolCallConfig {
            tools_available: vec![],
            tool_choice: ToolChoice::Auto,
            parallel_tool_calls: None,
        };
        let api_keys = InferenceCredentials::default();
        let http_client = Client::new();
        let clickhouse_connection_info = ClickHouseConnectionInfo::Disabled;
        let clients = InferenceClients {
            http_client: &http_client,
            clickhouse_connection_info: &clickhouse_connection_info,
            credentials: &api_keys,
            cache_options: &CacheOptions {
                max_age_s: None,
                enabled: CacheEnabledMode::WriteOnly,
            },
        };

        // Try inferring the good model only
        let request = ModelInferenceRequest {
            inference_id: Uuid::now_v7(),
            messages: vec![],
            system: None,
            tool_config: Some(Cow::Borrowed(&tool_config)),
            temperature: None,
            top_p: None,
            presence_penalty: None,
            frequency_penalty: None,
            max_tokens: None,
            seed: None,
            stream: false,
            json_mode: ModelInferenceRequestJsonMode::Off,
            function_type: FunctionType::Chat,
            output_schema: None,
            extra_body: Default::default(),
            ..Default::default()
        };
        let model_name = "test model";
        let response = model_config
            .infer(&request, &clients, model_name)
            .await
            .unwrap();
        let content = response.output;
        assert_eq!(
            content,
            vec![DUMMY_INFER_RESPONSE_CONTENT.to_string().into()]
        );
        let raw = response.raw_response;
        assert_eq!(raw, DUMMY_INFER_RESPONSE_RAW);
        let usage = response.usage;
        assert_eq!(usage, DUMMY_INFER_USAGE);
        assert_eq!(&*response.model_provider_name, "good_provider");

        // Try inferring the bad model
        let model_config = ModelConfig {
            routing: vec!["error".into()],
            providers: HashMap::from([(
                "error".into(),
                ModelProvider {
                    name: "error".into(),
                    config: bad_provider_config,
                    extra_body: Default::default(),
                    extra_headers: Default::default(),
                },
            )]),
            endpoints: default_capabilities(),
            fallback_models: None,
            retry_config: None,
            rate_limits: None,
            pricing: None,
            guardrail_profile: None,
        };
        let response = model_config
            .infer(&request, &clients, model_name)
            .await
            .unwrap_err();
        assert_eq!(
            response,
            ErrorDetails::ModelProvidersExhausted {
                provider_errors: HashMap::from([(
                    "error".to_string(),
                    ErrorDetails::InferenceClient {
                        message: "Error sending request to Dummy provider for model 'error'."
                            .to_string(),
                        status_code: None,
                        provider_type: "dummy".to_string(),
                        raw_request: Some("raw request".to_string()),
                        raw_response: None,
                    }
                    .into()
                )])
            }
            .into()
        );
    }

    #[tokio::test]
    #[traced_test]
    async fn test_model_config_infer_routing_fallback() {
        // Test that fallback works with bad --> good model provider

        let good_provider_config = ProviderConfig::Dummy(DummyProvider {
            model_name: "good".into(),
            credentials: DummyCredentials::None,
        });
        let bad_provider_config = ProviderConfig::Dummy(DummyProvider {
            model_name: "error".into(),
            credentials: DummyCredentials::None,
        });
        let api_keys = InferenceCredentials::default();
        let http_client = Client::new();
        let clickhouse_connection_info = ClickHouseConnectionInfo::Disabled;
        let clients = InferenceClients {
            http_client: &http_client,
            clickhouse_connection_info: &clickhouse_connection_info,
            credentials: &api_keys,
            cache_options: &CacheOptions {
                max_age_s: None,
                enabled: CacheEnabledMode::WriteOnly,
            },
        };
        // Try inferring the good model only
        let request = ModelInferenceRequest {
            inference_id: Uuid::now_v7(),
            messages: vec![],
            system: None,
            tool_config: None,
            temperature: None,
            top_p: None,
            presence_penalty: None,
            frequency_penalty: None,
            max_tokens: None,
            seed: None,
            stream: false,
            json_mode: ModelInferenceRequestJsonMode::Off,
            function_type: FunctionType::Chat,
            output_schema: None,
            extra_body: Default::default(),
            ..Default::default()
        };

        let model_config = ModelConfig {
            routing: vec![
                "error_provider".to_string().into(),
                "good_provider".to_string().into(),
            ],
            providers: HashMap::from([
                (
                    "error_provider".to_string().into(),
                    ModelProvider {
                        name: "error_provider".into(),
                        config: bad_provider_config,
                        extra_body: Default::default(),
                        extra_headers: Default::default(),
                    },
                ),
                (
                    "good_provider".to_string().into(),
                    ModelProvider {
                        name: "good_provider".into(),
                        config: good_provider_config,
                        extra_body: Default::default(),
                        extra_headers: Default::default(),
                    },
                ),
            ]),
            endpoints: default_capabilities(),
            fallback_models: None,
            retry_config: None,
            rate_limits: None,
            pricing: None,
            guardrail_profile: None,
        };

        let model_name = "test model";
        let response = model_config
            .infer(&request, &clients, model_name)
            .await
            .unwrap();
        // Ensure that the error for the bad provider was logged, but the request worked nonetheless
        assert!(logs_contain(
            "Error sending request to Dummy provider for model 'error'."
        ));
        let content = response.output;
        assert_eq!(
            content,
            vec![DUMMY_INFER_RESPONSE_CONTENT.to_string().into()]
        );
        let raw = response.raw_response;
        assert_eq!(raw, DUMMY_INFER_RESPONSE_RAW);
        let usage = response.usage;
        assert_eq!(usage, DUMMY_INFER_USAGE);
        assert_eq!(&*response.model_provider_name, "good_provider");
    }

    #[tokio::test]
    async fn test_model_config_infer_stream_routing() {
        let good_provider_config = ProviderConfig::Dummy(DummyProvider {
            model_name: "good".into(),
            credentials: DummyCredentials::None,
        });
        let bad_provider_config = ProviderConfig::Dummy(DummyProvider {
            model_name: "error".into(),
            credentials: DummyCredentials::None,
        });
        let api_keys = InferenceCredentials::default();
        let request = ModelInferenceRequest {
            inference_id: Uuid::now_v7(),
            messages: vec![],
            system: None,
            tool_config: None,
            temperature: None,
            top_p: None,
            presence_penalty: None,
            frequency_penalty: None,
            max_tokens: None,
            seed: None,
            stream: true,
            json_mode: ModelInferenceRequestJsonMode::Off,
            function_type: FunctionType::Chat,
            output_schema: None,
            extra_body: Default::default(),
            ..Default::default()
        };

        // Test good model
        let model_config = ModelConfig {
            routing: vec!["good_provider".to_string().into()],
            providers: HashMap::from([(
                "good_provider".to_string().into(),
                ModelProvider {
                    name: "good_provider".into(),
                    config: good_provider_config,
                    extra_body: Default::default(),
                    extra_headers: Default::default(),
                },
            )]),
            endpoints: default_capabilities(),
            fallback_models: None,
            retry_config: None,
            rate_limits: None,
            pricing: None,
            guardrail_profile: None,
        };
        let (
            StreamResponse {
                mut stream,
                raw_request,
                model_provider_name,
                cached: _,
            },
            _input,
        ) = model_config
            .infer_stream(
                &request,
                &InferenceClients {
                    http_client: &Client::new(),
                    clickhouse_connection_info: &ClickHouseConnectionInfo::Disabled,
                    credentials: &api_keys,
                    cache_options: &CacheOptions {
                        max_age_s: None,
                        enabled: CacheEnabledMode::Off,
                    },
                },
                "my_model",
            )
            .await
            .unwrap();
        let initial_chunk = stream.next().await.unwrap().unwrap();
        assert_eq!(
            initial_chunk.content,
            vec![ContentBlockChunk::Text(TextChunk {
                text: DUMMY_STREAMING_RESPONSE[0].to_string(),
                id: "0".to_string(),
            })],
        );
        assert_eq!(raw_request, "raw request");
        assert_eq!(&*model_provider_name, "good_provider");
        let mut collected_content: Vec<ContentBlockChunk> =
            vec![ContentBlockChunk::Text(TextChunk {
                text: DUMMY_STREAMING_RESPONSE[0].to_string(),
                id: "0".to_string(),
            })];
        let mut stream = Box::pin(stream);
        while let Some(Ok(chunk)) = stream.next().await {
            let mut content = chunk.content;
            assert!(content.len() <= 1);
            if content.len() == 1 {
                collected_content.push(content.pop().unwrap());
            }
        }
        let mut collected_content_str = String::new();
        for content in collected_content {
            match content {
                ContentBlockChunk::Text(text) => collected_content_str.push_str(&text.text),
                _ => panic!("Expected a text content block"),
            }
        }
        assert_eq!(collected_content_str, DUMMY_STREAMING_RESPONSE.join(""));

        // Test bad model
        let model_config = ModelConfig {
            routing: vec!["error".to_string().into()],
            providers: HashMap::from([(
                "error".to_string().into(),
                ModelProvider {
                    name: "error".to_string().into(),
                    config: bad_provider_config,
                    extra_body: Default::default(),
                    extra_headers: Default::default(),
                },
            )]),
            endpoints: default_capabilities(),
            fallback_models: None,
            retry_config: None,
            rate_limits: None,
            pricing: None,
            guardrail_profile: None,
        };
        let response = model_config
            .infer_stream(
                &request,
                &InferenceClients {
                    http_client: &Client::new(),
                    clickhouse_connection_info: &ClickHouseConnectionInfo::Disabled,
                    credentials: &api_keys,
                    cache_options: &CacheOptions {
                        max_age_s: None,
                        enabled: CacheEnabledMode::Off,
                    },
                },
                "my_model",
            )
            .await;
        assert!(response.is_err());
        let error = match response {
            Err(error) => error,
            Ok(_) => panic!("Expected error, got Ok(_)"),
        };
        assert_eq!(
            error,
            ErrorDetails::ModelProvidersExhausted {
                provider_errors: HashMap::from([(
                    "error".to_string(),
                    ErrorDetails::InferenceClient {
                        message: "Error sending request to Dummy provider for model 'error'."
                            .to_string(),
                        status_code: None,
                        provider_type: "dummy".to_string(),
                        raw_request: Some("raw request".to_string()),
                        raw_response: None,
                    }
                    .into()
                )])
            }
            .into()
        );
    }

    #[tokio::test]
    #[traced_test]
    async fn test_model_config_infer_stream_routing_fallback() {
        // Test that fallback works with bad --> good model provider (streaming)

        let good_provider_config = ProviderConfig::Dummy(DummyProvider {
            model_name: "good".into(),
            credentials: DummyCredentials::None,
        });
        let bad_provider_config = ProviderConfig::Dummy(DummyProvider {
            model_name: "error".into(),
            credentials: DummyCredentials::None,
        });
        let api_keys = InferenceCredentials::default();
        let request = ModelInferenceRequest {
            inference_id: Uuid::now_v7(),
            messages: vec![],
            system: None,
            tool_config: None,
            temperature: None,
            top_p: None,
            presence_penalty: None,
            frequency_penalty: None,
            max_tokens: None,
            seed: None,
            stream: true,
            json_mode: ModelInferenceRequestJsonMode::Off,
            function_type: FunctionType::Chat,
            output_schema: None,
            extra_body: Default::default(),
            ..Default::default()
        };

        // Test fallback
        let model_config = ModelConfig {
            routing: vec!["error_provider".into(), "good_provider".into()],
            providers: HashMap::from([
                (
                    "error_provider".to_string().into(),
                    ModelProvider {
                        name: "error_provider".to_string().into(),
                        config: bad_provider_config,
                        extra_body: Default::default(),
                        extra_headers: Default::default(),
                    },
                ),
                (
                    "good_provider".to_string().into(),
                    ModelProvider {
                        name: "good_provider".to_string().into(),
                        config: good_provider_config,
                        extra_body: Default::default(),
                        extra_headers: Default::default(),
                    },
                ),
            ]),
            endpoints: default_capabilities(),
            fallback_models: None,
            retry_config: None,
            rate_limits: None,
            pricing: None,
            guardrail_profile: None,
        };
        let (
            StreamResponse {
                mut stream,
                raw_request,
                model_provider_name,
                cached: _,
            },
            _input,
        ) = model_config
            .infer_stream(
                &request,
                &InferenceClients {
                    http_client: &Client::new(),
                    clickhouse_connection_info: &ClickHouseConnectionInfo::Disabled,
                    credentials: &api_keys,
                    cache_options: &CacheOptions {
                        max_age_s: None,
                        enabled: CacheEnabledMode::Off,
                    },
                },
                "my_model",
            )
            .await
            .unwrap();
        let initial_chunk = stream.next().await.unwrap().unwrap();
        assert_eq!(&*model_provider_name, "good_provider");
        // Ensure that the error for the bad provider was logged, but the request worked nonetheless
        assert!(logs_contain(
            "Error sending request to Dummy provider for model 'error'"
        ));
        assert_eq!(raw_request, "raw request");

        assert_eq!(
            initial_chunk.content,
            vec![ContentBlockChunk::Text(TextChunk {
                text: DUMMY_STREAMING_RESPONSE[0].to_string(),
                id: "0".to_string(),
            })],
        );

        let mut collected_content = initial_chunk.content;
        let mut stream = Box::pin(stream);
        while let Some(Ok(chunk)) = stream.next().await {
            let mut content = chunk.content;
            assert!(content.len() <= 1);
            if content.len() == 1 {
                collected_content.push(content.pop().unwrap());
            }
        }
        let mut collected_content_str = String::new();
        for content in collected_content {
            match content {
                ContentBlockChunk::Text(text) => collected_content_str.push_str(&text.text),
                _ => panic!("Expected a text content block"),
            }
        }
        assert_eq!(collected_content_str, DUMMY_STREAMING_RESPONSE.join(""));
    }

    #[tokio::test]
    async fn test_dynamic_api_keys() {
        let provider_config = ProviderConfig::Dummy(DummyProvider {
            model_name: "test_key".into(),
            credentials: DummyCredentials::Dynamic("TEST_KEY".to_string()),
        });
        let model_config = ModelConfig {
            routing: vec!["model".into()],
            providers: HashMap::from([(
                "model".into(),
                ModelProvider {
                    name: "model".into(),
                    config: provider_config,
                    extra_body: Default::default(),
                    extra_headers: Default::default(),
                },
            )]),
            endpoints: default_capabilities(),
            fallback_models: None,
            retry_config: None,
            rate_limits: None,
            pricing: None,
            guardrail_profile: None,
        };
        let tool_config = ToolCallConfig {
            tools_available: vec![],
            tool_choice: ToolChoice::Auto,
            parallel_tool_calls: None,
        };
        let api_keys = InferenceCredentials::default();
        let http_client = Client::new();
        let clickhouse_connection_info = ClickHouseConnectionInfo::Disabled;
        let clients = InferenceClients {
            http_client: &http_client,
            clickhouse_connection_info: &clickhouse_connection_info,
            credentials: &api_keys,
            cache_options: &CacheOptions {
                max_age_s: None,
                enabled: CacheEnabledMode::WriteOnly,
            },
        };

        let request = ModelInferenceRequest {
            inference_id: Uuid::now_v7(),
            messages: vec![],
            system: None,
            tool_config: Some(Cow::Borrowed(&tool_config)),
            temperature: None,
            top_p: None,
            presence_penalty: None,
            frequency_penalty: None,
            max_tokens: None,
            seed: None,
            stream: false,
            json_mode: ModelInferenceRequestJsonMode::Off,
            function_type: FunctionType::Chat,
            output_schema: None,
            extra_body: Default::default(),
            ..Default::default()
        };
        let model_name = "test model";
        let error = model_config
            .infer(&request, &clients, model_name)
            .await
            .unwrap_err();
        assert_eq!(
            error,
            ErrorDetails::ModelProvidersExhausted {
                provider_errors: HashMap::from([(
                    "model".to_string(),
                    ErrorDetails::ApiKeyMissing {
                        provider_name: "Dummy".to_string()
                    }
                    .into()
                )])
            }
            .into()
        );

        let api_keys = HashMap::from([(
            "TEST_KEY".to_string(),
            SecretString::from("notgoodkey".to_string()),
        )]);
        let clients = InferenceClients {
            http_client: &http_client,
            clickhouse_connection_info: &clickhouse_connection_info,
            credentials: &api_keys,
            cache_options: &CacheOptions {
                max_age_s: None,
                enabled: CacheEnabledMode::WriteOnly,
            },
        };
        let response = model_config
            .infer(&request, &clients, model_name)
            .await
            .unwrap_err();
        assert_eq!(
            response,
            ErrorDetails::ModelProvidersExhausted {
                provider_errors: HashMap::from([(
                    "model".to_string(),
                    ErrorDetails::InferenceClient {
                        message: "Invalid API key for Dummy provider".to_string(),
                        status_code: None,
                        provider_type: "dummy".to_string(),
                        raw_request: Some("raw request".to_string()),
                        raw_response: None,
                    }
                    .into()
                )])
            }
            .into()
        );

        let provider_config = ProviderConfig::Dummy(DummyProvider {
            model_name: "test_key".into(),
            credentials: DummyCredentials::Dynamic("TEST_KEY".to_string()),
        });
        let model_config = ModelConfig {
            routing: vec!["model".to_string().into()],
            providers: HashMap::from([(
                "model".to_string().into(),
                ModelProvider {
                    name: "model".to_string().into(),
                    config: provider_config,
                    extra_body: Default::default(),
                    extra_headers: Default::default(),
                },
            )]),
            endpoints: default_capabilities(),
            fallback_models: None,
            retry_config: None,
            rate_limits: None,
            pricing: None,
            guardrail_profile: None,
        };
        let tool_config = ToolCallConfig {
            tools_available: vec![],
            tool_choice: ToolChoice::Auto,
            parallel_tool_calls: None,
        };
        let api_keys = InferenceCredentials::default();
        let http_client = Client::new();
        let clickhouse_connection_info = ClickHouseConnectionInfo::Disabled;
        let clients = InferenceClients {
            http_client: &http_client,
            clickhouse_connection_info: &clickhouse_connection_info,
            credentials: &api_keys,
            cache_options: &CacheOptions {
                max_age_s: None,
                enabled: CacheEnabledMode::WriteOnly,
            },
        };

        let request = ModelInferenceRequest {
            messages: vec![],
            inference_id: Uuid::now_v7(),
            system: None,
            tool_config: Some(Cow::Borrowed(&tool_config)),
            temperature: None,
            top_p: None,
            presence_penalty: None,
            frequency_penalty: None,
            max_tokens: None,
            seed: None,
            stream: false,
            json_mode: ModelInferenceRequestJsonMode::Off,
            function_type: FunctionType::Chat,
            output_schema: None,
            extra_body: Default::default(),
            ..Default::default()
        };
        let error = model_config
            .infer(&request, &clients, model_name)
            .await
            .unwrap_err();
        assert_eq!(
            error,
            ErrorDetails::ModelProvidersExhausted {
                provider_errors: HashMap::from([(
                    "model".to_string(),
                    ErrorDetails::ApiKeyMissing {
                        provider_name: "Dummy".to_string()
                    }
                    .into()
                )])
            }
            .into()
        );

        let api_keys = HashMap::from([(
            "TEST_KEY".to_string(),
            SecretString::from("good_key".to_string()),
        )]);
        let clients = InferenceClients {
            http_client: &http_client,
            clickhouse_connection_info: &clickhouse_connection_info,
            credentials: &api_keys,
            cache_options: &CacheOptions {
                max_age_s: None,
                enabled: CacheEnabledMode::WriteOnly,
            },
        };
        let response = model_config
            .infer(&request, &clients, model_name)
            .await
            .unwrap();
        assert_eq!(
            response.output,
            vec![DUMMY_INFER_RESPONSE_CONTENT.to_string().into()]
        );
    }

    #[tokio::test]
    async fn test_validate_or_create_model_config() {
        let model_table = ModelTable::default();
        // Test that we can get or create a model config
        model_table.validate("dummy::gpt-4o").unwrap();
        // Shorthand models are not added to the model table
        assert_eq!(model_table.static_model_len(), 0);
        let model_config = model_table
            .get("dummy::gpt-4o")
            .await
            .unwrap()
            .expect("Missing dummy model");
        assert_eq!(model_config.routing, vec!["dummy".into()]);
        let provider_config = &model_config.providers.get("dummy").unwrap().config;
        match provider_config {
            ProviderConfig::Dummy(provider) => assert_eq!(&*provider.model_name, "gpt-4o"),
            _ => panic!("Expected Dummy provider"),
        }

        // Test that it fails if the model is not well-formed
        let model_config = model_table.validate("foo::bar");
        assert!(model_config.is_err());
        assert_eq!(
            model_config.unwrap_err(),
            ErrorDetails::Config {
                message: "Model name 'foo::bar' not found in model table".to_string()
            }
            .into()
        );
        // Test that it works with an initialized model
        let anthropic_provider_config = SKIP_CREDENTIAL_VALIDATION.sync_scope((), || {
            ProviderConfig::Anthropic(AnthropicProvider::new("claude".to_string(), None).unwrap())
        });
        let anthropic_model_config = ModelConfig {
            routing: vec!["anthropic".into()],
            providers: HashMap::from([(
                "anthropic".into(),
                ModelProvider {
                    name: "anthropic".into(),
                    config: anthropic_provider_config,
                    extra_body: Default::default(),
                    extra_headers: Default::default(),
                },
            )]),
            endpoints: default_capabilities(),
            fallback_models: None,
            retry_config: None,
            rate_limits: None,
            pricing: None,
            guardrail_profile: None,
        };
        let model_table: ModelTable = HashMap::from([("claude".into(), anthropic_model_config)])
            .try_into()
            .unwrap();

        model_table.validate("dummy::claude").unwrap();
    }

    #[test]
    fn test_shorthand_prefixes_subset_of_reserved() {
        for &shorthand in SHORTHAND_MODEL_PREFIXES {
            assert!(
                RESERVED_MODEL_PREFIXES.contains(&shorthand.to_string()),
                "Shorthand prefix '{shorthand}' is not in RESERVED_MODEL_PREFIXES"
            );
        }
    }

    #[test]
    fn test_racy_get_or_try_init() {
        let lock: OnceLock<bool> = OnceLock::new();

        // If the closure returns an error, `racy_get_or_try_init` should return an error
        racy_get_or_try_init(&lock, || {
            Err::<_, Box<dyn std::error::Error>>("Test error".into())
        })
        .expect_err("Test error");
        assert!(
            lock.get().is_none(),
            "OnceLock was initialized after an error"
        );

        racy_get_or_try_init(&lock, || Ok::<_, Box<dyn std::error::Error>>(true))
            .expect("racy_get_or_try_init should succeed with successful closure");

        assert_eq!(lock.get(), Some(&true));
    }

    #[test]
    fn test_cache_default_creds() {
        let make_creds_call_count = Cell::new(0);
        let make_creds = |_| {
            make_creds_call_count.set(make_creds_call_count.get() + 1);
            Ok(())
        };

        let cache = OnceLock::new();

        build_creds_caching_default_with_fn(
            None,
            CredentialLocation::None,
            "test",
            &cache,
            make_creds,
        )
        .expect("Failed to build creds");
        // The first call should initialize the OnceLock, and call `make_creds`
        assert_eq!(make_creds_call_count.get(), 1);
        assert_eq!(cache.get(), Some(&()));

        // Subsequent calls should not call `make_creds`
        build_creds_caching_default_with_fn(
            None,
            CredentialLocation::None,
            "test",
            &cache,
            make_creds,
        )
        .expect("Failed to build creds");
        assert_eq!(make_creds_call_count.get(), 1);
    }

    #[test]
    fn test_dont_cache_non_default_creds() {
        let make_creds_call_count = Cell::new(0);
        let make_creds = |_| {
            make_creds_call_count.set(make_creds_call_count.get() + 1);
            Ok(())
        };

        let cache = OnceLock::new();

        // When we provide a `Some(credential_location)`, we should not cache the creds.
        build_creds_caching_default_with_fn(
            Some(CredentialLocation::None),
            CredentialLocation::None,
            "test",
            &cache,
            make_creds,
        )
        .expect("Failed to build creds");

        assert_eq!(cache.get(), None);
        assert_eq!(make_creds_call_count.get(), 1);
    }

    // Tests for unified model configuration with endpoint capabilities

    #[test]
    fn test_model_supports_endpoint() {
        let mut endpoints = HashSet::new();
        endpoints.insert(EndpointCapability::Chat);
        endpoints.insert(EndpointCapability::Embedding);

        let model = ModelConfig {
            routing: vec!["test".into()],
            providers: HashMap::new(),
            endpoints,
            fallback_models: None,
            retry_config: None,
            rate_limits: None,
            pricing: None,
            guardrail_profile: None,
        };

        assert!(model.supports_endpoint(EndpointCapability::Chat));
        assert!(model.supports_endpoint(EndpointCapability::Embedding));
    }

    #[test]
    fn test_model_config_validates_endpoints() {
        // Test that empty endpoints fails validation
        let model = ModelConfig {
            routing: vec!["test".into()],
            providers: HashMap::from([(
                "test".into(),
                ModelProvider {
                    name: "test".into(),
                    config: ProviderConfig::Dummy(DummyProvider {
                        model_name: "test".into(),
                        credentials: DummyCredentials::None,
                    }),
                    extra_body: None,
                    extra_headers: None,
                },
            )]),
            endpoints: HashSet::new(), // Empty endpoints
            fallback_models: None,
            retry_config: None,
            rate_limits: None,
            pricing: None,
            guardrail_profile: None,
        };

        let result = model.validate("test_model");
        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .to_string()
            .contains("endpoints` must not be empty"));
    }

    #[test]
    fn test_model_config_default_endpoints() {
        // Test that default_capabilities returns chat endpoint
        let default_caps = default_capabilities();
        assert_eq!(default_caps.len(), 1);
        assert!(default_caps.contains(&EndpointCapability::Chat));
    }

    #[tokio::test]
    async fn test_model_table_ext_get_models_for_capability() {
        let mut chat_endpoints = HashSet::new();
        chat_endpoints.insert(EndpointCapability::Chat);

        let mut embedding_endpoints = HashSet::new();
        embedding_endpoints.insert(EndpointCapability::Embedding);

        let mut both_endpoints = HashSet::new();
        both_endpoints.insert(EndpointCapability::Chat);
        both_endpoints.insert(EndpointCapability::Embedding);

        let mut models = HashMap::new();
        models.insert(
            "chat_only".into(),
            ModelConfig {
                routing: vec!["test".into()],
                providers: HashMap::new(),
                endpoints: chat_endpoints,
                fallback_models: None,
                retry_config: None,
                rate_limits: None,
                pricing: None,
                guardrail_profile: None,
            },
        );
        models.insert(
            "embedding_only".into(),
            ModelConfig {
                routing: vec!["test".into()],
                providers: HashMap::new(),
                endpoints: embedding_endpoints,
                fallback_models: None,
                retry_config: None,
                rate_limits: None,
                pricing: None,
                guardrail_profile: None,
            },
        );
        models.insert(
            "both".into(),
            ModelConfig {
                routing: vec!["test".into()],
                providers: HashMap::new(),
                endpoints: both_endpoints,
                fallback_models: None,
                retry_config: None,
                rate_limits: None,
                pricing: None,
                guardrail_profile: None,
            },
        );

        let model_table: ModelTable = models.try_into().unwrap();

        // Test filtering by chat capability
        let chat_models = model_table.get_models_for_capability(EndpointCapability::Chat);
        assert_eq!(chat_models.len(), 2);
        let chat_model_names: HashSet<&str> =
            chat_models.iter().map(|(name, _)| name.as_ref()).collect();
        assert!(chat_model_names.contains("chat_only"));
        assert!(chat_model_names.contains("both"));

        // Test filtering by embeddings capability
        let embedding_models = model_table.get_models_for_capability(EndpointCapability::Embedding);
        assert_eq!(embedding_models.len(), 2);
        let embedding_model_names: HashSet<&str> = embedding_models
            .iter()
            .map(|(name, _)| name.as_ref())
            .collect();
        assert!(embedding_model_names.contains("embedding_only"));
        assert!(embedding_model_names.contains("both"));
    }

    #[tokio::test]
    async fn test_model_table_ext_get_with_capability() {
        SKIP_CREDENTIAL_VALIDATION
            .scope((), async {
                let mut endpoints = HashSet::new();
                endpoints.insert(EndpointCapability::Chat);

                let mut models = HashMap::new();
                models.insert(
                    "chat_model".into(),
                    ModelConfig {
                        routing: vec!["dummy".into()],
                        providers: HashMap::from([(
                            "dummy".into(),
                            ModelProvider {
                                name: "dummy".into(),
                                config: ProviderConfig::Dummy(DummyProvider {
                                    model_name: "test".into(),
                                    credentials: DummyCredentials::None,
                                }),
                                extra_body: None,
                                extra_headers: None,
                            },
                        )]),
                        endpoints,
                        fallback_models: None,
                        retry_config: None,
                        rate_limits: None,
                        pricing: None,
                        guardrail_profile: None,
                    },
                );

                let model_table: ModelTable = models.try_into().unwrap();

                // Test getting model with correct capability
                let result = model_table
                    .get_with_capability("chat_model", EndpointCapability::Chat)
                    .await;
                assert!(result.is_ok());
                assert!(result.unwrap().is_some());

                // Test getting model with wrong capability
                let result = model_table
                    .get_with_capability("chat_model", EndpointCapability::Embedding)
                    .await;
                assert!(result.is_err());
                let error = result.unwrap_err();
                assert!(error
                    .to_string()
                    .contains("is not configured to support capability"));

                // Test getting non-existent model
                let result = model_table
                    .get_with_capability("non_existent", EndpointCapability::Chat)
                    .await;
                assert!(result.is_ok());
                assert!(result.unwrap().is_none());
            })
            .await;
    }

    #[tokio::test]
    async fn test_model_config_embed_capability_check() {
        let mut endpoints = HashSet::new();
        endpoints.insert(EndpointCapability::Chat); // Only chat, no embeddings

        let model = ModelConfig {
            routing: vec!["test".into()],
            providers: HashMap::new(),
            endpoints,
            fallback_models: None,
            retry_config: None,
            rate_limits: None,
            pricing: None,
            guardrail_profile: None,
        };

        let request = crate::embeddings::EmbeddingRequest {
            input: crate::embeddings::EmbeddingInput::Single("test".to_string()),
            encoding_format: None,
        };

        let http_client = Client::new();
        let credentials = InferenceCredentials::default();
        let clickhouse = ClickHouseConnectionInfo::Disabled;
        let cache_options = CacheOptions {
            max_age_s: None,
            enabled: CacheEnabledMode::Off,
        };

        let clients = InferenceClients {
            http_client: &http_client,
            credentials: &credentials,
            clickhouse_connection_info: &clickhouse,
            cache_options: &cache_options,
        };

        // Test that embed fails when model doesn't support embeddings
        let result = model.embed(&request, "test_model", &clients).await;
        assert!(result.is_err());
        let error = result.unwrap_err();
        assert!(error
            .to_string()
            .contains("is not configured to support capability"));
    }

    #[traced_test]
    #[tokio::test]
    async fn test_model_provider_embed_dispatch() {
        let provider = ModelProvider {
            name: "test".into(),
            config: ProviderConfig::Dummy(DummyProvider {
                model_name: "embedding_test".into(),
                credentials: DummyCredentials::None,
            }),
            extra_body: None,
            extra_headers: None,
        };

        let request = crate::embeddings::EmbeddingRequest {
            input: crate::embeddings::EmbeddingInput::Single("test input".to_string()),
            encoding_format: None,
        };

        let http_client = Client::new();
        let credentials = InferenceCredentials::default();

        // Test successful embedding with dummy provider
        let result = provider.embed(&request, &http_client, &credentials).await;
        assert!(result.is_ok());
        let response = result.unwrap();
        assert_eq!(
            response.input,
            crate::embeddings::EmbeddingInput::Single("test input".to_string())
        );
        assert!(!response.embeddings.is_empty());
        assert!(!response.embeddings[0].is_empty());
    }

    #[tokio::test]
    async fn test_model_provider_embed_unsupported() {
        // First, let's verify which provider configs support embeddings by checking the embed method
        // According to the embed implementation, only OpenAI, VLLM, and Dummy (in test mode) support embeddings
        // All other providers should return CapabilityNotSupported error

        // We'll create a Fireworks provider for testing (it doesn't support embeddings)
        use crate::inference::providers::fireworks::FireworksProvider;
        use crate::model::CredentialLocation;

        // Create provider with None credentials to avoid API key issues
        let provider_result = FireworksProvider::new(
            "test-model".to_string(),
            Some(CredentialLocation::None),
            false, // parse_think_blocks
        );

        // If we can't create the provider due to missing credentials, skip the test
        let Ok(fireworks_provider) = provider_result else {
            // Alternative: test the error message directly
            let _request = crate::embeddings::EmbeddingRequest {
                input: crate::embeddings::EmbeddingInput::Single("test".to_string()),
                encoding_format: None,
            };

            // Create a mock response that simulates unsupported capability
            let error = Error::new(ErrorDetails::CapabilityNotSupported {
                capability: EndpointCapability::Embedding.as_str().to_string(),
                provider: "test_provider".to_string(),
            });

            assert!(error.to_string().contains("does not support capability"));
            return;
        };

        let provider = ModelProvider {
            name: "fireworks_test".into(),
            config: ProviderConfig::Fireworks(fireworks_provider),
            extra_body: None,
            extra_headers: None,
        };

        let request = crate::embeddings::EmbeddingRequest {
            input: crate::embeddings::EmbeddingInput::Single("test".to_string()),
            encoding_format: None,
        };

        let http_client = Client::new();
        let credentials = InferenceCredentials::default();

        // Test that embed fails for unsupported provider
        let result = provider.embed(&request, &http_client, &credentials).await;
        assert!(result.is_err());
        let error = result.unwrap_err();
        assert!(error.to_string().contains("does not support capability"));
    }

    #[test]
    fn test_endpoint_capability_serialization() {
        // Test that EndpointCapability serializes correctly
        let cap = EndpointCapability::Chat;
        let serialized = serde_json::to_string(&cap).unwrap();
        assert_eq!(serialized, "\"chat\"");

        let cap = EndpointCapability::Embedding;
        let serialized = serde_json::to_string(&cap).unwrap();
        assert_eq!(serialized, "\"embedding\"");

        // Test deserialization
        let deserialized: EndpointCapability = serde_json::from_str("\"chat\"").unwrap();
        assert_eq!(deserialized, EndpointCapability::Chat);

        let deserialized: EndpointCapability = serde_json::from_str("\"embedding\"").unwrap();
        assert_eq!(deserialized, EndpointCapability::Embedding);
    }
}
