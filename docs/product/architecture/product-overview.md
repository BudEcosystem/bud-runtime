# Bud AI Foundry - Product Overview

---

## Overview

Bud AI Foundry is an enterprise platform for deploying, managing, and optimizing AI/ML model infrastructure at scale. It provides a unified control plane for GenAI workloads across multi-cloud and on-premises environments, with intelligent resource optimization that maximizes infrastructure performance while minimizing costs.

---

## What Problem Does It Solve?

Deploying production AI systems today requires teams to:

- Manually provision and configure Kubernetes clusters across cloud providers
- Guess at GPU/CPU resource requirements for different model architectures
- Build custom tooling for model deployment, versioning, and rollback
- Cobble together monitoring from multiple observability vendors
- Manage credentials and access control across disparate systems

**Bud AI Foundry consolidates these concerns into a single platform**, providing:

1. **One-click cluster provisioning** across AWS EKS, Azure AKS, and on-premises
2. **ML-powered resource optimization** that predicts optimal deployment configurations
3. **Unified model registry** with licensing, security scanning, and metadata management
4. **Built-in observability** with inference metrics, distributed tracing, and alerting
5. **Enterprise-grade security** with Keycloak SSO, RBAC, and encrypted credentials

---

## Platform Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Bud AI Foundry                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   budadmin   │  │ budplayground│  │ budCustomer  │  │   ask-bud    │    │
│  │  Dashboard   │  │ Model Testing│  │   Portal     │  │ AI Assistant │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                 │                 │             │
│  ───────┴─────────────────┴─────────────────┴─────────────────┴──────────   │
│                              API Gateway (budgateway)                        │
│                         High-performance Rust inference router               │
│  ────────────────────────────────────────────────────────────────────────   │
│         │                 │                 │                 │             │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐    │
│  │    budapp    │  │  budcluster  │  │    budsim    │  │   budmodel   │    │
│  │   Core API   │  │   Cluster    │  │  Performance │  │    Model     │    │
│  │  Auth/Users  │  │  Lifecycle   │  │  Simulation  │  │   Registry   │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│         │                 │                 │                 │             │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐    │
│  │  budmetrics  │  │   budeval    │  │  budnotify   │  │  budpipeline │    │
│  │ Observability│  │  Evaluation  │  │ Notifications│  │   Workflows  │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                           Infrastructure Layer                               │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │ PostgreSQL │  │   Redis    │  │ ClickHouse │  │   MinIO    │            │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │  Keycloak  │  │    Dapr    │  │   Kafka    │  │ LGTM Stack │            │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
             ┌───────────┐    ┌───────────┐    ┌───────────┐
             │  AWS EKS  │    │ Azure AKS │    │On-Premises│
             │  Clusters │    │  Clusters │    │  Clusters │
             └───────────┘    └───────────┘    └───────────┘
