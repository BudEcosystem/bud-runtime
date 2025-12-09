use std::collections::HashMap;

use axum::http::{HeaderMap, HeaderValue, Response};
use axum::body::Body;
use crate::error::{Error, ErrorDetails};

pub mod batch_inference;
pub mod capability;
pub mod datasets;
pub mod dynamic_evaluation_run;
pub mod fallback;
pub mod feedback;
pub mod inference;
pub mod model_resolution;
pub mod object_storage;
pub mod openai_compatible;
pub mod status;

/// Add auth metadata headers from request to response for analytics tracking.
/// This copies relevant auth headers (evaluation_id, api_key_id, user_id, project_id, endpoint_id)
/// from the request headers to the response headers so the analytics middleware can capture them.
pub fn add_auth_metadata_to_response(response: &mut Response<Body>, request_headers: &HeaderMap) {
    // List of auth metadata headers to copy from request to response
    let auth_headers = [
        "x-tensorzero-evaluation-id",
        "x-tensorzero-api-key-id",
        "x-tensorzero-user-id",
        "x-tensorzero-project-id",
        "x-tensorzero-endpoint-id",
        "x-tensorzero-api-key-project-id",
    ];

    for header_name in &auth_headers {
        if let Some(header_value) = request_headers.get(*header_name) {
            if let Ok(cloned_value) = HeaderValue::from_bytes(header_value.as_bytes()) {
                response.headers_mut().insert(*header_name, cloned_value);
            }
        }
    }
}

pub fn validate_tags(tags: &HashMap<String, String>, internal: bool) -> Result<(), Error> {
    if internal {
        return Ok(());
    }
    for tag_name in tags.keys() {
        if tag_name.starts_with("tensorzero::") {
            return Err(Error::new(ErrorDetails::InvalidRequest {
                message: format!("Tag name cannot start with 'tensorzero::': {tag_name}"),
            }));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_tags() {
        let mut tags = HashMap::new();
        assert!(validate_tags(&tags, false).is_ok());
        tags.insert("tensorzero::test".to_string(), "test".to_string());
        assert!(validate_tags(&tags, false).is_err());
        // once we're in internal mode, we can have tags that start with "tensorzero::"
        assert!(validate_tags(&tags, true).is_ok());
    }
}
