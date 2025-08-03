use crate::clickhouse::migration_manager::migration_trait::Migration;
use crate::clickhouse::ClickHouseConnectionInfo;
use crate::error::Error;
use async_trait::async_trait;

use super::check_column_exists;

/// This migration adds gateway_request and gateway_response columns to the ModelInference table
/// to support observability of what the gateway receives from clients and sends back to them,
/// in addition to the existing raw_request/raw_response which track provider communication.
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
        // Check if gateway_request column already exists
        let gateway_request_exists = check_column_exists(
            self.clickhouse,
            "ModelInference",
            "gateway_request",
            MIGRATION_ID,
        )
        .await?;

        // Check if gateway_response column already exists
        let gateway_response_exists = check_column_exists(
            self.clickhouse,
            "ModelInference",
            "gateway_response",
            MIGRATION_ID,
        )
        .await?;

        // Apply migration if either column is missing
        Ok(!gateway_request_exists || !gateway_response_exists)
    }

    async fn apply(&self, _clean_start: bool) -> Result<(), Error> {
        // Add gateway_request column
        self.clickhouse
            .run_query_synchronous(
                "ALTER TABLE ModelInference ADD COLUMN IF NOT EXISTS gateway_request Nullable(String)".to_string(),
                None,
            )
            .await?;

        // Add gateway_response column
        self.clickhouse
            .run_query_synchronous(
                "ALTER TABLE ModelInference ADD COLUMN IF NOT EXISTS gateway_response Nullable(String)".to_string(),
                None,
            )
            .await?;

        Ok(())
    }

    fn rollback_instructions(&self) -> String {
        r#"
        ALTER TABLE ModelInference DROP COLUMN IF EXISTS gateway_request;
        ALTER TABLE ModelInference DROP COLUMN IF EXISTS gateway_response;
        "#
        .to_string()
    }

    async fn has_succeeded(&self) -> Result<bool, Error> {
        let should_apply = self.should_apply().await?;
        Ok(!should_apply)
    }
}
