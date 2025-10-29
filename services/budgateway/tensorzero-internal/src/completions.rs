use crate::endpoints::inference::InferenceCredentials;
use crate::error::Error;
use crate::inference::types::{Latency, Usage};
use futures::Stream;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::Value;
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
    pub repetition_penalty: Option<f32>,
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
    #[serde(skip_serializing_if = "Option::is_none")]
    pub usage: Option<Usage>,
    /// Catch-all field for forward compatibility with vLLM API changes
    /// This prevents deserialization failures when vLLM adds new fields
    #[serde(flatten)]
    pub extra: HashMap<String, Value>,
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
    /// Catch-all field for forward compatibility with vLLM API changes
    /// This prevents deserialization failures when vLLM adds new fields
    #[serde(flatten)]
    pub extra: HashMap<String, Value>,
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

impl CompletionRequest {
    /// Validate completion request parameters
    ///
    /// Ensures parameters are within reasonable bounds to prevent provider errors
    pub fn validate(&self) -> Result<(), Error> {
        use crate::error::ErrorDetails;

        // Validate n (number of completions)
        if let Some(n) = self.n {
            if n == 0 {
                return Err(Error::new(ErrorDetails::InvalidRequest {
                    message: "n must be >= 1".to_string(),
                }));
            }
            if n > 128 {
                return Err(Error::new(ErrorDetails::InvalidRequest {
                    message: "n must be <= 128".to_string(),
                }));
            }
        }

        // Validate best_of must be >= n
        if let Some(best_of) = self.best_of {
            let n = self.n.unwrap_or(1);
            if best_of < n {
                return Err(Error::new(ErrorDetails::InvalidRequest {
                    message: format!("best_of ({}) must be >= n ({})", best_of, n),
                }));
            }
            if best_of > 128 {
                return Err(Error::new(ErrorDetails::InvalidRequest {
                    message: "best_of must be <= 128".to_string(),
                }));
            }
        }

        // Validate temperature range
        if let Some(temp) = self.temperature {
            if temp < 0.0 || temp > 2.0 {
                return Err(Error::new(ErrorDetails::InvalidRequest {
                    message: "temperature must be between 0.0 and 2.0".to_string(),
                }));
            }
        }

        // Validate top_p range
        if let Some(top_p) = self.top_p {
            if top_p < 0.0 || top_p > 1.0 {
                return Err(Error::new(ErrorDetails::InvalidRequest {
                    message: "top_p must be between 0.0 and 1.0".to_string(),
                }));
            }
        }

        // Validate repetition_penalty range (must be > 0.0, matching vLLM validation)
        if let Some(rep_penalty) = self.repetition_penalty {
            if rep_penalty <= 0.0 {
                return Err(Error::new(ErrorDetails::InvalidRequest {
                    message: "repetition_penalty must be greater than 0.0".to_string(),
                }));
            }
        }

        // Validate stop sequences (max 4 for OpenAI)
        if let Some(ref stop) = self.stop {
            if let Some(arr) = stop.as_string_array() {
                if arr.len() > 4 {
                    return Err(Error::new(ErrorDetails::InvalidRequest {
                        message: "stop array must contain at most 4 sequences".to_string(),
                    }));
                }
            }
        }

        Ok(())
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

    // Validation tests
    fn create_test_request() -> CompletionRequest {
        CompletionRequest {
            id: Uuid::now_v7(),
            model: Arc::from("test-model"),
            prompt: Some(CompletionPrompt::String("test".to_string())),
            suffix: None,
            max_tokens: Some(100),
            temperature: Some(0.7),
            top_p: Some(0.9),
            n: Some(1),
            stream: Some(false),
            logprobs: None,
            echo: None,
            stop: None,
            presence_penalty: None,
            frequency_penalty: None,
            repetition_penalty: None,
            best_of: None,
            logit_bias: None,
            user: None,
            seed: None,
            ignore_eos: None,
        }
    }

    #[test]
    fn test_validation_valid_request() {
        let request = create_test_request();
        assert!(request.validate().is_ok());
    }

    #[test]
    fn test_validation_n_zero() {
        let mut request = create_test_request();
        request.n = Some(0);
        let result = request.validate();
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("n must be >= 1"));
    }

