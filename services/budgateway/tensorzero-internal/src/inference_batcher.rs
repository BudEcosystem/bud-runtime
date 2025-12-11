//! Inference Batcher - Batches inference records for efficient ClickHouse writes
//!
//! This module provides a batch processor that accumulates inference records
//! and writes them to ClickHouse in batches, reducing the number of individual
//! database writes and improving throughput under high load.
//!
//! ## Design
//!
//! The batcher uses an actor pattern with tokio mpsc channels:
//! - Producers (inference handlers) send records to channels
//! - Background tasks accumulate records and flush based on:
//!   - Batch size threshold (e.g., 500 records)
//!   - Time interval (e.g., every 1 second)
//!
//! ## Supported Tables
//!
//! - ModelInference (serde_json::Value)
//! - ChatInference
//! - JsonInference
//! - EmbeddingInference
//! - AudioInference
//! - ImageInference
//! - ModerationInference
//!
//! ## Concurrency
//!
//! - Channel buffer: 10,000 pending records per table
//! - Non-blocking send: `try_send_*()` for fire-and-forget
//! - Graceful degradation: Logs errors but doesn't block requests

use std::sync::Arc;
use std::time::Duration;
use tokio::sync::mpsc;
use tokio::time::interval;
use tracing::{debug, error, info, warn};

use crate::clickhouse::ClickHouseConnectionInfo;
use crate::guardrail::GuardrailInferenceDatabaseInsert;
use crate::inference::types::{
    AudioInferenceDatabaseInsert, ChatInferenceDatabaseInsert, EmbeddingInferenceDatabaseInsert,
    ImageInferenceDatabaseInsert, JsonInferenceDatabaseInsert, ModerationInferenceDatabaseInsert,
};

/// Default batch size before flush
const DEFAULT_BATCH_SIZE: usize = 500;

/// Default flush interval in milliseconds
const DEFAULT_FLUSH_INTERVAL_MS: u64 = 1000;

/// Channel buffer size (max pending records per table)
const CHANNEL_BUFFER_SIZE: usize = 10000;

/// Inference batcher that accumulates records and writes them in batches
#[derive(Clone, Debug)]
pub struct InferenceBatcher {
    model_inference_tx: mpsc::Sender<serde_json::Value>,
    chat_inference_tx: mpsc::Sender<ChatInferenceDatabaseInsert>,
    json_inference_tx: mpsc::Sender<JsonInferenceDatabaseInsert>,
    embedding_inference_tx: mpsc::Sender<EmbeddingInferenceDatabaseInsert>,
    audio_inference_tx: mpsc::Sender<AudioInferenceDatabaseInsert>,
    image_inference_tx: mpsc::Sender<ImageInferenceDatabaseInsert>,
    moderation_inference_tx: mpsc::Sender<ModerationInferenceDatabaseInsert>,
    guardrail_inference_tx: mpsc::Sender<GuardrailInferenceDatabaseInsert>,
}

impl InferenceBatcher {
    /// Create a new batcher with default settings (500 records, 1 second flush)
    pub fn new(clickhouse: Arc<ClickHouseConnectionInfo>) -> Self {
        Self::with_config(clickhouse, DEFAULT_BATCH_SIZE, DEFAULT_FLUSH_INTERVAL_MS)
    }

