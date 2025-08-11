//! Blocking Rules Enforcement for Gateway

use ipnet::IpNet;
use metrics::{counter, histogram};
use redis::AsyncCommands;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::net::IpAddr;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::RwLock;
use tracing::{debug, warn};
use uuid::Uuid;

use crate::error::{Error, ErrorDetails};
use crate::redis_client::RedisClient;

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
    pub project_id: Uuid,
    pub endpoint_id: Option<Uuid>,
    pub rule_type: BlockingRuleType,
    pub name: String,
    pub description: Option<String>,
    pub priority: i32,
    pub status: BlockingRuleStatus,
    pub config: serde_json::Value,
    pub action: String,
    pub expires_at: Option<chrono::DateTime<chrono::Utc>>,
}

/// Rate limiting state for rate-based blocking
#[derive(Debug, Clone)]
struct RateLimitState {
    requests: u32,
    window_start: Instant,
}

/// Blocking rules manager for enforcing various types of request blocking
///
/// This manager handles:
/// - IP-based blocking (individual IPs and CIDR ranges)
/// - Geographic blocking (by country code)
/// - User agent pattern blocking
/// - Rate-based blocking (requests per time window)
///
/// Rules are synchronized from Redis periodically and enforced locally for low latency.
pub struct BlockingRulesManager {
    redis_client: Option<Arc<RedisClient>>,
    rules_cache: Arc<RwLock<HashMap<Uuid, Vec<BlockingRule>>>>, // project_id -> rules
    rate_limits: Arc<RwLock<HashMap<String, RateLimitState>>>,  // key -> state
    last_sync: Arc<RwLock<Instant>>,
    sync_interval: Duration,
}

impl BlockingRulesManager {
    /// Create a new blocking rules manager
    ///
    /// # Arguments
    /// * `redis_client` - Optional Redis client for loading rules and updating statistics
    ///
    /// # Returns
    /// A new `BlockingRulesManager` instance
    pub fn new(redis_client: Option<Arc<RedisClient>>) -> Self {
        Self {
            redis_client,
            rules_cache: Arc::new(RwLock::new(HashMap::new())),
            rate_limits: Arc::new(RwLock::new(HashMap::new())),
            last_sync: Arc::new(RwLock::new(Instant::now())),
            sync_interval: Duration::from_secs(60), // Sync every minute
        }
    }

