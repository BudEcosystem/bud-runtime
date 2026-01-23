# Bud AI Foundry - Component Catalog

---

## Overview

Complete catalog of all platform components including services, databases, infrastructure, and external integrations.

---

## Backend Services

### Core Services (Python/FastAPI)

| Component | App ID | Port | Description |
|-----------|--------|------|-------------|
| **budapp** | budapp | 9081 | Core API handling users, projects, models, endpoints, and Keycloak authentication |
| **budcluster** | budcluster | 9082 | Cluster lifecycle management for AWS EKS, Azure AKS, and on-premises via Terraform/Ansible |
| **budsim** | budsim | 9083 | Performance simulation using XGBoost + genetic algorithms for deployment optimization |
| **budmodel** | budmodel | 9084 | Model registry for metadata, licensing, security scanning, and leaderboard data |
| **budmetrics** | budmetrics | 9085 | Observability service for inference tracking and time-series analytics |
| **budpipeline** | budpipeline | 9086 | Workflow orchestration for DAG execution, scheduling, and event-driven pipelines |
| **budeval** | budeval | 9087 | Model evaluation and benchmarking service |
| **budnotify** | budnotify | 9088 | Notification service wrapping Novu for email, SMS, push, and in-app notifications |
| **ask-bud** | ask-bud | 9089 | AI assistant for cluster analysis, performance Q&A, and troubleshooting |

### Gateway Service (Rust)

| Component | Port | Description |
|-----------|------|-------------|
| **budgateway** | 3000 | High-performance API gateway for model inference routing, OpenAI-compatible API |

---

## Frontend Services

### Web Applications (TypeScript/Next.js)

| Component | Port | Description |
|-----------|------|-------------|
| **budadmin** | 8007 | Main dashboard for deployments, clusters, models, and infrastructure management |
| **budplayground** | 8008 | Interactive AI model testing interface for prompt experimentation |
| **budCustomer** | 8009 | Customer-facing portal for usage dashboards, billing, and API key management |

---

## Databases

### Relational (PostgreSQL)

| Database | Owner Service | Purpose |
|----------|---------------|---------|
| **budapp_db** | budapp | Users, projects, models, endpoints, audit records |
| **budcluster_db** | budcluster | Clusters, deployments, encrypted credentials |
| **budsim_db** | budsim | Simulations, optimization results, hardware profiles |
| **budmodel_db** | budmodel | Model metadata, licenses, leaderboard, benchmarks |
| **budpipeline_db** | budpipeline | Pipelines, executions, progress tracking |
| **budeval_db** | budeval | Evaluations, benchmark results |
| **askbud_db** | ask-bud | Conversation sessions, context |

### Time-Series (ClickHouse)

| Database | Owner Service | Purpose |
|----------|---------------|---------|
| **budmetrics_db** | budmetrics | Inference metrics, token counts, latencies, cost analytics |

### Document Store (MongoDB)

| Database | Owner Service | Purpose |
|----------|---------------|---------|
| **budnotify_db** | budnotify | Notification records, Novu integration data |

### Cache/State (Valkey)

| Purpose | Description |
|---------|-------------|
| **Dapr State Store** | Workflow state, distributed locks |
| **Dapr Pub/Sub** | Event-driven messaging between services |
| **Session Cache** | User session data |
| **Rate Limiting** | API rate limit counters |

### Object Storage (MinIO)

| Bucket | Purpose |
|--------|---------|
| **models** | Model artifacts and weights |
| **datasets** | Training and evaluation datasets |
| **backups** | Database and configuration backups |
| **logs** | Archived log data |

---

## Service Mesh Components

### Dapr

| Component | Description |
|-----------|-------------|
| **Dapr Sidecar (daprd)** | Runs alongside each service, provides service mesh capabilities |
| **Dapr Placement** | Actor placement service for distributed state |
| **Dapr Operator** | Kubernetes operator for Dapr component management |
| **Dapr Sentry** | Certificate authority for mTLS |

### Dapr Building Blocks Used

| Building Block | Component | Description |
|----------------|-----------|-------------|
| **Service Invocation** | All services | HTTP/gRPC RPC with retries and circuit breaking |
| **State Management** | Valkey | Distributed state for workflows and caching |
| **Pub/Sub** | Valkey | Asynchronous event-driven communication |
| **Workflows** | Built-in | Long-running orchestration (provisioning, simulations) |
| **Secrets** | Kubernetes | Centralized secret management |
| **Bindings** | Cron | Scheduled tasks (leaderboard updates, cleanup) |

---

## Observability Stack (LGTM)

| Component | Purpose | Storage |
|-----------|---------|---------|
| **Grafana** | Dashboards, visualization, alerting | - |
| **Loki** | Log aggregation and search | MinIO |
| **Tempo** | Distributed tracing | MinIO |
| **Mimir** | Long-term metrics storage | MinIO |
| **Prometheus** | Metrics collection (per cluster) | Local |
| **OpenTelemetry Collector** | Unified telemetry data ingestion | - |

---

## Identity & Security

| Component | Description |
|-----------|-------------|
| **Keycloak** | Identity provider, SAML 2.0/OIDC federation, multi-realm tenancy |

### Encryption Components

| Component | Algorithm | Purpose |
|-----------|-----------|---------|
| **RSA Private Key** | RSA-4096 | Key wrapping, credential encryption |
| **Symmetric Key** | AES-256 | Data encryption at rest |
| **TLS Certificates** | TLS 1.3 | Transport encryption |

---

## Infrastructure as Code

### Terraform/OpenTofu Modules

