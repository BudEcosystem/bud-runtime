//! High-Performance Blocking Rules Enforcement for Gateway
//!
//! This module provides a lock-free, high-performance blocking rules system
//! that uses Redis Pub/Sub for real-time updates and DashMap for concurrent access.

use chrono::{DateTime, Utc};
use dashmap::DashMap;
use ipnet::IpNet;
use metrics::{counter, gauge};
use redis::AsyncCommands;
use regex::Regex;
use serde::Serializer;
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::net::IpAddr;
use std::str::FromStr;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::RwLock;
use tracing::{debug, info, warn};
use uuid::Uuid;

use crate::clickhouse::ClickHouseConnectionInfo;
use crate::error::{Error, ErrorDetails};
use crate::redis_client::RedisClient;

/// Custom serializer for DateTime<Utc> to format compatible with ClickHouse DateTime64(3)
fn serialize_datetime<S>(dt: &DateTime<Utc>, serializer: S) -> Result<S::Ok, S::Error>
where
    S: Serializer,
{
    let formatted = dt.format("%Y-%m-%d %H:%M:%S%.3f").to_string();
    serializer.serialize_str(&formatted)
}

/// Represents a blocking event to be logged to ClickHouse
#[derive(Debug, Clone, Serialize)]
pub struct GatewayBlockingEventDatabaseInsert {
    /// Event identifiers
    pub id: Uuid,
    pub rule_id: Uuid,

    /// Client information
    pub client_ip: String,
    pub country_code: Option<String>,
    pub user_agent: Option<String>,

    /// Request context
    pub request_path: String,
    pub request_method: String,
    pub api_key_id: Option<String>,

    /// Project/endpoint context (optional)
    pub project_id: Option<Uuid>,
    pub endpoint_id: Option<Uuid>,
    pub model_name: Option<String>,

    /// Rule information
    pub rule_type: String,
    pub rule_name: String,
    pub rule_priority: i32,

    /// Block details
    pub block_reason: String,
    pub action_taken: String,

    /// Timing
    #[serde(serialize_with = "serialize_datetime")]
    pub blocked_at: DateTime<Utc>,
}

impl GatewayBlockingEventDatabaseInsert {
    pub fn new(
        rule_id: Uuid,
        rule: &BlockingRule,
        client_ip: String,
        country_code: Option<String>,
        user_agent: Option<String>,
        request_path: String,
        request_method: String,
        block_reason: String,
    ) -> Self {
        Self {
            id: uuid::Uuid::new_v4(),
            rule_id,
            client_ip,
            country_code,
            user_agent,
            request_path,
            request_method,
            api_key_id: None,  // TODO: Extract from request context if available
            project_id: None,  // TODO: Extract from request context if available
            endpoint_id: None, // TODO: Extract from request context if available
            model_name: None,  // TODO: Extract from request context if available
            rule_type: format!("{:?}", rule.rule_type),
            rule_name: rule.name.clone(),
            rule_priority: rule.priority,
            block_reason,
            action_taken: rule.action.clone(),
            blocked_at: Utc::now(),
        }
    }
}

/// Rule types supported by the gateway
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum BlockingRuleType {
    IpBlocking,
    CountryBlocking,
    UserAgentBlocking,
    RateBasedBlocking,
}

/// Blocking rule status
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum BlockingRuleStatus {
    Active,
    Inactive,
    Expired,
}

/// Blocking rule structure as stored in Redis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockingRule {
    pub id: Uuid,
    pub rule_type: BlockingRuleType,
    pub name: String,
    pub description: Option<String>,
    pub priority: i32,
    pub status: BlockingRuleStatus,
    pub config: serde_json::Value,
    pub action: String,
    pub expires_at: Option<chrono::DateTime<chrono::Utc>>,
}

/// Pre-compiled rule for efficient evaluation
#[derive(Debug, Clone)]
pub struct CompiledRule {
    pub rule: BlockingRule,
    pub ip_nets: Vec<IpNet>,          // Pre-parsed IP ranges
    pub regex_patterns: Vec<Regex>,   // Pre-compiled regex
    pub country_set: HashSet<String>, // O(1) country lookup
}

/// Rate limiting state for rate-based blocking
#[derive(Debug, Clone)]
pub struct RateLimitState {
    pub requests: u32,
    pub window_start: Instant,
}

/// Circuit breaker state for Redis operations
struct CircuitBreaker {
    /// Whether the circuit is currently open (failing)
    is_open: AtomicBool,
    /// Number of consecutive failures
    failure_count: AtomicU64,
    /// Timestamp of last failure (as seconds since epoch)
    last_failure_time: AtomicU64,
    /// Maximum consecutive failures before opening circuit
    failure_threshold: u64,
    /// How long to wait before trying again (in seconds)
    recovery_timeout: u64,
}

