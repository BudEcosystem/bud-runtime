# Database Schema

## Overview

The application uses ClickHouse as its primary database for high-performance analytics on time-series data. The schema is optimized for:

- Fast aggregations across time periods
- Efficient filtering by project, model, and endpoint
- Low-latency concurrent query execution
- Automatic data partitioning and retention

## Tables

### ModelInferenceDetails

Primary table for inference metrics and request tracking.

```sql
CREATE TABLE ModelInferenceDetails
(
    inference_id UUID,
    request_ip Nullable(IPv4),
    project_id UUID,
    endpoint_id UUID,
    model_id UUID,
    cost Nullable(Float64),
    response_analysis Nullable(JSON),
    is_success Bool,
    request_arrival_time DateTime,
    request_forward_time DateTime,
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(request_arrival_time)
ORDER BY (project_id, model_id, endpoint_id, request_arrival_time, inference_id)
SETTINGS index_granularity = 8192;
```

#### Column Descriptions

| Column | Type | Description |
|--------|------|-------------|
| `inference_id` | UUID | Unique identifier for each inference request |
| `request_ip` | Nullable(IPv4) | Client IP address (optional) |
| `project_id` | UUID | Project identifier |
| `endpoint_id` | UUID | API endpoint identifier |
| `model_id` | UUID | ML model identifier |
| `cost` | Nullable(Float64) | Cost of the inference in dollars |
| `response_analysis` | Nullable(JSON) | Additional analysis metadata |
| `is_success` | Bool | Whether the inference succeeded |
| `request_arrival_time` | DateTime | When the request arrived at the system |
| `request_forward_time` | DateTime | When the request was forwarded to the model |
| `created_at` | DateTime | Database insertion timestamp |

#### Indexes

```sql
-- Primary key index (automatic)
-- ORDER BY (project_id, model_id, endpoint_id, request_arrival_time, inference_id)

-- Additional indexes for query optimization
ALTER TABLE ModelInferenceDetails 
ADD INDEX idx_project_timestamp (project_id, request_arrival_time) TYPE minmax GRANULARITY 1;

ALTER TABLE ModelInferenceDetails 
ADD INDEX idx_model_timestamp (model_id, request_arrival_time) TYPE minmax GRANULARITY 1;

ALTER TABLE ModelInferenceDetails 
ADD INDEX idx_endpoint_timestamp (endpoint_id, request_arrival_time) TYPE minmax GRANULARITY 1;

ALTER TABLE ModelInferenceDetails 
ADD INDEX idx_project_model_endpoint_timestamp 
    (project_id, model_id, endpoint_id, request_arrival_time) TYPE minmax GRANULARITY 1;
```

### ModelInference (Optional)

Extended inference data including model-specific metrics. This table is optional and only created when `--include-model-inference` flag is used during migration.

```sql
CREATE TABLE ModelInference
(
    id UUID,
    inference_id UUID,
    raw_request String,
    raw_response String,
    model_name LowCardinality(String),
    model_provider_name LowCardinality(String),
    input_tokens Nullable(UInt32),
    output_tokens Nullable(UInt32),
    response_time_ms Nullable(UInt32),
    ttft_ms Nullable(UInt32),
    timestamp DateTime MATERIALIZED UUIDv7ToDateTime(id),
    system Nullable(String),
    input_messages String,
    output String,
    cached Bool DEFAULT false,
    finish_reason Nullable(Enum8(
        'stop' = 1, 
        'length' = 2, 
        'tool_call' = 3, 
        'content_filter' = 4, 
        'unknown' = 5
    ))
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (model_name, timestamp, inference_id)
SETTINGS index_granularity = 8192;
```

