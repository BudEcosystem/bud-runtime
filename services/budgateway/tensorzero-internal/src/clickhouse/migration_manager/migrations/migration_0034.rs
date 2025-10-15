use crate::clickhouse::migration_manager::migration_trait::Migration;
use crate::clickhouse::ClickHouseConnectionInfo;
use crate::error::Error;
use async_trait::async_trait;

use super::check_table_exists;

/// This migration creates the GuardrailInference table for tracking guardrail scan results.
/// It enables comprehensive observability of content moderation activities including
/// multi-stage scanning, provider results, and performance metrics.
pub struct Migration0034<'a> {
    pub clickhouse: &'a ClickHouseConnectionInfo,
}

const MIGRATION_ID: &str = "0034";

#[async_trait]
impl Migration for Migration0034<'_> {
    async fn can_apply(&self) -> Result<(), Error> {
        Ok(())
    }

    async fn should_apply(&self) -> Result<bool, Error> {
        let table_exists =
            check_table_exists(self.clickhouse, "GuardrailInference", MIGRATION_ID).await?;
        Ok(!table_exists)
    }

    async fn apply(&self, _clean_start: bool) -> Result<(), Error> {
        // Create the GuardrailInference table
        let query = r#"
            CREATE TABLE IF NOT EXISTS GuardrailInference
            (
                -- Core identifiers
                id UUID,                              -- UUIDv7 for this specific scan
                inference_id UUID,                    -- Links to ModelInference
                parent_scan_id Nullable(UUID),        -- Links to parent scan (L2→L1, L3→L2)

                -- Scan configuration
                guardrail_profile LowCardinality(String),    -- Which guardrail config was used
                guard_type Enum8('input' = 1, 'output' = 2),
                scan_stage LowCardinality(String),           -- 'l1', 'l2', 'l3', 'multi', etc.
                scan_mode Enum8('single' = 1, 'provider_managed_multi' = 2, 'gateway_managed_multi' = 3),

                -- Results
                flagged Bool,                         -- Was content flagged at this stage
                confidence_score Nullable(Float32),   -- Confidence level of the scan
                provider_results String,              -- JSON with ALL provider details

                -- Performance & Status
                scan_status Enum8('completed' = 1, 'in_progress' = 2, 'cancelled' = 3, 'timed_out' = 4),
                scan_latency_ms Nullable(UInt32),    -- NULL if still in progress
                scan_started_at DateTime64(3),
                scan_completed_at Nullable(DateTime64(3)),

                -- Decision tracking
                action_taken LowCardinality(String),  -- 'allow', 'block', 'escalate_to_l2', etc.
                external_scan_id Nullable(String),    -- Provider's internal scan ID

                -- Content (for debugging/analysis)
                input_hash String,                    -- Hash of scanned content for privacy
                scan_metadata String DEFAULT '{}',    -- Additional metadata as JSON

                -- Materialized columns for efficient querying
                timestamp DateTime MATERIALIZED UUIDv7ToDateTime(id),
                date Date MATERIALIZED toDate(timestamp)
            )
            ENGINE = MergeTree()
            ORDER BY (inference_id, guard_type, scan_stage, id)
            PARTITION BY toYYYYMM(timestamp)
            TTL timestamp + INTERVAL 90 DAY
            SETTINGS index_granularity = 8192;
        "#;

        self.clickhouse
            .run_query_synchronous(query.to_string(), None)
            .await?;

        // Create indices for common query patterns
        let indices = vec![
            (
                "idx_guardrail_profile",
                r#"ALTER TABLE GuardrailInference ADD INDEX idx_guardrail_profile guardrail_profile TYPE set(100) GRANULARITY 4;"#,
            ),
            (
                "idx_flagged",
                r#"ALTER TABLE GuardrailInference ADD INDEX idx_flagged flagged TYPE set(2) GRANULARITY 1;"#,
            ),
            (
                "idx_scan_status",
                r#"ALTER TABLE GuardrailInference ADD INDEX idx_scan_status scan_status TYPE set(4) GRANULARITY 4;"#,
            ),
            (
                "idx_timestamp",
                r#"ALTER TABLE GuardrailInference ADD INDEX idx_timestamp timestamp TYPE minmax GRANULARITY 1;"#,
            ),
        ];

        for (index_name, index_query) in indices {
            // Check if index already exists
            let check_query = format!(
                "SELECT count() FROM system.data_skipping_indices WHERE table = 'GuardrailInference' AND name = '{}' AND database = currentDatabase()",
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
        r#"DROP TABLE IF EXISTS GuardrailInference;"#.to_string()
    }

    async fn has_succeeded(&self) -> Result<bool, Error> {
        let should_apply = self.should_apply().await?;
        Ok(!should_apply)
    }
}
