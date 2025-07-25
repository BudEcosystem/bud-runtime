# API Reference

## Overview

The Bud Serve Metrics API provides two main endpoints:
- **Analytics API**: Query time-series metrics with flexible filtering and aggregation
- **Metrics Ingestion API**: Ingest metrics data via CloudEvents (Dapr pub/sub)

## Base URL

```
http://localhost:8000
```

## Analytics Endpoint

### Get Analytics Metrics

Retrieve time-series metrics with various aggregation options.

```http
POST /observability/analytics
Content-Type: application/json
```

#### Request Body

```json
{
  "metrics": ["request_count", "latency"],
  "from_date": "2024-01-01T00:00:00Z",
  "to_date": "2024-01-31T23:59:59Z",
  "frequency_unit": "day",
  "frequency_interval": 1,
  "filters": {
    "project": ["uuid1", "uuid2"],
    "model": "uuid3",
    "endpoint": "uuid4"
  },
  "group_by": ["project", "model"],
  "return_delta": true,
  "fill_time_gaps": true,
  "topk": 10
}
```

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `metrics` | array[string] | Yes | List of metrics to retrieve. See [Available Metrics](#available-metrics) |
| `from_date` | string (ISO 8601) | Yes | Start date for the query |
| `to_date` | string (ISO 8601) | No | End date (defaults to current time) |
| `frequency_unit` | string | No | Time bucket unit: `hour`, `day`, `week`, `month`, `quarter`, `year` (default: `day`) |
| `frequency_interval` | integer | No | Custom interval multiplier. If null, uses standard intervals. If set (including 1), aligns to from_date |
| `filters` | object | No | Filter by project, model, or endpoint UUIDs |
| `group_by` | array[string] | No | Group results by: `project`, `model`, `endpoint` |
| `return_delta` | boolean | No | Include period-over-period changes (default: false) |
| `fill_time_gaps` | boolean | No | Fill missing time periods with null (default: true) |
| `topk` | integer | No | Return only top K entities by primary metric |

#### Available Metrics

| Metric | Description | Unit |
|--------|-------------|------|
| `request_count` | Total number of requests | count |
| `success_request` | Successful requests with success rate | count, % |
| `failure_request` | Failed requests with failure rate | count, % |
| `queuing_time` | Average time in queue | ms |
| `input_token` | Total input tokens | count |
| `output_token` | Total output tokens | count |
| `concurrent_requests` | Maximum concurrent requests | count |
| `ttft` | Time to first token (avg, p95, p99) | ms |
| `latency` | End-to-end latency (avg, p95, p99) | ms |
| `throughput` | Average tokens per second | tokens/s |
| `cache` | Cache hit rate and performance | %, ms |

#### Response

```json
{
  "object": "observability_metrics",
  "items": [
    {
      "time_period": "2024-01-01T00:00:00",
      "items": [
        {
          "model_id": "uuid-here",
          "project_id": "uuid-here",
          "endpoint_id": "uuid-here",
          "data": {
            "request_count": {
              "count": 1000,
              "rate": 41.67,
              "delta": 100,
              "delta_percent": 11.11
            },
            "latency": {
              "avg_latency_ms": 250.5,
              "latency_p95": 450,
              "latency_p99": 650,
              "delta": 25.5,
              "delta_percent": 11.34
            }
          }
        }
      ]
    }
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `object` | string | Always "observability_metrics" |
| `items` | array | List of time period buckets |
| `items[].time_period` | string | ISO 8601 timestamp for the bucket |
| `items[].items` | array | Metrics for each entity in this time period |
| `items[].items[].model_id` | string/null | Model UUID (if grouped by model) |
| `items[].items[].project_id` | string/null | Project UUID (if grouped by project) |
| `items[].items[].endpoint_id` | string/null | Endpoint UUID (if grouped by endpoint) |
| `items[].items[].data` | object | Metric values |

#### Metric Data Structure

Each metric in the `data` object contains:

| Field | Type | Description |
|-------|------|-------------|
| `count`/`value` | number | Primary metric value |
| `rate` | number/null | Rate per second (for count metrics) |
| `delta` | number/null | Change from previous period |
| `delta_percent` | number/null | Percentage change from previous period |

### Examples

#### 1. Simple Daily Request Count

```bash
curl -X POST http://localhost:8000/observability/analytics \
  -H "Content-Type: application/json" \
  -d '{
    "metrics": ["request_count"],
    "from_date": "2024-01-01T00:00:00Z",
    "to_date": "2024-01-07T23:59:59Z",
    "frequency_unit": "day"
  }'
