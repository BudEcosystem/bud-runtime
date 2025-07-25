use crate::endpoints::batch_inference::StartBatchInferenceParams;
use crate::error::{Error, ErrorDetails};
use crate::inference::types::{Input, InputMessage, InputMessageContent, Role, TextKind};
use crate::tool::BatchDynamicToolParams;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;

/// OpenAI batch request format as specified in their documentation
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct OpenAIBatchRequestItem {
    pub custom_id: String,
    pub method: String,
    pub url: String,
    pub body: Value,
}

/// OpenAI batch response format for successful requests
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct OpenAIBatchResponseItem {
    pub id: String,
    pub custom_id: String,
    pub response: OpenAIBatchResponseBody,
}

/// Response body for successful batch requests
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct OpenAIBatchResponseBody {
    pub status_code: u16,
    pub request_id: String,
    pub body: Value,
}

/// OpenAI batch error format for failed requests
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct OpenAIBatchErrorItem {
    pub id: String,
    pub custom_id: String,
    pub error: OpenAIBatchError,
}

/// Error details for failed batch requests
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct OpenAIBatchError {
    pub code: String,
    pub message: String,
}

/// Parsed JSONL content with validation
#[derive(Debug)]
pub struct ParsedBatchInput {
    pub requests: Vec<OpenAIBatchRequestItem>,
    pub total_requests: usize,
    pub supported_requests: usize,
    pub unsupported_requests: Vec<(usize, String)>, // (line_number, reason)
}

/// Parse JSONL content into OpenAI batch requests
pub fn parse_jsonl_batch_input(content: &str) -> Result<ParsedBatchInput, Error> {
    let lines: Vec<&str> = content.lines().collect();

    if lines.is_empty() {
        return Err(Error::new(ErrorDetails::InvalidRequest {
            message: "Empty JSONL file".to_string(),
        }));
    }

    // Check maximum number of requests (OpenAI limit is 50,000)
    const MAX_REQUESTS: usize = 50_000;
    if lines.len() > MAX_REQUESTS {
        return Err(Error::new(ErrorDetails::InvalidRequest {
            message: format!("Too many requests: {} (max {})", lines.len(), MAX_REQUESTS),
        }));
    }

    let mut requests = Vec::new();
    let mut unsupported_requests = Vec::new();
    let mut request_counter = 0;

    for (line_number, line) in lines.iter().enumerate() {
        let line = line.trim();
        if line.is_empty() {
            continue; // Skip empty lines
        }

        request_counter += 1;

        // Parse JSON line
        let request_item: OpenAIBatchRequestItem = serde_json::from_str(line).map_err(|e| {
            Error::new(ErrorDetails::InvalidRequest {
                message: format!("Invalid JSON on line {}: {}", line_number + 1, e),
            })
        })?;

        // Validate request format
        if let Err(reason) = validate_batch_request_item(&request_item) {
            unsupported_requests.push((line_number + 1, reason));
            continue;
        }

        requests.push(request_item);
    }

    Ok(ParsedBatchInput {
        total_requests: request_counter,
        supported_requests: requests.len(),
        unsupported_requests,
        requests,
    })
}

/// Validate an individual batch request item
fn validate_batch_request_item(item: &OpenAIBatchRequestItem) -> Result<(), String> {
    // Check method
    if item.method.to_uppercase() != "POST" {
        return Err(format!("Unsupported method: {}", item.method));
    }

    // Check supported endpoints
    match item.url.as_str() {
        "/v1/chat/completions" => {
            // Validate chat completion request
            validate_chat_completion_body(&item.body)?;
        }
        "/v1/embeddings" => {
            // Validate embedding request
            validate_embedding_body(&item.body)?;
        }
        _ => {
            return Err(format!("Unsupported endpoint: {}", item.url));
        }
    }

    // Validate custom_id
    if item.custom_id.is_empty() {
        return Err("custom_id cannot be empty".to_string());
    }

    if item.custom_id.len() > 64 {
        return Err("custom_id too long (max 64 characters)".to_string());
    }

    Ok(())
}

/// Validate chat completion request body
fn validate_chat_completion_body(body: &Value) -> Result<(), String> {
    let obj = body.as_object().ok_or("Request body must be an object")?;

    // Check required fields
    if !obj.contains_key("model") {
        return Err("Missing required field: model".to_string());
    }

    if !obj.contains_key("messages") {
        return Err("Missing required field: messages".to_string());
    }

    // Validate messages is an array
    let messages = obj
        .get("messages")
        .ok_or("Missing required field: messages")?;
    if !messages.is_array() {
        return Err("messages must be an array".to_string());
    }

    Ok(())
}

