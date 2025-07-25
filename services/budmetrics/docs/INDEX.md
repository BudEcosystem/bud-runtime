# Documentation Index

This is a comprehensive index of all documentation for the Bud Serve Metrics system.

## Main Documentation

### Core Guides

- **[README.md](../README.md)** - Project overview and quick start guide
- **[Architecture Overview](./ARCHITECTURE.md)** - System design, components, and data flow
- **[API Reference](./API_REFERENCE.md)** - Complete API documentation with examples
- **[Database Schema](./DATABASE_SCHEMA.md)** - ClickHouse tables, indexes, and optimization

### Implementation Guides

- **[Query Building Guide](./QUERY_BUILDING.md)** - Understanding and extending the query builder
- **[Performance Analysis](./PERFORMANCE.md)** - Benchmarks and optimization strategies
- **[Migration Guide](./MIGRATION.md)** - Database setup and migration procedures
- **[Data Seeding Guide](./SEEDER.md)** - Test data generation and seeding options

### Operations Guides

- **[Development Guide](./DEVELOPMENT.md)** - Setup, coding standards, and testing
- **[Deployment Guide](./DEPLOYMENT.md)** - Production deployment with Docker/Kubernetes

## Code Examples

Located in the `examples/` directory:

- **[Examples README](../examples/README.md)** - Guide to running examples
- **[analytics_examples.py](../examples/analytics_examples.py)** - API usage patterns
- **[query_builder_examples.py](../examples/query_builder_examples.py)** - Query construction

## Key Concepts

### Metrics System
- 11 metric types (request_count, latency, throughput, etc.)
- Time series analysis with standard and custom intervals
- Filtering and grouping by model, project, endpoint
- TopK queries for high-cardinality data
- Delta analysis for trend tracking

### Technical Features
- **CTE System**: Reusable query components with template support
- **Time Alignment**: Custom intervals that align to specified start dates
- **Performance Profiling**: Built-in performance tracking in debug mode
- **Response Compression**: 99% payload reduction with Brotli
- **Connection Pooling**: Configurable pool with warmup support

### Integration
- **Dapr Pub/Sub**: Event-driven metrics ingestion via Redis
- **CloudEvents**: Standard format for metrics events
- **BudMicroframe**: Microservices framework abstraction

## Quick Links

### For Users
- [API Endpoint Documentation](./API_REFERENCE.md#analytics-endpoint)
- [Available Metrics](./API_REFERENCE.md#available-metrics)
- [Example Queries](../examples/analytics_examples.py)

### For Developers
- [Adding New Metrics](./QUERY_BUILDING.md#adding-a-new-metric)
- [Testing Guide](./DEVELOPMENT.md#testing)
- [Code Style Guidelines](./DEVELOPMENT.md#code-style-guidelines)

### For Operators
- [Docker Deployment](./DEPLOYMENT.md#docker-deployment)
- [Kubernetes Setup](./DEPLOYMENT.md#kubernetes-deployment)
- [Monitoring & Maintenance](./DEPLOYMENT.md#maintenance)

## Documentation Standards

When contributing documentation:

1. **Use Clear Headers**: Organize content with descriptive headers
2. **Include Examples**: Show code snippets and command examples
3. **Explain Concepts**: Don't assume prior knowledge
4. **Keep Updated**: Update docs when code changes
5. **Cross-Reference**: Link to related documentation

## Getting Help

- **Issues**: Report bugs or request features on GitHub
- **Examples**: Check the `examples/` directory for working code
- **Architecture**: Review [ARCHITECTURE.md](./ARCHITECTURE.md) for system design
- **API**: Consult [API_REFERENCE.md](./API_REFERENCE.md) for endpoint details