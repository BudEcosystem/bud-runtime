#[cfg(test)]
mod test_batch_file_api_types {
    use std::collections::HashMap;
    use tensorzero_internal::openai_batch::{
        ListBatchesParams, OpenAIBatchCreateRequest, OpenAIBatchObject, OpenAIBatchStatus,
        OpenAIFileObject,
    };

    #[test]
    fn test_file_object_serialization() {
        let file_object = OpenAIFileObject {
            id: "file-abc123".to_string(),
            object: "file".to_string(),
            bytes: 1024,
            created_at: 1234567890,
            filename: "test.jsonl".to_string(),
            purpose: "batch".to_string(),
            status: None,
            status_details: None,
        };

        let json_value = serde_json::to_value(&file_object).unwrap();
        assert_eq!(json_value["id"], "file-abc123");
        assert_eq!(json_value["object"], "file");
        assert_eq!(json_value["bytes"], 1024);
        assert_eq!(json_value["purpose"], "batch");
    }

    #[test]
    fn test_create_batch_params_deserialization() {
        let json_str = r#"{
            "input_file_id": "file-abc123",
            "endpoint": "/v1/chat/completions",
            "completion_window": "24h",
            "metadata": {
                "customer_id": "customer-123",
                "batch_type": "daily"
            }
        }"#;

        let params: OpenAIBatchCreateRequest = serde_json::from_str(json_str).unwrap();
        assert_eq!(params.input_file_id, "file-abc123");
        assert_eq!(params.endpoint, "/v1/chat/completions");
        assert_eq!(params.completion_window, "24h");
        assert!(params.metadata.is_some());

        let metadata = params.metadata.unwrap();
        assert_eq!(metadata["customer_id"], "customer-123");
        assert_eq!(metadata["batch_type"], "daily");
    }

    #[test]
    fn test_batch_object_serialization() {
        let batch_object = OpenAIBatchObject {
            id: "batch_abc123".to_string(),
            object: "batch".to_string(),
            endpoint: "/v1/chat/completions".to_string(),
            errors: None,
            input_file_id: "file-abc123".to_string(),
            completion_window: "24h".to_string(),
            status: OpenAIBatchStatus::InProgress,
            output_file_id: None,
            error_file_id: None,
            created_at: 1234567890,
            in_progress_at: Some(1234567900),
            expires_at: Some(1234654290),
            finalizing_at: None,
            completed_at: None,
            failed_at: None,
            expired_at: None,
            cancelling_at: None,
            cancelled_at: None,
            request_counts: tensorzero_internal::openai_batch::RequestCounts {
                total: 100,
                completed: 50,
                failed: 0,
            },
            metadata: Some({
                let mut map = HashMap::new();
                map.insert("test".to_string(), "true".to_string());
                map
            }),
        };

        let json_value = serde_json::to_value(&batch_object).unwrap();
        assert_eq!(json_value["id"], "batch_abc123");
        assert_eq!(json_value["status"], "in_progress");
        assert_eq!(json_value["request_counts"]["total"], 100);
        assert_eq!(json_value["request_counts"]["completed"], 50);
    }

    #[test]
    fn test_list_batches_params() {
        let params = ListBatchesParams {
            after: Some("batch_123".to_string()),
            limit: 10,
        };

        assert_eq!(params.after.unwrap(), "batch_123");
        assert_eq!(params.limit, 10);
    }

    #[test]
    fn test_batch_status_serialization() {
        let statuses = [
            OpenAIBatchStatus::Validating,
            OpenAIBatchStatus::Failed,
            OpenAIBatchStatus::InProgress,
            OpenAIBatchStatus::Finalizing,
            OpenAIBatchStatus::Completed,
            OpenAIBatchStatus::Expired,
            OpenAIBatchStatus::Cancelling,
            OpenAIBatchStatus::Cancelled,
        ];

        let expected = [
            "validating",
            "failed",
            "in_progress",
            "finalizing",
            "completed",
            "expired",
            "cancelling",
            "cancelled",
        ];

        for (status, expected_str) in statuses.iter().zip(expected.iter()) {
            let json_value = serde_json::to_value(status).unwrap();
            assert_eq!(json_value, *expected_str);
        }
    }

    #[test]
    fn test_file_upload_validation() {
        // Test that we can parse valid JSONL for batch requests
        let valid_jsonl = r#"{"custom_id": "req-1", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Hello"}]}}
{"custom_id": "req-2", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "World"}]}}"#;

        // Each line should be valid JSON
        for line in valid_jsonl.lines() {
            let parsed: serde_json::Value = serde_json::from_str(line).unwrap();
            assert!(parsed["custom_id"].is_string());
            assert!(parsed["method"].is_string());
            assert!(parsed["url"].is_string());
            assert!(parsed["body"].is_object());
        }
    }
}