```

---

## Core Capabilities

### 1. Multi-Cloud Cluster Management

**budcluster** provisions and manages Kubernetes clusters across cloud providers and on-premises infrastructure.

| Feature | Description |
|---------|-------------|
| Cloud Provisioning | AWS EKS and Azure AKS via Terraform/OpenTofu |
| On-Premises | Bare metal and VMware via Ansible |
| Hardware Detection | Automatic GPU/CPU detection via Node Feature Discovery (NFD) |
| GPU Time-Slicing | HAMI integration for GPU sharing across workloads |
| Credential Management | RSA/AES encrypted kubeconfigs and secrets |

**Supported Infrastructure:**
- NVIDIA GPUs (A100, H100, L40S, T4, etc.)
- Intel Gaudi HPUs
- CPU-only deployments
- Mixed hardware clusters

### 2. Intelligent Resource Optimization

**budsim** uses machine learning to predict optimal deployment configurations, eliminating guesswork from capacity planning.

| Method | Use Case |
|--------|----------|
| **REGRESSOR** | XGBoost + genetic algorithms for full parameter optimization |
| **HEURISTIC** | Fast memory-based calculations for TP/PP tuning |

**Optimization Targets:**
- Time to First Token (TTFT)
- Output token throughput
- End-to-end latency
- GPU memory utilization
- Cost per inference

### 3. Model Registry & Lifecycle

**budmodel** provides a centralized registry for model metadata, licensing, and security.

| Feature | Description |
|---------|-------------|
| Model Extraction | Automatic metadata extraction from HuggingFace, local files |
| License Tracking | License compliance checking and FAQ generation |
| Security Scanning | ClamAV and modelscan integration |
| Leaderboard | Benchmark aggregation from multiple sources |
| Version Control | Model versioning with rollback support |

### 4. High-Performance Inference Gateway

**budgateway** is a Rust-based API gateway optimized for AI inference routing.

| Feature | Description |
|---------|-------------|
| Provider Routing | Route to OpenAI, Anthropic, local models, or custom endpoints |
| OpenAI Compatibility | Drop-in replacement for OpenAI API |
| Multi-Modal Support | Chat, embeddings, audio, image generation |
| Authentication | API key management with RSA encryption support |
| Performance | Sub-millisecond P99 latency for gateway operations |

**Supported Endpoints:**
- `/v1/chat/completions`
- `/v1/embeddings`
- `/v1/audio/transcriptions`
- `/v1/audio/speech`
- `/v1/images/generations`
- `/v1/responses`

### 5. Observability & Metrics

**budmetrics** provides comprehensive observability for AI workloads.

| Component | Purpose |
|-----------|---------|
| ClickHouse | Time-series storage for inference metrics |
| Grafana | Dashboards and visualization |
| Loki | Log aggregation |
| Tempo | Distributed tracing |
| Mimir | Long-term metrics storage |

**Key Metrics:**
- Inference latency (P50, P95, P99)
- Token throughput
- GPU utilization
- Model-level cost tracking
- Error rates and SLOs

### 6. Enterprise Security

| Feature | Description |
|---------|-------------|
| Authentication | Keycloak with SAML/OIDC SSO |
| Authorization | RBAC with project-level permissions |
| Encryption | At-rest (AES-256) and in-transit (TLS 1.3) |
| Secrets | RSA-encrypted credentials, HSM/KMS integration |
| Audit Logging | Tamper-proof audit trail with hash verification |
| Multi-Tenancy | Isolated projects with resource quotas |

### 7. Workflow Orchestration

**budpipeline** enables complex ML workflows with DAG-based execution.

| Feature | Description |
|---------|-------------|
| DAG Execution | Multi-step pipelines with dependencies |
| Scheduling | Cron-based and event-triggered execution |
| Progress Tracking | Real-time step progress and ETA |
| Callbacks | Webhook and pub/sub notifications |
| Pluggable Actions | Extensible action framework |

---

## Deployment Options

| Option | Description | Best For |
|--------|-------------|----------|
| **SaaS** | Fully managed by Bud AI | Teams wanting zero infrastructure management |
| **Self-Hosted** | Deploy to your cloud/on-prem | Data sovereignty, air-gapped environments |
| **Hybrid** | Control plane SaaS, compute self-hosted | Compliance with flexible scaling |

**Deployment Methods:**
- Helm chart for Kubernetes
- Terraform/OpenTofu modules for cloud infrastructure
- Docker Compose for development/evaluation

---

## Supported AI Frameworks

| Framework | Support Level |
|-----------|---------------|
| vLLM | Full (primary inference engine) |
| SGLang | Full |
| TensorRT-LLM | Full |
| LiteLLM | Full |
| PyTorch | Training and custom inference |
| TensorFlow | Training and custom inference |
| ONNX | Model conversion and inference |

---

## Technology Stack

| Layer | Technologies |
|-------|--------------|
| Frontend | Next.js 14, React 18, TypeScript, Tailwind, Ant Design |
| Backend Services | Python 3.11, FastAPI, Pydantic, SQLAlchemy |
| Gateway | Rust, Axum, Tokio |
| Databases | PostgreSQL, ClickHouse, MongoDB, Redis |
| Infrastructure | Kubernetes, Helm, Terraform/OpenTofu, Ansible |
| Service Mesh | Dapr (service invocation, pub/sub, workflows, state) |
| Observability | Grafana, Loki, Tempo, Mimir, Prometheus |
| Auth | Keycloak |
| Storage | MinIO (S3-compatible) |

---

## Key Differentiators

| vs. | Bud AI Foundry Advantage |
|-----|--------------------------|
| Manual K8s + Helm | Automated provisioning, no YAML wrangling |
| Cloud-specific tools (SageMaker, Vertex) | Multi-cloud, no vendor lock-in |
| Open-source MLOps (MLflow, Kubeflow) | Integrated platform vs. assembly required |
| Generic inference servers | ML-powered optimization, not just serving |

---

## Getting Started

### Quick Evaluation

```bash
# Clone and start with Docker Compose
git clone https://github.com/budai/bud-tools
cd bud-tools
nix develop  # or install dependencies manually

# Start the platform
cd services/budadmin && npm install && npm run dev  # Dashboard on :8007
cd services/budapp && ./deploy/start_dev.sh         # API on :9081
```

### Production Deployment

```bash
# Deploy via Helm
helm install bud infra/helm/bud/ \
  --set global.domain=ai.company.com \
  --set keycloak.enabled=true \
  --set postgresql.enabled=true

# Or use Terraform for full infrastructure
cd infra/tofu
tofu init && tofu plan && tofu apply
```

---

## Related Documentation

- [Architecture Whitepaper](./architecture-whitepaper.md)
- [Security Architecture](../security/security-architecture.md)
- [Deployment Guide](../infrastructure/installation-guide.md)
- [API Reference](../api/api-reference.md)
