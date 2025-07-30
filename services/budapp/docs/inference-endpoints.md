# Inference Request/Prompt Listing API Documentation

This document describes the API endpoints for viewing and analyzing inference requests, including prompts, responses, and performance metrics.

## Overview

The inference API provides comprehensive access to AI/ML model inference data, including:
- Individual request details with prompts and responses
- Performance metrics (latency, tokens, cost)
- User feedback and ratings
- Filtering and pagination capabilities
- Export functionality

## Authentication

All endpoints require authentication via Bearer token in the Authorization header:

```
Authorization: Bearer <your-access-token>
```

## Endpoints

### 1. List Inference Requests

Retrieve a paginated list of inference requests with filtering options.

**Endpoint:** `POST /api/v1/metrics/inferences/list`

**Request Body:**
```json
{
  "project_id": "uuid",           // Optional: Filter by project
  "endpoint_id": "uuid",          // Optional: Filter by endpoint
  "model_id": "uuid",             // Optional: Filter by model
  "from_date": "2024-01-01T00:00:00Z",  // Required: Start date (ISO 8601)
  "to_date": "2024-01-31T23:59:59Z",    // Optional: End date (ISO 8601)
  "is_success": true,             // Optional: Filter by success status
  "min_tokens": 100,              // Optional: Minimum total tokens
  "max_tokens": 1000,             // Optional: Maximum total tokens
  "max_latency_ms": 5000,         // Optional: Maximum response time
  "sort_by": "timestamp",         // Optional: Sort field (timestamp, tokens, latency, cost)
  "sort_order": "desc",           // Optional: Sort order (asc, desc)
  "offset": 0,                    // Optional: Pagination offset (default: 0)
  "limit": 50                     // Optional: Page size (default: 50, max: 1000)
}
```

**Response:**
```json
{
  "items": [
    {
      "inference_id": "550e8400-e29b-41d4-a716-446655440001",
      "timestamp": "2024-01-15T10:30:00Z",
      "project_id": "proj-123",
      "project_name": "My AI Project",        // Enriched field
      "endpoint_id": "ep-456",
      "endpoint_name": "Production Endpoint",  // Enriched field
      "model_id": "model-789",
      "model_name": "gpt-4",
      "model_display_name": "GPT-4",          // Enriched field
      "model_provider": "openai",
      "is_success": true,
      "input_tokens": 150,
      "output_tokens": 250,
      "response_time_ms": 1234,
      "ttft_ms": 123,                         // Time to first token (optional)
      "cost": 0.0045,
      "cached": false,
      "prompt_preview": "What is the capital of...",  // First 100 chars
      "response_preview": "The capital of France is...", // First 100 chars
      "feedback_count": 3,
      "average_rating": 4.5
    }
  ],
  "total_count": 1523,
  "offset": 0,
  "limit": 50
}
```

**Status Codes:**
- `200 OK`: Success
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Missing or invalid authentication
- `404 Not Found`: Project not found or access denied
- `500 Internal Server Error`: Server error

### 2. Get Inference Details

Retrieve complete details for a single inference request.

**Endpoint:** `GET /api/v1/metrics/inferences/{inference_id}`

**Path Parameters:**
- `inference_id`: The UUID of the inference request

**Response:**
```json
{
  "inference_id": "550e8400-e29b-41d4-a716-446655440001",
  "timestamp": "2024-01-15T10:30:00Z",
  "project_id": "proj-123",
  "project_name": "My AI Project",
  "endpoint_id": "ep-456",
  "endpoint_name": "Production Endpoint",
  "model_id": "model-789",
  "model_name": "gpt-4",
  "model_display_name": "GPT-4",
  "model_provider": "openai",
  "is_success": true,
  "input_tokens": 150,
  "output_tokens": 250,
  "response_time_ms": 1234,
  "ttft_ms": 123,
  "processing_time_ms": 1100,
  "cost": 0.0045,
  "cached": false,
  "request_ip": "192.168.1.100",
  "system_prompt": "You are a helpful AI assistant...",
  "messages": [
    {
      "role": "user",
      "content": "What is the capital of France?"
    },
    {
      "role": "assistant",
      "content": "The capital of France is Paris. Paris is not only the capital but also the largest city in France..."
    }
  ],
  "output": "The capital of France is Paris. Paris is not only the capital but also the largest city in France...",
  "finish_reason": "stop",
  "raw_request": "{\"model\": \"gpt-4\", \"messages\": [...]}",  // Optional: Raw API request
  "raw_response": "{\"id\": \"chatcmpl-...\", \"object\": \"chat.completion\", ...}",  // Optional: Raw API response
  "feedback_count": 3,
  "average_rating": 4.5
}
```

