# Bud AI Foundry - Architecture Whitepaper

---

## Overview

This whitepaper provides a comprehensive view of Bud AI Foundry's architecture, design principles, and technical decisions for enterprise architects, technical decision-makers, and engineering teams evaluating the platform.

---

## Executive Summary

Bud AI Foundry addresses the complexity of enterprise GenAI deployment through a unified control plane architecture that:

- **Abstracts infrastructure complexity** across multiple cloud providers and on-premises environments
- **Optimizes performance automatically** using ML-based simulation and genetic algorithms
- **Provides enterprise-grade security** with defense-in-depth, encryption, and comprehensive audit trails
- **Scales horizontally** from pilot deployments to organization-wide AI infrastructure

The platform follows a microservices architecture with Dapr service mesh, enabling loose coupling, independent scaling, and operational resilience.

---

## Design Principles

### 1. Cloud-Agnostic by Design

The platform treats Kubernetes as the universal abstraction layer:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Bud AI Foundry Control Plane                     │
│                                                                      │
│  Single management interface for all workload clusters regardless   │
│  of cloud provider, region, or deployment model                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│    AWS EKS    │      │   Azure AKS   │      │  On-Premises  │
│               │      │               │      │               │
│  • us-east-1  │      │  • eastus     │      │  • DC1        │
│  • eu-west-1  │      │  • westeurope │      │  • DC2        │
└───────────────┘      └───────────────┘      └───────────────┘
```

Cloud-specific implementations are encapsulated in:
- **Terraform modules** for provisioning (AWS EKS, Azure AKS)
- **Ansible playbooks** for on-premises and post-provisioning configuration
- **Credential encryption** using RSA-4096 with cloud-agnostic key management

### 2. Intelligent Optimization Over Manual Configuration

Rather than requiring users to manually configure GPU allocation, parallelism settings, and batch sizes, the platform uses **budsim** to automatically determine optimal configurations:

| Optimization Method | Approach | Best For |
|---------------------|----------|----------|
| **REGRESSOR** | XGBoost ML model + DEAP genetic algorithm | All parameters, maximum accuracy |
| **HEURISTIC** | Memory-based calculations | TP/PP only, faster results |

The optimizer considers:
- Model architecture (parameter count, attention heads, layers)
- Hardware capabilities (GPU memory, compute units, interconnects)
- Performance targets (latency, throughput, cost)
- Deployment constraints (max replicas, available nodes)

### 3. Security as a Foundation

Security is not an afterthought but a foundational design principle:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Security Layers                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Layer 1: Identity & Access                                   │   │
│  │ • Keycloak with SAML 2.0 / OIDC federation                  │   │
│  │ • Multi-realm multi-tenancy                                  │   │
│  │ • Role-based access control (RBAC)                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Layer 2: Network Security                                    │   │
│  │ • TLS 1.3 for all external traffic                          │   │
│  │ • mTLS within service mesh (Dapr)                           │   │
│  │ • Network policies for pod-level isolation                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Layer 3: Data Protection                                     │   │
│  │ • AES-256 encryption at rest                                │   │
│  │ • RSA-4096 key wrapping for secrets                         │   │
│  │ • Encrypted kubeconfigs and credentials                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Layer 4: Audit & Compliance                                  │   │
│  │ • Tamper-proof audit trail (hash chain)                     │   │
│  │ • All API actions logged with user context                  │   │
│  │ • Configurable retention policies                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 4. Observable by Default

Every component is instrumented for observability using the LGTM stack:

| Component | Purpose | Data Store |
|-----------|---------|------------|
| **Grafana** | Visualization, dashboards, alerting | - |
| **Loki** | Log aggregation and search | Object storage |
| **Tempo** | Distributed tracing | Object storage |
| **Mimir** | Long-term metrics storage | Object storage |
| **ClickHouse** | Inference-specific time-series analytics | Local |

OpenTelemetry collectors provide unified data ingestion across all services.

---

## Architectural Layers

### Layer 1: Presentation

The presentation layer provides user interfaces for different personas:

| Component | Technology | Users |
|-----------|------------|-------|
| **budadmin** | Next.js 14, Zustand, Ant Design | Platform admins, MLOps engineers |
| **budplayground** | Next.js, React | ML engineers, developers |
| **budCustomer** | Next.js, React | End customers, billing admins |

Key architectural decisions:
- **Server-side rendering (SSR)** for initial page loads
- **Zustand** for client-state management (lighter than Redux)
- **Centralized API client** (`pages/api/requests.ts`) for consistent error handling

### Layer 2: API Gateway

**budgateway** is a high-performance Rust service that handles all inference traffic:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         budgateway (Rust)                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Request Flow:                                                       │
│                                                                      │
│  Client ──► Auth ──► Route Resolution ──► Provider Proxy ──► Model  │
│     │         │              │                   │             │     │
│     │    API Key        Model ID →          Transform &        │     │
│     │    Validation     Provider Lookup     Forward            │     │
│     │                                                          │     │
│     ◄──────────────────────────────────────────────────────────┘     │
│                     Stream Response                                  │
│                                                                      │
│  Capabilities:                                                       │
│  • OpenAI-compatible API (/v1/chat/completions, etc.)              │
│  • Multi-provider routing with fallback chains                      │
│  • Request/response streaming                                        │
│  • <1ms P99 gateway latency                                         │
│  • TOML-based declarative configuration                             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Layer 3: Service Mesh

All Python services run with Dapr sidecars, providing:

| Capability | Implementation | Use Case |
|------------|----------------|----------|
| **Service Invocation** | HTTP/gRPC with retries | Inter-service RPC |
| **State Management** | Valkey (Redis-compatible) | Workflow state, caching |
| **Pub/Sub** | Valkey | Event-driven communication |
| **Workflows** | Dapr Workflow API | Long-running orchestrations |
| **Secrets** | Kubernetes Secret Store | Centralized secret access |
| **Cron Bindings** | Built-in scheduler | Scheduled tasks |

The sidecar pattern provides these capabilities without code changes:

```
┌──────────────────────────────────────────────────────────────────┐
│                         Kubernetes Pod                            │
│  ┌─────────────────────┐      ┌─────────────────────┐           │
│  │   Application       │◄────►│   Dapr Sidecar      │           │
│  │   Container         │      │   (daprd)           │           │
│  │                     │      │                     │           │
│  │  • FastAPI app      │      │  • Service mesh     │           │
│  │  • Business logic   │      │  • State store      │           │
│  │  • No Dapr SDK      │      │  • Pub/sub broker   │           │
│  │    required         │      │  • Secret store     │           │
│  └─────────────────────┘      └─────────────────────┘           │
│                                        │                         │
│                               HTTP localhost:3500                │
│                               (Dapr API)                         │
└──────────────────────────────────────────────────────────────────┘
```

### Layer 4: Microservices

#### Core Services

| Service | Responsibility | Database | Key Dependencies |
|---------|----------------|----------|------------------|
| **budapp** | Core API, auth, users, projects, endpoints | PostgreSQL | Keycloak, all services |
| **budcluster** | Cluster lifecycle, provisioning, deployment | PostgreSQL | Terraform, Ansible, cloud APIs |
| **budsim** | Performance optimization and prediction | PostgreSQL | XGBoost, DEAP |
| **budmodel** | Model registry, metadata, security scanning | PostgreSQL | HuggingFace, ClamAV |
| **budmetrics** | Inference observability, time-series analytics | ClickHouse | LGTM stack |
| **budpipeline** | Workflow orchestration, DAG execution | PostgreSQL | All services via Dapr |

#### Supporting Services

| Service | Responsibility | Database |
|---------|----------------|----------|
| **budeval** | Model evaluation, benchmarking | PostgreSQL |
| **budnotify** | Notifications (email, SMS, push) | MongoDB |
| **ask-bud** | AI assistant for cluster/performance Q&A | PostgreSQL |

#### Service Code Pattern

All Python services follow a consistent structure:

```
service_name/
├── routes.py          # FastAPI endpoints
├── services.py        # Business logic
├── crud.py            # Database operations
├── models.py          # SQLAlchemy models
├── schemas.py         # Pydantic schemas
├── workflows.py       # Dapr workflows (if applicable)
└── deploy/
    ├── start_dev.sh   # Development startup
    └── docker-compose.yaml
