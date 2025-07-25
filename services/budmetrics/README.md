# BudMetrics Service

[![License](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://opensource.org/licenses/AGPL-3.0)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![ClickHouse](https://img.shields.io/badge/ClickHouse-22.6+-yellow.svg)](https://clickhouse.com/)
[![Dapr](https://img.shields.io/badge/Dapr-1.10+-blue.svg)](https://dapr.io/)

A high-performance observability service built on ClickHouse for analytics and time-series metrics collection. BudMetrics provides comprehensive monitoring, analytics, and performance insights for AI/ML model deployments across the Bud Stack platform.

## 🚀 Features

- **Time-Series Analytics**: High-performance time-series data analysis with ClickHouse
- **Real-time Metrics Collection**: Collects and processes metrics from all platform services
- **Performance Monitoring**: Model deployment performance, throughput, and latency tracking
- **Resource Analytics**: Cluster resource utilization and optimization insights
- **Custom Dashboards**: Flexible analytics API for building custom visualizations
- **Data Aggregation**: Multi-level aggregation (hourly, daily, weekly, monthly)
- **Query Optimization**: Optimized SQL generation with CTE and efficient indexing
- **High Throughput**: Handles millions of metrics with sub-second query performance
- **Bulk Operations**: Efficient bulk data insertion and processing

## 📋 Table of Contents

- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Development](#-development)
- [API Documentation](#-api-documentation)
- [Performance](#-performance)
- [Deployment](#-deployment)
- [Testing](#-testing)
- [Troubleshooting](#-troubleshooting)

## 🏗️ Architecture

### Service Structure

```
budmetrics/
├── budmetrics/
│   ├── analytics/          # Core analytics functionality
│   │   ├── routes.py       # REST API endpoints
│   │   ├── services.py     # Business logic
│   │   └── schemas.py      # Pydantic schemas
│   ├── models/             # Data models and query builders
│   │   ├── query_builder.py # ClickHouse query builder
│   │   ├── clickhouse_client.py # ClickHouse client
│   │   └── data_models.py  # Data models
│   ├── observability/      # Observability metrics
│   │   ├── routes.py       # Metrics endpoints
│   │   ├── collectors.py   # Metric collectors
│   │   └── processors.py   # Data processors
│   └── commons/            # Shared utilities
│       ├── config.py       # Configuration
│       ├── profiling.py    # Performance profiling
│       └── exceptions.py   # Custom exceptions
├── scripts/                # Utility scripts
│   ├── migrate_clickhouse.py # Database migrations
│   ├── seed_observability_metrics.py # Data seeding
│   └── query_examples.py   # Query examples
├── docs/                   # Documentation
│   ├── API_REFERENCE.md    # API documentation
│   ├── PERFORMANCE.md      # Performance analysis
│   └── QUERY_BUILDING.md   # Query building guide
├── examples/               # Usage examples
├── tests/                  # Test suite
└── deploy/                 # Deployment scripts
```

### Core Components

- **Analytics Engine**: High-performance time-series analytics with ClickHouse
- **Query Builder**: Dynamic SQL generation with optimization strategies
- **Metrics Collector**: Real-time metrics ingestion from platform services
- **Data Processor**: ETL pipeline for data transformation and aggregation
- **Cache Manager**: Redis-based caching for query optimization
- **API Layer**: RESTful endpoints for analytics and metrics access

### Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Platform   │────▶│    Dapr     │────▶│ BudMetrics  │
│  Services   │     │   Pub/Sub   │     │  Collector  │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ ClickHouse  │◄────│    ETL      │◄────│   Data      │
│  Database   │     │ Processing  │     │Validation   │
└──────┬──────┘     └─────────────┘     └─────────────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Analytics   │────▶│   Query     │────▶│    API      │
│   Engine    │     │  Builder    │     │ Response    │
└─────────────┘     └─────────────┘     └─────────────┘
```

## 📦 Prerequisites

### Required

- **Python** 3.11+
- **Docker** and Docker Compose
- **Git**

### Service Dependencies

- **ClickHouse** 22.6+ - Primary analytics database
- **Redis** - Dapr pub/sub and caching
- **Dapr** - Service mesh and event handling

### Optional Dependencies

- **Grafana** - Visualization dashboards
- **Prometheus** - Additional metrics collection

## 🚀 Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/BudEcosystem/bud-stack.git
cd bud-stack/services/budmetrics

# Setup environment
cp .env.sample .env
# Edit .env with your configuration
```

### 2. Configure Environment

Edit `.env` file with required configurations:

```bash
# Database
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_DATABASE=budmetrics
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=

# Redis
REDIS_URL=redis://localhost:6379

# Dapr
DAPR_HTTP_PORT=3510
DAPR_GRPC_PORT=50007
DAPR_API_TOKEN=your-token

# Application
APP_NAME=bud-serve-metrics
LOG_LEVEL=INFO

# Performance Settings
CLICKHOUSE_POOL_SIZE=10
CLICKHOUSE_MAX_CONNECTIONS=100
QUERY_CACHE_TTL=300
ENABLE_QUERY_PROFILING=true

# Data Retention
METRICS_RETENTION_DAYS=365
RAW_DATA_RETENTION_DAYS=90
AGGREGATED_DATA_RETENTION_DAYS=730
```

### 3. Start Development Environment

```bash
# Start with ClickHouse
./deploy/start_dev.sh

# Or start individual components
docker-compose -f deploy/docker-compose-dev.yaml up -d
docker-compose -f deploy/docker-compose-clickhouse.yaml up -d

# Service will be available at:
# API: http://localhost:9085
# API Docs: http://localhost:9085/docs
```

### 4. Initialize Database

```bash
# Run ClickHouse migrations
python scripts/migrate_clickhouse.py --max-retries 30 --retry-delay 2

# Verify tables were created
python scripts/migrate_clickhouse.py --verify-only

# Optional: Seed test data
python scripts/seed_observability_metrics.py --records 10000
```

## 💻 Development

### Code Quality

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
./scripts/install_hooks.sh

# Linting and formatting
ruff check budmetrics/ --fix
ruff format budmetrics/

# Type checking
mypy budmetrics/

# Run all quality checks
./scripts/lint.sh
```

### Database Operations

```bash
# Create new migration
python scripts/create_migration.py --name "add_new_metrics_table"

# Run migrations
python scripts/migrate_clickhouse.py

# Check migration status
python scripts/migrate_clickhouse.py --status

# Rollback migration (if supported)
python scripts/migrate_clickhouse.py --rollback 1
```

### Query Development

```bash
# Test query builder
python examples/query_builder_examples.py

# Validate query performance
python scripts/profile_queries.py --query-file examples/sample_queries.sql

# Generate sample data
python scripts/seed_observability_metrics.py --direct-db --records 100000
```

## 📚 API Documentation

### Key Endpoints

#### Analytics
- `POST /observability/analytics` - Retrieve time-series metrics with filtering
- `GET /observability/metrics/summary` - Get metrics summary
- `GET /observability/metrics/types` - List available metric types

#### Data Ingestion
- `POST /observability/add` - Bulk insert metrics data
- `POST /observability/events` - Add individual events
- `GET /observability/health` - Service health check

#### Administration
- `GET /admin/stats` - Database statistics
- `POST /admin/optimize` - Optimize database tables
- `GET /admin/metrics/cache` - Cache statistics

### Analytics Query Examples

#### Basic Time-Series Query
```json
POST /observability/analytics
{
  "metrics": ["request_count", "latency"],
  "time_range": {
    "from_date": "2024-01-01T00:00:00Z",
    "to_date": "2024-01-31T23:59:59Z"
  },
  "interval": "daily",
  "filters": {
    "model": "llama-2-7b",
    "cluster": "production"
  }
}
```

#### Advanced Analytics with Aggregation
```json
POST /observability/analytics
{
  "metrics": ["throughput", "success_rate"],
  "time_range": {
    "from_date": "2024-01-15T00:00:00Z",
    "to_date": "2024-01-15T23:59:59Z"
  },
  "interval": "hourly",
  "filters": {
    "project": "ai-chatbot"
  },
  "group_by": ["model", "endpoint"],
  "aggregation": {
    "type": "percentile",
    "percentile": 95
  },
  "limit": 100
}
```

#### Performance Comparison
```json
POST /observability/analytics
{
  "metrics": ["ttft", "latency"],
  "time_range": {
    "from_date": "2024-01-01T00:00:00Z",
    "to_date": "2024-01-31T23:59:59Z"
  },
  "interval": "weekly",
  "comparison": {
    "type": "previous_period",
    "periods": 2
  },
  "filters": {
    "model": ["llama-2-7b", "gpt-3.5-turbo"]
  }
}
```

### Bulk Data Insertion

#### CloudEvents Format
```json
POST /observability/add
{
  "events": [
    {
      "specversion": "1.0",
      "type": "model.inference",
      "source": "budapp",
      "subject": "model-123",
      "time": "2024-01-15T10:30:00Z",
      "data": {
        "metric_type": "request_count",
        "value": 1,
        "model": "llama-2-7b",
        "cluster": "production",
        "endpoint": "chat-completion"
      }
    }
  ]
}
```

## ⚡ Performance

### Optimization Features

- **Connection Pooling**: Configurable min/max connections
- **Query Caching**: TTL-based caching with Redis
- **Concurrent Execution**: Semaphore-protected parallel queries
- **Efficient CTEs**: Common Table Expressions for complex aggregations
- **Response Compression**: Brotli compression (99% size reduction)
- **Fast Serialization**: orjson for high-performance JSON processing

### Performance Benchmarks

With 1 billion+ rows in ClickHouse:
- Query execution: ~750ms
- Result processing: ~1.1s  
- End-to-end latency: ~3.95s (with compression + orjson)
- Payload size: 143KB compressed (from 15.59MB raw)
- Throughput: 10,000+ queries per minute
- Concurrent users: 1,000+ simultaneous connections

### Optimization Tips

```bash
# Enable all optimizations
export CLICKHOUSE_POOL_SIZE=20
export QUERY_CACHE_TTL=600
export ENABLE_COMPRESSION=true
export ENABLE_QUERY_PROFILING=true

# Database optimizations
# In ClickHouse settings:
SET max_threads = 8;
SET max_memory_usage = 4000000000;
SET optimize_read_in_order = 1;
```

## 🚀 Deployment

### Docker Deployment

```bash
# Build image
docker build -t budmetrics:latest .

# Run with docker-compose
docker-compose up -d

# With ClickHouse
docker-compose -f docker-compose.yml -f docker-compose-clickhouse.yml up -d
```

### Kubernetes Deployment

```bash
# Deploy with Helm
helm install budmetrics ./charts/budmetrics/

# Or as part of full stack
cd ../../infra/helm/bud
helm dependency update
helm install bud .
```

### Production Configuration

```yaml
# values.yaml for Helm
budmetrics:
  replicas: 3
  resources:
    requests:
      memory: "1Gi"
      cpu: "1000m"
    limits:
      memory: "4Gi"
      cpu: "4000m"
  clickhouse:
    enabled: true
    persistence:
      enabled: true
      size: 100Gi
    resources:
      requests:
        memory: "4Gi"
        cpu: "2000m"
      limits:
        memory: "16Gi"
        cpu: "8000m"
  env:
    - name: CLICKHOUSE_POOL_SIZE
      value: "20"
    - name: QUERY_CACHE_TTL
      value: "600"
```

## 🧪 Testing

### Unit Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=budmetrics --cov-report=html

# Run specific test module
pytest tests/test_query_builder.py
```

### Integration Tests

```bash
# With Dapr sidecar
pytest tests/integration/ --dapr-http-port 3510 --dapr-api-token $DAPR_API_TOKEN
```

### Performance Tests

```bash
# Load test with sample data
python tests/performance/test_query_performance.py

# Benchmark query builder
python tests/performance/benchmark_queries.py

# Test bulk insertion performance
python tests/performance/test_bulk_insert.py
```

### Data Validation Tests

```bash
# Validate data integrity
python tests/validation/test_data_integrity.py

# Test aggregation accuracy
python tests/validation/test_aggregations.py
```

## 🔧 Troubleshooting

### Common Issues

#### ClickHouse Connection Failed
```bash
# Error: Connection refused to ClickHouse
# Solution: Ensure ClickHouse is running and accessible
docker-compose ps clickhouse
curl http://localhost:8123/ping

# Check connection parameters
ping localhost 8123
telnet localhost 8123
```

#### Query Performance Issues
```bash
# Error: Queries taking too long
# Solution: Optimize queries and increase resources
# Check ClickHouse query log:
SELECT query, query_duration_ms, memory_usage 
FROM system.query_log 
WHERE type = 'QueryFinish' 
ORDER BY query_duration_ms DESC 
LIMIT 10;

# Optimize table:
OPTIMIZE TABLE observability_metrics FINAL;
```

#### Memory Issues
```bash
# Error: Out of memory during query execution
# Solution: Increase ClickHouse memory limits
# In ClickHouse config:
<max_memory_usage>8000000000</max_memory_usage>
<max_bytes_before_external_group_by>2000000000</max_bytes_before_external_group_by>
```

#### High Disk Usage
```bash
# Error: Disk space running low
# Solution: Implement data retention policies
# Clean old data:
ALTER TABLE observability_metrics 
DELETE WHERE timestamp < now() - INTERVAL 90 DAY;

# Check table sizes:
SELECT 
    table,
    formatReadableSize(sum(bytes)) as size
FROM system.parts 
WHERE active 
GROUP BY table 
ORDER BY sum(bytes) DESC;
```

### Debug Mode

Enable detailed logging:
```bash
# In .env
LOG_LEVEL=DEBUG
ENABLE_QUERY_PROFILING=true
CLICKHOUSE_LOG_QUERIES=true

# For SQL debugging
ENABLE_SQL_LOGGING=true
SHOW_QUERY_PLANS=true
```

### Performance Monitoring

```bash
# Check service health
curl http://localhost:9085/health

# Monitor ClickHouse performance
curl http://localhost:9085/admin/stats

# Check cache hit rates
curl http://localhost:9085/admin/metrics/cache

# Monitor query performance
curl http://localhost:9085/metrics/query-performance
```

## 🤝 Contributing

Please see the main [Bud Stack Contributing Guide](../../CONTRIBUTING.md).

### Service-Specific Guidelines

1. Optimize queries for ClickHouse performance
2. Add comprehensive tests for new analytics features
3. Document query patterns and performance characteristics
4. Ensure proper data validation and sanitization
5. Maintain backward compatibility for API changes
6. Profile performance impact of new features

## 📄 License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](../../LICENSE) file for details.

## 🔗 Related Documentation

- [Main Bud Stack README](../../README.md)
- [CLAUDE.md Development Guide](../../CLAUDE.md)
- [API Documentation](http://localhost:9085/docs) (when running)
- [Performance Analysis](./docs/PERFORMANCE.md)
- [Query Building Guide](./docs/QUERY_BUILDING.md)
- [Database Schema](./docs/DATABASE_SCHEMA.md)
- [Analytics Examples](./examples/README.md)