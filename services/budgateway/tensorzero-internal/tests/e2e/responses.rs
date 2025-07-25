use std::collections::HashMap;

use reqwest::StatusCode;
use serde_json::{json, Value};

use crate::common::get_gateway_endpoint;

#[tokio::test]
async fn test_response_create_basic() {
    let client = reqwest::Client::new();

    let request_body = json!({
        "model": "gpt-4-responses",
        "input": "Hello, world!",
        "instructions": "Be helpful and friendly"
    });

    let response = client
        .post(get_gateway_endpoint("/openai/v1/responses"))
        .header("Authorization", "Bearer test-key")
        .json(&request_body)
        .send()
        .await
        .unwrap();

    // Since we don't have a real responses model configured, this should fail
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);

    let error_body: Value = response.json().await.unwrap();
    assert!(error_body["error"]["message"]
        .as_str()
        .unwrap()
        .contains("Model"));
}

#[tokio::test]
async fn test_response_create_with_tools() {
    let client = reqwest::Client::new();

    let tools = vec![json!({
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather in a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA"
                    }
                },
                "required": ["location"]
            }
        }
    })];

    let request_body = json!({
        "model": "gpt-4-responses",
        "input": "What's the weather like in New York?",
        "tools": tools,
        "tool_choice": "auto",
        "parallel_tool_calls": true
    });

    let response = client
        .post(get_gateway_endpoint("/openai/v1/responses"))
        .header("Authorization", "Bearer test-key")
        .json(&request_body)
        .send()
        .await
        .unwrap();

    // Since we don't have a real responses model configured, this should fail
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
}

#[tokio::test]
async fn test_response_create_streaming() {
    let client = reqwest::Client::new();

    let request_body = json!({
        "model": "gpt-4-responses",
        "input": "Tell me a story",
        "stream": true,
        "stream_options": {
            "include_usage": true
        }
    });

    let response = client
        .post(get_gateway_endpoint("/openai/v1/responses"))
        .header("Authorization", "Bearer test-key")
        .json(&request_body)
        .send()
        .await
        .unwrap();

    // Since we don't have a real responses model configured, this should fail
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
}

#[tokio::test]
async fn test_response_create_multimodal() {
    let client = reqwest::Client::new();

    let request_body = json!({
        "model": "gpt-4o-responses",
        "input": [
            {
                "type": "text",
                "text": "What's in this image?"
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
                }
            }
        ],
        "modalities": ["text", "image"]
    });

    let response = client
        .post(get_gateway_endpoint("/openai/v1/responses"))
        .header("Authorization", "Bearer test-key")
        .json(&request_body)
        .send()
        .await
        .unwrap();

    // Since we don't have a real responses model configured, this should fail
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
}

#[tokio::test]
async fn test_response_retrieve() {
    let client = reqwest::Client::new();

    let response = client
        .get(get_gateway_endpoint("/openai/v1/responses/resp_123"))
        .header("Authorization", "Bearer test-key")
        .send()
        .await
        .unwrap();

    // This should return an error since retrieval is not supported
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);

    let error_body: Value = response.json().await.unwrap();
    assert!(error_body["error"]["message"]
        .as_str()
        .unwrap()
        .contains("Response retrieval is not supported"));
}

#[tokio::test]
async fn test_response_delete() {
    let client = reqwest::Client::new();

    let response = client
        .delete(get_gateway_endpoint("/openai/v1/responses/resp_123"))
        .header("Authorization", "Bearer test-key")
        .send()
        .await
        .unwrap();

    // This should return an error since deletion is not supported
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);

    let error_body: Value = response.json().await.unwrap();
    assert!(error_body["error"]["message"]
        .as_str()
        .unwrap()
        .contains("Response deletion is not supported"));
}

