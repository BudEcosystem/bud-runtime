use axum::body::Body;
use axum::extract::{Extension, State};
use axum::http::HeaderMap;
use axum::response::sse::{Event, Sse};
use axum::response::{IntoResponse, Response};
use axum::{debug_handler, Json};
use futures::stream::Stream;
use http::StatusCode;
use metrics::counter;
use object_store::{ObjectStore, PutMode, PutOptions};
use secrecy::SecretString;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::future::Future;
use std::pin::Pin;
use std::sync::Arc;
use std::time::Duration;
use tokio::time::Instant;
use tokio_stream::StreamExt;
use tracing::instrument;
use uuid::Uuid;

use crate::analytics::RequestAnalytics;
use crate::cache::{CacheOptions, CacheParamsOptions};
use crate::clickhouse::ClickHouseConnectionInfo;
use crate::config_parser::{Config, ObjectStoreInfo};
use crate::error::{Error, ErrorDetails};
use crate::function::FunctionConfig;
use crate::function::{sample_variant, FunctionConfigChat};
use crate::gateway_util::{AppState, AppStateData, StructuredJson};
use crate::inference::types::extra_body::UnfilteredInferenceExtraBody;
use crate::inference::types::extra_headers::UnfilteredInferenceExtraHeaders;
use crate::inference::types::resolved_input::{FileWithPath, ResolvedInput};
use crate::inference::types::storage::StoragePath;
use crate::inference::types::{
    collect_chunks, serialize_or_log, AudioInferenceDatabaseInsert, Base64File,
    ChatInferenceDatabaseInsert, CollectChunksArgs, ContentBlockChatOutput, ContentBlockChunk,
    EmbeddingInferenceDatabaseInsert, FetchContext, FinishReason, ImageInferenceDatabaseInsert,
    InferenceResult, InferenceResultChunk, InferenceResultStream, Input,
    InternalJsonInferenceOutput, JsonInferenceDatabaseInsert, JsonInferenceOutput,
    ModelInferenceResponseWithMetadata, ModerationInferenceDatabaseInsert, RequestMessage,
    ResolvedInputMessageContent, Usage,
};
use crate::jsonschema_util::DynamicJSONSchema;
use crate::kafka::KafkaConnectionInfo;
use crate::model::ModelTable;
use crate::tool::{DynamicToolParams, ToolCallConfig, ToolChoice};
use crate::variant::chat_completion::ChatCompletionConfig;
use crate::variant::{InferenceConfig, JsonMode, Variant, VariantConfig};

use super::dynamic_evaluation_run::validate_inference_episode_id_and_apply_dynamic_evaluation_run;
use super::validate_tags;

/// The expected payload is a JSON object with the following fields:
#[derive(Debug, Default, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Params {
    // The function name. Exactly one of `function_name` or `model_name` must be provided.
    pub function_name: Option<String>,
    // The model name to run using a default function. Exactly one of `function_name` or `model_name` must be provided.
    pub model_name: Option<String>,
    // the episode ID (if not provided, it'll be set to inference_id)
    // NOTE: DO NOT GENERATE EPISODE IDS MANUALLY. THE API WILL DO THAT FOR YOU.
    pub episode_id: Option<Uuid>,
    // the input for the inference
    pub input: Input,
    // default False
    pub stream: Option<bool>,
    // Inference-time overrides for variant types (use with caution)
    #[serde(default)]
    pub params: InferenceParams,
    // if the client would like to pin a specific variant to be used
    // NOTE: YOU SHOULD TYPICALLY LET THE API SELECT A VARIANT FOR YOU (I.E. IGNORE THIS FIELD).
    //       ONLY PIN A VARIANT FOR SPECIAL USE CASES (E.G. TESTING / DEBUGGING VARIANTS).
    pub variant_name: Option<String>,
    // if true, the inference will not be stored
    pub dryrun: Option<bool>,
    // if true, the inference will be internal and validation of tags will be skipped
    #[serde(default)]
    pub internal: bool,
    // the tags to add to the inference
    #[serde(default)]
    pub tags: HashMap<String, String>,
    // dynamic information about tool calling. Don't directly include `dynamic_tool_params` in `Params`.
    #[serde(flatten)]
    pub dynamic_tool_params: DynamicToolParams,
    // `dynamic_tool_params` includes the following fields, passed at the top level of `Params`:
    // If provided, the inference will only use the specified tools (a subset of the function's tools)
    // allowed_tools: Option<Vec<String>>,
    // If provided, the inference will use the specified tools in addition to the function's tools
    // additional_tools: Option<Vec<Tool>>,
    // If provided, the inference will use the specified tool choice
    // tool_choice: Option<ToolChoice>,
    // If true, the inference will use parallel tool calls
    // parallel_tool_calls: Option<bool>,
    // If provided for a JSON inference, the inference will use the specified output schema instead of the
    // configured one. We only lazily validate this schema.
    pub output_schema: Option<Value>,
    #[serde(default)]
    pub cache_options: CacheParamsOptions,
    #[serde(default)]
    pub credentials: InferenceCredentials,
    /// If `true`, add an `original_response` field to the response, containing the raw string response from the model.
    /// Note that for complex variants (e.g. `experimental_best_of_n_sampling`), the response may not contain `original_response`
    /// if the fuser/judge model failed
    #[serde(default)]
    pub include_original_response: bool,
    #[serde(default)]
    pub extra_body: UnfilteredInferenceExtraBody,
    #[serde(default)]
    pub extra_headers: UnfilteredInferenceExtraHeaders,
    /// Observability metadata from auth middleware
    #[serde(skip)]
    pub observability_metadata: Option<ObservabilityMetadata>,
    /// The original request received by the gateway from the client
    #[serde(skip)]
    pub gateway_request: Option<String>,
}

#[derive(Clone, Debug, Default)]
pub struct ObservabilityMetadata {
    pub project_id: String,
    pub endpoint_id: String,
    pub model_id: String,
    // Authentication metadata
    pub api_key_id: Option<String>,
    pub user_id: Option<String>,
    pub api_key_project_id: Option<String>,
}

#[derive(Clone, Debug)]
struct InferenceMetadata {
    pub function_name: String,
    pub variant_name: String,
    pub episode_id: Uuid,
    pub inference_id: Uuid,
    pub input: ResolvedInput,
    pub dryrun: bool,
    pub start_time: Instant,
    pub inference_params: InferenceParams,
    pub model_name: Arc<str>,
    pub model_provider_name: Arc<str>,
    pub raw_request: String,
    pub system: Option<String>,
    pub input_messages: Vec<RequestMessage>,
    pub previous_model_inference_results: Vec<ModelInferenceResponseWithMetadata>,
    pub tags: HashMap<String, String>,
    pub tool_config: Option<ToolCallConfig>,
    pub dynamic_output_schema: Option<DynamicJSONSchema>,
    pub cached: bool,
    pub extra_body: UnfilteredInferenceExtraBody,
    pub extra_headers: UnfilteredInferenceExtraHeaders,
    pub observability_metadata: Option<ObservabilityMetadata>,
    pub gateway_request: Option<String>,
}

pub type InferenceCredentials = HashMap<String, SecretString>;

