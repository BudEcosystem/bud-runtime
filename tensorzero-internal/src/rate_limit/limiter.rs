use crate::error::{Error, ErrorDetails};
use crate::rate_limit::{
    config::RateLimitConfig, RateLimitDecision, RateLimitHeaders, RateLimiterMetrics,
};
use crate::redis_client::RedisClient;
use dashmap::DashMap;
use governor::{
    clock::{Clock, QuantaClock, QuantaInstant, Reference},
    middleware::NoOpMiddleware,
    state::{InMemoryState, NotKeyed},
    Quota, RateLimiter,
};
use moka::future::Cache;
// Redis connection managed by RedisClient
use redis::{AsyncCommands, Script};
use std::num::NonZeroU32;
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::sync::RwLock;
// use futures::StreamExt;  // TODO: Uncomment when pub/sub is re-enabled
use serde::{Deserialize, Serialize};
use tokio::task::JoinHandle;
use tokio::time::{interval, timeout};
use tracing::{debug, warn};

/// Helper function to get current Unix timestamp.
/// Returns 0 if system time is before UNIX_EPOCH (extremely rare).
fn get_unix_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/// Cached rate limit entry with local counting
#[derive(Clone, Debug)]
struct CachedRateLimit {
    remaining: u32,
    limit: u32,
    local_consumed: Arc<std::sync::atomic::AtomicU32>,  // Track local usage since cache
    #[allow(dead_code)]
    reset_at: QuantaInstant,
    cached_at: QuantaInstant,
    ttl: Duration,
}

impl CachedRateLimit {
    /// Check if the cache entry is still fresh
    fn is_fresh(&self) -> bool {
        let elapsed = QuantaClock::default().now().duration_since(self.cached_at);
        elapsed < self.ttl.into()
    }
    
    /// Try to consume one request from local quota
    /// Returns Some(remaining) if allowed, None if local quota exhausted
    fn try_consume_local(&self) -> Option<u32> {
        let consumed = self.local_consumed.load(std::sync::atomic::Ordering::Relaxed);
        
        // Check if we have local quota remaining
        if consumed < self.remaining {
            // Atomically increment and check again
            let new_consumed = self.local_consumed.fetch_add(1, std::sync::atomic::Ordering::Relaxed) + 1;
            
            if new_consumed <= self.remaining {
                // Successfully consumed locally
                Some(self.remaining - new_consumed)
            } else {
                // Raced with another thread, local quota exhausted
                None
            }
        } else {
            // Local quota already exhausted
            None
        }
    }
    
    /// Convert to rate limit headers
    fn to_headers(&self, retry_after: Option<u32>) -> RateLimitHeaders {
        let consumed = self.local_consumed.load(std::sync::atomic::Ordering::Relaxed);
        let remaining = self.remaining.saturating_sub(consumed);
        
        RateLimitHeaders {
            limit: self.limit,
            remaining,
            reset: get_unix_timestamp() + self.ttl.as_secs(),
            retry_after,
        }
    }
}

/// Configuration update message for pub/sub
#[derive(Debug, Deserialize, Serialize)]
struct ConfigUpdate {
    action: String, // "create", "update", or "delete"
    config: Option<RateLimitConfig>,
}


/// Model-specific rate limiter with multiple time windows
struct ModelRateLimiter {
    per_second: Option<Arc<RateLimiter<NotKeyed, InMemoryState, QuantaClock, NoOpMiddleware>>>,
    per_minute: Option<Arc<RateLimiter<NotKeyed, InMemoryState, QuantaClock, NoOpMiddleware>>>,
    per_hour: Option<Arc<RateLimiter<NotKeyed, InMemoryState, QuantaClock, NoOpMiddleware>>>,
    config: Arc<RateLimitConfig>,
}