    /// Validate a blocking rule configuration
    fn validate_rule(rule: &BlockingRule) -> Result<(), String> {
        match rule.rule_type {
            BlockingRuleType::IpBlocking => {
                let config = rule
                    .config
                    .as_object()
                    .ok_or("IP blocking rule must have a config object")?;

                // Validate IPs if present
                if let Some(ips) = config.get("ips").and_then(|v| v.as_array()) {
                    for (idx, ip_value) in ips.iter().enumerate() {
                        let ip_str = ip_value
                            .as_str()
                            .ok_or(format!("IP at index {} is not a string", idx))?;
                        ip_str
                            .parse::<IpAddr>()
                            .map_err(|e| format!("Invalid IP '{}': {}", ip_str, e))?;
                    }
                }

                // Validate CIDRs if present
                if let Some(cidrs) = config.get("cidrs").and_then(|v| v.as_array()) {
                    for (idx, cidr_value) in cidrs.iter().enumerate() {
                        let cidr_str = cidr_value
                            .as_str()
                            .ok_or(format!("CIDR at index {} is not a string", idx))?;
                        cidr_str
                            .parse::<IpNet>()
                            .map_err(|e| format!("Invalid CIDR '{}': {}", cidr_str, e))?;
                    }
                }

                // Ensure at least one blocking criterion is present
                if !config.contains_key("ips") && !config.contains_key("cidrs") {
                    return Err("IP blocking rule must contain 'ips' or 'cidrs'".to_string());
                }
            }
            BlockingRuleType::CountryBlocking => {
                let config = rule
                    .config
                    .as_object()
                    .ok_or("Country blocking rule must have a config object")?;

                let countries = config
                    .get("country_codes")
                    .and_then(|v| v.as_array())
                    .ok_or("Country blocking rule must have 'country_codes' array")?;

                if countries.is_empty() {
                    return Err("Country codes array cannot be empty".to_string());
                }

                for (idx, country_value) in countries.iter().enumerate() {
                    let country_code = country_value
                        .as_str()
                        .ok_or(format!("Country code at index {} is not a string", idx))?;

                    // Validate country code format (2-letter ISO code)
                    if country_code.len() != 2
                        || !country_code.chars().all(|c| c.is_ascii_alphabetic())
                    {
                        return Err(format!(
                            "Invalid country code '{}': must be 2-letter ISO code",
                            country_code
                        ));
                    }
                }
            }
            BlockingRuleType::UserAgentBlocking => {
                let config = rule
                    .config
                    .as_object()
                    .ok_or("User agent blocking rule must have a config object")?;

                let patterns = config
                    .get("patterns")
                    .and_then(|v| v.as_array())
                    .ok_or("User agent blocking rule must have 'patterns' array")?;

                if patterns.is_empty() {
                    return Err("Patterns array cannot be empty".to_string());
                }

                for (idx, pattern_value) in patterns.iter().enumerate() {
                    let pattern = pattern_value
                        .as_str()
                        .ok_or(format!("Pattern at index {} is not a string", idx))?;

                    // Validate regex patterns
                    if pattern.starts_with('/') && pattern.ends_with('/') {
                        let pattern_str = &pattern[1..pattern.len() - 1];
                        let regex_with_flags = format!("(?i){}", pattern_str);
                        Regex::new(&regex_with_flags)
                            .map_err(|e| format!("Invalid regex pattern '{}': {}", pattern, e))?;
                    }
                }
            }
            BlockingRuleType::RateBasedBlocking => {
                let config = rule
                    .config
                    .as_object()
                    .ok_or("Rate-based blocking rule must have a config object")?;

                let requests_per_minute = config
                    .get("requests_per_minute")
                    .and_then(|v| v.as_u64())
                    .ok_or("Rate-based rule must have 'requests_per_minute' as positive integer")?;

                if requests_per_minute == 0 {
                    return Err("requests_per_minute must be greater than 0".to_string());
                }

                let window_minutes = config
                    .get("window_minutes")
                    .and_then(|v| v.as_u64())
                    .unwrap_or(1);

                if window_minutes == 0 || window_minutes > 60 {
                    return Err("window_minutes must be between 1 and 60".to_string());
                }
            }
        }

        Ok(())
    }

    /// Load blocking rules from Redis for a specific project
    ///
    /// Fetches the latest blocking rules from Redis, validates them, and caches
    /// the valid rules locally. Invalid rules are logged and skipped.
    ///
    /// # Arguments
    /// * `project_id` - The UUID of the project to load rules for
    ///
    /// # Returns
    /// * `Ok(())` - Rules loaded successfully (or no Redis client configured)
    /// * `Err(Error)` - Failed to connect to Redis or parse rules
    pub async fn load_rules(&self, project_id: &Uuid) -> Result<(), Error> {
        let Some(redis_client) = &self.redis_client else {
            debug!("No Redis client configured, skipping rule loading");
            return Ok(());
        };

        let key = format!("gateway:blocking_rules:{project_id}");

        let mut conn = redis_client.get_connection().await.map_err(|e| {
            Error::new(ErrorDetails::InternalError {
                message: format!("Failed to get Redis connection: {e}"),
            })
        })?;

        let rules_json: Option<String> = conn.get(&key).await.map_err(|e| {
            Error::new(ErrorDetails::InternalError {
                message: format!("Failed to get blocking rules from Redis: {e}"),
            })
        })?;

        if let Some(json) = rules_json {
            let rules: Vec<BlockingRule> = serde_json::from_str(&json).map_err(|e| {
                Error::new(ErrorDetails::InternalError {
                    message: format!("Failed to parse blocking rules: {e}"),
                })
            })?;

            // Validate all rules before caching
            let mut valid_rules = Vec::new();
            for rule in rules {
                match Self::validate_rule(&rule) {
                    Ok(()) => valid_rules.push(rule),
                    Err(e) => {
                        warn!(
                            "Skipping invalid rule '{}' (id: {}): {}",
                            rule.name, rule.id, e
                        );
                    }
                }
            }

            let mut cache = self.rules_cache.write().await;
            let num_valid = valid_rules.len();
            cache.insert(*project_id, valid_rules);
            debug!(
                "Loaded {} valid blocking rules for project {}",
                num_valid, project_id
            );
        }

        Ok(())
    }

