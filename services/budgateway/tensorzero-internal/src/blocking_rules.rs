//! Blocking Rules Enforcement for Gateway

use ipnet::IpNet;
use redis::AsyncCommands;
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

/// Blocking rules manager
pub struct BlockingRulesManager {
    redis_client: Option<Arc<RedisClient>>,
    rules_cache: Arc<RwLock<HashMap<Uuid, Vec<BlockingRule>>>>, // project_id -> rules
    rate_limits: Arc<RwLock<HashMap<String, RateLimitState>>>,  // key -> state
    last_sync: Arc<RwLock<Instant>>,
    sync_interval: Duration,
}

impl BlockingRulesManager {
    /// Create a new blocking rules manager
    pub fn new(redis_client: Option<Arc<RedisClient>>) -> Self {
        Self {
            redis_client,
            rules_cache: Arc::new(RwLock::new(HashMap::new())),
            rate_limits: Arc::new(RwLock::new(HashMap::new())),
            last_sync: Arc::new(RwLock::new(Instant::now())),
            sync_interval: Duration::from_secs(60), // Sync every minute
        }
    }

    /// Load rules from Redis for a project
    pub async fn load_rules(&self, project_id: &Uuid) -> Result<(), Error> {
        let Some(redis_client) = &self.redis_client else {
            debug!("No Redis client configured, skipping rule loading");
            return Ok(());
        };

        let key = format!("gateway:blocking_rules:{}", project_id);

        let mut conn = redis_client.get_connection().await.map_err(|e| {
            Error::new(ErrorDetails::InternalError {
                message: format!("Failed to get Redis connection: {}", e),
            })
        })?;

        let rules_json: Option<String> = conn.get(&key).await.map_err(|e| {
            Error::new(ErrorDetails::InternalError {
                message: format!("Failed to get blocking rules from Redis: {}", e),
            })
        })?;

        if let Some(json) = rules_json {
            let rules: Vec<BlockingRule> = serde_json::from_str(&json).map_err(|e| {
                Error::new(ErrorDetails::InternalError {
                    message: format!("Failed to parse blocking rules: {}", e),
                })
            })?;

            let mut cache = self.rules_cache.write().await;
            cache.insert(*project_id, rules);
            debug!(
                "Loaded {} blocking rules for project {}",
                cache.get(project_id).map(|r| r.len()).unwrap_or(0),
                project_id
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

    /// Check if a request should be blocked
    pub async fn should_block(
        &self,
        project_id: &Uuid,
        endpoint_id: Option<&Uuid>,
        client_ip: &str,
        country_code: Option<&str>,
        user_agent: Option<&str>,
    ) -> Result<Option<(BlockingRule, String)>, Error> {
        // Sync rules if needed
        self.maybe_sync_rules(project_id).await?;

        let cache = self.rules_cache.read().await;
        let Some(rules) = cache.get(project_id) else {
            return Ok(None);
        };

        // Sort rules by priority (higher priority first)
        let mut sorted_rules = rules.clone();
        sorted_rules.sort_by(|a, b| b.priority.cmp(&a.priority));

        for rule in sorted_rules {
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

                return Ok(Some((rule, reason)));
            }
        }

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
                            return (true, format!("IP {} is blocked", client_ip));
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
                                format!("IP {} is in blocked range {}", client_ip, cidr_str),
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
                        return (true, format!("Country {} is blocked", country));
                    }
                }
            }
        }

        (false, String::new())
    }

    /// Check user agent blocking rule
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
                    // Simple substring matching for now
                    // TODO: Add regex support if needed
                    if ua.to_lowercase().contains(&pattern.to_lowercase()) {
                        return (
                            true,
                            format!("User agent matches blocked pattern: {}", pattern),
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
            .unwrap_or(1) as u64;

        let key = format!("{}:{}:{}", project_id, rule.id, client_ip);
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
                    "Rate limit exceeded: {} requests in {} minutes (limit: {})",
                    state.requests, window_minutes, requests_per_minute
                ),
            );
        }

        (false, String::new())
    }

    /// Clear rate limit states periodically
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
            message: format!("Failed to get Redis connection: {}", e),
        })
    })?;

    let stats_key = format!("gateway:rule_stats:{}", rule_id);
    let now = chrono::Utc::now().timestamp();

    // Increment match count
    let _: () = conn
        .hincr(&stats_key, "match_count", 1)
        .await
        .map_err(|e| {
            Error::new(ErrorDetails::InternalError {
                message: format!("Failed to update rule stats: {}", e),
            })
        })?;

    // Update last matched timestamp
    let _: () = conn
        .hset(&stats_key, "last_matched", now)
        .await
        .map_err(|e| {
            Error::new(ErrorDetails::InternalError {
                message: format!("Failed to update rule stats: {}", e),
            })
        })?;

    // Set expiry to 7 days
    let _: () = conn.expire(&stats_key, 604800).await.map_err(|e| {
        Error::new(ErrorDetails::InternalError {
            message: format!("Failed to set expiry on rule stats: {}", e),
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
}
