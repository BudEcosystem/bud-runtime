use std::collections::HashMap;

use axum::http::StatusCode;
use axum::response::{IntoResponse, Json, Response};
use serde_json::{json, Value};
use std::fmt::{Debug, Display};
use tokio::sync::OnceCell;
use url::Url;
use uuid::Uuid;

use crate::inference::types::storage::StoragePath;

/// Controls whether to include raw request/response details in error output
///
/// When true:
/// - Raw request/response details are logged for inference provider errors
/// - Raw details are included in error response bodies
/// - Most commonly affects errors from provider API requests/responses
///
/// WARNING: Setting this to true will expose potentially sensitive request/response
/// data in logs and error responses. Use with caution.
static DEBUG: OnceCell<bool> = if cfg!(feature = "e2e_tests") {
    OnceCell::const_new_with(true)
} else {
    OnceCell::const_new()
};

pub fn set_debug(debug: bool) -> Result<(), Error> {
    // We already initialized `DEBUG`, so do nothing
    if cfg!(feature = "e2e_tests") {
        return Ok(());
    }
    DEBUG.set(debug).map_err(|_| {
        Error::new(ErrorDetails::Config {
            message: "Failed to set debug mode".to_string(),
        })
    })
}

pub const IMPOSSIBLE_ERROR_MESSAGE: &str = "This should never happen, please file a bug report at https://github.com/tensorzero/tensorzero/discussions/new?category=bug-reports";

/// Chooses between a `Debug` or `Display` representation based on the gateway-level `DEBUG` flag.
pub struct DisplayOrDebugGateway<T: Debug + Display> {
    val: T,
}

impl<T: Debug + Display> DisplayOrDebugGateway<T> {
    pub fn new(val: T) -> Self {
        Self { val }
    }
}

impl<T: Debug + Display> Display for DisplayOrDebugGateway<T> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        if *DEBUG.get().unwrap_or(&false) {
            write!(f, "{:?}", self.val)
        } else {
            write!(f, "{}", self.val)
        }
    }
}

#[derive(Debug, PartialEq)]
// As long as the struct member is private, we force people to use the `new` method and log the error.
// We box `ErrorDetails` per the `clippy::result_large_err` lint
pub struct Error(Box<ErrorDetails>);

impl Error {
    pub fn new(details: ErrorDetails) -> Self {
        details.log();
        Error(Box::new(details))
    }

    pub fn new_without_logging(details: ErrorDetails) -> Self {
        Error(Box::new(details))
    }

    pub fn status_code(&self) -> StatusCode {
        self.0.status_code()
    }

    pub fn get_details(&self) -> &ErrorDetails {
        &self.0
    }

    pub fn get_owned_details(self) -> ErrorDetails {
        *self.0
    }

    pub fn log(&self) {
        self.0.log();
    }
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        std::fmt::Display::fmt(&self.0, f)
    }
}

impl From<ErrorDetails> for Error {
    fn from(details: ErrorDetails) -> Self {
        Error::new(details)
    }
}

