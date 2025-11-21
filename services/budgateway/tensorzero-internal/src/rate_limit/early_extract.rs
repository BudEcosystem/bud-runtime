use axum::{body::Body, extract::Request, middleware::Next, response::Response};

/// Early model extraction layer
///
/// This layer runs BEFORE rate limiting and extracts the model name from the request body,
/// storing it in request extensions so the rate limiter can access it without re-parsing.
pub async fn early_model_extraction(mut request: Request, next: Next) -> Response {
    // Fast path: Check for X-Model-Name header first
    if let Some(model_header) = request.headers().get("x-model-name") {
        if let Ok(model_str) = model_header.to_str() {
            let model = model_str.to_string();
            tracing::debug!(
                "Fast path: extracted model '{}' from X-Model-Name header",
                model
            );
            request.extensions_mut().insert(ExtractedModel(model));
            return next.run(request).await;
        }
    }

    // Special handling for /v1/models endpoint (GET request, no model in body)
    // Use a static endpoint identifier for rate limiting
    if request.uri().path() == "/v1/models" {
        tracing::debug!("Setting static endpoint ID for /v1/models");
        request
            .extensions_mut()
            .insert(ExtractedModel("models_list".to_string()));
        return next.run(request).await;
    }

    // Only process POST requests to OpenAI endpoints
    if request.method() == axum::http::Method::POST {
        let path = request.uri().path();
        tracing::debug!("Early extraction checking path: {}", path);

        // Check if this is an endpoint that needs model extraction
        if path == "/v1/chat/completions"
            || path == "/v1/embeddings"
            || path == "/v1/moderations"
            || path == "/v1/messages"
        {
            tracing::debug!("Early extraction starting for path: {}", path);
            let extract_start = tokio::time::Instant::now();

            // Extract and buffer the body
            let (parts, body) = request.into_parts();
            let body_read_start = tokio::time::Instant::now();
            let bytes = match axum::body::to_bytes(body, 1024 * 1024).await {
                Ok(bytes) => bytes,
                Err(_) => {
                    // If we can't read the body, reconstruct and continue
                    request = Request::from_parts(parts, Body::empty());
                    return next.run(request).await;
                }
            };

            // Try to extract model name from JSON
            if let Ok(json_str) = std::str::from_utf8(&bytes) {
                if let Some(model) = extract_model_from_json(json_str) {
                    // Store the model in request extensions
                    request = Request::from_parts(parts, Body::from(bytes.clone()));
                    request
                        .extensions_mut()
                        .insert(ExtractedModel(model.clone()));
                    let total_time = extract_start.elapsed();
                    let body_time = body_read_start.elapsed();
                    tracing::debug!(
                        "Early extraction SUCCESS: found model '{}' in JSON. Total: {:?}, Body read: {:?}",
                        model, total_time, body_time
                    );
                } else {
                    // No model found, reconstruct request
                    let preview = &json_str[..std::cmp::min(200, json_str.len())];
                    tracing::debug!(
                        "Early extraction FAILED: no model found in JSON preview: {}",
                        preview
                    );
                    request = Request::from_parts(parts, Body::from(bytes));
                }
            } else {
                // Not valid UTF-8, reconstruct request
                tracing::debug!("Early extraction failed: body is not valid UTF-8");
                request = Request::from_parts(parts, Body::from(bytes));
            }
        } else {
            tracing::debug!(
                "Early extraction skipped: path '{}' not in extraction list",
                path
            );
        }
    } else {
        tracing::debug!(
            "Early extraction skipped: method '{}' is not POST",
            request.method()
        );
    }

    next.run(request).await
}

/// Extracted model stored in request extensions
#[derive(Clone)]
pub struct ExtractedModel(pub String);

/// Fast JSON model extraction
fn extract_model_from_json(json_str: &str) -> Option<String> {
    // Look for "model": "value" pattern
    let model_key = "\"model\"";
    let model_pos = json_str.find(model_key)?;

    // Find the colon after "model"
    let after_key = &json_str[model_pos + model_key.len()..];
    let colon_pos = after_key.find(':')?;

    // Skip whitespace after colon
    let after_colon = &after_key[colon_pos + 1..].trim_start();

    // Check if value starts with quote
    if !after_colon.starts_with('"') {
        return None;
    }

    // Find the closing quote
    let value_start = 1;
    let closing_quote = after_colon[value_start..].find('"')?;

    Some(after_colon[value_start..value_start + closing_quote].to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_model_from_json() {
        assert_eq!(
            extract_model_from_json(r#"{"model": "gpt-3.5-turbo", "messages": []}"#),
            Some("gpt-3.5-turbo".to_string())
        );

        assert_eq!(
            extract_model_from_json(r#"{"messages": [], "model": "gpt-4"}"#),
            Some("gpt-4".to_string())
        );

        assert_eq!(
            extract_model_from_json(r#"{"model":"claude-3","temperature":0.7}"#),
            Some("claude-3".to_string())
        );

        assert_eq!(extract_model_from_json(r#"{"no_model": "here"}"#), None);
    }
}
