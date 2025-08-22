# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BudPrompt is a full-featured platform for designing, testing, comparing, and deploying LLM prompts. It's built as a microservice using FastAPI, PostgreSQL, Redis, and Dapr for distributed application runtime.

## Common Development Commands

### Quick Start
```bash
# Start development environment with all services
./deploy/start_dev.sh

# Start with rebuild
./deploy/start_dev.sh --build

# Run in background
./deploy/start_dev.sh -d
```

### Code Quality
```bash
# Run linting
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
# First, start the application
./deploy/start_dev.sh

# Wait for containers to be ready, then run tests inside the container
docker exec -it budserve-development-budprompt pytest tests/test_health.py -v

# Run all tests
docker exec -it budserve-development-budprompt pytest

# Run specific test
docker exec -it budserve-development-budprompt pytest path/to/test_file.py -k "test_name"

# Run with verbose output
docker exec -it budserve-development-budprompt pytest -v -s
```

### Database
```bash
# Create new migration
alembic -c ./alembic.ini revision --autogenerate -m "description"

# Apply migrations
alembic -c ./alembic.ini upgrade head

# View migration history
alembic -c ./alembic.ini history
```

## Architecture Overview

### Framework Foundation
Built on `budmicroframe`, a custom microservices framework providing:
- Base configuration management (`BaseAppConfig`, `BaseSecretsConfig`)
- Dapr workflow integration
- PostgreSQL base models
- Application lifecycle management

### Project Structure
```
budprompt/
├── main.py          # FastAPI app with lifespan management
├── commons/         # Shared utilities
│   ├── config.py    # AppConfig and SecretsConfig classes
│   ├── constants.py # Application constants
│   └── exceptions.py # Custom exception hierarchy
├── prompt/          # Main module (follow this pattern for new modules)
│   ├── routes.py    # API endpoints
│   ├── models.py    # SQLAlchemy models
│   ├── schemas.py   # Pydantic schemas
│   ├── services.py  # Business logic
│   ├── crud.py      # Database operations
│   └── workflows.py # Dapr workflows
└── shared/          # Additional shared components
```

### Key Technologies
- **Web Framework**: FastAPI with async support
- **Database**: PostgreSQL with SQLAlchemy 2.0
- **ORM**: SQLAlchemy with Alembic migrations
- **Validation**: Pydantic for request/response schemas
- **Distributed Runtime**: Dapr for microservice concerns
- **Caching**: Redis
- **Logging**: Structlog

### Dapr Integration
The application uses Dapr for:
- Service-to-service communication
- State management (Redis)
- Pub/Sub messaging (Redis)
- Secret management
- Configuration store
- Workflow orchestration

### Development Patterns

1. **Adding New Features**: Create a new module following the `prompt/` pattern
2. **API Routes**: Use FastAPI router pattern in `routes.py`
3. **Database Models**: Extend SQLAlchemy models in `models.py`
4. **Business Logic**: Implement in `services.py`, keep routes thin
5. **Configuration**: Extend `AppConfig` or `SecretsConfig` in `commons/config.py`

### Database Schema
Current tables focus on workflow management:
- `workflow_runs`: Workflow execution tracking
- `workflow_steps`: Individual step execution

Use Alembic for all schema changes.

### Environment Configuration
Key environment variables (see `.env.sample`):
- `APP_NAME=budprompt`
- `APP_PORT=9088`
- `NAMESPACE=development`
- `LOG_LEVEL=DEBUG`
- Database and Redis connection strings

### Docker Development
- Main app runs with hot-reload enabled
- Dapr sidecar handles distributed concerns
- All services included in docker-compose-dev.yaml
- Migrations run automatically on startup

### Important Notes
- The `prompt/` module is scaffolded but not yet implemented
- Always use Alembic for database changes
- Configuration syncs periodically from Dapr configuration store
- Pre-commit hooks enforce code quality standards
- Ruff is configured for 119 character line length

# Code Quality (*VERY IMPORTANT*)
- Use the following design patterns on planning the code **VERY IMPORTANT**
    - https://refactoring.guru/design-patterns/catalog
- Do a research on the codebase before writing and planning the code
- If you are not sure about what to do, ask me for help
- Make sure to follow single responsibility, Solid, DRY, etc. principles.
- When creating a new file or directory, make sure to follow the project structure and file structure from docs/microservice_guidelines.md
- New envs should be added to the .env.sample file
