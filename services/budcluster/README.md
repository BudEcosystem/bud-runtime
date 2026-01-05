# BudCluster Service

[![License](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://opensource.org/licenses/AGPL-3.0)
[![Python 3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Dapr](https://img.shields.io/badge/Dapr-1.10+-blue.svg)](https://dapr.io/)

A comprehensive cluster lifecycle management service that provisions, manages, and deploys AI/ML models to Kubernetes/OpenShift clusters across multiple cloud providers. Part of the Bud Stack platform.

## 🚀 Features

- **Multi-Cloud Support**: Automated provisioning for AWS EKS, Azure AKS, and on-premises OpenShift clusters
- **Infrastructure as Code**: Terraform modules for cloud infrastructure and Ansible playbooks for configuration
- **Model Deployment**: Orchestrates AI/ML model deployments with CPU/CUDA/HPU runtime support
- **Security**: RSA/AES encryption for sensitive credentials and kubeconfigs
- **Hardware Detection**: Automatic node capability detection for optimal model placement
- **Workflow Orchestration**: Long-running operations managed through Dapr workflows
- **Monitoring**: Real-time cluster health monitoring and status tracking

## 📋 Table of Contents

- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Development](#-development)
- [API Documentation](#-api-documentation)
- [Deployment](#-deployment)
- [Testing](#-testing)
- [Troubleshooting](#-troubleshooting)

## 🏗️ Architecture

### Service Structure

```
budcluster/
├── budcluster/
│   ├── cluster_ops/        # Cluster lifecycle management
│   │   ├── routes.py       # REST API endpoints
│   │   ├── services.py     # Business logic
│   │   ├── crud.py         # Database operations
│   │   ├── models.py       # SQLAlchemy models
│   │   ├── schemas.py      # Pydantic schemas
│   │   └── workflows.py    # Dapr workflows
│   ├── deployment/         # Model deployment orchestration
│   │   ├── routes.py       # Deployment endpoints
│   │   ├── services.py     # Deployment logic
│   │   └── workflows.py    # Deployment workflows
│   └── common/            # Shared utilities
├── charts/                # Helm charts
│   ├── bud_runtime_container/    # Model serving runtime
│   ├── nfd/                      # Node Feature Discovery
│   └── prometheus-stack/         # Metrics collection
├── playbooks/             # Ansible automation
│   ├── deploy_runtime.yml
│   ├── delete_runtime.yml
│   └── collect_node_info.yml
└── terraform/             # Infrastructure modules
    ├── modules/
    │   ├── aws-eks/
    │   └── azure-aks/
    └── environments/
```

### Core Components

- **Cluster Operations**: Manages cluster registration, provisioning, and lifecycle
- **Deployment Engine**: Handles model transfers, runtime creation, and benchmarking
- **Infrastructure Automation**: Terraform for cloud resources, Ansible for configuration
- **Security Layer**: Encryption/decryption of sensitive data using RSA and AES
- **Dapr Integration**: Service mesh capabilities for communication and workflows

### Data Flow

1. **Cluster Registration** → Validate credentials → Encrypt and store
2. **Infrastructure Provisioning** → Terraform plan/apply → Update status
3. **Node Detection** → Deploy collectors → Gather hardware capabilities
4. **Model Deployment** → Transfer model → Create runtime → Run benchmarks
5. **Monitoring** → Health checks → Status updates → Event notifications

## 📦 Prerequisites

### Required

- **Python 3.10+
- **Docker** and Docker Compose
- **Git**
- **OpenSSL** (for key generation)

### Optional

- **Terraform/OpenTofu** (for cloud provisioning)
- **Ansible** (for on-premises clusters)
- **kubectl** (for direct cluster access)
- **Helm** (for chart deployment)

## 🚀 Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/BudEcosystem/bud-stack.git
cd bud-stack/services/budcluster

# Generate encryption keys (required)
mkdir -p crypto-keys
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -out crypto-keys/rsa-private-key.pem
openssl rand -out crypto-keys/symmetric-key-256 32
chmod 644 crypto-keys/*

# Setup environment
cp .env.sample .env
# Edit .env with your configuration
```

### 2. Start Development Environment

```bash
# Start with build
./deploy/start_dev.sh --build

# Or start without rebuild
./deploy/start_dev.sh

# Access the service
# API: http://localhost:9082
# API Docs: http://localhost:9082/docs
```

### 3. Initialize Database

```bash
# Run migrations
alembic upgrade head

# Optional: Initialize with sample data
python scripts/initialize_db.py
```

## 💻 Development

### Environment Variables

Key environment variables in `.env`:

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/budcluster

# Redis (Dapr state store)
REDIS_URL=redis://localhost:6379

# Dapr Configuration
DAPR_HTTP_PORT=3510
DAPR_GRPC_PORT=50002
DAPR_API_TOKEN=your-token

# Cloud Credentials (optional)
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-secret
AZURE_TENANT_ID=your-tenant

# Crypto Keys
CRYPTO_PRIVATE_KEY_PATH=crypto-keys/rsa-private-key.pem
CRYPTO_SYMMETRIC_KEY_PATH=crypto-keys/symmetric-key-256
```

### Code Quality

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
./scripts/install_hooks.sh

# Linting and formatting
ruff check budcluster/ --fix
ruff format budcluster/

# Type checking
mypy budcluster/

# Run all quality checks
./scripts/lint.sh
```

### Database Operations

```bash
# Create migration
alembic revision --autogenerate -m "Add cluster metadata"

# Apply migrations
alembic upgrade head

# Rollback one revision
alembic downgrade -1
```

## 📚 API Documentation

### Key Endpoints

#### Cluster Management
- `POST /clusters/register` - Register new cluster
- `GET /clusters` - List all clusters
- `GET /clusters/{cluster_id}` - Get cluster details
- `PUT /clusters/{cluster_id}` - Update cluster
- `DELETE /clusters/{cluster_id}` - Delete cluster
- `POST /clusters/{cluster_id}/provision` - Provision infrastructure

#### Deployment Operations
- `POST /deployments/deploy` - Deploy model to cluster
- `GET /deployments/{deployment_id}` - Get deployment status
- `DELETE /deployments/{deployment_id}` - Remove deployment
- `POST /deployments/{deployment_id}/benchmark` - Run benchmarks

#### Hardware Detection
- `POST /clusters/{cluster_id}/collect-node-info` - Deploy node collectors
- `GET /clusters/{cluster_id}/nodes` - Get node capabilities

### Workflow Operations

Long-running operations are handled via Dapr workflows:

```python
# Example: Provision cluster
POST /clusters/{cluster_id}/provision
{
  "provider": "aws",
  "region": "us-west-2",
  "node_count": 3
}
```

## 🚀 Deployment

### Docker Deployment

```bash
# Build image
docker build -t budcluster:latest .

# Run with docker-compose
docker-compose up -d
```

### Kubernetes Deployment

```bash
# Deploy with Helm
helm install budcluster ./charts/budcluster/

# Or as part of full stack
cd ../../infra/helm/bud
helm dependency update
helm install bud .
```

## 🧪 Testing

### Unit Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=budcluster --cov-report=html

# Run specific test
pytest tests/test_cluster_ops.py::test_register_cluster
```

### Integration Tests

```bash
# With Dapr sidecar
pytest tests/integration/ --dapr-http-port 3510 --dapr-api-token $DAPR_API_TOKEN
```

### End-to-End Tests

```bash
# Deploy test cluster and model
python tests/e2e/test_full_workflow.py
```

## 🔧 Troubleshooting

### Common Issues

#### Missing Crypto Keys
```bash
# Error: FileNotFoundError: crypto-keys/rsa-private-key.pem
# Solution: Generate keys as shown in Quick Start
```

#### Database Connection Failed
```bash
# Error: sqlalchemy.exc.OperationalError
# Solution: Ensure PostgreSQL is running
docker-compose ps
docker-compose up -d postgres
```

#### Dapr Sidecar Not Ready
```bash
# Error: Connection refused to localhost:3510
# Solution: Wait for Dapr initialization or restart
docker-compose restart budcluster-dapr
```

#### Terraform/Ansible Not Found
```bash
# These are optional for development
# Install if testing cloud provisioning:
pip install ansible
brew install terraform  # or use OpenTofu
```

### Debug Mode

Enable debug logging:
```bash
# In .env
LOG_LEVEL=DEBUG

# Or via environment
export LOG_LEVEL=DEBUG
./deploy/start_dev.sh
```

### Health Checks

```bash
# Service health
curl http://localhost:9082/health

# Dapr health
curl http://localhost:3510/v1.0/healthz

# Database connectivity
curl http://localhost:9082/health/db
```

## 🤝 Contributing

Please see the main [Bud Stack Contributing Guide](../../CONTRIBUTING.md).

### Service-Specific Guidelines

1. Follow existing patterns for new endpoints
2. Add tests for new functionality
3. Update API documentation
4. Test with different cluster types
5. Ensure encryption for sensitive data

## 📄 License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](../../LICENSE) file for details.

## 🔗 Related Documentation

- [Main Bud Stack README](../../README.md)
- [CLAUDE.md Development Guide](./CLAUDE.md)
- [API Documentation](http://localhost:9082/docs) (when running)
- [Helm Charts](./charts/)
- [Terraform Modules](./terraform/modules/)
