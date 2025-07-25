# Batch API Quick Start Guide

This guide helps you get started with TensorZero's OpenAI-compatible Batch API in 5 minutes.

## Prerequisites

- TensorZero API key
- Python 3.7+ or any HTTP client
- JSONL formatted requests file

## Step 1: Prepare Your Requests

Create a file `requests.jsonl` with your batch requests:

```jsonl
{"custom_id": "req-1", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-4", "messages": [{"role": "user", "content": "What is 2+2?"}]}}
{"custom_id": "req-2", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-4", "messages": [{"role": "user", "content": "What is the capital of France?"}]}}
{"custom_id": "req-3", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-4", "messages": [{"role": "user", "content": "Explain quantum computing in simple terms"}]}}
```

## Step 2: Upload Your File

```bash
# Upload the file
curl -X POST https://api.tensorzero.com/v1/files \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@requests.jsonl" \
  -F "purpose=batch"

# Response
{
  "id": "file-abc123",
  "object": "file",
  "bytes": 512,
  "created_at": 1735775425,
  "filename": "requests.jsonl",
  "purpose": "batch"
}
```

## Step 3: Create a Batch

```bash
# Create batch using the file ID from step 2
curl -X POST https://api.tensorzero.com/v1/batches \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input_file_id": "file-abc123",
    "endpoint": "/v1/chat/completions",
    "completion_window": "24h"
  }'

# Response
{
  "id": "batch_xyz789",
  "object": "batch",
  "status": "validating",
  "created_at": 1735775425,
  ...
}
```

## Step 4: Check Batch Status

```bash
# Poll for completion
curl https://api.tensorzero.com/v1/batches/batch_xyz789 \
  -H "Authorization: Bearer YOUR_API_KEY"

# Response when completed
{
  "id": "batch_xyz789",
  "status": "completed",
  "output_file_id": "file-output123",
  "request_counts": {
    "total": 3,
    "completed": 3,
    "failed": 0
  },
  ...
}
```

## Step 5: Download Results

```bash
# Download the output file
curl https://api.tensorzero.com/v1/files/file-output123/content \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -o results.jsonl

# View results
cat results.jsonl
```

Output format:
```jsonl
{"id": "batch_req_1", "custom_id": "req-1", "response": {"status_code": 200, "body": {"choices": [{"message": {"content": "2+2 equals 4"}}]}}}
{"id": "batch_req_2", "custom_id": "req-2", "response": {"status_code": 200, "body": {"choices": [{"message": {"content": "The capital of France is Paris"}}]}}}
{"id": "batch_req_3", "custom_id": "req-3", "response": {"status_code": 200, "body": {"choices": [{"message": {"content": "Quantum computing uses quantum bits..."}}]}}}
```

## Python Example

```python
import requests
import json
import time

API_KEY = "YOUR_API_KEY"
BASE_URL = "https://api.tensorzero.com/v1"

# 1. Upload file
with open("requests.jsonl", "rb") as f:
    upload_response = requests.post(
        f"{BASE_URL}/files",
        headers={"Authorization": f"Bearer {API_KEY}"},
        files={"file": f},
        data={"purpose": "batch"}
    )
file_id = upload_response.json()["id"]
print(f"File uploaded: {file_id}")

# 2. Create batch
batch_response = requests.post(
    f"{BASE_URL}/batches",
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    },
    json={
        "input_file_id": file_id,
        "endpoint": "/v1/chat/completions",
        "completion_window": "24h"
    }
)
batch_id = batch_response.json()["id"]
print(f"Batch created: {batch_id}")

# 3. Poll for completion
while True:
    batch = requests.get(
        f"{BASE_URL}/batches/{batch_id}",
        headers={"Authorization": f"Bearer {API_KEY}"}
    ).json()
    
    print(f"Status: {batch['status']}")
    
    if batch["status"] == "completed":
        output_file_id = batch["output_file_id"]
        break
    elif batch["status"] == "failed":
        print("Batch failed!")
        exit(1)
    
    time.sleep(30)  # Wait 30 seconds

# 4. Download and process results
results = requests.get(
    f"{BASE_URL}/files/{output_file_id}/content",
    headers={"Authorization": f"Bearer {API_KEY}"}
)

for line in results.text.strip().split("\n"):
    result = json.loads(line)
    custom_id = result["custom_id"]
    response_content = result["response"]["body"]["choices"][0]["message"]["content"]
    print(f"{custom_id}: {response_content}")
```

## Common Use Cases

### 1. Bulk Content Generation
```jsonl
{"custom_id": "article-1", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-4", "messages": [{"role": "system", "content": "You are a helpful blog writer"}, {"role": "user", "content": "Write a 200-word article about AI in healthcare"}]}}
{"custom_id": "article-2", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-4", "messages": [{"role": "system", "content": "You are a helpful blog writer"}, {"role": "user", "content": "Write a 200-word article about sustainable energy"}]}}
```

### 2. Bulk Data Analysis
```jsonl
{"custom_id": "analysis-1", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-4", "messages": [{"role": "user", "content": "Analyze this customer review and extract sentiment: 'Great product, fast shipping!'"}]}}
{"custom_id": "analysis-2", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-4", "messages": [{"role": "user", "content": "Analyze this customer review and extract sentiment: 'Disappointed with the quality'"}]}}
```

### 3. Bulk Embeddings
```jsonl
{"custom_id": "embed-1", "method": "POST", "url": "/v1/embeddings", "body": {"model": "text-embedding-ada-002", "input": "Machine learning is a subset of artificial intelligence"}}
{"custom_id": "embed-2", "method": "POST", "url": "/v1/embeddings", "body": {"model": "text-embedding-ada-002", "input": "Deep learning uses neural networks with multiple layers"}}
```

## Tips and Best Practices

1. **Batch Size**: Keep batches under 50,000 requests for optimal processing
2. **Custom IDs**: Use meaningful custom IDs to track your requests
3. **Error Handling**: Always check the `error_file_id` for any failed requests
4. **Polling Frequency**: Poll every 30-60 seconds to avoid rate limits
5. **File Cleanup**: Delete processed files after downloading results

## Error Handling

Check for errors in your batch:

```python
# If batch has errors
if batch["errors"]:
    error_file_id = batch["error_file_id"]
    errors = requests.get(
        f"{BASE_URL}/files/{error_file_id}/content",
        headers={"Authorization": f"Bearer {API_KEY}"}
    )
    print("Errors found:", errors.text)
```

## Rate Limits

- File upload: 100MB per file
- Batch size: 50,000 requests per batch
- Completion window: 24 hours
- Concurrent batches: Based on your account tier

## Next Steps

- Read the [full API documentation](./batch-file-api.md)
- Check out the [OpenAPI specification](./openapi-batch-file.yaml)
- Join our [Discord community](https://discord.gg/tensorzero) for support