**Status Codes:**
- `200 OK`: Success
- `401 Unauthorized`: Missing or invalid authentication
- `403 Forbidden`: Access denied (inference belongs to another project)
- `404 Not Found`: Inference not found
- `500 Internal Server Error`: Server error

### 3. Get Inference Feedback

Retrieve all feedback associated with an inference request.

**Endpoint:** `GET /api/v1/metrics/inferences/{inference_id}/feedback`

**Path Parameters:**
- `inference_id`: The UUID of the inference request

**Response:**
```json
[
  {
    "feedback_id": "fb-001",
    "inference_id": "550e8400-e29b-41d4-a716-446655440001",
    "created_at": "2024-01-15T10:35:00Z",
    "feedback_type": "boolean",
    "metric_name": "helpful",
    "value": true
  },
  {
    "feedback_id": "fb-002",
    "inference_id": "550e8400-e29b-41d4-a716-446655440001",
    "created_at": "2024-01-15T10:36:00Z",
    "feedback_type": "float",
    "metric_name": "quality_rating",
    "value": 4.5
  },
  {
    "feedback_id": "fb-003",
    "inference_id": "550e8400-e29b-41d4-a716-446655440001",
    "created_at": "2024-01-15T10:37:00Z",
    "feedback_type": "comment",
    "metric_name": "user_comment",
    "value": "Great response, very helpful!"
  },
  {
    "feedback_id": "fb-004",
    "inference_id": "550e8400-e29b-41d4-a716-446655440001",
    "created_at": "2024-01-15T10:38:00Z",
    "feedback_type": "demonstration",
    "metric_name": "corrected_output",
    "value": "The capital of France is Paris, which has a population of over 2 million people."
  }
]
```

**Feedback Types:**
- `boolean`: Yes/no feedback (e.g., helpful, accurate)
- `float`: Numeric ratings (e.g., quality score 1-5)
- `comment`: Text feedback from users
- `demonstration`: Example corrections or improvements

**Status Codes:**
- `200 OK`: Success (returns empty array if no feedback)
- `401 Unauthorized`: Missing or invalid authentication
- `403 Forbidden`: Access denied (inference belongs to another project)
- `404 Not Found`: Inference not found
- `500 Internal Server Error`: Server error

## Error Responses

All error responses follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

## Rate Limiting

API endpoints are rate-limited to ensure fair usage:
- List requests: 100 requests per minute
- Detail/feedback requests: 500 requests per minute

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Unix timestamp when limit resets

## Pagination

The list endpoint supports pagination with the following parameters:
- `offset`: Number of records to skip (0-based)
- `limit`: Number of records to return (max: 1000)

The response includes:
- `total_count`: Total number of matching records
- `offset`: Current offset
- `limit`: Current page size

## Filtering Best Practices

1. **Date Ranges**: Always specify a `from_date` to limit the search scope. Without date filtering, queries may be slow.

2. **Project Filtering**: When possible, filter by `project_id` to improve performance and ensure you only see authorized data.

3. **Token Filtering**: Use `min_tokens` and `max_tokens` to find requests within specific token ranges.

4. **Performance Analysis**: Use `max_latency_ms` to identify slow requests that may need optimization.

## Export Functionality

While not directly part of the API, the frontend provides export capabilities:
- CSV format for spreadsheet analysis
- JSON format for programmatic processing

## Examples

### Example 1: Get recent failed inferences

```bash
curl -X POST https://api.example.com/api/v1/metrics/inferences/list \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "proj-123",
    "from_date": "2024-01-01T00:00:00Z",
    "is_success": false,
    "sort_by": "timestamp",
    "sort_order": "desc",
    "limit": 20
  }'
```

### Example 2: Find expensive inferences

```bash
curl -X POST https://api.example.com/api/v1/metrics/inferences/list \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "from_date": "2024-01-01T00:00:00Z",
    "min_tokens": 1000,
    "sort_by": "cost",
    "sort_order": "desc",
    "limit": 50
  }'
```

### Example 3: Get inference with feedback

```bash
# First get the inference details
INFERENCE_ID="550e8400-e29b-41d4-a716-446655440001"
curl -X GET "https://api.example.com/api/v1/metrics/inferences/$INFERENCE_ID" \
  -H "Authorization: Bearer $TOKEN"

# Then get the feedback
curl -X GET "https://api.example.com/api/v1/metrics/inferences/$INFERENCE_ID/feedback" \
  -H "Authorization: Bearer $TOKEN"
```

## Data Retention

Inference data is retained according to the following policy:
- Standard plan: 30 days
- Pro plan: 90 days
- Enterprise plan: Customizable

After the retention period, data is automatically archived or deleted.