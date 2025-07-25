#![expect(clippy::print_stdout)]

use axum::http::StatusCode;
use reqwest::{multipart, Client};
use serde_json::{json, Value};

use crate::common::get_gateway_endpoint;

/// Test the file upload endpoint
#[tokio::test]
async fn test_file_upload() {
    let client = Client::new();

    // Create a sample JSONL file content
    let jsonl_content = r#"{"custom_id": "req-1", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Hello"}]}}
{"custom_id": "req-2", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "World"}]}}"#;

    // Create multipart form
    let form = multipart::Form::new().text("purpose", "batch").part(
        "file",
        multipart::Part::bytes(jsonl_content.as_bytes().to_vec())
            .file_name("test_batch.jsonl")
            .mime_str("application/jsonl")
            .unwrap(),
    );

    let response = client
        .post(get_gateway_endpoint("/v1/files"))
        .multipart(form)
        .send()
        .await
        .unwrap();

    // Check response
    assert_eq!(response.status(), StatusCode::OK);
    let response_json: Value = response.json().await.unwrap();
    println!("File upload response: {response_json:?}");

    // Verify response structure
    assert_eq!(response_json["object"], "file");
    assert!(response_json["id"].as_str().unwrap().starts_with("file-"));
    assert_eq!(response_json["purpose"], "batch");
    assert!(response_json["bytes"].as_u64().unwrap() > 0);
    assert!(response_json["created_at"].as_u64().is_some());
    assert_eq!(response_json["filename"], "test_batch.jsonl");
}

/// Test file upload with missing file
#[tokio::test]
async fn test_file_upload_missing_file() {
    let client = Client::new();

    // Create multipart form without file
    let form = multipart::Form::new().text("purpose", "batch");

    let response = client
        .post(get_gateway_endpoint("/v1/files"))
        .multipart(form)
        .send()
        .await
        .unwrap();

    // Should fail with bad request
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    let error_json: Value = response.json().await.unwrap();
    println!("Error response for missing file: {error_json:?}");
    // Check both possible error formats
    let error_message = error_json["error"]["message"]
        .as_str()
        .or_else(|| error_json["error"].as_str())
        .unwrap();
    assert!(error_message.contains("Missing file field"));
}

/// Test file upload with invalid purpose
#[tokio::test]
async fn test_file_upload_invalid_purpose() {
    let client = Client::new();

    let jsonl_content = r#"{"custom_id": "req-1", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Hello"}]}}"#;

    let form = multipart::Form::new()
        .text("purpose", "invalid_purpose")
        .part(
            "file",
            multipart::Part::bytes(jsonl_content.as_bytes().to_vec())
                .file_name("test.jsonl")
                .mime_str("application/jsonl")
                .unwrap(),
        );

    let response = client
        .post(get_gateway_endpoint("/v1/files"))
        .multipart(form)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    let error_json: Value = response.json().await.unwrap();
    // Check both possible error formats
    let error_message = error_json["error"]["message"]
        .as_str()
        .or_else(|| error_json["error"].as_str())
        .unwrap();
    assert!(error_message.contains("Invalid purpose"));
}

/// Test file retrieve endpoint
#[tokio::test]
async fn test_file_retrieve() {
    let client = Client::new();
    let file_id = "file-abc123";

    let response = client
        .get(get_gateway_endpoint(&format!("/v1/files/{file_id}")))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let response_json: Value = response.json().await.unwrap();
    println!("File retrieve response: {response_json:?}");

    // Verify dummy response structure
    assert_eq!(response_json["id"], file_id);
    assert_eq!(response_json["object"], "file");
    assert_eq!(response_json["purpose"], "batch");
}

/// Test file content endpoint
#[tokio::test]
async fn test_file_content() {
    let client = Client::new();
    let file_id = "file-abc123";

    let response = client
        .get(get_gateway_endpoint(&format!(
            "/v1/files/{file_id}/content"
        )))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);

    // Check content type header
    assert_eq!(
        response.headers().get("content-type").unwrap(),
        "application/jsonl"
    );

    let content = response.text().await.unwrap();
    println!("File content: {content}");

    // Verify it's valid JSONL
    for line in content.lines() {
        if !line.trim().is_empty() {
            let _: Value = serde_json::from_str(line).expect("Invalid JSON line");
        }
    }
}

