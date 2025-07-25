# BudApp Service

[![License](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://opensource.org/licenses/AGPL-3.0)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Dapr](https://img.shields.io/badge/Dapr-1.10+-blue.svg)](https://dapr.io/)

The main application service for the Bud Stack platform, handling user management, projects, AI/ML models, endpoints, and workflow orchestration. BudApp serves as the central API gateway coordinating activities across all other services.

## 🚀 Features

- **User & Project Management**: Multi-tenant support with Keycloak authentication and role-based access control
- **Model Registry Integration**: Manages AI/ML models with cloud and local storage support via MinIO
- **Endpoint Management**: Orchestrates model deployments to clusters with automatic resource allocation
- **Workflow Orchestration**: Complex multi-step operations using Dapr workflows
- **Dataset Management**: Upload, store, and version datasets for model training and evaluation
- **Benchmarking**: Automated performance testing and metrics collection
- **Multi-Cluster Support**: Deploy models across different clusters with intelligent placement
- **Real-time Updates**: WebSocket support for live status updates and notifications

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
budapp/
├── budapp/
│   ├── auth/               # Authentication and authorization
│   │   ├── auth_routes.py  # Auth endpoints
│   │   ├── services.py     # Keycloak integration
│   │   └── models.py       # User/role models
│   ├── cluster_ops/        # Cluster management
│   │   ├── cluster_routes.py
│   │   ├── services.py
│   │   ├── crud.py
│   │   └── workflows.py
│   ├── model_ops/          # Model management
│   │   ├── cloud_model_routes.py
│   │   ├── local_model_routes.py
│   │   ├── services.py
│   │   └── workflows.py
│   ├── endpoint_ops/       # Endpoint deployment
│   │   ├── endpoint_routes.py
│   │   ├── services.py
│   │   └── workflows.py
│   ├── dataset_ops/        # Dataset management
│   │   ├── dataset_routes.py
│   │   └── services.py
│   ├── project_ops/        # Project organization
│   │   ├── project_routes.py
│   │   └── crud.py
│   ├── workflow_ops/       # Workflow definitions
│   │   └── workflows.py
│   └── commons/            # Shared utilities
│       ├── config.py       # Configuration
│       ├── database.py     # Database setup
│       ├── dependencies.py # FastAPI dependencies
│       └── exceptions.py   # Custom exceptions
├── alembic/               # Database migrations
├── tests/                 # Test suite
└── deploy/                # Deployment scripts
```

### Core Components

- **Authentication Layer**: Keycloak integration for SSO and multi-tenant support
- **API Gateway**: RESTful endpoints for all platform operations
- **Workflow Engine**: Dapr workflows for long-running operations
- **Storage Layer**: MinIO for object storage, PostgreSQL for metadata
- **Service Communication**: Dapr service invocation for inter-service calls
- **Caching**: Redis for session management and temporary data

### Integration Points

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Keycloak  │     │    MinIO    │     │   Redis     │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                    │
       └───────────────────┴────────────────────┘
                           │
                    ┌──────┴──────┐
                    │   BudApp    │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────┴───────┐  ┌───────┴───────┐  ┌──────┴──────┐
│  BudCluster   │  │   BudModel    │  │   BudSim    │
└───────────────┘  └───────────────┘  └─────────────┘
```

## 📦 Prerequisites

### Required

- **Python** 3.8+
- **Docker** and Docker Compose
- **Git**

### Service Dependencies

- **PostgreSQL** - Primary database
- **Redis** - Caching and state management
- **Keycloak** - Authentication service
- **MinIO** - Object storage
- **Dapr** - Service mesh and workflows

## 🚀 Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/BudEcosystem/bud-stack.git
cd bud-stack/services/budapp

# Setup environment
cp .env.sample .env
# Edit .env with your configuration
```

### 2. Configure Services

Edit `.env` file with required configurations:

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=budapp
POSTGRES_PASSWORD=budapp123
POSTGRES_DB=budapp

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# Keycloak
KEYCLOAK_URL=http://localhost:8080
KEYCLOAK_REALM=bud-serve
KEYCLOAK_CLIENT_ID=bud-serve-app
KEYCLOAK_CLIENT_SECRET=your-secret

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false

# Dapr
DAPR_HTTP_PORT=3510
DAPR_GRPC_PORT=50001
DAPR_API_TOKEN=your-token

# Application
APP_NAME=bud-serve-app
SECRET_KEY=your-secret-key
ALGORITHM=HS256
```

### 3. Start Development Environment

```bash
# Start all services with Docker Compose
./deploy/start_dev.sh

# Service will be available at:
# API: http://localhost:9081
# API Docs: http://localhost:9081/docs
# Keycloak: http://localhost:8080
# MinIO: http://localhost:9000
```

### 4. Initialize Database

```bash
# Run migrations
alembic -c ./budapp/alembic.ini upgrade head

# Optional: Seed initial data
python scripts/seed_data.py
```

## 💻 Development

### Environment Variables

Key environment variables in `.env`:

```bash
# Authentication
TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_MINUTES=10080

# Storage
MINIO_BUCKET_NAME=bud-models
MAX_UPLOAD_SIZE=5368709120  # 5GB

# Service URLs
BUDCLUSTER_SERVICE_URL=http://budcluster:8000
BUDMODEL_SERVICE_URL=http://budmodel:8000
BUDSIM_SERVICE_URL=http://budsim:8000

# Feature Flags
ENABLE_METRICS=true
ENABLE_TRACING=true
```

### Code Quality

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
./scripts/install_hooks.sh

# Linting and formatting
ruff check budapp/ --fix
ruff format budapp/

# Type checking
mypy budapp/

# Run all quality checks
./scripts/lint.sh
```

### Database Operations

```bash
# Create migration
alembic -c ./budapp/alembic.ini revision --autogenerate -m "Add feature"

# Apply migrations
alembic -c ./budapp/alembic.ini upgrade head

# Rollback one revision
alembic -c ./budapp/alembic.ini downgrade -1

# View migration history
alembic -c ./budapp/alembic.ini history
```

## 📚 API Documentation

### Key Endpoints

#### Authentication
- `POST /auth/login` - User login with Keycloak
- `POST /auth/refresh` - Refresh access token
- `POST /auth/logout` - Logout user
- `GET /auth/me` - Get current user info

#### Projects
- `POST /projects` - Create new project
- `GET /projects` - List user projects
- `GET /projects/{id}` - Get project details
- `PUT /projects/{id}` - Update project
- `DELETE /projects/{id}` - Delete project

#### Models
- `POST /models/cloud` - Register cloud model
- `POST /models/local` - Upload local model
- `GET /models` - List available models
- `GET /models/{id}` - Get model details
- `POST /models/{id}/deploy` - Deploy model

#### Endpoints
- `POST /endpoints` - Create endpoint
- `GET /endpoints` - List endpoints
- `GET /endpoints/{id}` - Get endpoint details
- `PUT /endpoints/{id}` - Update endpoint
- `DELETE /endpoints/{id}` - Delete endpoint
- `GET /endpoints/{id}/metrics` - Get endpoint metrics

#### Datasets
- `POST /datasets/upload` - Upload dataset
- `GET /datasets` - List datasets
- `GET /datasets/{id}` - Get dataset details
- `DELETE /datasets/{id}` - Delete dataset

#### Clusters
- `GET /clusters` - List available clusters
- `GET /clusters/{id}/status` - Get cluster status
- `POST /clusters/{id}/sync` - Sync cluster info

### Workflow Examples

#### Deploy Model Workflow

```python
# 1. Register/upload model
POST /models/cloud
{
  "name": "llama-2-7b",
  "source": "huggingface",
  "repo_id": "meta-llama/Llama-2-7b"
}

# 2. Create endpoint
POST /endpoints
{
  "name": "llama-endpoint",
  "model_id": "model-uuid",
  "cluster_id": "cluster-uuid",
  "replicas": 2
}

# 3. Monitor deployment
GET /endpoints/{endpoint_id}/status
```

## 🚀 Deployment

### Docker Deployment

```bash
# Build image
docker build -t budapp:latest .

# Run with docker-compose
docker-compose up -d
```

### Kubernetes Deployment

```bash
# Deploy with Helm
helm install budapp ./charts/budapp/

# Or as part of full stack
cd ../../infra/helm/bud
helm dependency update
helm install bud .
```

### Production Configuration

```yaml
# values.yaml for Helm
budapp:
  replicas: 3
  resources:
    requests:
      memory: "512Mi"
      cpu: "500m"
    limits:
      memory: "2Gi"
      cpu: "2000m"
  env:
    - name: LOG_LEVEL
      value: "INFO"
    - name: ENABLE_METRICS
      value: "true"
```

## 🧪 Testing

### Unit Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=budapp --cov-report=html

# Run specific test module
pytest tests/test_auth.py
```

### Integration Tests

```bash
# With Dapr sidecar
pytest tests/integration/ --dapr-http-port 3510 --dapr-api-token $DAPR_API_TOKEN
```

### API Tests

```bash
# Test authentication flow
pytest tests/api/test_auth_flow.py

# Test model deployment
pytest tests/api/test_model_deployment.py
```

### Load Testing

```bash
# Using locust
locust -f tests/load/locustfile.py --host=http://localhost:9081
```

## 🔧 Troubleshooting

### Common Issues

#### Keycloak Connection Failed
```bash
# Error: Unable to connect to Keycloak
# Solution: Ensure Keycloak is running and accessible
docker-compose ps keycloak
docker-compose logs keycloak

# Verify Keycloak URL in .env
curl http://localhost:8080/auth/realms/bud-serve
```

#### MinIO Upload Failed
```bash
# Error: Failed to upload to MinIO
# Solution: Check MinIO credentials and bucket
docker-compose exec minio mc ls local/
docker-compose exec minio mc mb local/bud-models
```

#### Dapr Workflow Failed
```bash
# Error: Failed to start workflow
# Solution: Check Dapr sidecar status
curl http://localhost:3510/v1.0/healthz

# Restart Dapr sidecar
docker-compose restart budapp-dapr
```

#### Database Migration Failed
```bash
# Error: alembic.util.exc.CommandError
# Solution: Check database connection
docker-compose ps postgres
psql -h localhost -U budapp -d budapp

# Reset migrations if needed
alembic -c ./budapp/alembic.ini downgrade base
alembic -c ./budapp/alembic.ini upgrade head
```

### Debug Mode

Enable detailed logging:
```bash
# In .env
LOG_LEVEL=DEBUG
SQLALCHEMY_ECHO=true

# Restart service
./deploy/stop_dev.sh
./deploy/start_dev.sh
```

### Health Checks

```bash
# Service health
curl http://localhost:9081/health

# Detailed health with dependencies
curl http://localhost:9081/health/ready

# Dapr health
curl http://localhost:3510/v1.0/healthz
```

## 🤝 Contributing

Please see the main [Bud Stack Contributing Guide](../../CONTRIBUTING.md).

### Service-Specific Guidelines

1. Follow the module structure pattern
2. Use dependency injection for services
3. Implement proper error handling
4. Add OpenAPI documentation to endpoints
5. Write tests for new features
6. Update migrations for model changes

## 📄 License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](../../LICENSE) file for details.

## 🔗 Related Documentation

- [Main Bud Stack README](../../README.md)
- [CLAUDE.md Development Guide](./CLAUDE.md)
- [API Documentation](http://localhost:9081/docs) (when running)
- [Keycloak Admin Guide](http://localhost:8080/auth/admin/)
- [MinIO Console](http://localhost:9000)
- [Database Schema](./docs/database-schema.md)