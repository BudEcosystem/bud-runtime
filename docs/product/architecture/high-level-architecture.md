# Bud AI Foundry - High-Level Architecture

---

## Overview

This document describes the high-level architecture of Bud AI Foundry, including system components, their interactions, data flows, and design decisions.

---

## System Context

![System Context Diagram](../diagrams/system-context.png)
---

## Component Architecture

### Layer 1: Presentation Layer

![Presentation Layer](../diagrams/presentation-layer.png)

| Component | Technology | Purpose |
|-----------|------------|---------|
| budadmin | Next.js 14, Zustand, Ant Design | Primary admin dashboard for platform management |
| budplayground | Next.js, React | Interactive environment for model testing |
| budCustomer | Next.js, React | Customer-facing portal for usage and billing |
| budchat | Onyx (React) | RAG-powered chat interface with document connectors |

### Layer 2: API Gateway Layer

![API Gateway Layer](../diagrams/api-gateway-layer.png)

**Key Capabilities:**
- OpenAI-compatible API for all inference endpoints
- Multi-provider routing with fallback chains
- RSA-encrypted API key management
- Request/response streaming
- TOML-based declarative configuration

### Layer 3: Service Mesh Layer

![Service Mesh Layer](../diagrams/service-mesh-layer.png)

### Layer 4: Microservices Layer

![Microservices Layer](../diagrams/microservices-layer.png)

#### Service Responsibilities

| Service | Primary Responsibility | Database | Key Integrations |
|---------|----------------------|----------|------------------|
| **budapp** | Core API, auth, users, projects | PostgreSQL | Keycloak, all services |
| **budcluster** | Cluster lifecycle management | PostgreSQL | Terraform, Ansible, cloud APIs |
| **budsim** | Performance optimization | PostgreSQL | XGBoost, DEAP |
| **budmodel** | Model registry & metadata | PostgreSQL | HuggingFace, ClamAV |
| **budmetrics** | Observability & analytics | ClickHouse | LGTM stack |
| **budpipeline** | Workflow orchestration | PostgreSQL | All services via Dapr |
| **budeval** | Model evaluation | PostgreSQL | budmodel, budcluster |
| **budnotify** | Notifications | MongoDB | Novu |
| **ask-bud** | AI assistant | PostgreSQL | LLM providers |

### Layer 5: Data Layer

![Data Layer](../diagrams/data-layer.png)

### Layer 6: Infrastructure Layer

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Infrastructure Layer                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Kubernetes (Control Plane)                        │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  Helm Chart: infra/helm/bud/                                 │   │   │
│  │  │                                                              │   │   │
│  │  │  Dependencies:                                               │   │   │
│  │  │  • PostgreSQL (Bitnami 16.7.18)                             │   │   │
│  │  │  • Valkey/Redis (Bitnami 3.0.20)                            │   │   │
│  │  │  • ClickHouse (Bitnami 9.3.9)                               │   │   │
│  │  │  • MinIO (Bitnami 17.0.15)                                  │   │   │
│  │  │  • Keycloak (Bitnami 24.7.7)                                │   │   │
│  │  │  • Kafka (Bitnami 32.3.5)                                   │   │   │
│  │  │  • MongoDB (Bitnami 16.5.31)                                │   │   │
│  │  │  • Prometheus (prometheus-community 25.27.0)                │   │   │
│  │  │  • Novu (local chart 0.1.6)                                 │   │   │
│  │  │  • Onyx (local chart 0.4.4)                                 │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Observability Stack (LGTM)                        │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐        │   │
│  │  │  Grafana  │  │   Loki    │  │   Tempo   │  │   Mimir   │        │   │
│  │  │ Dashboards│  │   Logs    │  │  Traces   │  │  Metrics  │        │   │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘        │   │
│  │        │              │              │              │               │   │
│  │        └──────────────┴──────────────┴──────────────┘               │   │
│  │                              │                                       │   │
│  │                    ┌─────────┴─────────┐                            │   │
│  │                    │  OpenTelemetry    │                            │   │
│  │                    │    Collector      │                            │   │
│  │                    └───────────────────┘                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Infrastructure as Code                            │   │
│  │  ┌─────────────────────────┐  ┌─────────────────────────┐          │   │
│  │  │   Terraform/OpenTofu    │  │        Ansible          │          │   │
│  │  │   infra/tofu/           │  │   budcluster/playbooks/ │          │   │
│  │  ├─────────────────────────┤  ├─────────────────────────┤          │   │
│  │  │ • AWS EKS modules       │  │ • Runtime deployment    │          │   │
│  │  │ • Azure AKS modules     │  │ • NFD installation      │          │   │
│  │  │ • VPC/networking        │  │ • HAMI setup            │          │   │
│  │  │ • IAM/security          │  │ • GPU Operator          │          │   │
│  │  │ • Storage classes       │  │ • Prometheus stack      │          │   │
│  │  └─────────────────────────┘  └─────────────────────────┘          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flows