/// A handler for the inference endpoint
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
    analytics: Option<Extension<Arc<tokio::sync::Mutex<RequestAnalytics>>>>,
    StructuredJson(mut params): StructuredJson<Params>,
) -> Result<Response<Body>, Error> {
    // Extract observability metadata from headers
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

        Some(ObservabilityMetadata {
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

    params.observability_metadata = observability_metadata;

    let inference_output = inference(
        config.clone(),
        &http_client,
        clickhouse_connection_info.clone(),
        kafka_connection_info.clone(),
        model_credential_store,
        params,
        analytics.as_ref().map(|ext| ext.0.clone()),
    )
    .await;

    match inference_output {
        Ok(InferenceOutput::NonStreaming {
            response,
            result,
            write_info,
        }) => {
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

            // Serialize the response to capture what we're sending back to the client (without null values)
            let gateway_response =
                super::openai_compatible::serialize_without_nulls(&response).ok();

            // Perform the database write if we have write info
            if let Some(write_info) = write_info {
                let async_writes = config.gateway.observability.async_writes;
                let config = config.clone();
                let clickhouse_connection_info = clickhouse_connection_info.clone();
                let kafka_connection_info = kafka_connection_info.clone();

                let write_future = tokio::spawn(async move {
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
                        None, // No guardrail records for standard inference endpoint
                    )
                    .await;
                });

                if !async_writes {
                    write_future.await.map_err(|e| {
                        Error::new(ErrorDetails::InternalError {
                            message: format!("Failed to await ClickHouse inference write: {e:?}"),
                        })
                    })?;
                }
            }

            // Extract inference_id from the response
            let inference_id = match &response {
                InferenceResponse::Chat(chat_response) => chat_response.inference_id,
                InferenceResponse::Json(json_response) => json_response.inference_id,
            };

            let response_json = Json(response);
            let mut http_response = response_json.into_response();

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
        Ok(InferenceOutput::Streaming(stream)) => {
            let event_stream = prepare_serialized_events(stream);

            Ok(Sse::new(event_stream)
                .keep_alive(axum::response::sse::KeepAlive::new())
                .into_response())
        }
        Err(error) => {
            // The inference function already sends failure events internally for AllVariantsFailed
            // Convert error to response and add inference_id header for analytics middleware
            let mut error_response = error.into_response();

            // Extract inference_id from analytics if available
            if let Some(analytics_ext) = &analytics {
                if let Ok(analytics_guard) = analytics_ext.0.try_lock() {
                    if let Some(inference_id) = analytics_guard.record.inference_id {
                        error_response.headers_mut().insert(
                            "x-tensorzero-inference-id",
                            inference_id.to_string().parse().unwrap(),
                        );
                    }
                }
            }

            Ok(error_response)
        }
    }
}

pub type InferenceStream =
    Pin<Box<dyn Stream<Item = Result<InferenceResponseChunk, Error>> + Send>>;

pub enum InferenceOutput {
    NonStreaming {
        response: InferenceResponse,
        result: InferenceResult,
        write_info: Option<WriteInfo>,
    },
    Streaming(InferenceStream),
}

pub struct WriteInfo {
    pub resolved_input: ResolvedInput,
    pub metadata: InferenceDatabaseInsertMetadata,
    pub observability_metadata: Option<ObservabilityMetadata>,
    pub gateway_request: Option<String>,
    pub model_pricing: Option<crate::model::ModelPricing>,
}

impl std::fmt::Debug for InferenceOutput {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            InferenceOutput::NonStreaming { response, .. } => {
                write!(f, "NonStreaming({response:?})")
            }
            InferenceOutput::Streaming(_) => write!(f, "Streaming"),
        }
    }
}

pub const DEFAULT_FUNCTION_NAME: &str = "tensorzero::default";

#[derive(Copy, Clone, Debug)]
pub struct InferenceIds {
    pub inference_id: Uuid,
    pub episode_id: Uuid,
}

#[instrument(
    name="inference",
    skip(config, http_client, clickhouse_connection_info, kafka_connection_info, params),
    fields(
        function_name,
        model_name,
        variant_name,
        inference_id,
        episode_id,
        otel.name = "function_inference"
    )
)]
pub async fn inference(
    config: Arc<Config<'static>>,
    http_client: &reqwest::Client,
    clickhouse_connection_info: ClickHouseConnectionInfo,
    kafka_connection_info: KafkaConnectionInfo,
    model_credential_store: Arc<std::sync::RwLock<HashMap<String, SecretString>>>,
    params: Params,
    analytics: Option<Arc<tokio::sync::Mutex<RequestAnalytics>>>,
) -> Result<InferenceOutput, Error> {
    let span = tracing::Span::current();
    if let Some(function_name) = &params.function_name {
        span.record("function_name", function_name);
    }
    if let Some(model_name) = &params.model_name {
        span.record("model_name", model_name);
    }
    if let Some(variant_name) = &params.variant_name {
        span.record("variant_name", variant_name);
    }
    if let Some(episode_id) = &params.episode_id {
        span.record("episode_id", episode_id.to_string());
    }
    // To be used for the Inference table processing_time measurements
    let start_time = Instant::now();
    let inference_id = Uuid::now_v7();
    span.record("inference_id", inference_id.to_string());
    validate_tags(&params.tags, params.internal)?;

    if params.include_original_response && params.stream.unwrap_or(false) {
        return Err(ErrorDetails::InvalidRequest {
            message: "Cannot set both `include_original_response` and `stream` to `true`"
                .to_string(),
        }
        .into());
    }

    // Retrieve or generate the episode ID
    let episode_id = params.episode_id.unwrap_or(Uuid::now_v7());
    let mut params = params;
    validate_inference_episode_id_and_apply_dynamic_evaluation_run(
        episode_id,
        params.function_name.as_ref(),
        &mut params.variant_name,
        &mut params.tags,
        &clickhouse_connection_info,
    )
    .await?;
    tracing::Span::current().record("episode_id", episode_id.to_string());

    let models = config.models.read().await;
    let (function, function_name) = find_function(&params, &config, &models)?;
    // Release the read lock on the models table before potentially spawning
    drop(models);

    // Collect the function variant names as a Vec<&str>
    let mut candidate_variant_names: Vec<&str> =
        function.variants().keys().map(AsRef::as_ref).collect();

    // If the function has no variants, return an error
    if candidate_variant_names.is_empty() {
        return Err(ErrorDetails::InvalidFunctionVariants {
            message: format!("Function `{function_name}` has no variants"),
        }
        .into());
    }

    // Validate the input
    function.validate_inference_params(&params)?;

    let tool_config = function.prepare_tool_config(params.dynamic_tool_params, &config.tools)?;

    // If a variant is pinned, only that variant should be attempted
    if let Some(ref variant_name) = params.variant_name {
        candidate_variant_names.retain(|k| k == variant_name);

        // If the pinned variant doesn't exist, return an error
        if candidate_variant_names.is_empty() {
            return Err(ErrorDetails::UnknownVariant {
                name: variant_name.to_string(),
            }
            .into());
        }
        params.tags.insert(
            "tensorzero::variant_pinned".to_string(),
            variant_name.to_string(),
        );
    } else {
        // Remove all zero-weight variants - these can only be used if explicitly pinned above
        candidate_variant_names.retain(|name| {
            if let Some(variant) = function.variants().get(*name) {
                // Retain 'None' and positive-weight variants, discarding zero-weight variants
                variant.weight().is_none_or(|w| w > 0.0)
            } else {
                // Keep missing variants - later code will error if we try to use them
                true
            }
        });
    }

    // Clone values that will be needed after params is partially moved
    let obs_metadata_clone = params.observability_metadata.clone();
    let function_name_clone = params.function_name.clone();
    let model_name_clone = params.model_name.clone();
    let gateway_request_clone = params.gateway_request.clone();

    // Should we store the results?
    let dryrun = params.dryrun.unwrap_or(false);

    // Increment the request count if we're not in dryrun mode
    if !dryrun {
        let mut labels = vec![
            ("endpoint", "inference".to_string()),
            ("function_name", function_name.clone()),
        ];
        if let Some(ref model_name) = model_name_clone {
            labels.push(("model_name", model_name.clone()));
        }
        counter!("request_count", &labels).increment(1);
        counter!("inference_count", &labels).increment(1);
    }

    // Should we stream the inference?
    let stream = params.stream.unwrap_or(false);

    // Keep track of which variants failed
    let mut variant_errors = std::collections::HashMap::new();

    // Set up inference config
    let output_schema = params.output_schema.map(DynamicJSONSchema::new);
    let mut inference_config = InferenceConfig {
        function_name: &function_name,
        variant_name: None,
        templates: &config.templates,
        tool_config: tool_config.as_ref(),
        dynamic_output_schema: output_schema.as_ref(),
        ids: InferenceIds {
            inference_id,
            episode_id,
        },
        extra_cache_key: None,
        extra_body: Default::default(),
        extra_headers: Default::default(),
        gateway_request: params.gateway_request.clone(),
    };
    // Merge credentials from the credential store with the provided credentials
    let mut merged_credentials = params.credentials.clone();
    {
        #[expect(clippy::expect_used)]
        let credential_store = model_credential_store.read().expect("RwLock poisoned");
        for (key, value) in credential_store.iter() {
            // Only add if not already present (user-provided credentials take precedence)
            if !merged_credentials.contains_key(key) {
                merged_credentials.insert(key.clone(), value.clone());
            }
        }
    }

    let inference_clients = InferenceClients {
        http_client,
        clickhouse_connection_info: &clickhouse_connection_info,
        credentials: &merged_credentials,
        cache_options: &(params.cache_options, dryrun).into(),
    };

    let models = config.models.read().await;
    let inference_models = InferenceModels { models: &models };

    let resolved_input = params
        .input
        .resolve(&FetchContext {
            client: http_client,
            object_store_info: &config.object_store_info,
        })
        .await?;
    // Keep sampling variants until one succeeds
    while !candidate_variant_names.is_empty() {
        let (variant_name, variant) = sample_variant(
            &mut candidate_variant_names,
            function.variants(),
            &function_name,
            &episode_id,
        )?;
        // Will be edited by the variant as part of making the request so we must clone here
        let variant_inference_params = params.params.clone();

        inference_config.variant_name = Some(variant_name);
        inference_config.extra_body = params.extra_body.clone();
        inference_config.extra_headers = params.extra_headers.clone();
        if stream {
            let result = variant
                .infer_stream(
                    &resolved_input,
                    &inference_models,
                    function.as_ref(),
                    &inference_config,
                    &inference_clients,
                    variant_inference_params,
                )
                .await;

            // Make sure the response worked prior to launching the thread and starting to return chunks.
            // The provider has already checked that the first chunk is OK.
            let (stream, model_used_info) = match result {
                Ok((stream, model_used_info)) => (stream, model_used_info),
                Err(e) => {
                    tracing::warn!(
                        "functions.{function_name:?}.variants.{variant_name:?} failed during inference: {e}",
                        function_name = params.function_name,
                        variant_name = variant_name,
                    );
                    variant_errors.insert(variant_name.to_string(), e);
                    continue;
                }
            };

            let extra_body = inference_config.extra_body.clone();
            let extra_headers = inference_config.extra_headers.clone();

            // Create InferenceMetadata for a streaming inference
            let inference_metadata = InferenceMetadata {
                function_name: function_name.to_string(),
                variant_name: variant_name.to_string(),
                inference_id,
                episode_id,
                input: resolved_input.clone(),
                dryrun,
                start_time,
                inference_params: model_used_info.inference_params,
                model_name: model_used_info.model_name,
                model_provider_name: model_used_info.model_provider_name,
                raw_request: model_used_info.raw_request,
                system: model_used_info.system,
                input_messages: model_used_info.input_messages,
                previous_model_inference_results: model_used_info.previous_model_inference_results,
                tags: params.tags,
                tool_config,
                dynamic_output_schema: output_schema,
                cached: model_used_info.cached,
                extra_body,
                extra_headers,
                observability_metadata: params.observability_metadata,
                gateway_request: params
                    .gateway_request
                    .clone()
                    .or(model_used_info.gateway_request),
            };

            let stream = create_stream(
                function,
                config.clone(),
                inference_metadata,
                stream,
                clickhouse_connection_info,
                kafka_connection_info,
            );

            return Ok(InferenceOutput::Streaming(Box::pin(stream)));
        } else {
            let result = variant
                .infer(
                    &resolved_input,
                    &inference_models,
                    function.as_ref(),
                    &inference_config,
                    &inference_clients,
                    variant_inference_params,
                )
                .await;

            let mut result = match result {
                Ok(result) => result,
                Err(e) => {
                    tracing::warn!(
                        "functions.{function_name}.variants.{variant_name} failed during inference for inference_id {inference_id}: {e}",
                        function_name = function_name,
                        variant_name = variant_name,
                        inference_id = inference_id,
                    );
                    variant_errors.insert(variant_name.to_string(), e);
                    continue;
                }
            };

            // Prepare write info if not dryrun
            let write_info = if !dryrun {
                let extra_body = inference_config.extra_body.clone();
                let extra_headers = inference_config.extra_headers.clone();
                let write_metadata = InferenceDatabaseInsertMetadata {
                    function_name: function_name.to_string(),
                    variant_name: variant_name.to_string(),
                    episode_id,
                    tool_config,
                    processing_time: Some(start_time.elapsed()),
                    tags: params.tags.clone(),
                    extra_body,
                    extra_headers,
                };

                // Get model pricing from the result
                let model_pricing =
                    if let Some(first_result) = result.model_inference_results().first() {
                        // Look up the model config to get pricing
                        match models.get(&first_result.model_name).await {
                            Ok(Some(model)) => model.pricing.clone(),
                            _ => None,
                        }
                    } else {
                        None
                    };

                Some(WriteInfo {
                    resolved_input: resolved_input.clone(),
                    metadata: write_metadata,
                    observability_metadata: params.observability_metadata.clone(),
                    gateway_request: params.gateway_request.clone(),
                    model_pricing,
                })
            } else {
                None
            };

            if !params.include_original_response {
                result.set_original_response(None);
            }

            let response =
                InferenceResponse::new(result.clone(), episode_id, variant_name.to_string());

            return Ok(InferenceOutput::NonStreaming {
                response,
                result,
                write_info,
            });
        }
    }

    // Eventually, if we get here, it means we tried every variant and none of them worked
    let error = Error::new(ErrorDetails::AllVariantsFailed {
        errors: variant_errors,
    });

    // Serialize the error response BEFORE sending to metrics
    // This ensures the gateway_response field contains what will be sent to the client
    let (_status_code, error_response_json) = error.to_response_json();

    // Set inference_id in analytics so the middleware can extract it from header
    if let Some(analytics_arc) = &analytics {
        if let Ok(mut analytics_guard) = analytics_arc.try_lock() {
            analytics_guard.record.inference_id = Some(inference_id);
        }
    }

    // Send failure event to Kafka and ClickHouse for observability
    if !dryrun {
        send_failure_event(
            &kafka_connection_info,
            &clickhouse_connection_info,
            inference_id,
            episode_id,
            &error,
            Some(&error_response_json), // Pass the serialized error response
            &resolved_input,
            obs_metadata_clone,
            function_name_clone,
            model_name_clone,
            start_time,
            gateway_request_clone,
        )
        .await;
    }

    Err(error)
}