    #[test]
    fn test_validation_n_too_large() {
        let mut request = create_test_request();
        request.n = Some(129);
        let result = request.validate();
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("n must be <= 128"));
    }

    #[test]
    fn test_validation_best_of_less_than_n() {
        let mut request = create_test_request();
        request.n = Some(5);
        request.best_of = Some(3);
        let result = request.validate();
        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .to_string()
            .contains("best_of (3) must be >= n (5)"));
    }

    #[test]
    fn test_validation_best_of_valid() {
        let mut request = create_test_request();
        request.n = Some(3);
        request.best_of = Some(5);
        assert!(request.validate().is_ok());

        request.n = Some(5);
        request.best_of = Some(5);
        assert!(request.validate().is_ok());
    }

    #[test]
    fn test_validation_best_of_too_large() {
        let mut request = create_test_request();
        request.best_of = Some(129);
        let result = request.validate();
        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .to_string()
            .contains("best_of must be <= 128"));
    }

    #[test]
    fn test_validation_temperature_out_of_range() {
        let mut request = create_test_request();
        request.temperature = Some(-0.1);
        let result = request.validate();
        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .to_string()
            .contains("temperature must be between 0.0 and 2.0"));

        request.temperature = Some(2.1);
        let result = request.validate();
        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .to_string()
            .contains("temperature must be between 0.0 and 2.0"));
    }

    #[test]
    fn test_validation_temperature_valid() {
        let mut request = create_test_request();
        request.temperature = Some(0.0);
        assert!(request.validate().is_ok());

        request.temperature = Some(1.0);
        assert!(request.validate().is_ok());

        request.temperature = Some(2.0);
        assert!(request.validate().is_ok());
    }

    #[test]
    fn test_validation_top_p_out_of_range() {
        let mut request = create_test_request();
        request.top_p = Some(-0.1);
        let result = request.validate();
        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .to_string()
            .contains("top_p must be between 0.0 and 1.0"));

        request.top_p = Some(1.1);
        let result = request.validate();
        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .to_string()
            .contains("top_p must be between 0.0 and 1.0"));
    }

    #[test]
    fn test_validation_top_p_valid() {
        let mut request = create_test_request();
        request.top_p = Some(0.0);
        assert!(request.validate().is_ok());

        request.top_p = Some(0.5);
        assert!(request.validate().is_ok());

        request.top_p = Some(1.0);
        assert!(request.validate().is_ok());
    }

    #[test]
    fn test_validation_stop_sequences_too_many() {
        let mut request = create_test_request();
        request.stop = Some(CompletionStop::StringArray(vec![
            "stop1".to_string(),
            "stop2".to_string(),
            "stop3".to_string(),
            "stop4".to_string(),
            "stop5".to_string(),
        ]));
        let result = request.validate();
        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .to_string()
            .contains("stop array must contain at most 4 sequences"));
    }

    #[test]
    fn test_validation_stop_sequences_valid() {
        let mut request = create_test_request();
        request.stop = Some(CompletionStop::String("STOP".to_string()));
        assert!(request.validate().is_ok());

        request.stop = Some(CompletionStop::StringArray(vec![
            "stop1".to_string(),
            "stop2".to_string(),
            "stop3".to_string(),
            "stop4".to_string(),
        ]));
        assert!(request.validate().is_ok());
    }

    #[test]
    fn test_validation_repetition_penalty_zero() {
        let mut request = create_test_request();
        request.repetition_penalty = Some(0.0);
        let result = request.validate();
        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .to_string()
            .contains("repetition_penalty must be greater than 0.0"));
    }

    #[test]
    fn test_validation_repetition_penalty_negative() {
        let mut request = create_test_request();
        request.repetition_penalty = Some(-1.0);
        let result = request.validate();
        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .to_string()
            .contains("repetition_penalty must be greater than 0.0"));
    }

    #[test]
    fn test_validation_repetition_penalty_valid() {
        let mut request = create_test_request();

        // Test small positive value
        request.repetition_penalty = Some(0.1);
        assert!(request.validate().is_ok());

        // Test typical value around 1.0
        request.repetition_penalty = Some(1.0);
        assert!(request.validate().is_ok());

        // Test value slightly above 1.0
        request.repetition_penalty = Some(1.5);
        assert!(request.validate().is_ok());

        // Test larger value (no upper bound in vLLM)
        request.repetition_penalty = Some(5.0);
        assert!(request.validate().is_ok());

        // Test very large value
        request.repetition_penalty = Some(100.0);
        assert!(request.validate().is_ok());
    }
}