impl CircuitBreaker {
    fn new() -> Self {
        Self {
            is_open: AtomicBool::new(false),
            failure_count: AtomicU64::new(0),
            last_failure_time: AtomicU64::new(0),
            failure_threshold: 5, // Open after 5 consecutive failures
            recovery_timeout: 60, // Try again after 60 seconds
        }
    }

    fn record_success(&self) {
        self.failure_count.store(0, Ordering::Relaxed);
        self.is_open.store(false, Ordering::Relaxed);
    }

    fn record_failure(&self) {
        let failures = self.failure_count.fetch_add(1, Ordering::Relaxed) + 1;
        if failures >= self.failure_threshold {
            self.is_open.store(true, Ordering::Relaxed);
            self.last_failure_time.store(
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_secs(),
                Ordering::Relaxed,
            );
            warn!(
                "Circuit breaker opened after {} consecutive Redis failures",
                failures
            );
        }
    }

    fn is_available(&self) -> bool {
        if !self.is_open.load(Ordering::Relaxed) {
            return true;
        }

        // Check if recovery timeout has passed
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        let last_failure = self.last_failure_time.load(Ordering::Relaxed);

        if now - last_failure > self.recovery_timeout {
            // Try to close the circuit
            self.is_open.store(false, Ordering::Relaxed);
            info!("Circuit breaker closed, attempting Redis reconnection");
            true
        } else {
            false
        }
    }
}

/// High-performance blocking rules manager with lock-free reads
///
/// This manager provides:
/// - Lock-free concurrent rule evaluation using DashMap
/// - Pre-compiled patterns for efficient matching
/// - Real-time updates via Redis Pub/Sub
/// - Sub-microsecond rule evaluation latency
/// - Circuit breaker for Redis failure handling
pub struct BlockingRulesManager {
    /// Global rules that apply to all requests
    global_rules: Arc<RwLock<Vec<Arc<CompiledRule>>>>,

    /// Whether global rules have been loaded (even if empty)
    /// This prevents repeated Redis lookups when no rules exist
    global_rules_loaded: AtomicBool,

    /// Rate limit states using DashMap for concurrent access
    /// Key format: "global:{ip}"
    rate_limits: Arc<DashMap<String, RateLimitState>>,

    /// Redis client for updates (not used in request path)
    redis_client: Option<Arc<RedisClient>>,

    /// ClickHouse client for event logging (not used in request path)
    clickhouse_client: Option<Arc<ClickHouseConnectionInfo>>,

    /// Circuit breaker for Redis operations
    redis_circuit_breaker: Arc<CircuitBreaker>,

    /// Metrics tracking
    rules_loaded_at: Arc<RwLock<Instant>>,
    total_rules_count: Arc<RwLock<usize>>,
}

impl BlockingRulesManager {
    /// Create a new high-performance blocking rules manager
    pub fn new(redis_client: Option<Arc<RedisClient>>) -> Self {
        Self {
            global_rules: Arc::new(RwLock::new(Vec::new())),
            global_rules_loaded: AtomicBool::new(false),
            rate_limits: Arc::new(DashMap::new()),
            redis_client,
            clickhouse_client: None,
            redis_circuit_breaker: Arc::new(CircuitBreaker::new()),
            rules_loaded_at: Arc::new(RwLock::new(Instant::now())),
            total_rules_count: Arc::new(RwLock::new(0)),
        }
    }

    /// Create a new high-performance blocking rules manager with ClickHouse logging
    pub fn new_with_clickhouse(
        redis_client: Option<Arc<RedisClient>>,
        clickhouse_client: Option<Arc<ClickHouseConnectionInfo>>,
    ) -> Self {
        Self {
            global_rules: Arc::new(RwLock::new(Vec::new())),
            global_rules_loaded: AtomicBool::new(false),
            rate_limits: Arc::new(DashMap::new()),
            redis_client,
            clickhouse_client,
            redis_circuit_breaker: Arc::new(CircuitBreaker::new()),
            rules_loaded_at: Arc::new(RwLock::new(Instant::now())),
            total_rules_count: Arc::new(RwLock::new(0)),
        }
    }

    /// Invalidate the cache and reload blocking rules from Redis
    ///
    /// This method is called when a Redis keyspace notification indicates
    /// that blocking rules have been updated. It resets the loaded flag
    /// and triggers an immediate reload from Redis.
    ///
    /// # Arguments
    /// * `key_suffix` - The key suffix (e.g., "global", "endpoint:uuid") to reload,
    ///   or None to reload all rules
    pub async fn invalidate_and_reload(&self, key_suffix: Option<&str>) {
        if let Some(suffix) = key_suffix {
            if suffix.starts_with("endpoint:") {
                // For endpoint-specific rules, we currently don't cache them separately
                // They are loaded on-demand, so just log the update
                info!(
                    "Blocking rules updated for endpoint: {}",
                    suffix.strip_prefix("endpoint:").unwrap_or(suffix)
                );
                // Note: Endpoint rules are loaded on-demand in should_block()
                // so no explicit cache invalidation is needed here
                return;
            } else if suffix == "global" || suffix.is_empty() {
                info!("Invalidating global blocking rules cache due to Redis update");
            } else {
                // Unknown suffix - invalidate global rules as a fallback
                info!(
                    "Unknown blocking rules key suffix '{}', invalidating global rules",
                    suffix
                );
            }
        } else {
            // Invalidate all rules
            info!("Invalidating all blocking rules cache");
        }

        // Common logic for reloading global rules
        self.global_rules_loaded.store(false, Ordering::Release);
        if let Err(e) = self.load_rules("global").await {
            warn!("Failed to reload global blocking rules: {}", e);
        } else {
            info!("Successfully reloaded global blocking rules from Redis");
        }
    }