#### Column Descriptions

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key (UUIDv7 for time ordering) |
| `inference_id` | UUID | Links to ModelInferenceDetails |
| `raw_request` | String | Original request payload |
| `raw_response` | String | Original response payload |
| `model_name` | LowCardinality(String) | Model identifier |
| `model_provider_name` | LowCardinality(String) | Provider (OpenAI, Anthropic, etc.) |
| `input_tokens` | Nullable(UInt32) | Number of input tokens |
| `output_tokens` | Nullable(UInt32) | Number of output tokens |
| `response_time_ms` | Nullable(UInt32) | Total response time |
| `ttft_ms` | Nullable(UInt32) | Time to first token |
| `timestamp` | DateTime | Extracted from UUIDv7 id |
| `system` | Nullable(String) | System prompt |
| `input_messages` | String | Input messages |
| `output` | String | Model output |
| `cached` | Bool | Whether response was cached |
| `finish_reason` | Nullable(Enum8) | Why generation stopped |

## Schema Design Principles

### 1. Partitioning Strategy

Tables are partitioned by month for efficient data management:

```sql
PARTITION BY toYYYYMM(request_arrival_time)
```

Benefits:
- Fast data deletion (drop entire partitions)
- Improved query performance (partition pruning)
- Easy data archival and retention

### 2. Sort Order Optimization

The ORDER BY clause defines the primary index:

```sql
ORDER BY (project_id, model_id, endpoint_id, request_arrival_time, inference_id)
```

This order optimizes for:
- Filtering by project/model/endpoint
- Time-range queries
- Unique constraint on inference_id

### 3. Data Types

#### UUIDs
- Used for all identifiers (project, model, endpoint, inference)
- Ensures global uniqueness
- Supports distributed systems

#### LowCardinality
- Used for string columns with limited unique values
- Reduces storage and improves compression
- Example: model names, provider names

#### Nullable Types
- Used for optional fields
- Allows proper NULL handling in aggregations

#### JSON Type
- Used for flexible metadata storage
- Supports dynamic schema evolution
- Queryable with JSONExtract functions

### 4. Materialized Columns

```sql
timestamp DateTime MATERIALIZED UUIDv7ToDateTime(id)
```

- Computed automatically from UUIDv7
- No storage overhead
- Ensures time consistency

## Query Patterns

### 1. Time-Series Aggregation

```sql
SELECT
    toDate(request_arrival_time) AS date,
    COUNT(*) AS request_count,
    AVG(cost) AS avg_cost
FROM ModelInferenceDetails
WHERE request_arrival_time >= '2024-01-01'
  AND request_arrival_time < '2024-02-01'
  AND project_id = 'uuid-here'
GROUP BY date
ORDER BY date
```

### 2. Concurrent Request Analysis

```sql
SELECT
    request_arrival_time,
    COUNT(*) AS concurrent_count
FROM ModelInferenceDetails
WHERE request_arrival_time >= '2024-01-01'
  AND project_id = 'uuid-here'
GROUP BY request_arrival_time
HAVING concurrent_count > 1
```

### 3. Success Rate Calculation

```sql
SELECT
    model_id,
    COUNT(*) AS total_requests,
    SUM(is_success) AS successful_requests,
    AVG(is_success) * 100 AS success_rate
FROM ModelInferenceDetails
WHERE request_arrival_time >= today()
GROUP BY model_id
```

### 4. Cost Analysis

```sql
SELECT
    toStartOfHour(request_arrival_time) AS hour,
    project_id,
    SUM(cost) AS total_cost,
    COUNT(*) AS request_count,
    AVG(cost) AS avg_cost_per_request
FROM ModelInferenceDetails
WHERE cost IS NOT NULL
GROUP BY hour, project_id
ORDER BY hour DESC
```

### 5. Response Analysis Query

```sql
SELECT
    JSONExtractString(response_analysis, 'sentiment') AS sentiment,
    COUNT(*) AS count,
    AVG(JSONExtractFloat(response_analysis, 'confidence')) AS avg_confidence
FROM ModelInferenceDetails
WHERE response_analysis IS NOT NULL
GROUP BY sentiment
```

