//use crate::error::{Error, ErrorDetails};
use crate::rate_limit::config::{GlobalRateLimitConfig, RateLimitConfig};
use arc_swap::ArcSwap;
use dashmap::DashMap;
use std::sync::Arc;

/// Store for managing rate limiters for different models
#[derive(Clone)]
pub struct RateLimiterStore {
    /// Map of model name to rate limit configuration
    configs: Arc<DashMap<String, Arc<RateLimitConfig>>>,

    /// Global rate limit configuration
    global_config: Arc<ArcSwap<GlobalRateLimitConfig>>,

    /// Default configuration for models without specific config
    default_config: Arc<RateLimitConfig>,
}

impl RateLimiterStore {
    /// Create a new rate limiter store
    pub fn new(global_config: GlobalRateLimitConfig) -> Self {
        let default_config = Arc::new(RateLimitConfig {
            requests_per_minute: global_config.default_requests_per_minute,
            burst_size: global_config.default_burst_size,
            algorithm: global_config.default_algorithm,
            ..Default::default()
        });

        Self {
            configs: Arc::new(DashMap::new()),
            global_config: Arc::new(ArcSwap::from_pointee(global_config)),
            default_config,
        }
    }

    /// Add or update rate limit configuration for a model
    pub fn update_model_config(&self, model_name: String, config: RateLimitConfig) {
        self.configs.insert(model_name, Arc::new(config));
    }

    /// Get rate limit configuration for a model
    pub fn get_model_config(&self, model_name: &str) -> Arc<RateLimitConfig> {
        self.configs
            .get(model_name)
            .map(|entry| Arc::clone(entry.value()))
            .unwrap_or_else(|| Arc::clone(&self.default_config))
    }

    /// Remove rate limit configuration for a model
    pub fn remove_model_config(&self, model_name: &str) {
        self.configs.remove(model_name);
    }

    /// Check if rate limiting is enabled globally
    pub fn is_enabled(&self) -> bool {
        self.global_config.load().enabled
    }

    /// Update global configuration
    pub fn update_global_config(&self, config: GlobalRateLimitConfig) {
        self.global_config.store(Arc::new(config));
    }

    /// Get all configured models
    pub fn list_models(&self) -> Vec<String> {
        self.configs
            .iter()
            .map(|entry| entry.key().clone())
            .collect()
    }

    /// Clear all model configurations
    pub fn clear(&self) {
        self.configs.clear();
    }

    /// Load configurations from a map (useful for initialization)
    pub fn load_configs(&self, configs: impl IntoIterator<Item = (String, RateLimitConfig)>) {
        for (model_name, config) in configs {
            self.update_model_config(model_name, config);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::rate_limit::config::RateLimitAlgorithm;

    #[test]
    fn test_rate_limiter_store() {
        let global_config = GlobalRateLimitConfig {
            enabled: true,
            default_requests_per_minute: Some(60),
            default_burst_size: Some(10),
            default_algorithm: RateLimitAlgorithm::SlidingWindow,
        };

        let store = RateLimiterStore::new(global_config);

        // Test default config
        let config = store.get_model_config("unknown-model");
        assert_eq!(config.requests_per_minute, Some(60));
        assert_eq!(config.burst_size, Some(10));

        // Test updating model config
        let custom_config = RateLimitConfig {
            requests_per_minute: Some(100),
            requests_per_second: Some(5),
            ..Default::default()
        };

        store.update_model_config("gpt-4".to_string(), custom_config);

        let retrieved = store.get_model_config("gpt-4");
        assert_eq!(retrieved.requests_per_minute, Some(100));
        assert_eq!(retrieved.requests_per_second, Some(5));

        // Test listing models
        let models = store.list_models();
        assert!(models.contains(&"gpt-4".to_string()));

        // Test removing config
        store.remove_model_config("gpt-4");
        let config_after_remove = store.get_model_config("gpt-4");
        assert_eq!(config_after_remove.requests_per_minute, Some(60)); // Back to default
    }
}