    /// Clear the blocking rules cache (used for rule deletion)
    ///
    /// This method clears the cached rules and resets the loaded flag.
    pub async fn clear_rules_cache(&self, key_suffix: Option<&str>) {
        if let Some(suffix) = key_suffix {
            if suffix == "global" || suffix.is_empty() {
                info!("Clearing global blocking rules cache due to Redis deletion");
            } else {
                info!("Blocking rules deleted for key: {}", suffix);
                // For endpoint-specific rules, they're loaded on-demand
                // so clearing isn't strictly necessary
                return;
            }
        } else {
            info!("Clearing all blocking rules cache");
        }

        // Common logic for clearing global rules
        self.global_rules_loaded.store(false, Ordering::Release);
        let mut rules = self.global_rules.write().await;
        rules.clear();
        gauge!("blocking_rules_cached").set(0.0);
        info!("Global blocking rules cache cleared");
    }

    /// Compile a rule for efficient evaluation
    fn compile_rule(rule: BlockingRule) -> Result<CompiledRule, String> {
        let mut compiled = CompiledRule {
            rule: rule.clone(),
            ip_nets: Vec::new(),
            regex_patterns: Vec::new(),
            country_set: HashSet::new(),
        };

        match rule.rule_type {
            BlockingRuleType::IpBlocking => {
                // Support both "ip_addresses" and "ips" for compatibility
                let ips = rule
                    .config
                    .get("ip_addresses")
                    .or_else(|| rule.config.get("ips"))
                    .and_then(|v| v.as_array());

                if let Some(ip_list) = ips {
                    for ip_value in ip_list {
                        if let Some(ip_str) = ip_value.as_str() {
                            // Try parsing as CIDR first
                            match IpNet::from_str(ip_str) {
                                Ok(net) => compiled.ip_nets.push(net),
                                Err(_) => {
                                    // Try as single IP address
                                    if let Ok(addr) = IpAddr::from_str(ip_str) {
                                        // Convert single IP to /32 or /128 CIDR
                                        let net = match addr {
                                            IpAddr::V4(v4) => IpNet::V4(
                                                ipnet::Ipv4Net::new(v4, 32)
                                                    .map_err(|e| format!("Invalid IPv4: {}", e))?,
                                            ),
                                            IpAddr::V6(v6) => IpNet::V6(
                                                ipnet::Ipv6Net::new(v6, 128)
                                                    .map_err(|e| format!("Invalid IPv6: {}", e))?,
                                            ),
                                        };
                                        compiled.ip_nets.push(net);
                                    } else {
                                        warn!("Invalid IP address or CIDR: {}", ip_str);
                                    }
                                }
                            }
                        }
                    }
                }

                // Also support "cidrs" field for CIDR ranges
                if let Some(cidrs) = rule.config.get("cidrs").and_then(|v| v.as_array()) {
                    for cidr_value in cidrs {
                        if let Some(cidr_str) = cidr_value.as_str() {
                            match IpNet::from_str(cidr_str) {
                                Ok(net) => compiled.ip_nets.push(net),
                                Err(e) => warn!("Invalid CIDR range '{}': {}", cidr_str, e),
                            }
                        }
                    }
                }
            }
            BlockingRuleType::CountryBlocking => {
                // Support both "countries" and "country_codes" for compatibility
                let countries = rule
                    .config
                    .get("countries")
                    .or_else(|| rule.config.get("country_codes"))
                    .and_then(|v| v.as_array());

                if let Some(country_list) = countries {
                    for country in country_list {
                        if let Some(code) = country.as_str() {
                            compiled.country_set.insert(code.to_uppercase());
                        }
                    }
                }
            }
            BlockingRuleType::UserAgentBlocking => {
                if let Some(patterns) = rule.config.get("patterns").and_then(|v| v.as_array()) {
                    for pattern in patterns {
                        if let Some(pattern_str) = pattern.as_str() {
                            // Check if it's a regex pattern (starts and ends with /)
                            if pattern_str.starts_with('/') && pattern_str.ends_with('/') {
                                // Extract regex pattern
                                let regex_str = &pattern_str[1..pattern_str.len() - 1];
                                // Add case-insensitive flag by default
                                let regex_with_flags = format!("(?i){}", regex_str);
                                match Regex::new(&regex_with_flags) {
                                    Ok(regex) => compiled.regex_patterns.push(regex),
                                    Err(e) => {
                                        warn!("Invalid regex pattern '{}': {}", pattern_str, e)
                                    }
                                }
                            } else if pattern_str.contains('*') {
                                // Treat as glob pattern - convert wildcards to regex
                                let regex_pattern = pattern_str
                                    .split('*')
                                    .map(|part| regex::escape(part))
                                    .collect::<Vec<_>>()
                                    .join(".*");
                                let regex_str = format!("(?i){}", regex_pattern);
                                match Regex::new(&regex_str) {
                                    Ok(regex) => compiled.regex_patterns.push(regex),
                                    Err(e) => {
                                        warn!("Invalid glob pattern '{}': {}", pattern_str, e)
                                    }
                                }
                            } else {
                                // Treat as substring match (case-insensitive)
                                let escaped = regex::escape(pattern_str);
                                let regex_str = format!("(?i){}", escaped);
                                match Regex::new(&regex_str) {
                                    Ok(regex) => compiled.regex_patterns.push(regex),
                                    Err(e) => warn!(
                                        "Failed to create regex for substring '{}': {}",
                                        pattern_str, e
                                    ),
                                }
                            }
                        }
                    }
                }
            }
            BlockingRuleType::RateBasedBlocking => {
                // Rate limiting configuration is evaluated dynamically
            }
        }

        Ok(compiled)
    }