#[derive(Debug, PartialEq)]
pub enum ErrorDetails {
    AllVariantsFailed {
        errors: HashMap<String, Error>,
    },
    InvalidInferenceTarget {
        message: String,
    },
    ApiKeyMissing {
        provider_name: String,
    },
    AppState {
        message: String,
    },
    BadCredentialsPreInference {
        provider_name: String,
    },
    BatchInputValidation {
        index: usize,
        message: String,
    },
    BatchNotFound {
        id: Uuid,
    },
    BadImageFetch {
        url: Url,
        message: String,
    },
    Cache {
        message: String,
    },
    ChannelWrite {
        message: String,
    },
    ClickHouseConnection {
        message: String,
    },
    ClickHouseDeserialization {
        message: String,
    },
    ClickHouseMigration {
        id: String,
        message: String,
    },
    ClickHouseQuery {
        message: String,
    },
    Config {
        message: String,
    },
    ObjectStoreUnconfigured {
        block_type: String,
    },
    DatapointNotFound {
        dataset_name: String,
        datapoint_id: Uuid,
    },
    DynamicJsonSchema {
        message: String,
    },
    FileRead {
        message: String,
        file_path: String,
    },
    GCPCredentials {
        message: String,
    },
    Inference {
        message: String,
    },
    InferenceClient {
        message: String,
        status_code: Option<StatusCode>,
        provider_type: String,
        raw_request: Option<String>,
        raw_response: Option<String>,
    },
    InferenceNotFound {
        inference_id: Uuid,
    },
    InferenceServer {
        message: String,
        provider_type: String,
        raw_request: Option<String>,
        raw_response: Option<String>,
    },
    InvalidClientMode {
        mode: String,
        message: String,
    },
    ObjectStoreWrite {
        message: String,
        path: StoragePath,
    },
    InternalError {
        message: String,
    },
    InferenceTimeout {
        variant_name: String,
    },
    InputValidation {
        source: Box<Error>,
    },
    InvalidBatchParams {
        message: String,
    },
    InvalidBaseUrl {
        message: String,
    },
    InvalidCandidate {
        variant_name: String,
        message: String,
    },
    InvalidDatasetName {
        dataset_name: String,
    },
    InvalidDiclConfig {
        message: String,
    },
    InvalidDynamicEvaluationRun {
        episode_id: Uuid,
    },
    InvalidTensorzeroUuid {
        kind: String,
        message: String,
    },
    InvalidFunctionVariants {
        message: String,
    },
    InvalidMessage {
        message: String,
    },
    InvalidModel {
        model_name: String,
    },
    InvalidModelProvider {
        model_name: String,
        provider_name: String,
    },
    InvalidOpenAICompatibleRequest {
        message: String,
    },
    InvalidProviderConfig {
        message: String,
    },
    InvalidRequest {
        message: String,
    },
    GuardrailInputViolation {
        message: String,
    },
    GuardrailOutputViolation {
        message: String,
    },
    InvalidTemplatePath,
    InvalidTool {
        message: String,
    },
    InvalidVariantForOptimization {
        function_name: String,
        variant_name: String,
    },
    InvalidUuid {
        raw_uuid: String,
    },
    JsonRequest {
        message: String,
    },
    JsonSchema {
        message: String,
    },
    JsonSchemaValidation {
        messages: Vec<String>,
        data: Box<Value>,
        schema: Box<Value>,
    },
    MissingFunctionInVariants {
        function_name: String,
    },
    MiniJinjaEnvironment {
        message: String,
    },
    MiniJinjaTemplate {
        template_name: String,
        message: String,
    },
    MiniJinjaTemplateMissing {
        template_name: String,
    },
    MiniJinjaTemplateRender {
        template_name: String,
        message: String,
    },
    MissingBatchInferenceResponse {
        inference_id: Option<Uuid>,
    },
    MissingFileExtension {
        file_name: String,
    },
    ModelProvidersExhausted {
        provider_errors: HashMap<String, Error>,
    },
    /// All models in the fallback chain failed
    ModelChainExhausted {
        model_errors: HashMap<String, Error>,
    },
    /// Circular dependency detected in model fallback chain
    CircularFallbackDetected {
        chain: Vec<String>,
    },
    /// Referenced fallback model does not exist
    FallbackModelNotFound {
        model_name: String,
        fallback_model: String,
    },
    ModelValidation {
        message: String,
    },
    Observability {
        message: String,
    },
    OutputParsing {
        message: String,
        raw_output: String,
    },
    OutputValidation {
        source: Box<Error>,
    },
    ModelNotFound {
        name: String,
    },
    ProviderNotFound {
        provider_name: String,
    },
    Serialization {
        message: String,
    },
    ExtraBodyReplacement {
        message: String,
        pointer: String,
    },
    StreamError {
        source: Box<Error>,
    },
    ToolNotFound {
        name: String,
    },
    ToolNotLoaded {
        name: String,
    },
    TypeConversion {
        message: String,
    },
    UnknownCandidate {
        name: String,
    },
    UnknownFunction {
        name: String,
    },
    UnknownModel {
        name: String,
    },
    UnknownTool {
        name: String,
    },
    UnknownVariant {
        name: String,
    },
    UnknownMetric {
        name: String,
    },
    UnsupportedModelProviderForBatchInference {
        provider_type: String,
    },
    UnsupportedVariantForBatchInference {
        variant_name: Option<String>,
    },
    UnsupportedVariantForStreamingInference {
        variant_type: String,
        issue_link: Option<String>,
    },
    UnsupportedVariantForFunctionType {
        function_name: String,
        variant_name: String,
        function_type: String,
        variant_type: String,
    },
    UnsupportedContentBlockType {
        content_block_type: String,
        provider_type: String,
    },
    UuidInFuture {
        raw_uuid: String,
    },
    UnsupportedFileExtension {
        extension: String,
    },
    RouteNotFound {
        path: String,
        method: String,
    },
    KafkaConnection {
        message: String,
    },
    KafkaProducer {
        message: String,
    },
    KafkaSerialization {
        message: String,
    },
    CapabilityNotSupported {
        capability: String,
        provider: String,
    },
    ModelNotConfiguredForCapability {
        model_name: String,
        capability: String,
    },
}

