#![expect(clippy::print_stdout)]

use std::collections::HashSet;

use axum::{extract::State, http::HeaderMap};
use reqwest::{Client, StatusCode};
use serde_json::{json, Value};
use uuid::Uuid;

use crate::{common::get_gateway_endpoint, providers::common::make_embedded_gateway_no_config};
use tensorzero_internal::{
    clickhouse::test_helpers::{
        get_clickhouse, select_chat_inference_clickhouse, select_json_inference_clickhouse,
        select_model_inference_clickhouse,
    },
    gateway_util::StructuredJson,
};

#[tokio::test]
async fn test_openai_compatible_route() {
    // Test that both the old and new formats work.
    test_openai_compatible_route_with_function_name_asmodel(
        "tensorzero::function_name::basic_test_no_system_schema",
    )
    .await;
    test_openai_compatible_route_with_function_name_asmodel(
        "tensorzero::basic_test_no_system_schema",
    )
    .await;
}

async fn test_openai_compatible_route_with_function_name_asmodel(model: &str) {
    let client = Client::new();
    let episode_id = Uuid::now_v7();

    let payload = json!({
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "TensorBot"
            },
            {
                "role": "user",
                "content": "What is the capital of Japan?"
            }
        ],
        "stream": false,
    });

    let response = client
        .post(get_gateway_endpoint("/v1/chat/completions"))
        .header("episode_id", episode_id.to_string())
        .json(&payload)
        .send()
        .await
        .unwrap();

    // Check Response is OK, then fields in order
    assert_eq!(response.status(), StatusCode::OK);
    let response_json = response.json::<Value>().await.unwrap();
    println!("response: {response_json:?}");
    let choices = response_json.get("choices").unwrap().as_array().unwrap();
    assert!(choices.len() == 1);
    let choice = choices.first().unwrap();
    assert_eq!(choice.get("index").unwrap().as_u64().unwrap(), 0);
    let message = choice.get("message").unwrap();
    assert_eq!(message.get("role").unwrap().as_str().unwrap(), "assistant");
    let content = message.get("content").unwrap().as_str().unwrap();
    assert_eq!(content, "Megumin gleefully chanted her spell, unleashing a thunderous explosion that lit up the sky and left a massive crater in its wake.");
    let finish_reason = choice.get("finish_reason").unwrap().as_str().unwrap();
    assert_eq!(finish_reason, "stop");
    let response_model = response_json.get("model").unwrap().as_str().unwrap();
    assert_eq!(
        response_model,
        "tensorzero::function_name::basic_test_no_system_schema::variant_name::test"
    );

    let inference_id: Uuid = response_json
        .get("id")
        .unwrap()
        .as_str()
        .unwrap()
        .parse()
        .unwrap();

    // Sleep for 1 second to allow time for data to be inserted into ClickHouse (trailing writes from API)
    tokio::time::sleep(std::time::Duration::from_secs(1)).await;

    // Check ClickHouse
    let clickhouse = get_clickhouse().await;

    // First, check Inference table
    let result = select_chat_inference_clickhouse(&clickhouse, inference_id)
        .await
        .unwrap();
    let id = result.get("id").unwrap().as_str().unwrap();
    let id_uuid = Uuid::parse_str(id).unwrap();
    assert_eq!(id_uuid, inference_id);
    let function_name = result.get("function_name").unwrap().as_str().unwrap();
    assert_eq!(function_name, "basic_test_no_system_schema");
    let input: Value =
        serde_json::from_str(result.get("input").unwrap().as_str().unwrap()).unwrap();
    let correct_input = json!({
        "system": "TensorBot",
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "value": "What is the capital of Japan?"}]
            }
        ]
    });
    assert_eq!(input, correct_input);
    let content_blocks = result.get("output").unwrap().as_str().unwrap();
    // Check that content_blocks is a list of blocks length 1
    let content_blocks: Vec<Value> = serde_json::from_str(content_blocks).unwrap();
    assert_eq!(content_blocks.len(), 1);
    let content_block = content_blocks.first().unwrap();
    // Check the type and content in the block
    let content_block_type = content_block.get("type").unwrap().as_str().unwrap();
    assert_eq!(content_block_type, "text");
    let clickhouse_content = content_block.get("text").unwrap().as_str().unwrap();
    assert_eq!(clickhouse_content, content);
    // Check that episode_id is here and correct
    let retrieved_episode_id = result.get("episode_id").unwrap().as_str().unwrap();
    let retrieved_episode_id = Uuid::parse_str(retrieved_episode_id).unwrap();
    assert_eq!(retrieved_episode_id, episode_id);
    // Check the variant name
    let variant_name = result.get("variant_name").unwrap().as_str().unwrap();
    assert_eq!(variant_name, "test");
    // Check the processing time
    let _processing_time_ms = result.get("processing_time_ms").unwrap().as_u64().unwrap();

    // Check the ModelInference Table
    let result = select_model_inference_clickhouse(&clickhouse, inference_id)
        .await
        .unwrap();
    println!("ModelInference result: {result:?}");
    let inference_id_result = result.get("inference_id").unwrap().as_str().unwrap();
    let inference_id_result = Uuid::parse_str(inference_id_result).unwrap();
    assert_eq!(inference_id_result, inference_id);
    let model_name = result.get("model_name").unwrap().as_str().unwrap();
    assert_eq!(model_name, "test");
    let model_provider_name = result.get("model_provider_name").unwrap().as_str().unwrap();
    assert_eq!(model_provider_name, "good");
    let raw_request = result.get("raw_request").unwrap().as_str().unwrap();
    assert_eq!(raw_request, "raw request");
    let input_tokens = result.get("input_tokens").unwrap().as_u64().unwrap();
    assert!(input_tokens > 5);
    let output_tokens = result.get("output_tokens").unwrap().as_u64().unwrap();
    assert!(output_tokens > 5);
    let response_time_ms = result.get("response_time_ms").unwrap().as_u64().unwrap();
    assert!(response_time_ms > 0);
    assert!(result.get("ttft_ms").unwrap().is_null());
    let raw_response = result.get("raw_response").unwrap().as_str().unwrap();
    let _raw_response_json: Value = serde_json::from_str(raw_response).unwrap();
    let finish_reason = result.get("finish_reason").unwrap().as_str().unwrap();
    assert_eq!(finish_reason, "stop");
}

