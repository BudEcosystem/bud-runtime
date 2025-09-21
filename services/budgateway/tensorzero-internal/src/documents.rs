use crate::endpoints::inference::InferenceCredentials;
use crate::error::Error;
use crate::inference::types::{Latency, Usage};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;

// Document processing types matching buddoc's Mistral-compatible format

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DocumentType {
    DocumentUrl,
    ImageUrl,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DocumentInput {
    #[serde(rename = "type")]
    pub doc_type: DocumentType,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub document_url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub image_url: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DocumentProcessingRequest {
    pub id: Uuid,
    pub model: Arc<str>,
    pub document: DocumentInput,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prompt: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PageResult {
    pub page_number: i32,
    pub markdown: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UsageInfo {
    pub pages_processed: i32,
    pub size_bytes: i64,
    pub filename: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DocumentProcessingResponse {
    pub id: Uuid,
    pub document_id: Uuid,
    pub model: Arc<str>,
    pub pages: Vec<PageResult>,
    pub usage_info: UsageInfo,
    pub raw_request: String,
    pub raw_response: String,
    pub usage: Usage,
    pub latency: Latency,
    pub document_provider_name: Arc<str>,
}

// Provider response type (before adding gateway metadata)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DocumentProcessingProviderResponse {
    pub document_id: Uuid,
    pub model: String,
    pub pages: Vec<PageResult>,
    pub usage_info: UsageInfo,
    pub raw_request: String,
    pub raw_response: String,
    pub usage: Usage,
    pub latency: Latency,
}

impl DocumentProcessingResponse {
    pub fn new(
        provider_response: DocumentProcessingProviderResponse,
        provider_name: Arc<str>,
    ) -> Self {
        Self {
            id: Uuid::now_v7(),
            document_id: provider_response.document_id,
            model: Arc::from(provider_response.model),
            pages: provider_response.pages,
            usage_info: provider_response.usage_info,
            raw_request: provider_response.raw_request,
            raw_response: provider_response.raw_response,
            usage: provider_response.usage,
            latency: provider_response.latency,
            document_provider_name: provider_name,
        }
    }
}

// Document processing provider trait
pub trait DocumentProcessingProvider {
    fn process_document(
        &self,
        request: &DocumentProcessingRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> impl std::future::Future<Output = Result<DocumentProcessingProviderResponse, Error>> + Send;
}

// OpenAI-compatible request/response types for the gateway endpoint

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OpenAICompatibleDocumentParams {
    pub model: String,
    pub document: DocumentInput,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prompt: Option<String>,
    #[serde(flatten)]
    pub unknown_fields: serde_json::Map<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OpenAICompatibleDocumentResponse {
    pub id: String,
    pub object: String,
    pub created: u64,
    pub model: String,
    pub document_id: String,
    pub pages: Vec<PageResult>,
    pub usage_info: UsageInfo,
}
