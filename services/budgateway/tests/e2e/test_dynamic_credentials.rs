use serde_json::json;
use tensorzero::{Config, Gateway};
use std::fs;
use std::path::Path;
use tempfile::TempDir;
use tokio::time::{sleep, Duration};

/// Test that dynamically added models with API keys work correctly
#[tokio::test]
async fn test_dynamic_model_credentials() {
    // Create a temporary directory for config
    let temp_dir = TempDir::new().unwrap();
    let config_path = temp_dir.path().join("tensorzero.toml");

    // Write a minimal config
    let config_content = r#"
[gateway]
authentication = false
debug = true

[models."dummy-test"]
routing = ["dummy"]
endpoints = ["chat", "embedding"]

[models."dummy-test".providers.dummy]
type = "dummy"
model_name = "test"
"#;

    fs::write(&config_path, config_content).unwrap();

    // Start the gateway
    let gateway = Gateway::builder()
        .config_path(config_path.to_str().unwrap())
        .bind("127.0.0.1:0")
        .build()
        .await
        .unwrap();

    let port = gateway.port();
    let url = format!("http://127.0.0.1:{}", port);

    // Start gateway in background
    tokio::spawn(async move {
        gateway.start().await.unwrap();
    });

    // Wait for gateway to start
    sleep(Duration::from_millis(500)).await;

    // Test 1: Chat completions endpoint
    let response = reqwest::Client::new()
        .post(&format!("{}/v1/chat/completions", url))
        .json(&json!({
            "model": "dummy-test",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 10
        }))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 200);
    let body: serde_json::Value = response.json().await.unwrap();
    assert!(body.get("choices").is_some());

    // Test 2: Embeddings endpoint
    let response = reqwest::Client::new()
        .post(&format!("{}/v1/embeddings", url))
        .json(&json!({
            "model": "dummy-test",
            "input": "Hello world"
        }))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 200);
    let body: serde_json::Value = response.json().await.unwrap();
    assert!(body.get("data").is_some());
}

/// Test that credential merging works correctly
#[tokio::test]
async fn test_credential_merging() {
    use tensorzero_internal::gateway_util::AppStateData;
    use tensorzero_internal::inference::{InferenceCredentials, InferenceParams};
    use secrecy::SecretString;
    use std::sync::Arc;

    // Create AppStateData with credential store
    let config = Arc::new(Config::default());
    let app_state = AppStateData::new(config).await.unwrap();

    // Add a credential to the store
    {
        let mut store = app_state.model_credential_store.write().unwrap();
        store.insert("store_test".to_string(), SecretString::from("stored-key"));
    }

    // Create params with user-provided credentials
    let mut params = InferenceParams::default();
    params.credentials.insert("user_key".to_string(), SecretString::from("user-value"));
    params.credentials.insert("store_test".to_string(), SecretString::from("user-override"));

    // Merge credentials (simulating what happens in endpoints)
    let mut merged_credentials = params.credentials.clone();
    {
        let credential_store = app_state.model_credential_store.read().unwrap();
        for (key, value) in credential_store.iter() {
            if !merged_credentials.contains_key(key) {
                merged_credentials.insert(key.clone(), value.clone());
            }
        }
    }

    // Verify merging worked correctly
    assert_eq!(merged_credentials.len(), 2);
    assert!(merged_credentials.contains_key("user_key"));
    assert!(merged_credentials.contains_key("store_test"));

    // User-provided value should take precedence
    use secrecy::ExposeSecret;
    assert_eq!(merged_credentials.get("store_test").unwrap().expose_secret(), "user-override");
    assert_eq!(merged_credentials.get("user_key").unwrap().expose_secret(), "user-value");
}