#[tokio::test]
async fn test_openai_compatible_matches_response_fields() {
    let client = Client::new();

    let tensorzero_payload = json!({
        "model": "tensorzero::model_name::openai::gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": "What is the capital of Japan?"
            }
        ],
    });

    let openai_payload = json!({
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": "What is the capital of Japan?"
            }
        ],
    });

    let tensorzero_response_fut = client
        .post(get_gateway_endpoint("/v1/chat/completions"))
        .json(&tensorzero_payload)
        .send();

    let openai_response_fut = client
        .post("https://api.openai.com/v1/chat/completions")
        .bearer_auth(std::env::var("OPENAI_API_KEY").unwrap())
        .json(&openai_payload)
        .send();

    let (tensorzero_response, openai_response) =
        tokio::try_join!(tensorzero_response_fut, openai_response_fut).unwrap();

    assert_eq!(
        tensorzero_response.status(),
        StatusCode::OK,
        "TensorZero request failed"
    );
    assert_eq!(
        openai_response.status(),
        StatusCode::OK,
        "OpenAI request failed"
    );

    let openai_json: serde_json::Value = openai_response.json().await.unwrap();
    let tensorzero_json: serde_json::Value = tensorzero_response.json().await.unwrap();

    let openai_keys: HashSet<_> = openai_json.as_object().unwrap().keys().collect();
    let tensorzero_keys: HashSet<_> = tensorzero_json.as_object().unwrap().keys().collect();

    let missing_keys: Vec<_> = openai_keys.difference(&tensorzero_keys).collect();
    assert!(
        missing_keys.is_empty(),
        "Missing keys in TensorZero response: {missing_keys:?}"
    );
}

#[tokio::test]
async fn test_openai_compatible_dryrun() {
    let client = Client::new();
    let episode_id = Uuid::now_v7();

    let payload = json!({
        "model": "tensorzero::model_name::json",
        "messages": [
            {
                "role": "system",
                "content": "TensorBot"
            },
            {
                "role": "user",
                "content": "What is the capital of Japan?"
            }
        ],
        "stream": false,
        "tensorzero::episode_id": episode_id.to_string(),
        "tensorzero::dryrun": true
    });

    let response = client
        .post(get_gateway_endpoint("/v1/chat/completions"))
        .json(&payload)
        .send()
        .await
        .unwrap();
    // Check Response is OK, then fields in order
    assert_eq!(response.status(), StatusCode::OK);
    let response_json = response.json::<Value>().await.unwrap();
    println!("response_json: {response_json:?}");
    let choices = response_json.get("choices").unwrap().as_array().unwrap();
    assert!(choices.len() == 1);
    let choice = choices.first().unwrap();
    assert_eq!(choice.get("index").unwrap().as_u64().unwrap(), 0);
    let message = choice.get("message").unwrap();
    assert_eq!(message.get("role").unwrap().as_str().unwrap(), "assistant");
    let content = message.get("content").unwrap().as_str().unwrap();
    assert_eq!(content, "{\"answer\":\"Hello\"}");
    let finish_reason = choice.get("finish_reason").unwrap().as_str().unwrap();
    assert_eq!(finish_reason, "stop");
    let response_model = response_json.get("model").unwrap().as_str().unwrap();
    assert_eq!(response_model, "tensorzero::model_name::json");

    let inference_id: Uuid = response_json
        .get("id")
        .unwrap()
        .as_str()
        .unwrap()
        .parse()
        .unwrap();

    // Sleep for 1 second to allow time for data to be inserted into ClickHouse (trailing writes from API)
    tokio::time::sleep(std::time::Duration::from_secs(1)).await;

    // Check ClickHouse
    let clickhouse = get_clickhouse().await;

    let chat_result = select_chat_inference_clickhouse(&clickhouse, inference_id).await;
    let json_result = select_json_inference_clickhouse(&clickhouse, inference_id).await;
    // No inference should be written to ClickHouse when dryrun is true
    assert!(chat_result.is_none());
    assert!(json_result.is_none());
}

#[tokio::test]
async fn test_openai_compatible_route_model_name_shorthand() {
    test_openai_compatible_route_with_default_function("tensorzero::model_name::dummy::good", "Megumin gleefully chanted her spell, unleashing a thunderous explosion that lit up the sky and left a massive crater in its wake.").await;
}

#[tokio::test]
async fn test_openai_compatible_route_model_name_toml() {
    test_openai_compatible_route_with_default_function(
        "tensorzero::model_name::json",
        "{\"answer\":\"Hello\"}",
    )
    .await;
}

