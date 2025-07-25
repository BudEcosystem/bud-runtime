# Test Suite Documentation

This directory contains comprehensive unit tests, integration tests, and performance tests for the bud-serve-metrics application.

## Test Structure

```
tests/
├── fixtures/           # Test data and fixtures
│   └── test_data.py   # Sample data for testing
├── unit/              # Unit tests
│   └── observability/ # Observability module tests
├── integration/       # Integration tests
├── performance/       # Performance and edge case tests
├── pytest.ini        # Pytest configuration
├── test_runner.py     # Test runner script
└── README.md         # This file
```

## Test Categories

### Unit Tests (`tests/unit/`)

#### Frequency and Time Handling (`test_models_frequency.py`)
- Tests for `FrequencyUnit` enum validation
- Tests for `Frequency` class parsing and validation
- Custom frequency interval handling
- Edge cases and error conditions

#### Time Series Helper (`test_time_series_helper.py`)
- Time bucket expression generation
- Standard vs custom frequency handling
- Timezone and alignment calculations
- ClickHouse function generation

#### QueryBuilder Basic (`test_query_builder_basic.py`)
- Basic query construction
- Filter building (project, model, endpoint, date ranges)
- Metric-specific SQL generation
- SQL injection protection
- Join requirements detection

#### QueryBuilder Advanced (`test_query_builder_advanced.py`)
- GROUP BY functionality
- TopK query generation with ROW_NUMBER
- Custom interval alignment
- Complex query combinations
- Concurrent requests CTE logic

#### ClickHouse Client (`test_clickhouse_client.py`)
- Connection management and pooling
- Query caching (LRU with TTL)
- Batch query execution
- Error handling and retry logic
- Performance profiling decorators

#### Services (`test_services.py`)
- Analytics query orchestration
- Result processing and formatting
- Delta and percent change calculations
- Bulk data ingestion with deduplication
- Validation error handling

#### Schemas (`test_schemas.py`)
- Pydantic model validation
- Request/response schema validation
- Metric type validation
- Error message validation
- Edge case data validation

### Integration Tests (`tests/integration/`)

#### API Routes (`test_routes.py`)
- `/observability/analytics` endpoint testing
- `/observability/add` endpoint testing
- Request validation and error handling
- Response format verification
- Concurrent request handling

### Performance Tests (`tests/performance/`)

#### Performance and Edge Cases (`test_performance_edge_cases.py`)
- Cache performance with large datasets
- Concurrent operation handling
- Large data processing efficiency
- Memory usage patterns
- Extreme date ranges and intervals
- Unicode and special character handling
- Error recovery scenarios

## Test Coverage

The test suite provides comprehensive coverage of:

### Core Functionality
- ✅ All 11 metric types (request_count, success_request, failure_request, queuing_time, input_token, output_token, concurrent_requests, ttft, latency, throughput, cache)
- ✅ All frequency types (standard: secondly to yearly, custom: N units)
- ✅ All GROUP BY combinations (model_id, endpoint_id)
- ✅ TopK functionality with ranking
- ✅ Custom interval alignment to from_date

### Data Flow
- ✅ Request validation → Query building → Database execution → Result processing → Response formatting
- ✅ Bulk ingestion → Deduplication → Validation → Database insertion
- ✅ Error handling at each stage

### Performance & Scalability
- ✅ Large dataset processing (10,000+ records)
- ✅ Concurrent request handling (50+ simultaneous)
- ✅ Cache efficiency (LRU eviction, TTL expiration)
- ✅ Memory usage patterns

### Edge Cases
- ✅ Extreme date ranges (seconds to decades)
- ✅ Special characters and Unicode in identifiers
- ✅ Null/None/empty value handling
- ✅ Timezone boundary conditions
- ✅ Leap year date handling
- ✅ Numeric extremes (infinity, NaN, very large/small numbers)

## Running Tests

### Quick Start

```bash
# Run all tests
python tests/test_runner.py

# Run specific test types
python tests/test_runner.py --type unit
python tests/test_runner.py --type integration
python tests/test_runner.py --type performance

# Run with coverage
python tests/test_runner.py --coverage

# Run individual test suites with detailed reporting
python tests/test_runner.py --suites
```

### Direct pytest Usage

```bash
# Run all tests
pytest tests/

# Run specific test files
pytest tests/unit/observability/test_query_builder_basic.py -v

# Run with coverage
pytest tests/ --cov=budmetrics --cov-report=html

# Run performance tests only
pytest tests/performance/ -v
```

