use reqwest::Client;
use serde_json::json;

use crate::common::get_gateway_endpoint;

#[tokio::test]
async fn test_openai_compatible_moderation_single_text() {
    let client = Client::new();

    // Create test request
    let request_body = json!({
        "model": "moderation_model",
        "input": "This is a test message"
    });

    // Make request through the OpenAI-compatible endpoint
    let response = client
        .post(get_gateway_endpoint("/openai/v1/moderations"))
        .json(&request_body)
        .send()
        .await
        .unwrap();

    // Check response
    assert_eq!(response.status(), 200);
    let response_body: serde_json::Value = response.json().await.unwrap();

    assert!(response_body["id"].as_str().unwrap().starts_with("modr-"));
    assert_eq!(response_body["model"], "moderation_model");
    assert!(response_body["results"].is_array());
    let results = response_body["results"].as_array().unwrap();
    assert_eq!(results.len(), 1);

    let result = &results[0];
    assert!(result["flagged"].is_boolean());
    assert!(result["categories"].is_object());
    assert!(result["category_scores"].is_object());
}

#[tokio::test]
async fn test_openai_compatible_moderation_multiple_texts() {
    let client = Client::new();

    // Create test request with multiple inputs
    let request_body = json!({
        "model": "moderation_model",
        "input": ["First message", "Second message", "Third message"]
    });

    // Make request through the OpenAI-compatible endpoint
    let response = client
        .post(get_gateway_endpoint("/openai/v1/moderations"))
        .json(&request_body)
        .send()
        .await
        .unwrap();

    // Check response
    assert_eq!(response.status(), 200);
    let response_body: serde_json::Value = response.json().await.unwrap();

    assert!(response_body["id"].as_str().unwrap().starts_with("modr-"));
    assert_eq!(response_body["model"], "moderation_model");
    assert!(response_body["results"].is_array());
    let results = response_body["results"].as_array().unwrap();
    assert_eq!(results.len(), 3);

    // Check each result
    for result in results {
        assert!(result["flagged"].is_boolean());
        assert!(result["categories"].is_object());
        assert!(result["category_scores"].is_object());
    }
}

#[tokio::test]
async fn test_openai_compatible_moderation_model_not_found() {
    let client = Client::new();

    // Create test request with non-existent model
    let request_body = json!({
        "model": "non-existent-model",
        "input": "Test message"
    });

    // Make request through the OpenAI-compatible endpoint
    let response = client
        .post(get_gateway_endpoint("/openai/v1/moderations"))
        .json(&request_body)
        .send()
        .await
        .unwrap();

    // Should return an error because the model doesn't exist
    assert_eq!(response.status(), 404);
    let error_body: serde_json::Value = response.json().await.unwrap();
    assert!(error_body["error"]["message"]
        .as_str()
        .unwrap()
        .contains("not found"));
}

#[tokio::test]
async fn test_openai_compatible_moderation_model_no_moderation_capability() {
    let client = Client::new();

    // Create test request with a chat model (that doesn't support moderation)
    let request_body = json!({
        "model": "openai::gpt-4o-mini",
        "input": "Test message"
    });

    // Make request through the OpenAI-compatible endpoint
    let response = client
        .post(get_gateway_endpoint("/openai/v1/moderations"))
        .json(&request_body)
        .send()
        .await
        .unwrap();

    // Should return an error because the model doesn't support moderation
    assert_eq!(response.status(), 400);
    let error_body: serde_json::Value = response.json().await.unwrap();
    assert!(error_body["error"]["message"]
        .as_str()
        .unwrap()
        .contains("does not support endpoint 'moderation'"));
}

#[tokio::test]
async fn test_openai_compatible_moderation_empty_input() {
    let client = Client::new();

    // Create test request with empty input
    let request_body = json!({
        "model": "moderation_model",
        "input": []
    });

    // Make request through the OpenAI-compatible endpoint
    let response = client
        .post(get_gateway_endpoint("/openai/v1/moderations"))
        .json(&request_body)
        .send()
        .await
        .unwrap();

    // Should return 400 for empty input
    assert_eq!(response.status(), 400);
}