/// Finds a function by `function_name` or `model_name`, erroring if an
/// invalid combination of parameters is provided.
/// If `model_name` is specified, then we use the special 'default' function
/// Returns the function config and the function name
fn find_function(
    params: &Params,
    config: &Config,
    models: &ModelTable,
) -> Result<(Arc<FunctionConfig>, String), Error> {
    match (&params.function_name, &params.model_name) {
        // Get the function config or return an error if it doesn't exist
        (Some(function_name), None) => Ok((
            config.get_function(function_name)?.into_owned(),
            function_name.to_string(),
        )),
        (None, Some(model_name)) => {
            if params.variant_name.is_some() {
                return Err(ErrorDetails::InvalidInferenceTarget {
                    message: "`variant_name` cannot be provided when using `model_name`"
                        .to_string(),
                }
                .into());
            }
            if let Err(e) = models.validate(model_name) {
                return Err(ErrorDetails::InvalidInferenceTarget {
                    message: format!("Invalid model name: {e}"),
                }
                .into());
            }

            Ok((
                Arc::new(FunctionConfig::Chat(FunctionConfigChat {
                    variants: [(
                        model_name.clone(),
                        VariantConfig::ChatCompletion(ChatCompletionConfig {
                            model: (&**model_name).into(),
                            ..Default::default()
                        }),
                    )]
                    .into_iter()
                    .collect(),
                    system_schema: None,
                    user_schema: None,
                    assistant_schema: None,
                    tools: vec![],
                    tool_choice: ToolChoice::Auto,
                    parallel_tool_calls: None,
                    description: None,
                })),
                DEFAULT_FUNCTION_NAME.to_string(),
            ))
        }
        (Some(_), Some(_)) => Err(ErrorDetails::InvalidInferenceTarget {
            message: "Only one of `function_name` or `model_name` can be provided".to_string(),
        }
        .into()),
        (None, None) => Err(ErrorDetails::InvalidInferenceTarget {
            message: "Either `function_name` or `model_name` must be provided".to_string(),
        }
        .into()),
    }
}

