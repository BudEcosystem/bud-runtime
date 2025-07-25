# Query Building Guide

## Overview

The QueryBuilder is the core component responsible for constructing optimized ClickHouse queries. It supports dynamic metric selection, filtering, grouping, and complex time-series operations.

## Architecture

```
QueryBuilder
    ├── MetricDefinitions
    │   ├── Basic Metrics (count, sum, avg)
    │   ├── Computed Metrics (rates, percentiles)
    │   └── Complex Metrics (concurrent requests)
    ├── CTEDefinitions
    │   ├── Static CTEs
    │   └── Template CTEs (with placeholders)
    ├── TimeSeriesHelper
    │   ├── Standard Intervals
    │   └── Custom Aligned Intervals
    └── Filter & Group Management
```

## Core Concepts

### 1. Metric Definitions

Each metric is defined with:

```python
@dataclass
class MetricDefinition:
    metrics_name: str              # Metric identifier
    required_tables: list[str]     # Tables needed for this metric
    select_clause: str             # SQL SELECT expression
    select_alias: str              # Output column name
    cte_definition: Optional[CTEDefinition] = None  # Associated CTE
    topk_cte_query: Optional[str] = None            # Custom TopK query
    topk_sort_order: Optional[Literal["ASC", "DESC"]] = None
```

#### Example: Request Count Metric

```python
def _get_request_count_metrics_definitions(self, ...):
    return [
        MetricDefinition(
            metrics_name="request_count",
            required_tables=["ModelInferenceDetails"],
            select_clause="COUNT(mid.inference_id) AS request_count",
            select_alias="request_count"
        )
    ]
```

### 2. CTE (Common Table Expression) System

CTEs allow complex calculations to be defined once and reused:

```python
@dataclass
class CTEDefinition:
    name: str                  # CTE name
    query: str                 # SQL query
    base_tables: list[str]     # Underlying tables
    is_template: bool = False  # Uses placeholders?
```

#### Static CTE Example

```sql
WITH model_stats AS (
    SELECT 
        model_id,
        COUNT(*) as total_requests,
        AVG(response_time_ms) as avg_latency
    FROM ModelInference
    WHERE timestamp >= '2024-01-01'
    GROUP BY model_id
)
```

#### Template CTE Example

```python
cte_template = """
    SELECT 
        {group_columns},
        COUNT(*) as concurrent_count
    FROM ModelInferenceDetails
    WHERE request_arrival_time >= '{from_date}' 
      AND request_arrival_time <= '{to_date}'
      {filters}
    GROUP BY {group_columns}
    HAVING COUNT(*) > 1
"""
```

### 3. Time Bucketing

The system supports two types of time bucketing:

#### Standard Intervals
Uses ClickHouse's built-in functions:

```python
# Daily buckets
toDate(request_arrival_time)

# Weekly buckets  
toStartOfWeek(request_arrival_time)

# Monthly buckets
toStartOfMonth(request_arrival_time)
```

#### Custom Aligned Intervals
Aligns to a specific start date:

```python
# 7-day intervals starting from 2024-01-01
toDateTime(
    toUnixTimestamp('2024-01-01 00:00:00') + 
    floor((toUnixTimestamp(request_arrival_time) - 
           toUnixTimestamp('2024-01-01 00:00:00')) / 604800) * 604800
)
```

## Adding a New Metric

### Step 1: Define the Metric Type

Add to the `metric_type` dictionary in `QueryBuilder.__init__`:

```python
self.metric_type = {
    # ... existing metrics ...
    "my_new_metric": self._get_my_new_metric_definitions,
}
```

### Step 2: Create Metric Definition Method

```python
def _get_my_new_metric_definitions(
    self,
    time_period_bin_alias: str,
    incl_delta: bool = False,
    group_by_fields: Optional[list[str]] = None,
    filters: Optional[dict[str, Union[list[UUID], UUID]]] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
) -> list[MetricDefinition]:
    
    # Define the primary metric
    metric = MetricDefinition(
        metrics_name="my_new_metric",
        required_tables=["ModelInferenceDetails"],
        select_clause="AVG(mid.custom_field) AS avg_custom",
        select_alias="avg_custom",
        topk_sort_order="DESC"  # Higher is better
    )
    
    # Add delta metrics if requested
    metric_delta = []
    if incl_delta:
        metric_delta = self._get_metrics_trend_definitions(
            "avg_custom", time_period_bin_alias, group_by_fields
        )
    
    return [metric, *metric_delta]
```

### Step 3: Update API Schema (if needed)

Add to the metrics enum in the API schema:

```python
class MetricType(str, Enum):
    # ... existing metrics ...
    MY_NEW_METRIC = "my_new_metric"
```

## Complex Metric Example: Concurrent Requests

The concurrent requests metric demonstrates advanced features:

```python
def _get_concurrent_requests_metrics_definitions(self, ...):
    # Build dynamic GROUP BY clause
    group_by_columns = ["request_arrival_time"]
    if group_by_fields:
        for field in group_by_fields:
            col_name = field.split(".")[-1]
            group_by_columns.append(col_name)
    
    # Create template CTE
    cte_template = f"""
        SELECT 
            {', '.join(group_by_columns)},
            COUNT(*) as concurrent_count
        FROM ModelInferenceDetails
        WHERE request_arrival_time >= '{{from_date}}' 
          AND request_arrival_time <= '{{to_date}}'
          {{filters}}
        GROUP BY {', '.join(group_by_columns)}
        HAVING COUNT(*) > 1
    """
    
    cte_def = CTEDefinition(
        name="concurrent_counts",
        query=cte_template,
        base_tables=["ModelInferenceDetails"],
        is_template=True
    )
    
    # Define the metric using the CTE
    metric = MetricDefinition(
        metrics_name="concurrent_requests",
        required_tables=["ModelInferenceDetails", "concurrent_counts"],
        select_clause="COALESCE(MAX(cc.concurrent_count), 0) AS max_concurrent",
        select_alias="max_concurrent_requests",
        cte_definition=cte_def
    )
    
    return [metric]
```