/// Validate embedding request body
fn validate_embedding_body(body: &Value) -> Result<(), String> {
    let obj = body.as_object().ok_or("Request body must be an object")?;

    // Check required fields
    if !obj.contains_key("model") {
        return Err("Missing required field: model".to_string());
    }

    if !obj.contains_key("input") {
        return Err("Missing required field: input".to_string());
    }

    Ok(())
}

/// Convert OpenAI batch requests to TensorZero format
pub fn convert_openai_to_tensorzero_batch(
    parsed_input: &ParsedBatchInput,
    function_name: &str,
) -> Result<StartBatchInferenceParams, Error> {
    let mut inputs = Vec::new();
    let mut custom_id_map = HashMap::new();

    for (index, request_item) in parsed_input.requests.iter().enumerate() {
        // Store custom_id mapping for later use
        custom_id_map.insert(index, request_item.custom_id.clone());

        // Convert based on endpoint
        let input = match request_item.url.as_str() {
            "/v1/chat/completions" => convert_chat_completion_to_input(&request_item.body)?,
            "/v1/embeddings" => convert_embedding_to_input(&request_item.body)?,
            _ => {
                return Err(Error::new(ErrorDetails::InvalidRequest {
                    message: format!("Unsupported endpoint: {}", request_item.url),
                }));
            }
        };

        inputs.push(input);
    }

    Ok(StartBatchInferenceParams {
        function_name: function_name.to_string(),
        episode_ids: None, // Let the system generate these
        inputs,
        params: Default::default(),
        variant_name: None,
        tags: None,
        dynamic_tool_params: BatchDynamicToolParams {
            allowed_tools: None,
            additional_tools: None,
            tool_choice: None,
            parallel_tool_calls: None,
        },
        output_schemas: None,
        credentials: Default::default(),
    })
}

/// Convert chat completion request to TensorZero Input
fn convert_chat_completion_to_input(body: &Value) -> Result<Input, Error> {
    let obj = body.as_object().ok_or_else(|| {
        Error::new(ErrorDetails::InvalidRequest {
            message: "Request body must be an object".to_string(),
        })
    })?;

    let messages = obj
        .get("messages")
        .and_then(|v| v.as_array())
        .ok_or_else(|| {
            Error::new(ErrorDetails::InvalidRequest {
                message: "messages field must be an array".to_string(),
            })
        })?;

    // Convert OpenAI messages to TensorZero InputMessage format
    let mut tensorzero_messages = Vec::new();

    for message in messages {
        let msg_obj = message.as_object().ok_or_else(|| {
            Error::new(ErrorDetails::InvalidRequest {
                message: "Each message must be an object".to_string(),
            })
        })?;

        let role = msg_obj
            .get("role")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                Error::new(ErrorDetails::InvalidRequest {
                    message: "Message must have a role field".to_string(),
                })
            })?;

        let content = msg_obj.get("content").ok_or_else(|| {
            Error::new(ErrorDetails::InvalidRequest {
                message: "Message must have a content field".to_string(),
            })
        })?;

        let role_enum = match role {
            "user" => Role::User,
            "assistant" => Role::Assistant,
            _ => {
                return Err(Error::new(ErrorDetails::InvalidRequest {
                    message: format!("Unsupported role: {role}"),
                }));
            }
        };

        let input_message = InputMessage {
            role: role_enum,
            content: vec![InputMessageContent::Text(TextKind::Text {
                text: content.to_string(),
            })],
        };

        tensorzero_messages.push(input_message);
    }

    // Create Input with the converted messages
    Ok(Input {
        system: None,
        messages: tensorzero_messages,
    })
}

