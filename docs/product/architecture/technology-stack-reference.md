# Bud AI Foundry - Technology Stack Reference

---

## Overview

Complete reference of all technologies, frameworks, libraries, and their versions used in Bud AI Foundry.

---

## Programming Languages

| Language | Version | Usage |
|----------|---------|-------|
| **Python** | 3.11 | Backend services (budapp, budcluster, budsim, etc.) |
| **Rust** | 1.70+ | budgateway (high-performance inference routing) |
| **TypeScript** | 5.x | Frontend applications (budadmin, budplayground, budCustomer) |
| **Go** | 1.21+ | Dapr sidecar (daprd) |
| **HCL** | 2.x | Terraform/OpenTofu configurations |
| **YAML** | - | Kubernetes manifests, Ansible playbooks, Helm charts |

---

## Backend Frameworks

### Python Services

| Framework/Library | Version | Purpose |
|-------------------|---------|---------|
| **FastAPI** | 0.109+ | REST API framework |
| **Pydantic** | 2.x | Data validation and schemas |
| **SQLAlchemy** | 2.x | ORM for PostgreSQL |
| **Alembic** | 1.13+ | Database migrations |
| **structlog** | 24.x | Structured logging |
| **httpx** | 0.27+ | Async HTTP client |
| **uvicorn** | 0.27+ | ASGI server |

### ML/Optimization Libraries

| Library | Version | Service | Purpose |
|---------|---------|---------|---------|
| **XGBoost** | 2.x | budsim | ML-based performance prediction |
| **DEAP** | 1.4+ | budsim | Genetic algorithms for optimization |
| **NumPy** | 1.26+ | budsim | Numerical computations |
| **Pandas** | 2.x | budsim, budmetrics | Data manipulation |
| **scikit-learn** | 1.4+ | budsim | ML utilities |

### Infrastructure Libraries

| Library | Version | Service | Purpose |
|---------|---------|---------|---------|
| **python-terraform** | 1.x | budcluster | Terraform execution wrapper |
| **ansible-runner** | 2.x | budcluster | Ansible playbook execution |
| **kubernetes** | 29.x | budcluster | Kubernetes API client |
| **boto3** | 1.34+ | budcluster | AWS SDK |
| **azure-identity** | 1.15+ | budcluster | Azure authentication |
| **azure-mgmt-containerservice** | 30.x | budcluster | Azure AKS management |

### Security Libraries

| Library | Version | Service | Purpose |
|---------|---------|---------|---------|
| **cryptography** | 42.x | budcluster | RSA/AES encryption |
| **python-jose** | 3.3+ | budapp | JWT handling |
| **passlib** | 1.7+ | budapp | Password hashing |

### Rust Service (budgateway)

| Crate | Version | Purpose |
|-------|---------|---------|
| **tokio** | 1.x | Async runtime |
| **axum** | 0.7+ | Web framework |
| **reqwest** | 0.11+ | HTTP client |
| **serde** | 1.x | Serialization |
| **toml** | 0.8+ | Configuration parsing |
| **tracing** | 0.1+ | Instrumentation |

---

## Frontend Frameworks

### Next.js Applications

| Framework/Library | Version | Purpose |
|-------------------|---------|---------|
| **Next.js** | 14.x | React framework with SSR |
| **React** | 18.x | UI library |
| **TypeScript** | 5.x | Type safety |
| **Zustand** | 4.x | State management |
| **Ant Design** | 5.x | UI component library (budadmin) |
| **Radix UI** | 1.x | Headless UI primitives |
| **Tailwind CSS** | 3.x | Utility-first CSS |
| **SWR** | 2.x | Data fetching |
| **Axios** | 1.x | HTTP client |

---

## Databases

### PostgreSQL

| Component | Version | Purpose |
|-----------|---------|---------|
| **pgvector** | 0.6+ | Vector similarity search (optional) |

### ClickHouse

| Component | Version | Purpose |
|-----------|---------|---------|
| **ClickHouse** | 24.x | Time-series analytics (budmetrics) |

### MongoDB

| Component | Version | Purpose |
|-----------|---------|---------|
| **MongoDB** | 7.x | Document store (budnotify) |

### Valkey/Redis

| Component | Version | Purpose |
|-----------|---------|---------|
| **Valkey** | 7.x | Redis-compatible cache, Dapr state/pub-sub |

---

## Service Mesh

### Dapr

| Component | Version | Purpose |
|-----------|---------|---------|
| **Dapr Runtime** | 1.13+ | Service mesh sidecar |
| **Dapr CLI** | 1.13+ | Development tooling |
| **Dapr Dashboard** | 0.14+ | Monitoring UI |

### Dapr Components

| Component Type | Implementation | Purpose |
|----------------|----------------|---------|
| **State Store** | Valkey | Distributed state |
| **Pub/Sub** | Valkey | Event messaging |
| **Secret Store** | Kubernetes | Secret management |
| **Binding (Cron)** | Built-in | Scheduled tasks |

