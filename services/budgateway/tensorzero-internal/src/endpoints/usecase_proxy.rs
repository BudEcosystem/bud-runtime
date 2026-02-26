use axum::body::Body;
use axum::extract::{Path, RawQuery, State};
use axum::http::{HeaderMap, Method, StatusCode};
#[cfg(test)]
use axum::http::HeaderValue;
use axum::response::{IntoResponse, Response};

use crate::gateway_util::{AppStateData, AuthenticationInfo};

/// Proxy handler for use case API requests.
///
/// Routes incoming requests to the appropriate deployment's ingress endpoint
/// by looking up the deployment route from the `UseCaseProxyState`.
///
/// Path pattern: `/usecases/{deployment_id}/api/{rest}`
///
/// Authentication: requires a valid API key whose `project_id` matches
/// the deployment route's `project_id`.
pub async fn usecase_api_proxy_handler(
    State(app_state): State<AppStateData>,
    Path((deployment_id, rest)): Path<(String, String)>,
    RawQuery(query_string): RawQuery,
    headers: HeaderMap,
    method: Method,
    body: Body,
) -> Result<Response<Body>, Response<Body>> {
    // 1. Validate API key and extract project_id
    let caller_project_id = validate_api_key_for_proxy(&app_state, &headers).map_err(|e| *e)?;

    // 2. Look up DeploymentRoute from UseCaseProxyState
    let route = {
        let routes = app_state.use_case_proxy.deployment_routes.read().await;
        routes.get(&deployment_id).cloned()
    };

    let route = route.ok_or_else(|| {
        let body = serde_json::json!({
            "error": "Deployment route not found"
        });
        (StatusCode::NOT_FOUND, axum::Json(body)).into_response()
    })?;

    // 3. Verify that the caller's project_id matches the route's project_id.
    // When caller_project_id is None (auth disabled or no project scoping on key),
    // we still enforce project matching against the route's project_id.
    match caller_project_id {
        Some(ref caller_pid) => {
            if *caller_pid != route.project_id {
                let body = serde_json::json!({
                    "error": "API key is not authorized for this deployment"
                });
                return Err((StatusCode::FORBIDDEN, axum::Json(body)).into_response());
            }
        }
        None => {
            // No project_id on the caller — reject since use case deployments
            // are always project-scoped.
            let body = serde_json::json!({
                "error": "API key must be scoped to a project to access use case deployments"
            });
            return Err((StatusCode::FORBIDDEN, axum::Json(body)).into_response());
        }
    }

    // 4. Verify the route is active (case-insensitive)
    if !route.status.eq_ignore_ascii_case("active") {
        let body = serde_json::json!({
            "error": format!("Deployment is not active (status: {})", route.status)
        });
        return Err((StatusCode::SERVICE_UNAVAILABLE, axum::Json(body)).into_response());
    }

    // 5. Sanitize the rest path to prevent path traversal.
    // Check both decoded and percent-encoded variants.
    let decoded_rest = percent_decode(&rest);
    if decoded_rest.contains("..") || rest.contains("..") {
        let body = serde_json::json!({
            "error": "Invalid path: path traversal is not allowed"
        });
        return Err((StatusCode::BAD_REQUEST, axum::Json(body)).into_response());
    }

    // 6. Construct target URL (preserve query string)
    let mut target_url = format!(
        "{}/usecases/{}/api/{}",
        route.ingress_url.trim_end_matches('/'),
        deployment_id,
        rest.trim_start_matches('/')
    );
    if let Some(ref qs) = query_string {
        target_url.push('?');
        target_url.push_str(qs);
    }

    // 7. Build the proxied request
    let mut proxy_request = app_state
        .http_client
        .request(method, &target_url)
        .timeout(std::time::Duration::from_secs(120));

    // Forward headers, excluding hop-by-hop headers, Host, Authorization, and Content-Length
    for (name, value) in headers.iter() {
        let name_str = name.as_str().to_lowercase();
        if should_forward_header(&name_str) {
            proxy_request = proxy_request.header(name.clone(), value.clone());
        }
    }

    // Forward the body
    let body_bytes = match axum::body::to_bytes(body, 100 * 1024 * 1024).await {
        Ok(bytes) => bytes,
        Err(e) => {
            tracing::error!(
                deployment_id = %deployment_id,
                "Failed to read request body: {e}"
            );
            let body = serde_json::json!({
                "error": "Failed to read request body"
            });
            return Err((StatusCode::INTERNAL_SERVER_ERROR, axum::Json(body)).into_response());
        }
    };

    if !body_bytes.is_empty() {
        proxy_request = proxy_request.body(body_bytes);
    }

    // 8. Send the proxied request
    let upstream_response = match proxy_request.send().await {
        Ok(resp) => resp,
        Err(e) => {
            tracing::error!(
                deployment_id = %deployment_id,
                target_url = %target_url,
                "Upstream request failed: {e}"
            );
            let body = serde_json::json!({
                "error": "Failed to reach upstream service"
            });
            return Err((StatusCode::BAD_GATEWAY, axum::Json(body)).into_response());
        }
    };

    // 9. Build the response to return to the caller
    let status = upstream_response.status();
    let upstream_headers = upstream_response.headers().clone();

    let response_bytes = match upstream_response.bytes().await {
        Ok(bytes) => bytes,
        Err(e) => {
            tracing::error!(
                deployment_id = %deployment_id,
                "Failed to read upstream response body: {e}"
            );
            let body = serde_json::json!({
                "error": "Failed to read upstream response"
            });
            return Err((StatusCode::BAD_GATEWAY, axum::Json(body)).into_response());
        }
    };

    let mut response = Response::builder().status(status);

    // Forward response headers, excluding hop-by-hop headers and content-length
    // (let axum set the correct content-length from the actual body)
    for (name, value) in upstream_headers.iter() {
        let name_str = name.as_str().to_lowercase();
        if should_forward_header(&name_str) {
            response = response.header(name.clone(), value.clone());
        }
    }

    response.body(Body::from(response_bytes)).map_err(|e| {
        tracing::error!("Failed to build proxy response: {e}");
        let body = serde_json::json!({
            "error": "Failed to construct proxy response"
        });
        (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(body)).into_response()
    })
}

