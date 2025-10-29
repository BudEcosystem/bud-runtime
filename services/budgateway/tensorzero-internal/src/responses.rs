use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;

/// Reference to a prompt template and its variables
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PromptReference {
    /// The unique identifier of the prompt template to use
    pub id: String,

    /// Optional map of values to substitute in for variables in your prompt
    #[serde(skip_serializing_if = "Option::is_none")]
    pub variables: Option<HashMap<String, Value>>,

    /// Optional version of the prompt template
    #[serde(skip_serializing_if = "Option::is_none")]
    pub version: Option<String>,
}

/// OpenAI-compatible request parameters for creating a response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OpenAIResponseCreateParams {
    /// ID of the model to use (optional for prompt-based requests)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,

    /// The input to the model. Can be a string or array of content items (optional for prompt-based requests)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input: Option<Value>,

    /// Developer-provided instructions for the model (can be string or array)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub instructions: Option<Value>,

    /// List of tools available to the model
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tools: Option<Vec<Value>>,

    /// Controls how the model selects tools
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tool_choice: Option<Value>,

    /// Whether to enable parallel tool calls
    #[serde(skip_serializing_if = "Option::is_none")]
    pub parallel_tool_calls: Option<bool>,

    /// Maximum number of tool calls allowed
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_tool_calls: Option<i32>,

    /// ID of a previous response for multi-turn conversations
    #[serde(skip_serializing_if = "Option::is_none")]
    pub previous_response_id: Option<String>,

    /// Sampling temperature between 0 and 2
    #[serde(skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f32>,

    /// Maximum number of tokens to generate
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_output_tokens: Option<i32>,

    /// Format of the response
    #[serde(skip_serializing_if = "Option::is_none")]
    pub response_format: Option<Value>,

    /// Configuration for reasoning models
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reasoning: Option<Value>,

    /// Additional data to include in the response
    #[serde(skip_serializing_if = "Option::is_none")]
    pub include: Option<Vec<String>>,

    /// Custom metadata for the response
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<HashMap<String, Value>>,

    /// Reference to a prompt template and its variables
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prompt: Option<PromptReference>,

    /// Whether to stream the response
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stream: Option<bool>,

    /// Options for streaming
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stream_options: Option<Value>,

    /// Whether to store the response
    #[serde(skip_serializing_if = "Option::is_none")]
    pub store: Option<bool>,

    /// Whether to process in the background
    #[serde(skip_serializing_if = "Option::is_none")]
    pub background: Option<bool>,

    /// Service tier for the request
    #[serde(skip_serializing_if = "Option::is_none")]
    pub service_tier: Option<String>,

    /// Supported modalities for the response
    #[serde(skip_serializing_if = "Option::is_none")]
    pub modalities: Option<Vec<String>>,

    /// Unique identifier for the end-user
    #[serde(skip_serializing_if = "Option::is_none")]
    pub user: Option<String>,

    /// Additional fields not explicitly defined
    #[serde(flatten)]
    pub unknown_fields: HashMap<String, Value>,
}

/// OpenAI-compatible response object
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OpenAIResponse {
    /// Unique identifier for the response
    pub id: String,

    /// Object type (always "response")
    #[serde(default = "default_object_type")]
    pub object: String,

    /// Unix timestamp of when the response was created
    pub created_at: i64,

    /// Status of the response
    pub status: ResponseStatus,

    /// Whether processing in background
    #[serde(skip_serializing_if = "Option::is_none")]
    pub background: Option<bool>,

    /// Error information if the response failed
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<ResponseError>,

    /// Incomplete details
    #[serde(skip_serializing_if = "Option::is_none")]
    pub incomplete_details: Option<Value>,

    /// Instructions used (can be string or array of message objects)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub instructions: Option<Value>,

    /// Max output tokens
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_output_tokens: Option<i32>,

    /// Max tool calls
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_tool_calls: Option<i32>,

    /// ID of the model used
    pub model: String,

    /// List of output items
    pub output: Vec<Value>,

    /// Parallel tool calls enabled
    #[serde(skip_serializing_if = "Option::is_none")]
    pub parallel_tool_calls: Option<bool>,

    /// Previous response ID if part of a conversation
    #[serde(skip_serializing_if = "Option::is_none")]
    pub previous_response_id: Option<String>,

    /// Prompt reference used for this response
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prompt: Option<PromptReference>,

    /// Reasoning information
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reasoning: Option<Value>,

    /// Service tier
    #[serde(skip_serializing_if = "Option::is_none")]
    pub service_tier: Option<String>,

    /// Whether to store
    #[serde(skip_serializing_if = "Option::is_none")]
    pub store: Option<bool>,

    /// Temperature used
    #[serde(skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f32>,

    /// Text formatting options
    #[serde(skip_serializing_if = "Option::is_none")]
    pub text: Option<Value>,

    /// Tool choice configuration used
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tool_choice: Option<Value>,

    /// Tools configuration used
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tools: Option<Vec<Value>>,

    /// Top logprobs
    #[serde(skip_serializing_if = "Option::is_none")]
    pub top_logprobs: Option<i32>,

    /// Top P
    #[serde(skip_serializing_if = "Option::is_none")]
    pub top_p: Option<f32>,

    /// Truncation settings
    #[serde(skip_serializing_if = "Option::is_none")]
    pub truncation: Option<Value>,

    /// Token usage statistics
    #[serde(skip_serializing_if = "Option::is_none")]
    pub usage: Option<ResponseUsage>,

    /// User ID
    #[serde(skip_serializing_if = "Option::is_none")]
    pub user: Option<String>,

    /// Custom metadata
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<HashMap<String, Value>>,
}