#[tokio::test]
async fn test_response_cancel() {
    let client = reqwest::Client::new();

    let response = client
        .post(get_gateway_endpoint("/openai/v1/responses/resp_123/cancel"))
        .header("Authorization", "Bearer test-key")
        .send()
        .await
        .unwrap();

    // This should return an error since cancellation is not supported
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);

    let error_body: Value = response.json().await.unwrap();
    assert!(error_body["error"]["message"]
        .as_str()
        .unwrap()
        .contains("Response cancellation is not supported"));
}

#[tokio::test]
async fn test_response_input_items() {
    let client = reqwest::Client::new();

    let response = client
        .get(get_gateway_endpoint(
            "/openai/v1/responses/resp_123/input_items",
        ))
        .header("Authorization", "Bearer test-key")
        .send()
        .await
        .unwrap();

    // This should return an error since input items listing is not supported
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);

    let error_body: Value = response.json().await.unwrap();
    assert!(error_body["error"]["message"]
        .as_str()
        .unwrap()
        .contains("Input items listing is not supported"));
}

#[tokio::test]
async fn test_response_create_with_metadata() {
    let client = reqwest::Client::new();

    let mut metadata = HashMap::new();
    metadata.insert("user_id", json!("user_123"));
    metadata.insert("session_id", json!("session_456"));
    metadata.insert("custom_field", json!({"nested": "value"}));

    let request_body = json!({
        "model": "gpt-4-responses",
        "input": "Hello",
        "metadata": metadata,
        "user": "user_123"
    });

    let response = client
        .post(get_gateway_endpoint("/openai/v1/responses"))
        .header("Authorization", "Bearer test-key")
        .json(&request_body)
        .send()
        .await
        .unwrap();

    // Since we don't have a real responses model configured, this should fail
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
}

#[tokio::test]
async fn test_response_create_with_previous_response() {
    let client = reqwest::Client::new();

    let request_body = json!({
        "model": "gpt-4-responses",
        "input": "Continue the conversation",
        "previous_response_id": "resp_previous_123"
    });

    let response = client
        .post(get_gateway_endpoint("/openai/v1/responses"))
        .header("Authorization", "Bearer test-key")
        .json(&request_body)
        .send()
        .await
        .unwrap();

    // Since we don't have a real responses model configured, this should fail
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
}

#[tokio::test]
async fn test_response_create_with_reasoning() {
    let client = reqwest::Client::new();

    let request_body = json!({
        "model": "o1-responses",
        "input": "Solve this complex problem step by step",
        "reasoning": {
            "reasoning_effort": "high"
        },
        "temperature": 0.7,
        "max_output_tokens": 2000
    });

    let response = client
        .post(get_gateway_endpoint("/openai/v1/responses"))
        .header("Authorization", "Bearer test-key")
        .json(&request_body)
        .send()
        .await
        .unwrap();

    // Since we don't have a real responses model configured, this should fail
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
}

#[tokio::test]
async fn test_response_create_with_unknown_fields() {
    let client = reqwest::Client::new();

    let request_body = json!({
        "model": "gpt-4-responses",
        "input": "Test input",
        "custom_field": "custom_value",
        "another_unknown": 123
    });

    let response = client
        .post(get_gateway_endpoint("/openai/v1/responses"))
        .header("Authorization", "Bearer test-key")
        .json(&request_body)
        .send()
        .await
        .unwrap();

    // The gateway should accept unknown fields (with warnings) but still fail due to missing model
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
}

