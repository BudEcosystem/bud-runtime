# Gateway Analytics Module

This module provides API endpoints for accessing gateway analytics data from the budmetrics service. It acts as a proxy layer that adds authentication, authorization, and user context filtering to the raw analytics data.

## Endpoints

### 1. POST `/api/v1/gateway/analytics`
Query comprehensive gateway analytics with flexible filtering options.

**Request Body:**
```json
{
  "project_ids": ["uuid1", "uuid2"],  // Optional: defaults to user's accessible projects
  "model_ids": ["uuid3", "uuid4"],     // Optional
  "endpoint_ids": ["uuid5", "uuid6"],  // Optional
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-01-31T23:59:59Z",
  "time_bucket": "1h",  // Options: 1m, 5m, 1h, 1d
  "metrics": ["total_requests", "error_rate", "avg_response_time"],
  "group_by": ["project_id", "model_id"],
  "filters": {}  // Additional custom filters
}
```

**Response:**
- Time-series analytics data with enriched project/model/endpoint names
- Summary statistics across all time buckets

### 2. GET `/api/v1/gateway/geographical-stats`
Get geographical distribution of API requests.

**Query Parameters:**
- `start_time`: Start time (defaults to 7 days ago)
- `end_time`: End time (defaults to now)
- `project_ids`: Comma-separated list of project IDs (optional)

**Response:**
- Request counts by country, region, and city
- Error counts and average response times by location

### 3. GET `/api/v1/gateway/blocking-stats`
Get statistics on blocked requests for security analysis.

**Query Parameters:**
- `start_time`: Start time (defaults to 7 days ago)
- `end_time`: End time (defaults to now)
- `project_ids`: Comma-separated list of project IDs (optional)

**Response:**
- Blocked IP addresses with reasons
- Block counts and patterns
- Associated project information

### 4. GET `/api/v1/gateway/top-routes`
Get the most frequently accessed API routes.

**Query Parameters:**
- `start_time`: Start time (defaults to 7 days ago)
- `end_time`: End time (defaults to now)
- `limit`: Maximum number of routes to return (1-100, default: 10)
- `project_ids`: Comma-separated list of project IDs (optional)

**Response:**
- Top routes by request count
- Performance metrics (avg, p95, p99 response times)
- Error rates and associated resources

### 5. GET `/api/v1/gateway/client-analytics`
Get analytics data grouped by client/user.

**Query Parameters:**
- `start_time`: Start time (defaults to 7 days ago)
- `end_time`: End time (defaults to now)
- `project_ids`: Comma-separated list of project IDs (optional)

**Response:**
- Per-client request and error counts
- Token usage and cost analysis
- Associated projects and models

## Security

All endpoints:
- Require authentication via JWT token
- Filter results based on the user's project access
- Automatically enrich response data with resource names

## Architecture

The module consists of:
- `schemas.py`: Pydantic models for request/response validation
- `services.py`: Business logic for proxying to budmetrics and filtering data
- `gateway_analytics_routes.py`: FastAPI route definitions

Data flow:
1. Client sends request to budapp endpoint
2. budapp validates authentication and extracts user context
3. budapp determines user's accessible projects
4. Request is proxied to budmetrics service via Dapr
5. Response is enriched with resource names (projects, models, endpoints)
6. Filtered and enriched data is returned to client
