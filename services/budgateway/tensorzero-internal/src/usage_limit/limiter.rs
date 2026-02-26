use crate::error::{Error, ErrorDetails};
use crate::usage_limit::{UsageLimitDecision, UsageLimitStatus};
use moka::future::Cache;
use redis::AsyncCommands;
use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::Instant;
use tokio::sync::RwLock;
use tokio::time::{interval, timeout, Duration};
use tracing::{debug, error, info, warn};

/// Check if a Redis error indicates a broken connection that requires reconnection
fn is_connection_error(err: &redis::RedisError) -> bool {
    // Check for error kinds that are definitively connection-related first.
    // This avoids expensive string allocation for common I/O errors.
    if matches!(
        err.kind(),
        redis::ErrorKind::IoError | redis::ErrorKind::BusyLoadingError
    ) {
        return true;
    }

    // For other error kinds, fall back to string matching.
    let err_str = err.to_string().to_lowercase();
    err_str.contains("broken pipe")
        || err_str.contains("connection reset")
        || err_str.contains("connection refused")
        || err_str.contains("connection closed")
        || err_str.contains("not connected")
        || err_str.contains("eof")
        || err_str.contains("socket")
        || err_str.contains("timed out")
}

/// Usage limit information from Redis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UsageLimitInfo {
    pub user_id: String,
    #[serde(default = "default_user_type")]
    pub user_type: String, // "admin" or "client"
    pub allowed: bool,
    pub status: String,
    pub tokens_quota: Option<i64>,
    pub tokens_used: i64,
    pub cost_quota: Option<f64>,
    pub cost_used: f64,
    #[serde(default)]
    pub update_id: u64, // Incremented by budapp on each update
    pub reason: Option<String>,
    pub reset_at: Option<String>,
    pub last_updated: Option<String>,
    #[serde(default)]
    pub billing_cycle_start: Option<String>, // Track billing cycle
    #[serde(default)]
    pub billing_cycle_end: Option<String>, // When cycle ends
}

fn default_user_type() -> String {
    "client".to_string()
}