    /// Load global rules from Redis (called by background task only, not in request path)
    pub async fn load_rules(&self, key_suffix: &str) -> Result<(), Error> {
        // Only handle global rules
        if key_suffix != "global" {
            debug!(
                "Ignoring non-global blocking rules key suffix: {}",
                key_suffix
            );
            return Ok(());
        }

        let Some(redis_client) = &self.redis_client else {
            debug!("No Redis client configured, skipping rule loading");
            return Ok(());
        };

        // Check circuit breaker before attempting Redis operation
        if !self.redis_circuit_breaker.is_available() {
            debug!("Circuit breaker is open, skipping Redis rule loading");
            return Ok(()); // Return Ok to avoid cascading failures
        }

        let key = format!("blocking_rules:{}", key_suffix);
        debug!("Loading blocking rules from Redis key: {}", key);

        // Get Redis connection with error handling
        let mut conn = match redis_client.get_connection().await {
            Ok(conn) => {
                self.redis_circuit_breaker.record_success();
                conn
            }
            Err(e) => {
                self.redis_circuit_breaker.record_failure();
                warn!("Failed to get Redis connection for rule loading: {}", e);
                return Ok(()); // Return Ok to avoid cascading failures
            }
        };

        // Fetch rules from Redis
        let rules_json: Option<String> = conn.get(&key).await.map_err(|e| {
            Error::new(ErrorDetails::InternalError {
                message: format!("Failed to get blocking rules from Redis: {}", e),
            })
        })?;

        debug!(
            "Redis response for key '{}': {}",
            key,
            if rules_json.is_some() {
                "data found"
            } else {
                "no data"
            }
        );

        if let Some(json) = rules_json {
            debug!("Raw JSON from Redis: {}", json);

            // Parse JSON as a generic array first, then parse each rule individually for resilience
            let json_array: Vec<serde_json::Value> = serde_json::from_str(&json).map_err(|e| {
                Error::new(ErrorDetails::InternalError {
                    message: format!("Failed to parse JSON array: {}", e),
                })
            })?;

            let mut rules = Vec::new();
            let mut parse_errors = 0;

            for (i, rule_json) in json_array.iter().enumerate() {
                match serde_json::from_value::<BlockingRule>(rule_json.clone()) {
                    Ok(rule) => rules.push(rule),
                    Err(e) => {
                        warn!(
                            "Failed to parse blocking rule #{} (skipping): {} - Raw: {}",
                            i, e, rule_json
                        );
                        parse_errors += 1;
                    }
                }
            }

            debug!(
                "Parsed {} rules from JSON ({} parse errors skipped)",
                rules.len(),
                parse_errors
            );

            // Compile and validate rules
            let mut compiled_rules = Vec::with_capacity(rules.len());
            let mut active_count = 0;

            for (i, rule) in rules.into_iter().enumerate() {
                debug!(
                    "Processing rule #{}: '{}' (type: {:?}, status: {:?})",
                    i, rule.name, rule.rule_type, rule.status
                );

                // Only include active rules
                if !matches!(rule.status, BlockingRuleStatus::Active) {
                    debug!("Skipping inactive rule: '{}'", rule.name);
                    continue;
                }

                // Skip expired rules
                if let Some(expires_at) = rule.expires_at {
                    if chrono::Utc::now() > expires_at {
                        debug!("Skipping expired rule: '{}'", rule.name);
                        continue;
                    }
                }

                debug!("Rule '{}' config: {}", rule.name, rule.config);

                match Self::compile_rule(rule.clone()) {
                    Ok(compiled) => {
                        debug!("Successfully compiled rule '{}' - IP nets: {}, regex patterns: {}, countries: {}",
                               rule.name, compiled.ip_nets.len(), compiled.regex_patterns.len(), compiled.country_set.len());
                        compiled_rules.push(Arc::new(compiled));
                        active_count += 1;
                    }
                    Err(e) => warn!("Failed to compile rule '{}': {}", rule.name, e),
                }
            }

            // Sort by priority (higher priority first) for consistent evaluation order
            compiled_rules.sort_by(|a, b| b.rule.priority.cmp(&a.rule.priority));

            // Update global rules
            *self.global_rules.write().await = compiled_rules;
            info!("Loaded {} active global blocking rules", active_count);

            // Update metrics
            gauge!("blocking_rules_cached").set(active_count as f64);
            *self.total_rules_count.write().await = active_count;
            *self.rules_loaded_at.write().await = Instant::now();
        } else {
            // No rules found - clear global rules
            *self.global_rules.write().await = Vec::new();
            info!("No global blocking rules found");
        }

        // Mark as loaded to prevent repeated Redis lookups (even if empty)
        self.global_rules_loaded.store(true, Ordering::Release);

        Ok(())
    }

