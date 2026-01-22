# Embeddings API

The `/v1/embeddings` endpoint generates vector embeddings for input text(s). This endpoint is compatible with OpenAI's embeddings API format.

## Endpoint

```
POST /v1/embeddings
```

## Authentication

This endpoint requires API key authentication.

**Required Header:**
```
Authorization: Bearer <YOUR_API_KEY>
```

## Request Format

### Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes | Bearer token for API authentication |
| `Content-Type` | Yes | Must be `application/json` |

### Request Body

```json
{
  "model": "string",
  "input": "string" | ["array", "of", "strings"],
  "encoding_format": "float",
  "dimensions": 1536,
  "modality": "text",
  "priority": "high",
  "include_input": true,
  "chunking": {
    "enabled": true,
    "strategy": "token",
    "chunk_size": 512,
    "chunk_overlap": 50,
    "tokenizer": "cl100k_base",
    "return_chunk_text": true
  },
  "tensorzero::cache_options": {
    "enabled": "on" | "off",
    "max_age_s": 3600
  },
  "provider_specific_param": "value"
}
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | Yes | The model identifier to use for embeddings. Can be a simple model name (e.g., `text-embedding-3-small`) or prefixed with `tensorzero::` (e.g., `tensorzero::my-embedding-model::`) |
| `input` | string \| string[] | Yes | The text(s) to generate embeddings for. Can be a single string or an array of strings for batch processing |
| `encoding_format` | string | No | The format of the embeddings. Currently only `"float"` is supported (default) |
| `dimensions` | integer | No | Matryoshka dimensions to request from providers that support it |
| `modality` | string | No | Input modality (e.g., `"text"`, `"image"`, `"audio"`) for providers that support multimodal embeddings |
| `priority` | string | No | Priority hint (e.g., `"high"`, `"normal"`, `"low"`) forwarded to the provider |
| `include_input` | boolean | No | Request that the provider include input text in the response |
| `chunking` | object | No | Chunking configuration forwarded to the provider |
| `chunking.enabled` | boolean | No | Enable provider-side chunking |
| `chunking.strategy` | string | No | Chunking strategy (e.g., `"token"`, `"sentence"`, `"recursive"`) |
| `chunking.chunk_size` | integer | No | Chunk size for provider-side chunking |
| `chunking.chunk_overlap` | integer | No | Overlap between chunks |
| `chunking.tokenizer` | string | No | Tokenizer identifier for provider-side chunking |
| `chunking.return_chunk_text` | boolean | No | Request that the provider return chunk text |
| `tensorzero::cache_options` | object | No | Caching configuration for the request |
| `tensorzero::cache_options.enabled` | string | No | Enable (`"on"`) or disable (`"off"`) caching for this request |
| `tensorzero::cache_options.max_age_s` | integer | No | Maximum age in seconds for cached embeddings |
| `provider_specific_param` | any | No | Additional provider-specific parameters are accepted and passed through unchanged |

## Response Format

### Success Response (200 OK)

```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "embedding": [0.0023064255, -0.009327292, ...],
      "index": 0,
      "text": "original input",
      "chunk_text": "chunk text",
      "chunk_info": {
        "start": 0,
        "end": 512
      }
    }
  ],
  "model": "text-embedding-3-small",
  "usage": {
    "prompt_tokens": 8,
    "total_tokens": 8
  },
  "id": "infinity-123456",
  "created": 1700000000,
  "chunking_info": {
    "strategy": "token",
    "chunk_size": 512
  }
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `object` | string | Always `"list"` |
| `data` | array | Array of embedding objects |
| `data[].object` | string | Always `"embedding"` |
| `data[].embedding` | float[] | The embedding vector as an array of floats |
| `data[].index` | integer | The index of this embedding in the batch (0-based) |
| `data[].text` | string | Original input text when the provider returns it |
| `data[].chunk_text` | string | Chunk text when provider-side chunking is enabled |
| `data[].chunk_info` | object | Provider-specific chunk metadata |
| `model` | string | The model used to generate the embeddings |
| `usage` | object | Token usage information |
| `usage.prompt_tokens` | integer | Number of tokens in the input |
| `usage.total_tokens` | integer | Total tokens used (same as prompt_tokens for embeddings) |
| `id` | string | Provider response ID when available |
| `created` | integer | Provider response timestamp (Unix seconds) when available |
| `chunking_info` | object | Provider-specific chunking metadata when available |

