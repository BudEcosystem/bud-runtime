# Development Guide

## Getting Started

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git
- Virtual environment tool (venv, virtualenv, or conda)

### Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd bud-serve-metrics
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   # Install runtime dependencies
   pip install -r requirements.txt

   # Install development dependencies
   pip install -r requirements-dev.txt
   pip install -r requirements-test.txt
   pip install -r requirements-lint.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your local configuration
   ```

5. **Start local services**
   ```bash
   # Start ClickHouse
   docker-compose -f deploy/docker-compose-clickhouse.yaml up -d

   # Or use the convenience script
   ./deploy/start_dev.sh
   ```

6. **Run database migrations**
   ```bash
   python scripts/migrate_clickhouse.py
   ```

7. **Start the development server**
   ```bash
   uvicorn budmetrics.main:app --reload --port 8000
   ```

## Project Structure

```
bud-serve-metrics/
├── budmetrics/              # Main application package
│   ├── __init__.py
│   ├── main.py             # FastAPI application entry point
│   ├── commons/            # Shared utilities
│   │   ├── config.py       # Configuration management
│   │   ├── constants.py    # Application constants
│   │   ├── profiling_utils.py  # Performance profiling
│   │   └── schemas.py      # Common Pydantic schemas
│   └── observability/      # Observability module
│       ├── models.py       # Database models, QueryBuilder
│       ├── routes.py       # API endpoints
│       ├── schemas.py      # Request/response schemas
│       ├── services.py     # Business logic
│       └── endpoint_schemas/  # External API schemas
├── scripts/                # Utility scripts
│   ├── migrate_clickhouse.py  # Database migration
│   ├── seed_observability_metrics.py  # Data seeding
│   └── startup.sh          # Container startup script
├── deploy/                 # Deployment configurations
│   ├── docker-compose-*.yaml
│   └── Dockerfile
├── tests/                  # Test suite
├── docs/                   # Documentation
└── clickhouse/            # ClickHouse-specific utilities
```

## Code Style Guidelines

### Python Style

We follow PEP 8 with some modifications:

1. **Line length**: 100 characters maximum
2. **Imports**: Group in order: stdlib, third-party, local
3. **Type hints**: Required for all functions
4. **Docstrings**: Required for all public functions

```python
from datetime import datetime, UTC
from typing import Optional, Union
from uuid import UUID

from pydantic import BaseModel

from budmetrics.commons.config import app_settings


async def process_metrics(
    metrics: list[str],
    from_date: datetime,
    to_date: Optional[datetime] = None,
) -> dict[str, Any]:
    """Process metrics for the given time range.

    Args:
        metrics: List of metric names to process
        from_date: Start date for processing
        to_date: End date (defaults to current time)

    Returns:
        Dictionary containing processed metrics
    """
    # Implementation
    pass
```

### SQL Style

For ClickHouse queries:

```sql
-- Use uppercase for SQL keywords
SELECT
    toDate(request_arrival_time) AS date,
    project_id,
    COUNT(*) AS request_count
FROM ModelInferenceDetails
WHERE request_arrival_time >= '2024-01-01'
  AND project_id IN ('uuid1', 'uuid2')
GROUP BY date, project_id
ORDER BY date DESC
```

### Commit Messages

Use conventional commits:

```
feat(observability): add new throughput metric
fix(query-builder): handle null values in aggregations
docs(api): update endpoint documentation
perf(clickhouse): optimize concurrent request query
refactor(services): extract result processing logic
test(analytics): add integration tests for topk
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=budmetrics --cov-report=html

# Run specific test file
pytest tests/test_observability_services.py

# Run with verbose output
pytest -v

# Run only marked tests
pytest -m "not slow"
```

### Writing Tests

#### Unit Tests

```python
import pytest
from datetime import datetime, UTC
from budmetrics.observability.models import QueryBuilder


class TestQueryBuilder:
    @pytest.fixture
    def query_builder(self):
        return QueryBuilder(performance_metrics=None)

    def test_simple_query(self, query_builder):
        query, fields = query_builder.build_query(
            metrics=["request_count"],
            from_date=datetime(2024, 1, 1, tzinfo=UTC),
            to_date=datetime(2024, 1, 31, tzinfo=UTC),
            frequency_unit="day"
        )

        assert "SELECT" in query
        assert "request_count" in query
        assert len(fields) > 0
```

#### Integration Tests

```python
import pytest
from httpx import AsyncClient

from budmetrics.main import app


