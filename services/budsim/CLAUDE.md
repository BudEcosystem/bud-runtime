# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BudServe Simulator (`budsim`) is a microservice that simulates and optimizes LLM deployment configurations. It uses machine learning models to predict performance metrics and genetic algorithms to find optimal deployment strategies across different hardware configurations (CPU, CUDA, HPU).

## Architecture

The project follows a microservice architecture using:
- **FastAPI** via budmicroframe for API endpoints
- **Dapr** for service mesh capabilities (pub/sub, state management)
- **PostgreSQL** for persistent storage with Alembic migrations
- **Redis** for pub/sub and state store
- **XGBoost** regressors for performance prediction
- **DEAP** genetic algorithms for optimization

Key directories:
- `budsim/simulator/`: Core simulation logic including routes, services, and evolution algorithms
- `budsim/engine_ops/`: Engine-specific operations (VLLM, SGLang, LiteLLM, LLMC)
- `budsim/model_ops/`: Model analysis and operations
- `cache/pretrained_models/`: Pre-trained ML models for different hardware types

## Development Commands

### Setup and Running

```bash
# Initial setup
cp .env.sample .env
./scripts/install_hooks.sh

# Start development environment
./deploy/start_dev.sh

# Start with rebuild
./deploy/start_dev.sh --build

# Stop environment
./deploy/stop_dev.sh
```

### Code Quality

```bash
# Linting and formatting
ruff check . --fix
ruff format .

# Type checking
mypy budsim/

# Run all pre-commit hooks
pre-commit run --all-files
```

### Testing

```bash
# Run all tests (requires Dapr token from .env)
pytest --dapr-http-port 3510 --dapr-api-token <YOUR_DAPR_API_TOKEN>

# Run specific test
pytest tests/test_engine_vllm.py -v
```

### Database Operations

```bash
# Run migrations (automatic in docker-compose)
alembic upgrade head

# Create new migration
alembic revision -m "Description"

# Check migration status
alembic current
```

## Key Implementation Notes

1. **API Structure**: Main endpoint is `/simulator/run` in `budsim/simulator/routes.py`

2. **Hardware Support**: Different pre-trained models exist for CPU, CUDA, and HPU in `cache/pretrained_models/`

3. **Engine Abstraction**: All LLM engines follow a common interface defined in engine_ops modules

4. **Performance Prediction**: Uses XGBoost regressors trained on benchmark data to predict:
   - Time to First Token (TTFT)
   - Output token throughput
   - End-to-end latency

5. **Optimization**: Genetic algorithms in `budsim/simulator/evolution.py` optimize deployment configurations

6. **Configuration**: Environment-based configuration via `.env` file and Dapr state store

7. **Logging**: Comprehensive logging configured through budmicroframe

## Testing Patterns

- Use `pytest-asyncio` for async route testing
- Mock Dapr state store and pub/sub in tests
- Test fixtures defined in `tests/conftest.py`
- Integration tests require running Dapr sidecar

## Common Development Tasks

When modifying the simulator:
1. Update schemas in `budsim/simulator/schemas.py` for new request/response formats
2. Implement business logic in `budsim/simulator/services.py`
3. Add new routes in `budsim/simulator/routes.py`
4. Update tests in `tests/` directory
5. Run linting and type checking before committing

When adding new engine support:
1. Create new module in `budsim/engine_ops/`
2. Implement common interface methods
3. Add engine-specific configurations
4. Update `ENGINE_COMPATIBILITY_MAPPING` in commons