async fn test_openai_compatible_route_with_default_function(
    prefixed_model_name: &str,
    expected_content: &str,
) {
    let client = Client::new();
    let episode_id = Uuid::now_v7();

    let payload = json!({
        "model": prefixed_model_name,
        "messages": [
            {
                "role": "system",
                "content": "TensorBot"
            },
            {
                "role": "user",
                "content": "What is the capital of Japan?"
            }
        ],
        "stream": false,
    });

    let response = client
        .post(get_gateway_endpoint("/v1/chat/completions"))
        .header("episode_id", episode_id.to_string())
        .json(&payload)
        .send()
        .await
        .unwrap();
    // Check Response is OK, then fields in order
    assert_eq!(response.status(), StatusCode::OK);
    let response_json = response.json::<Value>().await.unwrap();
    println!("response_json: {response_json:?}");
    let choices = response_json.get("choices").unwrap().as_array().unwrap();
    assert!(choices.len() == 1);
    let choice = choices.first().unwrap();
    assert_eq!(choice.get("index").unwrap().as_u64().unwrap(), 0);
    let message = choice.get("message").unwrap();
    assert_eq!(message.get("role").unwrap().as_str().unwrap(), "assistant");
    let content = message.get("content").unwrap().as_str().unwrap();
    assert_eq!(content, expected_content);
    let finish_reason = choice.get("finish_reason").unwrap().as_str().unwrap();
    assert_eq!(finish_reason, "stop");
    let response_model = response_json.get("model").unwrap().as_str().unwrap();
    assert_eq!(response_model, prefixed_model_name);

    let inference_id: Uuid = response_json
        .get("id")
        .unwrap()
        .as_str()
        .unwrap()
        .parse()
        .unwrap();

    // Sleep for 1 second to allow time for data to be inserted into ClickHouse (trailing writes from API)
    tokio::time::sleep(std::time::Duration::from_secs(1)).await;

    // Check ClickHouse
    let clickhouse = get_clickhouse().await;

    // First, check Inference table
    let result = select_chat_inference_clickhouse(&clickhouse, inference_id)
        .await
        .unwrap();
    let id = result.get("id").unwrap().as_str().unwrap();
    let id_uuid = Uuid::parse_str(id).unwrap();
    assert_eq!(id_uuid, inference_id);
    let function_name = result.get("function_name").unwrap().as_str().unwrap();
    assert_eq!(function_name, "tensorzero::default");
    let input: Value =
        serde_json::from_str(result.get("input").unwrap().as_str().unwrap()).unwrap();
    let correct_input = json!({
        "system": "TensorBot",
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "value": "What is the capital of Japan?"}]
            }
        ]
    });
    assert_eq!(input, correct_input);
    let content_blocks = result.get("output").unwrap().as_str().unwrap();
    // Check that content_blocks is a list of blocks length 1
    let content_blocks: Vec<Value> = serde_json::from_str(content_blocks).unwrap();
    assert_eq!(content_blocks.len(), 1);
    let content_block = content_blocks.first().unwrap();
    // Check the type and content in the block
    let content_block_type = content_block.get("type").unwrap().as_str().unwrap();
    assert_eq!(content_block_type, "text");
    let clickhouse_content = content_block.get("text").unwrap().as_str().unwrap();
    assert_eq!(clickhouse_content, content);
    // Check that episode_id is here and correct
    let retrieved_episode_id = result.get("episode_id").unwrap().as_str().unwrap();
    let retrieved_episode_id = Uuid::parse_str(retrieved_episode_id).unwrap();
    assert_eq!(retrieved_episode_id, episode_id);
    // Check the processing time
    let _processing_time_ms = result.get("processing_time_ms").unwrap().as_u64().unwrap();

    // Check the ModelInference Table
    let result = select_model_inference_clickhouse(&clickhouse, inference_id)
        .await
        .unwrap();
    let inference_id_result = result.get("inference_id").unwrap().as_str().unwrap();
    let inference_id_result = Uuid::parse_str(inference_id_result).unwrap();
    assert_eq!(inference_id_result, inference_id);
    let model_name = result.get("model_name").unwrap().as_str().unwrap();
    assert_eq!(
        model_name,
        prefixed_model_name
            .strip_prefix("tensorzero::model_name::")
            .unwrap()
    );
    let raw_request = result.get("raw_request").unwrap().as_str().unwrap();
    assert_eq!(raw_request, "raw request");
    let input_tokens = result.get("input_tokens").unwrap().as_u64().unwrap();
    assert!(input_tokens > 5);
    let output_tokens = result.get("output_tokens").unwrap().as_u64().unwrap();
    assert!(output_tokens > 5);
    let response_time_ms = result.get("response_time_ms").unwrap().as_u64().unwrap();
    assert!(response_time_ms > 0);
    assert!(result.get("ttft_ms").unwrap().is_null());
    let raw_response = result.get("raw_response").unwrap().as_str().unwrap();
    let _raw_response_json: Value = serde_json::from_str(raw_response).unwrap();
    let finish_reason = result.get("finish_reason").unwrap().as_str().unwrap();
    assert_eq!(finish_reason, "stop");
}

#[tokio::test]
async fn test_openai_compatible_route_bad_model_name() {
    let client = Client::new();
    let episode_id = Uuid::now_v7();

    let payload = json!({
        "model": "tensorzero::model_name::my_missing_model",
        "messages": [
            {
                "role": "system",
                "content": "TensorBot"
            },
            {
                "role": "user",
                "content": "What is the capital of Japan?"
            }
        ],
        "stream": false,
    });

    let response = client
        .post(get_gateway_endpoint("/v1/chat/completions"))
        .header("episode_id", episode_id.to_string())
        .json(&payload)
        .send()
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    let response_json = response.json::<Value>().await.unwrap();
    assert_eq!(
        response_json,
        json!({
            "error": "Invalid inference target: Invalid model name: Model name 'my_missing_model' not found in model table"
        })
    )
}

