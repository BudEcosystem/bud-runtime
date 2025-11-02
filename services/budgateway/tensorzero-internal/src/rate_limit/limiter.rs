use crate::error::{Error, ErrorDetails};
use crate::rate_limit::{
    config::{RateLimitAlgorithm, RateLimitConfig},
    RateLimitDecision, RateLimitHeaders, RateLimiterMetrics,
};
use crate::redis_client::RedisClient;
use dashmap::DashMap;
use futures::StreamExt;
use governor::{
    clock::{Clock, QuantaClock, QuantaInstant, Reference},
    middleware::NoOpMiddleware,
    state::{InMemoryState, NotKeyed},
    Quota, RateLimiter,
};
use moka::future::Cache;
// Redis connection managed by RedisClient
use redis::{AsyncCommands, Script};
use serde::{Deserialize, Serialize};
use std::num::NonZeroU32;
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::sync::RwLock;
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
    local_consumed: Arc<std::sync::atomic::AtomicU32>, // Track local usage since cache
    #[expect(dead_code)] // May be used in future for more sophisticated caching
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
        let consumed = self
            .local_consumed
            .load(std::sync::atomic::Ordering::Relaxed);

        // Check if we have local quota remaining
        if consumed < self.remaining {
            // Atomically increment and check again
            let new_consumed = self
                .local_consumed
                .fetch_add(1, std::sync::atomic::Ordering::Relaxed)
                + 1;

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
        let consumed = self
            .local_consumed
            .load(std::sync::atomic::Ordering::Relaxed);
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
    pub(crate) redis_client: Arc<RedisClient>,

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

    /// Track local consumption per key for background sync
    local_consumption: Arc<DashMap<String, Arc<AtomicU32>>>,
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
            local_consumption: Arc::new(DashMap::new()),
        })
    }

    /// Add or update a model's rate limit configuration
    pub fn update_model_config(&self, model: String, config: RateLimitConfig) {
        let limiter = Arc::new(ModelRateLimiter::new(Arc::new(config)));
        self.local_limiters.insert(model, limiter);

        // Clear cache entries for this model
        // Note: moka doesn't have pattern-based invalidation, so we'd need to track keys
    }

    /// Remove a model's rate limit configuration
    pub fn remove_model_config(&self, model: &str) {
        self.local_limiters.remove(model);
        debug!("Removed rate limit configuration for model: {}", model);
    }

    /// Update rate limit configurations from model table changes
    /// This integrates with the existing model table update mechanism
    pub fn sync_from_model_table(&self, models: &crate::model::ModelTable) {
        let current_models: std::collections::HashSet<String> = self
            .local_limiters
            .iter()
            .map(|entry| entry.key().clone())
            .collect();

        let mut updated_models = std::collections::HashSet::new();

        // Update or add configurations from the model table
        for (model_name, model_config) in models.iter() {
            updated_models.insert(model_name.to_string());

            if let Some(rate_config) = &model_config.rate_limits {
                // Check if this is a new configuration or an update
                let needs_update = match self.local_limiters.get(model_name.as_ref()) {
                    Some(_existing) => {
                        // Compare configurations to see if update is needed
                        // For simplicity, we'll always update if rate_limits is present
                        true
                    }
                    None => true, // New model with rate limits
                };

                if needs_update {
                    debug!("Syncing rate limit config for model: {}", model_name);
                    self.update_model_config(model_name.to_string(), rate_config.clone());
                }
            } else {
                // Model doesn't have rate limits configured, remove if it exists
                if current_models.contains(model_name.as_ref()) {
                    debug!(
                        "Removing rate limit config for model (no longer configured): {}",
                        model_name
                    );
                    self.remove_model_config(model_name);
                }
            }
        }

        // Remove configurations for models that are no longer in the model table
        for old_model in current_models {
            if !updated_models.contains(&old_model) {
                debug!(
                    "Removing rate limit config for deleted model: {}",
                    old_model
                );
                self.remove_model_config(&old_model);
            }
        }
    }

    /// Check rate limit for a model and API key
    pub async fn check_rate_limit(
        &self,
        model: &str,
        api_key: &str,
    ) -> Result<RateLimitDecision, Error> {
        let start = tokio::time::Instant::now();

        // Skip cache check if local_allowance is 1.0 (always local)
        let dashmap_start = tokio::time::Instant::now();
        if let Some(limiter) = self.local_limiters.get(model) {
            let dashmap_time = dashmap_start.elapsed();
            if limiter.config.local_allowance >= 1.0 {
                // Fast path for 100% local allowance - skip all cache/Redis logic
                let governor_start = tokio::time::Instant::now();
                match limiter.check_local() {
                    Ok(_) => {
                        let governor_time = governor_start.elapsed();
                        self.metrics.record_local_allow();
                        debug!(
                            "Fast path timing - DashMap: {:?}, Governor: {:?}, Total: {:?}",
                            dashmap_time,
                            governor_time,
                            start.elapsed()
                        );
                        let (limit, window_seconds) =
                            if let Some(rps) = limiter.config.requests_per_second {
                                (rps, 1)
                            } else if let Some(rpm) = limiter.config.requests_per_minute {
                                (rpm, 60)
                            } else if let Some(rph) = limiter.config.requests_per_hour {
                                (rph, 3600)
                            } else {
                                (1000, 60) // Default fallback
                            };

                        let headers = RateLimitHeaders {
                            limit,
                            remaining: limit - 1,
                            reset: get_unix_timestamp() + window_seconds,
                            retry_after: None,
                        };
                        return Ok(RateLimitDecision::Allow(headers));
                    }
                    Err(_) => {
                        let (limit, window_seconds) =
                            if let Some(rps) = limiter.config.requests_per_second {
                                (rps, 1)
                            } else if let Some(rpm) = limiter.config.requests_per_minute {
                                (rpm, 60)
                            } else if let Some(rph) = limiter.config.requests_per_hour {
                                (rph, 3600)
                            } else {
                                (1000, 60) // Default fallback
                            };

                        let headers = RateLimitHeaders {
                            limit,
                            remaining: 0,
                            reset: get_unix_timestamp() + window_seconds,
                            retry_after: Some(window_seconds as u32),
                        };
                        return Ok(RateLimitDecision::Deny(headers));
                    }
                }
            }
        }

        let cache_key = format!("{model}:{api_key}");
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

        // Fast path 2: On cache miss, ALWAYS use local governor immediately
        // But spawn background task to refresh cache from Redis
        if let Some(limiter) = self.local_limiters.get(model) {
            // Spawn background Redis refresh (fire and forget)
            let cache_for_refresh = Arc::clone(&self.cache);
            let cache_key_for_refresh = cache_key.clone();
            let model_for_refresh = model.to_string();
            let api_key_for_refresh = api_key.to_string();
            let redis_client = Arc::clone(&self.redis_client);
            let config_clone = Arc::clone(&limiter.config);

            tokio::spawn(async move {
                // Try to get fresh data from Redis in background
                if let Ok(mut conn) = redis_client.get_connection().await {
                    let key = format!("rl:{model_for_refresh}:{api_key_for_refresh}");

                    // Just get the current count - don't increment here
                    // The background sync will handle incrementing
                    if let Ok(count) = conn.get::<_, Option<u32>>(&key).await {
                        let count = count.unwrap_or(0);

                        // Get the appropriate limit and window based on config
                        let (limit, window_seconds) = match config_clone.algorithm {
                            RateLimitAlgorithm::FixedWindow => {
                                // Use the most restrictive limit
                                if let Some(rps) = config_clone.requests_per_second {
                                    (rps, 1)
                                } else if let Some(rpm) = config_clone.requests_per_minute {
                                    (rpm, 60)
                                } else if let Some(rph) = config_clone.requests_per_hour {
                                    (rph, 3600)
                                } else {
                                    (1000, 60) // Default fallback
                                }
                            }
                            _ => (1000, 60), // Default for other algorithms
                        };

                        let remaining = limit.saturating_sub(count);
                        let cached = CachedRateLimit {
                            remaining,
                            limit,
                            local_consumed: Arc::new(std::sync::atomic::AtomicU32::new(0)),
                            reset_at: QuantaClock::default().now()
                                + Duration::from_secs(window_seconds).into(),
                            cached_at: QuantaClock::default().now(),
                            ttl: Duration::from_millis(config_clone.cache_ttl_ms),
                        };
                        cache_for_refresh
                            .insert(cache_key_for_refresh, cached)
                            .await;
                    }

                    // Note: expiry is already handled by the background sync process
                    // which has access to the proper window configuration
                }
            });

            // Always use local decision first for speed
            match limiter.check_local() {
                Ok(_) => {
                    self.metrics.record_local_allow();

                    // Track local consumption for this key
                    let consumption_entry = self
                        .local_consumption
                        .entry(cache_key.clone())
                        .or_insert_with(|| Arc::new(AtomicU32::new(0)));
                    consumption_entry.fetch_add(1, Ordering::Relaxed);

                    // Use proper headers based on config
                    let (limit, window_seconds) =
                        if let Some(rps) = limiter.config.requests_per_second {
                            (rps, 1)
                        } else if let Some(rpm) = limiter.config.requests_per_minute {
                            (rpm, 60)
                        } else if let Some(rph) = limiter.config.requests_per_hour {
                            (rph, 3600)
                        } else {
                            (1000, 60) // Default fallback
                        };

                    let headers = RateLimitHeaders {
                        limit,
                        remaining: limit - 1, // Approximate
                        reset: get_unix_timestamp() + window_seconds,
                        retry_after: None,
                    };

                    // Also update cache with local result immediately
                    let cached = CachedRateLimit {
                        remaining: limit - 1,
                        limit,
                        local_consumed: Arc::new(std::sync::atomic::AtomicU32::new(1)),
                        reset_at: QuantaClock::default().now()
                            + Duration::from_secs(window_seconds).into(),
                        cached_at: QuantaClock::default().now(),
                        ttl: Duration::from_millis(limiter.config.cache_ttl_ms),
                    };
                    self.cache.insert(cache_key.clone(), cached).await;

                    return Ok(RateLimitDecision::Allow(headers));
                }
                Err(_retry_at) => {
                    // Local limit exceeded, return deny immediately
                    let (limit, window_seconds) =
                        if let Some(rps) = limiter.config.requests_per_second {
                            (rps, 1)
                        } else if let Some(rpm) = limiter.config.requests_per_minute {
                            (rpm, 60)
                        } else if let Some(rph) = limiter.config.requests_per_hour {
                            (rph, 3600)
                        } else {
                            (1000, 60) // Default fallback
                        };

                    let headers = RateLimitHeaders {
                        limit,
                        remaining: 0,
                        reset: get_unix_timestamp() + window_seconds,
                        retry_after: Some(window_seconds as u32),
                    };
                    return Ok(RateLimitDecision::Deny(headers));
                }
            }
        }

        // Slow path: Check with Redis
        self.metrics.record_cache_miss();
        self.check_redis_with_timeout(model, api_key).await
    }

    /// Check rate limit with Redis, using timeout for performance
    async fn check_redis_with_timeout(
        &self,
        model: &str,
        api_key: &str,
    ) -> Result<RateLimitDecision, Error> {
        let key = format!("rl:{model}:{api_key}");

        // Get the rate limit config for this model
        // If model not found, fall back to local fallback (allows unknown models)
        let config = match self.local_limiters.get(model) {
            Some(limiter) => Arc::clone(&limiter.config),
            None => {
                debug!(
                    model = model,
                    "Model not configured for rate limiting, allowing request"
                );
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
        let remaining = u32::try_from(result[1]).unwrap_or(0);
        let limit = u32::try_from(result[2]).unwrap_or(0);
        let reset_at = if result.len() > 3 {
            u64::try_from(result[3]).unwrap_or_else(|_| get_unix_timestamp() + 60)
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
                Some(u32::try_from(reset_at.saturating_sub(get_unix_timestamp())).unwrap_or(0))
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
            // Get the window from the model configuration
            let (limit, window_seconds) = if let Some(rps) = limiter.config.requests_per_second {
                (rps, 1)
            } else if let Some(rpm) = limiter.config.requests_per_minute {
                (rpm, 60)
            } else if let Some(rph) = limiter.config.requests_per_hour {
                (rph, 3600)
            } else {
                (1000, 60) // Default fallback
            };

            match limiter.check_local() {
                Ok(_) => {
                    let headers = RateLimitHeaders {
                        limit,
                        remaining: limit - 1, // Approximate
                        reset: get_unix_timestamp() + window_seconds,
                        retry_after: None,
                    };
                    Ok(RateLimitDecision::Allow(headers))
                }
                Err(_retry_at) => {
                    let headers = RateLimitHeaders {
                        limit,
                        remaining: 0,
                        reset: get_unix_timestamp() + window_seconds,
                        retry_after: Some(window_seconds as u32),
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

    /// Start background synchronization with Redis
    pub async fn start_background_sync(&self) {
        // Get all necessary components
        let redis_client = Arc::clone(&self.redis_client);
        let local_consumption = Arc::clone(&self.local_consumption);
        let local_limiters = Arc::clone(&self.local_limiters);

        // Get sync interval from first model config (or use default)
        let sync_interval_ms = self
            .local_limiters
            .iter()
            .next()
            .map(|entry| entry.value().config.sync_interval_ms)
            .unwrap_or(100);

        let handle = tokio::spawn(async move {
            let mut sync_interval = interval(Duration::from_millis(sync_interval_ms));
            sync_interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);

            loop {
                sync_interval.tick().await;

                // Sync local consumption to Redis
                if let Ok(mut conn) = redis_client.get_connection().await {
                    // Collect all entries to sync
                    let mut entries_to_sync = Vec::new();
                    for entry in local_consumption.iter() {
                        let key = entry.key().clone();
                        let count = entry.value().swap(0, Ordering::Relaxed);
                        if count > 0 {
                            entries_to_sync.push((key, count));
                        }
                    }

                    // Sync each entry to Redis
                    for (cache_key, count) in entries_to_sync {
                        // Extract model and api_key from cache key (format: "model:api_key")
                        if let Some(colon_pos) = cache_key.find(':') {
                            let model = &cache_key[..colon_pos];
                            let redis_key = format!("rl:{cache_key}");

                            // Increment by the local count
                            let _: Result<(), _> = conn.incr(&redis_key, count).await;

                            // Determine the appropriate window based on model configuration
                            let window_seconds = if let Some(limiter) = local_limiters.get(model) {
                                // Get the window from the most restrictive limit
                                if limiter.config.requests_per_second.is_some() {
                                    1
                                } else if limiter.config.requests_per_minute.is_some() {
                                    60
                                } else if limiter.config.requests_per_hour.is_some() {
                                    3600
                                } else {
                                    60 // Default to 60 seconds if no limits configured
                                }
                            } else {
                                60 // Default to 60 seconds if model not found
                            };

                            // Set expiry with the appropriate window
                            let _: Result<(), _> = conn.expire(&redis_key, window_seconds).await;

                            debug!(
                                "Synced {} requests for key {} with {}s window",
                                count, cache_key, window_seconds
                            );
                        }
                    }
                }

                // debug!("Background sync completed");
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
    pub fn start_pubsub_listener(&self) -> Result<(), Error> {
        let redis_client = Arc::clone(&self.redis_client);
        let local_limiters = Arc::clone(&self.local_limiters);
        let cache = Arc::clone(&self.cache);

        let handle = tokio::spawn(async move {
            loop {
                match Self::run_pubsub_listener(&redis_client, &local_limiters, &cache).await {
                    Ok(()) => {
                        warn!("Pub/sub listener stream ended, reconnecting in 5 seconds");
                        tokio::time::sleep(Duration::from_secs(5)).await;
                    }
                    Err(e) => {
                        warn!("Pub/sub listener error: {}, retrying in 5 seconds", e);
                        tokio::time::sleep(Duration::from_secs(5)).await;
                    }
                }
            }
        });

        // Store handle for cleanup - spawn a task to store it since we can't await here
        let handle_for_storage = Arc::clone(&self.pubsub_handle);
        tokio::spawn(async move {
            if let Ok(mut pubsub_handle_guard) = handle_for_storage.try_write() {
                *pubsub_handle_guard = Some(handle);
            } else {
                warn!("Failed to store pub/sub handle - could not acquire write lock");
            }
        });

        debug!("Started pub/sub listener for rate limit configuration updates");
        Ok(())
    }

    /// Internal function to run the pub/sub listener
    async fn run_pubsub_listener(
        redis_client: &RedisClient,
        local_limiters: &Arc<DashMap<String, Arc<ModelRateLimiter>>>,
        cache: &Arc<Cache<String, CachedRateLimit>>,
    ) -> Result<(), Error> {
        // Get a connection for pub/sub
        let mut pubsub_conn = redis_client.client.get_async_pubsub().await.map_err(|e| {
            Error::new(ErrorDetails::InternalError {
                message: format!("Failed to get Redis pub/sub connection: {e}"),
            })
        })?;

        // Subscribe to rate limit configuration updates
        pubsub_conn
            .psubscribe("rate_limit:config:*")
            .await
            .map_err(|e| {
                Error::new(ErrorDetails::InternalError {
                    message: format!("Failed to subscribe to rate limit config updates: {e}"),
                })
            })?;

        debug!("Listening for rate limit configuration updates on rate_limit:config:*");

        let mut stream = pubsub_conn.on_message();
        while let Some(msg) = stream.next().await {
            let channel: String = msg.get_channel_name().to_string();

            // Extract model name from channel (format: rate_limit:config:model_name)
            let model_name = if let Some(model_name) = channel.strip_prefix("rate_limit:config:") {
                model_name.to_string()
            } else {
                warn!("Received message from unexpected channel: {}", channel);
                continue;
            };

            let payload: String = match msg.get_payload() {
                Ok(p) => p,
                Err(e) => {
                    warn!("Failed to decode rate limit config message: {}", e);
                    continue;
                }
            };

            if let Err(e) =
                Self::handle_config_update(&model_name, &payload, local_limiters, cache).await
            {
                warn!(
                    "Failed to handle rate limit config update for model {}: {}",
                    model_name, e
                );
            }
        }

        Ok(())
    }

    /// Handle a configuration update message
    async fn handle_config_update(
        model_name: &str,
        payload: &str,
        local_limiters: &Arc<DashMap<String, Arc<ModelRateLimiter>>>,
        _cache: &Arc<Cache<String, CachedRateLimit>>,
    ) -> Result<(), Error> {
        let update: ConfigUpdate = serde_json::from_str(payload).map_err(|e| {
            Error::new(ErrorDetails::InternalError {
                message: format!("Failed to parse config update: {e}"),
            })
        })?;

        match update.action.as_str() {
            "create" | "update" => {
                if let Some(config) = update.config {
                    debug!("Updating rate limit config for model: {}", model_name);

                    // Create new rate limiter with updated config
                    let limiter = Arc::new(ModelRateLimiter::new(Arc::new(config)));
                    local_limiters.insert(model_name.to_string(), limiter);

                    // Invalidate cache entries for this model
                    // Since moka doesn't have pattern-based invalidation, we'll let entries expire naturally
                    // or implement a more sophisticated cache key tracking system if needed

                    debug!(
                        "Successfully updated rate limit config for model: {}",
                        model_name
                    );
                } else {
                    warn!(
                        "Received create/update action without config for model: {}",
                        model_name
                    );
                }
            }
            "delete" => {
                debug!("Removing rate limit config for model: {}", model_name);
                local_limiters.remove(model_name);

                // Note: Cache entries will expire naturally or could be invalidated
                // if we implement cache key tracking

                debug!(
                    "Successfully removed rate limit config for model: {}",
                    model_name
                );
            }
            _ => {
                warn!(
                    "Unknown config update action: {} for model: {}",
                    update.action, model_name
                );
            }
        }

        Ok(())
    }

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
                message: format!("Failed to serialize config update: {e}"),
            })
        })?;

        let channel = format!("rate_limit:config:{model_name}");

        // Use a multiplexed connection for publishing
        let mut conn = redis_client.get_connection().await.map_err(|e| {
            Error::new(ErrorDetails::InternalError {
                message: format!("Failed to get Redis connection for publishing: {e}"),
            })
        })?;

        let _: i32 = conn.publish(&channel, &payload).await.map_err(|e| {
            Error::new(ErrorDetails::InternalError {
                message: format!("Failed to publish config update: {e}"),
            })
        })?;

        debug!(
            "Published config update for model {}: {}",
            model_name, action
        );
        Ok(())
    }
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
