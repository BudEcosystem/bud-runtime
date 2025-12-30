use crate::clickhouse::migration_manager::migration_trait::Migration;
use crate::clickhouse::ClickHouseConnectionInfo;
use crate::error::{Error, ErrorDetails};
use async_trait::async_trait;

use super::{check_column_exists, check_table_exists};

/// This migration adds the country_name column to the GatewayAnalytics table.
/// The column was missing from the original migration (0032) but the Rust struct
/// expects it, causing analytics writes to fail silently.
pub struct Migration0036<'a> {
    pub clickhouse: &'a ClickHouseConnectionInfo,
}

const MIGRATION_ID: &str = "0036";

#[async_trait]
impl Migration for Migration0036<'_> {
    async fn can_apply(&self) -> Result<(), Error> {
        // Check if GatewayAnalytics table exists
        let table_exists =
            check_table_exists(self.clickhouse, "GatewayAnalytics", MIGRATION_ID).await?;

        if !table_exists {
            return Err(Error::new(ErrorDetails::ClickHouseMigration {
                id: MIGRATION_ID.to_string(),
                message: "GatewayAnalytics table does not exist".to_string(),
            }));
        }

        Ok(())
    }

    async fn should_apply(&self) -> Result<bool, Error> {
        // Check if country_name column already exists
        let column_exists = check_column_exists(
            self.clickhouse,
            "GatewayAnalytics",
            "country_name",
            MIGRATION_ID,
        )
        .await?;

        // Apply if column is missing
        Ok(!column_exists)
    }

    async fn apply(&self, _clean_start: bool) -> Result<(), Error> {
        // Add country_name column after country_code
        let query = r#"
            ALTER TABLE GatewayAnalytics
            ADD COLUMN IF NOT EXISTS country_name Nullable(String) AFTER country_code
        "#;
        self.clickhouse
            .run_query_synchronous(query.to_string(), None)
            .await?;

        Ok(())
    }

    fn rollback_instructions(&self) -> String {
        r#"
        ALTER TABLE GatewayAnalytics DROP COLUMN IF EXISTS country_name;
        "#
        .to_string()
    }

    async fn has_succeeded(&self) -> Result<bool, Error> {
        let should_apply = self.should_apply().await?;
        Ok(!should_apply)
    }
}
