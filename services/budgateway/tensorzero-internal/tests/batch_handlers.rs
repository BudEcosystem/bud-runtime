#[cfg(test)]
mod tests {

    use std::collections::HashMap;
    use tensorzero_internal::openai_batch::{
        calculate_request_counts, create_openai_file_object, validate_batch_create_request,
        OpenAIBatchCreateRequest,
    };

    #[test]
    fn test_validate_batch_create_request() {
        // Valid request
        let valid_request = OpenAIBatchCreateRequest {
            input_file_id: "file-123".to_string(),
            endpoint: "/v1/chat/completions".to_string(),
            completion_window: "24h".to_string(),
            metadata: None,
        };
        assert!(validate_batch_create_request(&valid_request).is_ok());

        // Invalid endpoint
        let invalid_endpoint = OpenAIBatchCreateRequest {
            input_file_id: "file-123".to_string(),
            endpoint: "/v1/unsupported".to_string(),
            completion_window: "24h".to_string(),
            metadata: None,
        };
        assert!(validate_batch_create_request(&invalid_endpoint).is_err());

        // Invalid completion window
        let invalid_window = OpenAIBatchCreateRequest {
            input_file_id: "file-123".to_string(),
            endpoint: "/v1/chat/completions".to_string(),
            completion_window: "48h".to_string(),
            metadata: None,
        };
        assert!(validate_batch_create_request(&invalid_window).is_err());

        // Invalid file ID format
        let invalid_file_id = OpenAIBatchCreateRequest {
            input_file_id: "invalid-123".to_string(),
            endpoint: "/v1/chat/completions".to_string(),
            completion_window: "24h".to_string(),
            metadata: None,
        };
        assert!(validate_batch_create_request(&invalid_file_id).is_err());

        // Too many metadata keys
        let mut too_many_metadata = HashMap::new();
        for i in 0..20 {
            too_many_metadata.insert(format!("key{i}"), "value".to_string());
        }
        let invalid_metadata = OpenAIBatchCreateRequest {
            input_file_id: "file-123".to_string(),
            endpoint: "/v1/chat/completions".to_string(),
            completion_window: "24h".to_string(),
            metadata: Some(too_many_metadata),
        };
        assert!(validate_batch_create_request(&invalid_metadata).is_err());
    }

    #[test]
    fn test_file_object_creation() {
        let file_obj = create_openai_file_object(
            "file-123".to_string(),
            "test.jsonl".to_string(),
            1024,
            1234567890,
            "batch".to_string(),
        );

        assert_eq!(file_obj.id, "file-123");
        assert_eq!(file_obj.object, "file");
        assert_eq!(file_obj.bytes, 1024);
        assert_eq!(file_obj.created_at, 1234567890);
        assert_eq!(file_obj.filename, "test.jsonl");
        assert_eq!(file_obj.purpose, "batch");
        assert_eq!(file_obj.status, Some("processed".to_string()));
    }

    #[test]
    fn test_batch_status_conversion() {
        use tensorzero_internal::inference::types::batch::BatchStatus;
        use tensorzero_internal::openai_batch::OpenAIBatchStatus;

        // Test TensorZero to OpenAI
        assert_eq!(
            OpenAIBatchStatus::from(BatchStatus::Pending),
            OpenAIBatchStatus::InProgress
        );
        assert_eq!(
            OpenAIBatchStatus::from(BatchStatus::Completed),
            OpenAIBatchStatus::Completed
        );
        assert_eq!(
            OpenAIBatchStatus::from(BatchStatus::Failed),
            OpenAIBatchStatus::Failed
        );

        // Test OpenAI to TensorZero
        assert_eq!(
            BatchStatus::from(OpenAIBatchStatus::InProgress),
            BatchStatus::InProgress
        );
        assert_eq!(
            BatchStatus::from(OpenAIBatchStatus::Completed),
            BatchStatus::Completed
        );
        assert_eq!(
            BatchStatus::from(OpenAIBatchStatus::Failed),
            BatchStatus::Failed
        );
    }

    #[test]
    fn test_request_counts() {
        let counts = calculate_request_counts(100, 95, 5);
        assert_eq!(counts.total, 100);
        assert_eq!(counts.completed, 95);
        assert_eq!(counts.failed, 5);
    }
}
