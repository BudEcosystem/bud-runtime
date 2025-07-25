# Examples

This directory contains example scripts demonstrating how to use the Bud Serve Metrics system.

## Available Examples

### 1. analytics_examples.py
Demonstrates using the Analytics API endpoint with various query patterns:
- Simple daily metrics
- Multiple metrics with grouping
- Custom time intervals
- Filtered queries
- Performance metrics (latency, TTFT, throughput)
- Cache metrics
- Token usage analysis
- Error pattern analysis

### 2. query_builder_examples.py
Shows direct usage of the QueryBuilder class:
- Basic query construction
- Complex filtering and grouping
- TopK queries
- CTE usage (concurrent requests)
- Custom interval alignment
- All available metrics

## Running the Examples

### Prerequisites
1. Ensure the application is running:
   ```bash
   docker-compose -f deploy/docker-compose-dev.yaml up -d
   ```

2. Seed some test data:
   ```bash
   python scripts/seed_observability_metrics.py --records 10000 --days 30
   ```

### Running Analytics Examples
```bash
# Activate virtual environment
source .venv/bin/activate

# Run the examples
python examples/analytics_examples.py
```

### Running QueryBuilder Examples
```bash
# These examples only show generated SQL, no API calls needed
python examples/query_builder_examples.py
```

## Key Concepts Demonstrated

### Time Series Analysis
- Standard intervals (hourly, daily, weekly)
- Custom intervals with from_date alignment
- Gap filling for missing data points

### Filtering and Grouping
- Filter by project, model, or endpoint
- Group results by one or more dimensions
- TopK to limit results to top entities

### Metrics Types
- **Count Metrics**: request_count, success_request, failure_request
- **Token Metrics**: input_token, output_token
- **Performance Metrics**: latency, ttft, throughput, queuing_time
- **Advanced Metrics**: concurrent_requests, cache performance

### Delta Analysis
- Period-over-period changes
- Percentage change calculations
- Trend identification

## Example Output

### Simple Daily Metrics
```json
{
  "object": "observability_metrics",
  "items": [
    {
      "time_period": "2024-01-07T00:00:00",
      "items": [
        {
          "data": {
            "request_count": {
              "count": 15234,
              "rate": 176.3
            }
          }
        }
      ]
    }
  ]
}
```

### Grouped Metrics with Deltas
```json
{
  "time_period": "2024-01-07T00:00:00",
  "items": [
    {
      "model_id": "uuid-here",
      "data": {
        "request_count": {
          "count": 5000,
          "delta": 500,
          "delta_percent": 11.1
        },
        "latency": {
          "avg_latency_ms": 250.5,
          "latency_p95": 450,
          "latency_p99": 650
        }
      }
    }
  ]
}
```

## Custom Intervals

The system supports custom time intervals that align to your specified start date:

```python
# 7-day intervals starting from a specific Sunday
payload = {
    "from_date": "2024-01-07T00:00:00Z",  # Sunday
    "frequency_unit": "day",
    "frequency_interval": 7  # Creates 7-day buckets
}
```

This ensures buckets are:
- 2024-01-07 (Start)
- 2024-01-14 (+7 days)
- 2024-01-21 (+14 days)
- etc.

## Performance Tips

1. **Use TopK for high-cardinality grouping**: When grouping by model or endpoint with many unique values
2. **Appropriate time ranges**: Avoid querying years of data with hourly granularity
3. **Selective metrics**: Only request the metrics you need
4. **Caching**: Repeated identical queries will be served from cache

## Error Handling

The examples include basic error handling. In production, implement:
- Retry logic for transient failures
- Proper logging of errors
- Graceful degradation
- Rate limit handling