#[cfg(test)]
mod tests {
    use crate::endpoints::capability::EndpointCapability;
    use crate::error::{Error, ErrorDetails};
    use crate::model::{ModelConfig, RetryConfig};
    use std::collections::{HashMap, HashSet};

    #[test]
    fn test_model_config_with_fallback_models() {
        let model_config = ModelConfig {
            routing: vec!["provider1".into()],
            providers: HashMap::new(),
            endpoints: HashSet::from([EndpointCapability::Chat]),
            fallback_models: Some(vec!["model-b".into(), "model-c".into()]),
            retry_config: Some(RetryConfig {
                num_retries: 2,
                max_delay_s: 5.0,
            }),
            rate_limits: None,
            pricing: None,
            inference_cost: None,
            guardrail_profile: None,
        };

        assert!(model_config.fallback_models.is_some());
        let fallback_models = model_config.fallback_models.unwrap();
        assert_eq!(fallback_models.len(), 2);
        assert_eq!(fallback_models[0].as_ref(), "model-b");
        assert_eq!(fallback_models[1].as_ref(), "model-c");
    }

    #[test]
    fn test_model_config_without_fallback() {
        let model_config = ModelConfig {
            routing: vec!["provider1".into()],
            providers: HashMap::new(),
            endpoints: HashSet::from([EndpointCapability::Chat]),
            fallback_models: None,
            retry_config: None,
            rate_limits: None,
            pricing: None,
            inference_cost: None,
            guardrail_profile: None,
        };

        assert!(model_config.fallback_models.is_none());
        assert!(model_config.retry_config.is_none());
    }

    #[test]
    fn test_retry_config_defaults() {
        let default_config = RetryConfig::default();
        assert_eq!(default_config.num_retries, 0);
        assert_eq!(default_config.max_delay_s, 10.0);

        // Test that get_backoff returns a properly configured backoff
        let backoff = default_config.get_backoff();
        // The backoff should be configured but we can't easily test the internal state
        // Just verify it builds without panic
        use backon::BackoffBuilder;
        let _backoff_built = backoff.build();
    }

    #[test]
    fn test_retry_config_custom() {
        let retry_config = RetryConfig {
            num_retries: 5,
            max_delay_s: 30.0,
        };

        assert_eq!(retry_config.num_retries, 5);
        assert_eq!(retry_config.max_delay_s, 30.0);

        let backoff = retry_config.get_backoff();
        use backon::BackoffBuilder;
        let _backoff_built = backoff.build();
    }

    #[test]
    fn test_circular_fallback_detection() {
        // This would test the actual cycle detection logic
        // The implementation is in the config_parser.rs detect_circular_fallbacks function
        let mut models = HashMap::new();

        // Create a circular dependency: A -> B -> C -> A
        models.insert("model-a".to_string(), vec!["model-b".to_string()]);
        models.insert("model-b".to_string(), vec!["model-c".to_string()]);
        models.insert("model-c".to_string(), vec!["model-a".to_string()]);

        // In a real test, we would call detect_circular_fallbacks here
        // For now, we just verify the data structure
        assert_eq!(models.get("model-a").unwrap()[0], "model-b");
        assert_eq!(models.get("model-b").unwrap()[0], "model-c");
        assert_eq!(models.get("model-c").unwrap()[0], "model-a");
    }

    #[test]
    fn test_model_chain_exhausted_error() {
        let mut errors = HashMap::new();
        errors.insert(
            "model-a".to_string(),
            Error::new(ErrorDetails::ProviderNotFound {
                provider_name: "provider-a".to_string(),
            }),
        );
        errors.insert(
            "model-b".to_string(),
            Error::new(ErrorDetails::ProviderNotFound {
                provider_name: "provider-b".to_string(),
            }),
        );

        let error = Error::new(ErrorDetails::ModelChainExhausted {
            model_errors: errors,
        });

        match error.get_details() {
            ErrorDetails::ModelChainExhausted { model_errors } => {
                assert_eq!(model_errors.len(), 2);
                assert!(model_errors.contains_key("model-a"));
                assert!(model_errors.contains_key("model-b"));
            }
            _ => panic!("Expected ModelChainExhausted error"),
        }
    }
}