/// Convert embedding request to TensorZero Input
fn convert_embedding_to_input(body: &Value) -> Result<Input, Error> {
    let obj = body.as_object().ok_or_else(|| {
        Error::new(ErrorDetails::InvalidRequest {
            message: "Request body must be an object".to_string(),
        })
    })?;

    let input_value = obj.get("input").ok_or_else(|| {
        Error::new(ErrorDetails::InvalidRequest {
            message: "Missing input field".to_string(),
        })
    })?;

    // Convert input to text
    let text = match input_value {
        Value::String(s) => s.clone(),
        Value::Array(arr) => {
            // If it's an array, join the strings
            let strings: Result<Vec<_>, _> = arr
                .iter()
                .map(|v| {
                    v.as_str()
                        .ok_or("Array elements must be strings")
                        .map(|s| s.to_string())
                })
                .collect();
            strings
                .map_err(|e| {
                    Error::new(ErrorDetails::InvalidRequest {
                        message: e.to_string(),
                    })
                })?
                .join(" ")
        }
        _ => {
            return Err(Error::new(ErrorDetails::InvalidRequest {
                message: "Input must be a string or array of strings".to_string(),
            }));
        }
    };

    // For embeddings, create a simple user message with the text
    Ok(Input {
        system: None,
        messages: vec![InputMessage {
            role: Role::User,
            content: vec![InputMessageContent::Text(TextKind::Text { text })],
        }],
    })
}

/// Generate JSONL output file for successful responses
pub fn generate_output_jsonl(
    responses: &[(String, Value)], // (custom_id, response_body)
) -> Result<String, Error> {
    let mut lines = Vec::new();

    for (index, (custom_id, response_body)) in responses.iter().enumerate() {
        let response_item = OpenAIBatchResponseItem {
            id: format!("batch_req_{index}"),
            custom_id: custom_id.clone(),
            response: OpenAIBatchResponseBody {
                status_code: 200,
                request_id: format!("req_{}", uuid::Uuid::now_v7()),
                body: response_body.clone(),
            },
        };

        let line = serde_json::to_string(&response_item).map_err(|e| {
            Error::new(ErrorDetails::Serialization {
                message: format!("Failed to serialize response: {e}"),
            })
        })?;

        lines.push(line);
    }

    Ok(lines.join("\n"))
}

/// Generate JSONL error file for failed responses
pub fn generate_error_jsonl(
    errors: &[(String, String, String)], // (custom_id, error_code, error_message)
) -> Result<String, Error> {
    let mut lines = Vec::new();

    for (index, (custom_id, error_code, error_message)) in errors.iter().enumerate() {
        let error_item = OpenAIBatchErrorItem {
            id: format!("batch_req_{index}"),
            custom_id: custom_id.clone(),
            error: OpenAIBatchError {
                code: error_code.clone(),
                message: error_message.clone(),
            },
        };

        let line = serde_json::to_string(&error_item).map_err(|e| {
            Error::new(ErrorDetails::Serialization {
                message: format!("Failed to serialize error: {e}"),
            })
        })?;

        lines.push(line);
    }

    Ok(lines.join("\n"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_valid_jsonl() {
        let content = r#"{"custom_id": "req_1", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]}}
{"custom_id": "req_2", "method": "POST", "url": "/v1/embeddings", "body": {"model": "text-embedding-ada-002", "input": "Hello world"}}"#;

        let parsed = parse_jsonl_batch_input(content).unwrap();
        assert_eq!(parsed.total_requests, 2);
        assert_eq!(parsed.supported_requests, 2);
        assert_eq!(parsed.unsupported_requests.len(), 0);
    }

    #[test]
    fn test_parse_invalid_endpoint() {
        let content =
            r#"{"custom_id": "req_1", "method": "POST", "url": "/v1/unsupported", "body": {}}"#;

        let parsed = parse_jsonl_batch_input(content).unwrap();
        assert_eq!(parsed.total_requests, 1);
        assert_eq!(parsed.supported_requests, 0);
        assert_eq!(parsed.unsupported_requests.len(), 1);
    }

    #[test]
    fn test_validate_chat_completion() {
        let valid_body = serde_json::json!({
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}]
        });
        assert!(validate_chat_completion_body(&valid_body).is_ok());

        let invalid_body = serde_json::json!({
            "model": "gpt-4"
            // missing messages
        });
        assert!(validate_chat_completion_body(&invalid_body).is_err());
    }

    #[test]
    fn test_generate_output_jsonl() {
        let responses = vec![
            ("req_1".to_string(), serde_json::json!({"choices": []})),
            ("req_2".to_string(), serde_json::json!({"data": []})),
        ];

        let jsonl = generate_output_jsonl(&responses).unwrap();
        let lines: Vec<&str> = jsonl.lines().collect();
        assert_eq!(lines.len(), 2);

        // Each line should be valid JSON
        for line in lines {
            let _: OpenAIBatchResponseItem = serde_json::from_str(line).unwrap();
        }
    }
}
