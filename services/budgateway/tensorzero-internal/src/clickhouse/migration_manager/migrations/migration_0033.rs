use crate::clickhouse::migration_manager::migration_trait::Migration;
use crate::clickhouse::ClickHouseConnectionInfo;
use crate::error::Error;
use async_trait::async_trait;

use super::check_table_exists;

/// This migration creates the GatewayBlockingEvents table for storing blocked request events.
/// It captures details about which requests were blocked by which rules, enabling comprehensive
/// analytics and reporting on blocking rule effectiveness.
pub struct Migration0033<'a> {
    pub clickhouse: &'a ClickHouseConnectionInfo,
}

const MIGRATION_ID: &str = "0033";

#[async_trait]
impl Migration for Migration0033<'_> {
    async fn can_apply(&self) -> Result<(), Error> {
        Ok(())
    }

    async fn should_apply(&self) -> Result<bool, Error> {
        let table_exists =
            check_table_exists(self.clickhouse, "GatewayBlockingEvents", MIGRATION_ID).await?;
        Ok(!table_exists)
    }

    async fn apply(&self, _clean_start: bool) -> Result<(), Error> {
        // Create the GatewayBlockingEvents table
        let query = r#"
            CREATE TABLE IF NOT EXISTS GatewayBlockingEvents
            (
                -- Event identifiers
                id UUID,                           -- UUIDv7 for event record
                rule_id UUID,                      -- Blocking rule that triggered the block

                -- Client information
                client_ip String,
                country_code Nullable(String),
                user_agent Nullable(String),

                -- Request context
                request_path String,
                request_method LowCardinality(String),
                api_key_id Nullable(String),       -- Hashed/masked API key if available

                -- Project/endpoint context (optional)
                project_id Nullable(UUID),
                endpoint_id Nullable(UUID),
                model_name LowCardinality(Nullable(String)),

                -- Rule information
                rule_type LowCardinality(String),  -- IP_BLOCKING, COUNTRY_BLOCKING, etc.
                rule_name String,
                rule_priority Int32,

                -- Block details
                block_reason String,
                action_taken LowCardinality(String), -- BLOCK, RATE_LIMIT, etc.

                -- Timing
                blocked_at DateTime64(3),          -- When the block occurred

                -- Materialized columns for efficient querying
                timestamp DateTime MATERIALIZED toDateTime(blocked_at),
                date Date MATERIALIZED toDate(blocked_at),
                hour DateTime MATERIALIZED toStartOfHour(blocked_at)
            )
            ENGINE = MergeTree()
            PARTITION BY toYYYYMM(blocked_at)
            ORDER BY (rule_id, blocked_at, id)
            TTL toDateTime(blocked_at) + INTERVAL 90 DAY
            SETTINGS index_granularity = 8192;
        "#;

        self.clickhouse
            .run_query_synchronous(query.to_string(), None)
            .await?;

        // Create indices for common query patterns
        let indices = vec![
            // Index for querying by rule and timestamp for statistics
            r#"ALTER TABLE GatewayBlockingEvents ADD INDEX idx_rule_timestamp (rule_id, blocked_at) TYPE minmax GRANULARITY 1;"#,
            // Index for client IP analysis
            r#"ALTER TABLE GatewayBlockingEvents ADD INDEX idx_client_ip client_ip TYPE bloom_filter(0.01) GRANULARITY 8;"#,
            // Index for country-based analysis
            r#"ALTER TABLE GatewayBlockingEvents ADD INDEX idx_country_code country_code TYPE set(300) GRANULARITY 4;"#,
            // Index for rule type analysis
            r#"ALTER TABLE GatewayBlockingEvents ADD INDEX idx_rule_type rule_type TYPE set(10) GRANULARITY 4;"#,
            // Index for project-based queries
            r#"ALTER TABLE GatewayBlockingEvents ADD INDEX idx_project_timestamp (project_id, blocked_at) TYPE minmax GRANULARITY 1;"#,
            // Index for endpoint-based queries
            r#"ALTER TABLE GatewayBlockingEvents ADD INDEX idx_endpoint_timestamp (endpoint_id, blocked_at) TYPE minmax GRANULARITY 1;"#,
        ];

        for index_query in indices {
            self.clickhouse
                .run_query_synchronous(index_query.to_string(), None)
                .await?;
        }

        Ok(())
    }

    fn rollback_instructions(&self) -> String {
        r#"DROP TABLE IF EXISTS GatewayBlockingEvents;"#.to_string()
    }

    async fn has_succeeded(&self) -> Result<bool, Error> {
        let should_apply = self.should_apply().await?;
        Ok(!should_apply)
    }
}