```

#### 2. Hourly Latency by Model (Top 5)

```bash
curl -X POST http://localhost:8000/observability/analytics \
  -H "Content-Type: application/json" \
  -d '{
    "metrics": ["latency", "ttft"],
    "from_date": "2024-01-01T00:00:00Z",
    "to_date": "2024-01-01T23:59:59Z",
    "frequency_unit": "hour",
    "group_by": ["model"],
    "topk": 5,
    "return_delta": true
  }'
```

#### 3. Custom 7-Day Intervals with Filters

```bash
curl -X POST http://localhost:8000/observability/analytics \
  -H "Content-Type: application/json" \
  -d '{
    "metrics": ["request_count", "success_request"],
    "from_date": "2024-01-01T00:00:00Z",
    "to_date": "2024-01-31T23:59:59Z",
    "frequency_unit": "day",
    "frequency_interval": 7,
    "filters": {
      "project": ["550e8400-e29b-41d4-a716-446655440000"]
    },
    "fill_time_gaps": false
  }'
```

## Metrics Ingestion Endpoint

### Add Metrics

Ingest metrics data via CloudEvents format. This endpoint is typically called by Dapr pub/sub.

```http
POST /observability/add
Content-Type: application/json
```

#### Request Body

```json
{
  "entries": [
    {
      "event": {
        "inference_id": "550e8400-e29b-41d4-a716-446655440001",
        "project_id": "550e8400-e29b-41d4-a716-446655440002",
        "endpoint_id": "550e8400-e29b-41d4-a716-446655440003",
        "model_id": "550e8400-e29b-41d4-a716-446655440004",
        "is_success": true,
        "request_arrival_time": "2024-01-01T12:00:00",
        "request_forward_time": "2024-01-01T12:00:00.100",
        "cost": 0.025,
        "request_ip": "192.168.1.1",
        "response_analysis": {
          "sentiment": "positive",
          "confidence": 0.95
        }
      },
      "entryId": "unique-entry-id",
      "metadata": {
        "cloudevent.id": "event-id",
        "cloudevent.type": "add_request_metrics"
      },
      "contentType": "add_request_metrics"
    }
  ],
  "id": "bulk-request-id",
  "pubsubname": "pubsub",
  "topic": "observability-metrics",
  "type": "add_request_metrics"
}
```

#### Event Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `inference_id` | string (UUID) | Yes | Unique inference identifier |
| `project_id` | string (UUID) | Yes | Project identifier |
| `endpoint_id` | string (UUID) | Yes | Endpoint identifier |
| `model_id` | string (UUID) | Yes | Model identifier |
| `is_success` | boolean | Yes | Whether the inference was successful |
| `request_arrival_time` | string | Yes | When the request arrived |
| `request_forward_time` | string | Yes | When the request was forwarded |
| `cost` | number | No | Cost of the inference |
| `request_ip` | string | No | Client IP address |
| `response_analysis` | object | No | Additional analysis data |

#### Response

```json
{
  "message": "Processed 10 metrics",
  "param": {
    "summary": {
      "total_events": 10,
      "successfully_inserted": 8,
      "duplicates_skipped": 2,
      "validation_failures": 0
    },
    "details": {
      "duplicates": ["inference-id-1", "inference-id-2"],
      "failures": []
    }
  }
}
```

## Error Responses

All endpoints use standard HTTP status codes and return errors in the following format:

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
| 400 | `INVALID_REQUEST` | Invalid request parameters |
| 400 | `INVALID_METRIC` | Unknown metric name |
| 400 | `INVALID_FILTER` | Invalid filter field |
| 400 | `INVALID_DATE_RANGE` | Invalid date range |
| 404 | `NOT_FOUND` | Resource not found |
| 500 | `INTERNAL_ERROR` | Server error |
| 503 | `DATABASE_ERROR` | Database connection error |

## Rate Limiting

The API implements rate limiting to prevent abuse:

- **Analytics endpoint**: 100 requests per minute
- **Ingestion endpoint**: 1000 events per second

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Reset timestamp

## Best Practices

1. **Use appropriate time ranges**: Avoid querying years of data with hourly granularity
2. **Leverage TopK**: When grouping by high-cardinality fields, use topk to limit results
3. **Batch ingestion**: Send multiple events in a single request for better performance
4. **Handle duplicates**: The system automatically skips duplicate inference_ids
5. **Time alignment**: Use custom intervals when you need specific time alignment
6. **Caching**: Results are cached; identical queries will be faster

## Webhook Integration

For Dapr pub/sub integration, configure your subscription:

```yaml
apiVersion: dapr.io/v1alpha1
kind: Subscription
metadata:
  name: observability-metrics-subscription
spec:
  topic: observability-metrics
  route: /observability/add
  pubsubname: pubsub
```