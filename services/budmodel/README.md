# BudModel Service

[![License](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://opensource.org/licenses/AGPL-3.0)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Dapr](https://img.shields.io/badge/Dapr-1.10+-blue.svg)](https://dapr.io/)

A comprehensive model registry and leaderboard service that manages AI/ML model metadata, licensing information, and performance metrics from various AI benchmarks. BudModel serves as the central repository for model information across the Bud Stack platform.

## 🚀 Features

- **Model Registry**: Centralized catalog of AI/ML models with metadata, licensing, and versioning
- **Performance Leaderboards**: Benchmarking results and performance metrics from various AI evaluation suites
- **Licensing Management**: Model licensing information and compliance tracking
- **Benchmark Integration**: Integration with popular AI benchmarks and evaluation frameworks
- **Model Categorization**: Organization by model types, sizes, capabilities, and domains
- **Search & Discovery**: Advanced filtering and search capabilities for model exploration
- **API Integration**: RESTful API for model metadata access and management
- **Compliance Tracking**: License compatibility and usage restrictions monitoring

## 📋 Table of Contents

- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Development](#-development)
- [API Documentation](#-api-documentation)
- [Deployment](#-deployment)
- [Testing](#-testing)
- [Troubleshooting](#-troubleshooting)

## 🏗️ Architecture

### Service Structure

```
budmodel/
├── budmodel/
│   ├── model_ops/          # Model management operations
│   │   ├── routes.py       # REST API endpoints
│   │   ├── services.py     # Business logic
│   │   ├── crud.py         # Database operations
│   │   ├── models.py       # SQLAlchemy models
│   │   └── schemas.py      # Pydantic schemas
│   ├── leaderboard/        # Performance leaderboards
│   │   ├── routes.py       # Leaderboard endpoints
│   │   ├── services.py     # Scoring and ranking logic
│   │   └── benchmarks.py   # Benchmark integrations
│   ├── licensing/          # License management
│   │   ├── routes.py       # License endpoints
│   │   ├── services.py     # License validation
│   │   └── compliance.py   # Compliance checking
│   └── commons/            # Shared utilities
│       ├── config.py       # Configuration
│       ├── database.py     # Database setup
│       └── exceptions.py   # Custom exceptions
├── tests/                  # Test suite
├── scripts/                # Utility scripts
└── deploy/                 # Deployment scripts
```

### Core Components

- **Model Registry**: Centralized metadata storage for AI/ML models
- **Leaderboard Engine**: Performance ranking and comparison system
- **License Manager**: Licensing information and compliance tracking
- **Benchmark Integrator**: Integration with evaluation frameworks
- **Search Engine**: Advanced model discovery and filtering
- **API Layer**: RESTful endpoints for external integrations

### Integration Points

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Hugging Face│     │  Benchmark  │     │   License   │
│   Hub API   │     │  Services   │     │ Databases   │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                    │
       └───────────────────┴────────────────────┘
                           │
                    ┌──────┴──────┐
                    │  BudModel   │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────┴───────┐  ┌───────┴───────┐  ┌──────┴──────┐
│    BudApp     │  │  BudCluster   │  │   BudSim    │
└───────────────┘  └───────────────┘  └─────────────┘
```

## 📦 Prerequisites

### Required

- **Python** 3.8+
- **Docker** and Docker Compose
- **Git**

### Service Dependencies

- **PostgreSQL** - Primary database
- **Redis** - Dapr state store and pub/sub
- **Dapr** - Service mesh and workflows

### Optional Dependencies

- **Hugging Face API Token** - For model metadata synchronization
- **Benchmark APIs** - For performance data collection

## 🚀 Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/BudEcosystem/bud-stack.git
cd bud-stack/services/budmodel

# Setup environment
cp .env.sample .env
# Edit .env with your configuration
```

### 2. Configure Environment

Edit `.env` file with required configurations:

```bash
# Database
DATABASE_URL=postgresql://budmodel:budmodel123@localhost:5432/budmodel

# Redis
REDIS_URL=redis://localhost:6379

# Dapr
DAPR_HTTP_PORT=3510
DAPR_GRPC_PORT=50004
DAPR_API_TOKEN=your-token

# Application
APP_NAME=bud-serve-model
LOG_LEVEL=INFO

# External APIs
HUGGING_FACE_API_TOKEN=your-hf-token
ENABLE_HF_SYNC=true

# Benchmark Integration
ENABLE_BENCHMARK_SYNC=true
BENCHMARK_UPDATE_INTERVAL=3600
```

### 3. Start Development Environment

```bash
# Start development environment
./deploy/start_dev.sh

# Service will be available at:
# API: http://localhost:9084
# API Docs: http://localhost:9084/docs
```

### 4. Initialize Database

```bash
# Run migrations
alembic upgrade head

# Optional: Seed initial model data
python scripts/seed_models.py
```

## 💻 Development

### Code Quality

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
./scripts/install_hooks.sh

# Linting and formatting
ruff check budmodel/ --fix
ruff format budmodel/

# Type checking
mypy budmodel/

# Run all quality checks
./scripts/lint.sh
```

### Database Operations

```bash
# Create migration
alembic revision --autogenerate -m "Add model categories"

# Apply migrations
alembic upgrade head

# Rollback one revision
alembic downgrade -1

# View migration history
alembic history
```

### Data Synchronization

```bash
# Sync models from Hugging Face
python scripts/sync_huggingface_models.py

# Update benchmark data
python scripts/update_benchmarks.py

# Validate license information
python scripts/validate_licenses.py
```

## 📚 API Documentation

### Key Endpoints

#### Model Management
- `GET /models` - List all models with filtering
- `GET /models/{model_id}` - Get detailed model information
- `POST /models` - Register new model
- `PUT /models/{model_id}` - Update model metadata
- `DELETE /models/{model_id}` - Remove model from registry

#### Search & Discovery
- `GET /models/search` - Advanced model search
- `GET /models/categories` - List model categories
- `GET /models/tags` - List available tags
- `GET /models/similar/{model_id}` - Find similar models

#### Leaderboards
- `GET /leaderboards` - List available leaderboards
- `GET /leaderboards/{board_id}` - Get leaderboard rankings
- `POST /leaderboards/{board_id}/submit` - Submit benchmark results
- `GET /leaderboards/{board_id}/history` - Get historical performance

#### Licensing
- `GET /licenses` - List available licenses
- `GET /models/{model_id}/license` - Get model license details
- `POST /models/{model_id}/license/check` - Check license compatibility
- `GET /compliance/report` - Generate compliance report

### Model Search Examples

#### Basic Search
```json
GET /models/search?query=llama&size=7b&type=language_model
```

#### Advanced Filtering
```json
POST /models/search
{
  "filters": {
    "model_type": ["language_model", "vision_model"],
    "license": ["apache-2.0", "mit"],
    "performance": {
      "min_score": 0.8,
      "benchmark": "mmlu"
    },
    "hardware": {
      "supports_gpu": true,
      "min_memory_gb": 16
    }
  },
  "sort_by": "performance_score",
  "limit": 20
}
```

### Leaderboard API Examples

#### Get MMLU Leaderboard
```json
GET /leaderboards/mmlu
{
  "leaderboard_id": "mmlu",
  "name": "MMLU Benchmark",
  "description": "Measuring Massive Multitask Language Understanding",
  "rankings": [
    {
      "rank": 1,
      "model_id": "gpt-4",
      "model_name": "GPT-4",
      "score": 0.867,
      "date_evaluated": "2024-01-15T00:00:00Z"
    }
  ]
}
```

## 🚀 Deployment

### Docker Deployment

```bash
# Build image
docker build -t budmodel:latest .

# Run with docker-compose
docker-compose up -d
```

### Kubernetes Deployment

```bash
# Deploy with Helm
helm install budmodel ./charts/budmodel/

# Or as part of full stack
cd ../../infra/helm/bud
helm dependency update
helm install bud .
```

### Production Configuration

```yaml
# values.yaml for Helm
budmodel:
  replicas: 2
  resources:
    requests:
      memory: "512Mi"
      cpu: "500m"
    limits:
      memory: "2Gi"
      cpu: "2000m"
  env:
    - name: ENABLE_HF_SYNC
      value: "true"
    - name: BENCHMARK_UPDATE_INTERVAL
      value: "7200"
  persistence:
    enabled: true
    size: 10Gi
```

## 🧪 Testing

### Unit Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=budmodel --cov-report=html

# Run specific test module
pytest tests/test_model_registry.py
```

### Integration Tests

```bash
# With Dapr sidecar
pytest tests/integration/ --dapr-http-port 3510 --dapr-api-token $DAPR_API_TOKEN
```

### API Tests

```bash
# Test model search
pytest tests/api/test_search.py

# Test leaderboard APIs
pytest tests/api/test_leaderboards.py

# Test license validation
pytest tests/api/test_licensing.py
```

### Data Validation Tests

```bash
# Validate model metadata
python tests/validation/test_model_metadata.py

# Test benchmark data integrity
python tests/validation/test_benchmark_data.py
```

## 🔧 Troubleshooting

### Common Issues

#### Database Connection Failed
```bash
# Error: Could not connect to database
# Solution: Ensure PostgreSQL is running
docker-compose ps postgres
docker-compose up -d postgres
```

#### Hugging Face API Rate Limit
```bash
# Error: Rate limit exceeded for Hugging Face API
# Solution: Use API token or reduce sync frequency
export HUGGING_FACE_API_TOKEN=your_token
```

#### Missing Benchmark Data
```bash
# Error: No benchmark data available
# Solution: Run initial data sync
python scripts/sync_benchmarks.py --initial-load
```

#### License Validation Failed
```bash
# Error: Could not validate model license
# Solution: Update license database
python scripts/update_license_db.py
```

### Debug Mode

Enable detailed logging:
```bash
# In .env
LOG_LEVEL=DEBUG
ENABLE_SQL_LOGGING=true

# For API debugging
ENABLE_REQUEST_LOGGING=true
```

### Performance Monitoring

```bash
# Check service health
curl http://localhost:9084/health

# Monitor database performance
curl http://localhost:9084/health/db

# Check cache statistics
curl http://localhost:9084/metrics/cache
```

## 🤝 Contributing

Please see the main [Bud Stack Contributing Guide](../../CONTRIBUTING.md).

### Service-Specific Guidelines

1. Follow the data schema patterns for new model types
2. Add comprehensive tests for new benchmark integrations
3. Update API documentation for new endpoints
4. Validate license information accuracy
5. Maintain backward compatibility for API changes

## 📄 License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](../../LICENSE) file for details.

## 🔗 Related Documentation

- [Main Bud Stack README](../../README.md)
- [CLAUDE.md Development Guide](../../CLAUDE.md)
- [API Documentation](http://localhost:9084/docs) (when running)
- [Model Schema Documentation](./docs/model-schema.md)
- [Benchmark Integration Guide](./docs/benchmark-integration.md)
- [License Compliance Guide](./docs/license-compliance.md)