# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bud-stack is a comprehensive multi-service platform for AI/ML model deployment and cluster management. It consists of seven main services:

### Backend Services (Python/FastAPI)
- **budapp**: Main application service handling user management, projects, models, endpoints, and AI/ML workflow orchestration with Keycloak authentication
- **budcluster**: Cluster lifecycle management service that provisions and manages Kubernetes/OpenShift clusters across multiple clouds (AWS EKS, Azure AKS, on-premises) using Terraform and Ansible
- **budsim**: Performance simulation service that uses ML models and genetic algorithms to optimize LLM deployment configurations across CPU/CUDA/HPU hardware
- **budmodel**: Model registry and leaderboard service managing model metadata, licensing, and performance metrics from various AI benchmarks
- **budmetrics**: Observability service built on ClickHouse for analytics and time-series metrics collection
- **budnotify**: Notification service for pub/sub messaging across the platform
- **ask-bud**: AI assistant service providing cluster and performance analysis capabilities
- **budgateway**: Rust-based high-performance API gateway service for model inference routing and load balancing

### Frontend Service (TypeScript/Next.js)
- **budadmin**: Next.js 14 dashboard application for managing AI/ML model deployments and infrastructure with real-time updates via Socket.io

The platform uses Dapr for distributed runtime capabilities, Terraform/Ansible for infrastructure automation, and Helm for Kubernetes deployments.

## Repository Structure

```
bud-stack/
├── services/
│   ├── budapp/              # Main application service (users, projects, models, endpoints)
│   ├── budcluster/          # Cluster management service (AWS EKS, Azure AKS, on-premises)
│   ├── budsim/              # Performance simulation service (ML optimization)
│   ├── budmodel/            # Model registry and leaderboard service
│   ├── budmetrics/          # Observability service (ClickHouse analytics)
│   ├── budnotify/           # Notification service (pub/sub messaging)
│   ├── ask-bud/             # AI assistant service
│   ├── budgateway/          # Rust API gateway service (high-performance inference routing)
│   ├── budadmin/            # Next.js 14 frontend dashboard
│   ├── budeval/             # Evaluation service (AI model benchmarking)
│   └── budplayground/       # Interactive playground interface
├── infra/
│   ├── terraform/           # Infrastructure as code (multi-cloud)
│   └── helm/               # Main Helm chart with dependencies
└── nix/                    # Nix development environment
```

## Development Environment Setup

### Nix Shell (Recommended)
```bash
# Enter development shell with all tools
nix develop

# Or use specific shell
nix develop .#bud
```

### Individual Services
Each service has its own development setup:

```bash
# Backend Python services (FastAPI with Dapr) - use --build flag for first run
cd services/budapp && ./deploy/start_dev.sh
cd services/budcluster && ./deploy/start_dev.sh --build
cd services/budsim && ./deploy/start_dev.sh --build
cd services/budmodel && ./deploy/start_dev.sh
cd services/budmetrics && ./deploy/start_dev.sh
cd services/budnotify && ./deploy/start_dev.sh
cd services/ask-bud && ./deploy/start_dev.sh

# Frontend dashboard (Next.js 14)
cd services/budadmin && npm install && npm run dev  # Starts on http://localhost:8007

# Rust gateway service
cd services/budgateway && cargo run

# Stop services
cd services/<service_name> && ./deploy/stop_dev.sh  # For Python services
```

## Common Development Commands

### Code Quality (Run from service directories)

#### Python Services (budapp, budcluster, budsim, budmodel, budmetrics, budnotify, ask-bud)
```bash
# Linting and formatting
ruff check . --fix
ruff format .

# Type checking
mypy <service_name>/  # e.g., mypy budapp/

# Run all tests
pytest

# Run specific test
pytest tests/test_specific.py::test_function

# Run tests with Dapr (required for most services)
pytest --dapr-http-port 3510 --dapr-api-token <YOUR_DAPR_API_TOKEN>

# Install pre-commit hooks for code quality
./scripts/install_hooks.sh
```

#### Frontend Service (budadmin)
```bash
# Development server (runs on port 8007)
npm run dev

# Linting and building
npm run lint
npm run build

# Production server
npm run start
```

#### Rust Service (budgateway)
```bash
# Format code
cargo fmt

# Lint code
cargo clippy

# Run tests
cargo test

# Build project
cargo build --release
```