## Query Building Process

### 1. Basic Query Structure

```sql
WITH cte1 AS (...), cte2 AS (...)
SELECT
    time_bucket,
    group_field1,
    group_field2,
    metric1,
    metric2
FROM table1
JOIN table2 ON condition
WHERE filters
GROUP BY time_bucket, group_field1, group_field2
ORDER BY time_bucket DESC
WITH FILL STEP INTERVAL 1 DAY
```

### 2. Filter Building

Filters are constructed with proper escaping:

```python
def _get_filter_conditions(self, ...):
    conditions = []
    
    # Date filters
    conditions.append(f"request_arrival_time >= '{from_date}'")
    conditions.append(f"request_arrival_time <= '{to_date}'")
    
    # Entity filters
    if filters:
        for key, value in filters.items():
            if isinstance(value, list):
                conditions.append(
                    f"{column} IN ({','.join([f\"'{v}'\" for v in value])})"
                )
            else:
                conditions.append(f"{column} = '{value}'")
    
    return conditions
```

### 3. TopK Implementation

TopK filtering limits results to top entities:

```python
# Generate TopK CTE
topk_entities AS (
    SELECT project_id
    FROM (
        SELECT 
            project_id, 
            SUM(request_count) as rank_value
        FROM ModelInferenceDetails
        WHERE [conditions]
        GROUP BY project_id
    )
    ORDER BY rank_value DESC
    LIMIT 10
)

# Add to main query
WHERE project_id IN (SELECT project_id FROM topk_entities)
```

## Performance Optimization Tips

### 1. Index Usage

Ensure queries use appropriate indexes:

```sql
-- Good: Uses index on (project_id, request_arrival_time)
WHERE project_id = 'uuid' AND request_arrival_time >= '2024-01-01'

-- Bad: Full table scan
WHERE JSON_VALUE(response_analysis, '$.sentiment') = 'positive'
```

### 2. CTE vs Subqueries

CTEs are preferred for:
- Reusable calculations
- Complex aggregations
- Improving readability

### 3. Partitioning

Queries automatically benefit from ClickHouse partitioning:

```sql
-- Partition pruning happens automatically
PARTITION BY toYYYYMM(request_arrival_time)
```

### 4. Aggregation Functions

Use appropriate aggregation functions:

```python
# Fast: Native aggregations
"COUNT(*)", "SUM(field)", "AVG(field)"

# Slower: Complex calculations
"COUNT(DISTINCT field)", "quantile(0.99)(field)"
```

## Debugging Queries

### 1. Enable Debug Mode

```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
```

### 2. Log Generated Queries

```python
logger.debug(f"Generated query: {query}")
```

### 3. Explain Query Plan

```sql
EXPLAIN SYNTAX
SELECT ...

EXPLAIN PLAN
SELECT ...
```

### 4. Profile Query Performance

```sql
SET log_queries = 1;
SET log_query_threads = 1;

-- Run query
SELECT ...

-- Check system.query_log
SELECT 
    query,
    query_duration_ms,
    read_rows,
    read_bytes,
    memory_usage
FROM system.query_log
WHERE query_id = 'your-query-id'
```

## Common Patterns

### 1. Period-over-Period Comparison

```python
# Use lagInFrame for previous period
lagInFrame(metric, 1, metric) OVER (
    PARTITION BY group_fields 
    ORDER BY time_bucket ASC
) AS previous_metric
```

### 2. Rate Calculation

```python
# Requests per second
COUNT(*) / (3600.0) AS requests_per_second  # For hourly buckets
```

### 3. Null Handling

```python
# Handle nulls in calculations
COALESCE(value, 0) AS value
NULLIF(denominator, 0)  # Prevent division by zero
```

### 4. JSON Field Access

```python
# Access JSON fields safely
JSONExtractString(response_analysis, 'sentiment') AS sentiment
```

## Testing Queries

### 1. Unit Test Metric Definitions

```python
def test_request_count_metric():
    qb = QueryBuilder()
    metrics = qb._get_request_count_metrics_definitions(
        "time_bucket",
        incl_delta=True,
        group_by_fields=["mid.project_id"]
    )
    
    assert len(metrics) == 4  # Base + 3 delta metrics
    assert metrics[0].select_alias == "request_count"
```

### 2. Integration Test Full Queries

```python
async def test_analytics_query():
    query, fields = query_builder.build_query(
        metrics=["request_count"],
        from_date=datetime(2024, 1, 1),
        to_date=datetime(2024, 1, 31),
        frequency_unit="day",
        group_by=["project"]
    )
    
    # Verify query structure
    assert "WITH" in query or "SELECT" in query
    assert "GROUP BY" in query
    assert "time_bucket" in fields
```

### 3. Performance Test

```python
async def test_query_performance():
    start = time.time()
    
    result = await client.execute_query(query)
    
    duration = time.time() - start
    assert duration < 1.0  # Should complete in under 1 second
    assert len(result) > 0
```