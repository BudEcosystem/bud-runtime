use crate::clickhouse::migration_manager::migration_trait::Migration;
use crate::clickhouse::ClickHouseConnectionInfo;
use crate::error::Error;
use async_trait::async_trait;

use super::check_table_exists;

/// This migration creates the GatewayAnalytics table for storing API gateway request analytics.
/// It captures comprehensive metadata about each request including network info, geographical data,
/// client information, performance metrics, and blocking decisions.
pub struct Migration0030<'a> {
    pub clickhouse: &'a ClickHouseConnectionInfo,
}

const MIGRATION_ID: &str = "0030";

#[async_trait]
impl Migration for Migration0030<'_> {
    async fn can_apply(&self) -> Result<(), Error> {
        Ok(())
    }

    async fn should_apply(&self) -> Result<bool, Error> {
        let table_exists =
            check_table_exists(self.clickhouse, "GatewayAnalytics", MIGRATION_ID).await?;
        Ok(!table_exists)
    }

    async fn apply(&self, _clean_start: bool) -> Result<(), Error> {
        // Create the GatewayAnalytics table
        let query = r#"
            CREATE TABLE IF NOT EXISTS GatewayAnalytics
            (
                -- Core identifiers
                id UUID,                           -- UUIDv7 for analytics record
                inference_id Nullable(UUID),       -- Associated inference if applicable

                -- Network metadata
                client_ip String,
                proxy_chain Nullable(String),      -- X-Forwarded-For chain
                protocol_version LowCardinality(String),

                -- Geographical data (from GeoIP lookup)
                country_code Nullable(String),
                region Nullable(String),
                city Nullable(String),
                latitude Nullable(Float32),
                longitude Nullable(Float32),
                timezone Nullable(String),
                asn Nullable(UInt32),              -- Autonomous System Number
                isp Nullable(String),              -- Internet Service Provider

                -- Client metadata
                user_agent Nullable(String),
                device_type Nullable(LowCardinality(String)),
                browser_name Nullable(LowCardinality(String)),
                browser_version Nullable(String),
                os_name Nullable(LowCardinality(String)),
                os_version Nullable(String),
                is_bot Bool DEFAULT false,

                -- Request context
                method LowCardinality(String),
                path String,
                query_params Nullable(String),
                request_headers Map(String, String),
                body_size Nullable(UInt32),

                -- Authentication context
                api_key_id Nullable(String),       -- Hashed/masked API key
                auth_method Nullable(LowCardinality(String)),
                user_id Nullable(String),
                project_id Nullable(UUID),
                endpoint_id Nullable(UUID),

                -- Performance metrics
                request_timestamp DateTime64(3),
                response_timestamp DateTime64(3),
                gateway_processing_ms UInt32,
                total_duration_ms UInt32,

                -- Model routing information
                model_name Nullable(LowCardinality(String)),
                model_provider Nullable(LowCardinality(String)),
                model_version Nullable(String),
                routing_decision Nullable(LowCardinality(String)),

                -- Response metadata
                status_code UInt16,
                response_size Nullable(UInt32),
                response_headers Map(String, String),
                error_type Nullable(LowCardinality(String)),
                error_message Nullable(String),

                -- Blocking information
                is_blocked Bool DEFAULT false,
                block_reason Nullable(String),
                block_rule_id Nullable(String),

                -- Custom tags
                tags Map(String, String),

                -- Materialized columns
                timestamp DateTime MATERIALIZED toDateTime(request_timestamp),
                date Date MATERIALIZED toDate(request_timestamp),
                hour DateTime MATERIALIZED toStartOfHour(request_timestamp)
            )
            ENGINE = MergeTree()
            PARTITION BY toYYYYMM(request_timestamp)
            ORDER BY (project_id, timestamp, id)
            TTL request_timestamp + INTERVAL 90 DAY
            SETTINGS index_granularity = 8192;
        "#;

        self.clickhouse
            .run_query_synchronous(query.to_string(), None)
            .await?;

        // Create indices for common query patterns
        let indices = vec![
            // Index for querying by model
            r#"ALTER TABLE GatewayAnalytics ADD INDEX idx_model_name model_name TYPE set(100) GRANULARITY 4;"#,
            // Index for querying by country
            r#"ALTER TABLE GatewayAnalytics ADD INDEX idx_country_code country_code TYPE set(300) GRANULARITY 4;"#,
            // Index for querying by status code
            r#"ALTER TABLE GatewayAnalytics ADD INDEX idx_status_code status_code TYPE set(20) GRANULARITY 4;"#,
            // Index for blocked requests
            r#"ALTER TABLE GatewayAnalytics ADD INDEX idx_is_blocked is_blocked TYPE minmax GRANULARITY 1;"#,
            // Index for endpoint queries
            r#"ALTER TABLE GatewayAnalytics ADD INDEX idx_endpoint_id endpoint_id TYPE bloom_filter(0.01) GRANULARITY 4;"#,
            // Index for client IP analysis
            r#"ALTER TABLE GatewayAnalytics ADD INDEX idx_client_ip client_ip TYPE bloom_filter(0.01) GRANULARITY 8;"#,
        ];

        for index_query in indices {
            self.clickhouse
                .run_query_synchronous(index_query.to_string(), None)
                .await?;
        }

        Ok(())
    }

    fn rollback_instructions(&self) -> String {
        r#"DROP TABLE IF EXISTS GatewayAnalytics;"#.to_string()
    }

    async fn has_succeeded(&self) -> Result<bool, Error> {
        let should_apply = self.should_apply().await?;
        Ok(!should_apply)
    }
}