@pytest.mark.asyncio
async def test_analytics_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/observability/analytics",
            json={
                "metrics": ["request_count"],
                "from_date": "2024-01-01T00:00:00Z",
                "frequency_unit": "day"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
```

### Test Data

See the [Data Seeding Guide](./SEEDER.md) for comprehensive seeding options.

Quick examples:
```bash
# Seed test data via API
python scripts/seed_observability_metrics.py \
    --records 1000 \
    --days 7

# Seed directly to database (faster)
python scripts/seed_observability_metrics.py \
    --direct-db \
    --records 10000 \
    --batch-size 500
```

## Debugging

### Enable Debug Mode

```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
export ENABLE_PERFORMANCE_PROFILING=true
```

### Logging

```python
from budmicroframe.commons import logging

logger = logging.get_logger(__name__)

logger.debug("Query generated", extra={"query": query})
logger.info("Processing metrics", extra={"count": len(metrics)})
logger.error("Query failed", extra={"error": str(e)})
```

### Performance Profiling

The application includes built-in profiling:

```python
from budmetrics.commons.profiling_utils import profile_async

@profile_async("my_operation")
async def my_function():
    # Function is automatically profiled
    pass
```

View profiling results in logs when DEBUG=true.

### Query Debugging

1. **Log generated queries**
   ```python
   logger.debug(f"Executing query: {query}")
   ```

2. **Use ClickHouse client directly**
   ```bash
   docker exec -it clickhouse-container clickhouse-client
   ```

3. **Explain query plans**
   ```sql
   EXPLAIN SYNTAX SELECT ...
   EXPLAIN PLAN SELECT ...
   ```

## Common Development Tasks

### Adding a New Metric

1. **Update metric definitions** in `models.py`
2. **Add to metric enum** in `schemas.py`
3. **Implement metric method** in `QueryBuilder`
4. **Add tests** for the new metric
5. **Update documentation**

Example:
```python
# In models.py
def _get_my_metric_definitions(self, ...):
    return [
        MetricDefinition(
            metrics_name="my_metric",
            required_tables=["ModelInferenceDetails"],
            select_clause="AVG(field) AS my_metric",
            select_alias="my_metric"
        )
    ]

# In schemas.py
class MetricType(str, Enum):
    MY_METRIC = "my_metric"
```

### Modifying Database Schema

1. **Create migration script**
   ```python
   # In scripts/migrations/add_new_column.py
   async def migrate():
       await client.execute_query("""
           ALTER TABLE ModelInferenceDetails
           ADD COLUMN new_field String DEFAULT ''
       """)
   ```

2. **Update models and schemas**
3. **Test migration locally**
4. **Document schema changes**

### Performance Optimization

1. **Identify slow queries**
   ```sql
   SELECT
       query,
       query_duration_ms,
       read_rows,
       memory_usage
   FROM system.query_log
   WHERE query_duration_ms > 1000
   ORDER BY query_duration_ms DESC
   ```

2. **Add appropriate indexes**
   ```sql
   ALTER TABLE ModelInferenceDetails
   ADD INDEX idx_field (field) TYPE minmax GRANULARITY 1
   ```

3. **Use query profiling**
   ```python
   with profiler.profile("complex_operation"):
       result = await complex_operation()
   ```

## API Development

### Adding New Endpoints

1. **Define request/response schemas**
   ```python
   class MyRequest(BaseModel):
       field: str

   class MyResponse(BaseModel):
       result: str
   ```

2. **Implement endpoint**
   ```python
   @router.post("/my-endpoint", response_model=MyResponse)
   async def my_endpoint(
       request: MyRequest,
       service: ObservabilityService = Depends()
   ):
       result = await service.process(request)
       return MyResponse(result=result)
   ```

3. **Add tests**
4. **Update API documentation**

### Error Handling

```python
from fastapi import HTTPException

try:
    result = await process_data()
except ValueError as e:
    raise HTTPException(
        status_code=400,
        detail={"error": "INVALID_INPUT", "message": str(e)}
    )
except DatabaseError as e:
    logger.error("Database error", exc_info=True)
    raise HTTPException(
        status_code=503,
        detail={"error": "DATABASE_ERROR", "message": "Service unavailable"}
    )
```

## Deployment

### Local Docker Build

```bash
# Build image
docker build -f deploy/Dockerfile -t bud-serve-metrics:local .

# Run container
docker run -p 8000:8000 \
    -e PSQL_HOST=host.docker.internal \
    -e PSQL_PORT=9000 \
    bud-serve-metrics:local
```

### Environment Configuration

Required environment variables:

```bash
# Database
PSQL_HOST=localhost
PSQL_PORT=9000
PSQL_DB_NAME=tensorzero
PSQL_USER=default
PSQL_PASSWORD=password

# Application
APP_PORT=8000
LOG_LEVEL=INFO
DEBUG=false

# Optional
CLICKHOUSE_ENABLE_QUERY_CACHE=true
ENABLE_PERFORMANCE_PROFILING=false
```

## Troubleshooting

### Common Issues

1. **Connection to ClickHouse fails**
   - Check if ClickHouse is running: `docker ps`
   - Verify port mapping: `docker port <container>`
   - Check environment variables

2. **Migration fails**
   - Ensure database exists
   - Check user permissions
   - Review migration logs

3. **Slow queries**
   - Enable query profiling
   - Check index usage
   - Review partition pruning

4. **Memory issues**
   - Limit concurrent queries
   - Use streaming for large results
   - Adjust pool size

### Debug Commands

```bash
# Check ClickHouse logs
docker logs clickhouse-container

# Connect to ClickHouse
docker exec -it clickhouse-container clickhouse-client

# View running queries
SELECT * FROM system.processes;

# Kill long-running query
KILL QUERY WHERE query_id = 'query-id';
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Update documentation
6. Submit a pull request

### Pull Request Checklist

- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] Documentation updated
- [ ] Commit messages follow convention
- [ ] No sensitive data in commits
- [ ] Performance impact considered
