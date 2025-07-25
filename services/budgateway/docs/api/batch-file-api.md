# Batch and File API Reference

TensorZero provides OpenAI-compatible batch and file APIs for processing large-scale inference requests asynchronously. These APIs allow you to upload files containing multiple requests and process them in batches for better efficiency and cost optimization.

## Overview

The Batch API enables:
- **Asynchronous Processing**: Submit large batches of requests for processing
- **Cost Efficiency**: Potentially lower costs for large-scale operations
- **Better Throughput**: Process thousands of requests without hitting rate limits
- **Reliability**: Automatic retries and error handling for failed requests

## Authentication

All batch and file API endpoints require authentication when gateway authentication is enabled:

```bash
Authorization: Bearer YOUR_API_KEY
```

## File API Endpoints

### Upload File

Upload a file containing batch requests in JSONL format.

**Endpoint**: `POST /v1/files`

**Request**:
```bash
curl -X POST https://api.tensorzero.com/v1/files \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@batch_requests.jsonl" \
  -F "purpose=batch"
```

**Parameters**:
- `file` (required): The JSONL file to upload (max 100MB)
- `purpose` (required): Must be "batch" for batch processing

**Response**:
```json
{
  "id": "file-abc123def456",
  "object": "file",
  "bytes": 2048,
  "created_at": 1735775425,
  "filename": "batch_requests.jsonl",
  "purpose": "batch",
  "status": "processed",
  "status_details": null
}
```

### Retrieve File

Get metadata about an uploaded file.

**Endpoint**: `GET /v1/files/{file_id}`

**Request**:
```bash
curl https://api.tensorzero.com/v1/files/file-abc123def456 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response**:
```json
{
  "id": "file-abc123def456",
  "object": "file",
  "bytes": 2048,
  "created_at": 1735775425,
  "filename": "batch_requests.jsonl",
  "purpose": "batch",
  "status": "processed",
  "status_details": null
}
```

### Retrieve File Content

Download the content of a file.

**Endpoint**: `GET /v1/files/{file_id}/content`

**Request**:
```bash
curl https://api.tensorzero.com/v1/files/file-abc123def456/content \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -o output.jsonl
```

**Response**: The raw file content (JSONL format)

### Delete File

Delete an uploaded file.

**Endpoint**: `DELETE /v1/files/{file_id}`

**Request**:
```bash
curl -X DELETE https://api.tensorzero.com/v1/files/file-abc123def456 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response**:
```json
{
  "id": "file-abc123def456",
  "object": "file",
  "deleted": true
}
```

## Batch API Endpoints

### Create Batch

Create a new batch for processing.

**Endpoint**: `POST /v1/batches`

**Request**:
```bash
curl -X POST https://api.tensorzero.com/v1/batches \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input_file_id": "file-abc123def456",
    "endpoint": "/v1/chat/completions",
    "completion_window": "24h",
    "metadata": {
      "project": "customer-support",
      "version": "v1"
    }
  }'
```

**Parameters**:
- `input_file_id` (required): ID of the uploaded JSONL file
- `endpoint` (required): The endpoint to use (`/v1/chat/completions` or `/v1/embeddings`)
- `completion_window` (required): Must be "24h"
- `metadata` (optional): Key-value pairs for tracking (max 16 keys)

**Response**:
```json
{
  "id": "batch_0197c6ed-31bd-7a50-8eeb-e29e06078ebf",
  "object": "batch",
  "endpoint": "/v1/chat/completions",
  "errors": null,
  "input_file_id": "file-abc123def456",
  "completion_window": "24h",
  "status": "validating",
  "output_file_id": null,
  "error_file_id": null,
  "created_at": 1735775425,
  "in_progress_at": null,
  "expires_at": 1735861825,
  "finalizing_at": null,
  "completed_at": null,
  "failed_at": null,
  "expired_at": null,
  "cancelling_at": null,
  "cancelled_at": null,
  "request_counts": {
    "total": 0,
    "completed": 0,
    "failed": 0
  },
  "metadata": {
    "project": "customer-support",
    "version": "v1"
  }
}
```

