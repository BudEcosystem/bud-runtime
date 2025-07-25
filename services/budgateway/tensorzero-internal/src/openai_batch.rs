use crate::error::{Error, ErrorDetails};
use crate::inference::types::batch::BatchStatus;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// OpenAI Batch API status enum
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum OpenAIBatchStatus {
    Validating,
    Failed,
    InProgress,
    Finalizing,
    Completed,
    Expired,
    Cancelling,
    Cancelled,
}

/// Request to create a new batch
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct OpenAIBatchCreateRequest {
    pub input_file_id: String,
    pub endpoint: String,
    pub completion_window: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<HashMap<String, String>>,
}

/// Parameters for listing batches
#[derive(Debug, Clone, Deserialize)]
pub struct ListBatchesParams {
    #[serde(default)]
    pub after: Option<String>,
    #[serde(default = "default_limit")]
    pub limit: i32,
}

fn default_limit() -> i32 {
    20
}

/// Response for listing batches
#[derive(Debug, Serialize, Deserialize)]
pub struct ListBatchesResponse {
    pub object: String,
    pub data: Vec<OpenAIBatchObject>,
    pub first_id: Option<String>,
    pub last_id: Option<String>,
    pub has_more: bool,
}

/// OpenAI Batch object
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OpenAIBatchObject {
    pub id: String,
    pub object: String,
    pub endpoint: String,
    pub errors: Option<BatchErrors>,
    pub input_file_id: String,
    pub completion_window: String,
    pub status: OpenAIBatchStatus,
    pub output_file_id: Option<String>,
    pub error_file_id: Option<String>,
    pub created_at: i64,
    pub in_progress_at: Option<i64>,
    pub expires_at: Option<i64>,
    pub finalizing_at: Option<i64>,
    pub completed_at: Option<i64>,
    pub failed_at: Option<i64>,
    pub expired_at: Option<i64>,
    pub cancelling_at: Option<i64>,
    pub cancelled_at: Option<i64>,
    pub request_counts: RequestCounts,
    pub metadata: Option<HashMap<String, String>>,
}

/// Batch error information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BatchErrors {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub object: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<Vec<BatchError>>,
}

/// Individual batch error
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BatchError {
    pub code: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub param: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub line: Option<i32>,
}

/// Request counts for batch processing
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct RequestCounts {
    pub total: i32,
    pub completed: i32,
    pub failed: i32,
}

/// File upload request
#[derive(Debug, Clone, Deserialize)]
pub struct FileUploadRequest {
    pub file: Vec<u8>,
    pub purpose: String,
}

/// File object returned from upload
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OpenAIFileObject {
    pub id: String,
    pub object: String,
    pub bytes: i64,
    pub created_at: i64,
    pub filename: String,
    pub purpose: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub status: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub status_details: Option<String>,
}

/// Convert TensorZero BatchStatus to OpenAI BatchStatus
impl From<BatchStatus> for OpenAIBatchStatus {
    fn from(status: BatchStatus) -> Self {
        match status {
            BatchStatus::Pending => OpenAIBatchStatus::InProgress,
            BatchStatus::Completed => OpenAIBatchStatus::Completed,
            BatchStatus::Failed => OpenAIBatchStatus::Failed,
            BatchStatus::Validating => OpenAIBatchStatus::Validating,
            BatchStatus::InProgress => OpenAIBatchStatus::InProgress,
            BatchStatus::Finalizing => OpenAIBatchStatus::Finalizing,
            BatchStatus::Expired => OpenAIBatchStatus::Expired,
            BatchStatus::Cancelling => OpenAIBatchStatus::Cancelling,
            BatchStatus::Cancelled => OpenAIBatchStatus::Cancelled,
        }
    }
}

/// Convert OpenAI BatchStatus to TensorZero BatchStatus
impl From<OpenAIBatchStatus> for BatchStatus {
    fn from(status: OpenAIBatchStatus) -> Self {
        match status {
            OpenAIBatchStatus::Validating => BatchStatus::Validating,
            OpenAIBatchStatus::Failed => BatchStatus::Failed,
            OpenAIBatchStatus::InProgress => BatchStatus::InProgress,
            OpenAIBatchStatus::Finalizing => BatchStatus::Finalizing,
            OpenAIBatchStatus::Completed => BatchStatus::Completed,
            OpenAIBatchStatus::Expired => BatchStatus::Expired,
            OpenAIBatchStatus::Cancelling => BatchStatus::Cancelling,
            OpenAIBatchStatus::Cancelled => BatchStatus::Cancelled,
        }
    }
}