```

### Layer 5: Data

The data layer uses purpose-built databases for different access patterns:

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Data Architecture                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    PostgreSQL (OLTP)                         │   │
│  │                                                              │   │
│  │  budapp_db      │ budcluster_db │ budsim_db    │ budmodel_db│   │
│  │  • Users        │ • Clusters    │ • Simulations│ • Models   │   │
│  │  • Projects     │ • Deployments │ • Results    │ • Licenses │   │
│  │  • Endpoints    │ • Credentials │              │ • Benchmarks│  │
│  │                 │               │              │            │   │
│  │  budpipeline_db │ budeval_db    │ askbud_db    │            │   │
│  │  • Pipelines    │ • Evaluations │ • Sessions   │            │   │
│  │  • Executions   │ • Benchmarks  │ • Context    │            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────┐      ┌─────────────────────┐              │
│  │  ClickHouse (OLAP)  │      │    MongoDB          │              │
│  │                     │      │                     │              │
│  │  • Inference metrics│      │  • Notifications    │              │
│  │  • Token counts     │      │  • Novu data        │              │
│  │  • Latency tracking │      │  • Audit logs       │              │
│  │  • Cost analytics   │      │                     │              │
│  └─────────────────────┘      └─────────────────────┘              │
│                                                                      │
│  ┌─────────────────────┐      ┌─────────────────────┐              │
│  │   Valkey (Cache)    │      │    MinIO (Objects)  │              │
│  │                     │      │                     │              │
│  │  • Dapr state store │      │  • Model artifacts  │              │
│  │  • Dapr pub/sub     │      │  • Datasets         │              │
│  │  • Session cache    │      │  • Backups          │              │
│  │  • Rate limiting    │      │  • Log archives     │              │
│  └─────────────────────┘      └─────────────────────┘              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Layer 6: Infrastructure

Infrastructure is managed through:

| Tool | Scope | Location |
|------|-------|----------|
| **Helm** | Kubernetes deployments | `infra/helm/bud/` |
| **Terraform/OpenTofu** | Cloud infrastructure | `infra/tofu/` |
| **Ansible** | Post-provisioning, on-prem | `budcluster/playbooks/` |

---

## Key Workflows

### Model Deployment Workflow

```
User Request → budapp → budsim (optimize) → budcluster (deploy) → Target Cluster

