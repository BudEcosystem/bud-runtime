pub mod config;
pub mod limiter;
pub mod middleware;
pub mod middleware_optimized;
pub mod middleware_fast;
pub mod store;

#[cfg(test)]
mod tests;

pub use config::{RateLimitAlgorithm, RateLimitConfig};
pub use limiter::DistributedRateLimiter;
pub use middleware::{conditional_rate_limit_middleware, rate_limit_middleware, RateLimitError};
pub use store::RateLimiterStore;

use axum::http::{HeaderMap, HeaderValue};

/// Headers returned with rate limit information
#[derive(Debug, Clone)]
pub struct RateLimitHeaders {
    pub limit: u32,
    pub remaining: u32,
    pub reset: u64,               // Unix timestamp
    pub retry_after: Option<u32>, // Seconds
}

impl RateLimitHeaders {
    pub fn to_header_map(&self) -> HeaderMap {
        let mut headers = HeaderMap::new();

        // These conversions are safe because we're converting numbers to strings.
        // Numbers always produce valid header values.
        if let Ok(value) = HeaderValue::from_str(&self.limit.to_string()) {
            headers.insert("X-RateLimit-Limit", value);
        }
        
        if let Ok(value) = HeaderValue::from_str(&self.remaining.to_string()) {
            headers.insert("X-RateLimit-Remaining", value);
        }
        
        if let Ok(value) = HeaderValue::from_str(&self.reset.to_string()) {
            headers.insert("X-RateLimit-Reset", value);
        }

        if let Some(retry_after) = self.retry_after {
            if let Ok(value) = HeaderValue::from_str(&retry_after.to_string()) {
                headers.insert("Retry-After", value);
            }
        }

        headers
    }
}

/// Result of a rate limit check
#[derive(Debug)]
pub enum RateLimitDecision {
    Allow(RateLimitHeaders),
    Deny(RateLimitHeaders),
}

impl RateLimitDecision {
    pub fn is_allowed(&self) -> bool {
        matches!(self, RateLimitDecision::Allow(_))
    }

    pub fn headers(&self) -> &RateLimitHeaders {
        match self {
            RateLimitDecision::Allow(h) | RateLimitDecision::Deny(h) => h,
        }
    }
}

/// Metrics for rate limiter performance monitoring
#[derive(Debug, Default)]
pub struct RateLimiterMetrics {
    pub cache_hits: std::sync::atomic::AtomicU64,
    pub cache_misses: std::sync::atomic::AtomicU64,
    pub redis_timeouts: std::sync::atomic::AtomicU64,
    pub rate_limit_exceeded: std::sync::atomic::AtomicU64,
    pub local_allows: std::sync::atomic::AtomicU64,
    pub redis_checks: std::sync::atomic::AtomicU64,
}

impl RateLimiterMetrics {
    pub fn record_cache_hit(&self) {
        self.cache_hits
            .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
    }

    pub fn record_cache_miss(&self) {
        self.cache_misses
            .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
    }

    pub fn record_redis_timeout(&self) {
        self.redis_timeouts
            .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
    }

    pub fn record_rate_limit_exceeded(&self) {
        self.rate_limit_exceeded
            .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
    }

    pub fn record_local_allow(&self) {
        self.local_allows
            .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
    }

    pub fn record_redis_check(&self) {
        self.redis_checks
            .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
    }
}