Additional provider-specific fields may appear at the top level or within `data[]` entries; the gateway forwards them unchanged when returned by the provider.

## Error Responses

### 400 Bad Request

Invalid request format or parameters.

```json
{
  "error": {
    "message": "Invalid request: missing required field 'model'",
    "type": "invalid_request_error",
    "code": "invalid_request"
  }
}
```

### 401 Unauthorized

Missing or invalid API key.

```json
{
  "error": {
    "message": "Invalid API key",
    "type": "authentication_error",
    "code": "invalid_api_key"
  }
}
```

### 404 Not Found

Model not found or doesn't support embeddings.

```json
{
  "error": {
    "message": "Model 'unknown-model' not found",
    "type": "not_found_error",
    "code": "model_not_found"
  }
}
```

### 503 Service Unavailable

All model providers exhausted (no available providers could handle the request).

```json
{
  "error": {
    "message": "All model providers exhausted",
    "type": "service_unavailable",
    "code": "providers_exhausted"
  }
}
```

## Usage Examples

### Single Text Embedding

```bash
curl -X POST https://api.tensorzero.com/v1/embeddings \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "text-embedding-3-small",
    "input": "The quick brown fox jumps over the lazy dog"
  }'
```

### Batch Embeddings

```bash
curl -X POST https://api.tensorzero.com/v1/embeddings \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "text-embedding-3-small",
    "input": [
      "First text to embed",
      "Second text to embed",
      "Third text to embed"
    ]
  }'
```

### With Caching Options

```bash
curl -X POST https://api.tensorzero.com/v1/embeddings \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "text-embedding-3-small",
    "input": "Text to embed with caching",
    "tensorzero::cache_options": {
      "enabled": "on",
      "max_age_s": 3600
    }
  }'
```

### Python Example

```python
import requests
import json

url = "https://api.tensorzero.com/v1/embeddings"
headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}

# Single embedding
data = {
    "model": "text-embedding-3-small",
    "input": "The quick brown fox jumps over the lazy dog"
}

response = requests.post(url, headers=headers, json=data)
result = response.json()

# Extract the embedding vector
embedding = result["data"][0]["embedding"]
print(f"Embedding dimension: {len(embedding)}")

# Batch embeddings
batch_data = {
    "model": "text-embedding-3-small",
    "input": [
        "First text",
        "Second text",
        "Third text"
    ]
}

batch_response = requests.post(url, headers=headers, json=batch_data)
batch_result = batch_response.json()

for item in batch_result["data"]:
    print(f"Index {item['index']}: {len(item['embedding'])} dimensions")
```

### JavaScript/TypeScript Example

```javascript
const url = 'https://api.tensorzero.com/v1/embeddings';
const headers = {
  'Authorization': 'Bearer YOUR_API_KEY',
  'Content-Type': 'application/json'
};

// Single embedding
const data = {
  model: 'text-embedding-3-small',
  input: 'The quick brown fox jumps over the lazy dog'
};

fetch(url, {
  method: 'POST',
  headers: headers,
  body: JSON.stringify(data)
})
  .then(response => response.json())
  .then(result => {
    const embedding = result.data[0].embedding;
    console.log(`Embedding dimension: ${embedding.length}`);
  });

// Batch embeddings with async/await
async function getBatchEmbeddings() {
  const batchData = {
    model: 'text-embedding-3-small',
    input: [
      'First text',
      'Second text',
      'Third text'
    ]
  };

  const response = await fetch(url, {
    method: 'POST',
    headers: headers,
    body: JSON.stringify(batchData)
  });

  const result = await response.json();

  result.data.forEach(item => {
    console.log(`Index ${item.index}: ${item.embedding.length} dimensions`);
  });
}
```

## Notes

- The endpoint supports batch processing for efficiency when embedding multiple texts
- Embeddings are returned as arrays of floating-point numbers
- The model must be configured in TensorZero with embedding capabilities
- Caching can significantly improve performance for repeated queries
- Token usage is calculated based on the input text(s)
- The endpoint is compatible with OpenAI's embedding API format, making it easy to switch between providers
