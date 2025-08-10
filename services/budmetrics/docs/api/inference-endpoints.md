# Inference Request API Documentation

## Overview

The Inference Request API provides endpoints for viewing and analyzing individual AI model inference requests. This feature allows administrators and project members to examine detailed information about model interactions, including prompts, responses, performance metrics, and user feedback.

## Base URL

```
http://localhost:8000
```

## Authentication

All endpoints require proper authentication via the service's internal authentication mechanism.

## Endpoints

### 1. List Inference Requests

Retrieve a paginated list of inference requests with comprehensive filtering and sorting capabilities.

```http
POST /observability/inferences/list
Content-Type: application/json
```

#### Request Schema

```json
{
  "offset": 0,
  "limit": 50,
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "endpoint_id": "550e8400-e29b-41d4-a716-446655440001",
  "model_id": "550e8400-e29b-41d4-a716-446655440002",
  "from_date": "2024-01-01T00:00:00Z",
  "to_date": "2024-01-31T23:59:59Z",
  "is_success": true,
  "min_tokens": 100,
  "max_tokens": 5000,
  "max_latency_ms": 2000,
  "sort_by": "timestamp",
  "sort_order": "desc"
}
```

#### Request Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `offset` | integer | No | 0 | Number of records to skip for pagination |
| `limit` | integer | No | 50 | Maximum number of records to return (max 100) |
| `project_id` | UUID | No | - | Filter by specific project |
| `endpoint_id` | UUID | No | - | Filter by specific endpoint |
| `model_id` | UUID | No | - | Filter by specific model |
| `from_date` | datetime | Yes | - | Start date for inference requests (ISO 8601) |
| `to_date` | datetime | No | Now | End date for inference requests (ISO 8601) |
| `is_success` | boolean | No | - | Filter by success status (true/false/null for all) |
| `min_tokens` | integer | No | - | Minimum total token count filter |
| `max_tokens` | integer | No | - | Maximum total token count filter |
| `max_latency_ms` | integer | No | - | Maximum latency filter in milliseconds |
| `sort_by` | string | No | "timestamp" | Sort field: "timestamp", "tokens", "latency", "cost" |
| `sort_order` | string | No | "desc" | Sort order: "asc" or "desc" |

#### Response Schema

