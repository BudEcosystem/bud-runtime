# Observability Metrics Seeder

This script seeds test data for the observability metrics system using the `/add` API endpoint.

## Features

- Seeds ModelInferenceDetails via the `/observability/add` API endpoint
- Optionally seeds ModelInference table directly (with `--seed-model-inference`)
- Maintains proper relationships between projects, models, and endpoints
- Generates realistic test data with configurable parameters
- Provides progress tracking and verification

## Usage

### Basic seeding (ModelInferenceDetails only via API):
```bash
python scripts/seed_observability_metrics.py
```

### Seed both tables (ModelInference directly + ModelInferenceDetails via API):
```bash
python scripts/seed_observability_metrics.py --seed-model-inference
```

### Custom parameters:
```bash
python scripts/seed_observability_metrics.py \
    --url http://localhost:8000 \
    --records 100000 \
    --batch-size 500 \
    --days 90 \
    --delay 0.05 \
    --verify
```

## Command Line Options

- `--url`: Base URL of the API (default: http://localhost:8000)
- `--records`: Total number of records to seed (default: 10000)
- `--batch-size`: Number of records per batch (default: 100)
- `--days`: Number of days to spread the data over (default: 30)
- `--delay`: Delay between batches in seconds (default: 0.1)
- `--seed-model-inference`: Also seed ModelInference table directly
- `--verify`: Verify the data after seeding

## Data Relationships

The seeder maintains proper relationships:

1. **Projects → Endpoints**: One-to-Many
   - Each project can have multiple endpoints

2. **Models → Endpoints**: One-to-Many
   - Each model can have multiple endpoints
   - Each endpoint belongs to exactly one model

3. **Inference IDs**: Shared between tables
   - Same inference_id in both ModelInference and ModelInferenceDetails
   - Ensures data consistency across tables

## Environment Variables

When using `--seed-model-inference`, configure these for direct DB access:
- `PSQL_HOST`: ClickHouse host
- `PSQL_PORT`: ClickHouse port
- `PSQL_DB_NAME`: Database name
- `PSQL_USER`: Username
- `PSQL_PASSWORD`: Password

## Example Output

```
Starting data seeding:
  ModelInferenceDetails via API: http://localhost:8000/observability/add
  ModelInference via direct DB: localhost:9000
  Total records: 10,000
  Batch size: 100
  Total batches: 100
  Date range: 2024-11-15 to 2024-12-15

Progress: 1,000/10,000 sent (10.0%) - Inserted: 950, Duplicates: 50, Failed: 0 - Rate: 500 records/sec - ETA: 0.3 minutes

Seeding completed:
  Total time: 20.5 seconds
  Records sent: 10,000
  Successfully inserted: 9,500
  Duplicates skipped: 500
  Failed: 0
  Average rate: 488 records/second

Verifying seeded data...
  Total records in ModelInferenceDetails: 9,500
  Expected records (inserted): 9,500
  ✓ Verification successful!
```

## Performance Tips

1. **Batch Size**: Larger batches (500-1000) are more efficient but use more memory
2. **Delay**: Reduce delay for faster seeding, but monitor server load
3. **Direct DB**: Use `--seed-model-inference` for faster ModelInference seeding
4. **Parallel Runs**: Can run multiple instances with different date ranges

## Troubleshooting

1. **Connection Errors**: Verify the API is running and accessible
2. **Validation Errors**: Check the response details for specific field issues
3. **High Duplicate Rate**: Normal if re-running; inference_ids are checked
4. **Slow Performance**: Increase batch size or reduce delay