fn create_stream(
    function: Arc<FunctionConfig>,
    config: Arc<Config<'static>>,
    metadata: InferenceMetadata,
    mut stream: InferenceResultStream,
    clickhouse_connection_info: ClickHouseConnectionInfo,
    kafka_connection_info: KafkaConnectionInfo,
) -> impl Stream<Item = Result<InferenceResponseChunk, Error>> + Send {
    async_stream::stream! {
        let mut buffer = vec![];
        let mut gateway_response_chunks = vec![];

        while let Some(chunk) = stream.next().await {
            match chunk {
                Ok(chunk) => {
                    buffer.push(chunk.clone());
                    if let Some(response_chunk) = prepare_response_chunk(&metadata, chunk) {
                        // Capture the serialized chunk for gateway_response
                        if let Ok(chunk_json) = serde_json::to_string(&response_chunk) {
                            gateway_response_chunks.push(format!("data: {}\n\n", chunk_json));
                        }
                        yield Ok(response_chunk);
                    }
                }
                Err(e) => yield Err(e),
            }
        }

        // Add the final [DONE] event
        gateway_response_chunks.push("data: [DONE]\n\n".to_string());
        if !metadata.dryrun {
            // IMPORTANT: The following code will not be reached if the stream is interrupted.
            // Only do things that would be ok to skip in that case.
            //
            // For example, if we were using ClickHouse for billing, we would want to store the interrupted requests.
            //
            // If we really care about storing interrupted requests, we should use a drop guard:
            // https://github.com/tokio-rs/axum/discussions/1060
            let InferenceMetadata {
                function_name,
                variant_name,
                inference_id,
                episode_id,
                input,
                dryrun: _,
                start_time,
                inference_params,
                model_name,
                model_provider_name,
                raw_request,
                system,
                input_messages,
                previous_model_inference_results,
                tags,
                tool_config,
                dynamic_output_schema,
                cached,
                extra_body,
                extra_headers,
                observability_metadata,
                gateway_request,
            } = metadata;

            let config = config.clone();
            let async_write = config.gateway.observability.async_writes;
            let write_future = async move {
                let templates = &config.templates;
                let model_name_for_pricing = model_name.clone(); // Clone model_name before moving into CollectChunksArgs
                let collect_chunks_args = CollectChunksArgs {
                    value: buffer,
                    inference_id,
                    episode_id,
                    system,
                    input_messages,
                    function,
                    model_name,
                    model_provider_name,
                    raw_request,
                    inference_params,
                    function_name: &function_name,
                    variant_name: &variant_name,
                    dynamic_output_schema,
                    templates,
                    tool_config: tool_config.as_ref(),
                    cached,
                    extra_body: extra_body.clone(),
                    extra_headers: extra_headers.clone(),
                };
                let inference_response: Result<InferenceResult, Error> =
                    collect_chunks(collect_chunks_args).await;

                let inference_response = inference_response.ok();

                if let Some(inference_response) = inference_response {
                    let mut inference_response = inference_response;
                    inference_response.mut_model_inference_results().extend(previous_model_inference_results);
                    let write_metadata = InferenceDatabaseInsertMetadata {
                        function_name,
                        variant_name,
                        episode_id,
                        tool_config,
                        processing_time: Some(start_time.elapsed()),
                        tags,
                        extra_body,
                        extra_headers,
                    };
                    let config = config.clone();

                        let clickhouse_connection_info = clickhouse_connection_info.clone();
                        let kafka_connection_info = kafka_connection_info.clone();
                        // Concatenate all chunks to form the complete gateway response
                        let gateway_response = if gateway_response_chunks.is_empty() {
                            None
                        } else {
                            Some(gateway_response_chunks.join(""))
                        };

                        // Get model pricing from the model config
                        let models = config.models.read().await;
                        let model_pricing = match models.get(&model_name_for_pricing).await {
                            Ok(Some(model)) => model.pricing.clone(),
                            _ => None,
                        };

                        write_inference(
                            &clickhouse_connection_info,
                            &kafka_connection_info,
                            &config,
                            input,
                            inference_response,
                            write_metadata,
                            observability_metadata,
                            gateway_request,
                            gateway_response,
                            model_pricing,
                            None, // No guardrail records for standard inference endpoint
                        ).await;

                }
            };
            if async_write {
                tokio::spawn(write_future);
            } else {
                write_future.await;
            }
        }
    }
}

fn prepare_response_chunk(
    metadata: &InferenceMetadata,
    chunk: InferenceResultChunk,
) -> Option<InferenceResponseChunk> {
    InferenceResponseChunk::new(
        chunk,
        metadata.inference_id,
        metadata.episode_id,
        metadata.variant_name.clone(),
        metadata.cached,
    )
}

// Prepares an Event for SSE on the way out of the gateway
// When None is passed in, we send "[DONE]" to the client to signal the end of the stream
fn prepare_serialized_events(
    mut stream: InferenceStream,
) -> impl Stream<Item = Result<Event, Error>> {
    async_stream::stream! {
        while let Some(chunk) = stream.next().await {
            let chunk_json = match chunk {
                Ok(chunk) => {
                    serde_json::to_value(chunk).map_err(|e| {
                        Error::new(ErrorDetails::Inference {
                            message: format!("Failed to convert chunk to JSON: {e}"),
                        })
                    })?
                },
                Err(e) => {
                    // NOTE - in the future, we may want to end the stream early if we get an error
                    serde_json::json!({"error": e.to_string()})
                }
            };
            yield Event::default().json_data(chunk_json).map_err(|e| {
                Error::new(ErrorDetails::Inference {
                    message: format!("Failed to convert Value to Event: {e}"),
                })
            })
        }
        yield Ok(Event::default().data("[DONE]"));
    }
}

#[derive(Debug, Clone)]
pub struct InferenceDatabaseInsertMetadata {
    pub function_name: String,
    pub variant_name: String,
    pub episode_id: Uuid,
    pub tool_config: Option<ToolCallConfig>,
    pub processing_time: Option<Duration>,
    pub tags: HashMap<String, String>,
    pub extra_body: UnfilteredInferenceExtraBody,
    pub extra_headers: UnfilteredInferenceExtraHeaders,
}

async fn write_file(
    object_store: &Option<ObjectStoreInfo>,
    raw: &Base64File,
    storage_path: &StoragePath,
) -> Result<(), Error> {
    if let Some(object_store) = object_store {
        // The store might be explicitly disabled
        if let Some(store) = object_store.object_store.as_ref() {
            let data = raw.data()?;
            let bytes = aws_smithy_types::base64::decode(data).map_err(|e| {
                Error::new(ErrorDetails::ObjectStoreWrite {
                    message: format!("Failed to decode file as base64: {e:?}"),
                    path: storage_path.clone(),
                })
            })?;
            let res = store
                .put_opts(
                    &storage_path.path,
                    bytes.into(),
                    PutOptions {
                        mode: PutMode::Create,
                        ..Default::default()
                    },
                )
                .await;
            match res {
                Ok(_) | Err(object_store::Error::AlreadyExists { .. }) => {}
                Err(e) => {
                    return Err(ErrorDetails::ObjectStoreWrite {
                        message: format!("Failed to write file to object store: {e:?}"),
                        path: storage_path.clone(),
                    }
                    .into());
                }
            }
        }
    } else {
        return Err(ErrorDetails::InternalError {
            message: "Called `write_file` with no object store configured".to_string(),
        }
        .into());
    }
    Ok(())
}

