//! Analytics Batcher - Batches analytics records for efficient ClickHouse writes
//!
//! This module provides a batch processor actor that accumulates analytics records
//! and writes them to ClickHouse in batches, reducing the number of individual
//! database writes and improving throughput under high load.
//!
//! ## Design
//!
//! The batcher uses an actor pattern with a tokio mpsc channel:
//! - Producers (request handlers) send records to the channel
//! - A background task accumulates records and flushes based on:
//!   - Batch size threshold (e.g., 500 records)
//!   - Time interval (e.g., every 1 second)
//!
//! ## Concurrency
//!
//! - Channel buffer: 10,000 pending records
//! - Non-blocking send: `try_send()` for fire-and-forget
//! - Graceful degradation: Logs errors but doesn't block requests

use std::sync::Arc;
use std::time::Duration;
use tokio::sync::mpsc;
use tokio::time::interval;
use tracing::{debug, error, info, warn};

use crate::analytics::GatewayAnalyticsDatabaseInsert;
use crate::clickhouse::ClickHouseConnectionInfo;

/// Default batch size before flush
const DEFAULT_BATCH_SIZE: usize = 500;

/// Default flush interval in milliseconds
const DEFAULT_FLUSH_INTERVAL_MS: u64 = 1000;

/// Channel buffer size (max pending records)
const CHANNEL_BUFFER_SIZE: usize = 10000;

/// Analytics batcher that accumulates records and writes them in batches
#[derive(Clone)]
pub struct AnalyticsBatcher {
    tx: mpsc::Sender<GatewayAnalyticsDatabaseInsert>,
}

impl AnalyticsBatcher {
    /// Create a new batcher with default settings (500 records, 1 second flush)
    pub fn new(clickhouse: Arc<ClickHouseConnectionInfo>) -> Self {
        Self::with_config(clickhouse, DEFAULT_BATCH_SIZE, DEFAULT_FLUSH_INTERVAL_MS)
    }

    /// Create a new batcher with custom configuration
    ///
    /// # Arguments
    /// * `clickhouse` - ClickHouse connection info
    /// * `batch_size` - Number of records to accumulate before flushing
    /// * `flush_interval_ms` - Maximum time between flushes in milliseconds
    pub fn with_config(
        clickhouse: Arc<ClickHouseConnectionInfo>,
        batch_size: usize,
        flush_interval_ms: u64,
    ) -> Self {
        let (tx, rx) = mpsc::channel(CHANNEL_BUFFER_SIZE);

        // Spawn the background batch processor
        tokio::spawn(Self::batch_processor(
            rx,
            clickhouse,
            batch_size,
            flush_interval_ms,
        ));

        Self { tx }
    }

    /// Send a record to be batched (async, may block if channel is full)
    pub async fn send(&self, record: GatewayAnalyticsDatabaseInsert) {
        if let Err(e) = self.tx.send(record).await {
            error!("Failed to send analytics record to batcher: {}", e);
        }
    }

    /// Try to send a record without blocking (fire-and-forget)
    ///
    /// This is the preferred method for request handlers as it won't
    /// add latency to the response path even if the batcher is busy.
    pub fn try_send(&self, record: GatewayAnalyticsDatabaseInsert) {
        match self.tx.try_send(record) {
            Ok(_) => {
                debug!("Analytics record queued for batching");
            }
            Err(mpsc::error::TrySendError::Full(_)) => {
                warn!("Analytics batcher channel full, dropping record");
            }
            Err(mpsc::error::TrySendError::Closed(_)) => {
                error!("Analytics batcher channel closed");
            }
        }
    }

