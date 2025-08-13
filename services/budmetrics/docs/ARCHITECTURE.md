# Architecture Overview

## System Architecture

```
┌─────────────────────┐     ┌─────────────────────┐
│   Client Apps       │     │   Event Publishers  │
└──────────┬──────────┘     └──────────┬──────────┘
           │                           │
           │                           ▼
           │              ┌────────────────────────┐
           │              │   Dapr Runtime        │
           │              │  ┌─────────────────┐  │
           │              │  │ Pub/Sub (Redis) │  │
           │              │  └────────┬────────┘  │
           │              └───────────┼────────────┘
           │                          │
           ▼                          ▼
┌─────────────────────────────────────────────────┐
│              API Layer (FastAPI)                │
│  ┌─────────────┐      ┌────────────────────┐   │
│  │  Analytics  │      │   Metrics Ingestion │   │
│  │  Endpoint   │      │  Endpoint (/add)    │   │
│  └──────┬──────┘      └─────────┬──────────┘   │
└─────────┼───────────────────────┼──────────────┘
          │                       │
          ▼                       ▼
┌─────────────────────────────────────────────────┐
│            Service Layer                         │
│  ┌──────────────┐    ┌─────────────────────┐   │
│  │Query Builder │    │  Result Processor   │   │
│  │  & CTEs     │    │  & Aggregation      │   │
│  └──────┬───────┘    └─────────┬───────────┘   │
└─────────┼──────────────────────┼───────────────┘
          │                      │
          ▼                      ▼
┌─────────────────────────────────────────────────┐
│           Data Layer                            │
│  ┌──────────────┐    ┌─────────────────────┐   │
│  │  ClickHouse  │    │   Query Cache       │   │
│  │   Client     │    │   (In-Memory)       │   │
│  └──────┬───────┘    └─────────────────────┘   │
└─────────┼───────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────┐
│              ClickHouse Database                │
│  ┌──────────────────┐  ┌──────────────────┐    │
│  │ModelInference    │  │ModelInference     │    │
│  │                  │  │Details            │    │
│  └──────────────────┘  └──────────────────┘    │
└─────────────────────────────────────────────────┘
```

## Core Components

### 1. Dapr Integration

The application leverages Dapr runtime through BudMicroframe for event-driven communication:

- **Pub/Sub**: Redis-backed pub/sub for the `/add` endpoint to receive metrics events
- **CloudEvents**: Standardized event format for metrics ingestion
- **Decoupling**: Publishers can send metrics without direct API coupling

### 2. Models Layer (`budmetrics/observability/models.py`)

The models layer contains the core query building logic and data structures.

#### Key Classes

**QueryBuilder**
- Responsible for constructing ClickHouse SQL queries
- Supports dynamic metric selection, filtering, and grouping
- Handles CTE (Common Table Expression) generation
- Manages time series bucketing and alignment

**ClickHouseClient**
- Manages connection pooling to ClickHouse
- Provides async query execution
- Implements query caching (optional)
- Handles batch operations and streaming

**Frequency & TimeSeriesHelper**
- Manages time interval specifications
- Handles standard (daily, weekly) vs custom intervals
- Ensures proper time bucket alignment

**MetricDefinition**
- Defines how each metric is calculated
- Specifies required tables and joins
- Supports CTE dependencies
- Configures TopK sorting behavior

### 3. Services Layer (`budmetrics/observability/services.py`)

**ObservabilityService**
- Main business logic orchestrator
- Coordinates query building and execution
- Handles result post-processing
- Manages caching strategies

**Result Processing Pipeline**
1. Raw query results from ClickHouse
2. Gap-filled row detection and handling
3. Metric aggregation and grouping
4. Delta calculation (period-over-period)
5. Response formatting

### 4. API Layer (`budmetrics/observability/routes.py`)

**Analytics Endpoint**
- Request validation using Pydantic schemas
- Query parameter processing
- Error handling and response formatting
- Performance profiling integration

**Metrics Ingestion Endpoint (/add)**
- Receives events via Dapr pub/sub
- Bulk data ingestion using CloudEvents format
- Duplicate detection
- Batch processing for efficiency
- Validation and error reporting

## Key Architectural Patterns

### 1. Event-Driven Metrics Ingestion

The `/add` endpoint receives metrics through Dapr pub/sub:

```python
# CloudEvent structure for metrics ingestion
{
    "entries": [
        {
            "event": {
                "inference_id": "uuid",
                "project_id": "uuid",
                "endpoint_id": "uuid",
                "model_id": "uuid",
                "is_success": true,
                "request_arrival_time": "2024-01-01T00:00:00",
                "request_forward_time": "2024-01-01T00:00:01",
                "cost": 0.025,
                "response_analysis": {...}
            },
            "entryId": "request-id",
            "metadata": {
                "cloudevent.id": "event-id",
                "cloudevent.type": "add_request_metrics"
            },
            "contentType": "add_request_metrics"
        }
    ],
    "pubsubname": "pubsub",
    "topic": "observability-metrics",
    "type": "add_request_metrics"
}
```