pub async fn write_inference(
    clickhouse_connection_info: &ClickHouseConnectionInfo,
    kafka_connection_info: &crate::kafka::KafkaConnectionInfo,
    config: &Config<'_>,
    input: ResolvedInput,
    result: InferenceResult,
    metadata: InferenceDatabaseInsertMetadata,
    observability_metadata: Option<ObservabilityMetadata>,
    gateway_request: Option<String>,
    gateway_response: Option<String>,
    model_pricing: Option<crate::model::ModelPricing>,
    guardrail_records: Option<Vec<crate::guardrail::GuardrailInferenceDatabaseInsert>>,
) {
    let mut futures: Vec<Pin<Box<dyn Future<Output = ()> + Send>>> = Vec::new();
    if config.gateway.observability.enabled.unwrap_or(true) {
        for message in &input.messages {
            for content_block in &message.content {
                if let ResolvedInputMessageContent::File(FileWithPath {
                    file: raw,
                    storage_path,
                }) = content_block
                {
                    futures.push(Box::pin(async {
                        if let Err(e) =
                            write_file(&config.object_store_info, raw, storage_path).await
                        {
                            tracing::error!("Failed to write image to object store: {e:?}");
                        }
                    }));
                }
            }
        }
    }

    // Update model inference results with gateway fields if provided
    let mut result = result;
    for model_result in result.mut_model_inference_results() {
        if let Some(gw_request) = &gateway_request {
            model_result.gateway_request = Some(gw_request.clone());
        }
        if let Some(gw_response) = &gateway_response {
            model_result.gateway_response = Some(gw_response.clone());
        }
    }

    let model_responses: Vec<serde_json::Value> = result.get_serialized_model_inferences();

    // Clone for Kafka before moving into ClickHouse writes
    let kafka_connection_info = kafka_connection_info.clone();
    let result_clone = result.clone();
    let metadata_clone = metadata.clone();

    // ClickHouse writes
    futures.push(Box::pin(async {
        // Write the model responses to the ModelInference table
        for response in model_responses {
            let _ = clickhouse_connection_info
                .write(&[response], "ModelInference")
                .await;
        }
        // Write the inference to the Inference table
        match result {
            InferenceResult::Chat(result) => {
                let chat_inference =
                    ChatInferenceDatabaseInsert::new(result, input.clone(), metadata);
                let _ = clickhouse_connection_info
                    .write(&[chat_inference], "ChatInference")
                    .await;
            }
            InferenceResult::Json(result) => {
                let json_inference =
                    JsonInferenceDatabaseInsert::new(result, input.clone(), metadata);
                let _ = clickhouse_connection_info
                    .write(&[json_inference], "JsonInference")
                    .await;
            }
            InferenceResult::Embedding(result) => {
                let embedding_inference =
                    EmbeddingInferenceDatabaseInsert::new(result, input.clone(), metadata);
                let _ = clickhouse_connection_info
                    .write(&[embedding_inference], "EmbeddingInference")
                    .await;
            }
            InferenceResult::AudioTranscription(result) => {
                let audio_inference = AudioInferenceDatabaseInsert::new_transcription(
                    result,
                    "audio file".to_string(), // Will be overridden with actual input
                    metadata,
                );
                let _ = clickhouse_connection_info
                    .write(&[audio_inference], "AudioInference")
                    .await;
            }
            InferenceResult::AudioTranslation(result) => {
                let audio_inference = AudioInferenceDatabaseInsert::new_translation(
                    result,
                    "audio file".to_string(), // Will be overridden with actual input
                    metadata,
                );
                let _ = clickhouse_connection_info
                    .write(&[audio_inference], "AudioInference")
                    .await;
            }
            InferenceResult::TextToSpeech(result) => {
                // Extract the text input from the input
                let text_input = input
                    .messages
                    .first()
                    .and_then(|msg| msg.content.first())
                    .and_then(|content| match content {
                        ResolvedInputMessageContent::Text { value } => {
                            value.as_str().map(|s| s.to_string())
                        }
                        _ => None,
                    })
                    .unwrap_or_else(|| "text input".to_string());

                let audio_inference =
                    AudioInferenceDatabaseInsert::new_text_to_speech(result, text_input, metadata);
                let _ = clickhouse_connection_info
                    .write(&[audio_inference], "AudioInference")
                    .await;
            }
            InferenceResult::ImageGeneration(result) => {
                // Extract the prompt from the input
                let prompt = input
                    .messages
                    .first()
                    .and_then(|msg| msg.content.first())
                    .and_then(|content| match content {
                        ResolvedInputMessageContent::Text { value } => {
                            value.as_str().map(|s| s.to_string())
                        }
                        _ => None,
                    })
                    .unwrap_or_else(|| "image prompt".to_string());

                let image_inference = ImageInferenceDatabaseInsert::new(result, prompt, metadata);
                let _ = clickhouse_connection_info
                    .write(&[image_inference], "ImageInference")
                    .await;
            }
            InferenceResult::Moderation(result) => {
                // Extract the input text from the input
                let input_text = input
                    .messages
                    .first()
                    .and_then(|msg| msg.content.first())
                    .and_then(|content| match content {
                        ResolvedInputMessageContent::Text { value } => {
                            // Handle both direct string values and JSON string values
                            match value {
                                serde_json::Value::String(s) => Some(s.clone()),
                                _ => value.as_str().map(|s| s.to_string()),
                            }
                        }
                        _ => None,
                    })
                    .unwrap_or_else(|| "moderation input".to_string());

                let moderation_inference =
                    ModerationInferenceDatabaseInsert::new(result, input_text, metadata);
                let _ = clickhouse_connection_info
                    .write(&[moderation_inference], "ModerationInference")
                    .await;
            }
        }

        // Write guardrail records if provided
        if let Some(guardrail_records) = guardrail_records {
            // Batch write all guardrail records at once for efficiency
            if !guardrail_records.is_empty() {
                let _ = clickhouse_connection_info
                    .write(&guardrail_records, "GuardrailInference")
                    .await;
            }
        }
    }));

    // Kafka observability metrics
    let model_pricing = model_pricing.clone();

    futures.push(Box::pin(async move {
        // Create observability event from inference result
        let inference_id = match &result_clone {
            InferenceResult::Chat(result) => result.inference_id,
            InferenceResult::Json(result) => result.inference_id,
            InferenceResult::Embedding(result) => result.inference_id,
            InferenceResult::AudioTranscription(result) => result.inference_id,
            InferenceResult::AudioTranslation(result) => result.inference_id,
            InferenceResult::TextToSpeech(result) => result.inference_id,
            InferenceResult::ImageGeneration(result) => result.inference_id,
            InferenceResult::Moderation(result) => result.inference_id,
        };

        let request_arrival_time = chrono::Utc::now()
            - chrono::Duration::milliseconds(
                metadata_clone
                    .processing_time
                    .map(|d| d.as_millis() as i64)
                    .unwrap_or(0),
            );
        let request_forward_time = request_arrival_time + chrono::Duration::milliseconds(10); // Approximate forward time

        // Extract model info
        let model_id = match &result_clone {
            InferenceResult::Chat(result) => result
                .model_inference_results
                .first()
                .map(|m| m.model_name.clone())
                .unwrap_or_else(|| Arc::from("unknown")),
            InferenceResult::Json(result) => result
                .model_inference_results
                .first()
                .map(|m| m.model_name.clone())
                .unwrap_or_else(|| Arc::from("unknown")),
            InferenceResult::Embedding(result) => result
                .model_inference_results
                .first()
                .map(|m| m.model_name.clone())
                .unwrap_or_else(|| Arc::from("unknown")),
            InferenceResult::AudioTranscription(result) => result
                .model_inference_results
                .first()
                .map(|m| m.model_name.clone())
                .unwrap_or_else(|| Arc::from("unknown")),
            InferenceResult::AudioTranslation(result) => result
                .model_inference_results
                .first()
                .map(|m| m.model_name.clone())
                .unwrap_or_else(|| Arc::from("unknown")),
            InferenceResult::TextToSpeech(result) => result
                .model_inference_results
                .first()
                .map(|m| m.model_name.clone())
                .unwrap_or_else(|| Arc::from("unknown")),
            InferenceResult::ImageGeneration(result) => result
                .model_inference_results
                .first()
                .map(|m| m.model_name.clone())
                .unwrap_or_else(|| Arc::from("unknown")),
            InferenceResult::Moderation(result) => result
                .model_inference_results
                .first()
                .map(|m| m.model_name.clone())
                .unwrap_or_else(|| Arc::from("unknown")),
        };

        // Calculate cost (simplified - you may want to enhance this)
        let usage = match &result_clone {
            InferenceResult::Chat(result) => &result.usage,
            InferenceResult::Json(result) => &result.usage,
            InferenceResult::Embedding(result) => &result.usage,
            InferenceResult::AudioTranscription(result) => &result.usage,
            InferenceResult::AudioTranslation(result) => &result.usage,
            InferenceResult::TextToSpeech(result) => &result.usage,
            InferenceResult::ImageGeneration(result) => &result.usage,
            InferenceResult::Moderation(result) => &result.usage,
        };
        // Calculate cost using actual pricing if available, otherwise use defaults
        let cost = if usage.input_tokens > 0 || usage.output_tokens > 0 {
            if let Some(pricing) = &model_pricing {
                // Convert tokens to the pricing unit (e.g., if per_tokens is 1000, divide by 1000)
                let input_multiplier = usage.input_tokens as f64 / pricing.per_tokens as f64;
                let output_multiplier = usage.output_tokens as f64 / pricing.per_tokens as f64;

                let total_cost = (input_multiplier * pricing.input_cost)
                    + (output_multiplier * pricing.output_cost);
                Some(total_cost)
            } else {
                // Fallback to default pricing if not configured
                // Using reasonable defaults: $0.01 per 1K input tokens, $0.03 per 1K output tokens
                Some((usage.input_tokens as f64 * 0.00001) + (usage.output_tokens as f64 * 0.00003))
            }
        } else {
            None
        };

        // Use observability metadata if available, otherwise fall back to function/variant names
        let (project_id, endpoint_id, obs_model_id, api_key_id, user_id, api_key_project_id) =
            if let Some(obs_metadata) = observability_metadata {
                (
                    obs_metadata.project_id.clone(),
                    obs_metadata.endpoint_id.clone(),
                    obs_metadata.model_id.clone(),
                    obs_metadata.api_key_id.clone(),
                    obs_metadata.user_id.clone(),
                    obs_metadata.api_key_project_id.clone(),
                )
            } else {
                (
                    metadata_clone.function_name.clone(),
                    metadata_clone.variant_name.clone(),
                    model_id.to_string(),
                    None,
                    None,
                    None,
                )
            };

        let event = crate::kafka::cloudevents::ObservabilityEvent {
            inference_id,
            project_id,
            endpoint_id,
            model_id: obs_model_id,
            is_success: true,
            request_arrival_time,
            request_forward_time,
            request_ip: None, // Would need to extract from request context
            cost,
            response_analysis: None,
            api_key_id,
            user_id,
            api_key_project_id,
            error_code: None, // No error for successful inferences
            error_message: None,
            error_type: None,
            status_code: None,
        };

        // Send to Kafka observability topic
        if let Err(e) = kafka_connection_info.add_observability_event(event).await {
            tracing::error!("Failed to send observability event to Kafka: {}", e);
        }
    }));
    futures::future::join_all(futures).await;
}

/// Extract provider status code from nested error HashMap
/// When errors are wrapped (e.g., AllVariantsFailed wrapping InferenceClient),
/// we want the provider's status code (400) not the wrapper's (502)
fn extract_provider_status_code(
    errors: &HashMap<String, Error>,
    fallback_error: &Error,
) -> StatusCode {
    errors
        .values()
        .next()
        .and_then(|e| match e.get_details() {
            ErrorDetails::InferenceClient { status_code, .. } => *status_code,
            _ => None,
        })
        .unwrap_or_else(|| fallback_error.status_code())
}