### Test Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests  
pytest -m integration

# Run only performance tests
pytest -m performance
```

## Test Data and Fixtures

### Sample Data (`tests/fixtures/test_data.py`)
- `SAMPLE_INFERENCE_DATA`: Single inference record
- `SAMPLE_BULK_INFERENCE_DATA`: 50 inference records with variety
- `ANALYTICS_REQUEST_SAMPLES`: Pre-configured request samples
- `get_mock_clickhouse_response()`: Generates mock database responses
- `EXPECTED_QUERY_PATTERNS`: Expected SQL patterns for validation

### Mock Strategies
- **ClickHouse Client**: Mocked with AsyncMock for database operations
- **Service Dependencies**: Dependency injection override in FastAPI tests
- **Time-sensitive Tests**: Fixed datetime objects for consistency
- **Random Data**: Seeded random generation for reproducible tests

## Test Scenarios by Feature

### Analytics Query Building
1. **Basic Queries**: Single metric, basic filters
2. **Multi-metric**: All 11 metrics in combination
3. **Grouping**: Single and multiple GROUP BY dimensions
4. **TopK**: Ranking with various metric types
5. **Custom Intervals**: Alignment calculations and edge cases
6. **Concurrent Requests**: Special CTE logic for overlap calculation

### Data Ingestion
1. **Bulk Processing**: Large batches with validation
2. **Deduplication**: Handling duplicate inference_ids
3. **Validation Errors**: Partial success scenarios
4. **Performance**: Large dataset ingestion efficiency

### Caching System
1. **LRU Eviction**: Cache size management
2. **TTL Expiration**: Time-based cache invalidation
3. **Concurrent Access**: Thread-safe operations
4. **Performance**: Large cache operations

### Error Handling
1. **Validation Errors**: Schema validation failures
2. **Database Errors**: Connection and query failures
3. **Service Errors**: Business logic error scenarios
4. **Recovery**: Graceful degradation patterns

## Performance Benchmarks

The test suite includes performance benchmarks for:

- **Query Building**: 100 complex queries < 1 second
- **Cache Operations**: 1,000 set/get operations < 1 second  
- **Concurrent Processing**: 50 requests < 2 seconds
- **Large Dataset**: 10,000 records < 1 second
- **Memory Usage**: Cache size management under load

## Continuous Integration

The test suite is designed to run in CI/CD pipelines with:

- **Fast Feedback**: Unit tests complete quickly
- **Comprehensive Coverage**: Integration tests validate end-to-end flow
- **Performance Regression**: Performance tests catch degradation
- **Reproducible Results**: Fixed seeds and mocked dependencies

## Adding New Tests

When adding new functionality, ensure:

1. **Unit Tests**: Test individual components in isolation
2. **Integration Tests**: Test component interaction
3. **Performance Tests**: Test scalability if applicable
4. **Edge Cases**: Test boundary conditions and error scenarios
5. **Documentation**: Update this README with new test scenarios

### Test Template

```python
import pytest
from unittest.mock import Mock, AsyncMock

class TestNewFeature:
    \"\"\"Test cases for new feature.\"\"\"
    
    @pytest.fixture
    def mock_dependency(self):
        \"\"\"Mock external dependencies.\"\"\"
        return Mock()
    
    def test_basic_functionality(self, mock_dependency):
        \"\"\"Test basic feature functionality.\"\"\"
        # Arrange
        # Act  
        # Assert
        pass
    
    def test_edge_cases(self, mock_dependency):
        \"\"\"Test edge cases and error conditions.\"\"\"
        pass
    
    @pytest.mark.asyncio
    async def test_async_functionality(self, mock_dependency):
        \"\"\"Test async functionality.\"\"\"
        pass
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure `PYTHONPATH` includes project root
2. **Async Test Issues**: Use `pytest-asyncio` and `@pytest.mark.asyncio`
3. **Mock Issues**: Ensure proper mock setup and cleanup
4. **Performance Test Failures**: May be environment-dependent

### Debug Options

```bash
# Verbose output
pytest -v -s

# Stop on first failure  
pytest -x

# Run specific test
pytest tests/unit/observability/test_services.py::TestObservabilityMetricsService::test_get_analytics_basic

# Debug mode
pytest --pdb
```

This comprehensive test suite ensures the reliability, performance, and correctness of the bud-serve-metrics application across all usage scenarios.