impl ErrorDetails {
    /// Defines the error level for logging this error
    fn level(&self) -> tracing::Level {
        match self {
            ErrorDetails::AllVariantsFailed { .. } => tracing::Level::ERROR,
            ErrorDetails::ApiKeyMissing { .. } => tracing::Level::ERROR,
            ErrorDetails::AppState { .. } => tracing::Level::ERROR,
            ErrorDetails::ObjectStoreUnconfigured { .. } => tracing::Level::ERROR,
            ErrorDetails::ExtraBodyReplacement { .. } => tracing::Level::ERROR,
            ErrorDetails::InvalidInferenceTarget { .. } => tracing::Level::WARN,
            ErrorDetails::BadCredentialsPreInference { .. } => tracing::Level::ERROR,
            ErrorDetails::UnsupportedContentBlockType { .. } => tracing::Level::WARN,
            ErrorDetails::BatchInputValidation { .. } => tracing::Level::WARN,
            ErrorDetails::BatchNotFound { .. } => tracing::Level::WARN,
            ErrorDetails::Cache { .. } => tracing::Level::WARN,
            ErrorDetails::ChannelWrite { .. } => tracing::Level::ERROR,
            ErrorDetails::ClickHouseConnection { .. } => tracing::Level::ERROR,
            ErrorDetails::BadImageFetch { .. } => tracing::Level::ERROR,
            ErrorDetails::ClickHouseDeserialization { .. } => tracing::Level::ERROR,
            ErrorDetails::ClickHouseMigration { .. } => tracing::Level::ERROR,
            ErrorDetails::ClickHouseQuery { .. } => tracing::Level::ERROR,
            ErrorDetails::ObjectStoreWrite { .. } => tracing::Level::ERROR,
            ErrorDetails::Config { .. } => tracing::Level::ERROR,
            ErrorDetails::DatapointNotFound { .. } => tracing::Level::WARN,
            ErrorDetails::DynamicJsonSchema { .. } => tracing::Level::WARN,
            ErrorDetails::FileRead { .. } => tracing::Level::ERROR,
            ErrorDetails::GCPCredentials { .. } => tracing::Level::ERROR,
            ErrorDetails::Inference { .. } => tracing::Level::ERROR,
            ErrorDetails::InferenceClient { .. } => tracing::Level::ERROR,
            ErrorDetails::InferenceNotFound { .. } => tracing::Level::WARN,
            ErrorDetails::InferenceServer { .. } => tracing::Level::ERROR,
            ErrorDetails::InferenceTimeout { .. } => tracing::Level::WARN,
            ErrorDetails::InputValidation { .. } => tracing::Level::WARN,
            ErrorDetails::InternalError { .. } => tracing::Level::ERROR,
            ErrorDetails::InvalidBaseUrl { .. } => tracing::Level::ERROR,
            ErrorDetails::InvalidBatchParams { .. } => tracing::Level::ERROR,
            ErrorDetails::InvalidCandidate { .. } => tracing::Level::ERROR,
            ErrorDetails::InvalidClientMode { .. } => tracing::Level::ERROR,
            ErrorDetails::InvalidDiclConfig { .. } => tracing::Level::ERROR,
            ErrorDetails::InvalidDatasetName { .. } => tracing::Level::WARN,
            ErrorDetails::InvalidDynamicEvaluationRun { .. } => tracing::Level::ERROR,
            ErrorDetails::InvalidTensorzeroUuid { .. } => tracing::Level::WARN,
            ErrorDetails::InvalidFunctionVariants { .. } => tracing::Level::ERROR,
            ErrorDetails::InvalidVariantForOptimization { .. } => tracing::Level::WARN,
            ErrorDetails::InvalidMessage { .. } => tracing::Level::WARN,
            ErrorDetails::InvalidModel { .. } => tracing::Level::ERROR,
            ErrorDetails::InvalidModelProvider { .. } => tracing::Level::ERROR,
            ErrorDetails::InvalidOpenAICompatibleRequest { .. } => tracing::Level::ERROR,
            ErrorDetails::InvalidProviderConfig { .. } => tracing::Level::ERROR,
            ErrorDetails::InvalidRequest { .. } => tracing::Level::WARN,
            ErrorDetails::GuardrailInputViolation { .. } => tracing::Level::WARN,
            ErrorDetails::GuardrailOutputViolation { .. } => tracing::Level::ERROR,
            ErrorDetails::InvalidTemplatePath => tracing::Level::ERROR,
            ErrorDetails::InvalidTool { .. } => tracing::Level::ERROR,
            ErrorDetails::InvalidUuid { .. } => tracing::Level::ERROR,
            ErrorDetails::JsonRequest { .. } => tracing::Level::WARN,
            ErrorDetails::JsonSchema { .. } => tracing::Level::ERROR,
            ErrorDetails::JsonSchemaValidation { .. } => tracing::Level::ERROR,
            ErrorDetails::MiniJinjaEnvironment { .. } => tracing::Level::ERROR,
            ErrorDetails::MiniJinjaTemplate { .. } => tracing::Level::ERROR,
            ErrorDetails::MiniJinjaTemplateMissing { .. } => tracing::Level::ERROR,
            ErrorDetails::MiniJinjaTemplateRender { .. } => tracing::Level::ERROR,
            ErrorDetails::MissingFunctionInVariants { .. } => tracing::Level::ERROR,
            ErrorDetails::MissingBatchInferenceResponse { .. } => tracing::Level::WARN,
            ErrorDetails::MissingFileExtension { .. } => tracing::Level::WARN,
            ErrorDetails::ModelProvidersExhausted { .. } => tracing::Level::ERROR,
            ErrorDetails::ModelChainExhausted { .. } => tracing::Level::ERROR,
            ErrorDetails::CircularFallbackDetected { .. } => tracing::Level::ERROR,
            ErrorDetails::FallbackModelNotFound { .. } => tracing::Level::ERROR,
            ErrorDetails::ModelValidation { .. } => tracing::Level::ERROR,
            ErrorDetails::Observability { .. } => tracing::Level::ERROR,
            ErrorDetails::OutputParsing { .. } => tracing::Level::WARN,
            ErrorDetails::OutputValidation { .. } => tracing::Level::WARN,
            ErrorDetails::ModelNotFound { .. } => tracing::Level::WARN,
            ErrorDetails::ProviderNotFound { .. } => tracing::Level::ERROR,
            ErrorDetails::Serialization { .. } => tracing::Level::ERROR,
            ErrorDetails::StreamError { .. } => tracing::Level::ERROR,
            ErrorDetails::ToolNotFound { .. } => tracing::Level::WARN,
            ErrorDetails::ToolNotLoaded { .. } => tracing::Level::ERROR,
            ErrorDetails::TypeConversion { .. } => tracing::Level::ERROR,
            ErrorDetails::UnknownCandidate { .. } => tracing::Level::ERROR,
            ErrorDetails::UnknownFunction { .. } => tracing::Level::WARN,
            ErrorDetails::UnknownModel { .. } => tracing::Level::ERROR,
            ErrorDetails::UnknownTool { .. } => tracing::Level::ERROR,
            ErrorDetails::UnknownVariant { .. } => tracing::Level::WARN,
            ErrorDetails::UnknownMetric { .. } => tracing::Level::WARN,
            ErrorDetails::UnsupportedFileExtension { .. } => tracing::Level::WARN,
            ErrorDetails::UnsupportedModelProviderForBatchInference { .. } => tracing::Level::WARN,
            ErrorDetails::UnsupportedVariantForBatchInference { .. } => tracing::Level::WARN,
            ErrorDetails::UnsupportedVariantForFunctionType { .. } => tracing::Level::ERROR,
            ErrorDetails::UnsupportedVariantForStreamingInference { .. } => tracing::Level::WARN,
            ErrorDetails::UuidInFuture { .. } => tracing::Level::WARN,
            ErrorDetails::RouteNotFound { .. } => tracing::Level::WARN,
            ErrorDetails::KafkaConnection { .. } => tracing::Level::ERROR,
            ErrorDetails::KafkaProducer { .. } => tracing::Level::ERROR,
            ErrorDetails::KafkaSerialization { .. } => tracing::Level::ERROR,
            ErrorDetails::CapabilityNotSupported { .. } => tracing::Level::WARN,
            ErrorDetails::ModelNotConfiguredForCapability { .. } => tracing::Level::WARN,
        }
    }