### Retrieve Batch

Get the status and details of a batch.

**Endpoint**: `GET /v1/batches/{batch_id}`

**Request**:
```bash
curl https://api.tensorzero.com/v1/batches/batch_0197c6ed-31bd-7a50-8eeb-e29e06078ebf \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response**:
```json
{
  "id": "batch_0197c6ed-31bd-7a50-8eeb-e29e06078ebf",
  "object": "batch",
  "endpoint": "/v1/chat/completions",
  "errors": null,
  "input_file_id": "file-abc123def456",
  "completion_window": "24h",
  "status": "completed",
  "output_file_id": "file-xyz789ghi012",
  "error_file_id": null,
  "created_at": 1735775425,
  "in_progress_at": 1735775430,
  "expires_at": 1735861825,
  "finalizing_at": 1735776000,
  "completed_at": 1735776100,
  "failed_at": null,
  "expired_at": null,
  "cancelling_at": null,
  "cancelled_at": null,
  "request_counts": {
    "total": 100,
    "completed": 98,
    "failed": 2
  },
  "metadata": {
    "project": "customer-support",
    "version": "v1"
  }
}
```

### List Batches

List all batches with optional pagination.

**Endpoint**: `GET /v1/batches`

**Request**:
```bash
curl "https://api.tensorzero.com/v1/batches?limit=10&after=batch_xyz" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Parameters**:
- `limit` (optional): Number of batches to return (default: 20, max: 100)
- `after` (optional): Cursor for pagination

**Response**:
```json
{
  "object": "list",
  "data": [
    {
      "id": "batch_0197c6ed-31bd-7a50-8eeb-e29e06078ebf",
      "object": "batch",
      "endpoint": "/v1/chat/completions",
      "status": "completed",
      // ... full batch object
    }
  ],
  "first_id": "batch_0197c6ed-31bd-7a50-8eeb-e29e06078ebf",
  "last_id": "batch_0197c6ed-31bd-7a50-8eeb-e29e06078ebf",
  "has_more": false
}
```

### Cancel Batch

Cancel a batch that is in progress.

**Endpoint**: `POST /v1/batches/{batch_id}/cancel`

