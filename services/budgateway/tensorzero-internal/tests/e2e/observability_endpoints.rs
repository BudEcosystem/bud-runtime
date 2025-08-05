#![expect(clippy::print_stdout)]

use std::time::Duration;

use reqwest::Client;
use serde_json::{json, Value};
use tokio::time::sleep;
use uuid::Uuid;

use crate::{common::get_gateway_endpoint, providers::common::make_embedded_gateway};
use tensorzero_internal::clickhouse::test_helpers::get_clickhouse;

// Helper function to select data from new observability tables
async fn select_embedding_inference_clickhouse(
    inference_id: Uuid,
) -> Result<Option<Value>, Box<dyn std::error::Error>> {
    let clickhouse = get_clickhouse().await;
    let query = format!(
        "SELECT * FROM EmbeddingInference WHERE id = '{}' FORMAT JSONEachRow",
        inference_id
    );
    let result = clickhouse.run_query_synchronous(query, None).await?;
    if result.trim().is_empty() {
        return Ok(None);
    }
    let json: Value = serde_json::from_str(result.trim())?;
    Ok(Some(json))
}

async fn select_audio_inference_clickhouse(
    inference_id: Uuid,
) -> Result<Option<Value>, Box<dyn std::error::Error>> {
    let clickhouse = get_clickhouse().await;
    let query = format!("SELECT * FROM AudioInference WHERE id = '{}' FORMAT JSONEachRow", inference_id);
    let result = clickhouse.run_query_synchronous(query, None).await?;
    if result.trim().is_empty() {
        return Ok(None);
    }
    let json: Value = serde_json::from_str(result.trim())?;
    Ok(Some(json))
}

async fn select_image_inference_clickhouse(
    inference_id: Uuid,
) -> Result<Option<Value>, Box<dyn std::error::Error>> {
    let clickhouse = get_clickhouse().await;
    let query = format!("SELECT * FROM ImageInference WHERE id = '{}' FORMAT JSONEachRow", inference_id);
    let result = clickhouse.run_query_synchronous(query, None).await?;
    if result.trim().is_empty() {
        return Ok(None);
    }
    let json: Value = serde_json::from_str(result.trim())?;
    Ok(Some(json))
}

async fn select_moderation_inference_clickhouse(
    inference_id: Uuid,
) -> Result<Option<Value>, Box<dyn std::error::Error>> {
    let clickhouse = get_clickhouse().await;
    let query = format!(
        "SELECT * FROM ModerationInference WHERE id = '{}' FORMAT JSONEachRow",
        inference_id
    );
    let result = clickhouse.run_query_synchronous(query, None).await?;
    if result.trim().is_empty() {
        return Ok(None);
    }
    let json: Value = serde_json::from_str(result.trim())?;
    Ok(Some(json))
}

async fn select_model_inference_by_endpoint_type(
    endpoint_type: &str,
) -> Result<Option<Value>, Box<dyn std::error::Error>> {
    let clickhouse = get_clickhouse().await;
    let query = format!(
        "SELECT * FROM ModelInference WHERE endpoint_type = '{}' ORDER BY id DESC LIMIT 1 FORMAT JSONEachRow",
        endpoint_type
    );
    let result = clickhouse.run_query_synchronous(query, None).await?;
    if result.trim().is_empty() {
        return Ok(None);
    }
    let json: Value = serde_json::from_str(result.trim())?;
    Ok(Some(json))
}

#[tokio::test]
async fn test_embedding_observability_clickhouse_write() {
    // Start the gateway in the background
    let _gateway_handle = make_embedded_gateway().await;

    let client = Client::new();

    // Make embedding request
    let payload = json!({
        "model": "text-embedding-3-small",
        "input": "Test embedding for observability"
    });

    let response = client
        .post(get_gateway_endpoint("/v1/embeddings"))
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 200);
    let response_body: Value = response.json().await.unwrap();

    // Wait a bit for async writes to complete
    sleep(Duration::from_millis(500)).await;

    // Check that ModelInference was written with correct endpoint_type
    let model_inference = select_model_inference_by_endpoint_type("embedding")
        .await
        .unwrap();
    assert!(model_inference.is_some(), "No ModelInference record found for embedding");
    let model_record = model_inference.unwrap();
    assert_eq!(model_record["endpoint_type"], "embedding");
    assert_eq!(model_record["model_name"], "text-embedding-3-small");

    // Extract inference_id to check EmbeddingInference table
    let inference_id_str = model_record["inference_id"].as_str().unwrap();
    let inference_id = Uuid::parse_str(inference_id_str).unwrap();

    // Check that EmbeddingInference was written
    let embedding_inference = select_embedding_inference_clickhouse(inference_id)
        .await
        .unwrap();
    assert!(embedding_inference.is_some(), "No EmbeddingInference record found");
    let embedding_record = embedding_inference.unwrap();
    assert_eq!(embedding_record["id"], inference_id_str);
    assert_eq!(embedding_record["function_name"], "text-embedding-3-small");
    assert!(embedding_record["embeddings"].as_str().unwrap().len() > 0);
    assert_eq!(embedding_record["input_count"], 1);

    println!("✅ Embedding observability test passed - data written to ClickHouse");
}

