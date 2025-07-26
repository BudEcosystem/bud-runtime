// Temporary stubs for removed client types to allow E2E tests to compile
// TODO: These E2E tests need to be rewritten to work without the client SDK

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use tensorzero_internal::inference::types::Role;

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ClientInferenceParams {
    pub function_name: Option<String>,
    pub variant_name: Option<String>,
    pub model_name: Option<String>,
    pub input: ClientInput,
    pub cache_options: Option<CacheParamsOptions>,
    pub tags: Option<HashMap<String, Value>>,
    pub dynamic_tool_params: Option<Value>,
    pub output_schema: Option<Value>,
    pub episode_id: Option<uuid::Uuid>,
    pub dryrun: Option<bool>,
    pub stream: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ClientInput {
    pub system: Option<serde_json::Value>,
    pub messages: Vec<ClientInputMessage>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClientInputMessage {
    pub role: Role,
    pub content: Vec<ClientInputMessageContent>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum ClientInputMessageContent {
    Text(tensorzero_internal::inference::types::TextKind),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheParamsOptions {
    pub enabled: CacheEnabledMode,
    pub max_age_s: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CacheEnabledMode {
    On,
    Off,
}

pub enum InferenceOutput {
    NonStreaming(InferenceResponse),
    Streaming(
        Box<dyn futures::Stream<Item = Result<ContentBlockChunk, anyhow::Error>> + Send + Unpin>,
    ),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InferenceResponse {
    pub inference_id: uuid::Uuid,
    pub episode_id: Option<uuid::Uuid>,
    pub variant_name: String,
    pub output: Vec<ContentBlockOutput>,
}

impl InferenceResponse {
    pub fn inference_id(&self) -> uuid::Uuid {
        self.inference_id
    }

    pub fn episode_id(&self) -> uuid::Uuid {
        self.episode_id.unwrap_or_else(|| uuid::Uuid::new_v4())
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContentBlockOutput {
    pub content: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContentBlockChunk {
    pub content: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InferenceResponseChunk {
    pub inference_id: uuid::Uuid,
    pub output: Vec<ContentBlockChunk>,
}

// Additional types for render_inferences tests
pub type StorageKind = tensorzero_internal::inference::types::storage::StorageKind;
pub type StoragePath = tensorzero_internal::inference::types::storage::StoragePath;
pub type Tool = tensorzero_internal::tool::Tool;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StoredInference;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StoredChatInference;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StoredJsonInference;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DynamicEvaluationRunParams;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FeedbackParams;

// Stub client that will panic if used
pub struct Client;

impl Client {
    pub async fn inference(
        &self,
        _params: ClientInferenceParams,
    ) -> Result<InferenceOutput, anyhow::Error> {
        panic!("E2E tests using the removed client SDK are not functional. These tests need to be rewritten to use HTTP requests directly.");
    }
}

// Stub for ClientBuilder
pub struct ClientBuilder;

pub enum ClientBuilderMode {
    HTTPGateway {
        url: String,
    },
    EmbeddedGateway {
        config_file: Option<std::path::PathBuf>,
        clickhouse_url: Option<String>,
        timeout: Option<u64>,
    },
}

impl ClientBuilder {
    pub fn new(_mode: ClientBuilderMode) -> Self {
        ClientBuilder
    }

    pub async fn build(self) -> Result<Client, anyhow::Error> {
        Ok(Client)
    }
}