### 1. Model Deployment Flow

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ budadmin │───►│  budapp  │───►│ budsim   │───►│budcluster│───►│  Target  │
│   UI     │    │   API    │    │Optimizer │    │ Deploy   │    │ Cluster  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │
     │  1. Deploy    │  2. Get       │  3. Return    │  4. Deploy    │
     │     Request   │    optimal    │    config     │    runtime    │
     │               │    config     │               │               │
     ▼               ▼               ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Deployment Workflow                             │
│                                                                          │
│  1. User initiates deployment from dashboard                            │
│  2. budapp validates request, checks permissions                        │
│  3. budsim runs optimization (XGBoost + genetic algorithm)             │
│     - Predicts TTFT, throughput, latency                               │
│     - Optimizes TP/PP, batch size, GPU allocation                      │
│  4. budcluster provisions runtime:                                      │
│     - Transfers model to cluster storage                               │
│     - Deploys Helm chart with optimized config                         │
│     - Configures ingress/service                                       │
│  5. budmetrics starts collecting inference metrics                     │
│  6. Dashboard shows deployment status via WebSocket                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2. Inference Request Flow

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Client  │───►│budgateway│───►│  Model   │───►│budmetrics│
│   App    │    │  Router  │    │ Runtime  │    │ Metrics  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │
     │  1. POST      │  2. Route to  │  3. Inference │
     │  /v1/chat/    │    provider   │    response   │
     │  completions  │               │               │
     ▼               ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Inference Flow                                  │
│                                                                          │
│  1. Client sends OpenAI-compatible request to budgateway               │
│  2. Gateway authenticates via API key (optional RSA decryption)        │
│  3. Gateway resolves model → provider routing                          │
│  4. Request forwarded to:                                              │
│     - Local vLLM/SGLang runtime on managed cluster                     │
│     - External provider (OpenAI, Anthropic, Together, etc.)            │
│  5. Response streamed back to client                                   │
│  6. Metrics recorded in ClickHouse:                                    │
│     - Token counts (input/output)                                      │
│     - Latency (TTFT, total)                                           │
│     - Cost calculation                                                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3. Cluster Provisioning Flow

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ budadmin │───►│  budapp  │───►│budcluster│───►│  Cloud   │
│   UI     │    │   API    │    │ Workflow │    │ Provider │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │
     │  1. Create    │  2. Start     │  3. Terraform │
     │    Cluster    │    workflow   │    apply      │
     ▼               ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Cluster Provisioning Workflow                       │
│                                                                          │
│  1. User submits cluster configuration                                  │
│  2. budapp creates cluster record, starts Dapr workflow                │
│  3. budcluster executes provisioning:                                  │
│                                                                          │
│     AWS EKS:                      Azure AKS:                            │
│     ┌────────────────────┐       ┌────────────────────┐                │
│     │ Terraform apply    │       │ Terraform apply    │                │
│     │ • VPC/subnets      │       │ • Resource group   │                │
│     │ • EKS cluster      │       │ • AKS cluster      │                │
│     │ • Node groups      │       │ • Node pools       │                │
│     │ • IAM roles        │       │ • AAD integration  │                │
│     └────────────────────┘       └────────────────────┘                │
│                                                                          │
│     On-Premises:                                                        │
│     ┌────────────────────┐                                             │
│     │ Ansible playbooks  │                                             │
│     │ • Validate access  │                                             │
│     │ • Install deps     │                                             │
│     │ • Configure K8s    │                                             │
│     └────────────────────┘                                             │
│                                                                          │
│  4. Post-provisioning setup:                                           │
│     • Deploy NFD for hardware detection                                │
│     • Install GPU Operator (if NVIDIA GPUs detected)                   │
│     • Install HAMI for GPU time-slicing                               │
│     • Deploy Prometheus stack                                          │
│                                                                          │
│  5. Kubeconfig encrypted and stored                                    │
│  6. Cluster status updated, UI notified                                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4. Pipeline Execution Flow

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ budadmin │───►│  budapp  │───►│budpipeline───►│ Target   │
│   UI     │    │  Proxy   │    │ Executor │    │ Services │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │
     │  1. Execute   │  2. Forward   │  3. Run DAG   │
     │    pipeline   │    to pipeline│    steps      │
     ▼               ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Pipeline Execution Flow                          │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        DAG Execution                             │   │
│  │                                                                  │   │
│  │   ┌───────┐     ┌───────┐     ┌───────┐     ┌───────┐          │   │
│  │   │Step 1 │────►│Step 2 │────►│Step 3 │────►│Step 4 │          │   │
│  │   │ Log   │     │ HTTP  │     │Model  │     │Notify │          │   │
│  │   └───────┘     └───────┘     │Deploy │     └───────┘          │   │
│  │                               └───┬───┘                         │   │
│  │                                   │                              │   │
│  │                          Awaiting Event                         │   │
│  │                                   │                              │   │
│  │                               ┌───┴───┐                         │   │
│  │                               │Event  │◄──── budcluster         │   │
│  │                               │Received│     (pub/sub)          │   │
│  │                               └───────┘                         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  Features:                                                              │
│  • Parallel step execution                                             │
│  • Event-driven completion for long-running ops                        │
│  • Progress tracking with weighted averaging                           │
│  • Callback topics for real-time updates                              │
│  • Optimistic locking for concurrent updates                          │
│  • Retry policies with exponential backoff                            │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Service Communication Patterns