impl ModelRateLimiter {
    fn new(config: Arc<RateLimitConfig>) -> Self {
        let clock = QuantaClock::default();

        let per_second = config.requests_per_second.and_then(|rps| {
            NonZeroU32::new(rps).map(|rps| {
                let quota = Quota::per_second(rps)
                    .allow_burst(config.burst_size.and_then(NonZeroU32::new).unwrap_or(rps));
                Arc::new(RateLimiter::direct_with_clock(quota, &clock))
            })
        });

        let per_minute = config.requests_per_minute.and_then(|rpm| {
            NonZeroU32::new(rpm).map(|rpm| {
                let quota = Quota::per_minute(rpm)
                    .allow_burst(config.burst_size.and_then(NonZeroU32::new).unwrap_or(rpm));
                Arc::new(RateLimiter::direct_with_clock(quota, &clock))
            })
        });

        let per_hour = config.requests_per_hour.and_then(|rph| {
            NonZeroU32::new(rph).map(|rph| {
                let quota = Quota::per_hour(rph)
                    .allow_burst(config.burst_size.and_then(NonZeroU32::new).unwrap_or(rph));
                Arc::new(RateLimiter::direct_with_clock(quota, &clock))
            })
        });

        Self {
            per_second,
            per_minute,
            per_hour,
            config,
        }
    }

    /// Check local rate limits
    fn check_local(&self) -> Result<(), QuantaInstant> {
        // Check all configured rate limits, return the most restrictive
        let mut earliest_retry = None;

        if let Some(limiter) = &self.per_second {
            match limiter.check() {
                Ok(_) => {}
                Err(not_until) => {
                    earliest_retry = Some(
                        earliest_retry
                            .unwrap_or(not_until.earliest_possible())
                            .min(not_until.earliest_possible()),
                    );
                }
            }
        }

        if let Some(limiter) = &self.per_minute {
            match limiter.check() {
                Ok(_) => {}
                Err(not_until) => {
                    earliest_retry = Some(
                        earliest_retry
                            .unwrap_or(not_until.earliest_possible())
                            .min(not_until.earliest_possible()),
                    );
                }
            }
        }

        if let Some(limiter) = &self.per_hour {
            match limiter.check() {
                Ok(_) => {}
                Err(not_until) => {
                    earliest_retry = Some(
                        earliest_retry
                            .unwrap_or(not_until.earliest_possible())
                            .min(not_until.earliest_possible()),
                    );
                }
            }
        }

        match earliest_retry {
            Some(retry_at) => Err(retry_at),
            None => Ok(()),
        }
    }
}

/// Distributed rate limiter with local caching and Redis backend
pub struct DistributedRateLimiter {
    /// Local governor instances per model
    local_limiters: Arc<DashMap<String, Arc<ModelRateLimiter>>>,

    /// Redis client for distributed coordination
    redis_client: Arc<RedisClient>,

    /// High-performance local cache
    cache: Arc<Cache<String, CachedRateLimit>>,

    /// Background sync handle
    sync_handle: Arc<RwLock<Option<JoinHandle<()>>>>,

    /// Pub/sub handle for config updates
    pubsub_handle: Arc<RwLock<Option<JoinHandle<()>>>>,

    /// Performance metrics
    metrics: Arc<RateLimiterMetrics>,

    /// Redis Lua script for atomic check and increment
    check_and_increment_script: Script,
}

impl DistributedRateLimiter {
    /// Create a new distributed rate limiter
    pub async fn new(redis_client: Arc<RedisClient>) -> Result<Self, Error> {
        // Initialize cache with 10k entries and 5 minute TTL
        let cache = Cache::builder()
            .max_capacity(10_000)
            .time_to_live(Duration::from_secs(300))
            .build();

        let check_and_increment_script = Script::new(
            r#"
            local key = KEYS[1]
            local limit = tonumber(ARGV[1])
            local window = tonumber(ARGV[2])
            local now = tonumber(ARGV[3])
            
            -- Clean old entries for sliding window
            redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
            
            -- Count current entries
            local current = redis.call('ZCARD', key)
            
            if current < limit then
                -- Add new entry
                redis.call('ZADD', key, now, now .. ':' .. redis.call('INCR', key .. ':counter'))
                redis.call('EXPIRE', key, window)
                return {1, limit - current - 1, limit}
            else
                -- Get oldest entry for reset time
                local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
                local reset_at = oldest[2] and (oldest[2] + window) or (now + window)
                return {0, 0, limit, reset_at}
            end
            "#,
        );

        Ok(Self {
            local_limiters: Arc::new(DashMap::new()),
            redis_client,
            cache: Arc::new(cache),
            sync_handle: Arc::new(RwLock::new(None)),
            pubsub_handle: Arc::new(RwLock::new(None)),
            metrics: Arc::new(RateLimiterMetrics::default()),
            check_and_increment_script,
        })
    }

