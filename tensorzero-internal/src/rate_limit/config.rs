use serde::{Deserialize, Serialize};

/// Algorithm to use for rate limiting
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RateLimitAlgorithm {
    /// Fixed window counter - fastest, slightly less accurate at boundaries
    FixedWindow,
    /// Sliding window counter - more accurate, slightly slower
    SlidingWindow,
    /// Token bucket - smooth rate limiting
    TokenBucket,
}

impl Default for RateLimitAlgorithm {
    fn default() -> Self {
        Self::SlidingWindow
    }
}

/// Configuration for rate limiting
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RateLimitConfig {
    /// Algorithm to use
    #[serde(default)]
    pub algorithm: RateLimitAlgorithm,

    /// Requests allowed per second
    pub requests_per_second: Option<u32>,

    /// Requests allowed per minute
    pub requests_per_minute: Option<u32>,

    /// Requests allowed per hour
    pub requests_per_hour: Option<u32>,

    /// Burst size for token bucket algorithm
    pub burst_size: Option<u32>,

    /// Whether rate limiting is enabled
    #[serde(default = "default_enabled")]
    pub enabled: bool,

    /// Local cache TTL in milliseconds
    #[serde(default = "default_cache_ttl_ms")]
    pub cache_ttl_ms: u64,

    /// Redis operation timeout in milliseconds
    #[serde(default = "default_redis_timeout_ms")]
    pub redis_timeout_ms: u64,

    /// Local allowance ratio (0.0-1.0) - allow this ratio over limit locally
    #[serde(default = "default_local_allowance")]
    pub local_allowance: f64,

    /// Background sync interval in milliseconds
    #[serde(default = "default_sync_interval_ms")]
    pub sync_interval_ms: u64,
}

fn default_enabled() -> bool {
    true
}

fn default_cache_ttl_ms() -> u64 {
    200
}

fn default_redis_timeout_ms() -> u64 {
    10
}

fn default_local_allowance() -> f64 {
    0.1
}

fn default_sync_interval_ms() -> u64 {
    100
}

impl Default for RateLimitConfig {
    fn default() -> Self {
        Self {
            algorithm: RateLimitAlgorithm::default(),
            requests_per_second: None,
            requests_per_minute: None,
            requests_per_hour: None,
            burst_size: None,
            enabled: default_enabled(),
            cache_ttl_ms: default_cache_ttl_ms(),
            redis_timeout_ms: default_redis_timeout_ms(),
            local_allowance: default_local_allowance(),
            sync_interval_ms: default_sync_interval_ms(),
        }
    }
}

impl RateLimitConfig {
    /// Check if any rate limits are configured
    pub fn has_limits(&self) -> bool {
        self.requests_per_second.is_some()
            || self.requests_per_minute.is_some()
            || self.requests_per_hour.is_some()
    }

    /// Get the most restrictive limit for quota calculation
    pub fn most_restrictive_limit(&self) -> Option<(u32, std::time::Duration)> {
        let mut limits = Vec::new();

        if let Some(rps) = self.requests_per_second {
            limits.push((rps, std::time::Duration::from_secs(1)));
        }

        if let Some(rpm) = self.requests_per_minute {
            limits.push((rpm, std::time::Duration::from_secs(60)));
        }

        if let Some(rph) = self.requests_per_hour {
            limits.push((rph, std::time::Duration::from_secs(3600)));
        }

        // Return the most restrictive (lowest rate) limit
        limits.into_iter().min_by_key(|(limit, duration)| {
            // Calculate requests per second for comparison
            (*limit as f64 / duration.as_secs_f64() * 1000.0) as u64
        })
    }

    /// Merge with another config, with other taking precedence
    pub fn merge(self, other: Self) -> Self {
        Self {
            algorithm: other.algorithm,
            requests_per_second: other.requests_per_second.or(self.requests_per_second),
            requests_per_minute: other.requests_per_minute.or(self.requests_per_minute),
            requests_per_hour: other.requests_per_hour.or(self.requests_per_hour),
            burst_size: other.burst_size.or(self.burst_size),
            enabled: other.enabled,
            cache_ttl_ms: if other.cache_ttl_ms != default_cache_ttl_ms() {
                other.cache_ttl_ms
            } else {
                self.cache_ttl_ms
            },
            redis_timeout_ms: if other.redis_timeout_ms != default_redis_timeout_ms() {
                other.redis_timeout_ms
            } else {
                self.redis_timeout_ms
            },
            local_allowance: if (other.local_allowance - default_local_allowance()).abs()
                > f64::EPSILON
            {
                other.local_allowance
            } else {
                self.local_allowance
            },
            sync_interval_ms: if other.sync_interval_ms != default_sync_interval_ms() {
                other.sync_interval_ms
            } else {
                self.sync_interval_ms
            },
        }
    }
}

/// Global rate limit configuration
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct GlobalRateLimitConfig {
    /// Whether rate limiting is enabled globally
    #[serde(default = "default_true")]
    pub enabled: bool,

    /// Default requests per minute for models without specific config
    pub default_requests_per_minute: Option<u32>,

    /// Default burst size
    pub default_burst_size: Option<u32>,

    /// Default algorithm
    #[serde(default)]
    pub default_algorithm: RateLimitAlgorithm,
}

fn default_true() -> bool {
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rate_limit_config_defaults() {
        let config = RateLimitConfig::default();
        assert!(config.enabled);
        assert_eq!(config.cache_ttl_ms, 200);
        assert_eq!(config.redis_timeout_ms, 10);
        assert_eq!(config.local_allowance, 0.1);
        assert_eq!(config.sync_interval_ms, 100);
    }

    #[test]
    fn test_most_restrictive_limit() {
        let config = RateLimitConfig {
            requests_per_second: Some(10),
            requests_per_minute: Some(300), // Less restrictive than 10/s
            requests_per_hour: Some(1000),  // Most restrictive
            ..Default::default()
        };

        let (limit, duration) = config.most_restrictive_limit().unwrap();
        assert_eq!(limit, 1000);
        assert_eq!(duration, std::time::Duration::from_secs(3600));
    }

    #[test]
    fn test_config_merge() {
        let base = RateLimitConfig {
            requests_per_minute: Some(60),
            cache_ttl_ms: 300,
            ..Default::default()
        };

        let override_config = RateLimitConfig {
            requests_per_second: Some(2),
            cache_ttl_ms: 500,
            ..Default::default()
        };

        let merged = base.merge(override_config);
        assert_eq!(merged.requests_per_minute, Some(60));
        assert_eq!(merged.requests_per_second, Some(2));
        assert_eq!(merged.cache_ttl_ms, 500);
    }
}