| Module | Location | Description |
|--------|----------|-------------|
| **aws-eks** | `infra/tofu/aws/` | AWS EKS cluster provisioning |
| **azure-aks** | `infra/tofu/azure/` | Azure AKS cluster provisioning |
| **networking** | `infra/tofu/modules/networking/` | VPC, subnets, security groups |
| **iam** | `infra/tofu/modules/iam/` | IAM roles and policies |

### Ansible Playbooks

| Playbook | Location | Description |
|----------|----------|-------------|
| **cluster-onboard** | `budcluster/playbooks/` | Onboard existing Kubernetes clusters |
| **runtime-deploy** | `budcluster/playbooks/` | Deploy model runtimes |
| **nfd-install** | `budcluster/playbooks/` | Node Feature Discovery installation |
| **hami-install** | `budcluster/playbooks/` | GPU time-slicing setup |
| **gpu-operator** | `budcluster/playbooks/` | NVIDIA GPU Operator installation |

### Helm Charts

| Chart | Location | Description |
|-------|----------|-------------|
| **bud** | `infra/helm/bud/` | Main umbrella chart for all services |
| **novu** | `infra/helm/novu/` | Notification service dependencies |
| **onyx** | `infra/helm/onyx/` | Document processing service |

---

## Helm Chart Dependencies

| Dependency | Chart | Version | Description |
|------------|-------|---------|-------------|
| PostgreSQL | bitnami/postgresql | 16.7.18 | Primary relational database |
| Valkey | bitnami/valkey | 3.0.20 | Redis-compatible cache/state |
| ClickHouse | bitnami/clickhouse | 9.3.9 | Time-series database |
| MinIO | bitnami/minio | 17.0.15 | S3-compatible object storage |
| Keycloak | bitnami/keycloak | 24.7.7 | Identity provider |
| Kafka | bitnami/kafka | 32.3.5 | Event streaming (optional) |
| MongoDB | bitnami/mongodb | 16.5.31 | Document database |
| Prometheus | prometheus-community | 25.27.0 | Metrics collection |

---

## External Integrations

### Cloud Providers

| Provider | Integration | Description |
|----------|-------------|-------------|
| **AWS** | EKS, S3, IAM, Secrets Manager, Route53 | Cluster provisioning, storage, identity |
| **Azure** | AKS, Blob Storage, AAD, Key Vault, DNS | Cluster provisioning, storage, identity |

### AI Model Providers

| Provider | Integration | Description |
|----------|-------------|-------------|
| **OpenAI** | API proxy | GPT-4, GPT-3.5, embeddings |
| **Anthropic** | API proxy | Claude models |
| **Azure OpenAI** | API proxy | Enterprise OpenAI deployment |
| **Together AI** | API proxy | Open-source model hosting |
| **Anyscale** | API proxy | Managed inference |

### Model Registries

| Registry | Integration | Description |
|----------|-------------|-------------|
| **HuggingFace Hub** | Model download | Pre-trained model access |
| **Custom S3/MinIO** | Model storage | Private model hosting |

### Identity Providers

| Provider | Protocol | Description |
|----------|----------|-------------|
| **LDAP** | LDAP | Directory services |
| **Active Directory** | LDAP/SAML | Microsoft identity |
| **Okta** | SAML 2.0/OIDC | Enterprise SSO |
| **Azure AD** | SAML 2.0/OIDC | Microsoft cloud identity |

### Monitoring Integrations

| System | Integration | Description |
|--------|-------------|-------------|
| **Datadog** | OpenTelemetry | APM and infrastructure monitoring |
| **Splunk** | Log forwarding | SIEM integration |
| **PagerDuty** | Alertmanager | Incident management |
| **Slack** | Webhooks | Alert notifications |

---

## GPU/Accelerator Support

### Hardware Detection

| Component | Description |
|-----------|-------------|
| **NFD (Node Feature Discovery)** | Detects hardware capabilities on cluster nodes |
| **GPU Operator** | NVIDIA driver and runtime management |
| **HAMI** | GPU time-slicing for multi-tenant workloads |

### Supported GPUs

| Vendor | Models |
|--------|--------|
| **NVIDIA** | A100, H100, L40S, A10G, T4, V100 |
| **Intel** | Gaudi (HPU) |
| **AMD** | MI300 (experimental) |

---

## Model Runtimes

| Runtime | Description |
|---------|-------------|
| **vLLM** | High-throughput LLM inference with PagedAttention |
| **SGLang** | Structured generation with RadixAttention |
| **TensorRT-LLM** | NVIDIA-optimized inference |
| **ONNX Runtime** | Cross-platform inference |

---

## Component Communication Matrix

| From | To | Protocol | Description |
|------|-----|----------|-------------|
| budadmin | budapp | HTTPS | All management API calls |
| budapp | budcluster | Dapr HTTP | Cluster operations |
| budapp | budsim | Dapr HTTP | Optimization requests |
| budapp | budpipeline | Dapr HTTP | Pipeline execution |
| budpipeline | budcluster | Dapr HTTP | Model deployment steps |
| budpipeline | * | Dapr Pub/Sub | Event completion notifications |
| budcluster | Cloud APIs | HTTPS | Terraform/Ansible execution |
| budgateway | Model Runtimes | HTTP/gRPC | Inference requests |
| budgateway | External Providers | HTTPS | Provider API proxy |
| * | Valkey | Redis protocol | State and pub/sub |
| * | PostgreSQL | PostgreSQL | Data persistence |
| * | Keycloak | OIDC/SAML | Authentication |

---

## Related Documents

- [High-Level Architecture](./high-level-architecture.md) - Component interactions
- [Technology Stack Reference](./technology-stack-reference.md) - Framework versions
- [Deployment Architecture](./deployment-architecture.md) - Environment topology
