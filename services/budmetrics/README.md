# Bud Serve Metrics Documentation

## Table of Contents

1. [Architecture Overview](./docs/ARCHITECTURE.md)
2. [API Reference](./docs/API_REFERENCE.md)
3. [Query Building Guide](./docs/QUERY_BUILDING.md)
4. [Performance & Optimization](./docs/PERFORMANCE.md)
5. [Database Schema](./docs/DATABASE_SCHEMA.md)
6. [Migration Guide](./docs/MIGRATION.md)
7. [Data Seeding Guide](./docs/SEEDER.md)
8. [Development Guide](./docs/DEVELOPMENT.md)
9. [Deployment Guide](./docs/DEPLOYMENT.md)

## Quick Start

### Prerequisites

- Python 3.11+
- ClickHouse database (v22.6+ for JSON support)
- Redis (for Dapr pub/sub)
- Docker & Docker Compose (for containerized deployment)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd bud-serve-metrics

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration
```

### Running the Application

#### Using Docker Compose

```bash
# Start all services (app + dependencies)
docker-compose -f deploy/docker-compose-dev.yaml up -d

# Start with local ClickHouse
docker-compose -f deploy/docker-compose-dev.yaml -f deploy/docker-compose-clickhouse.yaml up -d
```

#### Direct Python

```bash
# Run database migrations (with retry mechanism)
python scripts/migrate_clickhouse.py --max-retries 30 --retry-delay 2

# Verify tables were created
python scripts/migrate_clickhouse.py --verify-only

# Start the application
uvicorn budmetrics.main:app --host 0.0.0.0 --port 8000 --reload
```

See [Migration Guide](./docs/MIGRATION.md) for detailed migration options and troubleshooting.

### Seeding Test Data

```bash
# Quick start - seed via API
python scripts/seed_observability_metrics.py --records 10000

# Production-scale test data with direct DB insertion
python scripts/seed_observability_metrics.py \
    --direct-db \
    --records 100000 \
    --batch-size 1000 \
    --days 90 \
    --verify
```

See [Data Seeding Guide](./docs/SEEDER.md) for advanced seeding options and performance tips.

## Core Concepts

### Metrics Types

The system supports the following metrics:
- **request_count**: Total number of requests
- **success_request**: Successful requests with success rate
- **failure_request**: Failed requests with failure rate
- **queuing_time**: Time spent in queue before processing
- **input_token**: Number of input tokens processed
- **output_token**: Number of output tokens generated
- **concurrent_requests**: Maximum concurrent requests
- **ttft**: Time to first token (ms)
- **latency**: End-to-end latency (ms)
- **throughput**: Tokens per second
- **cache**: Cache hit rate and performance

### Time Series Analysis

- **Standard Intervals**: hourly, daily, weekly, monthly, quarterly, yearly
- **Custom Intervals**: Any custom interval (e.g., 7 days, 3 hours)
- **Time Alignment**: Custom intervals align to the specified `from_date`
- **Gap Filling**: Optional time gap filling with NULL values

### Filtering & Grouping

- Filter by: model, project, endpoint
- Group by: model, project, endpoint
- TopK: Limit results to top K entities by metric value
- Delta Analysis: Track changes over time periods

## API Endpoints

### Analytics Endpoint

```
POST /observability/analytics
```

Retrieve time-series metrics with flexible filtering and grouping.

### Add Metrics Endpoint

```
POST /observability/add
```

Bulk insert metrics data using CloudEvents format.

See [API Reference](./docs/API_REFERENCE.md) for detailed documentation.

## Architecture

The application follows a modular architecture:

- **Models Layer**: Query building, ClickHouse client, data models
- **Services Layer**: Business logic, result processing, caching
- **Routes Layer**: API endpoints, request/response handling
- **Commons Layer**: Shared utilities, configuration, profiling

See [Architecture Overview](./docs/ARCHITECTURE.md) for detailed information.

## Performance

The system is optimized for high-performance analytics:

- **Connection pooling** with configurable min/max connections
- **Query caching** with TTL support
- **Concurrent query execution** with semaphore protection
- **Efficient CTE usage** for complex aggregations
- **Response compression** using Brotli (99% size reduction)
- **Fast JSON serialization** with orjson

### Performance Benchmarks

With 1 billion+ rows in ClickHouse:
- Query execution: ~750ms
- Result processing: ~1.1s  
- End-to-end latency: ~3.95s (with compression + orjson)
- Payload size: 143KB compressed (from 15.59MB)

See [Performance Analysis](./docs/PERFORMANCE.md) for detailed benchmarks and optimization strategies.

## Examples

The `examples/` directory contains practical examples:

- **analytics_examples.py**: Real-world API usage patterns
- **query_builder_examples.py**: Direct QueryBuilder usage
- **README.md**: Guide to running the examples

Run examples:
```bash
# API examples (requires running application)
python examples/analytics_examples.py

# Query builder examples (shows generated SQL)
python examples/query_builder_examples.py
```

## Development

For contributing to the project:

1. Follow the code style guidelines
2. Write tests for new features
3. Update documentation
4. Use conventional commits

See [Development Guide](./docs/DEVELOPMENT.md) for detailed instructions.