    /// Background task that accumulates and flushes batches
    async fn batch_processor(
        mut rx: mpsc::Receiver<GatewayAnalyticsDatabaseInsert>,
        clickhouse: Arc<ClickHouseConnectionInfo>,
        batch_size: usize,
        flush_interval_ms: u64,
    ) {
        let mut buffer: Vec<GatewayAnalyticsDatabaseInsert> = Vec::with_capacity(batch_size);
        let mut flush_timer = interval(Duration::from_millis(flush_interval_ms));

        info!(
            "Analytics batcher started: batch_size={}, flush_interval={}ms, channel_buffer={}",
            batch_size, flush_interval_ms, CHANNEL_BUFFER_SIZE
        );

        loop {
            tokio::select! {
                // Receive new records
                msg = rx.recv() => {
                    match msg {
                        Some(record) => {
                            buffer.push(record);

                            // Flush if batch size reached
                            if buffer.len() >= batch_size {
                                Self::flush_batch(&clickhouse, &mut buffer).await;
                            }
                        }
                        None => {
                            // Channel closed, flush remaining and exit
                            info!("Analytics batcher channel closed, flushing remaining {} records", buffer.len());
                            if !buffer.is_empty() {
                                Self::flush_batch(&clickhouse, &mut buffer).await;
                            }
                            break;
                        }
                    }
                }

                // Periodic flush (every flush_interval_ms)
                _ = flush_timer.tick() => {
                    if !buffer.is_empty() {
                        Self::flush_batch(&clickhouse, &mut buffer).await;
                    }
                }
            }
        }

        info!("Analytics batcher stopped");
    }

    /// Flush the current buffer to ClickHouse
    async fn flush_batch(
        clickhouse: &ClickHouseConnectionInfo,
        buffer: &mut Vec<GatewayAnalyticsDatabaseInsert>,
    ) {
        if buffer.is_empty() {
            return;
        }

        let batch_len = buffer.len();
        debug!("Flushing analytics batch: {} records", batch_len);

        match clickhouse.write(buffer.as_slice(), "GatewayAnalytics").await {
            Ok(_) => {
                debug!("Successfully wrote {} analytics records to ClickHouse", batch_len);
            }
            Err(e) => {
                error!(
                    "Failed to write analytics batch ({} records) to ClickHouse: {}",
                    batch_len, e
                );
                // Note: Records are lost on failure. For critical analytics,
                // consider implementing a dead-letter queue or retry mechanism.
            }
        }

        buffer.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::analytics::GatewayAnalyticsDatabaseInsert;
    use chrono::Utc;
    use std::collections::HashMap;
    use uuid::Uuid;

    fn create_test_record() -> GatewayAnalyticsDatabaseInsert {
        GatewayAnalyticsDatabaseInsert {
            id: Uuid::now_v7(),
            request_timestamp: Utc::now(),
            response_timestamp: Utc::now(),
            client_ip: "127.0.0.1".to_string(),
            proxy_chain: None,
            protocol_version: "HTTP/1.1".to_string(),
            method: "POST".to_string(),
            path: "/v1/chat/completions".to_string(),
            query_params: None,
            user_agent: Some("test-agent".to_string()),
            browser_name: None,
            browser_version: None,
            os_name: None,
            os_version: None,
            device_type: None,
            is_bot: false,
            country_code: None,
            country_name: None,
            region: None,
            city: None,
            latitude: None,
            longitude: None,
            timezone: None,
            asn: None,
            isp: None,
            request_headers: HashMap::new(),
            response_headers: HashMap::new(),
            body_size: None,
            api_key_id: None,
            auth_method: None,
            user_id: None,
            project_id: None,
            endpoint_id: None,
            model_name: None,
            model_provider: None,
            model_version: None,
            routing_decision: None,
            response_size: None,
            error_type: None,
            error_message: None,
            status_code: 200,
            total_duration_ms: 100,
            gateway_processing_ms: 10,
            model_latency_ms: Some(90),
            inference_id: None,
            is_blocked: false,
            blocking_event: None,
            tags: HashMap::new(),
        }
    }

    #[tokio::test]
    async fn test_batcher_try_send() {
        // Create a mock/disabled clickhouse connection
        let clickhouse = Arc::new(ClickHouseConnectionInfo::Disabled);
        let batcher = AnalyticsBatcher::with_config(clickhouse, 10, 100);

        // Should not panic or block
        let record = create_test_record();
        batcher.try_send(record);

        // Give the batcher time to process
        tokio::time::sleep(Duration::from_millis(50)).await;
    }

    #[tokio::test]
    async fn test_batcher_async_send() {
        let clickhouse = Arc::new(ClickHouseConnectionInfo::Disabled);
        let batcher = AnalyticsBatcher::with_config(clickhouse, 10, 100);

        let record = create_test_record();
        batcher.send(record).await;

        tokio::time::sleep(Duration::from_millis(50)).await;
    }
}