/// Validate the API key from the Authorization header and return the caller's project_id.
///
/// If authentication is disabled, returns `Ok(None)`.
/// If authentication is enabled, validates the key and extracts the `api_key_project_id`
/// from auth metadata.
fn validate_api_key_for_proxy(
    app_state: &AppStateData,
    headers: &HeaderMap,
) -> Result<Option<String>, Box<Response<Body>>> {
    let auth = match &app_state.authentication_info {
        AuthenticationInfo::Enabled(auth) => auth,
        AuthenticationInfo::Disabled => return Ok(None),
    };

    let key = extract_bearer_token(headers)?;

    // Validate the API key exists
    auth.validate_api_key(&key).map_err(|_| {
        let body = serde_json::json!({
            "error": {
                "message": "Invalid API key",
                "type": "invalid_request_error",
                "code": 401
            }
        });
        Box::new((StatusCode::UNAUTHORIZED, axum::Json(body)).into_response())
    })?;

    // Extract auth metadata for project_id
    let project_id = auth
        .get_auth_metadata(&key)
        .and_then(|meta| meta.api_key_project_id);

    Ok(project_id)
}

/// Extract the Bearer token from the Authorization header.
fn extract_bearer_token(headers: &HeaderMap) -> Result<String, Box<Response<Body>>> {
    let auth_header = headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string());

    match auth_header {
        Some(header_value) => {
            let trimmed = header_value.trim();
            Ok(trimmed
                .strip_prefix("Bearer ")
                .unwrap_or(trimmed)
                .to_string())
        }
        None => {
            let body = serde_json::json!({
                "error": {
                    "message": "Missing authorization header",
                    "type": "invalid_request_error",
                    "code": 401
                }
            });
            Err(Box::new(
                (StatusCode::UNAUTHORIZED, axum::Json(body)).into_response(),
            ))
        }
    }
}