#[tokio::test]
async fn test_openai_compatible_route_with_json_mode_on() {
    let client = Client::new();
    let episode_id = Uuid::now_v7();

    let payload = json!({
        "model": "tensorzero::function_name::basic_test_no_system_schema",
        "messages": [
            {
                "role": "system",
                "content": "TensorBot"
            },
            {
                "role": "user",
                "content": "What is the capital of Japan?"
            }
        ],
        "stream": false,
        "response_format":{"type":"json_object"}
    });

    let response = client
        .post(get_gateway_endpoint("/v1/chat/completions"))
        .header("episode_id", episode_id.to_string())
        .json(&payload)
        .send()
        .await
        .unwrap();
    // Check Response is OK, then fields in order
    assert_eq!(response.status(), StatusCode::OK);
    let response_json = response.json::<Value>().await.unwrap();
    let choices = response_json.get("choices").unwrap().as_array().unwrap();
    assert!(choices.len() == 1);
    let choice = choices.first().unwrap();
    assert_eq!(choice.get("index").unwrap().as_u64().unwrap(), 0);
    let message = choice.get("message").unwrap();
    assert_eq!(message.get("role").unwrap().as_str().unwrap(), "assistant");
    let content = message.get("content").unwrap().as_str().unwrap();
    assert_eq!(content, "Megumin gleefully chanted her spell, unleashing a thunderous explosion that lit up the sky and left a massive crater in its wake.");
    let response_model = response_json.get("model").unwrap().as_str().unwrap();
    assert_eq!(
        response_model,
        "tensorzero::function_name::basic_test_no_system_schema::variant_name::test"
    );

    let inference_id: Uuid = response_json
        .get("id")
        .unwrap()
        .as_str()
        .unwrap()
        .parse()
        .unwrap();

    // Sleep for 1 second to allow time for data to be inserted into ClickHouse (trailing writes from API)
    tokio::time::sleep(std::time::Duration::from_secs(1)).await;

    // Check ClickHouse
    let clickhouse = get_clickhouse().await;

    // First, check Inference table
    let result = select_chat_inference_clickhouse(&clickhouse, inference_id)
        .await
        .unwrap();
    let id = result.get("id").unwrap().as_str().unwrap();
    let id_uuid = Uuid::parse_str(id).unwrap();
    assert_eq!(id_uuid, inference_id);
    let function_name = result.get("function_name").unwrap().as_str().unwrap();
    assert_eq!(function_name, "basic_test_no_system_schema");
    let input: Value =
        serde_json::from_str(result.get("input").unwrap().as_str().unwrap()).unwrap();
    let correct_input = json!({
        "system": "TensorBot",
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "value": "What is the capital of Japan?"}]
            }
        ]
    });
    assert_eq!(input, correct_input);
    let content_blocks = result.get("output").unwrap().as_str().unwrap();
    // Check that content_blocks is a list of blocks length 1
    let content_blocks: Vec<Value> = serde_json::from_str(content_blocks).unwrap();
    assert_eq!(content_blocks.len(), 1);
    let content_block = content_blocks.first().unwrap();
    // Check the type and content in the block
    let content_block_type = content_block.get("type").unwrap().as_str().unwrap();
    assert_eq!(content_block_type, "text");
    let clickhouse_content = content_block.get("text").unwrap().as_str().unwrap();
    assert_eq!(clickhouse_content, content);
    // Check that episode_id is here and correct
    let retrieved_episode_id = result.get("episode_id").unwrap().as_str().unwrap();
    let retrieved_episode_id = Uuid::parse_str(retrieved_episode_id).unwrap();
    assert_eq!(retrieved_episode_id, episode_id);
    // Check the variant name
    let variant_name = result.get("variant_name").unwrap().as_str().unwrap();
    assert_eq!(variant_name, "test");
    // Check the processing time
    let _processing_time_ms = result.get("processing_time_ms").unwrap().as_u64().unwrap();
    let inference_params = result.get("inference_params").unwrap().as_str().unwrap();
    let inference_params: Value = serde_json::from_str(inference_params).unwrap();
    let clickhouse_json_mode = inference_params
        .get("chat_completion")
        .unwrap()
        .get("json_mode")
        .unwrap()
        .as_str()
        .unwrap();
    assert_eq!("on", clickhouse_json_mode);

    // Check the ModelInference Table
    let result = select_model_inference_clickhouse(&clickhouse, inference_id)
        .await
        .unwrap();
    let inference_id_result = result.get("inference_id").unwrap().as_str().unwrap();
    let inference_id_result = Uuid::parse_str(inference_id_result).unwrap();
    assert_eq!(inference_id_result, inference_id);
    let model_name = result.get("model_name").unwrap().as_str().unwrap();
    assert_eq!(model_name, "test");
    let model_provider_name = result.get("model_provider_name").unwrap().as_str().unwrap();
    assert_eq!(model_provider_name, "good");
    let raw_request = result.get("raw_request").unwrap().as_str().unwrap();
    assert_eq!(raw_request, "raw request");
    let input_tokens = result.get("input_tokens").unwrap().as_u64().unwrap();
    assert!(input_tokens > 5);
    let output_tokens = result.get("output_tokens").unwrap().as_u64().unwrap();
    assert!(output_tokens > 5);
    let response_time_ms = result.get("response_time_ms").unwrap().as_u64().unwrap();
    assert!(response_time_ms > 0);
    assert!(result.get("ttft_ms").unwrap().is_null());
    let raw_response = result.get("raw_response").unwrap().as_str().unwrap();
    let _raw_response_json: Value = serde_json::from_str(raw_response).unwrap();
}

