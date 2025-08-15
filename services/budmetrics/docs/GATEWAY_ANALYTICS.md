# BudMetrics Gateway Analytics Module

## Overview

The Gateway Analytics module in BudMetrics provides comprehensive API endpoints for querying and analyzing gateway request data stored in ClickHouse. It serves as the analytics backend for understanding API usage patterns, performance metrics, and security events.

## Architecture

```
BudAdmin Dashboard
        ↓
    BudApp (Auth & Enrichment)
        ↓
    BudMetrics Gateway Analytics
        ↓
    ClickHouse Database
```

## API Endpoints

### 1. Query Gateway Analytics

**POST** `/gateway/analytics`

Query comprehensive analytics data with flexible filtering and aggregation options.

#### Request Body

```python
{
    "project_ids": ["uuid1", "uuid2"],        # Filter by projects
    "model_ids": ["uuid3"],                   # Filter by models
    "endpoint_ids": ["uuid4"],                # Filter by endpoints
    "start_time": "2024-01-01T00:00:00Z",    # Start time (required)
    "end_time": "2024-01-31T23:59:59Z",      # End time (required)
    "time_bucket": "1h",                      # Aggregation: 1m, 5m, 1h, 1d
    "metrics": [                               # Metrics to calculate
        "total_requests",
        "error_rate",
        "avg_response_time",
        "p95_response_time",
        "p99_response_time",
        "total_tokens",
        "unique_users"
    ],
    "group_by": ["project_id", "model_id"],   # Grouping dimensions
    "filters": {                               # Additional filters
        "status_code": 200,
        "country_code": "US"
    }
}
```

#### Response

```python
{
    "success": true,
    "data": {
        "time_series": [
            {
                "timestamp": "2024-01-01T00:00:00Z",
                "metrics": {
                    "total_requests": 1000,
                    "error_rate": 0.02,
                    "avg_response_time": 250.5
                },
                "groups": {
                    "project_id": "uuid1",
                    "model_id": "uuid3"
                }
            }
        ],
        "summary": {
            "total_requests": 50000,
            "total_errors": 1000,
            "avg_response_time": 245.3
        }
    }
}
```

### 2. Geographical Statistics

**GET** `/gateway/geographical-stats`

Get geographic distribution of API requests.

#### Query Parameters

- `start_time`: ISO 8601 timestamp (default: 7 days ago)
- `end_time`: ISO 8601 timestamp (default: now)
- `project_ids`: Comma-separated UUIDs

#### Response

```python
{
    "success": true,
    "data": {
        "countries": [
            {
                "country_code": "US",
                "country_name": "United States",
                "request_count": 10000,
                "error_count": 200,
                "avg_response_time": 250.5,
                "total_tokens": 500000
            }
        ],
        "regions": [...],
        "cities": [...],
        "summary": {
            "total_countries": 45,
            "total_requests": 50000
        }
    }
}
```

### 3. Blocking Statistics

**GET** `/gateway/blocking-stats`

Analyze blocked requests and security events.

#### Response

```python
{
    "success": true,
    "data": {
        "blocked_ips": [
            {
                "ip_address": "192.168.1.1",
                "block_count": 100,
                "reasons": ["rate_limit", "suspicious_activity"],
                "first_blocked": "2024-01-01T00:00:00Z",
                "last_blocked": "2024-01-01T01:00:00Z"
            }
        ],
        "blocking_rules": [
            {
                "rule_id": "uuid",
                "rule_type": "country_blocking",
                "match_count": 500,
                "effectiveness": 0.95
            }
        ],
        "summary": {
            "total_blocked": 1500,
            "block_rate": 0.03
        }
    }
}
```

### 4. Top Routes Analysis

**GET** `/gateway/top-routes`

Identify most accessed API routes and their performance.

#### Query Parameters

- `limit`: Number of routes (1-100, default: 10)
- `order_by`: Sorting field (requests, errors, avg_time)

#### Response

```python
{
    "success": true,
    "data": {
        "routes": [
            {
                "path": "/api/v1/inference",
                "method": "POST",
                "request_count": 10000,
                "error_count": 100,
                "error_rate": 0.01,
                "avg_response_time": 250,
                "p95_response_time": 500,
                "p99_response_time": 1000,
                "total_tokens": 500000
            }
        ]
    }
}
```

### 5. Client Analytics

**GET** `/gateway/client-analytics`

