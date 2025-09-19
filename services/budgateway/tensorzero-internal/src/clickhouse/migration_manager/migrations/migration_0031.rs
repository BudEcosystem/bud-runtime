use crate::clickhouse::migration_manager::migration_trait::Migration;
use crate::clickhouse::ClickHouseConnectionInfo;
use crate::error::{Error, ErrorDetails};
use async_trait::async_trait;

use super::{check_column_exists, check_table_exists};

/// This migration adds observability support for all OpenAI-compatible endpoints
/// beyond chat completions. It adds:
/// 1. endpoint_type column to ModelInference table to differentiate API types
/// 2. EmbeddingInference table for embedding requests
/// 3. AudioInference table for audio transcription/translation/TTS requests
/// 4. ImageInference table for image generation requests
/// 5. ModerationInference table for moderation requests
pub struct Migration0031<'a> {
    pub clickhouse: &'a ClickHouseConnectionInfo,
}

const MIGRATION_ID: &str = "0031";

#[async_trait]
impl Migration for Migration0031<'_> {
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
        // Check if endpoint_type column exists in ModelInference
        let endpoint_type_exists = check_column_exists(
            self.clickhouse,
            "ModelInference",
            "endpoint_type",
            MIGRATION_ID,
        )
        .await?;

        // Check if new tables exist
        let embedding_inference_exists =
            check_table_exists(self.clickhouse, "EmbeddingInference", MIGRATION_ID).await?;
        let audio_inference_exists =
            check_table_exists(self.clickhouse, "AudioInference", MIGRATION_ID).await?;
        let image_inference_exists =
            check_table_exists(self.clickhouse, "ImageInference", MIGRATION_ID).await?;
        let moderation_inference_exists =
            check_table_exists(self.clickhouse, "ModerationInference", MIGRATION_ID).await?;

        // Apply if any component is missing
        Ok(!endpoint_type_exists
            || !embedding_inference_exists
            || !audio_inference_exists
            || !image_inference_exists
            || !moderation_inference_exists)
    }

    async fn apply(&self, _clean_start: bool) -> Result<(), Error> {
        // Add endpoint_type column to ModelInference table
        let query = r#"
            ALTER TABLE ModelInference
            ADD COLUMN IF NOT EXISTS endpoint_type LowCardinality(String) DEFAULT 'chat'
        "#;
        self.clickhouse
            .run_query_synchronous(query.to_string(), None)
            .await?;

        // Create EmbeddingInference table
        let query = r#"
            CREATE TABLE IF NOT EXISTS EmbeddingInference
            (
                id UUID,
                function_name LowCardinality(String),
                variant_name LowCardinality(String),
                episode_id UUID,
                input String,
                embeddings String,
                embedding_dimensions UInt32,
                input_count UInt32,
                inference_params String,
                processing_time_ms Nullable(UInt32),
                tags Map(String, String) DEFAULT map(),
                extra_body String DEFAULT '{}',
                timestamp DateTime MATERIALIZED UUIDv7ToDateTime(id)
            ) ENGINE = MergeTree()
            ORDER BY (function_name, id)
            PARTITION BY toYYYYMM(timestamp)
        "#;
        self.clickhouse
            .run_query_synchronous(query.to_string(), None)
            .await?;

        // Create AudioInference table
        let query = r#"
            CREATE TABLE IF NOT EXISTS AudioInference
            (
                id UUID,
                function_name LowCardinality(String),
                variant_name LowCardinality(String),
                episode_id UUID,
                audio_type Enum8('transcription' = 1, 'translation' = 2, 'text_to_speech' = 3),
                input String,
                output String,
                language Nullable(String),
                duration_seconds Nullable(Float32),
                file_size_bytes Nullable(UInt64),
                response_format LowCardinality(String),
                inference_params String,
                processing_time_ms Nullable(UInt32),
                tags Map(String, String) DEFAULT map(),
                extra_body String DEFAULT '{}',
                timestamp DateTime MATERIALIZED UUIDv7ToDateTime(id)
            ) ENGINE = MergeTree()
            ORDER BY (function_name, audio_type, id)
            PARTITION BY toYYYYMM(timestamp)
        "#;
        self.clickhouse
            .run_query_synchronous(query.to_string(), None)
            .await?;

        // Create ImageInference table
        let query = r#"
            CREATE TABLE IF NOT EXISTS ImageInference
            (
                id UUID,
                function_name LowCardinality(String),
                variant_name LowCardinality(String),
                episode_id UUID,
                prompt String,
                image_count UInt8,
                size LowCardinality(String),
                quality LowCardinality(String),
                style Nullable(String),
                response_format LowCardinality(String),
                images String,
                inference_params String,
                processing_time_ms Nullable(UInt32),
                tags Map(String, String) DEFAULT map(),
                extra_body String DEFAULT '{}',
                timestamp DateTime MATERIALIZED UUIDv7ToDateTime(id)
            ) ENGINE = MergeTree()
            ORDER BY (function_name, id)
            PARTITION BY toYYYYMM(timestamp)
        "#;
        self.clickhouse
            .run_query_synchronous(query.to_string(), None)
            .await?;

        // Create ModerationInference table
        let query = r#"
            CREATE TABLE IF NOT EXISTS ModerationInference
            (
                id UUID,
                function_name LowCardinality(String),
                variant_name LowCardinality(String),
                episode_id UUID,
                input String,
                results String,
                flagged Bool,
                categories Map(String, Bool),
                category_scores Map(String, Float32),
                inference_params String,
                processing_time_ms Nullable(UInt32),
                tags Map(String, String) DEFAULT map(),
                extra_body String DEFAULT '{}',
                timestamp DateTime MATERIALIZED UUIDv7ToDateTime(id)
            ) ENGINE = MergeTree()
            ORDER BY (function_name, flagged, id)
            PARTITION BY toYYYYMM(timestamp)
        "#;
        self.clickhouse
            .run_query_synchronous(query.to_string(), None)
            .await?;

        Ok(())
    }

    fn rollback_instructions(&self) -> String {
        r#"DROP TABLE IF EXISTS EmbeddingInference;
DROP TABLE IF EXISTS AudioInference;
DROP TABLE IF EXISTS ImageInference;
DROP TABLE IF EXISTS ModerationInference;
ALTER TABLE ModelInference DROP COLUMN IF EXISTS endpoint_type;"#
            .to_string()
    }

    async fn has_succeeded(&self) -> Result<bool, Error> {
        let should_apply = self.should_apply().await?;
        Ok(!should_apply)
    }
}
