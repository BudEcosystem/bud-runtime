# Authentication Metadata Tracking

## Overview

This feature adds authentication metadata tracking to the API logging system by capturing and storing `api_key_id`, `user_id`, and `api_key_project_id` for each API request. This enables better usage analytics, cost attribution, and security auditing.

## Architecture

The metadata flows through the system as follows:

1. **Budapp** stores API key metadata in Redis when credentials are created/updated
2. **Budgateway** extracts metadata from Redis during authentication
3. **Budmetrics** stores metadata in ClickHouse for analytics

## Implementation Details

### Redis Data Structure

When budapp updates the proxy cache, it includes a `__metadata__` field alongside model entries:

```json
{
    "model_name_1": {
        "endpoint_id": "uuid",
        "model_id": "uuid",
        "project_id": "uuid"
    },
    "model_name_2": {
        "endpoint_id": "uuid",
        "model_id": "uuid",
        "project_id": "uuid"
    },
    "__metadata__": {
        "api_key_id": "uuid",
        "user_id": "uuid",
        "api_key_project_id": "uuid"
    }
}
```

### ClickHouse Schema

The `ModelInferenceDetails` table has been extended with three new columns:

```sql
ALTER TABLE ModelInferenceDetails
ADD COLUMN IF NOT EXISTS api_key_id UUID,
ADD COLUMN IF NOT EXISTS user_id UUID,
ADD COLUMN IF NOT EXISTS api_key_project_id UUID;
```

Indexes have been added for efficient querying:
- `idx_api_key_id` - Query by API key
- `idx_user_id` - Query by user
- `idx_api_key_project_id` - Query by API key's project

### Budapp Changes

The `update_proxy_cache` function in `credential_ops/services.py` now:

1. Fetches credential details including `user_id`
2. Adds `__metadata__` to the Redis cache data
3. Always includes metadata even if some fields are `None` for consistency

### Budmetrics Changes

The observability module has been updated to:

1. Accept new metadata fields in `InferenceDetailsMetrics` schema
2. Handle both legacy (10 fields) and new (13 fields) tuple formats
3. Insert metadata into ClickHouse with proper NULL handling

## Usage Examples

### Query by User

```sql
SELECT
    user_id,
    COUNT(*) as request_count,
    SUM(cost) as total_cost
FROM ModelInferenceDetails
WHERE user_id IS NOT NULL
    AND request_arrival_time >= today()
GROUP BY user_id
ORDER BY request_count DESC;
```

### Query by API Key

```sql
SELECT
    api_key_id,
    COUNT(*) as requests,
    COUNT(DISTINCT model_id) as unique_models,
    AVG(cost) as avg_cost_per_request
FROM ModelInferenceDetails
WHERE api_key_id IS NOT NULL
GROUP BY api_key_id;
```

### Project Usage Analysis

```sql
SELECT
    api_key_project_id,
    COUNT(*) as total_requests,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(DISTINCT api_key_id) as active_api_keys,
    SUM(cost) as total_cost
FROM ModelInferenceDetails
WHERE api_key_project_id IS NOT NULL
    AND request_arrival_time >= toStartOfMonth(now())
GROUP BY api_key_project_id
ORDER BY total_cost DESC;
```

## Migration Guide

### For Existing Deployments

1. **Run ClickHouse Migration**:
   ```bash
   # Apply schema changes
   clickhouse-client --query "$(cat scripts/add_auth_metadata_columns.sql)"
   ```

2. **Deploy Services in Order**:
   - Deploy budmetrics first (backward compatible)
   - Deploy budapp next (adds metadata to Redis)
   - Deploy budgateway last (extracts and uses metadata)

### For New Deployments

The migration script `migrate_clickhouse.py` already includes the new columns, so they will be created automatically during initial setup.

## Backward Compatibility

The implementation maintains full backward compatibility:

1. **Redis**: Old entries without `__metadata__` continue to work
2. **ClickHouse**: New columns are nullable, existing data remains valid
3. **Budmetrics**: Handles both old (10 field) and new (13 field) tuple formats
4. **Budgateway**: Gracefully handles missing metadata

## Security Considerations

1. **Access Control**: Metadata enables row-level security based on user/project
2. **Audit Trail**: All API usage can be traced to specific users and API keys
3. **Privacy**: User IDs are internal UUIDs, not exposing personal information

## Performance Impact

- **Redis**: Minimal overhead (~100 bytes per API key)
- **ClickHouse**: Indexes optimize query performance
- **Request Latency**: No measurable impact (metadata already in memory)

## Future Enhancements

1. **Rate Limiting**: Use metadata for per-user/per-key rate limits
2. **Billing**: Accurate cost attribution per API key
3. **Anomaly Detection**: Identify unusual usage patterns per user
4. **Compliance**: Generate audit reports for regulatory requirements