#[tokio::test]
async fn test_openai_compatible_route_with_json_schema() {
    let client = Client::new();
    let episode_id = Uuid::now_v7();

    let payload = json!({
        "model": "tensorzero::function_name::basic_test_no_system_schema",
        "messages": [
            {
                "role": "system",
                "content": "TensorBot"
            },
            {
                "role": "user",
                "content": "What is the capital of Japan?"
            }
        ],
        "stream": false,
        "response_format":{"type":"json_schema", "json_schema":{"name":"test", "strict":true, "schema":{}}}
    });

    let response = client
        .post(get_gateway_endpoint("/v1/chat/completions"))
        .header("episode_id", episode_id.to_string())
        .json(&payload)
        .send()
        .await
        .unwrap();
    // Check Response is OK, then fields in order
    assert_eq!(response.status(), StatusCode::OK);
    let response_json = response.json::<Value>().await.unwrap();
    println!("response_json: {response_json:?}");
    let choices = response_json.get("choices").unwrap().as_array().unwrap();
    assert!(choices.len() == 1);
    let choice = choices.first().unwrap();
    assert_eq!(choice.get("index").unwrap().as_u64().unwrap(), 0);
    let message = choice.get("message").unwrap();
    assert_eq!(message.get("role").unwrap().as_str().unwrap(), "assistant");
    let content = message.get("content").unwrap().as_str().unwrap();
    assert_eq!(content, "Megumin gleefully chanted her spell, unleashing a thunderous explosion that lit up the sky and left a massive crater in its wake.");
    let finish_reason = choice.get("finish_reason").unwrap().as_str().unwrap();
    assert_eq!(finish_reason, "stop");
    let response_model = response_json.get("model").unwrap().as_str().unwrap();
    assert_eq!(
        response_model,
        "tensorzero::function_name::basic_test_no_system_schema::variant_name::test"
    );

    let inference_id: Uuid = response_json
        .get("id")
        .unwrap()
        .as_str()
        .unwrap()
        .parse()
        .unwrap();

    // Sleep for 1 second to allow time for data to be inserted into ClickHouse (trailing writes from API)
    tokio::time::sleep(std::time::Duration::from_secs(1)).await;

    // Check ClickHouse
    let clickhouse = get_clickhouse().await;

    // First, check Inference table
    let result = select_chat_inference_clickhouse(&clickhouse, inference_id)
        .await
        .unwrap();
    let id = result.get("id").unwrap().as_str().unwrap();
    let id_uuid = Uuid::parse_str(id).unwrap();
    assert_eq!(id_uuid, inference_id);
    let function_name = result.get("function_name").unwrap().as_str().unwrap();
    assert_eq!(function_name, "basic_test_no_system_schema");
    let input: Value =
        serde_json::from_str(result.get("input").unwrap().as_str().unwrap()).unwrap();
    let correct_input = json!({
        "system": "TensorBot",
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "value": "What is the capital of Japan?"}]
            }
        ]
    });
    assert_eq!(input, correct_input);
    let content_blocks = result.get("output").unwrap().as_str().unwrap();
    // Check that content_blocks is a list of blocks length 1
    let content_blocks: Vec<Value> = serde_json::from_str(content_blocks).unwrap();
    assert_eq!(content_blocks.len(), 1);
    let content_block = content_blocks.first().unwrap();
    // Check the type and content in the block
    let content_block_type = content_block.get("type").unwrap().as_str().unwrap();
    assert_eq!(content_block_type, "text");
    let clickhouse_content = content_block.get("text").unwrap().as_str().unwrap();
    assert_eq!(clickhouse_content, content);
    // Check that episode_id is here and correct
    let retrieved_episode_id = result.get("episode_id").unwrap().as_str().unwrap();
    let retrieved_episode_id = Uuid::parse_str(retrieved_episode_id).unwrap();
    assert_eq!(retrieved_episode_id, episode_id);
    // Check the variant name
    let variant_name = result.get("variant_name").unwrap().as_str().unwrap();
    assert_eq!(variant_name, "test");
    // Check the processing time
    let _processing_time_ms = result.get("processing_time_ms").unwrap().as_u64().unwrap();
    let inference_params = result.get("inference_params").unwrap().as_str().unwrap();
    let inference_params: Value = serde_json::from_str(inference_params).unwrap();
    let clickhouse_json_mode = inference_params
        .get("chat_completion")
        .unwrap()
        .get("json_mode")
        .unwrap()
        .as_str()
        .unwrap();
    assert_eq!("strict", clickhouse_json_mode);

    // Check the ModelInference Table
    let result = select_model_inference_clickhouse(&clickhouse, inference_id)
        .await
        .unwrap();
    let inference_id_result = result.get("inference_id").unwrap().as_str().unwrap();
    let inference_id_result = Uuid::parse_str(inference_id_result).unwrap();
    assert_eq!(inference_id_result, inference_id);
    let model_name = result.get("model_name").unwrap().as_str().unwrap();
    assert_eq!(model_name, "test");
    let model_provider_name = result.get("model_provider_name").unwrap().as_str().unwrap();
    assert_eq!(model_provider_name, "good");
    let raw_request = result.get("raw_request").unwrap().as_str().unwrap();
    assert_eq!(raw_request, "raw request");
    let input_tokens = result.get("input_tokens").unwrap().as_u64().unwrap();
    assert!(input_tokens > 5);
    let output_tokens = result.get("output_tokens").unwrap().as_u64().unwrap();
    assert!(output_tokens > 5);
    let response_time_ms = result.get("response_time_ms").unwrap().as_u64().unwrap();
    assert!(response_time_ms > 0);
    assert!(result.get("ttft_ms").unwrap().is_null());
    let raw_response = result.get("raw_response").unwrap().as_str().unwrap();
    let _raw_response_json: Value = serde_json::from_str(raw_response).unwrap();
}

#[tokio::test]
async fn test_openai_compatible_streaming_tool_call() {
    use futures::StreamExt;
    use reqwest_eventsource::{Event, RequestBuilderExt};

    let client = Client::new();
    let episode_id = Uuid::now_v7();
    let body = json!({
        "stream": true,
        "stream_options": {
            "include_usage": true
        },
        "model": "tensorzero::model_name::openai::gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": "What's the weather like in Boston today?"
            }
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_current_weather",
                    "description": "Get the current weather in a given location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city and state, e.g. San Francisco, CA"
                            },
                            "unit": {
                                "type": "string",
                                "enum": ["celsius", "fahrenheit"]
                            }
                        },
                        "required": ["location"]
                    }
                }
            }
        ],
        "tool_choice": "auto"
    });

    let mut response = client
        .post(get_gateway_endpoint("/v1/chat/completions"))
        .header("Content-Type", "application/json")
        .header("X-Episode-Id", episode_id.to_string())
        .json(&body)
        .eventsource()
        .unwrap();

    let mut chunks = vec![];
    let mut found_done_chunk = false;
    while let Some(event) = response.next().await {
        let event = event.unwrap();
        match event {
            Event::Open => continue,
            Event::Message(message) => {
                if message.data == "[DONE]" {
                    found_done_chunk = true;
                    break;
                }
                chunks.push(message.data);
            }
        }
    }
    assert!(found_done_chunk);
    let first_chunk = chunks.first().unwrap();
    let parsed_chunk: Value = serde_json::from_str(first_chunk).unwrap();
    assert_eq!(parsed_chunk["choices"][0]["index"].as_i64().unwrap(), 0);
    assert_eq!(
        parsed_chunk["choices"][0]["delta"]["role"]
            .as_str()
            .unwrap(),
        "assistant"
    );
    assert!(parsed_chunk["choices"][0]["delta"].get("content").is_none());
    println!("parsed_chunk: {parsed_chunk:?}");
    let tool_calls = parsed_chunk["choices"][0]["delta"]["tool_calls"]
        .as_array()
        .unwrap();
    assert_eq!(tool_calls.len(), 1);
    let tool_call = tool_calls[0].as_object().unwrap();
    assert_eq!(tool_call["index"].as_i64().unwrap(), 0);
    assert_eq!(
        tool_call["function"]["name"].as_str().unwrap(),
        "get_current_weather"
    );
    assert_eq!(tool_call["function"]["arguments"].as_str().unwrap(), "");
    for (i, chunk) in chunks.iter().enumerate() {
        let parsed_chunk: Value = serde_json::from_str(chunk).unwrap();
        if let Some(tool_calls) = parsed_chunk["choices"][0]["delta"]["tool_calls"].as_array() {
            for tool_call in tool_calls {
                let index = tool_call["index"].as_i64().unwrap();
                assert_eq!(index, 0);
            }
        }
        if let Some(finish_reason) = parsed_chunk["choices"][0]["delta"]["finish_reason"].as_str() {
            assert_eq!(finish_reason, "tool_calls");
            assert_eq!(i, chunks.len() - 2);
        }
        if i == chunks.len() - 2 {
            assert!(parsed_chunk["choices"][0]["delta"].get("content").is_none());
            assert!(parsed_chunk["choices"][0]["delta"]
                .get("tool_calls")
                .is_none());
        }
        if i == chunks.len() - 1 {
            let usage = parsed_chunk["usage"].as_object().unwrap();
            assert!(usage["prompt_tokens"].as_i64().unwrap() > 0);
            assert!(usage["completion_tokens"].as_i64().unwrap() > 0);
        }
        let response_model = parsed_chunk.get("model").unwrap().as_str().unwrap();
        assert_eq!(response_model, "tensorzero::model_name::openai::gpt-4o");
    }
}