**Request**:
```bash
curl -X POST https://api.tensorzero.com/v1/batches/batch_0197c6ed-31bd-7a50-8eeb-e29e06078ebf/cancel \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response**: Returns the batch object with `status: "cancelling"` or `"cancelled"`

## Batch File Format

### Input File Format (JSONL)

Each line in the input file must be a valid JSON object with the following structure:

```jsonl
{"custom_id": "request-1", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-4", "messages": [{"role": "user", "content": "Hello!"}]}}
{"custom_id": "request-2", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-4", "messages": [{"role": "user", "content": "How are you?"}]}}
```

**Fields**:
- `custom_id` (required): Unique identifier for tracking the request
- `method` (required): Must be "POST"
- `url` (required): Must match the batch endpoint
- `body` (required): The request body for the endpoint

### Output File Format (JSONL)

The output file contains one response per line:

```jsonl
{"id": "batch_req_123", "custom_id": "request-1", "response": {"status_code": 200, "request_id": "req_456", "body": {"id": "chatcmpl-123", "object": "chat.completion", "created": 1735775425, "model": "gpt-4", "choices": [...]}}, "error": null}
{"id": "batch_req_124", "custom_id": "request-2", "response": {"status_code": 200, "request_id": "req_457", "body": {"id": "chatcmpl-124", "object": "chat.completion", "created": 1735775426, "model": "gpt-4", "choices": [...]}}, "error": null}
```

## Batch Status Values

- `validating`: Initial validation of the batch request
- `failed`: The batch failed during processing
- `in_progress`: The batch is currently being processed
- `finalizing`: The batch is being finalized
- `completed`: The batch completed successfully
- `expired`: The batch expired before completion
- `cancelling`: The batch is being cancelled
- `cancelled`: The batch was cancelled

## Error Handling

### File Upload Errors

```json
{
  "error": {
    "type": "invalid_request_error",
    "message": "File size exceeds maximum allowed size of 100MB"
  }
}
```

### Batch Creation Errors

```json
{
  "error": {
    "type": "invalid_request_error",
    "message": "Invalid input file ID format"
  }
}
```

### Common Error Types

- `invalid_request_error`: Invalid parameters or request format
- `authentication_error`: Invalid or missing API key
- `not_found_error`: File or batch not found
- `server_error`: Internal server error

## Best Practices

1. **File Size**: Keep files under 100MB for optimal processing
2. **Request Format**: Validate JSONL format before uploading
3. **Polling**: Poll batch status every 30-60 seconds
4. **Error Handling**: Always check for partial failures in completed batches
5. **Metadata**: Use metadata to track and organize batches
6. **Cleanup**: Delete processed files to free up storage

## Example Workflow

```python
import requests
import json
import time

# 1. Prepare batch requests
requests_data = [
    {
        "custom_id": f"request-{i}",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": f"Question {i}"}]
        }
    }
    for i in range(100)
]

# 2. Write to JSONL file
with open("batch_requests.jsonl", "w") as f:
    for req in requests_data:
        f.write(json.dumps(req) + "\n")

# 3. Upload file
with open("batch_requests.jsonl", "rb") as f:
    response = requests.post(
        "https://api.tensorzero.com/v1/files",
        headers={"Authorization": "Bearer YOUR_API_KEY"},
        files={"file": f},
        data={"purpose": "batch"}
    )
file_id = response.json()["id"]

# 4. Create batch
batch_response = requests.post(
    "https://api.tensorzero.com/v1/batches",
    headers={
        "Authorization": "Bearer YOUR_API_KEY",
        "Content-Type": "application/json"
    },
    json={
        "input_file_id": file_id,
        "endpoint": "/v1/chat/completions",
        "completion_window": "24h"
    }
)
batch_id = batch_response.json()["id"]

# 5. Poll for completion
while True:
    batch = requests.get(
        f"https://api.tensorzero.com/v1/batches/{batch_id}",
        headers={"Authorization": "Bearer YOUR_API_KEY"}
    ).json()
    
    if batch["status"] == "completed":
        break
    elif batch["status"] == "failed":
        raise Exception("Batch processing failed")
    
    time.sleep(60)  # Wait 1 minute before polling again

# 6. Download results
output_file_id = batch["output_file_id"]
results = requests.get(
    f"https://api.tensorzero.com/v1/files/{output_file_id}/content",
    headers={"Authorization": "Bearer YOUR_API_KEY"}
)

# 7. Process results
for line in results.text.strip().split("\n"):
    result = json.loads(line)
    custom_id = result["custom_id"]
    response = result["response"]["body"]
    # Process each response...
```

## Rate Limits and Quotas

- **File Size**: Maximum 100MB per file
- **Batch Size**: Maximum 50,000 requests per batch
- **Metadata**: Maximum 16 key-value pairs
- **Completion Window**: Currently only "24h" is supported
- **Concurrent Batches**: Depends on your account limits

## Migration from OpenAI

The TensorZero Batch API is fully compatible with OpenAI's Batch API. To migrate:

1. Change the base URL from `https://api.openai.com` to your TensorZero endpoint
2. Use your TensorZero API key instead of OpenAI's
3. All other parameters and formats remain the same

## Support

For questions or issues with the Batch API:
- Check the [TensorZero documentation](https://docs.tensorzero.com)
- Contact support at support@tensorzero.com
- Join our [Discord community](https://discord.gg/tensorzero)