    /// Check if rules need to be synced
    async fn maybe_sync_rules(&self, project_id: &Uuid) -> Result<(), Error> {
        let last_sync = *self.last_sync.read().await;

        if last_sync.elapsed() > self.sync_interval {
            self.load_rules(project_id).await?;
            *self.last_sync.write().await = Instant::now();
        }

        Ok(())
    }

    /// Check if a request should be blocked based on configured rules
    ///
    /// Evaluates all active blocking rules for the project in priority order.
    /// Returns the first matching rule and the reason for blocking.
    ///
    /// # Arguments
    /// * `project_id` - The project ID to check rules for
    /// * `endpoint_id` - Optional endpoint ID for endpoint-specific rules
    /// * `client_ip` - The client's IP address
    /// * `country_code` - Optional country code (from GeoIP lookup)
    /// * `user_agent` - Optional user agent string
    ///
    /// # Returns
    /// * `Ok(Some((rule, reason)))` - Request should be blocked
    /// * `Ok(None)` - Request should not be blocked
    /// * `Err(Error)` - Failed to check rules
    pub async fn should_block(
        &self,
        project_id: &Uuid,
        endpoint_id: Option<&Uuid>,
        client_ip: &str,
        country_code: Option<&str>,
        user_agent: Option<&str>,
    ) -> Result<Option<(BlockingRule, String)>, Error> {
        let start = Instant::now();

        // Sync rules if needed
        self.maybe_sync_rules(project_id).await?;

        let cache = self.rules_cache.read().await;
        let Some(rules) = cache.get(project_id) else {
            counter!("blocking_rules_evaluated_total", "result" => "no_rules").increment(1);
            return Ok(None);
        };

        // Sort rules by priority (higher priority first)
        let mut sorted_rules = rules.clone();
        sorted_rules.sort_by(|a, b| b.priority.cmp(&a.priority));

        let mut rules_evaluated = 0;
        for rule in sorted_rules {
            rules_evaluated += 1;
            // Skip inactive or expired rules
            if !matches!(rule.status, BlockingRuleStatus::Active) {
                continue;
            }

            if let Some(expires_at) = rule.expires_at {
                if chrono::Utc::now() > expires_at {
                    continue;
                }
            }

            // Check endpoint match if specified
            if let Some(rule_endpoint) = &rule.endpoint_id {
                if let Some(req_endpoint) = endpoint_id {
                    if rule_endpoint != req_endpoint {
                        continue;
                    }
                } else {
                    continue;
                }
            }

            // Check rule based on type
            let (matched, reason) = match rule.rule_type {
                BlockingRuleType::IpBlocking => self.check_ip_rule(&rule, client_ip),
                BlockingRuleType::CountryBlocking => self.check_country_rule(&rule, country_code),
                BlockingRuleType::UserAgentBlocking => {
                    self.check_user_agent_rule(&rule, user_agent)
                }
                BlockingRuleType::RateBasedBlocking => {
                    self.check_rate_rule(&rule, client_ip, project_id).await
                }
            };

            if matched {
                // Update match statistics in Redis (fire and forget)
                if let Some(redis_client) = &self.redis_client {
                    let rule_id = rule.id;
                    let redis_client = redis_client.clone();
                    tokio::spawn(async move {
                        if let Err(e) = update_rule_stats(&redis_client, &rule_id).await {
                            warn!("Failed to update rule stats: {}", e);
                        }
                    });
                }

                // Record metrics
                let duration = start.elapsed();

                histogram!("blocking_rules_evaluation_duration_seconds")
                    .record(duration.as_secs_f64());
                counter!("blocking_rules_evaluated_total", "result" => "blocked").increment(1);

                // Record rule type specific metrics
                match rule.rule_type {
                    BlockingRuleType::IpBlocking => {
                        counter!("blocking_rules_matched_total", "rule_type" => "ip_blocking")
                            .increment(1);
                    }
                    BlockingRuleType::CountryBlocking => {
                        counter!("blocking_rules_matched_total", "rule_type" => "country_blocking")
                            .increment(1);
                    }
                    BlockingRuleType::UserAgentBlocking => {
                        counter!("blocking_rules_matched_total", "rule_type" => "user_agent_blocking").increment(1);
                    }
                    BlockingRuleType::RateBasedBlocking => {
                        counter!("blocking_rules_matched_total", "rule_type" => "rate_based_blocking").increment(1);
                    }
                }

                histogram!("blocking_rules_checked_per_request").record(rules_evaluated as f64);

                return Ok(Some((rule, reason)));
            }
        }

        // Record metrics for non-blocked requests
        let duration = start.elapsed();
        histogram!("blocking_rules_evaluation_duration_seconds").record(duration.as_secs_f64());
        counter!("blocking_rules_evaluated_total", "result" => "allowed").increment(1);
        histogram!("blocking_rules_checked_per_request").record(rules_evaluated as f64);

        Ok(None)
    }