#[tokio::test]
#[tracing_test::traced_test]
async fn test_openai_compatible_warn_unknown_fields() {
    let client = make_embedded_gateway_no_config().await;
    let state = client.get_app_state_data().unwrap().clone();
    tensorzero_internal::endpoints::openai_compatible::inference_handler(
        State(state),
        HeaderMap::default(),
        StructuredJson(
            serde_json::from_value(serde_json::json!({
                "messages": [],
                "model": "tensorzero::model_name::dummy::good",
                "my_fake_param": "fake_value"
            }))
            .unwrap(),
        ),
    )
    .await
    .unwrap();

    assert!(logs_contain(
        "Ignoring unknown fields in OpenAI-compatible request: [\"my_fake_param\"]"
    ));
}

#[tokio::test]
async fn test_openai_compatible_streaming() {
    use futures::StreamExt;
    use reqwest_eventsource::{Event, RequestBuilderExt};

    let client = Client::new();
    let episode_id = Uuid::now_v7();
    let body = json!({
        "stream": true,
        "model": "tensorzero::model_name::openai::gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": "What's the reason for why we use AC not DC?"
            }
        ]
    });

    let mut response = client
        .post(get_gateway_endpoint("/v1/chat/completions"))
        .header("Content-Type", "application/json")
        .header("X-Episode-Id", episode_id.to_string())
        .json(&body)
        .eventsource()
        .unwrap();

    let mut chunks = vec![];
    let mut found_done_chunk = false;
    while let Some(event) = response.next().await {
        let event = event.unwrap();
        match event {
            Event::Open => continue,
            Event::Message(message) => {
                if message.data == "[DONE]" {
                    found_done_chunk = true;
                    break;
                }
                chunks.push(message.data);
            }
        }
    }
    assert!(found_done_chunk);
    let first_chunk = chunks.first().unwrap();
    let parsed_chunk: Value = serde_json::from_str(first_chunk).unwrap();
    assert_eq!(parsed_chunk["choices"][0]["index"].as_i64().unwrap(), 0);
    assert_eq!(
        parsed_chunk["choices"][0]["delta"]["role"]
            .as_str()
            .unwrap(),
        "assistant"
    );
    let _content = parsed_chunk["choices"][0]["delta"]["content"]
        .as_str()
        .unwrap();
    assert!(parsed_chunk["choices"][0]["delta"]
        .get("tool_calls")
        .is_none());
    for (i, chunk) in chunks.iter().enumerate() {
        let parsed_chunk: Value = serde_json::from_str(chunk).unwrap();
        assert!(parsed_chunk["choices"][0]["delta"]
            .get("tool_calls")
            .is_none());
        if i < chunks.len() - 2 {
            let _content = parsed_chunk["choices"][0]["delta"]["content"]
                .as_str()
                .unwrap();
        }
        assert_eq!(parsed_chunk["service_tier"].as_str().unwrap(), "");
        assert!(parsed_chunk["choices"][0]["logprobs"].is_null());
        if let Some(finish_reason) = parsed_chunk["choices"][0]["delta"]["finish_reason"].as_str() {
            assert_eq!(finish_reason, "stop");
            assert_eq!(i, chunks.len() - 2);
        }

        let response_model = parsed_chunk.get("model").unwrap().as_str().unwrap();
        assert_eq!(response_model, "tensorzero::model_name::openai::gpt-4o");
    }
}

#[tokio::test]
async fn test_openai_compatible_logprobs_true_non_stream() {
    let client = Client::new();
    let episode_id = Uuid::now_v7();
    let body = json!({
        "model": "tensorzero::model_name::dummy::good",
        "messages": [
            {"role": "user", "content": "Who are you?"}
        ],
        "stream": false,
        "logprobs": true
    });

    let response = client
        .post(get_gateway_endpoint("/v1/chat/completions"))
        .header("Content-Type", "application/json")
        .header("X-Episode-Id", episode_id.to_string())
        .json(&body)
        .send()
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);

    // Basic sanity check on returned JSON
    let response_json: Value = response.json().await.unwrap();
    let choices = response_json["choices"].as_array().unwrap();
    assert!(!choices.is_empty());
}

