# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BudCluster is a FastAPI-based microservice that manages Kubernetes/OpenShift clusters and AI model deployments. It uses Dapr for distributed runtime capabilities, Ansible/Terraform for infrastructure automation, and provides multi-cloud support (AWS EKS, Azure AKS, on-premises).

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
- Model deployments now use dynamic `--max-model-len` based on `input_tokens + output_tokens` with 10% safety margin
- Token parameters are optional and fallback to default (8192) when not provided

## Technical Stack

- **Framework**: FastAPI with Dapr sidecars
- **Database**: PostgreSQL with SQLAlchemy ORM and Alembic migrations
- **State Management**: Redis for Dapr state store and configuration
- **Containerization**: Docker with docker-compose for development
- **Infrastructure**: Terraform for cloud provisioning, Ansible for configuration
- **Validation**: Pydantic schemas for request/response handling
- **Code Quality**: Ruff for linting/formatting, MyPy for type checking
- **Testing**: pytest with asyncio support

## Configuration Management

Environment configuration uses budmicroframe patterns:
- `.env` files with `.env.sample` templates
- Dapr configuration components for runtime settings
- Periodic sync from configuration store
- Crypto keys for encryption/decryption of sensitive data

## Hardware Detection (NFD)

The service uses Node Feature Discovery (NFD) as the only method for hardware detection:
- Deploys NFD components to clusters for automatic hardware labeling
- Timeout configurable via `NFD_DETECTION_TIMEOUT` (default: 30s)
- NFD namespace configurable via `NFD_NAMESPACE` (default: `node-feature-discovery`)
- Legacy node-info-collector methods have been removed

## GPU Time-Slicing with HAMI

HAMI (HAMi GPU Device Plugin) is automatically installed during cluster onboarding when NVIDIA GPUs are detected:
- **Automatic Installation**: Deployed via Ansible playbook (`setup_cluster.yaml`) after GPU Operator installation
- **Helm Chart**: Uses the official HAMI Helm chart from `https://project-hami.github.io/HAMi/`
- **Configuration**: Pre-configured with device plugin enabled, NVIDIA runtime, and privileged security context
- **Metrics Collection**: Integrated with Prometheus for GPU utilization and time-slicing metrics
- **Automatic Cleanup**: Removed during cluster deletion, including CRDs and cluster resources

### HAMI Configuration

Environment variables in `.env`:
- `ENABLE_HAMI_METRICS=false` - Enable/disable HAMI metrics collection (set to `true` for GPU clusters)
- `HAMI_SCHEDULER_PORT=31993` - NodePort for HAMI scheduler metrics endpoint
- `HAMI_UTILIZATION_THRESHOLD=80` - GPU availability threshold percentage

### Installation Flow

HAMI installation occurs during the `register_cluster` workflow:
1. NFD detects NVIDIA GPUs via PCI vendor ID (10de)
2. GPU Operator is deployed (drivers, toolkit, device plugin)
3. HAMI is automatically installed in `kube-system` namespace
4. HAMI scheduler becomes available for GPU time-slicing
5. Metrics collection can be enabled for monitoring

### Development Notes

When working with GPU deployments:
- HAMI is conditionally installed only when `has_nvidia_gpus` flag is true
- Installation uses idempotent Helm operations (checks if already deployed)
- Failure to install HAMI will cause cluster registration to fail
- HAMI metrics are parsed via `budcluster/commons/hami_parser.py`
- GPU node information is enriched with HAMI time-slicing data

## Workflow Orchestration

Long-running operations use Dapr workflows:
- Cluster provisioning workflows for cloud providers
- Model deployment workflows with error handling
- State persistence in Redis state store
- Notification integration for status updates

## Development Patterns

Follow these patterns when adding new functionality:
- Use existing CRUD patterns in `base_crud.py`
- Implement Pydantic schemas for all API endpoints
- Add proper error handling and logging
- Use Dapr service invocation for inter-service communication
- Encrypt sensitive data before storing in database
- Add appropriate database migrations for schema changes