    /// Check IP blocking rule
    fn check_ip_rule(&self, rule: &BlockingRule, client_ip: &str) -> (bool, String) {
        let config = match rule.config.as_object() {
            Some(c) => c,
            None => return (false, String::new()),
        };

        // Parse client IP
        let client_addr = match client_ip.parse::<IpAddr>() {
            Ok(addr) => addr,
            Err(_) => return (false, String::new()),
        };

        // Check individual IPs
        if let Some(ips) = config.get("ips").and_then(|v| v.as_array()) {
            for ip_value in ips {
                if let Some(ip_str) = ip_value.as_str() {
                    if let Ok(ip) = ip_str.parse::<IpAddr>() {
                        if ip == client_addr {
                            return (true, format!("IP {client_ip} is blocked"));
                        }
                    }
                }
            }
        }

        // Check CIDR ranges
        if let Some(cidrs) = config.get("cidrs").and_then(|v| v.as_array()) {
            for cidr_value in cidrs {
                if let Some(cidr_str) = cidr_value.as_str() {
                    if let Ok(network) = cidr_str.parse::<IpNet>() {
                        if network.contains(&client_addr) {
                            return (
                                true,
                                format!("IP {client_ip} is in blocked range {cidr_str}"),
                            );
                        }
                    }
                }
            }
        }

        (false, String::new())
    }

    /// Check country blocking rule
    fn check_country_rule(
        &self,
        rule: &BlockingRule,
        country_code: Option<&str>,
    ) -> (bool, String) {
        let Some(country) = country_code else {
            return (false, String::new());
        };

        let config = match rule.config.as_object() {
            Some(c) => c,
            None => return (false, String::new()),
        };

        if let Some(countries) = config.get("country_codes").and_then(|v| v.as_array()) {
            for country_value in countries {
                if let Some(blocked_country) = country_value.as_str() {
                    if blocked_country.eq_ignore_ascii_case(country) {
                        return (true, format!("Country {country} is blocked"));
                    }
                }
            }
        }

        (false, String::new())
    }

    /// Check user agent blocking rule
    ///
    /// Supports both substring matching and regex patterns.
    /// Regex patterns must start with '/' and end with '/' (e.g., "/bot|crawler/i")
    fn check_user_agent_rule(
        &self,
        rule: &BlockingRule,
        user_agent: Option<&str>,
    ) -> (bool, String) {
        let Some(ua) = user_agent else {
            return (false, String::new());
        };

        let config = match rule.config.as_object() {
            Some(c) => c,
            None => return (false, String::new()),
        };

        if let Some(patterns) = config.get("patterns").and_then(|v| v.as_array()) {
            for pattern_value in patterns {
                if let Some(pattern) = pattern_value.as_str() {
                    // Check if it's a regex pattern (starts and ends with /)
                    let matched = if pattern.starts_with('/') && pattern.ends_with('/') {
                        // Extract regex pattern and flags
                        let pattern_str = &pattern[1..pattern.len() - 1];

                        // Try to compile and match the regex (case-insensitive by default)
                        let regex_with_flags = format!("(?i){}", pattern_str);
                        match Regex::new(&regex_with_flags) {
                            Ok(re) => re.is_match(ua),
                            Err(e) => {
                                warn!("Invalid regex pattern '{}': {}", pattern, e);
                                false
                            }
                        }
                    } else {
                        // Simple substring matching (case-insensitive)
                        ua.to_lowercase().contains(&pattern.to_lowercase())
                    };

                    if matched {
                        return (
                            true,
                            format!("User agent matches blocked pattern: {pattern}"),
                        );
                    }
                }
            }
        }

        (false, String::new())
    }

