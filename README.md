[![ Bud Ecosystem](https://github.com/BudEcosystem/.github/blob/main/assets/bud-runtime-banner.png)]()

# Bud AI Foundry


[![License](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://opensource.org/licenses/AGPL-3.0)
[![Next.js](https://img.shields.io/badge/Next.js-14+-black.svg)](https://nextjs.org/)
[![Rust](https://img.shields.io/badge/rust-1.70+-orange.svg)](https://www.rust-lang.org/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-1.25+-blue.svg)](https://kubernetes.io/)

Bud AI Foundry is a control panel for your GenAI deployments, designed to maximize infrastructure performance and give you full control over every aspect, from deployment administration to compliance and security management—All in one place

**[Quick Start](#-quick-start)** • **[Documentation](#-documentation)** • **[Contributing](#-contributing)**


![Model Deployment Flow](docs/images/model-deployment-flow.gif)

## 🚀 Features

- **Multi-Cloud Deployment**: Automated cluster provisioning on AWS EKS, Azure AKS, and on-premises OpenShift
- **AI Model Management**: Complete lifecycle management for LLM and ML models with metadata and licensing
- **Performance Optimization**: ML-based deployment optimization using genetic algorithms and XGBoost predictions
- **Real-time Analytics**: ClickHouse-powered observability and time-series metrics with inference request tracking
- **High-Performance Gateway**: Rust-based API gateway with sub-millisecond latency for model inference routing
- **Intelligent Assistance**: AI-powered cluster analysis and performance recommendations
- **Web Dashboard**: Modern Next.js frontend with real-time updates and interactive workflows
- **Enterprise Security**: Keycloak authentication, multi-tenancy, and encrypted credential management
- **Inference Observability**: Detailed tracking and analysis of AI model inference requests

## 📋 Table of Contents

- [Architecture](#-architecture)
- [Services](#-services)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Development](#-development)
- [Deployment](#-deployment)
- [Documentation](#-documentation)
- [Contributing](#-contributing)
- [License](#-license)

## 🏗️ Architecture

Bud Stack follows a microservices architecture built on Kubernetes with Dapr for service mesh capabilities:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   budadmin      │    │     budapp      │    │   budgateway    │
│   (Frontend)    │◄──►│  (Main API)     │◄──►│ (Rust Gateway)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                        │
        ┌─────────────────────┼────────────────────────┼─────────────────────┐
        │                     │                        │                     │
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ budcluster  │    │  budmodel   │    │ budmetrics  │    │  budnotify  │
│ (Clusters)  │    │ (Registry)  │    │(Analytics)  │    │(Messaging)  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
        │                     │                        │                     │
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   budsim    │    │   ask-bud   │    │  budeval    │    │budplayground│
│(Simulation) │    │ (AI Agent)  │    │(Evaluation) │    │(Playground) │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### Core Technologies

- **Backend**: Python 3.10+ with FastAPI and budmicroframe
- **Frontend**: Next.js 14 with TypeScript and Zustand state management
- **Gateway**: Rust with Tokio for high-performance async processing
- **Service Mesh**: Dapr for communication, workflows, and state management
- **Databases**: PostgreSQL, ClickHouse, Redis/Valkey
- **Infrastructure**: Kubernetes, Helm, Terraform/OpenTofu, Ansible
- **Authentication**: Keycloak with multi-tenant support
- **Storage**: MinIO for object storage
- **Observability**: ClickHouse for metrics

## 🛠️ Services

### Backend Services

| Service | Purpose | Technology Stack |
|---------|---------|------------------|
| **budapp** | Main API service for user management, projects, models, and endpoints | FastAPI, PostgreSQL, Keycloak, MinIO |
| **budcluster** | Cluster lifecycle management and infrastructure automation | FastAPI, Terraform, Ansible, PostgreSQL |
| **budsim** | Performance simulation and ML-based deployment optimization | FastAPI, XGBoost, DEAP, PostgreSQL |
| **budmodel** | Model registry with metadata, licensing, and leaderboard data | FastAPI, PostgreSQL, Hugging Face API |
| **budmetrics** | Observability service with time-series analytics and inference tracking | FastAPI, ClickHouse, Redis |
| **budnotify** | Notification and pub/sub messaging service | FastAPI, Redis, Dapr |
| **ask-bud** | AI assistant for cluster analysis and recommendations | FastAPI, PostgreSQL, AI models |
| **budgateway** | High-performance API gateway for model inference routing | Rust, Tokio, Redis, Multiple AI providers |
| **budeval** | Model evaluation and benchmarking service | FastAPI, PostgreSQL |
| **budplayground** | Interactive AI model testing interface | Next.js, React |

### Frontend Service

| Service | Purpose | Technology Stack |
|---------|---------|------------------|
| **budadmin** | Web dashboard for managing deployments and infrastructure | Next.js 14, TypeScript, Zustand, Socket.io |

## 📦 Prerequisites

### Required Tools

- **Docker & Docker Compose** (v20.10+)
- **Git** (v2.25+)
- **Node.js** (v20.16+) - for frontend development
- **Python** (v3.10+) - for backend development

### Optional (Recommended)

- **Nix** (v2.8+) - for reproducible development environment
- **kubectl** (v1.25+) - for Kubernetes operations
- **Helm** (v3.8+) - for chart management

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/BudEcosystem/bud-stack.git
cd bud-stack
```

### 2. Setup Development Environment

#### Option A: Using Nix (Recommended)
```bash
# Enter development shell with all tools
nix develop

# Or use specific shell
nix develop .#bud
```

#### Option B: Manual Setup
Ensure Docker, Node.js, and Python are installed on your system.

### 3. Start Services

#### Start Individual Services
```bash
# Backend services (Python/FastAPI)
cd services/budapp && ./deploy/start_dev.sh
cd services/budcluster && ./deploy/start_dev.sh --build
cd services/budsim && ./deploy/start_dev.sh --build
cd services/budmodel && ./deploy/start_dev.sh
cd services/budmetrics && ./deploy/start_dev.sh
cd services/budnotify && ./deploy/start_dev.sh
cd services/ask-bud && ./deploy/start_dev.sh

# Rust gateway service
cd services/budgateway && cargo run

# Frontend dashboard
cd services/budadmin && npm install && npm run dev
```

#### Or Start All Services
```bash
# Use the main Helm chart for full deployment
helm install bud infra/helm/bud/
```

### 4. Access the Dashboard

- **Frontend Dashboard**: http://localhost:8007
- **Main API (budapp)**: http://localhost:9081
- **API Documentation**: http://localhost:9081/docs

## 💻 Development

### Environment Setup

Each service requires environment configuration:

```bash
# Copy environment templates
cd services/budapp && cp .env.sample .env
cd services/budcluster && cp .env.sample .env
cd services/budadmin && cp .env.sample .env
# ... repeat for other services
```

### Code Quality

#### Python Services (budapp, budcluster, budsim, budmodel, budmetrics, budnotify, ask-bud)
```bash
# Linting and formatting
ruff check . --fix
ruff format .

# Type checking
mypy <service_name>/

# Testing
pytest --dapr-http-port 3510 --dapr-api-token <TOKEN>

# Install pre-commit hooks
./scripts/install_hooks.sh
```

#### Frontend Service (budadmin)
```bash
cd services/budadmin
npm run lint
npm run build
npm test
```

#### Rust Service (budgateway)
```bash
cd services/budgateway
cargo fmt              # Format code
cargo clippy          # Lint code
cargo test            # Run tests
cargo build --release # Build for production
```

### Database Operations

```bash
# PostgreSQL migrations
alembic upgrade head
alembic revision --autogenerate -m "description"

# ClickHouse migrations (budmetrics)
cd services/budmetrics && python scripts/migrate_clickhouse.py
```

### Special Setup for budcluster

Generate encryption keys for credential security:

```bash
cd services/budcluster
mkdir -p crypto-keys
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -out crypto-keys/rsa-private-key.pem
openssl rand -out crypto-keys/symmetric-key-256 32
chmod 644 crypto-keys/rsa-private-key.pem crypto-keys/symmetric-key-256
```

## 🚀 Deployment

### Kubernetes Deployment

```bash
# Deploy with Helm
helm dependency update infra/helm/bud/
helm install bud infra/helm/bud/

# Or deploy to specific namespace
helm install bud infra/helm/bud/ --namespace bud-system --create-namespace
```

### Infrastructure Provisioning

```bash
# Using Terraform/OpenTofu
cd infra/terraform/
tofu plan
tofu apply
```

### Production Considerations

- Configure persistent volumes for databases
- Setup TLS certificates for secure communication
- Configure backup strategies for PostgreSQL and ClickHouse
- Setup monitoring and alerting with the LGTM stack
- Configure multi-tenant Keycloak realms
- Setup proper RBAC for Kubernetes clusters

## 📚 Documentation

- **[CLAUDE.md](./CLAUDE.md)** - Comprehensive development guide
- **[Service Documentation](./services/)** - Individual service documentation
- **[Infrastructure Guide](./infra/)** - Deployment and infrastructure setup
- **API Documentation** - Available at each service's `/docs` endpoint

### Service-Specific Documentation

- [budapp README](./services/budapp/README.md) - Main application service
- [budcluster README](./services/budcluster/README.md) - Cluster management
- [budsim README](./services/budsim/README.md) - Performance simulation
- [budadmin README](./services/budadmin/readme.md) - Frontend dashboard
- [budmodel README](./services/budmodel/README.md) - Model registry
- [budmetrics README](./services/budmetrics/README.md) - Analytics service
- [budgateway README](./services/budgateway/README.md) - High-performance API gateway
- [ask-bud README](./services/ask-bud/README.md) - AI assistant service

## 🎯 Recent Features

### Inference Request/Prompt Listing (January 2025)

A comprehensive feature for viewing and analyzing AI model inference requests has been added:

#### Key Capabilities
- **Detailed Request Tracking**: View individual AI inference requests with full prompt/response details
- **Advanced Filtering**: Filter by date range, success status, token counts, and latency
- **Performance Metrics**: Track response time, token usage, and costs per inference
- **User Feedback**: Access ratings, boolean metrics, and comments for each inference
- **Data Export**: Export inference data in CSV and JSON formats for external analysis
- **Row-Level Security**: Ensures users can only access their project's inference data

#### Implementation Across Services
- **BudMetrics**: New endpoints for efficient ClickHouse-based inference data retrieval
- **BudApp**: Proxy endpoints with access control and entity name enrichment
- **BudAdmin**: Interactive UI with data tables, filtering, sorting, and detailed modal views

For more details, see the [inference endpoints documentation](./services/budapp/docs/inference-endpoints.md).

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Setup pre-commit hooks**: `./scripts/install_hooks.sh` (in service directories)
4. **Make your changes** following our coding standards
5. **Run tests**: `pytest` and `npm test`
6. **Commit changes**: Use [Conventional Commits](https://conventionalcommits.org/)
7. **Push to branch**: `git push origin feature/amazing-feature`
8. **Open a Pull Request**

### Development Guidelines

- Follow the existing code patterns and architecture
- Write tests for new functionality
- Update documentation for API changes
- Use Ruff for Python code formatting
- Follow TypeScript best practices for frontend code
- Ensure all services maintain backward compatibility

## 📄 License

This project is licensed under the AGPL-3.0 license - see the [LICENSE](./LICENSE) file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/BudEcosystem/bud-stack/issues)
- **Discussions**: [GitHub Discussions](https://github.com/BudEcosystem/bud-stack/discussions)
- **Documentation**: [CLAUDE.md](./CLAUDE.md)

## 🙏 Acknowledgments

- [Dapr](https://dapr.io/) for the distributed runtime platform
- [FastAPI](https://fastapi.tiangolo.com/) for the Python web framework
- [Next.js](https://nextjs.org/) for the React framework
- [Kubernetes](https://kubernetes.io/) for container orchestration
- [Helm](https://helm.sh/) for package management
- [TensorZero](https://www.tensorzero.com/) for initial version of the gateway.

---

**Bud Stack** - Intelligent AI/ML Infrastructure Platform
