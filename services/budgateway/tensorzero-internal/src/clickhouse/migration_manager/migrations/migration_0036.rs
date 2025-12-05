use crate::clickhouse::migration_manager::migration_trait::Migration;
use crate::clickhouse::ClickHouseConnectionInfo;
use crate::error::{Error, ErrorDetails};
use async_trait::async_trait;

use super::{check_column_exists, check_table_exists};

/// This migration adds evaluation_id column to the ModelInferenceDetails and GatewayAnalytics tables
/// to track inferences associated with specific evaluations.
pub struct Migration0036<'a> {
    pub clickhouse: &'a ClickHouseConnectionInfo,
}

const MIGRATION_ID: &str = "0036";

#[async_trait]
impl Migration for Migration0036<'_> {
    async fn can_apply(&self) -> Result<(), Error> {
        // Check if ModelInferenceDetails table exists
        let model_inference_details_exists =
            check_table_exists(self.clickhouse, "ModelInferenceDetails", MIGRATION_ID).await?;

        if !model_inference_details_exists {
            return Err(Error::new(ErrorDetails::ClickHouseMigration {
                id: MIGRATION_ID.to_string(),
                message: "ModelInferenceDetails table does not exist".to_string(),
            }));
        }

        Ok(())
    }

    async fn should_apply(&self) -> Result<bool, Error> {
        // Check if evaluation_id column already exists in ModelInferenceDetails
        let evaluation_id_exists_mid = check_column_exists(
            self.clickhouse,
            "ModelInferenceDetails",
            "evaluation_id",
            MIGRATION_ID,
        )
        .await?;

        // Check if evaluation_id column already exists in GatewayAnalytics
        let gateway_analytics_exists =
            check_table_exists(self.clickhouse, "GatewayAnalytics", MIGRATION_ID).await?;

        let evaluation_id_exists_ga = if gateway_analytics_exists {
            check_column_exists(
                self.clickhouse,
                "GatewayAnalytics",
                "evaluation_id",
                MIGRATION_ID,
            )
            .await?
        } else {
            true // If table doesn't exist, consider it as "already done" for this column
        };

        // Apply if any column is missing
        Ok(!evaluation_id_exists_mid || !evaluation_id_exists_ga)
    }

    async fn apply(&self, _clean_start: bool) -> Result<(), Error> {
        // Add evaluation_id column to ModelInferenceDetails
        let query = r#"
            ALTER TABLE ModelInferenceDetails
            ADD COLUMN IF NOT EXISTS evaluation_id Nullable(UUID)
        "#;
        self.clickhouse
            .run_query_synchronous(query.to_string(), None)
            .await?;

        // Add index for evaluation_id in ModelInferenceDetails
        let index_query = r#"
            ALTER TABLE ModelInferenceDetails
            ADD INDEX IF NOT EXISTS idx_evaluation_id evaluation_id TYPE bloom_filter(0.01) GRANULARITY 4
        "#;
        self.clickhouse
            .run_query_synchronous(index_query.to_string(), None)
            .await?;

        // Check if GatewayAnalytics table exists before adding column
        let gateway_analytics_exists =
            check_table_exists(self.clickhouse, "GatewayAnalytics", MIGRATION_ID).await?;

        if gateway_analytics_exists {
            // Add evaluation_id column to GatewayAnalytics
            let ga_query = r#"
                ALTER TABLE GatewayAnalytics
                ADD COLUMN IF NOT EXISTS evaluation_id Nullable(UUID)
            "#;
            self.clickhouse
                .run_query_synchronous(ga_query.to_string(), None)
                .await?;

            // Add index for evaluation_id in GatewayAnalytics
            let ga_index_query = r#"
                ALTER TABLE GatewayAnalytics
                ADD INDEX IF NOT EXISTS idx_evaluation_id evaluation_id TYPE bloom_filter(0.01) GRANULARITY 4
            "#;
            self.clickhouse
                .run_query_synchronous(ga_index_query.to_string(), None)
                .await?;
        }

        Ok(())
    }

    fn rollback_instructions(&self) -> String {
        r#"
        ALTER TABLE ModelInferenceDetails DROP INDEX IF EXISTS idx_evaluation_id;
        ALTER TABLE ModelInferenceDetails DROP COLUMN IF EXISTS evaluation_id;
        ALTER TABLE GatewayAnalytics DROP INDEX IF EXISTS idx_evaluation_id;
        ALTER TABLE GatewayAnalytics DROP COLUMN IF EXISTS evaluation_id;
        "#
        .to_string()
    }

    async fn has_succeeded(&self) -> Result<bool, Error> {
        let should_apply = self.should_apply().await?;
        Ok(!should_apply)
    }
}