fn default_object_type() -> String {
    "response".to_string()
}

/// Status of a response
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ResponseStatus {
    Completed,
    Failed,
    InProgress,
    Incomplete,
    Queued,
    Cancelled,
}

/// Token usage statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResponseUsage {
    pub input_tokens: i32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input_tokens_details: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output_tokens: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output_tokens_details: Option<serde_json::Value>,
    pub total_tokens: i32,
}

/// Error information for failed responses
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResponseError {
    pub code: String,
    pub message: String,
}

/// Response for listing input items
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResponseInputItemsList {
    pub data: Vec<Value>,
    pub has_more: bool,
    pub first_id: Option<String>,
    pub last_id: Option<String>,
}

/// Streaming event for Server-Sent Events
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResponseStreamEvent {
    pub event: String,
    pub data: Value,
}

/// Result type for responses that can be either streaming or non-streaming
/// Used by providers that need to auto-detect response format (e.g., BudPrompt)
pub enum ResponseResult {
    /// Streaming response (SSE)
    Streaming(
        Box<
            dyn futures::Stream<Item = Result<ResponseStreamEvent, crate::error::Error>>
                + Send
                + Unpin,
        >,
    ),
    /// Non-streaming JSON response
    NonStreaming(OpenAIResponse),
}

/// Types of streaming events
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ResponseEventType {
    ResponseCreated,
    ResponseInProgress,
    ResponseDone,
    ResponseFailed,
    ResponseCancelled,
    RateLimitUpdated,
    ContentBlockStart,
    ContentBlockDelta,
    ContentBlockStop,
    ToolUseBlockStart,
    ToolUseBlockDelta,
    ToolUseBlockStop,
}

/// Trait for providers that support the Responses API
#[async_trait::async_trait]
pub trait ResponseProvider {
    /// Create a new response
    async fn create_response(
        &self,
        request: &OpenAIResponseCreateParams,
        client: &reqwest::Client,
        api_keys: &crate::endpoints::inference::InferenceCredentials,
    ) -> Result<OpenAIResponse, crate::error::Error>;

    /// Stream a response
    async fn stream_response(
        &self,
        request: &OpenAIResponseCreateParams,
        client: &reqwest::Client,
        api_keys: &crate::endpoints::inference::InferenceCredentials,
    ) -> Result<
        Box<
            dyn futures::Stream<Item = Result<ResponseStreamEvent, crate::error::Error>>
                + Send
                + Unpin,
        >,
        crate::error::Error,
    >;

    /// Retrieve a response by ID
    async fn retrieve_response(
        &self,
        response_id: &str,
        client: &reqwest::Client,
        api_keys: &crate::endpoints::inference::InferenceCredentials,
    ) -> Result<OpenAIResponse, crate::error::Error>;

    /// Delete a response by ID
    async fn delete_response(
        &self,
        response_id: &str,
        client: &reqwest::Client,
        api_keys: &crate::endpoints::inference::InferenceCredentials,
    ) -> Result<serde_json::Value, crate::error::Error>;

    /// Cancel a response by ID
    async fn cancel_response(
        &self,
        response_id: &str,
        client: &reqwest::Client,
        api_keys: &crate::endpoints::inference::InferenceCredentials,
    ) -> Result<OpenAIResponse, crate::error::Error>;

    /// List input items for a response
    async fn list_response_input_items(
        &self,
        response_id: &str,
        client: &reqwest::Client,
        api_keys: &crate::endpoints::inference::InferenceCredentials,
    ) -> Result<ResponseInputItemsList, crate::error::Error>;