#[tokio::test]
#[cfg_attr(not(feature = "e2e_tests"), ignore = "test_dummy_only")]
async fn test_response_create_with_configured_dummy_model() {
    let client = reqwest::Client::new();

    let request_body = json!({
        "model": "dummy-responses",
        "input": "Hello from test!",
        "instructions": "This is a test with a configured dummy model"
    });

    let response = client
        .post(get_gateway_endpoint("/openai/v1/responses"))
        .header("Authorization", "Bearer test-key")
        .json(&request_body)
        .send()
        .await
        .unwrap();

    // With a properly configured dummy model, this should succeed
    assert_eq!(response.status(), StatusCode::OK);

    let response_body: Value = response.json().await.unwrap();

    // Verify response structure
    assert!(response_body["id"].is_string());
    assert_eq!(response_body["object"], "response");
    assert!(response_body["created_at"].is_number());
    assert_eq!(response_body["status"], "completed");

    // The dummy provider should return some output
    assert!(response_body["output"].is_array());
    assert!(!response_body["output"].as_array().unwrap().is_empty());

    // Verify usage information
    assert!(response_body["usage"].is_object());
    assert!(response_body["usage"]["input_tokens"].is_number());
    assert!(response_body["usage"]["output_tokens"].is_number());
    assert!(response_body["usage"]["total_tokens"].is_number());
}

#[tokio::test]
#[cfg_attr(not(feature = "e2e_tests"), ignore = "test_dummy_only")]
async fn test_response_operations_with_configured_model() {
    let client = reqwest::Client::new();

    // Create a response first
    let create_body = json!({
        "model": "dummy-responses",
        "input": "Test input for CRUD operations"
    });

    let create_response = client
        .post(get_gateway_endpoint("/openai/v1/responses"))
        .header("Authorization", "Bearer test-key")
        .json(&create_body)
        .send()
        .await
        .unwrap();

    assert_eq!(create_response.status(), StatusCode::OK);
    let created: Value = create_response.json().await.unwrap();
    let response_id = created["id"].as_str().unwrap();

    // Test retrieve with proper model header
    let retrieve_response = client
        .get(get_gateway_endpoint(&format!(
            "/openai/v1/responses/{response_id}"
        )))
        .header("Authorization", "Bearer test-key")
        .header("x-model-name", "dummy-responses")
        .send()
        .await
        .unwrap();

    // Dummy provider doesn't support retrieval, but it should return proper error
    assert_eq!(retrieve_response.status(), StatusCode::BAD_REQUEST);
    let error_body: Value = retrieve_response.json().await.unwrap();
    assert!(error_body["error"]["message"]
        .as_str()
        .unwrap()
        .contains("Response retrieval is not supported"));

    // Test without x-model-name header (should use default)
    let retrieve_no_header = client
        .get(get_gateway_endpoint(&format!(
            "/openai/v1/responses/{response_id}"
        )))
        .header("Authorization", "Bearer test-key")
        .send()
        .await
        .unwrap();

    // Should fail because default model "gpt-4-responses" doesn't exist
    assert_eq!(retrieve_no_header.status(), StatusCode::BAD_REQUEST);
    let error_body: Value = retrieve_no_header.json().await.unwrap();
    assert!(error_body["error"]["message"]
        .as_str()
        .unwrap()
        .contains("Model"));
}

#[tokio::test]
#[cfg_attr(not(feature = "e2e_tests"), ignore = "test_dummy_only")]
async fn test_response_streaming_with_dummy_model() {
    use futures::StreamExt;
    use reqwest_eventsource::{Event, EventSource};

    let client = reqwest::Client::new();

    let request_body = json!({
        "model": "dummy-responses",
        "input": "Stream this response",
        "stream": true
    });

    let request = client
        .post(get_gateway_endpoint("/openai/v1/responses"))
        .header("Authorization", "Bearer test-key")
        .json(&request_body);

    let mut event_source = EventSource::new(request).unwrap();
    let mut events_received = 0;
    let mut saw_done = false;

    while let Some(event) = event_source.next().await {
        match event {
            Ok(Event::Open) => {}
            Ok(Event::Message(message)) => {
                if message.data == "[DONE]" {
                    saw_done = true;
                    break;
                }

                let event_data: Value = serde_json::from_str(&message.data).unwrap();
                assert!(event_data["event_type"].is_string());
                events_received += 1;
            }
            Err(e) => panic!("Error in event stream: {e:?}"),
        }
    }

    assert!(events_received > 0, "Should have received some events");
    assert!(saw_done, "Should have received [DONE] event");
}