1. User selects model and target cluster in budadmin
2. budapp validates permissions, creates endpoint record
3. budsim runs optimization:
   - Fetches model metadata (parameters, architecture)
   - Fetches cluster hardware specs (GPUs, memory)
   - Runs XGBoost prediction + genetic algorithm
   - Returns optimal: TP, PP, batch size, replicas
4. budcluster deploys runtime:
   - Transfers model to cluster storage
   - Generates Helm values from optimization
   - Deploys vLLM/SGLang with configuration
   - Configures ingress and service
5. budmetrics begins collecting inference metrics
6. budadmin receives status updates via WebSocket
```

### Cluster Provisioning Workflow

```
User Config → budapp → budcluster (Dapr Workflow) → Cloud Provider

Cloud Provisioning (AWS/Azure):
1. Terraform plan/apply for:
   - VPC/subnet configuration
   - Kubernetes cluster
   - Node pools with GPU instances
   - IAM roles and security groups

On-Premises Onboarding:
1. Ansible playbooks validate and configure:
   - Connectivity verification
   - Dependency installation
   - Kubernetes configuration

Post-Provisioning (All):
2. Install NFD for hardware detection
3. Install GPU Operator (if NVIDIA detected)
4. Install HAMI for GPU time-slicing
5. Deploy Prometheus monitoring stack
6. Encrypt and store kubeconfig
```

---

## Deployment Topologies

### Single-Cluster (Evaluation)

All components in one Kubernetes cluster:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Single Kubernetes Cluster                         │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Control Plane Namespace (bud-system)                        │   │
│  │  • All Bud services, databases, observability               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Workload Namespace (bud-workloads)                          │   │
│  │  • Model runtimes (vLLM, SGLang)                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Multi-Cluster (Production)

Dedicated control plane with distributed workload clusters:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Control Plane Cluster                           │
│  • All Bud services    • Databases       • Observability            │
│  • High availability   • Regular backups  • DR configured           │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
          ▼                        ▼                        ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  AWS EKS (Prod)  │    │  Azure AKS (EU)  │    │   On-Prem (DR)   │
│  us-east-1       │    │  westeurope      │    │   Data Center    │
├──────────────────┤    ├──────────────────┤    ├──────────────────┤
│ • GPU node pools │    │ • GPU node pools │    │ • NVIDIA DGX     │
│ • Model runtimes │    │ • Model runtimes │    │ • Model runtimes │
│ • Prometheus     │    │ • Prometheus     │    │ • Prometheus     │
│ • NFD + HAMI     │    │ • NFD + HAMI     │    │ • NFD + HAMI     │
└──────────────────┘    └──────────────────┘    └──────────────────┘
```

---

## Scalability

### Horizontal Scaling

| Component | Scaling Strategy | Trigger |
|-----------|------------------|---------|
| **API Services** | Kubernetes HPA | CPU/memory thresholds |
| **budgateway** | HPA + load balancer | Request rate, latency |
| **Model Runtimes** | Cluster autoscaler | GPU utilization, queue depth |
| **Databases** | Read replicas, connection pooling | Query load |
| **Valkey** | Cluster mode | Memory, throughput |

### Tested Scale

| Metric | Validated Capacity |
|--------|-------------------|
| **Managed Clusters** | 50+ per control plane |
| **Concurrent Deployments** | 200+ active endpoints |
| **Inference Throughput** | 10,000+ req/sec (gateway) |
| **Model Size** | Up to 405B parameters |
| **Users** | 1,000+ concurrent |

---

## Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Service Mesh** | Dapr | Built-in workflows, state, pub/sub without custom infrastructure |
| **API Gateway** | Custom Rust (budgateway) | Sub-ms latency critical for inference; OpenAI compatibility |
| **Primary Database** | PostgreSQL | ACID compliance, mature tooling, Alembic migrations |
| **Time-Series** | ClickHouse | Column-oriented for analytics queries on metrics |
| **Cache/State** | Valkey | Redis-compatible, open-source, Dapr integration |
| **Object Storage** | MinIO | S3-compatible, on-prem friendly |
| **IaC** | Terraform + Ansible | Terraform for cloud, Ansible for K8s configuration |
| **Frontend** | Next.js + Zustand | SSR, modern React, lightweight state management |

---

## Related Documents

- [High-Level Design](./high-level-architecture.md) - Component details
- [Deployment Architecture](./deployment-architecture.md) - Environment topology
- [Platform Datasheet](./platform-datasheet.md) - Technical specifications
- [Product Overview](./product-overview.md) - Executive summary
