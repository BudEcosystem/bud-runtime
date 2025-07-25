# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bud-stack is a multi-service platform for AI/ML model deployment and cluster management. It consists of four main services:

### Backend Services (Python/FastAPI)
- **budapp**: Main application service handling user management, projects, models, endpoints, and AI/ML workflow orchestration
- **budcluster**: Cluster lifecycle management service that provisions and manages Kubernetes/OpenShift clusters across multiple clouds (AWS EKS, Azure AKS, on-premises)
- **budsim**: Performance simulation service that uses ML models and genetic algorithms to optimize LLM deployment configurations

### Frontend Service (TypeScript/Next.js)
- **budadmin**: Next.js dashboard application for managing AI/ML model deployments and infrastructure with real-time updates

The platform uses Dapr for distributed runtime capabilities, Terraform/Ansible for infrastructure automation, and Helm for Kubernetes deployments.

## Repository Structure

```
bud-stack/
├── services/
│   ├── budapp/              # Main application service (users, projects, models)
│   ├── budcluster/          # Cluster management service
│   ├── budsim/              # Performance simulation service
│   └── budadmin/            # Next.js frontend dashboard
├── infra/
│   ├── terraform/           # Infrastructure as code (Azure)
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
# For budapp (main application service)
cd services/budapp
./deploy/start_dev.sh

# For budcluster
cd services/budcluster
./deploy/start_dev.sh --build

# For budsim  
cd services/budsim
./deploy/start_dev.sh --build

# For budadmin (frontend dashboard)
cd services/budadmin
npm run dev  # Starts on http://localhost:8007
```

## Common Development Commands

### Code Quality (Run from service directories)

#### Python Services (budapp, budcluster, budsim)
```bash
# Linting and formatting
ruff check . --fix
ruff format .

# Type checking
mypy budapp/  # or budcluster/ or budsim/

# Run all tests
pytest

# Run specific test
pytest tests/test_specific.py::test_function

# Run tests with Dapr (for services that require it)
pytest --dapr-http-port 3510 --dapr-api-token <YOUR_DAPR_API_TOKEN>
```

#### Frontend Service (budadmin)
```bash
# Linting and building
npm run lint
npm run build

# Development server
npm run dev

# Production server  
npm run start
```

### Database Operations
```bash
# Run migrations (from service directory)
alembic upgrade head

# For budapp specifically
alembic -c ./budapp/alembic.ini upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# For budapp specifically  
alembic -c ./budapp/alembic.ini revision --autogenerate -m "description"
```

### Infrastructure Operations
```bash
# Deploy main Helm chart
helm install bud infra/helm/bud/

# Apply Terraform (from infra/terraform/)
tofu plan
tofu apply
```

## Architecture Overview

### Service Communication
- **Dapr Sidecar Pattern**: All services run with Dapr sidecars for service mesh capabilities
- **State Management**: Redis for pub/sub and state store
- **Configuration**: Environment-based config via `.env` files and Dapr components
- **Service Discovery**: Dapr service invocation for inter-service communication

### Data Flow
1. **User Management**: budapp handles authentication, projects, and user workflows
2. **Model Management**: budapp manages AI/ML models, datasets, and endpoints
3. **Cluster Registration**: budcluster registers new clusters and provisions infrastructure
4. **Performance Optimization**: budsim analyzes optimal deployment configurations
5. **Model Deployment**: budcluster deploys models to clusters based on optimization results
6. **Monitoring**: All services provide health and performance metrics via Dapr workflows

### Key Technologies
- **Python 3.8+** with FastAPI for REST APIs
- **SQLAlchemy + Alembic** for database ORM and migrations
- **Pydantic** for data validation and serialization
- **Dapr** for distributed runtime (pub/sub, state, service mesh)
- **Next.js 14 + TypeScript** for frontend dashboard
- **Kubernetes/Helm** for container orchestration
- **Terraform/OpenTofu** for infrastructure provisioning
- **Ansible** for configuration management

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
- **budapp**: Database, Redis, Keycloak, MinIO, Dapr configuration
- **budcluster**: Database, Redis, Dapr, cloud provider credentials  
- **budsim**: Database, Redis, Dapr, ML model cache configuration
- **budadmin**: `NEXT_PUBLIC_BASE_URL`, `NEXT_PUBLIC_NOVU_*`, authentication keys

## Development Guidelines

### Code Standards
- Follow **Conventional Commits** for commit messages (feat, fix, docs, etc.)
- Use **Ruff** for linting/formatting with Google docstring convention
- Maintain **MyPy** type annotations for all functions
- Write tests for new functionality using **pytest** with asyncio support

### Service Patterns (consistent across all services)

#### Backend Services (budapp, budcluster, budsim)
- **API Layer**: Routes in `*_routes.py` (budapp) or `routes.py` (budcluster/budsim)
- **Business Logic**: Services in `services.py` 
- **Data Access**: CRUD operations in `crud.py`
- **Database Models**: SQLAlchemy models in `models.py`
- **Data Validation**: Pydantic schemas in `schemas.py`
- **Workflows**: Long-running Dapr workflows in `workflows.py`

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
- PostgreSQL, Redis/Valkey for data persistence
- Dapr for service mesh and workflow orchestration
- ClickHouse for analytics (budapp)
- MinIO for object storage (budapp models/datasets)
- Keycloak for authentication (budapp multi-tenant)
- Grafana LGTM stack for observability
- Novu for notifications (budapp)

### Cloud Providers
- **Azure**: Primary cloud with AKS clusters via Terraform modules
- **AWS**: EKS support via Terraform modules  
- **On-premises**: OpenShift support via Ansible playbooks

### Deployment Workflow  
1. Infrastructure provisioning (Terraform/Ansible) via budcluster
2. Cluster registration and validation via budcluster
3. Service deployment via Helm charts
4. Model optimization analysis via budsim
5. Model deployment orchestration via budcluster + budapp
6. Performance monitoring and optimization via all services

## Troubleshooting

### Common Issues
- **Missing Dapr API Token**: Required for tests, check `.env` file
- **Database Connection**: Ensure PostgreSQL is running via docker-compose
- **Crypto Keys Missing**: Run key generation commands for budcluster
- **Port Conflicts**: Services use different ports (check docker-compose files)
- **Frontend API Connection**: Ensure `NEXT_PUBLIC_BASE_URL` points to correct backend
- **Node Version**: budadmin requires Node.js v20.16.0+ (managed via NVM in hook scripts)

### Development Tools
Available in Nix shell:
- `kubectl`, `helm` for Kubernetes operations
- `k3d` for local cluster testing
- `opentofu` for Terraform operations
- `azure-cli` for Azure management
- `sops` for secret encryption