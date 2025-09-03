use crate::error::{Error, ErrorDetails};
use crate::usage_limit::{UsageLimitDecision, UsageLimitStatus};
use moka::future::Cache;
use redis::AsyncCommands;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Instant;
use tokio::sync::RwLock;
use tokio::time::{interval, timeout, Duration};
use tracing::{debug, warn, error, info};

/// Usage limit information from Redis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UsageLimitInfo {
    pub user_id: String,
    pub allowed: bool,
    pub status: String,
    pub tokens_quota: Option<i64>,
    pub tokens_used: i64,
    pub cost_quota: Option<f64>,
    pub cost_used: f64,
    pub prev_tokens_used: i64,
    pub prev_cost_used: f64,
    pub reason: Option<String>,
    pub reset_at: Option<String>,
    pub last_updated: Option<String>,
    pub billing_cycle_start: Option<String>,  // Track billing cycle
    pub billing_cycle_end: Option<String>,    // When cycle ends
}

/// Configuration for usage limiter
#[derive(Debug, Clone)]
pub struct UsageLimiterConfig {
    /// TTL for cached usage limit status (in milliseconds)
    pub cache_ttl_ms: u64,
    /// Interval for syncing with Redis (in milliseconds)
    pub sync_interval_ms: u64,
    /// Timeout for Redis operations (in milliseconds)
    pub redis_timeout_ms: u64,
    /// Whether to fail open (allow) or closed (deny) on errors
    pub fail_open: bool,
    /// Maximum number of entries in cache
    pub max_cache_size: u64,
}

impl Default for UsageLimiterConfig {
    fn default() -> Self {
        Self {
            cache_ttl_ms: 30000,    // 30 seconds cache (matches budapp sync interval)
            sync_interval_ms: 2000, // Sync every 2 seconds from Redis
            redis_timeout_ms: 100,  // 100ms Redis timeout
            fail_open: true,        // Allow on errors
            max_cache_size: 10000,  // 10k entries max
        }
    }
}

/// Metrics for usage limiter
#[derive(Debug, Default)]
pub struct UsageLimiterMetrics {
    pub cache_hits: AtomicU64,
    pub cache_misses: AtomicU64,
    pub redis_fetches: AtomicU64,
    pub redis_errors: AtomicU64,
    pub allowed_requests: AtomicU64,
    pub denied_requests: AtomicU64,
}

