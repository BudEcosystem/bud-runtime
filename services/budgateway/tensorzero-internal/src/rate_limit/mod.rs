pub mod config;
pub mod early_extract;
pub mod limiter;
pub mod middleware;
pub mod store;

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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rate_limit_headers() {
        let headers = RateLimitHeaders {
            limit: 100,
            remaining: 45,
            reset: 1234567890,
            retry_after: None,
        };

        let header_map = headers.to_header_map();

        assert!(header_map.contains_key("X-RateLimit-Limit"));
        assert!(header_map.contains_key("X-RateLimit-Remaining"));
        assert!(header_map.contains_key("X-RateLimit-Reset"));
        assert!(!header_map.contains_key("Retry-After"));
    }

    #[test]
    fn test_rate_limit_headers_with_retry_after() {
        let headers = RateLimitHeaders {
            limit: 100,
            remaining: 0,
            reset: 1234567890,
            retry_after: Some(60),
        };

        let header_map = headers.to_header_map();

        assert!(header_map.contains_key("X-RateLimit-Limit"));
        assert!(header_map.contains_key("X-RateLimit-Remaining"));
        assert!(header_map.contains_key("X-RateLimit-Reset"));
        assert!(header_map.contains_key("Retry-After"));
    }

    #[test]
    fn test_rate_limit_decision_allow() {
        let headers = RateLimitHeaders {
            limit: 100,
            remaining: 45,
            reset: 1234567890,
            retry_after: None,
        };

        let decision = RateLimitDecision::Allow(headers);

        assert!(decision.is_allowed());
        assert_eq!(decision.headers().remaining, 45);
        assert!(decision.headers().retry_after.is_none());
    }

    #[test]
    fn test_rate_limit_decision_deny() {
        let headers = RateLimitHeaders {
            limit: 100,
            remaining: 0,
            reset: 1234567890,
            retry_after: Some(60),
        };

        let decision = RateLimitDecision::Deny(headers);

        assert!(!decision.is_allowed());
        assert_eq!(decision.headers().remaining, 0);
        assert_eq!(decision.headers().retry_after, Some(60));
    }

    #[test]
    fn test_rate_limiter_metrics() {
        let metrics = RateLimiterMetrics::default();

        // Test metric increments
        metrics.record_cache_hit();
        metrics.record_cache_miss();
        metrics.record_redis_timeout();
        metrics.record_rate_limit_exceeded();
        metrics.record_local_allow();
        metrics.record_redis_check();

        // Verify metrics were recorded
        assert_eq!(
            metrics
                .cache_hits
                .load(std::sync::atomic::Ordering::Relaxed),
            1
        );
        assert_eq!(
            metrics
                .cache_misses
                .load(std::sync::atomic::Ordering::Relaxed),
            1
        );
        assert_eq!(
            metrics
                .redis_timeouts
                .load(std::sync::atomic::Ordering::Relaxed),
            1
        );
        assert_eq!(
            metrics
                .rate_limit_exceeded
                .load(std::sync::atomic::Ordering::Relaxed),
            1
        );
        assert_eq!(
            metrics
                .local_allows
                .load(std::sync::atomic::Ordering::Relaxed),
            1
        );
        assert_eq!(
            metrics
                .redis_checks
                .load(std::sync::atomic::Ordering::Relaxed),
            1
        );
    }

    #[test]
    fn test_headers_generation_performance() {
        use std::time::Instant;

        // Test header generation performance
        let iterations = 10000;
        let start = Instant::now();

        for i in 0..iterations {
            let headers = RateLimitHeaders {
                limit: 100,
                remaining: 100 - (i % 100) as u32,
                reset: 1234567890 + i,
                retry_after: if i % 10 == 0 { Some(60) } else { None },
            };

            let _ = headers.to_header_map();
        }

        let duration = start.elapsed();
        let avg_latency_us = duration.as_micros() / iterations as u128;

        assert!(
            avg_latency_us < 100,
            "Header generation latency {avg_latency_us}μs exceeds 100μs target"
        );

        tracing::debug!("Header generation performance: {avg_latency_us}μs average");
    }

    #[test]
    fn test_metrics_recording_performance() {
        use std::sync::Arc;
        use std::time::Instant;

        // Test metrics recording performance
        let metrics = Arc::new(RateLimiterMetrics::default());
        let iterations = 100000;
        let start = Instant::now();

        for _ in 0..iterations {
            metrics.record_cache_hit();
            metrics.record_local_allow();
        }

        let duration = start.elapsed();
        let avg_latency_ns = duration.as_nanos() / iterations as u128;

        // Metrics recording should be extremely fast (< 50 nanoseconds)
        assert!(
            avg_latency_ns < 50,
            "Metrics recording latency {avg_latency_ns}ns exceeds 50ns target"
        );

        tracing::debug!("Metrics recording performance: {avg_latency_ns}ns average");
    }

    #[test]
    fn test_rate_limit_decision_throughput() {
        use std::time::Instant;

        // Test decision creation throughput
        let iterations = 100000;
        let start = Instant::now();

        for i in 0..iterations {
            let headers = RateLimitHeaders {
                limit: 1000,
                remaining: 1000 - (i % 1000) as u32,
                reset: 1234567890 + i / 1000,
                retry_after: if i % 1000 == 999 { Some(60) } else { None },
            };

            let decision = if i % 1000 < 999 {
                RateLimitDecision::Allow(headers)
            } else {
                RateLimitDecision::Deny(headers)
            };

            // Verify decision
            let _ = decision.is_allowed();
            let _ = decision.headers();
        }

        let duration = start.elapsed();
        let throughput = iterations as f64 / duration.as_secs_f64();

        tracing::debug!("Rate limit decision throughput: {throughput:.0} decisions/second");

        // Should handle at least 1M decisions per second
        assert!(
            throughput > 1_000_000.0,
            "Throughput {throughput:.0} decisions/s below 1M/s target"
        );
    }
}