    /// Defines the HTTP status code for responses involving this error
    fn status_code(&self) -> StatusCode {
        match self {
            ErrorDetails::AllVariantsFailed { .. } => StatusCode::BAD_GATEWAY,
            ErrorDetails::ApiKeyMissing { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::ExtraBodyReplacement { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::AppState { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::BadCredentialsPreInference { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::BatchInputValidation { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::BatchNotFound { .. } => StatusCode::NOT_FOUND,
            ErrorDetails::Cache { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::ChannelWrite { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::ClickHouseConnection { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::ClickHouseDeserialization { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::ClickHouseMigration { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::ClickHouseQuery { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::ObjectStoreUnconfigured { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::DatapointNotFound { .. } => StatusCode::NOT_FOUND,
            ErrorDetails::Config { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::DynamicJsonSchema { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::FileRead { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::GCPCredentials { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::InvalidInferenceTarget { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::Inference { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::ObjectStoreWrite { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::InferenceClient { status_code, .. } => {
                status_code.unwrap_or_else(|| StatusCode::INTERNAL_SERVER_ERROR)
            }
            ErrorDetails::BadImageFetch { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::InferenceNotFound { .. } => StatusCode::NOT_FOUND,
            ErrorDetails::InferenceServer { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::InferenceTimeout { .. } => StatusCode::REQUEST_TIMEOUT,
            ErrorDetails::InvalidClientMode { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::InvalidTensorzeroUuid { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::InvalidUuid { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::InputValidation { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::InternalError { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::InvalidBaseUrl { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::UnsupportedContentBlockType { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::InvalidBatchParams { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::InvalidCandidate { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::InvalidDiclConfig { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::InvalidDatasetName { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::InvalidDynamicEvaluationRun { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::InvalidFunctionVariants { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::InvalidMessage { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::InvalidModel { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::InvalidModelProvider { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::InvalidOpenAICompatibleRequest { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::InvalidProviderConfig { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::InvalidRequest { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::GuardrailInputViolation { .. } => StatusCode::FORBIDDEN,
            ErrorDetails::GuardrailOutputViolation { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::InvalidTemplatePath => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::InvalidTool { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::InvalidVariantForOptimization { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::JsonRequest { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::JsonSchema { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::JsonSchemaValidation { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::MiniJinjaEnvironment { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::MiniJinjaTemplate { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::MiniJinjaTemplateMissing { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::MiniJinjaTemplateRender { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::MissingBatchInferenceResponse { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::MissingFunctionInVariants { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::MissingFileExtension { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::ModelProvidersExhausted { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::ModelChainExhausted { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::CircularFallbackDetected { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::FallbackModelNotFound { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::ModelValidation { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::Observability { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::OutputParsing { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::OutputValidation { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::ModelNotFound { .. } => StatusCode::NOT_FOUND,
            ErrorDetails::ProviderNotFound { .. } => StatusCode::NOT_FOUND,
            ErrorDetails::Serialization { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::StreamError { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::ToolNotFound { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::ToolNotLoaded { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::TypeConversion { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::UnknownCandidate { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::UnknownFunction { .. } => StatusCode::NOT_FOUND,
            ErrorDetails::UnknownModel { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::UnknownTool { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::UnknownVariant { .. } => StatusCode::NOT_FOUND,
            ErrorDetails::UnknownMetric { .. } => StatusCode::NOT_FOUND,
            ErrorDetails::UnsupportedFileExtension { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::UnsupportedModelProviderForBatchInference { .. } => {
                StatusCode::INTERNAL_SERVER_ERROR
            }
            ErrorDetails::UnsupportedVariantForBatchInference { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::UnsupportedVariantForStreamingInference { .. } => {
                StatusCode::INTERNAL_SERVER_ERROR
            }
            ErrorDetails::UnsupportedVariantForFunctionType { .. } => {
                StatusCode::INTERNAL_SERVER_ERROR
            }
            ErrorDetails::UuidInFuture { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::RouteNotFound { .. } => StatusCode::NOT_FOUND,
            ErrorDetails::KafkaConnection { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::KafkaProducer { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::KafkaSerialization { .. } => StatusCode::INTERNAL_SERVER_ERROR,
            ErrorDetails::CapabilityNotSupported { .. } => StatusCode::BAD_REQUEST,
            ErrorDetails::ModelNotConfiguredForCapability { .. } => StatusCode::BAD_REQUEST,
        }
    }

    /// Log the error using the `tracing` library
    pub fn log(&self) {
        match self.level() {
            tracing::Level::ERROR => tracing::error!("{self}"),
            tracing::Level::WARN => tracing::warn!("{self}"),
            tracing::Level::INFO => tracing::info!("{self}"),
            tracing::Level::DEBUG => tracing::debug!("{self}"),
            tracing::Level::TRACE => tracing::trace!("{self}"),
        }
    }
}

impl std::fmt::Display for ErrorDetails {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ErrorDetails::AllVariantsFailed { errors } => {
                // Don't recursively stringify nested errors - that causes double-wrapping
                // Instead, provide a simple summary for Display trait
                // The full structured error is available via to_response_json()
                write!(f, "All variants failed with {} error(s)", errors.len())
            }
            ErrorDetails::ObjectStoreWrite { message, path } => {
                write!(
                    f,
                    "Error writing to object store: `{message}`. Path: {path:?}"
                )
            }
            ErrorDetails::InvalidInferenceTarget { message } => {
                write!(f, "Invalid inference target: {message}")
            }
            ErrorDetails::BadImageFetch { url, message } => {
                write!(f, "Error fetching image from {url}: {message}")
            }
            ErrorDetails::ObjectStoreUnconfigured { block_type } => {
                write!(f, "Object storage is not configured. You must configure `[object_storage]` before making requests containing a `{block_type}` content block")
            }
            ErrorDetails::UnsupportedContentBlockType {
                content_block_type,
                provider_type,
            } => {
                write!(
                    f,
                    "Unsupported content block type `{content_block_type}` for provider `{provider_type}`",
                )
            }
            ErrorDetails::ExtraBodyReplacement { message, pointer } => {
                write!(
                    f,
                    "Error replacing extra body: `{message}` with pointer: `{pointer}`"
                )
            }
            ErrorDetails::ApiKeyMissing { provider_name } => {
                write!(f, "API key missing for provider: {provider_name}")
            }
            ErrorDetails::AppState { message } => {
                write!(f, "Error initializing AppState: {message}")
            }
            ErrorDetails::BadCredentialsPreInference { provider_name } => {
                write!(
                    f,
                    "Bad credentials at inference time for provider: {provider_name}. This should never happen. Please file a bug report: https://github.com/tensorzero/tensorzero/issues/new"
                )
            }
            ErrorDetails::BatchInputValidation { index, message } => {
                write!(f, "Input at index {index} failed validation: {message}",)
            }
            ErrorDetails::BatchNotFound { id } => {
                write!(f, "Batch request not found for id: {id}")
            }
            ErrorDetails::Cache { message } => {
                write!(f, "Error in cache: {message}")
            }
            ErrorDetails::ChannelWrite { message } => {
                write!(f, "Error writing to channel: {message}")
            }
            ErrorDetails::ClickHouseConnection { message } => {
                write!(f, "Error connecting to ClickHouse: {message}")
            }
            ErrorDetails::ClickHouseDeserialization { message } => {
                write!(f, "Error deserializing ClickHouse response: {message}")
            }
            ErrorDetails::ClickHouseMigration { id, message } => {
                write!(f, "Error running ClickHouse migration {id}: {message}")
            }
            ErrorDetails::ClickHouseQuery { message } => {
                write!(f, "Failed to run ClickHouse query: {message}")
            }
            ErrorDetails::Config { message } => {
                write!(f, "{message}")
            }
            ErrorDetails::DatapointNotFound {
                dataset_name,
                datapoint_id,
            } => {
                write!(
                    f,
                    "Datapoint not found for dataset: {dataset_name} and id: {datapoint_id}"
                )
            }
            ErrorDetails::DynamicJsonSchema { message } => {
                write!(
                    f,
                    "Error in compiling client-provided JSON schema: {message}"
                )
            }
            ErrorDetails::FileRead { message, file_path } => {
                write!(f, "Error reading file {file_path}: {message}")
            }
            ErrorDetails::GCPCredentials { message } => {
                write!(f, "Error in acquiring GCP credentials: {message}")
            }
            ErrorDetails::Inference { message } => write!(f, "{message}"),
            ErrorDetails::InferenceClient {
                message,
                provider_type,
                raw_request,
                raw_response,
                status_code,
            } => {
                // `debug` defaults to false so we don't log raw request and response by default
                if *DEBUG.get().unwrap_or(&false) {
                    write!(
                        f,
                        "Error from {} client: {}{}{}",
                        provider_type,
                        message,
                        raw_request
                            .as_ref()
                            .map_or("".to_string(), |r| format!("\nRaw request: {r}")),
                        raw_response
                            .as_ref()
                            .map_or("".to_string(), |r| format!("\nRaw response: {r}"))
                    )
                } else {
                    write!(
                        f,
                        "Error{} from {} client: {}",
                        status_code.map_or("".to_string(), |s| format!(" {s}")),
                        provider_type,
                        message
                    )
                }
            }
            ErrorDetails::InferenceNotFound { inference_id } => {
                write!(f, "Inference not found for id: {inference_id}")
            }
            ErrorDetails::InferenceServer {
                message,
                provider_type,
                raw_request,
                raw_response,
            } => {
                // `debug` defaults to false so we don't log raw request and response by default
                if *DEBUG.get().unwrap_or(&false) {
                    write!(
                        f,
                        "Error from {} server: {}{}{}",
                        provider_type,
                        message,
                        raw_request
                            .as_ref()
                            .map_or("".to_string(), |r| format!("\nRaw request: {r}")),
                        raw_response
                            .as_ref()
                            .map_or("".to_string(), |r| format!("\nRaw response: {r}"))
                    )
                } else {
                    write!(f, "Error from {provider_type} server: {message}")
                }
            }
            ErrorDetails::InferenceTimeout { variant_name } => {
                write!(f, "Inference timed out for variant: {variant_name}")
            }
            ErrorDetails::InputValidation { source } => {
                write!(f, "Input validation failed with messages: {source}")
            }
            ErrorDetails::InternalError { message } => {
                write!(f, "Internal error: {message}")
            }
            ErrorDetails::InvalidBaseUrl { message } => {
                write!(f, "Invalid batch params retrieved from database: {message}")
            }
            ErrorDetails::InvalidBatchParams { message } => write!(f, "{message}"),
            ErrorDetails::InvalidCandidate {
                variant_name,
                message,
            } => {
                write!(
                    f,
                    "Invalid candidate variant as a component of variant {variant_name}: {message}"
                )
            }
            ErrorDetails::InvalidClientMode { mode, message } => {
                write!(f, "Invalid client mode: {mode}. {message}")
            }
            ErrorDetails::InvalidDiclConfig { message } => {
                write!(f, "Invalid dynamic in-context learning config: {message}. This should never happen. Please file a bug report: https://github.com/tensorzero/tensorzero/issues/new")
            }
            ErrorDetails::InvalidDatasetName { dataset_name } => {
                write!(f, "Invalid dataset name: {dataset_name}. Datasets cannot be named \"builder\" or begin with \"tensorzero::\"")
            }
            ErrorDetails::InvalidDynamicEvaluationRun { episode_id } => {
                write!(
                    f,
                    "Dynamic evaluation run not found for episode id: {episode_id}",
                )
            }
            ErrorDetails::InvalidFunctionVariants { message } => write!(f, "{message}"),
            ErrorDetails::InvalidTensorzeroUuid { message, kind } => {
                write!(f, "Invalid {kind} ID: {message}")
            }
            ErrorDetails::InvalidMessage { message } => write!(f, "{message}"),
            ErrorDetails::InvalidModel { model_name } => {
                write!(f, "Invalid model: {model_name}")
            }
            ErrorDetails::InvalidModelProvider {
                model_name,
                provider_name,
            } => {
                write!(
                    f,
                    "Invalid model provider: {provider_name} for model: {model_name}"
                )
            }
            ErrorDetails::InvalidOpenAICompatibleRequest { message } => write!(
                f,
                "Invalid request to OpenAI-compatible endpoint: {message}"
            ),
            ErrorDetails::InvalidProviderConfig { message } => write!(f, "{message}"),
            ErrorDetails::InvalidRequest { message } => write!(f, "{message}"),
            ErrorDetails::GuardrailInputViolation { message } => write!(f, "{message}"),
            ErrorDetails::GuardrailOutputViolation { message } => write!(f, "{message}"),
            ErrorDetails::InvalidTemplatePath => {
                write!(f, "Template path failed to convert to Rust string")
            }
            ErrorDetails::InvalidTool { message } => write!(f, "{message}"),
            ErrorDetails::InvalidUuid { raw_uuid } => {
                write!(f, "Failed to parse UUID as v7: {raw_uuid}")
            }
            ErrorDetails::InvalidVariantForOptimization {
                function_name,
                variant_name,
            } => {
                write!(f, "Invalid variant for optimization: {variant_name} for function: {function_name}")
            }
            ErrorDetails::JsonRequest { message } => write!(f, "{message}"),
            ErrorDetails::JsonSchema { message } => write!(f, "{message}"),
            ErrorDetails::JsonSchemaValidation {
                messages,
                data,
                schema,
            } => {
                write!(f, "JSON Schema validation failed:\n{}", messages.join("\n"))?;
                // `debug` defaults to false so we don't log data by default
                if *DEBUG.get().unwrap_or(&false) {
                    write!(
                        f,
                        "\n\nData:\n{}",
                        serde_json::to_string(data).map_err(|_| std::fmt::Error)?
                    )?;
                }
                write!(
                    f,
                    "\n\nSchema:\n{}",
                    serde_json::to_string(schema).map_err(|_| std::fmt::Error)?
                )
            }
            ErrorDetails::MiniJinjaEnvironment { message } => {
                write!(f, "Error initializing MiniJinja environment: {message}")
            }
            ErrorDetails::MiniJinjaTemplate {
                template_name,
                message,
            } => {
                write!(f, "Error rendering template {template_name}: {message}")
            }
            ErrorDetails::MiniJinjaTemplateMissing { template_name } => {
                write!(f, "Template not found: {template_name}")
            }
            ErrorDetails::MiniJinjaTemplateRender {
                template_name,
                message,
            } => {
                write!(f, "Error rendering template {template_name}: {message}")
            }
            ErrorDetails::MissingBatchInferenceResponse { inference_id } => match inference_id {
                Some(inference_id) => write!(
                    f,
                    "Missing batch inference response for inference id: {inference_id}"
                ),
                None => write!(f, "Missing batch inference response"),
            },
            ErrorDetails::MissingFunctionInVariants { function_name } => {
                write!(f, "Missing function in variants: {function_name}")
            }
            ErrorDetails::MissingFileExtension { file_name } => {
                write!(
                    f,
                    "Could not determine file extension for file: {file_name}"
                )
            }
            ErrorDetails::ModelProvidersExhausted { provider_errors } => {
                // Just show the first provider error for brevity
                if let Some((_, first_error)) = provider_errors.iter().next() {
                    write!(f, "{}", first_error)
                } else {
                    write!(f, "Model request failed")
                }
            }
            ErrorDetails::ModelChainExhausted { model_errors } => {
                // Just show the first model error for brevity
                if let Some((_, first_error)) = model_errors.iter().next() {
                    write!(f, "{}", first_error)
                } else {
                    write!(f, "Model request failed")
                }
            }
            ErrorDetails::CircularFallbackDetected { chain } => {
                write!(
                    f,
                    "Circular dependency detected in model fallback chain: {}",
                    chain.join(" -> ")
                )
            }
            ErrorDetails::FallbackModelNotFound {
                model_name,
                fallback_model,
            } => {
                write!(
                    f,
                    "Fallback model '{fallback_model}' referenced by model '{model_name}' does not exist"
                )
            }
            ErrorDetails::ModelValidation { message } => {
                write!(f, "Failed to validate model: {message}")
            }
            ErrorDetails::Observability { message } => {
                write!(f, "{message}")
            }
            ErrorDetails::OutputParsing {
                raw_output,
                message,
            } => {
                write!(
                    f,
                    "Error parsing output as JSON with message: {message}: {raw_output}"
                )
            }
            ErrorDetails::OutputValidation { source } => {
                write!(f, "Output validation failed with messages: {source}")
            }
            ErrorDetails::ModelNotFound { name } => {
                write!(f, "Model not found: {name}")
            }
            ErrorDetails::ProviderNotFound { provider_name } => {
                write!(f, "Provider not found: {provider_name}")
            }
            ErrorDetails::StreamError { source } => {
                write!(f, "Error in streaming response: {source}")
            }
            ErrorDetails::Serialization { message } => write!(f, "{message}"),
            ErrorDetails::TypeConversion { message } => write!(f, "{message}"),
            ErrorDetails::ToolNotFound { name } => write!(f, "Tool not found: {name}"),
            ErrorDetails::ToolNotLoaded { name } => write!(f, "Tool not loaded: {name}"),
            ErrorDetails::UnknownCandidate { name } => {
                write!(f, "Unknown candidate variant: {name}")
            }
            ErrorDetails::UnknownFunction { name } => write!(f, "Unknown function: {name}"),
            ErrorDetails::UnknownModel { name } => write!(f, "Unknown model: {name}"),
            ErrorDetails::UnknownTool { name } => write!(f, "Unknown tool: {name}"),
            ErrorDetails::UnknownVariant { name } => write!(f, "Unknown variant: {name}"),
            ErrorDetails::UnknownMetric { name } => write!(f, "Unknown metric: {name}"),
            ErrorDetails::UnsupportedModelProviderForBatchInference { provider_type } => {
                write!(
                    f,
                    "Unsupported model provider for batch inference: {provider_type}"
                )
            }
            ErrorDetails::UnsupportedFileExtension { extension } => {
                write!(f, "Unsupported file extension: {extension}")
            }
            ErrorDetails::UnsupportedVariantForBatchInference { variant_name } => {
                match variant_name {
                    Some(variant_name) => {
                        write!(f, "Unsupported variant for batch inference: {variant_name}")
                    }
                    None => write!(f, "Unsupported variant for batch inference"),
                }
            }
            ErrorDetails::UnsupportedVariantForStreamingInference {
                variant_type,
                issue_link,
            } => {
                if let Some(link) = issue_link {
                    write!(
                        f,
                        "Unsupported variant for streaming inference of type {variant_type}. For more information, see: {link}"
                    )
                } else {
                    write!(
                        f,
                        "Unsupported variant for streaming inference of type {variant_type}"
                    )
                }
            }
            ErrorDetails::UnsupportedVariantForFunctionType {
                function_name,
                variant_name,
                function_type,
                variant_type,
            } => {
                write!(f, "Unsupported variant `{variant_name}` of type `{variant_type}` for function `{function_name}` of type `{function_type}`")
            }
            ErrorDetails::UuidInFuture { raw_uuid } => {
                write!(f, "UUID is in the future: {raw_uuid}")
            }
            ErrorDetails::RouteNotFound { path, method } => {
                write!(f, "Route not found: {method} {path}")
            }
            ErrorDetails::KafkaConnection { message } => {
                write!(f, "Error connecting to Kafka: {message}")
            }
            ErrorDetails::KafkaProducer { message } => {
                write!(f, "Error with Kafka producer: {message}")
            }
            ErrorDetails::KafkaSerialization { message } => {
                write!(f, "Error serializing message for Kafka: {message}")
            }
            ErrorDetails::CapabilityNotSupported {
                capability,
                provider,
            } => {
                write!(
                    f,
                    "Provider `{provider}` does not support capability `{capability}`"
                )
            }
            ErrorDetails::ModelNotConfiguredForCapability {
                model_name,
                capability,
            } => {
                write!(
                    f,
                    "Model `{model_name}` is not configured to support capability `{capability}`. Add `endpoints = [\"{capability}\"]` to the model configuration."
                )
            }
        }
    }
}

impl std::error::Error for Error {}

impl Error {
    /// Convert error to OpenAI-compatible error format
    pub fn to_openai_error(&self) -> serde_json::Value {
        json!({
            "error": {
                "message": self.to_string(),
                "type": match self.get_details() {
                    ErrorDetails::InvalidRequest { .. } => "invalid_request_error",
                    ErrorDetails::ApiKeyMissing { .. } => "authentication_error",
                    ErrorDetails::BadCredentialsPreInference { .. } => "authentication_error",
                    ErrorDetails::CapabilityNotSupported { .. } => "invalid_request_error",
                    ErrorDetails::InferenceServer { .. } => "server_error",
                    _ => "internal_error"
                },
                "code": None::<String>
            }
        })
    }
}

impl Error {
    /// Get the JSON response body that would be sent to clients
    /// Returns (StatusCode, JSON Value) tuple matching what into_response() creates
    pub fn to_response_json(&self) -> (StatusCode, Value) {
        // Helper function to parse provider error messages
        fn parse_provider_error_message(message: &str) -> Value {
            if let Ok(json_msg) = serde_json::from_str::<Value>(message) {
                // If it's a JSON object with an "error" field, extract just the error
                if let Some(error_obj) = json_msg.get("error") {
                    error_obj.clone()
                } else {
                    // If no "error" field, use the whole JSON
                    json_msg
                }
            } else {
                // If not valid JSON, use the raw message
                json!(message)
            }
        }

        // Helper function to extract provider error details from nested errors
        fn extract_provider_error(error: &Error) -> Option<(Value, Option<StatusCode>)> {
            match error.get_details() {
                ErrorDetails::InferenceClient {
                    message,
                    status_code,
                    ..
                } => {
                    let provider_error = parse_provider_error_message(message);
                    Some((provider_error, *status_code))
                }
                ErrorDetails::ModelProvidersExhausted { provider_errors } => {
                    // Recursively check nested errors
                    provider_errors
                        .iter()
                        .next()
                        .and_then(|(_, e)| extract_provider_error(e))
                }
                ErrorDetails::ModelChainExhausted { model_errors } => {
                    // Recursively check nested errors
                    model_errors
                        .iter()
                        .next()
                        .and_then(|(_, e)| extract_provider_error(e))
                }
                _ => None,
            }
        }

        // Helper function to build response with provider error
        fn build_provider_error_response(
            error: &Error,
            provider_error: Value,
            provider_status: Option<StatusCode>,
        ) -> (StatusCode, Value) {
            let status = provider_status.unwrap_or_else(|| error.status_code());

            // Extract clean error message from provider_error
            // If provider_error.message contains nested JSON with error.message, extract it
            let clean_error = if let Some(error_obj) = provider_error.as_object() {
                if let Some(message_value) = error_obj.get("message") {
                    if let Some(message_str) = message_value.as_str() {
                        // Clean the message by trimming whitespace and removing trailing punctuation
                        // This handles cases where providers return invalid JSON like '{"error":{...}}. '
                        let cleaned_message = message_str.trim().trim_end_matches('.');

                        // Try to parse as JSON and extract nested error.message
                        if let Ok(parsed) = serde_json::from_str::<Value>(cleaned_message) {
                            if let Some(nested_error) = parsed.get("error") {
                                if let Some(nested_msg) =
                                    nested_error.get("message").and_then(|m| m.as_str())
                                {
                                    // Found nested message - use it!
                                    json!({"message": nested_msg})
                                } else {
                                    // No nested message, use cleaned string
                                    json!({"message": cleaned_message})
                                }
                            } else {
                                // No "error" key, use cleaned string
                                json!({"message": cleaned_message})
                            }
                        } else {
                            // Not valid JSON, use cleaned string
                            json!({"message": cleaned_message})
                        }
                    } else {
                        json!({"message": error.to_string()})
                    }
                } else {
                    json!({"message": error.to_string()})
                }
            } else {
                json!({"message": error.to_string()})
            };

            let body = json!({
                "error": clean_error,
                "provider_error": provider_error
            });
            (status, body)
        }

        // Helper function to handle errors with nested provider errors
        fn handle_nested_provider_error<'a, I>(
            error: &Error,
            mut errors_iter: I,
        ) -> (StatusCode, Value)
        where
            I: Iterator<Item = (&'a String, &'a Error)>,
        {
            if let Some((_, nested_error)) = errors_iter.next() {
                if let Some((provider_error, provider_status)) =
                    extract_provider_error(nested_error)
                {
                    return build_provider_error_response(error, provider_error, provider_status);
                }
            }
            (error.status_code(), json!({"error": error.to_string()}))
        }

        // Check if this is a provider error that we should pass through
        match self.get_details() {
            // For provider client errors, include the provider error details
            ErrorDetails::InferenceClient {
                message,
                status_code: provider_status_code,
                ..
            } => {
                let provider_error = parse_provider_error_message(message);
                build_provider_error_response(self, provider_error, *provider_status_code)
            }
            // For all variants failed, try to extract the underlying provider error
            ErrorDetails::AllVariantsFailed { errors } => {
                handle_nested_provider_error(self, errors.iter())
            }
            // For model providers exhausted, extract the underlying provider error
            ErrorDetails::ModelProvidersExhausted { provider_errors } => {
                handle_nested_provider_error(self, provider_errors.iter())
            }
            // For model chain exhausted, extract the underlying provider error
            ErrorDetails::ModelChainExhausted { model_errors } => {
                handle_nested_provider_error(self, model_errors.iter())
            }
            // Default case for other errors
            _ => (self.status_code(), json!({"error": self.to_string()})),
        }
    }
}

impl IntoResponse for Error {
    /// Log the error and convert it into an Axum response
    fn into_response(self) -> Response {
        let (status_code, body) = self.to_response_json();
        (status_code, Json(body)).into_response()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_capability_not_supported_error() {
        let error = Error::new(ErrorDetails::CapabilityNotSupported {
            capability: "embedding".to_string(),
            provider: "test_model".to_string(),
        });

        // Test error message
        assert_eq!(
            error.to_string(),
            "Provider `test_model` does not support capability `embedding`"
        );

        // Test status code
        assert_eq!(error.status_code(), StatusCode::BAD_REQUEST);

        // Test log level
        assert_eq!(error.get_details().level(), tracing::Level::WARN);
    }

    #[test]
    fn test_capability_not_supported_error_display() {
        let details = ErrorDetails::CapabilityNotSupported {
            capability: "chat".to_string(),
            provider: "embedding_only_model".to_string(),
        };

        let formatted = format!("{details}");
        assert_eq!(
            formatted,
            "Provider `embedding_only_model` does not support capability `chat`"
        );
    }

    #[test]
    fn test_model_not_configured_for_capability_error() {
        let error = Error::new(ErrorDetails::ModelNotConfiguredForCapability {
            model_name: "mistral-embed".to_string(),
            capability: "embedding".to_string(),
        });

        // Test error message
        assert_eq!(
            error.to_string(),
            "Model `mistral-embed` is not configured to support capability `embedding`. Add `endpoints = [\"embedding\"]` to the model configuration."
        );

        // Test status code
        assert_eq!(error.status_code(), StatusCode::BAD_REQUEST);

        // Test log level
        assert_eq!(error.get_details().level(), tracing::Level::WARN);
    }

    #[test]
    fn test_error_into_response() {
        let error = Error::new(ErrorDetails::CapabilityNotSupported {
            capability: "embedding".to_string(),
            provider: "test".to_string(),
        });

        let response = error.into_response();
        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    }
}