```json
{
  "data": {
    "inferences": [
      {
        "inference_id": "550e8400-e29b-41d4-a716-446655440001",
        "project_id": "550e8400-e29b-41d4-a716-446655440000",
        "endpoint_id": "550e8400-e29b-41d4-a716-446655440002",
        "model_id": "550e8400-e29b-41d4-a716-446655440003",
        "is_success": true,
        "created_at": "2024-01-15T10:30:00Z",
        "latency_ms": 250,
        "ttft_ms": 45,
        "input_tokens": 150,
        "output_tokens": 300,
        "total_tokens": 450,
        "cost": 0.0123,
        "prompt_preview": "What is the capital of France?",
        "response_preview": "The capital of France is Paris...",
        "has_feedback": true
      }
    ],
    "total_count": 1250,
    "has_more": true
  }
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `data.inferences` | array | List of inference records |
| `data.total_count` | integer | Total number of inferences matching filters |
| `data.has_more` | boolean | Whether more records are available |
| `inferences[].inference_id` | UUID | Unique identifier for the inference |
| `inferences[].project_id` | UUID | Project identifier |
| `inferences[].endpoint_id` | UUID | Endpoint identifier |
| `inferences[].model_id` | UUID | Model identifier |
| `inferences[].is_success` | boolean | Whether the inference completed successfully |
| `inferences[].created_at` | datetime | When the inference was created |
| `inferences[].latency_ms` | integer | Total response latency in milliseconds |
| `inferences[].ttft_ms` | integer | Time to first token in milliseconds |
| `inferences[].input_tokens` | integer | Number of input tokens |
| `inferences[].output_tokens` | integer | Number of output tokens |
| `inferences[].total_tokens` | integer | Total tokens (input + output) |
| `inferences[].cost` | float | Cost in USD for the inference |
| `inferences[].prompt_preview` | string | First 100 characters of the prompt |
| `inferences[].response_preview` | string | First 100 characters of the response |
| `inferences[].has_feedback` | boolean | Whether the inference has user feedback |

### 2. Get Inference Details

Retrieve complete details for a single inference request, including full prompt/response content and metadata.

```http
GET /observability/inferences/{inference_id}
```

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `inference_id` | UUID | Yes | The UUID of the inference to retrieve |

#### Response Schema

```json
{
  "data": {
    "inference_id": "550e8400-e29b-41d4-a716-446655440001",
    "project_id": "550e8400-e29b-41d4-a716-446655440000",
    "endpoint_id": "550e8400-e29b-41d4-a716-446655440002",
    "model_id": "550e8400-e29b-41d4-a716-446655440003",
    "is_success": true,
    "created_at": "2024-01-15T10:30:00Z",
    "request_arrival_time": "2024-01-15T10:29:58Z",
    "request_forward_time": "2024-01-15T10:29:59Z",
    "response_received_time": "2024-01-15T10:30:00Z",
    "latency_ms": 250,
    "ttft_ms": 45,
    "input_tokens": 150,
    "output_tokens": 300,
    "total_tokens": 450,
    "cost": 0.0123,
    "request_ip": "192.168.1.100",
    "messages": [
      {
        "role": "user",
        "content": "What is the capital of France?"
      },
      {
        "role": "assistant",
        "content": "The capital of France is Paris, a beautiful city known for its architecture, culture, and history."
      }
    ],
    "model_details": {
      "model_name": "gpt-4",
      "provider": "OpenAI",
      "version": "2024-01-01"
    },
    "raw_request": {
      "model": "gpt-4",
      "messages": [...],
      "temperature": 0.7,
      "max_tokens": 500
    },
    "raw_response": {
      "id": "chatcmpl-123",
      "object": "chat.completion",
      "created": 1704445800,
      "model": "gpt-4",
      "choices": [...]
    },
    "feedback_summary": {
      "has_feedback": true,
      "total_feedback_count": 3,
      "average_rating": 4.2
    }
  }
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `data.inference_id` | UUID | Unique identifier for the inference |
| `data.messages` | array | Chat messages in the conversation |
| `data.model_details` | object | Information about the model used |
| `data.raw_request` | object | Complete original request payload |
| `data.raw_response` | object | Complete response from the model provider |
| `data.feedback_summary` | object | Summary of user feedback |
| `data.request_ip` | string | IP address of the requesting client |
| `data.*_time` | datetime | Various timestamps in the inference lifecycle |

### 3. Get Inference Feedback

Retrieve all feedback associated with a specific inference request.

```http
GET /observability/inferences/{inference_id}/feedback
```

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `inference_id` | UUID | Yes | The UUID of the inference |

#### Response Schema

```json
{
  "data": {
    "inference_id": "550e8400-e29b-41d4-a716-446655440001",
    "feedback": {
      "boolean_metrics": [
        {
          "metric_name": "helpful",
          "value": true,
          "created_at": "2024-01-15T10:35:00Z",
          "user_id": "user-123"
        }
      ],
      "float_metrics": [
        {
          "metric_name": "accuracy",
          "value": 4.5,
          "created_at": "2024-01-15T10:36:00Z",
          "user_id": "user-123"
        }
      ],
      "comments": [
        {
          "comment": "This response was very helpful and accurate.",
          "created_at": "2024-01-15T10:37:00Z",
          "user_id": "user-123"
        }
      ],
      "demonstrations": [
        {
          "demonstration_data": {
            "preferred_response": "Alternative response that would be better..."
          },
          "created_at": "2024-01-15T10:38:00Z",
          "user_id": "user-456"
        }
      ]
    },
    "summary": {
      "total_feedback_items": 4,
      "boolean_metrics_count": 1,
      "float_metrics_count": 1,
      "comments_count": 1,
      "demonstrations_count": 1,
      "average_float_rating": 4.5,
      "positive_boolean_percentage": 100.0
    }
  }
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `data.feedback.boolean_metrics` | array | True/false feedback metrics |
| `data.feedback.float_metrics` | array | Numeric rating feedback |
| `data.feedback.comments` | array | Text comments from users |
| `data.feedback.demonstrations` | array | Alternative response demonstrations |
| `data.summary` | object | Aggregated feedback statistics |

## ClickHouse Integration Details

### Database Tables

The inference endpoints query the following ClickHouse tables:

1. **ModelInference**: Main inference records with performance metrics
2. **ChatInference**: Chat-specific data including messages
3. **ModelInferenceDetails**: Extended metadata and raw request/response data
4. **BooleanMetric**: Boolean feedback metrics
5. **FloatMetric**: Numeric feedback metrics
6. **CommentMetric**: Text feedback comments
7. **DemonstrationMetric**: Alternative response demonstrations

### Query Optimization

- **Indexes**: Primary indexes on `inference_id` and `created_at` for efficient filtering
- **Partitioning**: Tables partitioned by date for improved query performance
- **Compression**: ZSTD compression for optimal storage
- **Materialized Views**: Pre-aggregated views for common query patterns

### Performance Considerations

- **Date Range Filtering**: Always include date filters to leverage partitioning
- **Limit Usage**: Use reasonable limits (≤100) to prevent resource exhaustion
- **Complex Filters**: Token and latency filters are applied after primary filtering
- **Sorting**: Sorting by indexed columns (timestamp, inference_id) is most efficient

## Error Responses

All endpoints return standardized error responses:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Description of the error",
    "details": {
      "field": "Additional context"
    }
  }
}
```

### Common Error Codes

| Status | Code | Description |
|--------|------|-------------|
| 400 | `INVALID_REQUEST` | Invalid request parameters or format |
| 400 | `INVALID_UUID` | Malformed UUID in request |
| 400 | `INVALID_DATE_RANGE` | Invalid or illogical date range |
| 400 | `INVALID_PAGINATION` | Invalid offset/limit values |
| 404 | `INFERENCE_NOT_FOUND` | Inference ID does not exist |
| 422 | `VALIDATION_ERROR` | Request validation failed |
| 500 | `DATABASE_ERROR` | ClickHouse connection or query error |
| 503 | `SERVICE_UNAVAILABLE` | Service temporarily unavailable |

## Rate Limiting

- **List endpoint**: 100 requests per minute per client
- **Details endpoint**: 200 requests per minute per client
- **Feedback endpoint**: 200 requests per minute per client

Rate limit headers included in responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining in current window
- `X-RateLimit-Reset`: Unix timestamp when limit resets

## Best Practices

### Query Optimization
1. **Always specify date ranges**: Use reasonable date ranges to leverage partitioning
2. **Use appropriate pagination**: Start with reasonable limits (50-100 records)
3. **Filter early**: Apply project/endpoint/model filters to reduce dataset size
4. **Cache results**: Results are internally cached for identical queries

### Data Privacy
1. **Access Control**: Ensure proper authentication and authorization
2. **Sensitive Data**: Full prompts/responses may contain sensitive information
3. **Audit Logging**: All access is logged for security auditing
4. **Data Retention**: Respect data retention policies when querying historical data

### Performance Guidelines
1. **Avoid large date ranges**: Limit queries to reasonable time periods
2. **Use specific filters**: Apply entity filters (project_id, model_id) when possible
3. **Monitor query times**: Large result sets may impact performance
4. **Consider pagination**: Use offset/limit for large datasets

## Example Usage

### Basic Inference Listing

```bash
curl -X POST http://localhost:8000/observability/inferences/list \
  -H "Content-Type: application/json" \
  -d '{
    "from_date": "2024-01-01T00:00:00Z",
    "to_date": "2024-01-07T23:59:59Z",
    "project_id": "550e8400-e29b-41d4-a716-446655440000",
    "limit": 25,
    "sort_by": "timestamp",
    "sort_order": "desc"
  }'
```

### Filtered by Performance Metrics

```bash
curl -X POST http://localhost:8000/observability/inferences/list \
  -H "Content-Type: application/json" \
  -d '{
    "from_date": "2024-01-01T00:00:00Z",
    "min_tokens": 100,
    "max_tokens": 1000,
    "max_latency_ms": 500,
    "is_success": true,
    "sort_by": "latency"
  }'
```

### Get Complete Inference Details

```bash
curl -X GET http://localhost:8000/observability/inferences/550e8400-e29b-41d4-a716-446655440001
```

### Get Inference Feedback

```bash
curl -X GET http://localhost:8000/observability/inferences/550e8400-e29b-41d4-a716-446655440001/feedback
```

## Integration Notes

This API is designed to work with:
- **BudApp**: Provides proxy endpoints with access control
- **BudAdmin**: Frontend dashboard for viewing inference data
- **Authentication**: Integrates with existing service authentication
- **Monitoring**: All endpoints are monitored and logged
- **Caching**: Results cached for improved performance

The endpoints provide the foundation for comprehensive inference analysis and monitoring capabilities across the Bud platform.
