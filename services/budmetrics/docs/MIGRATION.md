# ClickHouse Migration Guide

This guide explains how to set up and migrate ClickHouse tables for the bud-serve-metrics application.

## Migration Script

The `migrate_clickhouse.py` script handles the creation of required ClickHouse tables.

### Usage

#### Basic migration (ModelInferenceDetails only):
```bash
python scripts/migrate_clickhouse.py
```

#### Include ModelInference table (optional):
```bash
python scripts/migrate_clickhouse.py --include-model-inference
```

#### Verify existing tables:
```bash
python scripts/migrate_clickhouse.py --verify-only
```

## Docker Compose Setup

The migration runs automatically when starting the application with docker-compose:

```bash
cd deploy
docker-compose -f docker-compose-dev.yaml up
```

### With Local ClickHouse

To run with a local ClickHouse instance:

```bash
cd deploy
docker-compose -f docker-compose-dev.yaml -f docker-compose-clickhouse.yaml up
```

## Manual Migration

If you need to run the migration manually:

1. Ensure environment variables are set:
   - `PSQL_HOST`: ClickHouse host
   - `PSQL_PORT`: ClickHouse port  
   - `PSQL_DBNAME`: Database name
   - `PSQL_USER`: Username
   - `PSQL_PASSWORD`: Password

2. Run the migration:
   ```bash
   python scripts/migrate_clickhouse.py
   ```

## Table Structure

### ModelInferenceDetails (Required)
- Stores inference request details
- Includes metadata like project_id, endpoint_id, model_id
- Supports JSON response analysis
- Partitioned by month for performance

### ModelInference (Optional)
- Stores raw inference data
- Includes request/response bodies
- Token counts and performance metrics
- Reference only - managed by another service

## Troubleshooting

1. **JSON Type Error**: Ensure your ClickHouse version supports the JSON type (v22.6+)
2. **Connection Issues**: Verify ClickHouse is accessible at the configured host/port
3. **Permission Errors**: Ensure the user has CREATE TABLE permissions