#[tokio::test]
async fn test_openai_compatible_logprobs_true_stream() {
    use futures::StreamExt;
    use reqwest_eventsource::{Event, RequestBuilderExt};

    let client = Client::new();
    let episode_id = Uuid::now_v7();
    let body = json!({
        "model": "tensorzero::model_name::dummy::good",
        "messages": [
            {"role": "user", "content": "Say hi"}
        ],
        "stream": true,
        "logprobs": true
    });

    let mut response = client
        .post(get_gateway_endpoint("/v1/chat/completions"))
        .header("Content-Type", "application/json")
        .header("X-Episode-Id", episode_id.to_string())
        .json(&body)
        .eventsource()
        .unwrap();

    // Just ensure we can iterate until we get the DONE chunk without error.
    while let Some(event) = response.next().await {
        let event = event.unwrap();
        match event {
            Event::Open => continue,
            Event::Message(message) => {
                if message.data == "[DONE]" {
                    break;
                }
            }
        }
    }
}

#[tokio::test]
async fn test_openai_compatible_logprobs_false_should_work() {
    let client = Client::new();
    let episode_id = Uuid::now_v7();
    let body = json!({
        "model": "tensorzero::model_name::dummy::good",
        "messages": [
            {"role": "user", "content": "Who are you?"}
        ],
        "stream": false,
        "logprobs": false
    });

    let response = client
        .post(get_gateway_endpoint("/v1/chat/completions"))
        .header("Content-Type", "application/json")
        .header("X-Episode-Id", episode_id.to_string())
        .json(&body)
        .send()
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
}

#[tokio::test]
async fn test_openai_compatible_logprobs_numeric_should_error() {
    let client = Client::new();
    let episode_id = Uuid::now_v7();
    let body = json!({
        "model": "tensorzero::model_name::dummy::good",
        "messages": [
            {"role": "user", "content": "Who are you?"}
        ],
        "stream": false,
        "logprobs": 3
    });

    let response = client
        .post(get_gateway_endpoint("/v1/chat/completions"))
        .header("Content-Type", "application/json")
        .header("X-Episode-Id", episode_id.to_string())
        .json(&body)
        .send()
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
}

#[tokio::test]
async fn test_openai_compatible_embeddings_route() {
    let client = Client::new();

    // Test single string input
    let payload = json!({
        "model": "text-embedding-3-small",
        "input": "Hello, world! This is a test embedding."
    });

    let response = client
        .post(get_gateway_endpoint("/v1/embeddings"))
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);

    let response_json: Value = response.json().await.unwrap();

    // Verify OpenAI-compatible response format
    assert_eq!(response_json["object"], "list");
    assert_eq!(response_json["model"], "text-embedding-3-small");

    let data = response_json["data"].as_array().unwrap();
    assert_eq!(data.len(), 1);

    let embedding_data = &data[0];
    assert_eq!(embedding_data["object"], "embedding");
    assert_eq!(embedding_data["index"], 0);

    let embedding = embedding_data["embedding"].as_array().unwrap();
    assert!(!embedding.is_empty());
    assert_eq!(embedding.len(), 1536); // text-embedding-3-small has 1536 dimensions

    // Verify all values are numbers
    for value in embedding {
        assert!(value.is_f64());
    }

    let usage = &response_json["usage"];
    assert!(usage["prompt_tokens"].as_u64().unwrap() > 0);
    assert!(usage["total_tokens"].as_u64().unwrap() > 0);
    assert_eq!(usage["prompt_tokens"], usage["total_tokens"]); // For embeddings, total == prompt
}

#[tokio::test]
async fn test_openai_compatible_embeddings_route_with_model_prefix() {
    let client = Client::new();

    // Test with TensorZero model prefix
    let payload = json!({
        "model": "tensorzero::model_name::text-embedding-3-small",
        "input": "Test with model prefix"
    });

    let response = client
        .post(get_gateway_endpoint("/v1/embeddings"))
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);

    let response_json: Value = response.json().await.unwrap();

    // Should return the original model name without prefix
    assert_eq!(response_json["model"], "text-embedding-3-small");
    assert_eq!(response_json["object"], "list");

    let data = response_json["data"].as_array().unwrap();
    assert_eq!(data.len(), 1);
    assert_eq!(data[0]["object"], "embedding");
}

#[tokio::test]
async fn test_openai_compatible_embeddings_route_with_cache_options() {
    let client = Client::new();

    // Test with TensorZero cache options
    let payload = json!({
        "model": "text-embedding-3-small",
        "input": "Test with cache options",
        "tensorzero::cache_options": {
            "max_age_s": 3600,
            "enabled": "on"
        }
    });

    let response = client
        .post(get_gateway_endpoint("/v1/embeddings"))
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);

    let response_json: Value = response.json().await.unwrap();
    assert_eq!(response_json["object"], "list");
    assert_eq!(response_json["model"], "text-embedding-3-small");
}

#[tokio::test]
async fn test_openai_compatible_embeddings_route_invalid_model() {
    let client = Client::new();

    // Test with non-existent model
    let payload = json!({
        "model": "nonexistent-embedding-model",
        "input": "This should fail"
    });

    let response = client
        .post(get_gateway_endpoint("/v1/embeddings"))
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::BAD_REQUEST);

    let response_json: Value = response.json().await.unwrap();
    assert!(response_json["error"]["message"]
        .as_str()
        .unwrap()
        .contains("not found or does not support embeddings"));
}

#[tokio::test]
async fn test_openai_compatible_embeddings_route_batch_support() {
    let client = Client::new();

    // Test batch input (should now work)
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

    assert_eq!(response.status(), StatusCode::OK);

    let response_json: Value = response.json().await.unwrap();
    assert_eq!(response_json["object"], "list");
    assert_eq!(response_json["model"], "text-embedding-3-small");

    let data = response_json["data"].as_array().unwrap();
    assert_eq!(data.len(), 3); // Should have 3 embeddings for 3 inputs

    // Check that each embedding has the correct structure and index
    for (i, embedding_data) in data.iter().enumerate() {
        assert_eq!(embedding_data["object"], "embedding");
        assert_eq!(embedding_data["index"], i);

        let embedding = embedding_data["embedding"].as_array().unwrap();
        assert!(!embedding.is_empty());
        assert_eq!(embedding.len(), 1536); // text-embedding-3-small has 1536 dimensions

        // Verify all values are numbers
        for value in embedding {
            assert!(value.is_f64());
        }
    }

    let usage = &response_json["usage"];
    assert!(usage["prompt_tokens"].as_u64().unwrap() > 0);
    assert!(usage["total_tokens"].as_u64().unwrap() > 0);
    assert_eq!(usage["prompt_tokens"], usage["total_tokens"]); // For embeddings, total == prompt
}