    /// Add or update a model's rate limit configuration
    pub fn update_model_config(&self, model: String, config: RateLimitConfig) {
        let limiter = Arc::new(ModelRateLimiter::new(Arc::new(config)));
        self.local_limiters.insert(model, limiter);

        // Clear cache entries for this model
        // Note: moka doesn't have pattern-based invalidation, so we'd need to track keys
    }

    /// Check rate limit for a model and API key
    pub async fn check_rate_limit(
        &self,
        model: &str,
        api_key: &str,
    ) -> Result<RateLimitDecision, Error> {
        let start = tokio::time::Instant::now();
        let cache_key = format!("{}:{}", model, api_key);
        let cache_key_time = start.elapsed();

        // Fast path 1: Check local cache with local counting
        let cache_check_start = tokio::time::Instant::now();
        if let Some(cached) = self.cache.get(&cache_key).await {
            let cache_lookup_time = cache_check_start.elapsed();
            if cached.is_fresh() {
                if let Some(remaining) = cached.try_consume_local() {
                    self.metrics.record_cache_hit();
                    debug!(
                        model = model,
                        remaining = remaining,
                        cache_key_us = cache_key_time.as_micros(),
                        cache_lookup_us = cache_lookup_time.as_micros(),
                        total_us = start.elapsed().as_micros(),
                        "Rate limit cache hit with local quota"
                    );
                    return Ok(RateLimitDecision::Allow(cached.to_headers(None)));
                } else {
                    debug!(
                        model = model,
                        "Rate limit cache hit but local quota exhausted, falling through to Redis"
                    );
                    // Cache exists but local quota exhausted, fall through to Redis
                }
            }
        }

        // Fast path 2: Check local governor with local_allowance
        if let Some(limiter) = self.local_limiters.get(model) {
            // Check if we should use local allowance to skip Redis
            let should_allow_locally = if limiter.config.local_allowance >= 1.0 {
                true // Always allow locally if local_allowance is 1.0
            } else if limiter.config.local_allowance <= 0.0 {
                false // Never allow locally if local_allowance is 0.0
            } else {
                // Use probabilistic approach for partial local allowance
                rand::random::<f64>() < limiter.config.local_allowance
            };

            if should_allow_locally {
                match limiter.check_local() {
                    Ok(_) => {
                        // Local check passed, update Redis asynchronously
                        self.schedule_redis_update(model, api_key);
                        self.metrics.record_local_allow();

                        let headers = self.compute_headers(model, api_key).await?;
                        debug!(
                            model = model,
                            local_allowance = limiter.config.local_allowance,
                            duration_us = start.elapsed().as_micros(),
                            "Rate limit local allow (within local_allowance)"
                        );
                        return Ok(RateLimitDecision::Allow(headers));
                    }
                    Err(_retry_at) => {
                        // Local limit exceeded, still check with Redis
                        debug!(model = model, "Local rate limit exceeded, checking Redis");
                    }
                }
            } else {
                debug!(
                    model = model, 
                    local_allowance = limiter.config.local_allowance,
                    "Not within local allowance, checking Redis"
                );
            }
        }

        // Slow path: Check with Redis
        self.metrics.record_cache_miss();
        self.check_redis_with_timeout(model, api_key).await
    }

    /// Schedule an async Redis update
    fn schedule_redis_update(&self, model: &str, api_key: &str) {
        let model = model.to_string();
        let api_key = api_key.to_string();
        let redis_client = Arc::clone(&self.redis_client);

        tokio::spawn(async move {
            // Fire and forget Redis update
            if let Err(e) = update_redis_counter(&redis_client, &model, &api_key).await {
                debug!("Failed to update Redis counter: {}", e);
            }
        });
    }

