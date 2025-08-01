# Metric Proxy API Documentation

## Overview

The Metric Proxy API provides secure access to inference request data by proxying requests to the BudMetrics service with added access control and response enrichment. These endpoints ensure users can only access inference data from projects they have permissions for, while providing additional context such as project names, endpoint names, and model display names.

## Base URL

```
http://localhost:3000/api/v1
```

## Authentication

All endpoints require authentication via JWT token and proper user permissions:
- **Bearer Token**: Include `Authorization: Bearer <token>` header
- **User Permissions**: Access controlled by project membership and user roles
- **Project Access**: Users can only view inferences from projects they have access to

## Endpoints

### 1. List Inference Requests

Retrieve a paginated list of inference requests with access control and enriched data.

```http
POST /api/v1/metrics/inferences/list
Content-Type: application/json
Authorization: Bearer <token>
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
| `limit` | integer | No | 50 | Maximum records to return (max 100) |
| `project_id` | UUID | No | - | Filter by specific project (user must have access) |
| `endpoint_id` | UUID | No | - | Filter by specific endpoint |
| `model_id` | UUID | No | - | Filter by specific model |
| `from_date` | datetime | Yes | - | Start date for inference requests (ISO 8601) |
| `to_date` | datetime | No | Now | End date for inference requests (ISO 8601) |
| `is_success` | boolean | No | - | Filter by success status |
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
        "project_name": "Production AI Assistant",
        "endpoint_id": "550e8400-e29b-41d4-a716-446655440002",
        "endpoint_name": "Chat Endpoint v1.0",
        "model_id": "550e8400-e29b-41d4-a716-446655440003",
        "model_name": "GPT-4 Turbo",
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

#### Response Enrichment

The proxy service enhances BudMetrics responses with:

| Enriched Field | Description | Source |
|----------------|-------------|---------|
| `project_name` | Human-readable project name | BudApp project registry |
| `endpoint_name` | Human-readable endpoint name | BudApp endpoint registry |
| `model_name` | Human-readable model display name | BudApp model registry |

### 2. Get Inference Details

Retrieve complete details for a single inference request with access control.

```http
GET /api/v1/metrics/inferences/{inference_id}
Authorization: Bearer <token>
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
    "project_name": "Production AI Assistant",
    "endpoint_id": "550e8400-e29b-41d4-a716-446655440002",
    "endpoint_name": "Chat Endpoint v1.0",
    "model_id": "550e8400-e29b-41d4-a716-446655440003",
    "model_name": "GPT-4 Turbo",
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

### 3. Get Inference Feedback

Retrieve all feedback associated with a specific inference request.

```http
GET /api/v1/metrics/inferences/{inference_id}/feedback
Authorization: Bearer <token>
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
    "project_name": "Production AI Assistant",
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

## Access Control

### Project-Level Security

The proxy service implements row-level security:

1. **User Authentication**: Validates JWT token and user status
2. **Project Access Validation**: Ensures user has access to requested project data
3. **Cross-Project Prevention**: Blocks access to inferences from unauthorized projects
4. **Role-Based Filtering**: Applies additional filtering based on user roles

### Access Control Flow

```mermaid
graph TD
    A[Request] --> B[Authenticate User]
    B --> C{Valid Token?}
    C -->|No| D[401 Unauthorized]
    C -->|Yes| E[Extract Project IDs]
    E --> F[Validate Project Access]
    F --> G{Has Access?}
    G -->|No| H[403 Forbidden]
    G -->|Yes| I[Proxy to BudMetrics]
    I --> J[Enrich Response]
    J --> K[Return Data]
```

### Access Validation Logic

```python
# Pseudo-code for access control
async def validate_access(user: User, project_ids: List[UUID]) -> bool:
    user_projects = await get_user_projects(user.id)
    accessible_projects = [p.id for p in user_projects]

    for project_id in project_ids:
        if project_id not in accessible_projects:
            raise ForbiddenException(f"No access to project {project_id}")

    return True
```

## Response Enrichment Process

### Enrichment Pipeline

1. **Proxy Request**: Forward request to BudMetrics service
2. **Receive Response**: Get raw inference data from BudMetrics
3. **Extract Identifiers**: Parse project_id, endpoint_id, model_id from response
4. **Fetch Metadata**: Query BudApp database for entity names
5. **Merge Data**: Combine original response with enriched metadata
6. **Return Enhanced Response**: Send enriched data to client

### Enrichment Details

```python
# Pseudo-code for response enrichment
async def enrich_response(raw_response: dict, session: Session) -> dict:
    enriched_response = raw_response.copy()

    # Extract unique IDs
    project_ids = extract_project_ids(raw_response)
    endpoint_ids = extract_endpoint_ids(raw_response)
    model_ids = extract_model_ids(raw_response)

    # Fetch metadata in batch
    projects = await fetch_projects(project_ids, session)
    endpoints = await fetch_endpoints(endpoint_ids, session)
    models = await fetch_models(model_ids, session)

    # Create lookup maps
    project_names = {p.id: p.name for p in projects}
    endpoint_names = {e.id: e.name for e in endpoints}
    model_names = {m.id: m.display_name for m in models}

    # Enrich response data
    for inference in enriched_response.get("data", {}).get("inferences", []):
        inference["project_name"] = project_names.get(inference["project_id"])
        inference["endpoint_name"] = endpoint_names.get(inference["endpoint_id"])
        inference["model_name"] = model_names.get(inference["model_id"])

    return enriched_response