#[tokio::test]
async fn test_openai_compatible_embeddings_route_empty_batch() {
    let client = Client::new();

    // Test empty batch input (should fail)
    let payload = json!({
        "model": "text-embedding-3-small",
        "input": []
    });

    let response = client
        .post(get_gateway_endpoint("/v1/embeddings"))
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::BAD_REQUEST);

    let response_json: Value = response.json().await.unwrap();
    assert!(response_json["error"]["message"]
        .as_str()
        .unwrap()
        .contains("Batch embedding requests cannot be empty"));
}

#[tokio::test]
async fn test_openai_compatible_embeddings_route_with_unknown_fields() {
    let client = Client::new();

    // Test with unknown OpenAI fields (should be ignored with warning)
    let payload = json!({
        "model": "text-embedding-3-small",
        "input": "Test with unknown fields",
        "encoding_format": "float",
        "dimensions": 1536,
        "user": "test-user"
    });

    let response = client
        .post(get_gateway_endpoint("/v1/embeddings"))
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await
        .unwrap();

    // Should succeed despite unknown fields
    assert_eq!(response.status(), StatusCode::OK);

    let response_json: Value = response.json().await.unwrap();
    assert_eq!(response_json["object"], "list");
    assert_eq!(response_json["model"], "text-embedding-3-small");
}

#[tokio::test]
async fn test_openai_compatible_embeddings_route_with_header_model() {
    let client = Client::new();

    // Test with x-tensorzero-original-model header
    let payload = json!({
        "model": "some-proxy-model-name",
        "input": "Test with header model override"
    });

    let response = client
        .post(get_gateway_endpoint("/v1/embeddings"))
        .header("Content-Type", "application/json")
        .header("x-tensorzero-original-model", "text-embedding-3-small")
        .json(&payload)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);

    let response_json: Value = response.json().await.unwrap();
    // Should use the model from header
    assert_eq!(response_json["model"], "text-embedding-3-small");
}

#[tokio::test]
async fn test_openai_compatible_image_generation() {
    let client = Client::new();

    // Test basic image generation with dummy provider
    let payload = json!({
        "model": "image-generation-test",
        "prompt": "A beautiful sunset over mountains",
        "n": 1,
        "size": "1024x1024",
        "response_format": "url"
    });

    let response = client
        .post(get_gateway_endpoint("/v1/images/generations"))
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);

    let response_json: Value = response.json().await.unwrap();

    // Verify response structure
    assert!(response_json["created"].is_u64());
    assert!(response_json["data"].is_array());
    assert_eq!(response_json["data"].as_array().unwrap().len(), 1);

    let image_data = &response_json["data"][0];
    assert!(image_data["url"].is_string() || image_data["b64_json"].is_string());

    // Test with multiple images
    let payload_multiple = json!({
        "model": "image-generation-test",
        "prompt": "Multiple views of a cityscape",
        "n": 2,
        "size": "512x512",
        "response_format": "b64_json"
    });

    let response_multiple = client
        .post(get_gateway_endpoint("/v1/images/generations"))
        .json(&payload_multiple)
        .send()
        .await
        .unwrap();

    assert_eq!(response_multiple.status(), StatusCode::OK);

    let response_multiple_json: Value = response_multiple.json().await.unwrap();
    assert_eq!(response_multiple_json["data"].as_array().unwrap().len(), 2);
}

#[tokio::test]
async fn test_openai_compatible_image_generation_with_together() {
    let client = Client::new();

    // Test Together provider with FLUX model
    let payload = json!({
        "model": "flux-schnell",
        "prompt": "A futuristic city with flying cars",
        "n": 1,
        "size": "1024x1024",
        "response_format": "url"
    });

    let response = client
        .post(get_gateway_endpoint("/v1/images/generations"))
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await
        .unwrap();

    // Since we don't have actual Together API key in tests, this should fail with auth error
    // But it validates that the routing works correctly
    assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);

    let error_json: Value = response.json().await.unwrap();
    assert!(error_json["error"].as_str().unwrap().contains("API key"));
}

#[tokio::test]
async fn test_openai_compatible_image_generation_errors() {
    let client = Client::new();

    // Test with non-existent model
    let payload = json!({
        "model": "non-existent-model",
        "prompt": "Test prompt",
        "n": 1,
        "size": "1024x1024"
    });

    let response = client
        .post(get_gateway_endpoint("/v1/images/generations"))
        .json(&payload)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::NOT_FOUND);

    // Test with model that doesn't support image generation
    let payload_wrong_capability = json!({
        "model": "gpt-4o-mini-2024-07-18",
        "prompt": "Test prompt",
        "n": 1,
        "size": "1024x1024"
    });

    let response_wrong_capability = client
        .post(get_gateway_endpoint("/v1/images/generations"))
        .json(&payload_wrong_capability)
        .send()
        .await
        .unwrap();

    assert_eq!(response_wrong_capability.status(), StatusCode::BAD_REQUEST);

    let error_json: Value = response_wrong_capability.json().await.unwrap();
    assert!(error_json["error"]
        .as_str()
        .unwrap()
        .contains("does not support"));

    // Test with invalid parameters
    let payload_invalid = json!({
        "model": "image-generation-test",
        "prompt": "Test prompt",
        "n": 11,  // Too many images
        "size": "1024x1024"
    });

    let response_invalid = client
        .post(get_gateway_endpoint("/v1/images/generations"))
        .json(&payload_invalid)
        .send()
        .await
        .unwrap();

    assert_eq!(response_invalid.status(), StatusCode::BAD_REQUEST);
}