---

## Infrastructure

### Container Orchestration

| Component | Version | Purpose |
|-----------|---------|---------|
| **Kubernetes** | 1.26+ | Container orchestration |
| **Helm** | 3.14+ | Package management |
| **Docker** | 24.x | Container runtime |
| **containerd** | 1.7+ | Container runtime (production) |

### Infrastructure as Code

| Tool | Version | Purpose |
|------|---------|---------|
| **Terraform** | 1.7+ | Cloud infrastructure |
| **OpenTofu** | 1.6+ | Open-source Terraform alternative |
| **Ansible** | 2.16+ | Configuration management |
| **Ansible Runner** | 2.x | Programmatic Ansible execution |

### Cloud SDKs

| SDK | Version | Cloud |
|-----|---------|-------|
| **AWS CDK** | 2.x | AWS (optional) |
| **Terraform AWS Provider** | 5.x | AWS provisioning |
| **Terraform Azure Provider** | 3.x | Azure provisioning |
| **eksctl** | 0.175+ | EKS cluster management |
| **Azure CLI** | 2.x | Azure management |

---

## Observability

### LGTM Stack

| Component | Version | Purpose |
|-----------|---------|---------|
| **Grafana** | 10.x | Dashboards and visualization |
| **Loki** | 2.9+ | Log aggregation |
| **Tempo** | 2.4+ | Distributed tracing |
| **Mimir** | 2.12+ | Long-term metrics storage |
| **Prometheus** | 2.50+ | Metrics collection |

### Instrumentation

| Library | Version | Language | Purpose |
|---------|---------|----------|---------|
| **OpenTelemetry** | 1.x | Python/Rust | Unified telemetry |
| **opentelemetry-instrumentation-fastapi** | 0.45+ | Python | Auto-instrumentation |
| **tracing-opentelemetry** | 0.23+ | Rust | Rust tracing bridge |
| **Prometheus client** | 0.20+ | Python | Metrics export |

---

## Security

### Identity & Access

| Component | Version | Purpose |
|-----------|---------|---------|
| **Keycloak** | 24.x | Identity provider |
| **OpenID Connect** | 1.0 | Authentication protocol |
| **SAML 2.0** | 2.0 | Federation protocol |

### Encryption

| Standard | Implementation | Purpose |
|----------|----------------|---------|
| **TLS** | 1.3 | Transport encryption |
| **mTLS** | Dapr Sentry | Service mesh encryption |
| **AES** | 256-bit | Data at rest |
| **RSA** | 4096-bit | Key wrapping |

### Scanning

| Tool | Version | Purpose |
|------|---------|---------|
| **ClamAV** | 1.x | Model artifact scanning |
| **Trivy** | 0.50+ | Container vulnerability scanning |

---

## Development Tools

### Python

| Tool | Version | Purpose |
|------|---------|---------|
| **Ruff** | 0.3+ | Linting and formatting |
| **mypy** | 1.9+ | Type checking |
| **pytest** | 8.x | Testing |
| **pre-commit** | 3.x | Git hooks |

### TypeScript

| Tool | Version | Purpose |
|------|---------|---------|
| **ESLint** | 8.x | Linting |
| **Prettier** | 3.x | Formatting |
| **Jest** | 29.x | Testing |

### Rust

| Tool | Version | Purpose |
|------|---------|---------|
| **Clippy** | latest | Linting |
| **rustfmt** | latest | Formatting |
| **cargo-nextest** | 0.9+ | Testing |

---

## CI/CD

| Tool | Version | Purpose |
|------|---------|---------|
| **GitHub Actions** | - | CI/CD workflows |
| **ArgoCD** | 2.10+ | GitOps deployment (optional) |
| **Flux** | 2.x | GitOps deployment (optional) |
| **Kaniko** | 1.x | Container image building |

---

## Notification Services

| Component | Version | Purpose |
|-----------|---------|---------|
| **Novu** | 0.24+ | Notification orchestration |
| **SMTP** | - | Email delivery |
| **Twilio** | - | SMS delivery (optional) |
| **Firebase** | - | Push notifications (optional) |

---

## Version Compatibility Matrix

### Kubernetes Compatibility

| Bud Version | K8s 1.26 | K8s 1.27 | K8s 1.28 | K8s 1.29 | K8s 1.30 |
|-------------|----------|----------|----------|----------|----------|
| 1.0.x | Yes | Yes | Yes | Yes | Yes |

### Cloud Provider Compatibility

| Bud Version | AWS EKS | Azure AKS | GKE | OpenShift |
|-------------|---------|-----------|-----|-----------|
| 1.0.x | 1.26+ | 1.26+ | Planned | 4.14+ |

### Database Compatibility

| Bud Version | PostgreSQL | ClickHouse | MongoDB | Valkey/Redis |
|-------------|------------|------------|---------|--------------|
| 1.0.x | 14+ | 23+ | 6+ | 7+ / 6+ |