    /// Create a new batcher with custom configuration
    pub fn with_config(
        clickhouse: Arc<ClickHouseConnectionInfo>,
        batch_size: usize,
        flush_interval_ms: u64,
    ) -> Self {
        // Create channels for each table type
        let (model_inference_tx, model_inference_rx) = mpsc::channel(CHANNEL_BUFFER_SIZE);
        let (chat_inference_tx, chat_inference_rx) = mpsc::channel(CHANNEL_BUFFER_SIZE);
        let (json_inference_tx, json_inference_rx) = mpsc::channel(CHANNEL_BUFFER_SIZE);
        let (embedding_inference_tx, embedding_inference_rx) = mpsc::channel(CHANNEL_BUFFER_SIZE);
        let (audio_inference_tx, audio_inference_rx) = mpsc::channel(CHANNEL_BUFFER_SIZE);
        let (image_inference_tx, image_inference_rx) = mpsc::channel(CHANNEL_BUFFER_SIZE);
        let (moderation_inference_tx, moderation_inference_rx) = mpsc::channel(CHANNEL_BUFFER_SIZE);
        let (guardrail_inference_tx, guardrail_inference_rx) = mpsc::channel(CHANNEL_BUFFER_SIZE);

        // Spawn background processors for each table
        tokio::spawn(Self::batch_processor(
            model_inference_rx,
            clickhouse.clone(),
            batch_size,
            flush_interval_ms,
            "ModelInference",
        ));

        tokio::spawn(Self::batch_processor(
            chat_inference_rx,
            clickhouse.clone(),
            batch_size,
            flush_interval_ms,
            "ChatInference",
        ));

        tokio::spawn(Self::batch_processor(
            json_inference_rx,
            clickhouse.clone(),
            batch_size,
            flush_interval_ms,
            "JsonInference",
        ));

        tokio::spawn(Self::batch_processor(
            embedding_inference_rx,
            clickhouse.clone(),
            batch_size,
            flush_interval_ms,
            "EmbeddingInference",
        ));

        tokio::spawn(Self::batch_processor(
            audio_inference_rx,
            clickhouse.clone(),
            batch_size,
            flush_interval_ms,
            "AudioInference",
        ));

        tokio::spawn(Self::batch_processor(
            image_inference_rx,
            clickhouse.clone(),
            batch_size,
            flush_interval_ms,
            "ImageInference",
        ));

        tokio::spawn(Self::batch_processor(
            moderation_inference_rx,
            clickhouse.clone(),
            batch_size,
            flush_interval_ms,
            "ModerationInference",
        ));

        tokio::spawn(Self::batch_processor(
            guardrail_inference_rx,
            clickhouse.clone(),
            batch_size,
            flush_interval_ms,
            "GuardrailInference",
        ));

        info!(
            "Inference batcher started: batch_size={}, flush_interval={}ms, channel_buffer={}",
            batch_size, flush_interval_ms, CHANNEL_BUFFER_SIZE
        );

        Self {
            model_inference_tx,
            chat_inference_tx,
            json_inference_tx,
            embedding_inference_tx,
            audio_inference_tx,
            image_inference_tx,
            moderation_inference_tx,
            guardrail_inference_tx,
        }
    }

    // ---- Try-send methods (non-blocking, fire-and-forget) ----

    /// Try to send a ModelInference record without blocking
    pub fn try_send_model_inference(&self, record: serde_json::Value) {
        Self::try_send(&self.model_inference_tx, record, "ModelInference");
    }

    /// Try to send a ChatInference record without blocking
    pub fn try_send_chat_inference(&self, record: ChatInferenceDatabaseInsert) {
        Self::try_send(&self.chat_inference_tx, record, "ChatInference");
    }

    /// Try to send a JsonInference record without blocking
    pub fn try_send_json_inference(&self, record: JsonInferenceDatabaseInsert) {
        Self::try_send(&self.json_inference_tx, record, "JsonInference");
    }

    /// Try to send an EmbeddingInference record without blocking
    pub fn try_send_embedding_inference(&self, record: EmbeddingInferenceDatabaseInsert) {
        Self::try_send(&self.embedding_inference_tx, record, "EmbeddingInference");
    }

    /// Try to send an AudioInference record without blocking
    pub fn try_send_audio_inference(&self, record: AudioInferenceDatabaseInsert) {
        Self::try_send(&self.audio_inference_tx, record, "AudioInference");
    }

    /// Try to send an ImageInference record without blocking
    pub fn try_send_image_inference(&self, record: ImageInferenceDatabaseInsert) {
        Self::try_send(&self.image_inference_tx, record, "ImageInference");
    }

    /// Try to send a ModerationInference record without blocking
    pub fn try_send_moderation_inference(&self, record: ModerationInferenceDatabaseInsert) {
        Self::try_send(&self.moderation_inference_tx, record, "ModerationInference");
    }

    /// Try to send GuardrailInference records without blocking
    pub fn try_send_guardrail_inferences(&self, records: Vec<GuardrailInferenceDatabaseInsert>) {
        for record in records {
            Self::try_send(&self.guardrail_inference_tx, record, "GuardrailInference");
        }
    }

    /// Generic try_send helper
    fn try_send<T>(tx: &mpsc::Sender<T>, record: T, table_name: &str) {
        match tx.try_send(record) {
            Ok(_) => {
                debug!("{} record queued for batching", table_name);
            }
            Err(mpsc::error::TrySendError::Full(_)) => {
                warn!(
                    "Inference batcher {} channel full, dropping record",
                    table_name
                );
            }
            Err(mpsc::error::TrySendError::Closed(_)) => {
                error!("Inference batcher {} channel closed", table_name);
            }
        }
    }