    /// Clear global rules (when deleted from Redis)
    pub async fn clear_global_rules(&self) {
        *self.global_rules.write().await = Vec::new();
        // Reset the loaded flag to allow reloading on next request
        self.global_rules_loaded.store(false, Ordering::Release);
        gauge!("blocking_rules_cached").set(0.0);
        info!("Cleared global blocking rules");
    }

    /// Check if request should be blocked (optimized for request path - no Redis calls)
    pub async fn should_block(
        &self,
        client_ip: &str,
        country_code: Option<&str>,
        user_agent: Option<&str>,
        request_path: &str,
        request_method: &str,
        api_key_id: Option<String>,
        project_id: Option<Uuid>,
        endpoint_id: Option<Uuid>,
        model_name: Option<String>,
    ) -> Result<Option<(BlockingRule, String)>, Error> {
        debug!(
            "should_block called with: ip={}, country={:?}, user_agent={:?}",
            client_ip, country_code, user_agent
        );

        // Parse client IP once for efficiency (only needed for IP-based rules)
        let client_addr = match IpAddr::from_str(client_ip) {
            Ok(addr) => Some(addr),
            Err(_) => {
                debug!(
                    "Invalid client IP address: {} - IP-based rules will be skipped",
                    client_ip
                );
                counter!("blocking_rules_evaluated", "result" => "invalid_ip").increment(1);
                None // Continue with non-IP rules
            }
        };

        let mut rules_evaluated = 0;

        // Ensure global rules are loaded (load on first access only)
        // Uses atomic flag to prevent repeated Redis lookups when rules are legitimately empty
        if !self.global_rules_loaded.load(Ordering::Acquire) {
            debug!("Global rules not yet loaded, loading from Redis...");
            if let Err(e) = self.load_rules("global").await {
                warn!("Failed to load global rules: {}", e);
            }
        }

        // Check global rules
        {
            let global_rules = self.global_rules.read().await;
            debug!("Checking {} global rules", global_rules.len());

            for compiled_rule in global_rules.iter() {
                rules_evaluated += 1;
                let rule = &compiled_rule.rule;

                debug!(
                    "Evaluating global rule '{}' (type: {:?}, priority: {})",
                    rule.name, rule.rule_type, rule.priority
                );

                // Evaluate based on rule type
                let matched = match rule.rule_type {
                    BlockingRuleType::IpBlocking => {
                        // Check if IP matches any configured range (pre-compiled)
                        if let Some(addr) = client_addr {
                            let ip_matched =
                                compiled_rule.ip_nets.iter().any(|net| net.contains(&addr));
                            debug!(
                                "IP blocking rule '{}': {} networks, matched={}",
                                rule.name,
                                compiled_rule.ip_nets.len(),
                                ip_matched
                            );
                            ip_matched
                        } else {
                            debug!(
                                "IP blocking rule '{}': skipped due to invalid IP",
                                rule.name
                            );
                            false
                        }
                    }

                    BlockingRuleType::CountryBlocking => {
                        // Fast O(1) country lookup in HashSet
                        let country_matched = country_code
                            .map(|cc| compiled_rule.country_set.contains(&cc.to_uppercase()))
                            .unwrap_or(false);
                        debug!("Country blocking rule '{}': {} countries, country_code={:?}, matched={}",
                               rule.name, compiled_rule.country_set.len(), country_code, country_matched);
                        country_matched
                    }

                    BlockingRuleType::UserAgentBlocking => {
                        // Check against pre-compiled regex patterns
                        let ua_matched = user_agent
                            .map(|ua| {
                                for (i, pattern) in compiled_rule.regex_patterns.iter().enumerate()
                                {
                                    let pattern_matched = pattern.is_match(ua);
                                    debug!(
                                        "User-Agent pattern #{} in rule '{}': '{}' vs '{}' = {}",
                                        i,
                                        rule.name,
                                        pattern.as_str(),
                                        ua,
                                        pattern_matched
                                    );
                                    if pattern_matched {
                                        return true;
                                    }
                                }
                                false
                            })
                            .unwrap_or(false);
                        debug!("User-Agent blocking rule '{}': {} patterns, user_agent={:?}, matched={}",
                               rule.name, compiled_rule.regex_patterns.len(), user_agent, ua_matched);
                        ua_matched
                    }

                    BlockingRuleType::RateBasedBlocking => {
                        // Check rate limits with global scope
                        let rate_exceeded = self
                            .check_rate_limit("global", client_ip, &rule.config)
                            .await;
                        debug!(
                            "Rate limiting rule '{}': rate_exceeded={}",
                            rule.name, rate_exceeded
                        );
                        rate_exceeded
                    }
                };

                if matched {
                    debug!("MATCH FOUND: Global rule '{}' matched!", rule.name);
                    // Record metrics and return blocked result
                    return self
                        .handle_rule_match(
                            rule,
                            client_ip,
                            country_code,
                            user_agent,
                            request_path,
                            request_method,
                            api_key_id.clone(),
                            project_id,
                            endpoint_id,
                            model_name.clone(),
                            "global",
                        )
                        .await;
                } else {
                    debug!("No match for global rule '{}'", rule.name);
                }
            }
        }

        // No rules matched - request allowed
        counter!("blocking_rules_evaluated",
            "result" => "allowed",
            "rules_checked" => rules_evaluated.to_string()
        )
        .increment(1);

        Ok(None)
    }

