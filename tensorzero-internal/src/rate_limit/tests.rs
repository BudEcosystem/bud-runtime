use super::*;

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_config() -> RateLimitConfig {
        RateLimitConfig {
            algorithm: RateLimitAlgorithm::FixedWindow,
            requests_per_second: Some(10),
            requests_per_minute: Some(100),
            requests_per_hour: None,
            burst_size: Some(15),
            enabled: true,
            cache_ttl_ms: 1000,
            redis_timeout_ms: 500,
            local_allowance: 0.8,
            sync_interval_ms: 10000,
        }
    }

    #[test]
    fn test_rate_limit_config_creation() {
        let config = create_test_config();

        assert_eq!(config.algorithm, RateLimitAlgorithm::FixedWindow);
        assert_eq!(config.requests_per_second, Some(10));
        assert_eq!(config.requests_per_minute, Some(100));
        assert!(config.requests_per_hour.is_none());
        assert_eq!(config.burst_size, Some(15));
        assert!(config.enabled);
        assert_eq!(config.cache_ttl_ms, 1000);
        assert_eq!(config.redis_timeout_ms, 500);
        assert_eq!(config.local_allowance, 0.8);
        assert_eq!(config.sync_interval_ms, 10000);
    }

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
    fn test_rate_limit_algorithms() {
        // Test different algorithm types
        let fixed_window = RateLimitAlgorithm::FixedWindow;
        let sliding_window = RateLimitAlgorithm::SlidingWindow;
        let token_bucket = RateLimitAlgorithm::TokenBucket;

        // Ensure they can be compared and cloned
        assert_ne!(fixed_window, sliding_window);
        assert_ne!(sliding_window, token_bucket);
        assert_ne!(token_bucket, fixed_window);

        let cloned = fixed_window.clone();
        assert_eq!(fixed_window, cloned);
    }

    // Note: GlobalRateLimitConfig is in config_parser module
    // This test would require importing from the parent crate

    // Integration tests would require Redis setup
    // These are placeholder tests for the structure
    #[test]
    fn test_rate_limiter_store_placeholder() {
        // This would test the RateLimiterStore if implemented
        // For now, it's a placeholder to demonstrate the testing structure
    }

    #[test]
    fn test_middleware_placeholder() {
        // This would test the middleware functionality
        // Requires more complex setup with Axum request/response mocking
    }
}

#[cfg(test)]
mod benchmark_tests {
    use super::*;
    use std::time::Instant;

    #[test]
    fn test_rate_limit_config_performance() {
        // Test configuration creation performance
        let iterations = 10000;
        let start = Instant::now();

        for _ in 0..iterations {
            let _config = RateLimitConfig {
                algorithm: RateLimitAlgorithm::FixedWindow,
                requests_per_second: Some(1000),
                requests_per_minute: None,
                requests_per_hour: None,
                burst_size: Some(100),
                enabled: true,
                cache_ttl_ms: 1000,
                redis_timeout_ms: 500,
                local_allowance: 0.8,
                sync_interval_ms: 10000,
            };
        }

        let duration = start.elapsed();
        let avg_ns = duration.as_nanos() / iterations as u128;

        // Config creation should be very fast (< 100 nanoseconds)
        assert!(
            avg_ns < 100,
            "Config creation average {}ns exceeds 100ns target",
            avg_ns
        );

        println!(
            "Rate limit config creation performance: {}ns average",
            avg_ns
        );
    }

    #[test]
    fn test_headers_generation_performance() {
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
            "Header generation latency {}μs exceeds 100μs target",
            avg_latency_us
        );

        println!(
            "Header generation performance: {}μs average",
            avg_latency_us
        );
    }

    #[test]
    fn test_metrics_recording_performance() {
        // Test metrics recording performance
        use std::sync::Arc;

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
            "Metrics recording latency {}ns exceeds 50ns target",
            avg_latency_ns
        );

        println!(
            "Metrics recording performance: {}ns average",
            avg_latency_ns
        );
    }
}

#[cfg(all(test, not(feature = "ci")))]
mod load_tests {
    use super::*;
    use std::time::Instant;

    #[test]
    fn test_rate_limit_decision_throughput() {
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

        println!(
            "Rate limit decision throughput: {:.0} decisions/second",
            throughput
        );

        // Should handle at least 1M decisions per second
        assert!(
            throughput > 1_000_000.0,
            "Throughput {:.0} decisions/s below 1M/s target",
            throughput
        );
    }
}
