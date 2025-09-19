use crate::clickhouse::migration_manager::migration_trait::Migration;
use crate::clickhouse::ClickHouseConnectionInfo;
use crate::error::{Error, ErrorDetails};
use async_trait::async_trait;

use super::{check_column_exists, check_table_exists};

/// This migration adds guardrail-related columns to the ModelInference table
/// to track guardrail scan summaries and their impact on response handling.
pub struct Migration0035<'a> {
    pub clickhouse: &'a ClickHouseConnectionInfo,
}

const MIGRATION_ID: &str = "0035";

#[async_trait]
impl Migration for Migration0035<'_> {
    async fn can_apply(&self) -> Result<(), Error> {
        // Check if ModelInference table exists
        let model_inference_exists =
            check_table_exists(self.clickhouse, "ModelInference", MIGRATION_ID).await?;

        if !model_inference_exists {
            return Err(Error::new(ErrorDetails::ClickHouseMigration {
                id: MIGRATION_ID.to_string(),
                message: "ModelInference table does not exist".to_string(),
            }));
        }

        Ok(())
    }

    async fn should_apply(&self) -> Result<bool, Error> {
        // Check if guardrail column already exists
        let guardrail_scan_summary_exists = check_column_exists(
            self.clickhouse,
            "ModelInference",
            "guardrail_scan_summary",
            MIGRATION_ID,
        )
        .await?;

        // Apply if column is missing
        Ok(!guardrail_scan_summary_exists)
    }

    async fn apply(&self, _clean_start: bool) -> Result<(), Error> {
        // Add guardrail_scan_summary column
        let query = r#"
            ALTER TABLE ModelInference
            ADD COLUMN IF NOT EXISTS guardrail_scan_summary String DEFAULT '{}'
        "#;
        self.clickhouse
            .run_query_synchronous(query.to_string(), None)
            .await?;

        Ok(())
    }

    fn rollback_instructions(&self) -> String {
        r#"
        ALTER TABLE ModelInference DROP COLUMN IF EXISTS guardrail_scan_summary;
        "#
        .to_string()
    }

    async fn has_succeeded(&self) -> Result<bool, Error> {
        let should_apply = self.should_apply().await?;
        Ok(!should_apply)
    }
}
