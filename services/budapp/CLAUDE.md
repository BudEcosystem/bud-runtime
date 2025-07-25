# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

Bud Serve App is a FastAPI-based microservice for the Bud Runtime ecosystem that manages AI/ML model deployments, clusters, and endpoints. The application uses:
- **Dapr** for microservice communication and workflow orchestration
- **PostgreSQL** for data persistence with Alembic migrations
- **Redis** for caching and session management
- **MinIO** for model/dataset storage
- **Keycloak** for authentication and multi-tenant support
- **Prometheus/Grafana** for metrics and monitoring

### Module Structure
Each module in `budapp/` follows a consistent pattern:
- `models.py` - SQLAlchemy models
- `schemas.py` - Pydantic schemas for API validation
- `crud.py` - Database operations
- `services.py` - Business logic
- `*_routes.py` - FastAPI route definitions

Key modules:
- `auth/` - Authentication with Keycloak integration
- `cluster_ops/` - Cluster management and workflows
- `model_ops/` - Model management (cloud and local)
- `endpoint_ops/` - Endpoint deployments
- `workflow_ops/` - Dapr workflow definitions
- `commons/` - Shared utilities, config, and dependencies

## Development Commands

### Start Development Environment
```bash
# Start all services (PostgreSQL, Redis, Keycloak, MinIO, Dapr)
./deploy/start_dev.sh

# Stop all services
./deploy/stop_dev.sh
```

### Database Operations
```bash
# Apply migrations
alembic -c ./budapp/alembic.ini upgrade head

# Create new migration
alembic -c ./budapp/alembic.ini revision --autogenerate -m "description"
```

### Testing
```bash
# Run all tests with Dapr
pytest --dapr-http-port 3510 --dapr-api-token <TOKEN>

# Run specific test file
pytest tests/test_cluster_metrics.py --dapr-http-port 3510 --dapr-api-token <TOKEN>
```

### Code Quality
```bash
# Format code with Ruff
ruff format .

# Lint code
ruff check .

# Type checking
mypy budapp/
```

## Key Development Patterns

### API Endpoints
All endpoints follow RESTful conventions with consistent response schemas:
- Use `APIResponseSchema` for standard responses
- Include proper status codes and error handling
- Implement pagination for list endpoints using `PaginationQuery`

### Dapr Workflows
Workflows are defined in `workflows.py` files and registered in `scheduler.py`:
- Each workflow must handle exceptions and update status appropriately
- Use `WorkflowActivityContext` for activity functions
- Store workflow instance IDs in the database for tracking

### Database Models
- All models inherit from `Base` with standard fields (id, created_at, updated_at)
- Use UUID primary keys
- Include proper relationships and indexes
- Handle soft deletes with status fields rather than actual deletion

### Authentication
- All protected endpoints require JWT tokens via `get_current_user` dependency
- Multi-tenant support through Keycloak realms
- Role-based access control with permissions stored in database

### Error Handling
- Use custom exceptions from `commons/exceptions.py`
- Implement proper error responses with meaningful messages
- Log errors with structured logging via structlog

## Environment Configuration

Required environment variables (see `.env.sample`):
- Database: `POSTGRES_*`
- Redis: `REDIS_*`
- Keycloak: `KEYCLOAK_*`
- MinIO: `MINIO_*`
- Dapr: `DAPR_*`
- Application: `APP_NAME`, `SECRET_KEY`, `ALGORITHM`

## Testing Guidelines

- Tests require Dapr to be running
- Use async test functions with `pytest.mark.asyncio`
- Mock external services (Keycloak, MinIO) in tests
- Test database operations use transactions that rollback after each test
- Include both positive and negative test cases