    /// Execute response with automatic format detection (for providers like BudPrompt)
    /// Default implementation falls back to stream parameter
    async fn execute_response_with_detection(
        &self,
        request: &OpenAIResponseCreateParams,
        _model_name: &str,
        client: &reqwest::Client,
        api_keys: &crate::endpoints::inference::InferenceCredentials,
    ) -> Result<ResponseResult, crate::error::Error> {
        // Default implementation: check stream parameter and call appropriate method
        if request.stream.unwrap_or(false) {
            Ok(ResponseResult::Streaming(
                self.stream_response(request, client, api_keys).await?,
            ))
        } else {
            Ok(ResponseResult::NonStreaming(
                self.create_response(request, client, api_keys).await?,
            ))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_response_create_params_serialization() {
        let params = OpenAIResponseCreateParams {
            model: Some("gpt-4".to_string()),
            input: Some(json!("Hello, world!")),
            instructions: Some(json!("Be helpful")),
            tools: Some(vec![
                json!({"type": "function", "function": {"name": "test"}}),
            ]),
            tool_choice: Some(json!("auto")),
            parallel_tool_calls: Some(true),
            max_tool_calls: Some(5),
            previous_response_id: None,
            temperature: Some(0.7),
            max_output_tokens: Some(1000),
            response_format: Some(json!({"type": "json_object"})),
            reasoning: None,
            include: Some(vec!["usage".to_string()]),
            metadata: Some(HashMap::from([("key".to_string(), json!("value"))])),
            prompt: Some(PromptReference {
                id: "template_123".to_string(),
                variables: Some(HashMap::from([("name".to_string(), json!("World"))])),
                version: Some("v1".to_string()),
            }),
            stream: Some(false),
            stream_options: None,
            store: Some(true),
            background: Some(false),
            service_tier: Some("default".to_string()),
            modalities: Some(vec!["text".to_string()]),
            user: Some("user123".to_string()),
            unknown_fields: HashMap::new(),
        };

        let serialized = serde_json::to_string(&params).unwrap();
        let deserialized: OpenAIResponseCreateParams = serde_json::from_str(&serialized).unwrap();

        assert_eq!(params.model, deserialized.model);
        assert_eq!(params.input, deserialized.input);
        assert_eq!(params.instructions, deserialized.instructions);
        assert_eq!(params.temperature, deserialized.temperature);
        assert_eq!(
            params.prompt.as_ref().map(|p| &p.id),
            deserialized.prompt.as_ref().map(|p| &p.id)
        );
    }

    #[test]
    fn test_response_create_params_minimal() {
        let json_str = r#"{
            "model": "gpt-4",
            "input": "Hello"
        }"#;

        let params: OpenAIResponseCreateParams = serde_json::from_str(json_str).unwrap();
        assert_eq!(params.model, Some("gpt-4".to_string()));
        assert_eq!(params.input, Some(json!("Hello")));
        assert!(params.instructions.is_none());
        assert!(params.tools.is_none());
        assert!(params.temperature.is_none());
        assert!(params.prompt.is_none());
    }

    #[test]
    fn test_response_create_params_with_unknown_fields() {
        let json_str = r#"{
            "model": "gpt-4",
            "input": "Hello",
            "custom_field": "custom_value",
            "another_field": 123
        }"#;

        let params: OpenAIResponseCreateParams = serde_json::from_str(json_str).unwrap();
        assert_eq!(params.model, Some("gpt-4".to_string()));
        assert_eq!(
            params.unknown_fields.get("custom_field").unwrap(),
            &json!("custom_value")
        );
        assert_eq!(
            params.unknown_fields.get("another_field").unwrap(),
            &json!(123)
        );
    }

    #[test]
    fn test_prompt_reference_serialization() {
        let prompt = PromptReference {
            id: "prompt_123".to_string(),
            variables: Some(HashMap::from([
                ("user_name".to_string(), json!("Alice")),
                ("topic".to_string(), json!("weather")),
            ])),
            version: Some("v2.1".to_string()),
        };

        let json = serde_json::to_value(&prompt).unwrap();
        assert_eq!(json["id"], "prompt_123");
        assert_eq!(json["variables"]["user_name"], "Alice");
        assert_eq!(json["variables"]["topic"], "weather");
        assert_eq!(json["version"], "v2.1");

        // Test deserialization
        let deserialized: PromptReference = serde_json::from_value(json.clone()).unwrap();
        assert_eq!(deserialized.id, "prompt_123");
        assert_eq!(deserialized.version, Some("v2.1".to_string()));
    }

    #[test]
    fn test_response_create_params_with_prompt() {
        let json_str = r#"{
            "model": "gpt-4",
            "input": "Test input",
            "prompt": {
                "id": "template_abc",
                "variables": {"name": "Bob", "age": 30},
                "version": "1.0"
            }
        }"#;

