# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bud AI Foundry is a control panel for GenAI deployments, designed to maximize infrastructure performance. The platform manages AI/ML model deployment, cluster lifecycle, and infrastructure optimization across multi-cloud environments.

### Services

**Backend Services (Python/FastAPI)**
| Service | Purpose | Database |
|---------|---------|----------|
| budapp | Main API: users, projects, models, endpoints, Keycloak auth | PostgreSQL |
| budcluster | Cluster lifecycle: AWS EKS, Azure AKS, on-premises via Terraform/Ansible | PostgreSQL |
| budsim | Performance simulation: XGBoost + genetic algorithms for deployment optimization | PostgreSQL |
| budmodel | Model registry: metadata, licensing, leaderboard data | PostgreSQL |
| budmetrics | Observability: inference tracking, time-series analytics | ClickHouse |
| budnotify | Notifications via Novu wrapper | MongoDB |
| ask-bud | AI assistant for cluster/performance analysis | PostgreSQL |
| budeval | Model evaluation and benchmarking | PostgreSQL |

**Rust Service**
| Service | Purpose |
|---------|---------|
| budgateway | High-performance API gateway for model inference routing (forked from TensorZero) |

**Frontend Services (TypeScript/Next.js)**
| Service | Purpose | Port |
|---------|---------|------|
| budadmin | Main dashboard for deployments and infrastructure | 8007 |
| budplayground | Interactive AI model testing interface | - |
| budCustomer | Customer-facing portal | - |

**Infrastructure**
- `infra/helm/` - Main Helm chart with all dependencies
- `infra/tofu/` - Terraform/OpenTofu modules for multi-cloud

## Quick Start

### Development Environment
```bash
# Nix shell (recommended) - includes Python 3.11, Node 20, Rust, Dapr tooling
nix develop

# Install pre-commit hooks after cloning
./scripts/install_hooks.sh
```

### Running Services
```bash
# Python services - use --build for first run
cd services/<service_name> && ./deploy/start_dev.sh --build
./deploy/stop_dev.sh  # to stop

# Frontend
cd services/budadmin && npm install && npm run dev

# Rust gateway
cd services/budgateway && cargo run
```

### Key Ports
- budapp API: 9081 (docs at /docs)
- budadmin: 8007

## Development Commands

### Python Services
```bash
ruff check . --fix && ruff format .  # Lint and format
mypy <service_name>/                 # Type check
pytest                               # Run tests
pytest tests/test_file.py::test_fn   # Run specific test
pytest --dapr-http-port 3510 --dapr-api-token <TOKEN>  # With Dapr
```

### Frontend Services
```bash
npm run dev        # Development server
npm run lint       # Lint
npm run typecheck  # Type check
npm run build      # Production build
```

### Rust Service (budgateway)
```bash
cargo fmt                  # Format
cargo clippy --all-targets --all-features -- -D warnings  # Lint
cargo test --workspace     # Test
cargo build --release      # Build
```

### Pre-commit
```bash
pre-commit run --all-files  # Run all hooks manually (CI mirrors this)
```

### Database Migrations
```bash
# PostgreSQL (most services)
alembic upgrade head
alembic revision --autogenerate -m "description"

# budapp specific
alembic -c ./budapp/alembic.ini upgrade head

# ClickHouse (budmetrics)
python scripts/migrate_clickhouse.py
```

### Infrastructure
```bash
helm install bud infra/helm/bud/      # Deploy Helm chart
helm dependency update infra/helm/bud/ # Update dependencies
cd infra/tofu && tofu plan && tofu apply  # OpenTofu
```

## Architecture

### Service Communication
- **Dapr Sidecar Pattern**: All Python services run with Dapr for service mesh
- **State Store**: Redis/Valkey for pub/sub and state across services
- **Workflows**: Dapr workflows for long-running operations (simulations, provisioning)
- **Inter-service**: Dapr service invocation with retry/circuit breaking

### Code Patterns (consistent across Python services)
```
<service>/
├── routes.py      # FastAPI endpoints (*_routes.py in budapp)
├── services.py    # Business logic
├── crud.py        # Database operations
├── models.py      # SQLAlchemy models
├── schemas.py     # Pydantic schemas
└── workflows.py   # Dapr workflows
```