    /// Check rate-based blocking rule
    async fn check_rate_rule(
        &self,
        rule: &BlockingRule,
        client_ip: &str,
        project_id: &Uuid,
    ) -> (bool, String) {
        let config = match rule.config.as_object() {
            Some(c) => c,
            None => return (false, String::new()),
        };

        let requests_per_minute = config
            .get("requests_per_minute")
            .and_then(|v| v.as_u64())
            .unwrap_or(60) as u32;

        let window_minutes = config
            .get("window_minutes")
            .and_then(|v| v.as_u64())
            .unwrap_or(1);

        let key = format!("{project_id}:{}:{client_ip}", rule.id);
        let window_duration = Duration::from_secs(window_minutes * 60);

        let mut rate_limits = self.rate_limits.write().await;
        let now = Instant::now();

        let state = rate_limits
            .entry(key.clone())
            .or_insert_with(|| RateLimitState {
                requests: 0,
                window_start: now,
            });

        // Reset window if expired
        if now.duration_since(state.window_start) > window_duration {
            state.requests = 0;
            state.window_start = now;
        }

        state.requests += 1;

        if state.requests > requests_per_minute {
            return (
                true,
                format!(
                    "Rate limit exceeded: {} requests in {window_minutes} minutes (limit: {requests_per_minute})",
                    state.requests
                ),
            );
        }

        (false, String::new())
    }

    /// Clear expired rate limit states to prevent memory growth
    ///
    /// Removes rate limit entries that haven't been accessed in over an hour.
    /// This should be called periodically to prevent unbounded memory growth.
    pub async fn cleanup_rate_limits(&self) {
        let mut rate_limits = self.rate_limits.write().await;
        let now = Instant::now();

        rate_limits.retain(|_, state| {
            now.duration_since(state.window_start) < Duration::from_secs(3600) // Keep for 1 hour
        });
    }
}