/// Determine whether a header should be forwarded through the proxy.
///
/// Excludes hop-by-hop headers, Host, Authorization (don't leak gateway
/// credentials to upstream), and Content-Length (let the HTTP client set it).
fn should_forward_header(name: &str) -> bool {
    !matches!(
        name,
        "host"
            | "connection"
            | "keep-alive"
            | "proxy-authenticate"
            | "proxy-authorization"
            | "te"
            | "trailers"
            | "transfer-encoding"
            | "upgrade"
            | "authorization"
            | "content-length"
    )
}

/// Decode percent-encoded characters in a URL path segment.
fn percent_decode(input: &str) -> String {
    let mut result = Vec::with_capacity(input.len());
    let bytes = input.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'%' && i + 2 < bytes.len() {
            if let (Some(hi), Some(lo)) = (
                hex_val(bytes[i + 1]),
                hex_val(bytes[i + 2]),
            ) {
                result.push(hi << 4 | lo);
                i += 3;
                continue;
            }
        }
        result.push(bytes[i]);
        i += 1;
    }
    String::from_utf8_lossy(&result).into_owned()
}

fn hex_val(b: u8) -> Option<u8> {
    match b {
        b'0'..=b'9' => Some(b - b'0'),
        b'a'..=b'f' => Some(b - b'a' + 10),
        b'A'..=b'F' => Some(b - b'A' + 10),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_should_forward_header() {
        // Headers that should be forwarded
        assert!(should_forward_header("content-type"));
        assert!(should_forward_header("accept"));
        assert!(should_forward_header("x-custom-header"));

        // Headers that should NOT be forwarded
        assert!(!should_forward_header("host"));
        assert!(!should_forward_header("connection"));
        assert!(!should_forward_header("keep-alive"));
        assert!(!should_forward_header("proxy-authenticate"));
        assert!(!should_forward_header("proxy-authorization"));
        assert!(!should_forward_header("te"));
        assert!(!should_forward_header("trailers"));
        assert!(!should_forward_header("transfer-encoding"));
        assert!(!should_forward_header("upgrade"));
        assert!(!should_forward_header("authorization"));
        assert!(!should_forward_header("content-length"));
    }

    #[test]
    fn test_extract_bearer_token_with_bearer_prefix() {
        let mut headers = HeaderMap::new();
        headers.insert(
            "authorization",
            HeaderValue::from_static("Bearer test-token-123"),
        );
        let result = extract_bearer_token(&headers);
        assert!(result.is_ok());
        assert_eq!(result.ok(), Some("test-token-123".to_string()));
    }

    #[test]
    fn test_extract_bearer_token_without_prefix() {
        let mut headers = HeaderMap::new();
        headers.insert("authorization", HeaderValue::from_static("raw-token-456"));
        let result = extract_bearer_token(&headers);
        assert!(result.is_ok());
        assert_eq!(result.ok(), Some("raw-token-456".to_string()));
    }

    #[test]
    fn test_extract_bearer_token_missing_header() {
        let headers = HeaderMap::new();
        let result = extract_bearer_token(&headers);
        assert!(result.is_err());
    }

    #[test]
    fn test_percent_decode() {
        assert_eq!(percent_decode("hello"), "hello");
        assert_eq!(percent_decode("%2e%2e"), "..");
        assert_eq!(percent_decode("%2E%2E"), "..");
        assert_eq!(percent_decode("foo%2fbar"), "foo/bar");
        assert_eq!(percent_decode("no%xxdecode"), "no%xxdecode");
    }

    #[test]
    fn test_path_traversal_detection() {
        // Direct ..
        let rest = "../etc/passwd";
        let decoded = percent_decode(rest);
        assert!(decoded.contains("..") || rest.contains(".."));

        // Percent-encoded ..
        let rest = "%2e%2e/etc/passwd";
        let decoded = percent_decode(rest);
        assert!(decoded.contains(".."));

        // Safe path
        let rest = "v1/chat/completions";
        let decoded = percent_decode(rest);
        assert!(!decoded.contains("..") && !rest.contains(".."));
    }
}
