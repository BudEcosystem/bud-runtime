# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bud-Serve-Cluster is a FastAPI-based microservice that manages Kubernetes/OpenShift clusters and AI model deployments. It uses Dapr for distributed runtime capabilities, Ansible/Terraform for infrastructure automation, and provides multi-cloud support (AWS EKS, Azure AKS, on-premises).

## Common Development Commands

### Setup and Dependencies
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks (includes Node.js for commitlint)
./scripts/install_hooks.sh

# Generate crypto keys (required for first-time setup)
mkdir -p crypto-keys
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -out crypto-keys/rsa-private-key.pem
openssl rand -out crypto-keys/symmetric-key-256 32
chmod 644 crypto-keys/rsa-private-key.pem crypto-keys/symmetric-key-256

# Copy environment variables
cp .env.sample .env  # Edit with your values
```

### Running Locally
```bash
# Start development environment (includes PostgreSQL, Redis, Dapr)
./deploy/start_dev.sh --build

# Stop development environment  
./deploy/stop_dev.sh

# Run without rebuilding
./deploy/start_dev.sh
```

### Code Quality
```bash
# Run linter
ruff check budcluster/

# Run formatter
ruff format budcluster/

# Run type checker (currently disabled in pre-commit)
mypy budcluster/

# Run all tests
pytest

# Run specific test
pytest tests/test_cluster_ops.py::test_specific_function
```

### Database Operations
```bash
# Run database migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Initialize database
python scripts/initialize_db.py
```

## Architecture Overview

### Service Structure
- **API Layer**: FastAPI routes in `*/routes.py` files
- **Business Logic**: Services in `*/services.py` files  
- **Data Access**: CRUD operations in `*/crud.py` files
- **Database Models**: SQLAlchemy models in `*/models.py` files
- **Workflows**: Dapr workflows in `*/workflows.py` files

### Key Components

**cluster_ops/**: Cluster lifecycle management
- Provisions clusters using Terraform (AWS/Azure)
- Manages on-premises clusters via Ansible
- Monitors cluster health and status

**deployment/**: Model deployment orchestration
- Deploys AI models to clusters
- Manages runtime containers (CPU/CUDA/HPU)
- Handles model transfers and quantization

**charts/**: Helm charts for Kubernetes deployments
- `bud_runtime_container`: Model serving runtime
- `node_info_collector`: Hardware detection daemon
- `litellm_container`: LLM proxy server

**playbooks/**: Ansible automation
- Deploy/delete runtimes and components
- Collect node information
- Apply security contexts

### Dapr Integration

The service runs with Dapr sidecars providing:
- **Service Discovery**: Service-to-service calls via Dapr
- **State Management**: Using Redis state store
- **Pub/Sub**: Event-driven communication
- **Configuration**: Dynamic config management
- **Workflows**: Long-running orchestrations

Dapr components are defined in `.dapr/components/` and configured via environment variables.

### Deployment Workflow

1. **Register Cluster**: Add cluster credentials to database
2. **Deploy Collectors**: Install node info collectors to detect hardware
3. **Transfer Model**: Copy model from registry to cluster storage  
4. **Deploy Runtime**: Create runtime deployment with appropriate resources
5. **Run Benchmarks**: Execute performance tests

### Security Considerations

- All sensitive data (kubeconfigs, credentials) is encrypted using RSA/AES
- Keys stored in `crypto-keys/` directory (gitignored)
- Service-to-service communication secured via Dapr
- Database connections use SSL when configured

## Development Tips

- Always run linting before committing (pre-commit hooks help)
- Use Dapr service invocation for cross-service calls
- Follow existing patterns for new endpoints/services
- Check hardware type (CPU/CUDA/HPU) when deploying runtimes
- Use workflows for long-running operations
- Test with different cluster types (cloud/on-prem)