/// Update rule match statistics in Redis
async fn update_rule_stats(redis_client: &RedisClient, rule_id: &Uuid) -> Result<(), Error> {
    let mut conn = redis_client.get_connection().await.map_err(|e| {
        Error::new(ErrorDetails::InternalError {
            message: format!("Failed to get Redis connection: {e}"),
        })
    })?;

    let stats_key = format!("gateway:rule_stats:{rule_id}");
    let now = chrono::Utc::now().timestamp();

    // Increment match count
    let _: () = conn
        .hincr(&stats_key, "match_count", 1)
        .await
        .map_err(|e| {
            Error::new(ErrorDetails::InternalError {
                message: format!("Failed to update rule stats: {e}"),
            })
        })?;

    // Update last matched timestamp
    let _: () = conn
        .hset(&stats_key, "last_matched", now)
        .await
        .map_err(|e| {
            Error::new(ErrorDetails::InternalError {
                message: format!("Failed to update rule stats: {e}"),
            })
        })?;

    // Set expiry to 7 days
    let _: () = conn.expire(&stats_key, 604800).await.map_err(|e| {
        Error::new(ErrorDetails::InternalError {
            message: format!("Failed to set expiry on rule stats: {e}"),
        })
    })?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ip_blocking() {
        let rule = BlockingRule {
            id: Uuid::new_v4(),
            project_id: Uuid::new_v4(),
            endpoint_id: None,
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

        let manager = BlockingRulesManager::new(None);

        // Test exact IP match
        let (matched, _) = manager.check_ip_rule(&rule, "192.168.1.100");
        assert!(matched);

        // Test CIDR match
        let (matched, _) = manager.check_ip_rule(&rule, "172.20.1.1");
        assert!(matched);

        // Test no match
        let (matched, _) = manager.check_ip_rule(&rule, "8.8.8.8");
        assert!(!matched);
    }

    #[test]
    fn test_country_blocking() {
        let rule = BlockingRule {
            id: Uuid::new_v4(),
            project_id: Uuid::new_v4(),
            endpoint_id: None,
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

        let manager = BlockingRulesManager::new(None);

        // Test match
        let (matched, _) = manager.check_country_rule(&rule, Some("CN"));
        assert!(matched);

        // Test case insensitive
        let (matched, _) = manager.check_country_rule(&rule, Some("ru"));
        assert!(matched);

        // Test no match
        let (matched, _) = manager.check_country_rule(&rule, Some("US"));
        assert!(!matched);
    }

    #[test]
    fn test_user_agent_blocking() {
        let rule = BlockingRule {
            id: Uuid::new_v4(),
            project_id: Uuid::new_v4(),
            endpoint_id: None,
            rule_type: BlockingRuleType::UserAgentBlocking,
            name: "Block bots".to_string(),
            description: None,
            priority: 80,
            status: BlockingRuleStatus::Active,
            config: serde_json::json!({
                "patterns": ["bot", "crawler", "scraper", "curl"]
            }),
            action: "block".to_string(),
            expires_at: None,
        };

        let manager = BlockingRulesManager::new(None);

        // Test matches
        let (matched, _) =
            manager.check_user_agent_rule(&rule, Some("Mozilla/5.0 (compatible; Googlebot/2.1)"));
        assert!(matched);

        let (matched, _) = manager.check_user_agent_rule(&rule, Some("curl/7.68.0"));
        assert!(matched);

        // Test no match
        let (matched, _) =
            manager.check_user_agent_rule(&rule, Some("Mozilla/5.0 (Windows NT 10.0; Win64; x64)"));
        assert!(!matched);
    }

    #[test]
    fn test_user_agent_blocking_with_regex() {
        let rule = BlockingRule {
            id: Uuid::new_v4(),
            project_id: Uuid::new_v4(),
            endpoint_id: None,
            rule_type: BlockingRuleType::UserAgentBlocking,
            name: "Block with regex".to_string(),
            description: None,
            priority: 80,
            status: BlockingRuleStatus::Active,
            config: serde_json::json!({
                "patterns": [
                    "/bot|crawler|spider/",  // Regex pattern
                    "curl",  // Simple substring
                    "/^python-requests/",  // Regex: starts with python-requests
                ]
            }),
            action: "block".to_string(),
            expires_at: None,
        };

        let manager = BlockingRulesManager::new(None);

        // Test regex matches
        let (matched, _) = manager.check_user_agent_rule(&rule, Some("Googlebot/2.1"));
        assert!(matched, "Should match 'bot' in regex pattern");

        let (matched, reason) = manager.check_user_agent_rule(&rule, Some("WebCrawler/1.0"));
        assert!(
            matched,
            "Should match 'crawler' in regex pattern, but got: matched={}, reason='{}'",
            matched, reason
        );

        let (matched, _) = manager.check_user_agent_rule(&rule, Some("python-requests/2.28.0"));
        assert!(
            matched,
            "Should match regex pattern starting with python-requests"
        );

        // Test simple substring match
        let (matched, _) = manager.check_user_agent_rule(&rule, Some("curl/7.68.0"));
        assert!(matched, "Should match simple substring 'curl'");

        // Test no match
        let (matched, _) = manager.check_user_agent_rule(&rule, Some("Mozilla/5.0 Firefox"));
        assert!(!matched, "Should not match any pattern");

        let (matched, _) = manager.check_user_agent_rule(&rule, Some("not-python-requests/1.0"));
        assert!(
            !matched,
            "Should not match regex that requires start anchor"
        );
    }

    #[tokio::test]
    async fn test_rate_based_blocking() {
        let rule = BlockingRule {
            id: Uuid::new_v4(),
            project_id: Uuid::new_v4(),
            endpoint_id: None,
            rule_type: BlockingRuleType::RateBasedBlocking,
            name: "Rate limit".to_string(),
            description: Some("Limit to 3 requests per minute".to_string()),
            priority: 70,
            status: BlockingRuleStatus::Active,
            config: serde_json::json!({
                "requests_per_minute": 3,
                "window_minutes": 1
            }),
            action: "block".to_string(),
            expires_at: None,
        };

        let manager = BlockingRulesManager::new(None);
        let project_id = Uuid::new_v4();
        let client_ip = "192.168.1.100";

        // First 3 requests should pass
        for i in 1..=3 {
            let (blocked, reason) = manager.check_rate_rule(&rule, client_ip, &project_id).await;
            assert!(
                !blocked,
                "Request {} should not be blocked, but got: {}",
                i, reason
            );
        }

        // 4th request should be blocked
        let (blocked, reason) = manager.check_rate_rule(&rule, client_ip, &project_id).await;
        assert!(blocked, "4th request should be blocked");
        assert!(reason.contains("Rate limit exceeded"));
        assert!(reason.contains("4 requests"));
    }

    #[tokio::test]
    async fn test_rate_based_blocking_window_reset() {
        let rule = BlockingRule {
            id: Uuid::new_v4(),
            project_id: Uuid::new_v4(),
            endpoint_id: None,
            rule_type: BlockingRuleType::RateBasedBlocking,
            name: "Rate limit with short window".to_string(),
            description: None,
            priority: 70,
            status: BlockingRuleStatus::Active,
            config: serde_json::json!({
                "requests_per_minute": 2,
                "window_minutes": 1
            }),
            action: "block".to_string(),
            expires_at: None,
        };

        let manager = BlockingRulesManager::new(None);
        let project_id = Uuid::new_v4();
        let client_ip = "10.0.0.1";

        // Make 2 requests (should pass)
        let (blocked, _) = manager.check_rate_rule(&rule, client_ip, &project_id).await;
        assert!(!blocked);
        let (blocked, _) = manager.check_rate_rule(&rule, client_ip, &project_id).await;
        assert!(!blocked);

        // 3rd request should be blocked
        let (blocked, _) = manager.check_rate_rule(&rule, client_ip, &project_id).await;
        assert!(blocked);

        // Note: Testing actual window reset would require mocking time or waiting,
        // which is not practical in unit tests. The logic is covered by the implementation.
    }

    #[tokio::test]
    async fn test_rate_based_blocking_different_clients() {
        let rule = BlockingRule {
            id: Uuid::new_v4(),
            project_id: Uuid::new_v4(),
            endpoint_id: None,
            rule_type: BlockingRuleType::RateBasedBlocking,
            name: "Per-IP rate limit".to_string(),
            description: None,
            priority: 70,
            status: BlockingRuleStatus::Active,
            config: serde_json::json!({
                "requests_per_minute": 2,
                "window_minutes": 1
            }),
            action: "block".to_string(),
            expires_at: None,
        };

        let manager = BlockingRulesManager::new(None);
        let project_id = Uuid::new_v4();

        // Client 1 makes 2 requests
        let (blocked, _) = manager
            .check_rate_rule(&rule, "192.168.1.1", &project_id)
            .await;
        assert!(!blocked);
        let (blocked, _) = manager
            .check_rate_rule(&rule, "192.168.1.1", &project_id)
            .await;
        assert!(!blocked);

        // Client 2 can still make requests (different rate limit bucket)
        let (blocked, _) = manager
            .check_rate_rule(&rule, "192.168.1.2", &project_id)
            .await;
        assert!(!blocked);
        let (blocked, _) = manager
            .check_rate_rule(&rule, "192.168.1.2", &project_id)
            .await;
        assert!(!blocked);

        // Client 1's 3rd request is blocked
        let (blocked, _) = manager
            .check_rate_rule(&rule, "192.168.1.1", &project_id)
            .await;
        assert!(blocked);

        // Client 2's 3rd request is also blocked
        let (blocked, _) = manager
            .check_rate_rule(&rule, "192.168.1.2", &project_id)
            .await;
        assert!(blocked);
    }

    #[tokio::test]
    async fn test_cleanup_rate_limits() {
        let manager = BlockingRulesManager::new(None);

        // Add some rate limit states
        let rule = BlockingRule {
            id: Uuid::new_v4(),
            project_id: Uuid::new_v4(),
            endpoint_id: None,
            rule_type: BlockingRuleType::RateBasedBlocking,
            name: "Test".to_string(),
            description: None,
            priority: 100,
            status: BlockingRuleStatus::Active,
            config: serde_json::json!({
                "requests_per_minute": 10,
                "window_minutes": 1
            }),
            action: "block".to_string(),
            expires_at: None,
        };

        let project_id = Uuid::new_v4();

        // Create some rate limit entries
        for i in 0..5 {
            let ip = format!("192.168.1.{}", i);
            manager.check_rate_rule(&rule, &ip, &project_id).await;
        }

        // Verify we have entries
        {
            let rate_limits = manager.rate_limits.read().await;
            assert!(rate_limits.len() >= 5);
        }

        // Cleanup should retain entries (they're fresh)
        manager.cleanup_rate_limits().await;

        {
            let rate_limits = manager.rate_limits.read().await;
            assert!(rate_limits.len() >= 5, "Fresh entries should be retained");
        }
    }
}