/// Send failure event to Kafka for observability when an inference fails
async fn send_failure_event(
    kafka_connection_info: &KafkaConnectionInfo,
    clickhouse_connection_info: &ClickHouseConnectionInfo,
    inference_id: Uuid,
    _episode_id: Uuid, // Currently unused but kept for future use
    error: &Error,
    gateway_response: Option<&serde_json::Value>, // Add gateway_response parameter
    resolved_input: &ResolvedInput,
    observability_metadata: Option<ObservabilityMetadata>,
    function_name: Option<String>,
    model_name: Option<String>,
    start_time: Instant,
    gateway_request: Option<String>,
) {
    let request_arrival_time = chrono::Utc::now()
        - chrono::Duration::milliseconds(start_time.elapsed().as_millis() as i64);
    let request_forward_time = request_arrival_time + chrono::Duration::milliseconds(10);

    // Extract error details
    let error_details = error.get_details();
    let error_message = error.to_string();

    // Extract the actual provider status code from nested errors
    // When errors are wrapped (e.g., AllVariantsFailed wrapping InferenceClient),
    // we want the provider's status code (400) not the wrapper's (502)
    let status_code = match error_details {
        ErrorDetails::AllVariantsFailed { errors } => extract_provider_status_code(errors, error),
        ErrorDetails::ModelProvidersExhausted { provider_errors } => {
            extract_provider_status_code(provider_errors, error)
        }
        ErrorDetails::ModelChainExhausted { model_errors } => {
            extract_provider_status_code(model_errors, error)
        }
        ErrorDetails::InferenceClient { status_code, .. } => {
            status_code.unwrap_or_else(|| error.status_code())
        }
        _ => error.status_code(),
    };

    // Determine error type based on ErrorDetails variant
    let error_type = match error_details {
        ErrorDetails::AllVariantsFailed { .. } => "AllVariantsFailed",
        ErrorDetails::InvalidInferenceTarget { .. } => "InvalidInferenceTarget",
        ErrorDetails::ApiKeyMissing { .. } => "ApiKeyMissing",
        ErrorDetails::BadCredentialsPreInference { .. } => "BadCredentials",
        ErrorDetails::InferenceClient { .. } => "InferenceClient",
        ErrorDetails::InferenceServer { .. } => "InferenceServer",
        ErrorDetails::InferenceTimeout { .. } => "InferenceTimeout",
        ErrorDetails::InputValidation { .. } => "InputValidation",
        ErrorDetails::OutputValidation { .. } => "OutputValidation",
        ErrorDetails::GuardrailInputViolation { .. } => "GuardrailInputViolation",
        ErrorDetails::GuardrailOutputViolation { .. } => "GuardrailOutputViolation",
        ErrorDetails::JsonSchemaValidation { .. } => "JsonSchemaValidation",
        ErrorDetails::ModelProvidersExhausted { .. } => "ModelProvidersExhausted",
        ErrorDetails::ModelChainExhausted { .. } => "ModelChainExhausted",
        _ => "UnknownError",
    };

    // Use observability metadata if available, otherwise use function/model names
    let (project_id, endpoint_id, model_id, api_key_id, user_id, api_key_project_id) =
        if let Some(obs_metadata) = &observability_metadata {
            (
                obs_metadata.project_id.clone(),
                obs_metadata.endpoint_id.clone(),
                obs_metadata.model_id.clone(),
                obs_metadata.api_key_id.clone(),
                obs_metadata.user_id.clone(),
                obs_metadata.api_key_project_id.clone(),
            )
        } else {
            // Fallback to function/model names
            let fn_name = function_name.as_deref().unwrap_or("unknown");
            let mdl_name = model_name.as_deref().unwrap_or("unknown");
            (
                fn_name.to_string(),
                "unknown".to_string(),
                mdl_name.to_string(),
                None,
                None,
                None,
            )
        };

    let event = crate::kafka::cloudevents::ObservabilityEvent {
        inference_id,
        project_id: project_id.clone(),
        endpoint_id: endpoint_id.clone(),
        model_id: model_id.clone(),
        is_success: false, // This is a failure event
        request_arrival_time,
        request_forward_time,
        request_ip: None,
        cost: None, // Failed requests may still incur costs, but we don't know yet
        response_analysis: None,
        api_key_id: api_key_id.clone(),
        user_id: user_id.clone(),
        api_key_project_id: api_key_project_id.clone(),
        error_code: Some(format!("{:?}", status_code)),
        error_message: Some(error_message.clone()),
        error_type: Some(error_type.to_string()),
        status_code: Some(status_code.as_u16()),
    };

    // Send to Kafka observability topic
    if let Err(e) = kafka_connection_info
        .add_observability_event(event.clone())
        .await
    {
        tracing::error!("Failed to send failure observability event to Kafka: {}", e);
    }

    // Also write to ClickHouse for failed inferences
    // First, create a ModelInference record (required for JOIN queries)

    let serialized_input = serialize_or_log(&resolved_input.messages);

    // Use the gateway_response passed in (already serialized from the error response)
    let gateway_response = gateway_response.and_then(|v| serde_json::to_string(v).ok());

    let model_inference = crate::inference::types::ModelInferenceDatabaseInsert {
        id: uuid::Uuid::now_v7(),
        inference_id,
        raw_request: "".to_string(), // Failed before request could be made
        raw_response: error_message.clone(), // Store error as response
        system: resolved_input
            .system
            .as_ref()
            .and_then(|v| v.as_str())
            .map(|s| s.to_string()),
        input_messages: serialized_input.clone(),
        output: format!("Error: {}", error_message),
        input_tokens: None,
        output_tokens: None,
        response_time_ms: Some(start_time.elapsed().as_millis() as u32),
        model_name: model_id.clone(),
        model_provider_name: "unknown".to_string(),
        ttft_ms: None,
        cached: false,
        finish_reason: None,
        gateway_request,
        gateway_response,
        endpoint_type: "chat".to_string(),
        guardrail_scan_summary: Some(serde_json::json!({}).to_string()),
    };

    // Write the ModelInference record
    if let Err(e) = clickhouse_connection_info
        .write(&[model_inference], "ModelInference")
        .await
    {
        tracing::error!(
            "Failed to write failure to ClickHouse ModelInference: {}",
            e
        );
    }

    // Create ModelInferenceDetails record with error information
    // Note: The api_key_project_id might be truncated in the error - handle gracefully
    let parsed_api_key_project_id = api_key_project_id.and_then(|id| {
        // If the ID looks truncated (like "4c..."), try to handle it
        if id.len() < 36 {
            None // Skip invalid UUIDs
        } else {
            uuid::Uuid::parse_str(&id).ok()
        }
    });

    let inference_details = crate::clickhouse::ModelInferenceDetailsInsert {
        inference_id,
        request_ip: None, // Gateway metadata now in GatewayAnalytics table
        project_id: uuid::Uuid::parse_str(&project_id).ok().unwrap_or_default(),
        endpoint_id: uuid::Uuid::parse_str(&endpoint_id).ok().unwrap_or_default(),
        model_id: uuid::Uuid::parse_str(&model_id).ok().unwrap_or_default(),
        cost: None,
        response_analysis: None,
        is_success: false,
        request_arrival_time,
        request_forward_time,
        api_key_id: api_key_id.and_then(|id| uuid::Uuid::parse_str(&id).ok()),
        user_id: user_id.and_then(|id| uuid::Uuid::parse_str(&id).ok()),
        api_key_project_id: parsed_api_key_project_id,
        error_code: Some(format!("{:?}", status_code)),
        error_message: Some(error_message),
        error_type: Some(error_type.to_string()),
        status_code: Some(status_code.as_u16()),
    };

    if let Err(e) = clickhouse_connection_info
        .write(&[inference_details], "ModelInferenceDetails")
        .await
    {
        tracing::error!(
            "Failed to write failure to ClickHouse ModelInferenceDetails: {}",
            e
        );
    }
}

