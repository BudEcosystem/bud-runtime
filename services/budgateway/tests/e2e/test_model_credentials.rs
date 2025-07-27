use tensorzero_internal::gateway_util::AppStateData;
use tensorzero_internal::endpoints::inference::{InferenceCredentials, Params};
use tensorzero_internal::config_parser::Config;
use std::sync::Arc;
use std::collections::HashMap;
use secrecy::SecretString;
use serde_json::json;

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_model_credential_flow_e2e() {
        // Initialize app state
        let config = Arc::new(Config::default());
        let app_state = AppStateData::new(config.clone()).await.unwrap();

        // Step 1: Simulate adding a model with API key via Redis
        // (In real scenario, this would come from Redis pubsub)
        {
            let mut store = app_state.model_credential_store.write().unwrap();
            store.insert(
                "store_test-gpt4".to_string(),
                SecretString::from("sk-test-12345"),
            );
        }

        // Step 2: Create inference parameters with no user credentials
        let params = Params {
            model_name: Some("test-gpt4".to_string()),
            credentials: HashMap::new(),
            stream: Some(false),
            input: json!({"messages": [{"role": "user", "content": "Hello"}]}),
            ..Default::default()
        };

        // Step 3: Simulate credential merging (from inference function)
        let mut merged_credentials = params.credentials.clone();
        {
            let credential_store = app_state.model_credential_store.read().unwrap();
            for (key, value) in credential_store.iter() {
                if !merged_credentials.contains_key(key) {
                    merged_credentials.insert(key.clone(), value.clone());
                }
            }
        }

        // Step 4: Verify the credential is available
        assert!(merged_credentials.contains_key("store_test-gpt4"));
        assert_eq!(
            merged_credentials.get("store_test-gpt4").unwrap().expose_secret(),
            "sk-test-12345"
        );

        // Step 5: Test user override
        let mut params_with_override = Params {
            model_name: Some("test-gpt4".to_string()),
            credentials: HashMap::new(),
            stream: Some(false),
            input: json!({"messages": [{"role": "user", "content": "Hello"}]}),
            ..Default::default()
        };
        params_with_override.credentials.insert(
            "store_test-gpt4".to_string(),
            SecretString::from("sk-user-override"),
        );

        let mut merged_with_override = params_with_override.credentials.clone();
        {
            let credential_store = app_state.model_credential_store.read().unwrap();
            for (key, value) in credential_store.iter() {
                if !merged_with_override.contains_key(key) {
                    merged_with_override.insert(key.clone(), value.clone());
                }
            }
        }

        // Verify user credential takes precedence
        assert_eq!(
            merged_with_override.get("store_test-gpt4").unwrap().expose_secret(),
            "sk-user-override"
        );

        // Step 6: Test model deletion
        app_state.remove_model_table("test-gpt4").await;

        // Verify credential was removed
        {
            let store = app_state.model_credential_store.read().unwrap();
            assert!(!store.contains_key("store_test-gpt4"));
        }
    }

    #[tokio::test]
    async fn test_multiple_models_with_different_keys() {
        let config = Arc::new(Config::default());
        let app_state = AppStateData::new(config).await.unwrap();

        // Add multiple models with different API keys
        {
            let mut store = app_state.model_credential_store.write().unwrap();
            store.insert(
                "store_openai-model".to_string(),
                SecretString::from("sk-openai-key"),
            );
            store.insert(
                "store_anthropic-model".to_string(),
                SecretString::from("sk-anthropic-key"),
            );
            store.insert(
                "store_together-model".to_string(),
                SecretString::from("sk-together-key"),
            );
        }

        // Verify all keys are available
        let empty_user_creds: InferenceCredentials = HashMap::new();
        let mut merged = empty_user_creds.clone();
        {
            let credential_store = app_state.model_credential_store.read().unwrap();
            for (key, value) in credential_store.iter() {
                merged.insert(key.clone(), value.clone());
            }
        }

        assert_eq!(merged.len(), 3);
        assert!(merged.contains_key("store_openai-model"));
        assert!(merged.contains_key("store_anthropic-model"));
        assert!(merged.contains_key("store_together-model"));

        // Test selective model deletion
        app_state.remove_model_table("anthropic-model").await;

        {
            let store = app_state.model_credential_store.read().unwrap();
            assert_eq!(store.len(), 2);
            assert!(store.contains_key("store_openai-model"));
            assert!(!store.contains_key("store_anthropic-model"));
            assert!(store.contains_key("store_together-model"));
        }
    }
}
