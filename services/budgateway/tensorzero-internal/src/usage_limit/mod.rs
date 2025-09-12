pub mod limiter;
pub mod middleware;

pub use limiter::{UsageLimiter, UsageLimitInfo, UsageLimiterConfig};
pub use middleware::usage_limit_middleware;

/// User usage limit status with usage tracking
#[derive(Debug, Clone)]
pub struct UsageLimitStatus {
    pub user_id: String,
    pub user_type: String,  // "admin" or "client"
    pub allowed: bool,
    pub status: String,
    pub tokens_quota: Option<i64>,
    pub tokens_used: i64,
    pub cost_quota: Option<f64>,
    pub cost_used: f64,
    pub reason: Option<String>,
    pub reset_at: Option<String>,
    pub last_updated: std::time::Instant,
    // Track the last update_id we've seen from budapp
    pub last_seen_update_id: u64,
    // Realtime increments from Redis (already applied to tokens_used/cost_used)
    pub realtime_tokens: i64,
    pub realtime_cost: f64,
    // Billing cycle tracking
    pub billing_cycle_start: Option<String>,
    pub billing_cycle_end: Option<String>,
}

impl UsageLimitStatus {
    /// Check if the cached status is still fresh
    pub fn is_fresh(&self, ttl_seconds: u64) -> bool {
        self.last_updated.elapsed().as_secs() < ttl_seconds
    }
}

/// Usage limit decision
#[derive(Debug)]
pub enum UsageLimitDecision {
    Allow,
    Deny { reason: String },
}

impl UsageLimitDecision {
    pub fn is_allowed(&self) -> bool {
        matches!(self, UsageLimitDecision::Allow)
    }
}
