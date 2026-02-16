use axum::body::Body;
use axum::extract::State;
use axum::http::{HeaderMap, StatusCode, Uri};
use axum::response::{IntoResponse, Response};
use std::time::Duration;

use crate::gateway_util::AppStateData;

const OTLP_PROXY_TIMEOUT: Duration = Duration::from_secs(10);

/// POST /v1/traces, /v1/metrics, /v1/logs
/// Transparent proxy to the internal OTEL collector.
/// Auth is handled by the require_api_key_telemetry middleware.
pub async fn otlp_proxy_handler(
    State(app_state): State<AppStateData>,
    uri: Uri,
    headers: HeaderMap,
    body: Body,
) -> Result<Response, Response> {
    let collector_endpoint = &app_state.config.gateway.otlp_proxy.collector_endpoint;
    let url = format!("{}{}", collector_endpoint, uri.path());

    let mut req = app_state
        .http_client
        .post(&url)
        .timeout(OTLP_PROXY_TIMEOUT)
        .body(reqwest::Body::wrap_stream(body.into_data_stream()));

    for (name, value) in headers.iter() {
        if name != "host" && name != "connection" && name != "authorization" {
            req = req.header(name, value);
        }
    }

    match req.send().await {
        Ok(resp) => {
            let status = StatusCode::from_u16(resp.status().as_u16())
                .unwrap_or(StatusCode::BAD_GATEWAY);
            let resp_headers = resp.headers().clone();
            let resp_body = resp.bytes().await.unwrap_or_default();

            let mut response = (status, resp_body).into_response();
            for (name, value) in resp_headers.iter() {
                response.headers_mut().insert(name, value.clone());
            }
            Ok(response)
        }
        Err(e) => {
            tracing::warn!(error = %e, url = %url, "OTLP proxy: failed to reach OTEL collector");
            Err((StatusCode::BAD_GATEWAY, "OTEL collector unavailable").into_response())
        }
    }
}
