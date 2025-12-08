use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize, Serializer};
use std::collections::HashMap;
use uuid::Uuid;

/// Custom serializer for DateTime<Utc> to format compatible with ClickHouse DateTime64(3)
fn serialize_datetime<S>(dt: &DateTime<Utc>, serializer: S) -> Result<S::Ok, S::Error>
where
    S: Serializer,
{
    let formatted = dt.format("%Y-%m-%d %H:%M:%S%.3f").to_string();
    serializer.serialize_str(&formatted)
}

/// Represents analytics data collected for each gateway request
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GatewayAnalyticsDatabaseInsert {
    /// Unique identifier for this analytics record
    pub id: Uuid,

    /// Associated inference ID if this request resulted in an inference
    pub inference_id: Option<Uuid>,

    /// Network metadata
    pub client_ip: String,
    pub proxy_chain: Option<String>, // X-Forwarded-For or similar
    pub protocol_version: String,    // HTTP/1.1, HTTP/2, etc.

    /// Geographical data (populated by GeoIP lookup)
    pub country_code: Option<String>,
    pub region: Option<String>,
    pub city: Option<String>,
    pub latitude: Option<f32>,
    pub longitude: Option<f32>,
    pub timezone: Option<String>,
    pub asn: Option<u32>,    // Autonomous System Number
    pub isp: Option<String>, // Internet Service Provider

    /// Client metadata
    pub user_agent: Option<String>,
    pub device_type: Option<String>, // desktop, mobile, tablet, bot
    pub browser_name: Option<String>,
    pub browser_version: Option<String>,
    pub os_name: Option<String>,
    pub os_version: Option<String>,
    pub is_bot: bool,

    /// Request context
    pub method: String,
    pub path: String,
    pub query_params: Option<String>,
    pub request_headers: HashMap<String, String>, // Selected headers
    pub body_size: Option<u32>,

    /// Authentication context
    pub api_key_id: Option<String>, // Hashed or masked API key
    pub auth_method: Option<String>, // bearer, basic, none
    pub user_id: Option<String>,
    pub project_id: Option<Uuid>,
    pub endpoint_id: Option<Uuid>,

    /// Performance metrics
    #[serde(serialize_with = "serialize_datetime")]
    pub request_timestamp: DateTime<Utc>,
    #[serde(serialize_with = "serialize_datetime")]
    pub response_timestamp: DateTime<Utc>,
    pub gateway_processing_ms: u32,
    pub total_duration_ms: u32,
    #[serde(skip)]
    pub model_latency_ms: Option<u32>,

    /// Model routing information
    pub model_name: Option<String>,
    pub model_provider: Option<String>,
    pub model_version: Option<String>,
    pub routing_decision: Option<String>, // primary, fallback, cached

    /// Response metadata
    pub status_code: u16,
    pub response_size: Option<u32>,
    pub response_headers: HashMap<String, String>, // Selected headers
    pub error_type: Option<String>,
    pub error_message: Option<String>,

    /// Blocking information
    pub is_blocked: bool,
    pub block_reason: Option<String>,
    pub block_rule_id: Option<String>,

    /// Custom tags
    pub tags: HashMap<String, String>,
}

impl GatewayAnalyticsDatabaseInsert {
    pub fn new(id: Uuid) -> Self {
        let now = Utc::now();
        Self {
            id,
            inference_id: None,
            client_ip: String::new(),
            proxy_chain: None,
            protocol_version: "HTTP/1.1".to_string(),
            country_code: None,
            region: None,
            city: None,
            latitude: None,
            longitude: None,
            timezone: None,
            asn: None,
            isp: None,
            user_agent: None,
            device_type: None,
            browser_name: None,
            browser_version: None,
            os_name: None,
            os_version: None,
            is_bot: false,
            method: String::new(),
            path: String::new(),
            query_params: None,
            request_headers: HashMap::new(),
            body_size: None,
            api_key_id: None,
            auth_method: None,
            user_id: None,
            project_id: None,
            endpoint_id: None,
            request_timestamp: now,
            response_timestamp: now,
            gateway_processing_ms: 0,
            total_duration_ms: 0,
            model_latency_ms: None,
            model_name: None,
            model_provider: None,
            model_version: None,
            routing_decision: None,
            status_code: 0,
            response_size: None,
            response_headers: HashMap::new(),
            error_type: None,
            error_message: None,
            is_blocked: false,
            block_reason: None,
            block_rule_id: None,
            tags: HashMap::new(),
        }
    }
}

/// Analytics data stored in request extensions during processing
#[derive(Debug, Clone)]
pub struct RequestAnalytics {
    pub record: GatewayAnalyticsDatabaseInsert,
    pub start_time: std::time::Instant,
}

impl Default for RequestAnalytics {
    fn default() -> Self {
        Self::new()
    }
}

impl RequestAnalytics {
    pub fn new() -> Self {
        Self {
            record: GatewayAnalyticsDatabaseInsert::new(Uuid::now_v7()),
            start_time: std::time::Instant::now(),
        }
    }
}