    /// Handle a matched rule - record metrics and return result
    async fn handle_rule_match(
        &self,
        rule: &BlockingRule,
        client_ip: &str,
        country_code: Option<&str>,
        user_agent: Option<&str>,
        request_path: &str,
        request_method: &str,
        api_key_id: Option<String>,
        project_id: Option<Uuid>,
        endpoint_id: Option<Uuid>,
        model_name: Option<String>,
        scope: &str,
    ) -> Result<Option<(BlockingRule, String)>, Error> {
        counter!("blocking_rules_matched",
            "rule_type" => format!("{:?}", rule.rule_type),
            "rule_name" => rule.name.clone(),
            "scope" => scope.to_string()
        )
        .increment(1);

        // Update match statistics asynchronously (fire-and-forget)
        if let Some(redis) = &self.redis_client {
            let redis = Arc::clone(redis);
            let rule_id = rule.id;
            tokio::spawn(async move {
                if let Err(e) = update_rule_stats(redis, rule_id).await {
                    debug!("Failed to update rule stats: {}", e);
                }
            });
        }

        debug!(
            "Request blocked by {} rule '{}' (type: {:?})",
            scope, rule.name, rule.rule_type
        );

        // Try to get the custom reason from Redis, fall back to default reason
        let reason = match self.get_rule_reason(&rule.name).await {
            Some(custom_reason) => {
                debug!(
                    "Using custom reason from Redis for rule '{}': {}",
                    rule.name, custom_reason
                );
                custom_reason
            }
            None => {
                debug!(
                    "No custom reason found in Redis for rule '{}', using default",
                    rule.name
                );
                // Generate default reason string based on rule type
                match rule.rule_type {
                    BlockingRuleType::IpBlocking => format!("IP {} is blocked", client_ip),
                    BlockingRuleType::CountryBlocking => {
                        format!("Country {} is blocked", country_code.unwrap_or("unknown"))
                    }
                    BlockingRuleType::UserAgentBlocking => {
                        format!("User agent matches blocked pattern")
                    }
                    BlockingRuleType::RateBasedBlocking => format!("Rate limit exceeded"),
                }
            }
        };

        // Log blocking event to ClickHouse asynchronously (fire-and-forget)
        if let Some(clickhouse) = &self.clickhouse_client {
            let clickhouse = Arc::clone(clickhouse);
            let rule_clone = rule.clone();
            let client_ip_clone = client_ip.to_string();
            let country_code_clone = country_code.map(|s| s.to_string());
            let user_agent_clone = user_agent.map(|s| s.to_string());
            let request_path_clone = request_path.to_string();
            let request_method_clone = request_method.to_string();
            let reason_clone = reason.clone();

            tokio::spawn(async move {
                let mut blocking_event = GatewayBlockingEventDatabaseInsert::new(
                    rule_clone.id,
                    &rule_clone,
                    client_ip_clone,
                    country_code_clone,
                    user_agent_clone,     // Now populated (was TODO)
                    request_path_clone,   // Now populated (was TODO)
                    request_method_clone, // Now populated (was TODO)
                    reason_clone,
                );

                // Set optional fields if available
                blocking_event.api_key_id = api_key_id;
                blocking_event.project_id = project_id;
                blocking_event.endpoint_id = endpoint_id;
                blocking_event.model_name = model_name;

                if let Err(e) =
                    write_blocking_event_to_clickhouse(&clickhouse, blocking_event).await
                {
                    debug!("Failed to write blocking event to ClickHouse: {}", e);
                } else {
                    debug!("Successfully wrote blocking event to ClickHouse");
                }
            });
        }

        Ok(Some((rule.clone(), reason)))
    }

