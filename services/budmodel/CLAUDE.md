# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BudModel is a FastAPI-based microservice system for managing and evaluating machine learning models. It's part of the Bud Ecosystem and provides APIs for model information extraction, leaderboard management, and security scanning.

## Development Commands

### Starting the Development Environment
```bash
# Start all services (PostgreSQL, Redis, MinIO, and the app)
./deploy/start_dev.sh

# Start with rebuild
./deploy/start_dev.sh --build

# Start in detached mode
./deploy/start_dev.sh -d

# Skip the app container (useful for running locally)
./deploy/start_dev.sh --skip-app
```

### Stopping Services
```bash
./deploy/stop_dev.sh
```

### Code Quality Commands
```bash
# Run linting with auto-fix
ruff check . --fix

# Format code
ruff format .

# Type checking
mypy .

# Run all pre-commit hooks
pre-commit run --all-files
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_specific.py

# Run with verbose output
pytest -v
```

### Database Migrations
```bash
# Apply all migrations (run inside container or with proper env)
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Rollback one migration
alembic downgrade -1
```

## Architecture Overview

### Core Structure
- `/budmodel/core/`: Database models, schemas, services, and seeders
- `/budmodel/model_info/`: Model extraction, licensing, security scanning
- `/budmodel/leaderboard/`: Model benchmarking and comparison
- `/budmodel/metrics_collector/`: AI benchmark integrations
- `/budmodel/commons/`: Shared utilities, configuration, constants

### API Endpoints
- `/model-info/*`: Model extraction, security scanning, license FAQ
- `/leaderboard/*`: Model comparison and ranking

### Key Dependencies
- **Framework**: FastAPI with async support
- **Database**: PostgreSQL with SQLAlchemy + Alembic
- **Cache/Queue**: Redis
- **Storage**: MinIO for model files
- **Service Mesh**: Dapr for microservice communication
- **ML Libraries**: transformers, OpenAI, Perplexity AI
- **Security**: ClamAV, modelscan

### Configuration
- Environment variables via `.env` file
- Pydantic-based configuration in `/budmodel/commons/config.py`
- Dapr configuration for service mesh features

### Important Services
1. **Main API**: Runs on port configured in `APP_PORT`
2. **PostgreSQL**: Database for model metadata
3. **Redis**: Caching and message queue
4. **MinIO**: Object storage for model files
5. **Dapr**: Service mesh sidecar

### Workflow System
- Dapr workflows for async processing
- Model extraction workflows with progress tracking
- Cron-based leaderboard updates

## Development Guidelines

### Pre-commit Hooks
The project enforces code quality through pre-commit hooks:
- Ruff for linting and formatting
- MyPy for type checking
- Commitlint for conventional commits

### Testing Strategy
- Pytest with async support
- Test files in `/tests/` directory
- Fixtures for database and API testing

### Database Schema
Key tables include:
- `sources`: Data sources for models
- `models`: Model metadata
- `model_info`: Extracted model information
- `leaderboard`: Benchmark data
- `licenses`: License information

### Environment Setup
Required environment variables:
- `APP_NAME`: Application name (default: budmodel)
- `APP_PORT`: API port
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `MINIO_*`: MinIO configuration
- `DAPR_*`: Dapr ports and configuration

### Common Development Tasks

1. **Adding a new API endpoint**: Create route in appropriate module, add schema in `/budmodel/core/schemas/`
2. **Modifying database schema**: Update SQLAlchemy models, create Alembic migration
3. **Adding new model extractor**: Implement in `/budmodel/model_info/extractors/`
4. **Adding benchmark integration**: Create collector in `/budmodel/metrics_collector/`

### Debugging Tips
- Logs are available via Docker: `docker logs bud-serve-eval-app-1`
- Dapr sidecar logs: `docker logs bud-serve-eval-app-dapr-1`
- Database queries can be debugged with SQLAlchemy echo mode
- API docs available at `http://localhost:{APP_PORT}/docs`
