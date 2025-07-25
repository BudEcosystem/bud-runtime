use crate::endpoints::inference::InferenceCredentials;
use crate::error::Error;
use crate::openai_batch::{
    ListBatchesParams, ListBatchesResponse, OpenAIBatchObject, OpenAIFileObject,
};
use async_trait::async_trait;

/// Trait for providers that support batch operations (file upload and batch processing)
#[async_trait]
pub trait BatchProvider: Send + Sync {
    /// Upload a file to the provider
    async fn upload_file(
        &self,
        content: Vec<u8>,
        filename: String,
        purpose: String,
        client: &reqwest::Client,
        api_keys: &InferenceCredentials,
    ) -> Result<OpenAIFileObject, Error>;

    /// Retrieve file metadata from the provider
    async fn get_file(
        &self,
        file_id: &str,
        client: &reqwest::Client,
        api_keys: &InferenceCredentials,
    ) -> Result<OpenAIFileObject, Error>;

    /// Retrieve file content from the provider
    async fn get_file_content(
        &self,
        file_id: &str,
        client: &reqwest::Client,
        api_keys: &InferenceCredentials,
    ) -> Result<Vec<u8>, Error>;

    /// Delete a file from the provider
    async fn delete_file(
        &self,
        file_id: &str,
        client: &reqwest::Client,
        api_keys: &InferenceCredentials,
    ) -> Result<OpenAIFileObject, Error>;

    /// Create a new batch with the provider
    async fn create_batch(
        &self,
        input_file_id: String,
        endpoint: String,
        completion_window: String,
        metadata: Option<std::collections::HashMap<String, String>>,
        client: &reqwest::Client,
        api_keys: &InferenceCredentials,
    ) -> Result<OpenAIBatchObject, Error>;

    /// Retrieve batch status from the provider
    async fn get_batch(
        &self,
        batch_id: &str,
        client: &reqwest::Client,
        api_keys: &InferenceCredentials,
    ) -> Result<OpenAIBatchObject, Error>;

    /// List batches from the provider
    async fn list_batches(
        &self,
        params: ListBatchesParams,
        client: &reqwest::Client,
        api_keys: &InferenceCredentials,
    ) -> Result<ListBatchesResponse, Error>;

    /// Cancel a batch with the provider
    async fn cancel_batch(
        &self,
        batch_id: &str,
        client: &reqwest::Client,
        api_keys: &InferenceCredentials,
    ) -> Result<OpenAIBatchObject, Error>;
}