### 2. CTE (Common Table Expression) System

CTEs are used for complex calculations that need to be reused:

```python
@dataclass
class CTEDefinition:
    name: str                    # CTE identifier
    query: str                   # SQL query (can contain placeholders)
    base_tables: list[str]       # Underlying tables
    is_template: bool           # Whether query uses placeholders
```

**Example: Concurrent Requests CTE**
```sql
WITH concurrent_counts AS (
    SELECT
        request_arrival_time,
        project_id,
        COUNT(*) as concurrent_count
    FROM ModelInferenceDetails
    WHERE request_arrival_time >= '{from_date}'
      AND request_arrival_time <= '{to_date}'
      {filters}
    GROUP BY request_arrival_time, project_id
    HAVING COUNT(*) > 1
)
```

### 3. TopK Filtering

TopK allows limiting results to the top N entities by a metric:

```python
# TopK CTE generation
topk_entities AS (
    SELECT project_id
    FROM (
        SELECT project_id, SUM(request_count) as rank_value
        FROM ...
        GROUP BY project_id
    )
    ORDER BY rank_value DESC
    LIMIT 10
)
```

### 4. Time Bucket Alignment

Custom intervals align to the specified `from_date`:

```python
# Standard interval (uses ClickHouse functions)
toDate(request_arrival_time)  # Daily

# Custom interval (aligns to from_date)
toDateTime(
    toUnixTimestamp('2024-01-01 00:00:00') +
    floor((toUnixTimestamp(request_arrival_time) -
           toUnixTimestamp('2024-01-01 00:00:00')) / 604800) * 604800
)  # 7-day intervals starting from 2024-01-01
```

### 5. Performance Profiling

The system includes comprehensive performance profiling:

```python
@profile_async("query_execution")
async def execute_query(self, query: str):
    # Automatically tracks execution time
    # Records in performance metrics
    # Logs in debug mode
```

### 6. Result Structure

The API returns a nested structure optimized for time series data:

```json
{
  "object": "observability_metrics",
  "items": [
    {
      "time_period": "2024-01-01T00:00:00",
      "items": [
        {
          "model_id": "uuid",
          "project_id": "uuid",
          "endpoint_id": "uuid",
          "data": {
            "request_count": {
              "count": 1000,
              "rate": 41.67,
              "delta": 100,
              "delta_percent": 11.11
            }
          }
        }
      ]
    }
  ]
}
```

## Data Flow

### Analytics Query Flow

1. **Request Reception**: API validates request parameters
2. **Query Building**:
   - Select appropriate metric definitions
   - Build CTEs if needed
   - Apply filters and grouping
   - Generate time buckets
3. **Query Execution**:
   - Check cache (if enabled)
   - Execute on ClickHouse
   - Stream results if large
4. **Post Processing**:
   - Detect gap-filled rows
   - Calculate deltas
   - Format response
5. **Response**: Return structured JSON

### Metrics Ingestion Flow (via Dapr)

1. **Event Publishing**: External services publish to Dapr pub/sub topic
2. **Event Reception**: Dapr runtime delivers CloudEvents to `/add` endpoint
3. **Bulk Processing**: Aggregate events into batches
4. **Validation**: Check required fields and formats
5. **Deduplication**: Query existing inference_ids
6. **Batch Insert**: Use ClickHouse batch insert
7. **Response**: Return success/failure counts

## Configuration

### Environment Variables

```bash
# ClickHouse Configuration
PSQL_HOST=localhost
PSQL_PORT=9000
PSQL_DB_NAME=tensorzero
PSQL_USER=default
PSQL_PASSWORD=password

# Application Settings
APP_PORT=8000
DEBUG=false
LOG_LEVEL=INFO

# Performance Settings
CLICKHOUSE_ENABLE_QUERY_CACHE=true
CLICKHOUSE_ENABLE_CONNECTION_WARMUP=true
ENABLE_PERFORMANCE_PROFILING=true

# Dapr Configuration (used by BudMicroframe)
DAPR_HTTP_PORT=3500
DAPR_GRPC_PORT=50001
```

### Connection Pool Settings

```python
@dataclass
class ClickHouseConfig:
    pool_min_size: int = 2
    pool_max_size: int = 20
    query_timeout: int = 300
    connect_timeout: int = 30
    max_concurrent_queries: int = 10
```

## Error Handling

The system implements comprehensive error handling:

1. **Database Errors**: Connection failures, query timeouts
2. **Validation Errors**: Invalid parameters, data format issues
3. **Business Logic Errors**: Invalid metric combinations
4. **Performance Limits**: Query size limits, timeout protection
5. **Event Processing Errors**: Malformed CloudEvents, pub/sub failures

## Security Considerations

1. **SQL Injection Prevention**: Parameterized queries
2. **Input Validation**: Pydantic models for all inputs
3. **Rate Limiting**: Configurable query limits
4. **Authentication**: Supports standard FastAPI auth middleware
5. **Data Privacy**: No PII in metrics data
6. **Event Security**: CloudEvents signature validation (when enabled)