// RealtimeUsage struct removed - we now update the main usage_limit key directly

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
            cache_ttl_ms: 60000,    // 60 seconds cache (matches incremental sync interval)
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
                }
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

    /// Check if current usage is within quotas
    fn check_quotas(&self, status: &UsageLimitStatus) -> bool {
        // If already marked as not allowed, respect that
        if !status.allowed {
            return false;
        }

        // Check token quota
        if let Some(token_quota) = status.tokens_quota {
            if status.tokens_used > token_quota {
                return false;
            }
        }

        // Check cost quota
        if let Some(cost_quota) = status.cost_quota {
            if status.cost_used > cost_quota {
                return false;
            }
        }

        true
    }

    /// Check usage limits for a user with optional consumption tracking
    pub async fn check_usage(
        &self,
        user_id: &str,
        tokens_to_consume: Option<i64>,
        cost_to_consume: Option<f64>,
    ) -> UsageLimitDecision {
        // Check local cache first
        if let Some(mut cached) = self.cache.get(user_id).await {
            self.metrics.record_cache_hit();

            // Check if user is admin - admins have unlimited access
            if cached.user_type == "admin" {
                debug!("Admin user {} allowed - unlimited access", user_id);
                self.metrics.record_allowed();
                return UsageLimitDecision::Allow;
            }

            // If consuming, write atomic increments to Redis immediately
            if tokens_to_consume.is_some() || cost_to_consume.is_some() {
                if let Err(e) = self
                    .increment_realtime_usage(user_id, tokens_to_consume, cost_to_consume)
                    .await
                {
                    warn!(
                        "Failed to increment realtime usage for user {}: {}",
                        user_id, e
                    );
                    // Continue with local tracking as fallback
                }

                // Update local cache optimistically
                if let Some(tokens) = tokens_to_consume {
                    cached.tokens_used += tokens;
                    cached.realtime_tokens += tokens;
                }
                if let Some(cost) = cost_to_consume {
                    cached.cost_used += cost;
                    cached.realtime_cost += cost;
                }
                self.cache.insert(user_id.to_string(), cached.clone()).await;
            }

            // Check against quotas
            let quota_allowed = self.check_quotas(&cached);
            let overall_allowed = cached.allowed && quota_allowed;

            let decision = if overall_allowed {
                self.metrics.record_allowed();
                UsageLimitDecision::Allow
            } else {
                self.metrics.record_denied();
                UsageLimitDecision::Deny {
                    reason: cached
                        .reason
                        .clone()
                        .unwrap_or_else(|| "Usage limit exceeded".to_string()),
                }
            };
            return decision;
        }

        // Cache miss, try to fetch from Redis
        self.metrics.record_cache_miss();

        match self.fetch_usage_limit(user_id).await {
            Ok(Some(limit_info)) => {
                // Since we now update the main usage_limit key directly,
                // no need to fetch and combine realtime usage

                // Create status for caching directly from limit_info
                let status = UsageLimitStatus {
                    user_id: user_id.to_string(),
                    user_type: limit_info.user_type.clone(),
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
                    last_seen_update_id: limit_info.update_id,
                    realtime_tokens: 0, // No longer using separate realtime tracking
                    realtime_cost: 0.0, // No longer using separate realtime tracking
                };

                // Insert into cache
                self.cache.insert(user_id.to_string(), status.clone()).await;

                // Check if user is admin - admins have unlimited access
                if limit_info.user_type == "admin" {
                    debug!("Admin user {} allowed - unlimited access", user_id);
                    self.metrics.record_allowed();
                    return UsageLimitDecision::Allow;
                }

                let decision = if limit_info.allowed && self.check_quotas(&status) {
                    self.metrics.record_allowed();
                    UsageLimitDecision::Allow
                } else {
                    self.metrics.record_denied();
                    UsageLimitDecision::Deny {
                        reason: limit_info
                            .reason
                            .unwrap_or_else(|| "Usage limit exceeded".to_string()),
                    }
                };
                decision
            }
            Ok(None) => {
                // No limit info found - user has no billing plan (allow for freemium)
                debug!(
                    "No usage limit info for user {} - allowing (freemium)",
                    user_id
                );
                self.metrics.record_allowed();

                // Cache the allow decision for freemium user
                let status = UsageLimitStatus {
                    user_id: user_id.to_string(),
                    user_type: "client".to_string(), // Default to client for freemium
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
                    last_seen_update_id: 0,
                    realtime_tokens: 0,
                    realtime_cost: 0.0,
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

    /// Update usage counters directly in the main usage_limit key
    async fn increment_realtime_usage(
        &self,
        user_id: &str,
        tokens: Option<i64>,
        cost: Option<f64>,
    ) -> Result<(), Error> {
        let redis_client = self.redis_client.read().await;

        if let Some(mut conn) = redis_client.as_ref().map(|c| c.clone()) {
            let key = format!("usage_limit:{}", user_id);

            // Skip if nothing to increment
            if tokens.is_none() && cost.is_none() {
                return Ok(());
            }

            // Use Lua script for atomic increment operations on JSON fields
            let lua_script = r#"
                local key = KEYS[1]
                local tokens_delta = tonumber(ARGV[1])
                local cost_delta = tonumber(ARGV[2])

                local current = redis.call('GET', key)
                if not current then
                    return {err = "No usage limit data found"}
                end

                local data = cjson.decode(current)

                -- Atomically increment the fields
                if tokens_delta ~= 0 then
                    data.tokens_used = data.tokens_used + tokens_delta
                end
                if cost_delta ~= 0 then
                    data.cost_used = data.cost_used + cost_delta
                end

                local updated = cjson.encode(data)
                redis.call('SET', key, updated)

                -- Return the updated values for cache sync
                return {data.tokens_used, data.cost_used}
            "#;

            let tokens_delta = tokens.unwrap_or(0);
            let cost_delta = cost.unwrap_or(0.0);

            // Execute atomic Lua script
            let timeout_result = timeout(
                Duration::from_millis(self.config.redis_timeout_ms),
                redis::Script::new(lua_script)
                    .key(&key)
                    .arg(tokens_delta)
                    .arg(cost_delta)
                    .invoke_async(&mut conn),
            )
            .await;

            // Handle timeout - this might indicate connection issues
            let result: Result<Vec<redis::Value>, _> = match timeout_result {
                Ok(r) => r,
                Err(_) => {
                    warn!(
                        "Redis timeout on atomic increment, clearing connection for reconnection"
                    );
                    drop(redis_client);
                    self.clear_connection_for_reconnect().await;
                    return Err(Error::new(ErrorDetails::Config {
                        message: "Redis timeout on atomic increment".to_string(),
                    }));
                }
            };

            match result {
                Ok(values) => {
                    // Extract updated values for cache sync
                    if values.len() == 2 {
                        let new_tokens_used: i64 = redis::from_redis_value(&values[0]).unwrap_or(0);
                        let new_cost_used: f64 = redis::from_redis_value(&values[1]).unwrap_or(0.0);

                        // Update local cache with the atomically updated values
                        if let Some(cached) = self.cache.get(user_id).await {
                            let mut updated_cached = cached;
                            updated_cached.tokens_used = new_tokens_used;
                            updated_cached.cost_used = new_cost_used;
                            updated_cached.last_updated = Instant::now();
                            self.cache.insert(user_id.to_string(), updated_cached).await;
                        }
                    }
                    Ok(())
                }
                Err(e) => {
                    warn!("Redis atomic increment failed for user {}: {}", user_id, e);
                    // Check if this is a connection error and trigger reconnection
                    if is_connection_error(&e) {
                        warn!(
                            "Connection error detected during increment, clearing connection for reconnection: {}",
                            e
                        );
                        // Release read lock before acquiring write lock
                        drop(redis_client);
                        self.clear_connection_for_reconnect().await;
                    }
                    Err(Error::new(ErrorDetails::Config {
                        message: format!("Redis atomic increment error: {}", e),
                    }))
                }
            }
        } else {
            Err(Error::new(ErrorDetails::Config {
                message: "No Redis connection available".to_string(),
            }))
        }
    }

    // fetch_realtime_usage function removed - we now update the main usage_limit key directly

    /// Fetch usage limit from Redis with fallback key support
    async fn fetch_usage_limit(&self, user_id: &str) -> Result<Option<UsageLimitInfo>, Error> {
        self.metrics.record_redis_fetch();

        let redis_client = self.redis_client.read().await;

        if let Some(mut conn) = redis_client.as_ref().map(|c| c.clone()) {
            let key = format!("usage_limit:{}", user_id);

            // Get usage limit data from Redis
            let result = timeout(
                Duration::from_millis(self.config.redis_timeout_ms),
                conn.get::<_, Option<String>>(&key),
            )
            .await;

            match result {
                Ok(Ok(Some(data))) => {
                    // Parse the JSON data
                    match serde_json::from_str::<UsageLimitInfo>(&data) {
                        Ok(info) => {
                            debug!(
                                "Fetched usage limit for user {}: allowed={}",
                                user_id, info.allowed
                            );
                            return Ok(Some(info));
                        }
                        Err(e) => {
                            error!(
                                "Failed to parse usage limit data for user {}: {}",
                                user_id, e
                            );
                            Ok(None)
                        }
                    }
                }
                Ok(Ok(None)) => {
                    debug!("No usage limit found for user {}", user_id);
                    Ok(None)
                }
                Ok(Err(e)) => {
                    warn!(
                        "Redis error fetching usage limit for user {}: {}",
                        user_id, e
                    );
                    // Check if this is a connection error and trigger reconnection
                    if is_connection_error(&e) {
                        warn!(
                            "Connection error detected, clearing connection for reconnection: {}",
                            e
                        );
                        // Release read lock before acquiring write lock
                        drop(redis_client);
                        self.clear_connection_for_reconnect().await;
                    }
                    Err(Error::new(ErrorDetails::Config {
                        message: format!("Redis error: {}", e),
                    }))
                }
                Err(_) => {
                    warn!("Redis timeout fetching usage limit for user {}", user_id);
                    // Timeout might also indicate connection issues
                    drop(redis_client);
                    self.clear_connection_for_reconnect().await;
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
                        let scan_result: Result<
                            Result<(u64, Vec<String>), redis::RedisError>,
                            tokio::time::error::Elapsed,
                        > = timeout(
                            redis_timeout,
                            redis::cmd("SCAN")
                                .arg(clear_cursor)
                                .arg("MATCH")
                                .arg(clear_pattern)
                                .arg("COUNT")
                                .arg(100)
                                .query_async(&mut conn),
                        )
                        .await;

                        match scan_result {
                            Ok(Ok((new_cursor, keys))) => {
                                for key in keys {
                                    if let Some(user_id) = key.strip_prefix("usage_limit_clear:") {
                                        // Clear this user's cache
                                        cache.remove(user_id).await;
                                        debug!(
                                            "Cleared cache for user {} due to reset signal",
                                            user_id
                                        );

                                        // Delete the clear signal
                                        let _ = conn.del::<_, ()>(&key).await;
                                    }
                                }

                                clear_cursor = new_cursor;
                                if clear_cursor == 0 {
                                    break;
                                }
                            }
                            Ok(Err(e)) => {
                                // Redis error - check if connection error
                                if is_connection_error(&e) {
                                    warn!("Connection error in sync task (clear signals), triggering reconnect: {}", e);
                                    let mut guard = redis_client.write().await;
                                    *guard = None;
                                }
                                metrics.record_redis_error();
                                break;
                            }
                            Err(_) => {
                                // Timeout - might indicate connection issues
                                warn!("Timeout in sync task (clear signals), triggering reconnect");
                                let mut guard = redis_client.write().await;
                                *guard = None;
                                metrics.record_redis_error();
                                break;
                            }
                        }
                    }

                    // Use SCAN to get all usage_limit keys instead of iterating cache
                    // This ensures we get fresh data from Redis
                    let pattern = "usage_limit:*";
                    let mut cursor = 0u64;
                    let mut refreshed_count = 0;

                    loop {
                        let scan_result: Result<
                            Result<(u64, Vec<String>), redis::RedisError>,
                            tokio::time::error::Elapsed,
                        > = timeout(
                            redis_timeout,
                            redis::cmd("SCAN")
                                .arg(cursor)
                                .arg("MATCH")
                                .arg(pattern)
                                .arg("COUNT")
                                .arg(100)
                                .query_async(&mut conn),
                        )
                        .await;

                        match scan_result {
                            Ok(Ok((new_cursor, keys))) => {
                                for key in keys {
                                    // Extract user_id from key
                                    if let Some(user_id) = key.strip_prefix("usage_limit:") {
                                        // Fetch the main usage limit value
                                        match timeout(
                                            redis_timeout,
                                            conn.get::<_, Option<String>>(&key),
                                        )
                                        .await
                                        {
                                            Ok(Ok(Some(data))) => {
                                                if let Ok(info) =
                                                    serde_json::from_str::<UsageLimitInfo>(&data)
                                                {
                                                    // No need to fetch realtime usage - main key contains everything

                                                    // Simplified sync - just update cache with main usage_limit data
                                                    let status = UsageLimitStatus {
                                                        user_id: user_id.to_string(),
                                                        user_type: info.user_type,
                                                        allowed: info.allowed,
                                                        status: info.status,
                                                        tokens_quota: info.tokens_quota,
                                                        tokens_used: info.tokens_used,
                                                        cost_quota: info.cost_quota,
                                                        cost_used: info.cost_used,
                                                        reason: info.reason,
                                                        reset_at: info.reset_at,
                                                        billing_cycle_start: info
                                                            .billing_cycle_start,
                                                        billing_cycle_end: info.billing_cycle_end,
                                                        last_updated: Instant::now(),
                                                        last_seen_update_id: info.update_id,
                                                        realtime_tokens: 0, // No longer using separate realtime tracking
                                                        realtime_cost: 0.0, // No longer using separate realtime tracking
                                                    };
                                                    cache.insert(user_id.to_string(), status).await;
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
                            Ok(Err(e)) => {
                                // Redis error - check if connection error
                                if is_connection_error(&e) {
                                    warn!("Connection error in sync task (usage limits), triggering reconnect: {}", e);
                                    let mut guard = redis_client.write().await;
                                    *guard = None;
                                }
                                metrics.record_redis_error();
                                break;
                            }
                            Err(_) => {
                                // Timeout - might indicate connection issues
                                warn!("Timeout in sync task (usage limits), triggering reconnect");
                                let mut guard = redis_client.write().await;
                                *guard = None;
                                metrics.record_redis_error();
                                break;
                            }
                        }
                    }

                    if refreshed_count > 0 {
                        debug!(
                            "Refreshed {} usage limit entries from Redis",
                            refreshed_count
                        );
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

    /// Clear the Redis connection to trigger reconnection on next sync cycle
    /// This should be called when a connection error (like broken pipe) is detected
    async fn clear_connection_for_reconnect(&self) {
        let mut redis_guard = self.redis_client.write().await;
        if redis_guard.is_some() {
            warn!("Clearing stale Redis connection to trigger reconnection");
            *redis_guard = None;
        }
    }
}

// #[cfg(test)]
// #[path = "tests.rs"]
// mod tests;