### Database Operations
```bash
# Run migrations (from service directory with PostgreSQL)
alembic upgrade head

# Service-specific migrations
alembic -c ./budapp/alembic.ini upgrade head      # budapp
alembic upgrade head                              # budcluster, budsim, budmodel

# For budmetrics (ClickHouse)
cd services/budmetrics && python scripts/migrate_clickhouse.py

# Create new migration
alembic revision --autogenerate -m "description"
alembic -c ./budapp/alembic.ini revision --autogenerate -m "description"  # budapp specific
```

### Infrastructure Operations
```bash
# Deploy main Helm chart with dependencies
helm install bud infra/helm/bud/

# Update Helm dependencies
helm dependency update infra/helm/bud/

# Apply Terraform (from infra/terraform/)
tofu plan
tofu apply

# Nix development tools
nix develop  # Enter development shell with k3d, kubectl, helm, opentofu, azure-cli
```

## Architecture Overview

### Service Communication
- **Dapr Sidecar Pattern**: All backend services run with Dapr sidecars for service mesh capabilities
- **State Management**: Redis/Valkey for pub/sub and state store across all services
- **Configuration**: Environment-based config via `.env` files and Dapr components with periodic sync
- **Service Discovery**: Dapr service invocation for inter-service communication
- **Frontend API**: budadmin communicates with budapp via REST API with automatic token refresh

### Data Flow
1. **User Management**: budapp handles authentication via Keycloak, projects, and user workflows
2. **Model Registry**: budmodel manages AI/ML model metadata, licensing, and leaderboard data
3. **Model Management**: budapp manages model deployments, datasets, and endpoints
4. **Cluster Registration**: budcluster registers new clusters and provisions infrastructure via Terraform/Ansible
5. **Performance Optimization**: budsim analyzes optimal deployment configurations using ML and genetic algorithms
6. **Model Deployment**: budcluster deploys models to clusters based on optimization results
7. **Observability**: budmetrics collects time-series data in ClickHouse for analytics
8. **Notifications**: budnotify handles pub/sub messaging across services
9. **AI Assistance**: ask-bud provides intelligent cluster and performance analysis

### Key Technologies
- **Python 3.10+** with FastAPI and budmicroframe for REST APIs
- **Rust** for high-performance gateway service (budgateway)
- **SQLAlchemy + Alembic** for PostgreSQL ORM and migrations
- **ClickHouse** for time-series analytics (budmetrics)
- **Pydantic** for data validation and serialization
- **Dapr** for distributed runtime (pub/sub, state, workflows, service mesh)
- **Next.js 14 + TypeScript** for frontend dashboard with Zustand state management
- **Kubernetes/Helm** for container orchestration
- **Terraform/OpenTofu** for multi-cloud infrastructure provisioning
- **Ansible** for configuration management and cluster operations
- **Keycloak** for authentication and multi-tenant support
- **MinIO** for object storage (models/datasets)
- **XGBoost + DEAP** for ML-based performance optimization (budsim)

### Frontend Architecture (budadmin)
- **Framework**: Next.js 14 with React 18 and TypeScript
- **State Management**: Zustand stores for client-side state
- **UI Components**: Tailwind CSS + Ant Design + Radix UI
- **Authentication**: JWT tokens with automatic refresh
- **API Communication**: Custom axios wrapper with error handling
- **Real-time Updates**: Socket.io integration
- **Key Features**: Model management, cluster operations, benchmarking, project organization

## Security & Configuration

### Crypto Keys (budcluster only)
Required for cluster credential encryption in budcluster service:
```bash
cd services/budcluster
mkdir -p crypto-keys
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -out crypto-keys/rsa-private-key.pem
openssl rand -out crypto-keys/symmetric-key-256 32
chmod 644 crypto-keys/rsa-private-key.pem crypto-keys/symmetric-key-256
```

### Environment Variables
Each service requires `.env` file (copy from `.env.sample`):
- **budapp**: Database, Redis, Keycloak, MinIO, Dapr, authentication configuration
- **budcluster**: Database, Redis, Dapr, cloud provider credentials, crypto keys
- **budsim**: Database, Redis, Dapr, ML model cache configuration
- **budmodel**: Database, Redis, Dapr, Hugging Face API tokens
- **budmetrics**: ClickHouse, Redis, Dapr configuration
- **budnotify**: Redis, Dapr, notification provider credentials
- **ask-bud**: Database, Redis, Dapr, AI model configuration
- **budgateway**: Redis, gateway configuration, model routing settings
- **budadmin**: `NEXT_PUBLIC_BASE_URL`, `NEXT_PUBLIC_NOVU_*`, authentication keys

## Development Guidelines