### Synchronous (Dapr Service Invocation)

```
┌──────────┐         ┌──────────┐         ┌──────────┐
│ Service  │ ──────► │   Dapr   │ ──────► │ Service  │
│    A     │         │ Sidecar  │         │    B     │
└──────────┘         └──────────┘         └──────────┘

URL Pattern: {dapr_endpoint}/v1.0/invoke/{app_id}/method/{path}

Examples:
• budapp → budcluster: Get cluster status
• budapp → budpipeline: Execute pipeline
• budpipeline → budcluster: Deploy model
```

### Asynchronous (Dapr Pub/Sub)

```
┌──────────┐         ┌──────────┐         ┌──────────┐
│ Publisher│ ──────► │  Valkey  │ ◄────── │Subscriber│
│          │  topic  │ (Pub/Sub)│  topic  │          │
└──────────┘         └──────────┘         └──────────┘

Topics:
• workflow-events    - Pipeline event completion
• pipeline-notifications - Execution status updates
• {callback_topics}  - Client-specified progress updates
```

### Authentication Layers

| Layer | Mechanism | Purpose |
|-------|-----------|---------|
| External API | Keycloak JWT | User authentication |
| Service Mesh | Dapr API Token | Inter-service auth |
| Internal Endpoints | APP_API_TOKEN | Application-level validation |
| API Gateway | RSA-encrypted keys | Inference auth |

---

## Security Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Security Architecture                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Identity & Access Management                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │                      Keycloak                                │   │   │
│  │  │  • Multi-realm multi-tenancy                                │   │   │
│  │  │  • SAML 2.0 / OIDC federation                              │   │   │
│  │  │  • Role-based access control                               │   │   │
│  │  │  • JWT token issuance                                      │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Data Protection                                   │   │
│  │                                                                      │   │
│  │  At Rest:                      In Transit:                          │   │
│  │  • AES-256 encryption          • TLS 1.3 everywhere                │   │
│  │  • RSA-4096 for key wrap       • mTLS for service mesh             │   │
│  │  • Encrypted kubeconfigs       • Certificate rotation              │   │
│  │                                                                      │   │
│  │  Secrets:                                                           │   │
│  │  • K8s Secret Store            • HashiCorp Vault (optional)        │   │
│  │  • Dapr secret component       • Never plain-text in DB            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Audit & Compliance                                │   │
│  │                                                                      │   │
│  │  • Tamper-proof audit trail (hash chain)                           │   │
│  │  • All API actions logged with user context                        │   │
│  │  • Retention policies configurable                                  │   │
│  │  • Export for compliance reporting                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Scalability Considerations

### Horizontal Scaling

| Component | Scaling Strategy |
|-----------|-----------------|
| API Services | Kubernetes HPA based on CPU/memory |
| budgateway | HPA + load balancer for inference traffic |
| Model Runtimes | Node auto-scaling per cluster |
| Databases | Read replicas, connection pooling |
| Message Queue | Valkey cluster mode |

### Multi-Cluster Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Multi-Cluster Topology                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Control Plane Cluster                             │   │
│  │                                                                      │   │
│  │    All Bud services, databases, observability                       │   │
│  │    Single point of management for all workload clusters             │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│            ┌────────────────────┼────────────────────┐                     │
│            ▼                    ▼                    ▼                     │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐           │
│  │ Workload Cluster │ │ Workload Cluster │ │ Workload Cluster │           │
│  │   (AWS EKS)      │ │   (Azure AKS)    │ │   (On-Prem)      │           │
│  ├──────────────────┤ ├──────────────────┤ ├──────────────────┤           │
│  │ • Model runtimes │ │ • Model runtimes │ │ • Model runtimes │           │
│  │ • Prometheus     │ │ • Prometheus     │ │ • Prometheus     │           │
│  │ • NFD + HAMI     │ │ • NFD + HAMI     │ │ • NFD + HAMI     │           │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Service Mesh | Dapr | Built-in workflows, state, pub/sub - no custom infrastructure |
| API Gateway | Custom Rust | Sub-ms latency critical for inference; OpenAI compatibility |
| Databases | PostgreSQL + ClickHouse | OLTP for app data, OLAP for time-series metrics |
| State/Cache | Valkey (Redis-compatible) | Dapr integration, performance, open-source |
| IaC | Terraform + Ansible | Terraform for cloud, Ansible for K8s-level config |
| Frontend | Next.js + Zustand | SSR, modern React patterns, lightweight state |

---

## Related Documents

- [Product Overview](./product-overview.md)
- [Low-Level Design](./low-level-design.md)
- [Security Architecture](../security/security-architecture.md)
- [Deployment Architecture](./deployment-architecture.md)
- [Network Topology](./network-topology.md)
