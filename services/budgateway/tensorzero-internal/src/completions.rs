use crate::endpoints::inference::InferenceCredentials;
use crate::error::Error;
use crate::inference::types::{Latency, Usage};
use futures::Stream;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::future::Future;
use std::pin::Pin;
use std::sync::Arc;
use uuid::Uuid;

/// Request for text completion (non-chat)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompletionRequest {
    pub id: Uuid,
    pub model: Arc<str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prompt: Option<CompletionPrompt>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub suffix: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_tokens: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub top_p: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub n: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stream: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub logprobs: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub echo: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stop: Option<CompletionStop>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub presence_penalty: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub frequency_penalty: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub best_of: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub logit_bias: Option<HashMap<String, f32>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub user: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub seed: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ignore_eos: Option<bool>,
}

/// Prompt can be a string, array of strings, array of tokens, or array of token arrays
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(untagged)]
pub enum CompletionPrompt {
    String(String),
    StringArray(Vec<String>),
    TokenArray(Vec<u32>),
    TokenArrays(Vec<Vec<u32>>),
}

/// Stop can be a string or array of up to 4 strings
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(untagged)]
pub enum CompletionStop {
    String(String),
    StringArray(Vec<String>),
}

/// Response from completion endpoint
#[derive(Debug, Clone)]
pub struct CompletionResponse {
    pub id: Uuid,
    pub object: String, // "text_completion"
    pub created: u64,
    pub model: Arc<str>,
    pub choices: Vec<CompletionChoice>,
    pub usage: Usage,
    pub raw_request: String,
    pub raw_response: String,
    pub latency: Latency,
}

/// Individual completion choice
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompletionChoice {
    pub text: String,
    pub index: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub logprobs: Option<CompletionLogProbs>,
    pub finish_reason: String,
}

/// Log probabilities for completion
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompletionLogProbs {
    pub tokens: Vec<String>,
    pub token_logprobs: Vec<Option<f32>>,
    pub top_logprobs: Vec<HashMap<String, f32>>,
    pub text_offset: Vec<u32>,
}

/// Provider response for completions
#[derive(Debug, Clone)]
pub struct CompletionProviderResponse {
    pub id: Uuid,
    pub created: u64,
    pub model: Arc<str>,
    pub choices: Vec<CompletionChoice>,
    pub usage: Usage,
    pub raw_request: String,
    pub raw_response: String,
    pub latency: Latency,
}

/// Chunk for streaming completions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompletionChunk {
    pub id: String,
    pub object: String, // "text_completion"
    pub created: u64,
    pub model: String,
    pub choices: Vec<CompletionChoiceChunk>,
}

/// Choice chunk for streaming
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompletionChoiceChunk {
    pub text: String,
    pub index: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub logprobs: Option<CompletionLogProbs>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub finish_reason: Option<String>,
}

/// Stream type for completions
pub type CompletionStream = Pin<Box<dyn Stream<Item = Result<CompletionChunk, Error>> + Send>>;

/// Provider trait for text completion
pub trait CompletionProvider {
    fn complete(
        &self,
        request: &CompletionRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> impl Future<Output = Result<CompletionProviderResponse, Error>> + Send;

    fn complete_stream(
        &self,
        request: &CompletionRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> impl Future<Output = Result<(CompletionStream, String), Error>> + Send;
}

impl CompletionPrompt {
    /// Returns true if this is a single string prompt
    pub fn is_string(&self) -> bool {
        matches!(self, CompletionPrompt::String(_))
    }

    /// Get the prompt as a single string if possible
    pub fn as_string(&self) -> Option<&str> {
        match self {
            CompletionPrompt::String(s) => Some(s),
            _ => None,
        }
    }

    /// Get the prompt as a string array if possible
    pub fn as_string_array(&self) -> Option<&[String]> {
        match self {
            CompletionPrompt::StringArray(arr) => Some(arr),
            _ => None,
        }
    }
}

impl CompletionStop {
    /// Get stop as a single string if possible
    pub fn as_string(&self) -> Option<&str> {
        match self {
            CompletionStop::String(s) => Some(s),
            _ => None,
        }
    }

    /// Get stop as string array if possible
    pub fn as_string_array(&self) -> Option<&[String]> {
        match self {
            CompletionStop::StringArray(arr) => Some(arr),
            _ => None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_completion_prompt_string() {
        let prompt = CompletionPrompt::String("Hello".to_string());
        assert!(prompt.is_string());
        assert_eq!(prompt.as_string(), Some("Hello"));
        assert_eq!(prompt.as_string_array(), None);
    }

    #[test]
    fn test_completion_prompt_string_array() {
        let prompt = CompletionPrompt::StringArray(vec!["Hello".to_string(), "World".to_string()]);
        assert!(!prompt.is_string());
        assert_eq!(prompt.as_string(), None);
        assert_eq!(prompt.as_string_array().map(|a| a.len()), Some(2));
    }

    #[test]
    fn test_completion_prompt_serialization() {
        // Test string prompt
        let prompt = CompletionPrompt::String("Hello".to_string());
        let json = serde_json::to_string(&prompt).unwrap();
        assert_eq!(json, "\"Hello\"");

        // Test string array
        let prompt = CompletionPrompt::StringArray(vec!["A".to_string(), "B".to_string()]);
        let json = serde_json::to_string(&prompt).unwrap();
        assert_eq!(json, "[\"A\",\"B\"]");

        // Test token array
        let prompt = CompletionPrompt::TokenArray(vec![1, 2, 3]);
        let json = serde_json::to_string(&prompt).unwrap();
        assert_eq!(json, "[1,2,3]");
    }

    #[test]
    fn test_completion_stop_variants() {
        let stop = CompletionStop::String("STOP".to_string());
        assert_eq!(stop.as_string(), Some("STOP"));

        let stop = CompletionStop::StringArray(vec!["STOP".to_string(), "END".to_string()]);
        assert_eq!(stop.as_string_array().map(|a| a.len()), Some(2));
    }

    #[test]
    fn test_completion_choice_serialization() {
        let choice = CompletionChoice {
            text: "Hello, world!".to_string(),
            index: 0,
            logprobs: None,
            finish_reason: "stop".to_string(),
        };

        let json = serde_json::to_string(&choice).unwrap();
        let deserialized: CompletionChoice = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.text, "Hello, world!");
        assert_eq!(deserialized.index, 0);
        assert_eq!(deserialized.finish_reason, "stop");
    }
}
