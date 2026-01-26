use std::future::Future;

use reqwest::Client;
use serde::{Deserialize, Serialize};

use crate::endpoints::inference::InferenceCredentials;
use crate::error::Error;
use crate::inference::types::{Latency, Usage};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClassificationRequest {
    pub input: Vec<String>,
    pub raw_scores: bool,
    /// Priority level (high/normal/low) - forwarded to provider
    #[serde(skip_serializing_if = "Option::is_none")]
    pub priority: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClassificationObject {
    pub score: f32,
    pub label: String,
}

#[derive(Debug, Clone)]
pub struct ClassificationProviderResponse {
    pub data: Vec<Vec<ClassificationObject>>,
    pub usage: Usage,
    pub raw_request: String,
    pub raw_response: String,
    pub latency: Latency,
}

pub trait ClassificationProvider {
    fn classify(
        &self,
        request: &ClassificationRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> impl Future<Output = Result<ClassificationProviderResponse, Error>> + Send;
}