/// InferenceResponse and InferenceResultChunk determine what gets serialized and sent to the client

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(untagged, rename_all = "snake_case")]
pub enum InferenceResponse {
    Chat(ChatInferenceResponse),
    Json(JsonInferenceResponse),
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct ChatInferenceResponse {
    pub inference_id: Uuid,
    pub episode_id: Uuid,
    pub variant_name: String,
    pub content: Vec<ContentBlockChatOutput>,
    pub usage: Usage,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub original_response: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub finish_reason: Option<FinishReason>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct JsonInferenceResponse {
    pub inference_id: Uuid,
    pub episode_id: Uuid,
    pub variant_name: String,
    pub output: JsonInferenceOutput,
    pub usage: Usage,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub original_response: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub finish_reason: Option<FinishReason>,
}

impl InferenceResponse {
    pub fn new(inference_result: InferenceResult, episode_id: Uuid, variant_name: String) -> Self {
        match inference_result {
            InferenceResult::Chat(result) => InferenceResponse::Chat(ChatInferenceResponse {
                inference_id: result.inference_id,
                episode_id,
                variant_name,
                content: result.content,
                usage: result.usage,
                original_response: result.original_response,
                finish_reason: result.finish_reason,
            }),
            InferenceResult::Json(result) => {
                let InternalJsonInferenceOutput { raw, parsed, .. } = result.output;
                let output = JsonInferenceOutput { raw, parsed };
                InferenceResponse::Json(JsonInferenceResponse {
                    inference_id: result.inference_id,
                    episode_id,
                    variant_name,
                    output,
                    usage: result.usage,
                    original_response: result.original_response,
                    finish_reason: result.finish_reason,
                })
            }
            _ => {
                // Other inference types don't use the generic inference endpoint
                // They have their own OpenAI-compatible endpoints
                panic!("Unsupported inference type for InferenceResponse")
            }
        }
    }

    pub fn variant_name(&self) -> &str {
        match self {
            InferenceResponse::Chat(c) => &c.variant_name,
            InferenceResponse::Json(j) => &j.variant_name,
        }
    }

    pub fn inference_id(&self) -> Uuid {
        match self {
            InferenceResponse::Chat(c) => c.inference_id,
            InferenceResponse::Json(j) => j.inference_id,
        }
    }

    pub fn episode_id(&self) -> Uuid {
        match self {
            InferenceResponse::Chat(c) => c.episode_id,
            InferenceResponse::Json(j) => j.episode_id,
        }
    }

    pub fn get_serialized_output(&self) -> Result<String, Error> {
        match self {
            InferenceResponse::Chat(c) => c.get_serialized_output(),
            InferenceResponse::Json(j) => j.get_serialized_output(),
        }
    }
}

impl ChatInferenceResponse {
    pub fn get_serialized_output(&self) -> Result<String, Error> {
        serde_json::to_string(&self.content).map_err(|e| {
            Error::new(ErrorDetails::Inference {
                message: format!("Failed to serialize chat inference response: {e:?}"),
            })
        })
    }
}

impl JsonInferenceResponse {
    pub fn get_serialized_output(&self) -> Result<String, Error> {
        serde_json::to_string(&self.output).map_err(|e| {
            Error::new(ErrorDetails::Inference {
                message: format!("Failed to serialize json inference response: {e:?}"),
            })
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(untagged)]
pub enum InferenceResponseChunk {
    Chat(ChatInferenceResponseChunk),
    Json(JsonInferenceResponseChunk),
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ChatInferenceResponseChunk {
    pub inference_id: Uuid,
    pub episode_id: Uuid,
    pub variant_name: String,
    pub content: Vec<ContentBlockChunk>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub usage: Option<Usage>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub finish_reason: Option<FinishReason>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct JsonInferenceResponseChunk {
    pub inference_id: Uuid,
    pub episode_id: Uuid,
    pub variant_name: String,
    pub raw: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub usage: Option<Usage>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub finish_reason: Option<FinishReason>,
}

const ZERO_USAGE: Usage = Usage {
    input_tokens: 0,
    output_tokens: 0,
};

impl InferenceResponseChunk {
    fn new(
        inference_result: InferenceResultChunk,
        inference_id: Uuid,
        episode_id: Uuid,
        variant_name: String,
        cached: bool,
    ) -> Option<Self> {
        Some(match inference_result {
            InferenceResultChunk::Chat(result) => {
                InferenceResponseChunk::Chat(ChatInferenceResponseChunk {
                    inference_id,
                    episode_id,
                    variant_name,
                    content: result.content,
                    // Token usage is intended to represent 'billed tokens',
                    // so set it to zero if the result is cached
                    usage: if cached {
                        Some(ZERO_USAGE)
                    } else {
                        result.usage
                    },
                    finish_reason: result.finish_reason,
                })
            }
            InferenceResultChunk::Json(result) => {
                if result.raw.is_none() && result.usage.is_none() {
                    return None;
                }
                InferenceResponseChunk::Json(JsonInferenceResponseChunk {
                    inference_id,
                    episode_id,
                    variant_name,
                    raw: result.raw.unwrap_or_default(),
                    // Token usage is intended to represent 'billed tokens',
                    // so set it to zero if the result is cached
                    usage: if cached {
                        Some(ZERO_USAGE)
                    } else {
                        result.usage
                    },
                    finish_reason: result.finish_reason,
                })
            }
        })
    }

    pub fn episode_id(&self) -> Uuid {
        match self {
            InferenceResponseChunk::Chat(c) => c.episode_id,
            InferenceResponseChunk::Json(j) => j.episode_id,
        }
    }

    pub fn inference_id(&self) -> Uuid {
        match self {
            InferenceResponseChunk::Chat(c) => c.inference_id,
            InferenceResponseChunk::Json(j) => j.inference_id,
        }
    }

    pub fn variant_name(&self) -> &str {
        match self {
            InferenceResponseChunk::Chat(c) => &c.variant_name,
            InferenceResponseChunk::Json(j) => &j.variant_name,
        }
    }
}

// Carryall struct for clients used in inference
pub struct InferenceClients<'a> {
    pub http_client: &'a reqwest::Client,
    pub clickhouse_connection_info: &'a ClickHouseConnectionInfo,
    pub credentials: &'a InferenceCredentials,
    pub cache_options: &'a CacheOptions,
}

// Carryall struct for models used in inference
#[derive(Debug)]
pub struct InferenceModels<'a> {
    pub models: &'a ModelTable,
}

/// InferenceParams is the top-level struct for inference parameters.
/// We backfill these from the configs given in the variants used and ultimately write them to the database.
#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct InferenceParams {
    pub chat_completion: ChatCompletionInferenceParams,
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ChatCompletionInferenceParams {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_tokens: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub seed: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub top_p: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub presence_penalty: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub frequency_penalty: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub repetition_penalty: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub chat_template: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub chat_template_kwargs: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mm_processor_kwargs: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub guided_json: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub guided_regex: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub guided_choice: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub guided_grammar: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub structural_tag: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub guided_decoding_backend: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub guided_whitespace_pattern: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub json_mode: Option<JsonMode>,
    #[serde(default, skip_serializing_if = "is_false")]
    pub logprobs: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub top_logprobs: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stop: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub n: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub logit_bias: Option<HashMap<String, f32>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub user: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ignore_eos: Option<bool>,
}

impl ChatCompletionInferenceParams {
    pub fn backfill_with_variant_params(
        &mut self,
        temperature: Option<f32>,
        max_tokens: Option<u32>,
        seed: Option<u32>,
        top_p: Option<f32>,
        presence_penalty: Option<f32>,
        frequency_penalty: Option<f32>,
    ) {
        if self.temperature.is_none() {
            self.temperature = temperature;
        }
        if self.max_tokens.is_none() {
            self.max_tokens = max_tokens;
        }
        if self.seed.is_none() {
            self.seed = seed;
        }
        if self.top_p.is_none() {
            self.top_p = top_p;
        }
        if self.presence_penalty.is_none() {
            self.presence_penalty = presence_penalty;
        }
        if self.frequency_penalty.is_none() {
            self.frequency_penalty = frequency_penalty;
        }
    }
}

fn is_false(v: &bool) -> bool {
    !*v
}

/// Write a blocked inference to the database for observability
/// This is used when a request is blocked by guardrails before reaching the model
pub async fn write_blocked_inference(
    clickhouse_connection_info: &ClickHouseConnectionInfo,
    kafka_connection_info: &crate::kafka::KafkaConnectionInfo,
    config: &Config<'_>,
    model_name: &str,
    model_provider: &str,
    resolved_input: ResolvedInput,
    inference_id: Uuid,
    episode_id: Uuid,
    guardrail_records: Vec<crate::guardrail::GuardrailInferenceDatabaseInsert>,
    observability_metadata: Option<ObservabilityMetadata>,
    model_pricing: Option<crate::model::ModelPricing>,
    gateway_request: Option<String>,
) {
    use crate::inference::types::{
        current_timestamp, ChatInferenceResult, ContentBlockOutput, Latency, RequestMessage, Text,
    };
    // Create blocked content
    let blocked_content = vec![ContentBlockChatOutput::Text(Text {
        text: "Request blocked by content policy".to_string(),
    })];

    // Create the gateway response that would be sent to the client
    let gateway_response_json = serde_json::json!({
        "error": {
            "message": "Input content violates content policy",
            "type": "invalid_request_error",
            "code": "content_filter"
        }
    });
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
        guardrail_scan_summary: if !guardrail_records.is_empty() {
            let context = crate::guardrail::GuardrailExecutionContext {
                scan_records: guardrail_records.clone(),
                input_scan_time_ms: guardrail_records
                    .iter()
                    .filter(|r| r.guard_type == 1) // Input guard type
                    .filter_map(|r| r.scan_latency_ms)
                    .sum::<u32>()
                    .into(),
                output_scan_time_ms: None,
                response_terminated: true,
            };
            Some(serde_json::to_string(&context.build_summary()).unwrap_or_default())
        } else {
            None
        },
    };

    // Create blocked result
    let blocked_result = InferenceResult::Chat(ChatInferenceResult {
        inference_id,
        created: current_timestamp(),
        content: blocked_content,
        usage: Usage::default(),
        model_inference_results: vec![model_response],
        inference_params: InferenceParams::default(),
        original_response: None,
        finish_reason: Some(FinishReason::ContentFilter),
    });

    // Create metadata
    let metadata = InferenceDatabaseInsertMetadata {
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
    write_inference(
        clickhouse_connection_info,
        kafka_connection_info,
        config,
        resolved_input,
        blocked_result,
        metadata,
        observability_metadata,
        None, // gateway_request
        None, // gateway_response
        model_pricing,
        Some(guardrail_records),
    )
    .await;
}

#[cfg(test)]
mod tests {
    use super::*;

    use serde_json::json;
    use std::time::Duration;
    use uuid::Uuid;

    use crate::inference::types::{
        ChatInferenceResultChunk, ContentBlockChunk, File, FileKind, InputMessageContent,
        JsonInferenceResultChunk, Role, TextChunk,
    };

    #[tokio::test]
    async fn test_prepare_event() {
        // Test case 1: Valid Chat ProviderInferenceResponseChunk
        let content = vec![ContentBlockChunk::Text(TextChunk {
            text: "Test content".to_string(),
            id: "0".to_string(),
        })];
        let chunk = InferenceResultChunk::Chat(ChatInferenceResultChunk {
            content: content.clone(),
            created: 0,
            usage: None,
            finish_reason: Some(FinishReason::Stop),
            raw_response: "".to_string(),
            latency: Duration::from_millis(100),
        });
        let raw_request = "raw request".to_string();
        let inference_metadata = InferenceMetadata {
            function_name: "test_function".to_string(),
            variant_name: "test_variant".to_string(),
            episode_id: Uuid::now_v7(),
            inference_id: Uuid::now_v7(),
            input: ResolvedInput {
                messages: vec![],
                system: None,
            },
            dryrun: false,
            inference_params: InferenceParams::default(),
            start_time: Instant::now(),
            model_name: "test_model".into(),
            model_provider_name: "test_provider".into(),
            raw_request: raw_request.clone(),
            system: None,
            input_messages: vec![],
            previous_model_inference_results: vec![],
            tags: HashMap::new(),
            tool_config: None,
            dynamic_output_schema: None,
            cached: false,
            extra_body: Default::default(),
            extra_headers: Default::default(),
            observability_metadata: None,
            gateway_request: None,
        };

        let result = prepare_response_chunk(&inference_metadata, chunk).unwrap();
        match result {
            InferenceResponseChunk::Chat(c) => {
                assert_eq!(c.inference_id, inference_metadata.inference_id);
                assert_eq!(c.episode_id, inference_metadata.episode_id);
                assert_eq!(c.variant_name, inference_metadata.variant_name);
                assert_eq!(c.content, content);
                assert!(c.usage.is_none());
                assert_eq!(c.finish_reason, Some(FinishReason::Stop));
            }
            InferenceResponseChunk::Json(_) => {
                panic!("Expected ChatInferenceResponseChunk, got JsonInferenceResponseChunk");
            }
        }

        // Test case 2: Valid JSON ProviderInferenceResponseChunk
        let chunk = InferenceResultChunk::Json(JsonInferenceResultChunk {
            raw: Some("Test content".to_string()),
            thought: Some("Thought 1".to_string()),
            created: 0,
            usage: None,
            raw_response: "".to_string(),
            latency: Duration::from_millis(100),
            finish_reason: Some(FinishReason::Stop),
        });
        let inference_metadata = InferenceMetadata {
            function_name: "test_function".to_string(),
            variant_name: "test_variant".to_string(),
            inference_id: Uuid::now_v7(),
            episode_id: Uuid::now_v7(),
            input: ResolvedInput {
                messages: vec![],
                system: None,
            },
            dryrun: false,
            inference_params: InferenceParams::default(),
            start_time: Instant::now(),
            model_name: "test_model".into(),
            model_provider_name: "test_provider".into(),
            raw_request: raw_request.clone(),
            system: None,
            input_messages: vec![],
            previous_model_inference_results: vec![],
            tags: HashMap::new(),
            tool_config: None,
            dynamic_output_schema: None,
            cached: false,
            extra_body: Default::default(),
            extra_headers: Default::default(),
            observability_metadata: None,
            gateway_request: None,
        };

        let result = prepare_response_chunk(&inference_metadata, chunk).unwrap();
        match result {
            InferenceResponseChunk::Json(c) => {
                assert_eq!(c.inference_id, inference_metadata.inference_id);
                assert_eq!(c.episode_id, inference_metadata.episode_id);
                assert_eq!(c.variant_name, inference_metadata.variant_name);
                assert_eq!(c.raw, "Test content".to_string());
                assert!(c.usage.is_none());
                assert_eq!(c.finish_reason, Some(FinishReason::Stop));
            }
            InferenceResponseChunk::Chat(_) => {
                panic!("Expected JsonInferenceResponseChunk, got ChatInferenceResponseChunk");
            }
        }
    }

    #[test]
    fn test_find_function_no_function_model() {
        let err = find_function(
            &Params {
                function_name: None,
                model_name: None,
                ..Default::default()
            },
            &Config::default(),
            &ModelTable::default(),
        )
        .expect_err("find_function should fail without either arg");
        assert!(
            err.to_string()
                .contains("Either `function_name` or `model_name` must be provided"),
            "Unexpected error: {err}"
        );
    }

    #[test]
    fn test_find_function_both_function_model() {
        let err = find_function(
            &Params {
                function_name: Some("my_function".to_string()),
                model_name: Some("my_model".to_string()),
                ..Default::default()
            },
            &Config::default(),
            &ModelTable::default(),
        )
        .expect_err("find_function should fail with both args provided");
        assert!(
            err.to_string()
                .contains("Only one of `function_name` or `model_name` can be provided"),
            "Unexpected error: {err}"
        );
    }

    #[test]
    fn test_find_function_model_and_variant() {
        let err = find_function(
            &Params {
                function_name: None,
                model_name: Some("my_model".to_string()),
                variant_name: Some("my_variant".to_string()),
                ..Default::default()
            },
            &Config::default(),
            &ModelTable::default(),
        )
        .expect_err("find_function should fail without model_name");
        assert!(
            err.to_string()
                .contains("`variant_name` cannot be provided when using `model_name`"),
            "Unexpected error: {err}"
        );
    }

    #[test]
    fn test_find_function_shorthand_model() {
        let (function_config, function_name) = find_function(
            &Params {
                function_name: None,
                model_name: Some("openai::gpt-9000".to_string()),
                ..Default::default()
            },
            &Config::default(),
            &ModelTable::default(),
        )
        .expect("Failed to find shorthand function");
        assert_eq!(function_name, "tensorzero::default");
        assert_eq!(function_config.variants().len(), 1);
        assert_eq!(
            function_config.variants().keys().next().unwrap(),
            "openai::gpt-9000"
        );
    }

    #[test]
    fn test_find_function_shorthand_missing_provider() {
        let err = find_function(
            &Params {
                model_name: Some("fake_provider::gpt-9000".to_string()),
                ..Default::default()
            },
            &Config::default(),
            &ModelTable::default(),
        )
        .expect_err("find_function should fail with invalid provider");
        assert!(
            err.to_string()
                .contains("Model name 'fake_provider::gpt-9000' not found in model table"),
            "Unexpected error: {err}"
        );
    }

    #[test]
    fn test_deserialize_file_content() {
        let input_with_url = json!({
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "file",
                            "url": "https://example.com/file.txt",
                        }
                    ]
                }
            ]
        });

        let input_with_url: Input = serde_json::from_value(input_with_url).unwrap();
        assert_eq!(input_with_url.messages.len(), 1);
        assert_eq!(input_with_url.messages[0].role, Role::User);
        assert_eq!(input_with_url.messages[0].content.len(), 1);
        assert_eq!(
            input_with_url.messages[0].content[0],
            InputMessageContent::File(File::Url {
                url: "https://example.com/file.txt".parse().unwrap(),
            })
        );

        let input_with_base64 = json!({
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "file",
                            "data": "fake_base64_data",
                            "mime_type": "image/png"
                        }
                    ]
                }
            ]
        });

        let input_with_base64: Input = serde_json::from_value(input_with_base64).unwrap();
        assert_eq!(input_with_base64.messages.len(), 1);
        assert_eq!(input_with_base64.messages[0].role, Role::User);
        assert_eq!(input_with_base64.messages[0].content.len(), 1);
        assert_eq!(
            input_with_base64.messages[0].content[0],
            InputMessageContent::File(File::Base64 {
                mime_type: FileKind::Png,
                data: "fake_base64_data".to_string(),
            })
        );
    }
}
