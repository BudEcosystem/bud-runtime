#![cfg(test)]

use std::sync::Arc;

use crate::clickhouse::ClickHouseConnectionInfo;
use crate::config_parser::Config;
use crate::gateway_util::{setup_authentication, AppStateData};
use crate::kafka::KafkaConnectionInfo;

pub fn get_unit_test_app_state_data(
    config: Arc<Config<'static>>,
    clickhouse_healthy: bool,
) -> AppStateData {
    let http_client = reqwest::Client::new();
    let clickhouse_connection_info = ClickHouseConnectionInfo::new_mock(clickhouse_healthy);
    let kafka_connection_info = KafkaConnectionInfo::Disabled;

    AppStateData {
        config: config.clone(),
        http_client,
        clickhouse_connection_info,
        kafka_connection_info,
        authentication_info: setup_authentication(&config),
        model_credential_store: std::sync::Arc::new(std::sync::RwLock::new(
            std::collections::HashMap::new(),
        )),
        rate_limiter: None,
        usage_limiter: None,
        geoip_service: None,
        ua_parser: None,
        blocking_manager: None,
        guardrails: Arc::new(tokio::sync::RwLock::new(std::collections::HashMap::new())),
        inference_batcher: None, // Not used in tests
        use_case_proxy: crate::gateway_util::UseCaseProxyState::default(),
    }
}