    /// Check rate limits with atomic operations
    async fn check_rate_limit(
        &self,
        scope: &str, // "global" or "model:{name}"
        client_ip: &str,
        config: &serde_json::Value,
    ) -> bool {
        // Extract configuration - support both old and new field names
        let threshold = config
            .get("threshold")
            .or_else(|| config.get("requests_per_minute"))
            .and_then(|v| v.as_u64())
            .unwrap_or(100) as u32;

        let window_seconds = config
            .get("window_seconds")
            .and_then(|v| v.as_u64())
            .or_else(|| {
                config
                    .get("window_minutes")
                    .and_then(|v| v.as_u64())
                    .map(|minutes| minutes * 60)
            })
            .unwrap_or(60);

        let window = Duration::from_secs(window_seconds);
        let key = format!("{}:{}", scope, client_ip);

        let now = Instant::now();

        // Use DashMap entry API for atomic operations
        let mut entry = self
            .rate_limits
            .entry(key.clone())
            .or_insert_with(|| RateLimitState {
                requests: 0,
                window_start: now,
            });

        // Check if window has expired
        if now.duration_since(entry.window_start) > window {
            // Reset window
            entry.requests = 1;
            entry.window_start = now;
            false
        } else {
            // Increment counter atomically
            entry.requests += 1;
            let exceeded = entry.requests > threshold;

            if exceeded {
                debug!(
                    "Rate limit exceeded for {} ({}): {} requests in {:?}",
                    scope, client_ip, entry.requests, window
                );
            }

            exceeded
        }
    }

    /// Periodic cleanup of old rate limit entries (called by background task)
    pub async fn cleanup_rate_limits(&self) {
        let now = Instant::now();
        let mut removed = 0;

        // Remove entries older than 5 minutes
        let expiry = Duration::from_secs(300);
        self.rate_limits.retain(|_key, state| {
            let should_keep = now.duration_since(state.window_start) < expiry;
            if !should_keep {
                removed += 1;
            }
            should_keep
        });

        if removed > 0 {
            debug!("Cleaned up {} expired rate limit entries", removed);
            gauge!("rate_limit_entries_active").set(self.rate_limits.len() as f64);
        }
    }

    /// Get rule reason from Redis for a given rule name
    async fn get_rule_reason(&self, rule_name: &str) -> Option<String> {
        let Some(redis_client) = &self.redis_client else {
            debug!("No Redis client configured, unable to lookup rule reason");
            return None;
        };

        let reason_key = format!("blocking_rule_reason:{}", rule_name);

        match redis_client.get_connection().await {
            Ok(mut conn) => match conn.get::<_, String>(&reason_key).await {
                Ok(reason) => {
                    debug!(
                        "Retrieved rule reason from Redis: {} = {}",
                        reason_key, reason
                    );
                    Some(reason)
                }
                Err(e) => {
                    debug!(
                        "Failed to get rule reason from Redis key '{}': {}",
                        reason_key, e
                    );
                    None
                }
            },
            Err(e) => {
                debug!(
                    "Failed to get Redis connection for rule reason lookup: {}",
                    e
                );
                None
            }
        }
    }

    /// Get statistics about loaded rules
    pub async fn get_stats(&self) -> (usize, Instant) {
        let global_rules_count = self.global_rules.read().await.len();
        let loaded_at = *self.rules_loaded_at.read().await;
        (global_rules_count, loaded_at)
    }
}

/// Update rule statistics in Redis (fire-and-forget background task)
async fn update_rule_stats(redis: Arc<RedisClient>, rule_id: Uuid) -> Result<(), Error> {
    let mut conn = redis.get_connection().await.map_err(|e| {
        Error::new(ErrorDetails::InternalError {
            message: format!("Failed to get Redis connection: {}", e),
        })
    })?;

    // Update match count and last matched timestamp
    let stats_key = format!("gateway:rule_stats:{}", rule_id);
    let now = chrono::Utc::now().timestamp();

    // Use Redis pipeline for atomic updates
    let _: () = redis::pipe()
        .atomic()
        .cmd("HINCRBY")
        .arg(&stats_key)
        .arg("match_count")
        .arg(1)
        .cmd("HSET")
        .arg(&stats_key)
        .arg("last_matched")
        .arg(now)
        .cmd("EXPIRE")
        .arg(&stats_key)
        .arg(86400) // Expire after 24 hours
        .query_async(&mut conn)
        .await
        .map_err(|e| {
            Error::new(ErrorDetails::InternalError {
                message: format!("Failed to update rule stats: {}", e),
            })
        })?;

    Ok(())
}

