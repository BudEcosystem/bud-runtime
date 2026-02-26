# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BudUseCases is a FastAPI-based microservice that provides pre-configured GenAI deployment templates and orchestration. It enables users to deploy common GenAI use cases (RAG, Chatbots, etc.) with minimal configuration by providing:

- **Template System**: YAML-based deployment templates for common use cases
- **Deployment Orchestration**: Coordinates multi-component deployments through BudCluster

## Architecture

### Service Structure
```
budusecases/
├── commons/          # Shared utilities and configuration
│   └── config.py     # Application and secrets configuration
├── templates/        # Template System module
│   ├── models.py     # SQLAlchemy models (Template, TemplateComponent)
│   ├── schemas.py    # Pydantic schemas
│   ├── loader.py     # YAML template loader
│   ├── services.py   # Business logic
│   └── routes.py     # REST API endpoints
├── deployments/      # Deployment Orchestration module
│   ├── models.py     # SQLAlchemy models (UseCaseDeployment)
│   ├── schemas.py    # Pydantic schemas
│   ├── services.py   # Orchestration logic
│   ├── workflows.py  # Dapr workflows
│   └── routes.py     # REST API endpoints
└── main.py           # FastAPI application entry point
```

### Key Concepts

**Templates**: YAML definitions of deployable use cases
- Define required component types and configurations
- Specify deployment parameters and resource requirements
- Stored in `templates/` directory, synced to database on startup

**Deployments**: Instances of templates deployed to clusters
- Track deployment status across multiple components
- Integrate with BudCluster Job tracking system
- Support multi-stage deployments with dependencies

## Development Commands

### Setup and Running
```bash
# Copy environment file
cp .env.sample .env

# Start development environment
./deploy/start_dev.sh --build

# Stop environment
./deploy/stop_dev.sh

# Run without rebuilding
./deploy/start_dev.sh
```

### Code Quality
```bash
# Linting and formatting
ruff check budusecases/ --fix
ruff format budusecases/

# Type checking
mypy budusecases/

# Run all pre-commit hooks
pre-commit run --all-files
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_components.py -v

# Run with coverage
pytest --cov=budusecases
```

### Database Operations
```bash
# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Check current migration
alembic current
```

## Configuration

Environment variables in `.env`:
- `APP_NAME`: Service name (budusecases)
- `APP_PORT`: HTTP port (9084)
- `DAPR_HTTP_PORT`: Dapr sidecar HTTP port (3512)
- `TEMPLATES_PATH`: Path to YAML templates directory
- `TEMPLATES_SYNC_ON_STARTUP`: Sync YAML templates to DB on startup
- `BUDCLUSTER_APP_ID`: Dapr app ID for BudCluster service

## Integration with BudCluster

BudUseCases integrates with BudCluster for deployment orchestration:

1. **Job Creation**: Each component deployment creates a Job in BudCluster
2. **Status Tracking**: Deployment status synced from BudCluster Jobs
3. **Service Invocation**: Uses Dapr service invocation to communicate with BudCluster

### Job Source Mapping
- Source: `BUDUSECASES`
- Source ID: UseCaseDeployment UUID
- Job Type: Based on component type (MODEL_DEPLOYMENT, etc.)

## Development Patterns

### Creating New Templates
1. Create YAML file in `templates/` directory
2. Define template metadata and component requirements
3. Restart service or call sync endpoint to load

### Template YAML Structure
```yaml
name: simple-rag
version: "1.0"
description: Simple RAG application
components:
  - name: llm
    type: model
    required: true
    default_component: llama-3-8b
  - name: embedder
    type: model  # All ML models use type: model
    required: true
    default_component: bge-large-en
parameters:
  chunk_size:
    type: integer
    default: 512
  retrieval_k:
    type: integer
    default: 5
```

## Testing Patterns

- Use `pytest-asyncio` for async route testing
- Mock Dapr client for service invocation tests
- Use factories for test data generation
- Test template loading from fixtures

## Technical Stack

- **Framework**: FastAPI with Dapr sidecars
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Migrations**: Alembic
- **Validation**: Pydantic v2 schemas
- **Templates**: YAML with PyYAML
- **Testing**: pytest with asyncio support
- **Code Quality**: Ruff, MyPy