Analyze usage patterns by client/user.

#### Response

```python
{
    "success": true,
    "data": {
        "clients": [
            {
                "client_id": "api_key_123",
                "client_ip": "10.0.0.1",
                "request_count": 5000,
                "error_count": 50,
                "avg_response_time": 300,
                "total_tokens": 250000,
                "total_cost": 125.50,
                "last_activity": "2024-01-31T23:59:59Z",
                "user_agent": "Python/3.9 requests/2.28.0",
                "device_type": "desktop",
                "browser": "Python Requests",
                "os": "Linux"
            }
        ]
    }
}
```

## Service Implementation

### Directory Structure

```
budmetrics/gateway_analytics/
├── __init__.py
├── models.py         # SQLAlchemy models
├── schemas.py        # Pydantic schemas
├── services.py       # Business logic
└── routes.py         # FastAPI endpoints
```

### Key Components

#### 1. ClickHouse Query Builder

Located in `services.py`:

```python
class GatewayAnalyticsService:
    def __init__(self, clickhouse_client: ClickHouseClient):
        self.client = clickhouse_client

    def build_analytics_query(
        self,
        filters: Dict,
        metrics: List[str],
        group_by: List[str],
        time_bucket: str
    ) -> str:
        """Build optimized ClickHouse query."""
        # Dynamic query construction
        # Parameterized to prevent SQL injection
        # Optimized for time-series data
```

#### 2. Data Aggregation Pipeline

```python
class MetricsAggregator:
    """Aggregate metrics across multiple dimensions."""

    supported_metrics = {
        "total_requests": "COUNT(*)",
        "error_rate": "AVG(IF(status_code >= 400, 1, 0))",
        "avg_response_time": "AVG(response_time_ms)",
        "p95_response_time": "quantile(0.95)(response_time_ms)",
        "p99_response_time": "quantile(0.99)(response_time_ms)",
        "total_tokens": "SUM(total_tokens)",
        "unique_users": "COUNT(DISTINCT client_id)"
    }
```

#### 3. Geographic Analysis

```python
class GeoAnalyzer:
    """Analyze geographic distribution of requests."""

    def aggregate_by_location(
        self,
        data: List[Dict],
        level: str  # country, region, city
    ) -> Dict:
        """Aggregate metrics by geographic level."""
        # Group by location
        # Calculate per-location metrics
        # Handle missing geo data gracefully
```

## Configuration

### Environment Variables

```bash
# ClickHouse Configuration
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_DATABASE=budmetrics
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
CLICKHOUSE_POOL_SIZE=10
CLICKHOUSE_POOL_TIMEOUT=30

# Query Configuration
MAX_QUERY_TIME_RANGE=90  # days
DEFAULT_TIME_BUCKET=1h
MAX_RESULT_SIZE=10000
QUERY_TIMEOUT=30  # seconds

# Caching
REDIS_URL=redis://localhost:6379
CACHE_TTL=300  # seconds
CACHE_ENABLED=true
```

### ClickHouse Tables

```sql
-- Main analytics table
CREATE TABLE gateway_analytics (
    request_id UUID,
    timestamp DateTime64(3),
    project_id UUID,
    model_id UUID,
    endpoint_id UUID,
    -- ... (see full schema in budgateway docs)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (project_id, timestamp);

-- Materialized views for performance
CREATE MATERIALIZED VIEW gateway_analytics_hourly
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(hour)
ORDER BY (project_id, model_id, hour)
AS SELECT
    toStartOfHour(timestamp) as hour,
    project_id,
    model_id,
    count() as request_count,
    avg(response_time_ms) as avg_response_time,
    sum(total_tokens) as total_tokens
FROM gateway_analytics
GROUP BY hour, project_id, model_id;
```

## Performance Optimization

### 1. Query Optimization

- **Use materialized views** for common aggregations
- **Partition by time** for efficient time-range queries
- **Create appropriate indexes** for filter columns
- **Limit result size** to prevent memory issues

### 2. Caching Strategy

```python
@cache(ttl=300)
async def get_geographical_stats(
    start_time: datetime,
    end_time: datetime,
    project_ids: List[UUID]
) -> Dict:
    """Cache frequently accessed geographic data."""
    cache_key = f"geo_stats:{hash(project_ids)}:{start_time}:{end_time}"
    # Check cache first
    # Query ClickHouse if cache miss
    # Update cache with results
```