/// Test file delete endpoint
#[tokio::test]
async fn test_file_delete() {
    let client = Client::new();
    let file_id = "file-abc123";

    let response = client
        .delete(get_gateway_endpoint(&format!("/v1/files/{file_id}")))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let response_json: Value = response.json().await.unwrap();
    println!("File delete response: {response_json:?}");

    assert_eq!(response_json["id"], file_id);
    assert_eq!(response_json["object"], "file");
    assert_eq!(response_json["deleted"], true);
}

/// Test batch create endpoint
#[tokio::test]
async fn test_batch_create() {
    let client = Client::new();

    let payload = json!({
        "input_file_id": "file-abc123",
        "endpoint": "/v1/chat/completions",
        "completion_window": "24h",
        "metadata": {
            "test": "true"
        }
    });

    let response = client
        .post(get_gateway_endpoint("/v1/batches"))
        .json(&payload)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let response_json: Value = response.json().await.unwrap();
    println!("Batch create response: {response_json:?}");

    // Verify response structure
    assert!(response_json["id"].as_str().unwrap().starts_with("batch_"));
    assert_eq!(response_json["object"], "batch");
    assert_eq!(response_json["endpoint"], "/v1/chat/completions");
    assert_eq!(response_json["input_file_id"], "file-abc123");
    assert_eq!(response_json["status"], "validating");
    assert_eq!(response_json["completion_window"], "24h");
    assert_eq!(response_json["metadata"]["test"], "true");
}

/// Test batch create with missing input file
#[tokio::test]
async fn test_batch_create_missing_input_file() {
    let client = Client::new();

    let payload = json!({
        "endpoint": "/v1/chat/completions",
        "completion_window": "24h"
    });

    let response = client
        .post(get_gateway_endpoint("/v1/batches"))
        .json(&payload)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::UNPROCESSABLE_ENTITY);
    let error_json: Value = response.json().await.unwrap();
    // Axum's JSON deserialization error format
    assert!(error_json["error"]
        .as_str()
        .unwrap()
        .contains("missing field `input_file_id`"));
}

/// Test batch retrieve endpoint
#[tokio::test]
async fn test_batch_retrieve() {
    let client = Client::new();
    let batch_id = "batch_abc123";

    let response = client
        .get(get_gateway_endpoint(&format!("/v1/batches/{batch_id}")))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let response_json: Value = response.json().await.unwrap();
    println!("Batch retrieve response: {response_json:?}");

    assert_eq!(response_json["id"], batch_id);
    assert_eq!(response_json["object"], "batch");
    assert_eq!(response_json["status"], "completed");
}

/// Test batch list endpoint
#[tokio::test]
async fn test_batch_list() {
    let client = Client::new();

    let response = client
        .get(get_gateway_endpoint("/v1/batches"))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let response_json: Value = response.json().await.unwrap();
    println!("Batch list response: {response_json:?}");

    assert_eq!(response_json["object"], "list");
    assert!(response_json["data"].is_array());
}

/// Test batch list with pagination
#[tokio::test]
async fn test_batch_list_with_pagination() {
    let client = Client::new();

    let response = client
        .get(get_gateway_endpoint("/v1/batches?limit=10&after=batch_123"))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let response_json: Value = response.json().await.unwrap();

    assert_eq!(response_json["object"], "list");
    assert!(response_json["data"].is_array());
    assert_eq!(response_json["has_more"], false);
}

/// Test batch cancel endpoint
#[tokio::test]
async fn test_batch_cancel() {
    let client = Client::new();
    let batch_id = "batch_abc123";

    let response = client
        .post(get_gateway_endpoint(&format!(
            "/v1/batches/{batch_id}/cancel"
        )))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let response_json: Value = response.json().await.unwrap();
    println!("Batch cancel response: {response_json:?}");

    assert_eq!(response_json["id"], batch_id);
    assert_eq!(response_json["object"], "batch");
    assert_eq!(response_json["status"], "cancelled");
}

/// Test file upload with oversized file
#[tokio::test]
async fn test_file_upload_oversized() {
    let client = Client::new();

    // Create a file that's too large (over 100MB)
    let large_content = "x".repeat(101 * 1024 * 1024);

    let form = multipart::Form::new().text("purpose", "batch").part(
        "file",
        multipart::Part::bytes(large_content.into_bytes())
            .file_name("large.jsonl")
            .mime_str("application/jsonl")
            .unwrap(),
    );

    let response = client
        .post(get_gateway_endpoint("/v1/files"))
        .multipart(form)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    let error_json: Value = response.json().await.unwrap();
    // Check both possible error formats
    let error_message = error_json["error"]["message"]
        .as_str()
        .or_else(|| error_json["error"].as_str())
        .unwrap();
    assert!(error_message.contains("File too large"));
}