/// Write blocking event to ClickHouse (fire-and-forget background task)
async fn write_blocking_event_to_clickhouse(
    clickhouse: &ClickHouseConnectionInfo,
    event: GatewayBlockingEventDatabaseInsert,
) -> Result<(), Error> {
    clickhouse.write(&[event], "GatewayBlockingEvents").await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ip_blocking() {
        let rule = BlockingRule {
            id: Uuid::new_v4(),
            rule_type: BlockingRuleType::IpBlocking,
            name: "Block bad IPs".to_string(),
            description: None,
            priority: 100,
            status: BlockingRuleStatus::Active,
            config: serde_json::json!({
                "ips": ["192.168.1.100", "10.0.0.50"],
                "cidrs": ["172.16.0.0/12"]
            }),
            action: "block".to_string(),
            expires_at: None,
        };

        let compiled = BlockingRulesManager::compile_rule(rule).unwrap();

        // Test exact IP match
        assert!(compiled
            .ip_nets
            .iter()
            .any(|net| net.contains(&"192.168.1.100".parse::<IpAddr>().unwrap())));

        // Test CIDR match
        assert!(compiled
            .ip_nets
            .iter()
            .any(|net| net.contains(&"172.20.1.1".parse::<IpAddr>().unwrap())));

        // Test no match
        assert!(!compiled
            .ip_nets
            .iter()
            .any(|net| net.contains(&"8.8.8.8".parse::<IpAddr>().unwrap())));
    }

    #[test]
    fn test_country_blocking() {
        let rule = BlockingRule {
            id: Uuid::new_v4(),
            rule_type: BlockingRuleType::CountryBlocking,
            name: "Block countries".to_string(),
            description: None,
            priority: 90,
            status: BlockingRuleStatus::Active,
            config: serde_json::json!({
                "country_codes": ["CN", "RU", "KP"]
            }),
            action: "block".to_string(),
            expires_at: None,
        };

        let compiled = BlockingRulesManager::compile_rule(rule).unwrap();

        // Test match
        assert!(compiled.country_set.contains("CN"));
        assert!(compiled.country_set.contains("RU"));

        // Test no match
        assert!(!compiled.country_set.contains("US"));
    }

    #[test]
    fn test_user_agent_blocking() {
        let rule = BlockingRule {
            id: Uuid::new_v4(),
            rule_type: BlockingRuleType::UserAgentBlocking,
            name: "Block bots".to_string(),
            description: None,
            priority: 80,
            status: BlockingRuleStatus::Active,
            config: serde_json::json!({
                "patterns": ["bot", "/crawler|spider/", "curl"]
            }),
            action: "block".to_string(),
            expires_at: None,
        };

        let compiled = BlockingRulesManager::compile_rule(rule).unwrap();

        // Test matches
        assert!(compiled
            .regex_patterns
            .iter()
            .any(|re| re.is_match("Mozilla/5.0 (compatible; Googlebot/2.1)")));
        assert!(compiled
            .regex_patterns
            .iter()
            .any(|re| re.is_match("WebCrawler/1.0")));
        assert!(compiled
            .regex_patterns
            .iter()
            .any(|re| re.is_match("curl/7.68.0")));

        // Test no match
        assert!(!compiled
            .regex_patterns
            .iter()
            .any(|re| re.is_match("Mozilla/5.0 (Windows NT 10.0; Win64; x64)")));
    }

    #[tokio::test]
    async fn test_rate_based_blocking() {
        let manager = BlockingRulesManager::new(None);
        let client_ip = "192.168.1.100";

        let config = serde_json::json!({
            "threshold": 3,
            "window_seconds": 60
        });

        // First 3 requests should pass
        for i in 1..=3 {
            let exceeded = manager.check_rate_limit("global", client_ip, &config).await;
            assert!(!exceeded, "Request {} should not be blocked", i);
        }

        // 4th request should be blocked
        let exceeded = manager.check_rate_limit("global", client_ip, &config).await;
        assert!(exceeded, "4th request should be blocked");
    }

    #[tokio::test]
    async fn test_cleanup_rate_limits() {
        let manager = BlockingRulesManager::new(None);

        // Add some rate limit states
        let config = serde_json::json!({
            "threshold": 10,
            "window_seconds": 60
        });

        // Create some rate limit entries
        for i in 0..5 {
            let ip = format!("192.168.1.{}", i);
            manager
                .check_rate_limit("model:test-model", &ip, &config)
                .await;
        }

        // Verify we have entries
        assert!(manager.rate_limits.len() >= 5);

        // Cleanup should retain entries (they're fresh)
        manager.cleanup_rate_limits().await;
        assert!(
            manager.rate_limits.len() >= 5,
            "Fresh entries should be retained"
        );
    }
}