## Performance Considerations

### 1. Index Granularity

```sql
SETTINGS index_granularity = 8192
```

- Default granularity works well for most cases
- Adjust for very high or low cardinality data

### 2. Query Optimization

#### Use Partition Pruning
```sql
-- Good: Uses partition
WHERE request_arrival_time >= '2024-01-01'

-- Bad: Scans all partitions  
WHERE toYear(request_arrival_time) = 2024
```

#### Leverage Sort Order
```sql
-- Good: Matches ORDER BY
WHERE project_id = 'uuid' AND model_id = 'uuid'

-- Less optimal: Skips first columns
WHERE endpoint_id = 'uuid'
```

### 3. Aggregation Performance

#### Pre-filter When Possible
```sql
-- Efficient
WITH filtered_data AS (
    SELECT * FROM ModelInferenceDetails
    WHERE project_id = 'uuid'
      AND request_arrival_time >= today()
)
SELECT ... FROM filtered_data
```

#### Use Approximate Functions
```sql
-- Faster for large datasets
SELECT 
    quantile(0.99)(cost) AS p99_cost,  -- Exact
    quantileTDigest(0.99)(cost) AS p99_cost_approx  -- Approximate but faster
```

## Data Retention

### Manual Partition Management

```sql
-- View partitions
SELECT 
    partition,
    name,
    rows,
    bytes_on_disk,
    modification_time
FROM system.parts
WHERE table = 'ModelInferenceDetails'
  AND active
ORDER BY partition DESC;

-- Drop old partitions
ALTER TABLE ModelInferenceDetails 
DROP PARTITION '202301';  -- Drops January 2023 data
```

### Automated Retention (TTL)

```sql
-- Add TTL to automatically delete old data
ALTER TABLE ModelInferenceDetails 
MODIFY TTL request_arrival_time + INTERVAL 6 MONTH;
```

## Migration Management

See the [Migration Guide](./MIGRATION.md) for detailed instructions on running migrations.

Key commands:
```bash
# Basic migration with retry
python scripts/migrate_clickhouse.py --max-retries 30 --retry-delay 2

# Include optional ModelInference table
python scripts/migrate_clickhouse.py --include-model-inference
```

### Schema Evolution

#### Adding Columns
```sql
ALTER TABLE ModelInferenceDetails 
ADD COLUMN new_field String DEFAULT '' AFTER cost;
```

#### Adding Indexes
```sql
ALTER TABLE ModelInferenceDetails 
ADD INDEX idx_new_field (new_field) TYPE bloom_filter GRANULARITY 1;
```

#### Changing Data Types
```sql
-- Create new column
ALTER TABLE ModelInferenceDetails 
ADD COLUMN cost_new Decimal(10, 4);

-- Migrate data
ALTER TABLE ModelInferenceDetails 
UPDATE cost_new = toDecimal64(cost, 4) WHERE 1;

-- Swap columns
ALTER TABLE ModelInferenceDetails 
RENAME COLUMN cost TO cost_old;

ALTER TABLE ModelInferenceDetails 
RENAME COLUMN cost_new TO cost;

-- Drop old column
ALTER TABLE ModelInferenceDetails 
DROP COLUMN cost_old;
```

## Monitoring

### Table Statistics

```sql
SELECT
    table,
    formatReadableSize(sum(bytes)) AS size,
    sum(rows) AS rows,
    max(modification_time) AS latest_modification
FROM system.parts
WHERE active
  AND database = currentDatabase()
GROUP BY table;
```

### Query Performance

```sql
SELECT
    query,
    query_duration_ms,
    read_rows,
    formatReadableSize(read_bytes) AS read_bytes,
    formatReadableSize(memory_usage) AS memory_usage
FROM system.query_log
WHERE type = 'QueryFinish'
  AND query_duration_ms > 1000
ORDER BY query_start_time DESC
LIMIT 10;
```