impl UsageLimiterMetrics {
    pub fn record_cache_hit(&self) {
        self.cache_hits.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_cache_miss(&self) {
        self.cache_misses.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_redis_fetch(&self) {
        self.redis_fetches.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_redis_error(&self) {
        self.redis_errors.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_allowed(&self) {
        self.allowed_requests.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_denied(&self) {
        self.denied_requests.fetch_add(1, Ordering::Relaxed);
    }
}

/// Usage limiter with local caching and Redis sync
pub struct UsageLimiter {
    /// High-performance local cache using moka
    cache: Arc<Cache<String, UsageLimitStatus>>,
    /// Redis connection pool
    redis_client: Arc<RwLock<Option<redis::aio::MultiplexedConnection>>>,
    /// Configuration
    config: UsageLimiterConfig,
    /// Redis URL for reconnection
    redis_url: String,
    /// Performance metrics
    metrics: Arc<UsageLimiterMetrics>,
}

impl UsageLimiter {
    /// Create a new usage limiter
    pub async fn new(redis_url: String, config: UsageLimiterConfig) -> Result<Self, Error> {
        // Initialize high-performance cache
        let cache = Cache::builder()
            .max_capacity(config.max_cache_size)
            .time_to_live(Duration::from_millis(config.cache_ttl_ms))
            .build();

        // Try to connect to Redis, but don't fail if it's unavailable
        let redis_conn = match redis::Client::open(redis_url.as_str()) {
            Ok(client) => match client.get_multiplexed_tokio_connection().await {
                Ok(conn) => {
                    info!("Connected to Redis for usage limiting");
                    Some(conn)
                },
                Err(e) => {
                    warn!("Failed to connect to Redis for usage limiting: {}", e);
                    None
                }
            },
            Err(e) => {
                warn!("Failed to create Redis client for usage limiting: {}", e);
                None
            }
        };

        let limiter = Self {
            cache: Arc::new(cache),
            redis_client: Arc::new(RwLock::new(redis_conn)),
            config,
            redis_url,
            metrics: Arc::new(UsageLimiterMetrics::default()),
        };

        // Start background sync task
        limiter.start_sync_task();

        Ok(limiter)
    }

    /// Check usage limits for a user with optional consumption tracking
    pub async fn check_usage(&self, user_id: &str, tokens_to_consume: Option<i64>, cost_to_consume: Option<f64>) -> UsageLimitDecision {
        // Check local cache first

        if let Some(mut cached) = self.cache.get(user_id).await {
            self.metrics.record_cache_hit();

            // If consuming, update local tracking
            if let Some(tokens) = tokens_to_consume {
                cached.local_tokens_consumed += tokens;
                cached.tokens_used += tokens;
            }
            if let Some(cost) = cost_to_consume {
                cached.local_cost_consumed += cost;
                cached.cost_used += cost;
            }

            // Check against quotas
            let allowed = self.check_quotas(&cached);

            debug!("Usage limit cache hit for user {}: allowed={}, tokens_used={}, cost_used={}",
                   user_id, allowed, cached.tokens_used, cached.cost_used);

            // Update cache with new consumption
            if tokens_to_consume.is_some() || cost_to_consume.is_some() {
                self.cache.insert(user_id.to_string(), cached.clone()).await;
            }

            let decision = if allowed {
                self.metrics.record_allowed();
                UsageLimitDecision::Allow
            } else {
                self.metrics.record_denied();
                UsageLimitDecision::Deny {
                    reason: cached.reason.clone().unwrap_or_else(|| "Usage limit exceeded".to_string()),
                }
            };
            return decision;
        }

        // Cache miss, try to fetch from Redis
        self.metrics.record_cache_miss();
        debug!("Usage limit cache miss for user {}, fetching from Redis", user_id);

        match self.fetch_usage_limit(user_id).await {
            Ok(Some(limit_info)) => {
                // Create status for caching with usage tracking
                let status = UsageLimitStatus {
                    user_id: user_id.to_string(),
                    allowed: limit_info.allowed,
                    status: limit_info.status.clone(),
                    tokens_quota: limit_info.tokens_quota,
                    tokens_used: limit_info.tokens_used,
                    cost_quota: limit_info.cost_quota,
                    cost_used: limit_info.cost_used,
                    reason: limit_info.reason.clone(),
                    reset_at: limit_info.reset_at.clone(),
                    billing_cycle_start: limit_info.billing_cycle_start.clone(),
                    billing_cycle_end: limit_info.billing_cycle_end.clone(),
                    last_updated: Instant::now(),
                    local_tokens_consumed: 0,
                    local_cost_consumed: 0.0,
                };

                // Insert into cache
                self.cache.insert(user_id.to_string(), status.clone()).await;

                let decision = if limit_info.allowed {
                    self.metrics.record_allowed();
                    UsageLimitDecision::Allow
                } else {
                    self.metrics.record_denied();
                    UsageLimitDecision::Deny {
                        reason: limit_info.reason.unwrap_or_else(|| "Usage limit exceeded".to_string()),
                    }
                };
                decision
            }
            Ok(None) => {
                // No limit info found - user has no billing plan (allow for freemium)
                debug!("No usage limit info for user {} - allowing (freemium)", user_id);
                self.metrics.record_allowed();

                // Cache the allow decision for freemium user
                let status = UsageLimitStatus {
                    user_id: user_id.to_string(),
                    allowed: true,
                    status: "no_billing_plan".to_string(),
                    tokens_quota: None,
                    tokens_used: 0,
                    cost_quota: None,
                    cost_used: 0.0,
                    reason: Some("No billing plan - freemium user".to_string()),
                    reset_at: None,
                    billing_cycle_start: None,
                    billing_cycle_end: None,
                    last_updated: Instant::now(),
                    local_tokens_consumed: 0,
                    local_cost_consumed: 0.0,
                };
                self.cache.insert(user_id.to_string(), status).await;

                UsageLimitDecision::Allow
            }
            Err(e) => {
                self.metrics.record_redis_error();
                warn!("Failed to fetch usage limit for user {}: {}", user_id, e);

                // Use fail-open/closed configuration
                if self.config.fail_open {
                    self.metrics.record_allowed();
                    UsageLimitDecision::Allow
                } else {
                    self.metrics.record_denied();
                    UsageLimitDecision::Deny {
                        reason: "Unable to verify usage limits".to_string(),
                    }
                }
            }
        }
    }

    /// Fetch usage limit from Redis
    async fn fetch_usage_limit(&self, user_id: &str) -> Result<Option<UsageLimitInfo>, Error> {
        self.metrics.record_redis_fetch();

        let redis_client = self.redis_client.read().await;

        if let Some(mut conn) = redis_client.as_ref().map(|c| c.clone()) {
            let key = format!("usage_limit:{}", user_id);

            // Use timeout for Redis operation
            let result = timeout(
                Duration::from_millis(self.config.redis_timeout_ms),
                conn.get::<_, Option<String>>(&key)
            ).await;

            match result {
                Ok(Ok(Some(data))) => {
                    // Parse the JSON data
                    match serde_json::from_str::<UsageLimitInfo>(&data) {
                        Ok(info) => {
                            debug!("Fetched usage limit for user {}: allowed={}", user_id, info.allowed);
                            Ok(Some(info))
                        },
                        Err(e) => {
                            error!("Failed to parse usage limit data for user {}: {}", user_id, e);
                            Ok(None)
                        }
                    }
                }
                Ok(Ok(None)) => {
                    debug!("No usage limit found in Redis for user {}", user_id);
                    Ok(None)
                },
                Ok(Err(e)) => {
                    warn!("Redis error fetching usage limit for user {}: {}", user_id, e);
                    Err(Error::new(ErrorDetails::Config {
                        message: format!("Redis error: {}", e),
                    }))
                }
                Err(_) => {
                    warn!("Redis timeout fetching usage limit for user {}", user_id);
                    Err(Error::new(ErrorDetails::Config {
                        message: "Redis timeout".to_string(),
                    }))
                }
            }
        } else {
            // No Redis connection
            debug!("No Redis connection available for usage limiting");
            Err(Error::new(ErrorDetails::Config {
                message: "No Redis connection available".to_string(),
            }))
        }
    }

    /// Start background task to sync usage limits
    fn start_sync_task(&self) {
        let cache = self.cache.clone();
        let redis_client = self.redis_client.clone();
        let redis_url = self.redis_url.clone();
        let sync_interval = Duration::from_millis(self.config.sync_interval_ms);
        let redis_timeout = Duration::from_millis(self.config.redis_timeout_ms);
        let metrics = self.metrics.clone();

        tokio::spawn(async move {
            let mut sync_timer = interval(sync_interval);

            loop {
                sync_timer.tick().await;

                // Try to ensure Redis connection
                let mut redis_guard = redis_client.write().await;
                if redis_guard.is_none() {
                    // Try to reconnect
                    match redis::Client::open(redis_url.as_str()) {
                        Ok(client) => {
                            if let Ok(conn) = client.get_multiplexed_tokio_connection().await {
                                *redis_guard = Some(conn);
                                info!("Reconnected to Redis for usage limiting");
                            }
                        }
                        Err(e) => {
                            debug!("Failed to reconnect to Redis: {}", e);
                            continue;
                        }
                    }
                }

                if let Some(mut conn) = redis_guard.as_ref().map(|c| c.clone()) {
                    drop(redis_guard); // Release the lock early

                    // First, check for any cache clear signals
                    let clear_pattern = "usage_limit_clear:*";
                    let mut clear_cursor = 0u64;

                    // Check for cache clear signals
                    loop {
                        let scan_result: Result<Result<(u64, Vec<String>), redis::RedisError>, tokio::time::error::Elapsed> = timeout(
                            redis_timeout,
                            redis::cmd("SCAN")
                                .arg(clear_cursor)
                                .arg("MATCH")
                                .arg(clear_pattern)
                                .arg("COUNT")
                                .arg(100)
                                .query_async(&mut conn)
                        ).await;

                        match scan_result {
                            Ok(Ok((new_cursor, keys))) => {
                                for key in keys {
                                    if let Some(user_id) = key.strip_prefix("usage_limit_clear:") {
                                        // Clear this user's cache
                                        cache.remove(user_id).await;
                                        debug!("Cleared cache for user {} due to reset signal", user_id);

                                        // Delete the clear signal
                                        let _ = conn.del::<_, ()>(&key).await;
                                    }
                                }

                                clear_cursor = new_cursor;
                                if clear_cursor == 0 {
                                    break;
                                }
                            }
                            _ => break,
                        }
                    }

                    // Use SCAN to get all usage_limit keys instead of iterating cache
                    // This ensures we get fresh data from Redis
                    let pattern = "usage_limit:*";
                    let mut cursor = 0u64;
                    let mut refreshed_count = 0;

                    loop {
                        let scan_result: Result<Result<(u64, Vec<String>), redis::RedisError>, tokio::time::error::Elapsed> = timeout(
                            redis_timeout,
                            redis::cmd("SCAN")
                                .arg(cursor)
                                .arg("MATCH")
                                .arg(pattern)
                                .arg("COUNT")
                                .arg(100)
                                .query_async(&mut conn)
                        ).await;

                        match scan_result {
                            Ok(Ok((new_cursor, keys))) => {
                                for key in keys {
                                    // Extract user_id from key
                                    if let Some(user_id) = key.strip_prefix("usage_limit:") {
                                        // Fetch the value
                                        match timeout(redis_timeout, conn.get::<_, Option<String>>(&key)).await {
                                            Ok(Ok(Some(data))) => {
                                                if let Ok(info) = serde_json::from_str::<UsageLimitInfo>(&data) {
                                                    // Get existing cache entry if it exists
                                                    if let Some(mut cached) = cache.get(user_id).await {
                                                        // Check for billing cycle reset
                                                        let cycle_reset = cached.billing_cycle_start != info.billing_cycle_start;

                                                        if cycle_reset {
                                                            // Billing cycle has reset - use new values directly
                                                            debug!("Billing cycle reset detected for user {}", user_id);
                                                            cached.tokens_used = info.tokens_used;
                                                            cached.cost_used = info.cost_used;
                                                            cached.local_tokens_consumed = 0;
                                                            cached.local_cost_consumed = 0.0;
                                                        } else {
                                                            // Normal delta reconciliation
                                                            let token_delta = info.tokens_used - info.prev_tokens_used;
                                                            let cost_delta = info.cost_used - info.prev_cost_used;

                                                            // Apply deltas plus local consumption
                                                            let new_tokens = cached.tokens_used + token_delta + cached.local_tokens_consumed;
                                                            let new_cost = cached.cost_used + cost_delta + cached.local_cost_consumed;

                                                            // Use higher value (Redis or calculated)
                                                            cached.tokens_used = new_tokens.max(info.tokens_used);
                                                            cached.cost_used = f64::max(new_cost, info.cost_used);

                                                            // Reset local consumption after applying it
                                                            cached.local_tokens_consumed = 0;
                                                            cached.local_cost_consumed = 0.0;
                                                        }

                                                        // Update other fields
                                                        cached.tokens_quota = info.tokens_quota;
                                                        cached.cost_quota = info.cost_quota;
                                                        cached.status = info.status;
                                                        cached.reason = info.reason;
                                                        cached.reset_at = info.reset_at;
                                                        cached.billing_cycle_start = info.billing_cycle_start.clone();
                                                        cached.billing_cycle_end = info.billing_cycle_end.clone();
                                                        cached.last_updated = Instant::now();

                                                        cache.insert(user_id.to_string(), cached).await;
                                                    } else {
                                                        // No existing cache, create new entry
                                                        let status = UsageLimitStatus {
                                                            user_id: user_id.to_string(),
                                                            allowed: info.allowed,
                                                            status: info.status,
                                                            tokens_quota: info.tokens_quota,
                                                            tokens_used: info.tokens_used,
                                                            cost_quota: info.cost_quota,
                                                            cost_used: info.cost_used,
                                                            reason: info.reason,
                                                            reset_at: info.reset_at,
                                                            billing_cycle_start: info.billing_cycle_start,
                                                            billing_cycle_end: info.billing_cycle_end,
                                                            last_updated: Instant::now(),
                                                            local_tokens_consumed: 0,
                                                            local_cost_consumed: 0.0,
                                                        };
                                                        cache.insert(user_id.to_string(), status).await;
                                                    }
                                                    refreshed_count += 1;
                                                }
                                            }
                                            _ => {}
                                        }
                                    }
                                }

                                cursor = new_cursor;
                                if cursor == 0 {
                                    break;
                                }
                            }
                            _ => {
                                metrics.record_redis_error();
                                break;
                            }
                        }
                    }

                    if refreshed_count > 0 {
                        debug!("Refreshed {} usage limit entries from Redis", refreshed_count);
                    }
                }
            }
        });
    }

    /// Clear the cache for a specific user
    pub async fn clear_user_cache(&self, user_id: &str) {
        self.cache.remove(user_id).await;
    }

    /// Clear all cached entries
    pub async fn clear_cache(&self) {
        self.cache.invalidate_all();
    }

    /// Get metrics
    pub fn get_metrics(&self) -> UsageLimiterMetrics {
        UsageLimiterMetrics {
            cache_hits: AtomicU64::new(self.metrics.cache_hits.load(Ordering::Relaxed)),
            cache_misses: AtomicU64::new(self.metrics.cache_misses.load(Ordering::Relaxed)),
            redis_fetches: AtomicU64::new(self.metrics.redis_fetches.load(Ordering::Relaxed)),
            redis_errors: AtomicU64::new(self.metrics.redis_errors.load(Ordering::Relaxed)),
            allowed_requests: AtomicU64::new(self.metrics.allowed_requests.load(Ordering::Relaxed)),
            denied_requests: AtomicU64::new(self.metrics.denied_requests.load(Ordering::Relaxed)),
        }
    }

    /// Get cache entry count
    pub fn get_cache_size(&self) -> u64 {
        self.cache.entry_count()
    }

    /// Check if usage is within quotas
    fn check_quotas(&self, status: &UsageLimitStatus) -> bool {
        // Check token quota
        if let Some(quota) = status.tokens_quota {
            if status.tokens_used >= quota {
                return false;
            }
        }

        // Check cost quota
        if let Some(quota) = status.cost_quota {
            if status.cost_used >= quota {
                return false;
            }
        }

        true
    }

    /// Update cache entry with new data from Redis using delta logic
    fn reconcile_cache_with_redis(&self, cached: &mut UsageLimitStatus, redis_info: &UsageLimitInfo) {
        // Calculate deltas from Redis
        let token_delta = redis_info.tokens_used - redis_info.prev_tokens_used;
        let cost_delta = redis_info.cost_used - redis_info.prev_cost_used;

        // Apply deltas to cached values
        let new_tokens_used = cached.tokens_used + token_delta;
        let new_cost_used = cached.cost_used + cost_delta;

        // Reconciliation: if calculated value is less than Redis value, use Redis value
        cached.tokens_used = if new_tokens_used < redis_info.tokens_used {
            redis_info.tokens_used
        } else {
            new_tokens_used
        };

        cached.cost_used = if new_cost_used < redis_info.cost_used {
            redis_info.cost_used
        } else {
            new_cost_used
        };

        // Update quotas and other fields
        cached.tokens_quota = redis_info.tokens_quota;
        cached.cost_quota = redis_info.cost_quota;
        cached.status = redis_info.status.clone();
        cached.reason = redis_info.reason.clone();
        cached.reset_at = redis_info.reset_at.clone();

        // Reset local consumption tracking after sync
        cached.local_tokens_consumed = 0;
        cached.local_cost_consumed = 0.0;
        cached.last_updated = Instant::now();
    }
}