/// Test batch create with invalid endpoint
#[tokio::test]
async fn test_batch_create_invalid_endpoint() {
    let client = Client::new();

    let payload = json!({
        "input_file_id": "file-abc123",
        "endpoint": "/v1/invalid/endpoint",
        "completion_window": "24h"
    });

    let response = client
        .post(get_gateway_endpoint("/v1/batches"))
        .json(&payload)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    let error_json: Value = response.json().await.unwrap();
    // Check both possible error formats
    let error_message = error_json["error"]["message"]
        .as_str()
        .or_else(|| error_json["error"].as_str())
        .unwrap();
    assert!(error_message.contains("Unsupported endpoint"));
}

/// Test file upload with invalid JSONL
#[tokio::test]
async fn test_file_upload_invalid_jsonl() {
    let client = Client::new();

    // Invalid JSONL content (missing closing brace)
    let invalid_jsonl = r#"{"custom_id": "req-1", "method": "POST"
not valid json"#;

    let form = multipart::Form::new().text("purpose", "batch").part(
        "file",
        multipart::Part::bytes(invalid_jsonl.as_bytes().to_vec())
            .file_name("invalid.jsonl")
            .mime_str("application/jsonl")
            .unwrap(),
    );

    let response = client
        .post(get_gateway_endpoint("/v1/files"))
        .multipart(form)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    let error_json: Value = response.json().await.unwrap();
    // Check both possible error formats
    let error_message = error_json["error"]["message"]
        .as_str()
        .or_else(|| error_json["error"].as_str())
        .unwrap();
    assert!(error_message.contains("Invalid JSONL"));
}

// TODO: Add authentication tests once the test infrastructure supports it
// Currently, authentication testing requires special test setup that's not
// available in the standard e2e test environment.

/// Test concurrent batch operations
#[tokio::test]
async fn test_concurrent_batch_operations() {
    let client = Client::new();

    // Create multiple batches concurrently
    let mut handles = vec![];

    for i in 0..5 {
        let client = client.clone();
        let handle = tokio::spawn(async move {
            let payload = json!({
                "input_file_id": format!("file-{}", i),
                "endpoint": "/v1/chat/completions",
                "completion_window": "24h",
                "metadata": {
                    "batch_number": i
                }
            });

            let response = client
                .post(get_gateway_endpoint("/v1/batches"))
                .json(&payload)
                .send()
                .await
                .unwrap();

            assert_eq!(response.status(), StatusCode::OK);
            response.json::<Value>().await.unwrap()
        });
        handles.push(handle);
    }

    // Wait for all requests to complete
    let mut results = Vec::new();
    for handle in handles {
        results.push(handle.await.unwrap());
    }

    // Verify all batches were created
    assert_eq!(results.len(), 5);
    for result in results.iter() {
        assert!(result["id"].as_str().unwrap().starts_with("batch_"));
        // Check that metadata exists and has batch_number field
        assert!(result["metadata"].is_object());
        assert!(result["metadata"]["batch_number"].is_number());
    }
}

/// Test batch list filtering
#[tokio::test]
async fn test_batch_list_filtering() {
    let client = Client::new();

    // Test with specific query parameters
    let response = client
        .get(get_gateway_endpoint("/v1/batches?limit=5"))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let response_json: Value = response.json().await.unwrap();
    assert_eq!(response_json["object"], "list");
}

/// Test file operations error handling
#[tokio::test]
async fn test_file_operations_error_handling() {
    let client = Client::new();

    // Test retrieving non-existent file
    let response = client
        .get(get_gateway_endpoint("/v1/files/nonexistent"))
        .send()
        .await
        .unwrap();

    // DummyProvider returns OK with dummy data for any file ID
    assert_eq!(response.status(), StatusCode::OK);

    // Test deleting file
    let response = client
        .delete(get_gateway_endpoint("/v1/files/file-to-delete"))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let response_json: Value = response.json().await.unwrap();
    assert_eq!(response_json["deleted"], true);
}