        let params: OpenAIResponseCreateParams = serde_json::from_str(json_str).unwrap();
        assert_eq!(params.model, Some("gpt-4".to_string()));
        assert!(params.prompt.is_some());

        let prompt = params.prompt.unwrap();
        assert_eq!(prompt.id, "template_abc");
        assert_eq!(prompt.version, Some("1.0".to_string()));
        assert!(prompt.variables.is_some());

        let vars = prompt.variables.unwrap();
        assert_eq!(vars.get("name").unwrap(), &json!("Bob"));
        assert_eq!(vars.get("age").unwrap(), &json!(30));
    }

    #[test]
    fn test_openai_response_serialization() {
        let response = OpenAIResponse {
            id: "resp_123".to_string(),
            object: "response".to_string(),
            created_at: 1234567890,
            status: ResponseStatus::Completed,
            background: Some(false),
            error: None,
            incomplete_details: None,
            instructions: Some(json!("Be helpful")),
            max_output_tokens: Some(1000),
            max_tool_calls: None,
            model: "gpt-4".to_string(),
            output: vec![json!({"type": "text", "text": "Hello!"})],
            parallel_tool_calls: Some(true),
            previous_response_id: None,
            prompt: None,
            reasoning: None,
            service_tier: Some("default".to_string()),
            store: Some(true),
            temperature: Some(0.7),
            text: None,
            tool_choice: None,
            tools: None,
            top_logprobs: None,
            top_p: None,
            truncation: None,
            usage: Some(ResponseUsage {
                input_tokens: 10,
                input_tokens_details: None,
                output_tokens: Some(20),
                output_tokens_details: None,
                total_tokens: 30,
            }),
            user: None,
            metadata: None,
        };

        let serialized = serde_json::to_string(&response).unwrap();
        let deserialized: OpenAIResponse = serde_json::from_str(&serialized).unwrap();

        assert_eq!(response.id, deserialized.id);
        assert_eq!(response.created_at, deserialized.created_at);
        assert_eq!(response.model, deserialized.model);
        assert_eq!(response.status, deserialized.status);
        assert_eq!(response.usage.as_ref().unwrap().total_tokens, 30);
    }

    #[test]
    fn test_response_status_serialization() {
        assert_eq!(
            serde_json::to_string(&ResponseStatus::Completed).unwrap(),
            r#""completed""#
        );
        assert_eq!(
            serde_json::to_string(&ResponseStatus::Failed).unwrap(),
            r#""failed""#
        );
        assert_eq!(
            serde_json::to_string(&ResponseStatus::InProgress).unwrap(),
            r#""in_progress""#
        );
        assert_eq!(
            serde_json::to_string(&ResponseStatus::Incomplete).unwrap(),
            r#""incomplete""#
        );
    }

    #[test]
    fn test_response_error_serialization() {
        let error = ResponseError {
            code: "invalid_request".to_string(),
            message: "Invalid model specified".to_string(),
        };

        let json = serde_json::to_value(&error).unwrap();
        assert_eq!(json["code"], "invalid_request");
        assert_eq!(json["message"], "Invalid model specified");
    }

    #[test]
    fn test_response_event_type_serialization() {
        assert_eq!(
            serde_json::to_string(&ResponseEventType::ResponseCreated).unwrap(),
            r#""response_created""#
        );
        assert_eq!(
            serde_json::to_string(&ResponseEventType::ContentBlockDelta).unwrap(),
            r#""content_block_delta""#
        );
        assert_eq!(
            serde_json::to_string(&ResponseEventType::ToolUseBlockStart).unwrap(),
            r#""tool_use_block_start""#
        );
    }

    #[test]
    fn test_response_stream_event() {
        let event = ResponseStreamEvent {
            event: "content_block_delta".to_string(),
            data: json!({"delta": {"text": "Hello"}}),
        };

        let json = serde_json::to_value(&event).unwrap();
        assert_eq!(json["event"], "content_block_delta");
        assert_eq!(json["data"]["delta"]["text"], "Hello");
    }

    #[test]
    fn test_response_input_items_list() {
        let list = ResponseInputItemsList {
            data: vec![json!({"id": "item1"}), json!({"id": "item2"})],
            has_more: true,
            first_id: Some("item1".to_string()),
            last_id: Some("item2".to_string()),
        };

        let json = serde_json::to_value(&list).unwrap();
        assert_eq!(json["data"].as_array().unwrap().len(), 2);
        assert_eq!(json["has_more"], true);
        assert_eq!(json["first_id"], "item1");
        assert_eq!(json["last_id"], "item2");
    }
}
