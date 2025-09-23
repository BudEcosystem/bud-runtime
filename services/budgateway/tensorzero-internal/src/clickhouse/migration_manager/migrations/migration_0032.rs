use crate::clickhouse::migration_manager::migration_trait::Migration;
use crate::clickhouse::ClickHouseConnectionInfo;
use crate::error::Error;
use async_trait::async_trait;

use super::check_table_exists;

/// This migration creates the GatewayAnalytics table for storing API gateway request analytics.
/// It captures comprehensive metadata about each request including network info, geographical data,
/// client information, performance metrics, and blocking decisions.
pub struct Migration0032<'a> {
    pub clickhouse: &'a ClickHouseConnectionInfo,
}

const MIGRATION_ID: &str = "0032";

#[async_trait]
impl Migration for Migration0032<'_> {
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
                device_type LowCardinality(Nullable(String)),
                browser_name LowCardinality(Nullable(String)),
                browser_version Nullable(String),
                os_name LowCardinality(Nullable(String)),
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
                auth_method LowCardinality(Nullable(String)),
                user_id Nullable(String),
                project_id Nullable(UUID),
                endpoint_id Nullable(UUID),

                -- Performance metrics
                request_timestamp DateTime64(3),
                response_timestamp DateTime64(3),
                gateway_processing_ms UInt32,
                total_duration_ms UInt32,

                -- Model routing information
                model_name LowCardinality(Nullable(String)),
                model_provider LowCardinality(Nullable(String)),
                model_version Nullable(String),
                routing_decision LowCardinality(Nullable(String)),

                -- Response metadata
                status_code UInt16,
                response_size Nullable(UInt32),
                response_headers Map(String, String),
                error_type LowCardinality(Nullable(String)),
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
            ORDER BY (timestamp, id)
            TTL toDateTime(request_timestamp) + INTERVAL 90 DAY
            SETTINGS index_granularity = 8192;
        "#;

        self.clickhouse
            .run_query_synchronous(query.to_string(), None)
            .await?;

        // Create indices for common query patterns with idempotent checks
        let indices = vec![
            (
                "idx_model_name",
                r#"ALTER TABLE GatewayAnalytics ADD INDEX idx_model_name model_name TYPE set(100) GRANULARITY 4;"#,
            ),
            (
                "idx_country_code",
                r#"ALTER TABLE GatewayAnalytics ADD INDEX idx_country_code country_code TYPE set(300) GRANULARITY 4;"#,
            ),
            (
                "idx_status_code",
                r#"ALTER TABLE GatewayAnalytics ADD INDEX idx_status_code status_code TYPE set(20) GRANULARITY 4;"#,
            ),
            (
                "idx_is_blocked",
                r#"ALTER TABLE GatewayAnalytics ADD INDEX idx_is_blocked is_blocked TYPE minmax GRANULARITY 1;"#,
            ),
            (
                "idx_endpoint_id",
                r#"ALTER TABLE GatewayAnalytics ADD INDEX idx_endpoint_id endpoint_id TYPE bloom_filter(0.01) GRANULARITY 4;"#,
            ),
            (
                "idx_client_ip",
                r#"ALTER TABLE GatewayAnalytics ADD INDEX idx_client_ip client_ip TYPE bloom_filter(0.01) GRANULARITY 8;"#,
            ),
        ];

        for (index_name, index_query) in indices {
            // Check if index already exists
            let check_query = format!(
                "SELECT count() FROM system.data_skipping_indices WHERE table = 'GatewayAnalytics' AND name = '{}' AND database = currentDatabase()",
                index_name
            );
            let result = self
                .clickhouse
                .run_query_synchronous(check_query, None)
                .await?;

            if result.trim() == "0" {
                // Index doesn't exist, create it
                if let Err(e) = self
                    .clickhouse
                    .run_query_synchronous(index_query.to_string(), None)
                    .await
                {
                    // Handle the case where index was created concurrently
                    if !e
                        .to_string()
                        .contains("index with this name already exists")
                    {
                        return Err(e);
                    }
                }
            }
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