    /// Check rate limit with Redis, using timeout for performance
    async fn check_redis_with_timeout(
        &self,
        model: &str,
        api_key: &str,
    ) -> Result<RateLimitDecision, Error> {
        let key = format!("rl:{}:{}", model, api_key);

        // Get the rate limit config for this model
        // If model not found, fall back to local fallback (allows unknown models)
        let config = match self.local_limiters.get(model) {
            Some(limiter) => Arc::clone(&limiter.config),
            None => {
                debug!(model = model, "Model not configured for rate limiting, allowing request");
                return self.check_local_fallback(model);
            }
        };

        // Use the most restrictive limit
        let (limit, window) = config.most_restrictive_limit().ok_or_else(|| {
            Error::new(ErrorDetails::Config {
                message: "No rate limits configured".to_string(),
            })
        })?;

        let now = get_unix_timestamp();

        // Execute Redis script with timeout
        let timeout_duration = Duration::from_millis(config.redis_timeout_ms);
        let script_result = timeout(
            timeout_duration,
            self.execute_redis_script(&key, limit, window.as_secs(), now),
        )
        .await;

        match script_result {
            Ok(Ok(result)) => {
                let decision = self.parse_redis_result(result, limit)?;

                // Update cache
                if let RateLimitDecision::Allow(ref headers) = decision {
                    let cached = CachedRateLimit {
                        remaining: headers.remaining,
                        limit: headers.limit,
                        local_consumed: Arc::new(std::sync::atomic::AtomicU32::new(0)),
                        reset_at: QuantaClock::default().now()
                            + Duration::from_secs(headers.reset - now).into(),
                        cached_at: QuantaClock::default().now(),
                        ttl: Duration::from_millis(config.cache_ttl_ms),
                    };
                    self.cache.insert(key, cached).await;
                }

                self.metrics.record_redis_check();
                Ok(decision)
            }
            Ok(Err(e)) => {
                warn!("Redis error: {}", e);
                self.metrics.record_redis_timeout();
                // Fallback to local only
                self.check_local_fallback(model)
            }
            Err(_) => {
                warn!("Redis timeout after {}ms", timeout_duration.as_millis());
                self.metrics.record_redis_timeout();
                // Fallback to local only
                self.check_local_fallback(model)
            }
        }
    }

    /// Execute Redis Lua script
    async fn execute_redis_script(
        &self,
        key: &str,
        limit: u32,
        window: u64,
        now: u64,
    ) -> Result<Vec<i64>, redis::RedisError> {
        let mut conn = self.redis_client.get_connection().await?;

        self.check_and_increment_script
            .key(key)
            .arg(limit)
            .arg(window)
            .arg(now)
            .invoke_async(&mut conn)
            .await
    }

    /// Parse Redis script result
    fn parse_redis_result(
        &self,
        result: Vec<i64>,
        _limit: u32,
    ) -> Result<RateLimitDecision, Error> {
        if result.len() < 3 {
            return Err(Error::new(ErrorDetails::InternalError {
                message: "Invalid Redis response".to_string(),
            }));
        }

        let allowed = result[0] == 1;
        let remaining = result[1] as u32;
        let limit = result[2] as u32;
        let reset_at = if result.len() > 3 {
            result[3] as u64
        } else {
            get_unix_timestamp() + 60
        };

        let headers = RateLimitHeaders {
            limit,
            remaining,
            reset: reset_at,
            retry_after: if allowed {
                None
            } else {
                Some((reset_at.saturating_sub(get_unix_timestamp())) as u32)
            },
        };

        if allowed {
            Ok(RateLimitDecision::Allow(headers))
        } else {
            self.metrics.record_rate_limit_exceeded();
            Ok(RateLimitDecision::Deny(headers))
        }
    }

    /// Fallback to local-only rate limiting
    fn check_local_fallback(&self, model: &str) -> Result<RateLimitDecision, Error> {
        if let Some(limiter) = self.local_limiters.get(model) {
            match limiter.check_local() {
                Ok(_) => {
                    let headers = RateLimitHeaders {
                        limit: 0,     // Unknown
                        remaining: 0, // Unknown
                        reset: get_unix_timestamp() + 60,
                        retry_after: None,
                    };
                    Ok(RateLimitDecision::Allow(headers))
                }
                Err(_retry_at) => {
                    let retry_after = 60; // Simplified - would calculate from retry_at
                    let headers = RateLimitHeaders {
                        limit: 0, // Unknown
                        remaining: 0,
                        reset: get_unix_timestamp() + retry_after as u64,
                        retry_after: Some(retry_after),
                    };
                    self.metrics.record_rate_limit_exceeded();
                    Ok(RateLimitDecision::Deny(headers))
                }
            }
        } else {
            // No rate limiting configured for this model
            Ok(RateLimitDecision::Allow(RateLimitHeaders {
                limit: 0,
                remaining: 0,
                reset: 0,
                retry_after: None,
            }))
        }
    }