```

## Error Responses

All endpoints return standardized error responses with appropriate HTTP status codes:

```json
{
  "error": {
    "code": 400,
    "message": "Description of the error",
    "details": {
      "field": "Additional context"
    }
  }
}
```

### Common Error Scenarios

| Status | Code | Description | Reason |
|--------|------|-------------|---------|
| 401 | `UNAUTHORIZED` | Authentication required | Missing or invalid token |
| 403 | `FORBIDDEN` | Access denied | User lacks project access |
| 400 | `BAD_REQUEST` | Invalid request | Malformed request parameters |
| 404 | `NOT_FOUND` | Resource not found | Inference ID does not exist |
| 500 | `INTERNAL_ERROR` | Server error | Service or database error |
| 503 | `SERVICE_UNAVAILABLE` | BudMetrics unavailable | Downstream service error |

## Integration with BudMetrics

### Service Communication

The proxy service communicates with BudMetrics via Dapr service invocation:

```python
# Service invocation configuration
BUDMETRICS_SERVICE_ID = "budmetrics"
DAPR_HTTP_PORT = 3500

# Endpoint mapping
ENDPOINTS = {
    "list": "/observability/inferences/list",
    "details": "/observability/inferences/{inference_id}",
    "feedback": "/observability/inferences/{inference_id}/feedback"
}
```

### Request Flow

1. **Client Request**: Frontend sends request to BudApp proxy
2. **Authentication**: BudApp validates user and permissions
3. **Service Invocation**: BudApp calls BudMetrics via Dapr
4. **Data Processing**: BudMetrics queries ClickHouse and returns data
5. **Response Enrichment**: BudApp adds entity names and metadata
6. **Client Response**: Enriched data returned to frontend

### Error Handling

- **Timeout Handling**: 30-second timeout for BudMetrics calls
- **Retry Logic**: Automatic retry for transient failures
- **Fallback Responses**: Graceful degradation when enrichment fails
- **Circuit Breaker**: Protection against cascading failures

## Performance Considerations

### Caching Strategy

- **Response Caching**: Identical requests cached for 5 minutes
- **Metadata Caching**: Entity names cached for 1 hour
- **Cache Invalidation**: Automatic invalidation on entity updates

### Optimization Techniques

- **Batch Queries**: Bulk fetch entity metadata to reduce database round trips
- **Connection Pooling**: Reuse database connections for better performance
- **Async Processing**: Non-blocking I/O for service calls
- **Request Deduplication**: Prevent duplicate concurrent requests

## Rate Limiting

- **Per User**: 1000 requests per hour per authenticated user
- **Per Endpoint**:
  - List endpoint: 100 requests per 10 minutes
  - Details endpoint: 500 requests per 10 minutes
  - Feedback endpoint: 500 requests per 10 minutes

Rate limit headers included in responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining in current window
- `X-RateLimit-Reset`: Unix timestamp when limit resets

## Monitoring and Logging

### Request Logging

All requests are logged with:
- User ID and authentication status
- Request parameters and filters applied
- Response time and status code
- Project access validation results
- Downstream service call metrics

### Metrics Collection

- **Request Volume**: Number of requests per endpoint
- **Response Times**: P50, P95, P99 latencies
- **Error Rates**: Error percentage by endpoint and error type
- **Access Denials**: Failed authorization attempts
- **Cache Hit Rates**: Effectiveness of caching strategy

## Security Best Practices

### Data Protection

1. **Sensitive Data Filtering**: Remove sensitive information from logs
2. **Input Validation**: Validate all request parameters
3. **Output Sanitization**: Clean response data before sending
4. **Audit Logging**: Track all data access for compliance

### Authentication Security

1. **Token Validation**: Verify JWT signatures and expiration
2. **Permission Caching**: Cache user permissions with TTL
3. **Session Management**: Track user sessions and enforce limits
4. **Access Logging**: Log all authentication and authorization events

## Example Usage

### List User's Inferences

```bash
curl -X POST https://api.example.com/api/v1/metrics/inferences/list \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "from_date": "2024-01-01T00:00:00Z",
    "to_date": "2024-01-07T23:59:59Z",
    "limit": 25,
    "sort_by": "timestamp",
    "sort_order": "desc"
  }'
```

### Get Specific Inference with Project Filter

```bash
curl -X POST https://api.example.com/api/v1/metrics/inferences/list \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "project_id": "550e8400-e29b-41d4-a716-446655440000",
    "from_date": "2024-01-01T00:00:00Z",
    "limit": 10
  }'
```

### Get Inference Details

```bash
curl -X GET https://api.example.com/api/v1/metrics/inferences/550e8400-e29b-41d4-a716-446655440001 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Get Inference Feedback

```bash
curl -X GET https://api.example.com/api/v1/metrics/inferences/550e8400-e29b-41d4-a716-446655440001/feedback \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## Integration Notes

### Frontend Integration

- **BudAdmin Dashboard**: Primary consumer of these endpoints
- **Authentication Flow**: Uses existing JWT token management
- **Error Handling**: Consistent error format for UI display
- **Loading States**: Supports progressive loading and pagination

### Service Dependencies

- **BudMetrics**: Upstream service providing raw inference data
- **Database**: PostgreSQL for entity metadata and user permissions
- **Dapr**: Service mesh for inter-service communication
- **Redis**: Caching layer for performance optimization

The proxy endpoints provide a secure, enriched interface for accessing inference data while maintaining proper access control and optimal performance.