/// Generate OpenAI-compatible batch ID
pub fn generate_openai_batch_id() -> String {
    format!("batch_{}", uuid::Uuid::now_v7())
}

/// Generate OpenAI-compatible file ID
pub fn generate_openai_file_id() -> String {
    format!("file-{}", uuid::Uuid::now_v7())
}

/// Validate OpenAI batch create request
pub fn validate_batch_create_request(request: &OpenAIBatchCreateRequest) -> Result<(), Error> {
    // Validate endpoint
    match request.endpoint.as_str() {
        "/v1/chat/completions" | "/v1/embeddings" => {
            // Valid endpoints
        }
        _ => {
            return Err(Error::new(ErrorDetails::InvalidRequest {
                message: format!("Unsupported endpoint: {}", request.endpoint),
            }));
        }
    }

    // Validate completion window
    match request.completion_window.as_str() {
        "24h" => {
            // Valid completion window
        }
        _ => {
            return Err(Error::new(ErrorDetails::InvalidRequest {
                message: format!("Invalid completion window: {}", request.completion_window),
            }));
        }
    }

    // Validate input file ID format
    if !request.input_file_id.starts_with("file-") {
        return Err(Error::new(ErrorDetails::InvalidRequest {
            message: "Invalid input file ID format".to_string(),
        }));
    }

    // Validate metadata if present
    if let Some(ref metadata) = request.metadata {
        if metadata.len() > 16 {
            return Err(Error::new(ErrorDetails::InvalidRequest {
                message: "Too many metadata keys (max 16)".to_string(),
            }));
        }

        for (key, value) in metadata {
            if key.len() > 64 {
                return Err(Error::new(ErrorDetails::InvalidRequest {
                    message: format!("Metadata key too long: {key} (max 64 chars)"),
                }));
            }
            if value.len() > 512 {
                return Err(Error::new(ErrorDetails::InvalidRequest {
                    message: format!("Metadata value too long: {value} (max 512 chars)"),
                }));
            }
        }
    }

    Ok(())
}

/// Create OpenAI batch object from TensorZero data
#[expect(clippy::too_many_arguments)]
pub fn create_openai_batch_object(
    _batch_id: String,
    openai_batch_id: String,
    input_file_id: String,
    endpoint: String,
    completion_window: String,
    status: BatchStatus,
    created_at: i64,
    request_counts: RequestCounts,
    metadata: Option<HashMap<String, String>>,
    output_file_id: Option<String>,
    error_file_id: Option<String>,
    in_progress_at: Option<i64>,
    expires_at: Option<i64>,
    finalizing_at: Option<i64>,
    completed_at: Option<i64>,
    failed_at: Option<i64>,
    expired_at: Option<i64>,
    cancelling_at: Option<i64>,
    cancelled_at: Option<i64>,
) -> OpenAIBatchObject {
    OpenAIBatchObject {
        id: openai_batch_id,
        object: "batch".to_string(),
        endpoint,
        errors: None, // TODO: Implement error handling
        input_file_id,
        completion_window,
        status: status.into(),
        output_file_id,
        error_file_id,
        created_at,
        in_progress_at,
        expires_at,
        finalizing_at,
        completed_at,
        failed_at,
        expired_at,
        cancelling_at,
        cancelled_at,
        request_counts,
        metadata,
    }
}

/// Create OpenAI file object from metadata
pub fn create_openai_file_object(
    file_id: String,
    filename: String,
    size: i64,
    created_at: i64,
    purpose: String,
) -> OpenAIFileObject {
    OpenAIFileObject {
        id: file_id,
        object: "file".to_string(),
        bytes: size,
        created_at,
        filename,
        purpose,
        status: Some("processed".to_string()),
        status_details: None,
    }
}