    /// Compute headers based on current state
    async fn compute_headers(
        &self,
        _model: &str,
        _api_key: &str,
    ) -> Result<RateLimitHeaders, Error> {
        // This is a simplified version - in production you'd want to query actual remaining counts
        Ok(RateLimitHeaders {
            limit: 100,    // Default, should be from config
            remaining: 99, // Should be calculated
            reset: get_unix_timestamp() + 60,
            retry_after: None,
        })
    }

    /// Start background synchronization with Redis
    pub async fn start_background_sync(&self) {
        let _redis_client = Arc::clone(&self.redis_client);
        let _cache = Arc::clone(&self.cache);

        let handle = tokio::spawn(async move {
            let mut sync_interval = interval(Duration::from_millis(100));

            loop {
                sync_interval.tick().await;

                // Batch sync logic would go here
                // For now, this is a placeholder
                debug!("Background sync tick");
            }
        });

        *self.sync_handle.write().await = Some(handle);
    }

    /// Stop background synchronization
    pub async fn stop_background_sync(&self) {
        if let Some(handle) = self.sync_handle.write().await.take() {
            handle.abort();
        }
    }

    /// Start Redis pub/sub listener for dynamic configuration updates
    pub async fn start_pubsub_listener(&self) -> Result<(), Error> {
        // TODO: Implement pub/sub listener for dynamic configuration updates
        // For now, log that this feature is not yet implemented
        warn!(
            "Pub/sub listener for dynamic rate limit configuration updates is not yet implemented"
        );
        warn!("Rate limit configurations will only be updated on gateway restart");

        Ok(())
    }

    /*
    // TODO: Re-enable pub/sub functionality once Redis connection setup is resolved

    /// Main pub/sub listener loop
    async fn pubsub_listener_loop(
        redis_client: Arc<RedisClient>,
        local_limiters: Arc<DashMap<String, Arc<ModelRateLimiter>>>,
    ) {
        loop {
            match Self::run_pubsub_listener(&redis_client, &local_limiters).await {
                Ok(()) => {
                    debug!("Pub/sub listener completed normally");
                    break;
                }
                Err(e) => {
                    warn!("Pub/sub listener error: {}, retrying in 5 seconds", e);
                    tokio::time::sleep(Duration::from_secs(5)).await;
                }
            }
        }
    }
    */

    // TODO: Implement full pub/sub functionality - currently commented out due to Redis connection issues

    /// Stop pub/sub listener
    pub async fn stop_pubsub_listener(&self) {
        let mut pubsub_handle_guard = self.pubsub_handle.write().await;
        if let Some(handle) = pubsub_handle_guard.take() {
            handle.abort();
        }
    }

    /// Publish a configuration update to all instances (for external configuration management)
    pub async fn publish_config_update(
        redis_client: &RedisClient,
        model_name: &str,
        action: &str,
        config: Option<RateLimitConfig>,
    ) -> Result<(), Error> {
        let update = ConfigUpdate {
            action: action.to_string(),
            config,
        };

        let payload = serde_json::to_string(&update).map_err(|e| {
            Error::new(ErrorDetails::InternalError {
                message: format!("Failed to serialize config update: {}", e),
            })
        })?;

        let channel = format!("rate_limit:config:{}", model_name);

        // Use a multiplexed connection for publishing
        let mut conn = redis_client.get_connection().await.map_err(|e| {
            Error::new(ErrorDetails::InternalError {
                message: format!("Failed to get Redis connection for publishing: {}", e),
            })
        })?;

        let _: i32 = conn.publish(&channel, &payload).await.map_err(|e| {
            Error::new(ErrorDetails::InternalError {
                message: format!("Failed to publish config update: {}", e),
            })
        })?;

        debug!(
            "Published config update for model {}: {}",
            model_name, action
        );
        Ok(())
    }
}

/// Helper function to update Redis counter
async fn update_redis_counter(
    redis_client: &RedisClient,
    model: &str,
    api_key: &str,
) -> Result<(), redis::RedisError> {
    let key = format!("rl:{}:{}", model, api_key);
    let mut conn = redis_client.get_connection().await?;

    // Simple increment for now - in production this would be more sophisticated
    let _: i64 = conn.incr(&key, 1).await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_model_rate_limiter() {
        let config = Arc::new(RateLimitConfig {
            requests_per_second: Some(10),
            requests_per_minute: Some(100),
            ..Default::default()
        });

        let limiter = ModelRateLimiter::new(config);

        // Should allow initial requests
        assert!(limiter.check_local().is_ok());
    }
}