    /// Generic batch processor for any serializable type
    async fn batch_processor<T: serde::Serialize + Send + Sync + 'static>(
        mut rx: mpsc::Receiver<T>,
        clickhouse: Arc<ClickHouseConnectionInfo>,
        batch_size: usize,
        flush_interval_ms: u64,
        table_name: &'static str,
    ) {
        let mut buffer: Vec<T> = Vec::with_capacity(batch_size);
        let mut flush_timer = interval(Duration::from_millis(flush_interval_ms));

        debug!(
            "Inference batcher for {} started: batch_size={}, flush_interval={}ms",
            table_name, batch_size, flush_interval_ms
        );

        loop {
            tokio::select! {
                msg = rx.recv() => {
                    match msg {
                        Some(record) => {
                            buffer.push(record);

                            // Flush if batch size reached
                            if buffer.len() >= batch_size {
                                Self::flush_batch(&clickhouse, &mut buffer, table_name).await;
                            }
                        }
                        None => {
                            // Channel closed, flush remaining and exit
                            info!(
                                "Inference batcher {} channel closed, flushing remaining {} records",
                                table_name,
                                buffer.len()
                            );
                            if !buffer.is_empty() {
                                Self::flush_batch(&clickhouse, &mut buffer, table_name).await;
                            }
                            break;
                        }
                    }
                }

                // Periodic flush
                _ = flush_timer.tick() => {
                    if !buffer.is_empty() {
                        Self::flush_batch(&clickhouse, &mut buffer, table_name).await;
                    }
                }
            }
        }

        info!("Inference batcher for {} stopped", table_name);
    }

    /// Flush the current buffer to ClickHouse
    async fn flush_batch<T: serde::Serialize + Send + Sync>(
        clickhouse: &ClickHouseConnectionInfo,
        buffer: &mut Vec<T>,
        table_name: &str,
    ) {
        if buffer.is_empty() {
            return;
        }

        let batch_len = buffer.len();
        debug!("Flushing {} batch: {} records", table_name, batch_len);

        match clickhouse.write(buffer.as_slice(), table_name).await {
            Ok(_) => {
                debug!(
                    "Successfully wrote {} {} records to ClickHouse",
                    batch_len, table_name
                );
            }
            Err(e) => {
                error!(
                    "Failed to write {} batch ({} records) to ClickHouse: {}",
                    table_name, batch_len, e
                );
            }
        }

        buffer.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use uuid::Uuid;

    use crate::endpoints::inference::InferenceParams;
    use crate::inference::types::resolved_input::ResolvedInput;

    fn create_test_chat_inference() -> ChatInferenceDatabaseInsert {
        ChatInferenceDatabaseInsert {
            id: Uuid::now_v7(),
            function_name: "test_function".to_string(),
            variant_name: "test_variant".to_string(),
            episode_id: Uuid::now_v7(),
            input: ResolvedInput {
                system: None,
                messages: vec![],
            },
            output: vec![],
            tool_params: None,
            inference_params: InferenceParams::default(),
            processing_time_ms: Some(100),
            tags: HashMap::new(),
            extra_body: Default::default(),
        }
    }

    #[tokio::test]
    async fn test_batcher_try_send_chat_inference() {
        let clickhouse = Arc::new(ClickHouseConnectionInfo::Disabled);
        let batcher = InferenceBatcher::with_config(clickhouse, 10, 100);

        let record = create_test_chat_inference();
        batcher.try_send_chat_inference(record);

        // Give the batcher time to process
        tokio::time::sleep(Duration::from_millis(50)).await;
    }

    #[tokio::test]
    async fn test_batcher_try_send_model_inference() {
        let clickhouse = Arc::new(ClickHouseConnectionInfo::Disabled);
        let batcher = InferenceBatcher::with_config(clickhouse, 10, 100);

        let record = serde_json::json!({
            "id": Uuid::now_v7().to_string(),
            "inference_id": Uuid::now_v7().to_string(),
            "raw_request": "{}",
            "raw_response": "{}",
            "model_name": "test-model",
            "model_provider_name": "test-provider"
        });
        batcher.try_send_model_inference(record);

        tokio::time::sleep(Duration::from_millis(50)).await;
    }
}