### 3. Batch Processing

```python
async def process_analytics_batch(
    records: List[Dict],
    batch_size: int = 1000
) -> None:
    """Process records in batches for efficiency."""
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        await clickhouse.insert_batch(batch)
```

## Monitoring and Debugging

### Key Metrics

Monitor these metrics for service health:

```python
# Prometheus metrics
gateway_analytics_query_duration = Histogram(
    'gateway_analytics_query_duration_seconds',
    'Time spent executing ClickHouse queries'
)

gateway_analytics_query_errors = Counter(
    'gateway_analytics_query_errors_total',
    'Total number of query errors'
)

gateway_analytics_cache_hits = Counter(
    'gateway_analytics_cache_hits_total',
    'Number of cache hits'
)
```

### Logging

```python
import structlog

logger = structlog.get_logger(__name__)

# Log query performance
logger.info(
    "analytics_query_executed",
    query_time=query_duration,
    result_count=len(results),
    filters=filters
)

# Log errors with context
logger.error(
    "clickhouse_query_failed",
    error=str(e),
    query=query,
    traceback=traceback.format_exc()
)
```

### Debug Mode

Enable debug mode for detailed logging:

```python
# In settings.py
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
LOG_QUERIES = os.getenv("LOG_QUERIES", "false").lower() == "true"

if DEBUG_MODE:
    # Log all queries
    # Include query execution plans
    # Enable ClickHouse query profiling
```

## Error Handling

### Common Errors and Solutions

1. **ClickHouse Connection Error**:
   ```python
   try:
       result = await clickhouse.execute(query)
   except ClickHouseException as e:
       if "Connection refused" in str(e):
           # Try backup ClickHouse instance
           result = await backup_clickhouse.execute(query)
       else:
           raise
   ```

2. **Query Timeout**:
   ```python
   @timeout(30)  # 30 second timeout
   async def execute_analytics_query(query: str):
       # Automatically cancelled if exceeds timeout
       return await clickhouse.execute(query)
   ```

3. **Memory Limit Exceeded**:
   ```python
   # Use streaming for large results
   async for batch in clickhouse.stream_query(query, batch_size=1000):
       process_batch(batch)
   ```

## Testing

### Unit Tests

```python
# tests/test_gateway_analytics.py
import pytest
from unittest.mock import Mock, patch

@pytest.mark.asyncio
async def test_analytics_query():
    """Test analytics query building."""
    service = GatewayAnalyticsService(Mock())
    query = service.build_analytics_query(
        filters={"project_id": "uuid"},
        metrics=["total_requests"],
        group_by=["model_id"],
        time_bucket="1h"
    )
    assert "COUNT(*)" in query
    assert "GROUP BY" in query
```

### Integration Tests

```python
@pytest.mark.integration
async def test_geographical_stats_endpoint():
    """Test geographical stats API endpoint."""
    async with AsyncClient(app=app) as client:
        response = await client.get(
            "/gateway/geographical-stats",
            params={"start_time": "2024-01-01T00:00:00Z"}
        )
        assert response.status_code == 200
        assert "countries" in response.json()["data"]
```

### Load Testing

```bash
# Using locust for load testing
locust -f tests/load_test.py --host=http://localhost:8000 --users=100 --spawn-rate=10
```

## Security Considerations

1. **SQL Injection Prevention**:
   - Use parameterized queries
   - Validate all input parameters
   - Escape special characters

2. **Access Control**:
   - Verify project ownership
   - Filter results by user permissions
   - Audit all queries

3. **Data Privacy**:
   - Anonymize IP addresses if required
   - Respect data retention policies
   - Implement GDPR compliance

## Troubleshooting Guide

### Performance Issues

1. **Slow Queries**:
   - Check ClickHouse query logs
   - Analyze query execution plan
   - Consider adding materialized views

2. **High Memory Usage**:
   - Reduce batch sizes
   - Implement pagination
   - Use streaming for large results

3. **Cache Misses**:
   - Increase cache TTL for stable data
   - Implement cache warming
   - Use distributed caching with Redis

### Data Issues

1. **Missing Data**:
   - Verify gateway analytics middleware is enabled
   - Check ClickHouse replication lag
   - Ensure proper time zone handling

2. **Incorrect Aggregations**:
   - Validate time bucket calculations
   - Check for NULL values in aggregations
   - Verify group by logic