### Frontend Pattern (budadmin)
```
src/
├── pages/         # Next.js pages
├── components/    # Reusable UI components
├── flows/         # Multi-step workflows
├── stores/        # Zustand state stores
├── hooks/         # Custom React hooks
└── pages/api/requests.ts  # Centralized API client
```

### Naming Conventions
- **Python**: snake_case modules, PascalCase Pydantic models, 119-char line limit
- **TypeScript**: PascalCase React components, colocated styles
- **Rust**: kebab-case module directories, CamelCase types

## Configuration

### Environment Setup
Each service needs `.env` (copy from `.env.sample`):
- **budcluster**: Also requires crypto keys for credential encryption:
```bash
mkdir -p crypto-keys
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -out crypto-keys/rsa-private-key.pem
openssl rand -out crypto-keys/symmetric-key-256 32
chmod 644 crypto-keys/rsa-private-key.pem crypto-keys/symmetric-key-256
```

### Key Dependencies (Helm chart)
PostgreSQL, Valkey/Redis, ClickHouse, Dapr, MinIO, Keycloak, MongoDB, Kafka, LGTM stack (Grafana, Loki, Tempo, Mimir)

## Testing Guidelines

### Python Testing Pitfalls

**SQLAlchemy Mocking** - Mock DataManagerUtils methods, not `session.query()`:
```python
# Correct
data_manager.execute_scalar = Mock(return_value=5)
data_manager.scalars_all = Mock(return_value=[])

# Wrong - won't work with modern SQLAlchemy
mock_session.query = Mock(return_value=mock_query)
```

**CRUD Methods** - Pass individual parameters, not schema objects:
```python
# Correct
data_manager.create_audit_record(
    action=AuditActionEnum.CREATE,
    resource_type=AuditResourceTypeEnum.PROJECT,
    resource_id=uuid4(),
    user_id=uuid4(),
    details={"key": "value"}
)

# Wrong
data_manager.create_audit_record(AuditRecordCreate(...))
```

**Pydantic Mocks** - Include ALL required fields when mocking for validation.

**Serialization** - Use compact JSON (`{"a":1}` not `{"a": 1}`) and lowercase booleans (`"true"` not `"True"`).

See `services/budapp/TESTING_GUIDELINES.md` for detailed examples.

## Service-Specific Notes

### BudSim Optimization Methods
- **REGRESSOR**: ML-based genetic algorithm optimizing all engine parameters
- **HEURISTIC**: Memory-based calculations optimizing only TP/PP parameters
- Select via `simulation_method` parameter; use `_is_heuristic_config()` to detect method

### BudCluster
- **Max Model Length**: Dynamically calculated as `(input_tokens + output_tokens) * 1.1`
- **NFD**: Node Feature Discovery for hardware detection (timeout: `NFD_DETECTION_TIMEOUT`)
- **HAMI**: GPU time-slicing auto-installed during cluster onboarding when NVIDIA GPUs detected

### BudGateway
- Forked from TensorZero
- TOML-based configuration in `config/`
- Provider proxy patterns for AI model APIs

## Commit Guidelines

Follow Conventional Commits: `feat(budadmin): ...`, `fix(budmodel): ...`

PRs must include:
- Scope and linked issues
- Migration steps if applicable
- Testing block with commands run
- Secret/IAM/Dapr updates called out explicitly

## Claude Code Usage

- Use subagents proactively for complex tasks
- Use **stack-keeper** agent to plan and distribute tasks across services
- Each service has its own CLAUDE.md with service-specific guidance
- Security is high priority: never store keys as plain text

### Planning & Research

When planning any non-trivial task, conduct extensive web-based research before implementation:
- **SOTA papers**: Search for state-of-the-art approaches and recent publications
- **Best practices**: Look up industry standards and recommended patterns
- **Documentation**: Check official docs for libraries, frameworks, and APIs involved
- **GitHub discussions**: Search for relevant issues, discussions, and solutions
- **GitHub code**: Find reference implementations and real-world examples
- **Articles/blogs**: Look for tutorials and experience reports from practitioners

This research phase should inform the implementation plan and help avoid reinventing solutions or missing established patterns.