/// Calculate request counts from batch response data
pub fn calculate_request_counts(
    total_requests: usize,
    successful_responses: usize,
    failed_responses: usize,
) -> RequestCounts {
    RequestCounts {
        total: total_requests as i32,
        completed: successful_responses as i32,
        failed: failed_responses as i32,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_status_conversion() {
        assert_eq!(
            OpenAIBatchStatus::from(BatchStatus::Pending),
            OpenAIBatchStatus::InProgress
        );
        assert_eq!(
            BatchStatus::from(OpenAIBatchStatus::Completed),
            BatchStatus::Completed
        );
    }

    #[test]
    fn test_validate_batch_create_request() {
        let valid_request = OpenAIBatchCreateRequest {
            input_file_id: "file-123".to_string(),
            endpoint: "/v1/chat/completions".to_string(),
            completion_window: "24h".to_string(),
            metadata: None,
        };
        assert!(validate_batch_create_request(&valid_request).is_ok());

        let invalid_endpoint = OpenAIBatchCreateRequest {
            input_file_id: "file-123".to_string(),
            endpoint: "/v1/unsupported".to_string(),
            completion_window: "24h".to_string(),
            metadata: None,
        };
        assert!(validate_batch_create_request(&invalid_endpoint).is_err());
    }

    #[test]
    fn test_generate_ids() {
        let batch_id = generate_openai_batch_id();
        assert!(batch_id.starts_with("batch_"));

        let file_id = generate_openai_file_id();
        assert!(file_id.starts_with("file-"));
    }

    #[test]
    fn test_request_counts() {
        let counts = calculate_request_counts(100, 95, 5);
        assert_eq!(counts.total, 100);
        assert_eq!(counts.completed, 95);
        assert_eq!(counts.failed, 5);
    }

    #[test]
    fn test_batch_id_parsing() {
        // Test extracting UUID from batch ID with prefix
        let batch_id_with_prefix = "batch_0197c6ed-31bd-7a50-8eeb-e29e06078ebf";
        let uuid_str = &batch_id_with_prefix[6..];
        assert_eq!(uuid_str, "0197c6ed-31bd-7a50-8eeb-e29e06078ebf");

        // Verify it's a valid UUID
        let parsed_uuid = uuid::Uuid::parse_str(uuid_str);
        assert!(parsed_uuid.is_ok());
    }

    #[test]
    fn test_batch_object_serialization() {
        let batch_obj = OpenAIBatchObject {
            id: "batch_123".to_string(),
            object: "batch".to_string(),
            endpoint: "/v1/chat/completions".to_string(),
            errors: None,
            input_file_id: "file-456".to_string(),
            completion_window: "24h".to_string(),
            status: OpenAIBatchStatus::Validating,
            output_file_id: None,
            error_file_id: None,
            created_at: 1751388425,
            in_progress_at: None,
            expires_at: Some(1751474825),
            finalizing_at: None,
            completed_at: None,
            failed_at: None,
            expired_at: None,
            cancelling_at: None,
            cancelled_at: None,
            request_counts: RequestCounts {
                total: 0,
                completed: 0,
                failed: 0,
            },
            metadata: None,
        };

        let json = serde_json::to_value(&batch_obj).unwrap();

        // Verify all fields are present (even null ones)
        assert!(json.get("id").is_some());
        assert!(json.get("object").is_some());
        assert!(json.get("endpoint").is_some());
        assert!(json.get("errors").is_some());
        assert!(json.get("input_file_id").is_some());
        assert!(json.get("completion_window").is_some());
        assert!(json.get("status").is_some());
        assert!(json.get("output_file_id").is_some());
        assert!(json.get("error_file_id").is_some());
        assert!(json.get("created_at").is_some());
        assert!(json.get("in_progress_at").is_some());
        assert!(json.get("expires_at").is_some());
        assert!(json.get("finalizing_at").is_some());
        assert!(json.get("completed_at").is_some());
        assert!(json.get("failed_at").is_some());
        assert!(json.get("expired_at").is_some());
        assert!(json.get("cancelling_at").is_some());
        assert!(json.get("cancelled_at").is_some());
        assert!(json.get("request_counts").is_some());
        assert!(json.get("metadata").is_some());

        // Verify null values are serialized as null
        assert_eq!(json.get("errors").unwrap(), &serde_json::Value::Null);
        assert_eq!(
            json.get("output_file_id").unwrap(),
            &serde_json::Value::Null
        );
    }
}