### Code Standards
- Follow **Conventional Commits** for commit messages (feat, fix, docs, etc.)
- Use **Ruff** for linting/formatting with Google docstring convention
- Maintain **MyPy** type annotations for all functions
- Write tests for new functionality using **pytest** with asyncio support

### Service Patterns (consistent across all services)

#### Python Backend Services (budapp, budcluster, budsim, budmodel, budmetrics, budnotify, ask-bud)
- **API Layer**: Routes in `*_routes.py` (budapp) or `routes.py` (other services)
- **Business Logic**: Services in `services.py`
- **Data Access**: CRUD operations in `crud.py`
- **Database Models**: SQLAlchemy models in `models.py`
- **Data Validation**: Pydantic schemas in `schemas.py`
- **Workflows**: Long-running Dapr workflows in `workflows.py`
- **Configuration**: Using budmicroframe for consistent config management

#### Rust Gateway Service (budgateway)
- **Configuration**: TOML-based configuration in `config/`
- **Route Handlers**: HTTP route handling in `gateway/src/`
- **Model Integration**: Provider proxy patterns for various AI model APIs
- **Load Balancing**: High-performance request routing and load balancing

#### Frontend Service (budadmin)
- **Pages**: Next.js pages in `/src/pages/`
- **Components**: Reusable UI components in `/src/components/`
- **Flows**: Multi-step workflows in `/src/flows/`
- **State**: Zustand stores in `/src/stores/`
- **Hooks**: Custom React hooks in `/src/hooks/`
- **API Layer**: Centralized API client in `/src/pages/api/requests.ts`

### Pre-commit Hooks
All services use pre-commit hooks for code quality:
```bash
./scripts/install_hooks.sh  # Run from service directory
```

## Infrastructure Management

### Helm Dependencies
Main chart (`infra/helm/bud/`) includes:
- **PostgreSQL**: Primary database for budapp, budcluster, budsim, budmodel, ask-bud
- **Valkey/Redis**: State store and pub/sub for all services
- **ClickHouse**: Analytics database for budmetrics
- **Dapr**: Service mesh and workflow orchestration for all backend services
- **MinIO**: Object storage for models and datasets (budapp)
- **Keycloak**: Authentication and multi-tenant support (budapp)
- **MongoDB**: Document storage for specific use cases
- **Kafka**: Event streaming for high-throughput scenarios
- **LGTM Stack**: Grafana, Loki, Tempo, Mimir for observability

### Cloud Providers
- **Azure**: Primary cloud with AKS clusters via Terraform modules
- **AWS**: EKS support via Terraform modules
- **On-premises**: OpenShift support via Ansible playbooks

### Deployment Workflow
1. **Infrastructure Provisioning**: Terraform/Ansible automation via budcluster
2. **Cluster Registration**: Validation and credential encryption via budcluster
3. **Model Registration**: Metadata and licensing via budmodel
4. **Service Deployment**: Helm charts orchestration via budcluster
5. **Performance Optimization**: ML-based analysis via budsim
6. **Model Deployment**: Orchestration via budcluster + budapp coordination
7. **Observability**: Metrics collection via budmetrics + notification via budnotify
8. **AI Assistance**: Intelligent analysis and recommendations via ask-bud

## Troubleshooting

### Common Issues
- **Missing Dapr API Token**: Required for tests, check `.env` file in each service
- **Database Connection**: Ensure PostgreSQL is running via docker-compose for each service
- **ClickHouse Connection**: budmetrics requires ClickHouse, check docker-compose-clickhouse.yaml
- **Crypto Keys Missing**: Run key generation commands for budcluster service
- **Port Conflicts**: Each service uses different ports (check respective docker-compose files)
- **Frontend API Connection**: Ensure `NEXT_PUBLIC_BASE_URL` points to correct budapp backend
- **Service Dependencies**: Some services depend on others (e.g., budapp needs budmodel, budmetrics)
- **Nix Environment**: Use `nix develop` for consistent tooling across development

### Development Tools
Available in Nix shell:
- `kubectl`, `helm` for Kubernetes operations and chart management
- `k3d` for local cluster testing and development
- `opentofu` for Terraform operations (OpenTofu as Terraform alternative)
- `azure-cli` for Azure management and AKS operations
- `sops` for secret encryption and GitOps workflows
- `openssl` for crypto key generation (budcluster)
- `yaml-language-server` for YAML validation and linting


### Claude dev guidelines

- Use sub agents when ever required
- Use the stack-keeper agent to plan the development task and distribute to respective agents.