#[tokio::test]
async fn test_moderation_observability_clickhouse_write() {
    let _gateway_handle = make_embedded_gateway().await;

    let client = Client::new();

    // Make moderation request
    let payload = json!({
        "model": "moderation_model",
        "input": "This is a test message for moderation observability"
    });

    let response = client
        .post(get_gateway_endpoint("/openai/v1/moderations"))
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 200);
    let response_body: Value = response.json().await.unwrap();

    // Wait for async writes
    sleep(Duration::from_millis(500)).await;

    // Check ModelInference table
    let model_inference = select_model_inference_by_endpoint_type("moderation")
        .await
        .unwrap();
    assert!(model_inference.is_some(), "No ModelInference record found for moderation");
    let model_record = model_inference.unwrap();
    assert_eq!(model_record["endpoint_type"], "moderation");

    // Extract inference_id
    let inference_id_str = model_record["inference_id"].as_str().unwrap();
    let inference_id = Uuid::parse_str(inference_id_str).unwrap();

    // Check ModerationInference table
    let moderation_inference = select_moderation_inference_clickhouse(inference_id)
        .await
        .unwrap();
    assert!(moderation_inference.is_some(), "No ModerationInference record found");
    let moderation_record = moderation_inference.unwrap();
    assert_eq!(moderation_record["id"], inference_id_str);
    assert_eq!(moderation_record["function_name"], "moderation_model");
    assert!(moderation_record["input"]
        .as_str()
        .unwrap()
        .contains("test message"));
    assert!(moderation_record["flagged"].is_boolean());

    println!("✅ Moderation observability test passed - data written to ClickHouse");
}

#[tokio::test]
async fn test_image_generation_observability_clickhouse_write() {
    let _gateway_handle = make_embedded_gateway().await;

    let client = Client::new();

    // Make image generation request
    let payload = json!({
        "model": "dall-e-3",
        "prompt": "A beautiful sunset over mountains for observability testing",
        "n": 1,
        "size": "1024x1024"
    });

    let response = client
        .post(get_gateway_endpoint("/v1/images/generations"))
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 200);
    let response_body: Value = response.json().await.unwrap();

    // Wait for async writes
    sleep(Duration::from_millis(500)).await;

    // Check ModelInference table
    let model_inference = select_model_inference_by_endpoint_type("image_generation")
        .await
        .unwrap();
    assert!(model_inference.is_some(), "No ModelInference record found for image generation");
    let model_record = model_inference.unwrap();
    assert_eq!(model_record["endpoint_type"], "image_generation");

    // Extract inference_id
    let inference_id_str = model_record["inference_id"].as_str().unwrap();
    let inference_id = Uuid::parse_str(inference_id_str).unwrap();

    // Check ImageInference table
    let image_inference = select_image_inference_clickhouse(inference_id)
        .await
        .unwrap();
    assert!(image_inference.is_some(), "No ImageInference record found");
    let image_record = image_inference.unwrap();
    assert_eq!(image_record["id"], inference_id_str);
    assert_eq!(image_record["function_name"], "dall-e-3");
    assert!(image_record["prompt"].as_str().unwrap().contains("sunset"));
    assert_eq!(image_record["size"], "1024x1024");
    assert_eq!(image_record["image_count"], 1);

    println!("✅ Image generation observability test passed - data written to ClickHouse");
}

#[tokio::test]
async fn test_endpoint_type_differentiation_in_model_inference() {
    let _gateway_handle = make_embedded_gateway().await;

    let client = Client::new();

    // Make requests to different endpoints
    let embedding_payload = json!({
        "model": "text-embedding-3-small",
        "input": "Test for endpoint type differentiation"
    });

    let moderation_payload = json!({
        "model": "moderation_model",
        "input": "Test moderation content"
    });

    // Make both requests
    let embedding_response = client
        .post(get_gateway_endpoint("/v1/embeddings"))
        .header("Content-Type", "application/json")
        .json(&embedding_payload)
        .send()
        .await
        .unwrap();

    let moderation_response = client
        .post(get_gateway_endpoint("/openai/v1/moderations"))
        .header("Content-Type", "application/json")
        .json(&moderation_payload)
        .send()
        .await
        .unwrap();

    assert_eq!(embedding_response.status(), 200);
    assert_eq!(moderation_response.status(), 200);

    // Wait for async writes
    sleep(Duration::from_millis(1000)).await;

    // Check that we have records for both endpoint types
    let clickhouse = get_clickhouse().await;

    let endpoint_types_query = "SELECT DISTINCT endpoint_type, COUNT(*) as count FROM ModelInference GROUP BY endpoint_type FORMAT JSONEachRow";
    let result = clickhouse
        .run_query_synchronous(endpoint_types_query.to_string(), None)
        .await
        .unwrap();

    // Parse multiple JSON lines
    let rows: Vec<Value> = result
        .trim()
        .lines()
        .filter(|line| !line.is_empty())
        .map(|line| serde_json::from_str(line).unwrap())
        .collect();

    // Should have multiple endpoint types
    assert!(
        rows.len() >= 2,
        "Expected at least 2 different endpoint types"
    );

    // Check for specific endpoint types
    let endpoint_types: std::collections::HashSet<String> = rows
        .iter()
        .map(|row| row["endpoint_type"].as_str().unwrap().to_string())
        .collect();

    assert!(
        endpoint_types.contains("embedding"),
        "Missing embedding endpoint type"
    );
    assert!(
        endpoint_types.contains("moderation"),
        "Missing moderation endpoint type"
    );

    println!("✅ Endpoint type differentiation test passed - ModelInference correctly tracks endpoint types: {:?}", endpoint_types);
}

#[tokio::test]
async fn test_embedding_batch_observability() {
    let _gateway_handle = make_embedded_gateway().await;

    let client = Client::new();

    // Make batch embedding request
    let payload = json!({
        "model": "text-embedding-3-small",
        "input": ["First text", "Second text", "Third text"]
    });

    let response = client
        .post(get_gateway_endpoint("/v1/embeddings"))
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 200);
    let response_body: Value = response.json().await.unwrap();

    // Wait for async writes
    sleep(Duration::from_millis(500)).await;

    // Check that batch request is tracked correctly
    let model_inference = select_model_inference_by_endpoint_type("embedding")
        .await
        .unwrap();
    assert!(model_inference.is_some(), "No ModelInference record found for batch embedding");
    let model_record = model_inference.unwrap();
    let inference_id_str = model_record["inference_id"].as_str().unwrap();
    let inference_id = Uuid::parse_str(inference_id_str).unwrap();

    // Check EmbeddingInference table
    let embedding_inference = select_embedding_inference_clickhouse(inference_id)
        .await
        .unwrap();
    assert!(embedding_inference.is_some(), "No EmbeddingInference record found for batch");
    let embedding_record = embedding_inference.unwrap();
    assert_eq!(embedding_record["input_count"], 3); // Should reflect batch size

    println!("✅ Batch embedding observability test passed - batch size correctly tracked");
}

#[tokio::test]
async fn test_observability_tables_creation() {
    // Test that all new observability tables exist
    let clickhouse = get_clickhouse().await;

    let tables_to_check = vec![
        "EmbeddingInference",
        "AudioInference",
        "ImageInference",
        "ModerationInference",
    ];

    for table_name in tables_to_check {
        let query = format!(
            "SELECT 1 FROM system.tables WHERE database = '{}' AND name = '{}'",
            clickhouse.database(),
            table_name
        );

        let result = clickhouse.run_query_synchronous(query, None).await.unwrap();
        assert_eq!(result.trim(), "1", "Table {} does not exist", table_name);

        println!("✅ Table {} exists", table_name);
    }

    // Check that ModelInference has endpoint_type column
    let column_query = format!(
        "SELECT 1 FROM system.columns WHERE database = '{}' AND table = 'ModelInference' AND name = 'endpoint_type'",
        clickhouse.database()
    );

    let result = clickhouse
        .run_query_synchronous(column_query, None)
        .await
        .unwrap();
    assert_eq!(
        result.trim(),
        "1",
        "endpoint_type column not found in ModelInference"
    );

    println!("✅ ModelInference.endpoint_type column exists");
    println!("✅ All observability tables and columns are properly created");
}

#[tokio::test]
async fn test_observability_data_consistency() {
    let _gateway_handle = make_embedded_gateway().await;

    let client = Client::new();

    // Make an embedding request
    let payload = json!({
        "model": "text-embedding-3-small",
        "input": "Consistency test"
    });

    let response = client
        .post(get_gateway_endpoint("/v1/embeddings"))
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 200);

    // Wait for async writes
    sleep(Duration::from_millis(500)).await;

    // Get the latest embedding record
    let model_inference = select_model_inference_by_endpoint_type("embedding")
        .await
        .unwrap();
    assert!(model_inference.is_some());
    let model_record = model_inference.unwrap();
    let inference_id_str = model_record["inference_id"].as_str().unwrap();
    let inference_id = Uuid::parse_str(inference_id_str).unwrap();

    // Get corresponding EmbeddingInference record
    let embedding_inference = select_embedding_inference_clickhouse(inference_id)
        .await
        .unwrap();
    assert!(embedding_inference.is_some());
    let embedding_record = embedding_inference.unwrap();

    // Verify data consistency between tables
    assert_eq!(model_record["inference_id"], embedding_record["id"]);
    assert_eq!(
        model_record["model_name"],
        embedding_record["function_name"]
    );
    assert_eq!(model_record["endpoint_type"], "embedding");

    // Check that both records have valid timestamps
    assert!(model_record.get("timestamp").is_some());
    assert!(embedding_record.get("timestamp").is_some());

    println!("✅ Data consistency test passed - related records match across tables");
}
