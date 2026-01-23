# Bud AI Foundry - Deployment Architecture

---

## Overview

This document describes how Bud AI Foundry is deployed across different environments, including infrastructure topology, environment configurations, and deployment patterns.

---

## Deployment Models

Bud AI Foundry supports three deployment models:

| Model | Control Plane | Workload Clusters | Best For |
|-------|--------------|-------------------|----------|
| **SaaS** | Bud-managed | Bud-managed or customer | Zero-ops teams |
| **Self-Hosted** | Customer infrastructure | Customer infrastructure | Data sovereignty, air-gapped |
| **Hybrid** | Bud-managed | Customer infrastructure | Compliance + flexibility |

---

## Environment Topology

### Standard Environment Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Environment Topology                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Development Environment                           │   │
│  │                    (dev.bud.studio)                                  │   │
│  │                                                                      │   │
│  │  Purpose: Active development, nightly builds                        │   │
│  │  Images: budstudio/*:nightly                                        │   │
│  │  Features: Dev mode enabled, debug logging, hot reload              │   │
│  │  Auto-deploy: Keel polling every 1 minute                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                     │                                       │
│                                     ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Staging Environment                               │   │
│  │                    (stage.bud.studio)                                │   │
│  │                                                                      │   │
│  │  Purpose: Pre-production validation, QA testing                     │   │
│  │  Images: budstudio/*:staging                                        │   │
│  │  Features: Production-like config, synthetic load testing           │   │
│  │  Promotion: Manual approval from dev                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                     │                                       │
│                                     ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Production Environment                            │   │
│  │                    (app.bud.studio)                                  │   │
│  │                                                                      │   │
│  │  Purpose: Live customer traffic                                     │   │
│  │  Images: budstudio/*:v{semver}                                      │   │
│  │  Features: HA configuration, monitoring, alerting                   │   │
│  │  Promotion: Manual approval from staging, rollback ready            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Environment Configuration Matrix

| Aspect | Development | Staging | Production |
|--------|-------------|---------|------------|
| **Domain** | dev.bud.studio | stage.bud.studio | app.bud.studio |
| **Image Tag** | nightly | staging | v{semver} |
| **Replicas** | 1 | 2 | 3+ |
| **Dev Mode** | Enabled | Disabled | Disabled |
| **Log Level** | DEBUG | INFO | INFO |
| **TLS** | Internal (self-signed) | Let's Encrypt | Let's Encrypt |
| **Auto-Deploy** | Yes (Keel) | No | No |
| **DB Backups** | Daily | Daily | Continuous |
| **Monitoring** | Basic | Full | Full + Alerting |

---

## Kubernetes Cluster Architecture

### Control Plane Cluster

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Control Plane Cluster                                    │
│                     (Single cluster hosting all Bud services)                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Namespaces                                   │   │
│  │                                                                      │   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐           │   │
│  │  │   bud-system  │  │  bud-infra    │  │   bud-obs     │           │   │
│  │  │               │  │               │  │               │           │   │
│  │  │ • budapp      │  │ • PostgreSQL  │  │ • Grafana     │           │   │
│  │  │ • budcluster  │  │ • Valkey      │  │ • Loki        │           │   │
│  │  │ • budsim      │  │ • ClickHouse  │  │ • Tempo       │           │   │
│  │  │ • budmodel    │  │ • MinIO       │  │ • Mimir       │           │   │
│  │  │ • budmetrics  │  │ • MongoDB     │  │ • Prometheus  │           │   │
│  │  │ • budpipeline │  │ • Kafka       │  │ • AlertManager│           │   │
│  │  │ • budeval     │  │               │  │               │           │   │
│  │  │ • budnotify   │  │               │  │               │           │   │
│  │  │ • askbud      │  │               │  │               │           │   │
│  │  │ • budgateway  │  │               │  │               │           │   │
│  │  └───────────────┘  └───────────────┘  └───────────────┘           │   │
│  │                                                                      │   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐           │   │
│  │  │   bud-auth    │  │    dapr       │  │   bud-web     │           │   │
│  │  │               │  │               │  │               │           │   │
│  │  │ • Keycloak    │  │ • Dapr        │  │ • budadmin    │           │   │
│  │  │               │  │   operator    │  │ • budplaygrnd │           │   │
│  │  │               │  │ • Components  │  │ • budcustomer │           │   │
│  │  └───────────────┘  └───────────────┘  └───────────────┘           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Node Pools                                   │   │
│  │                                                                      │   │
│  │  ┌───────────────────────────────────────────────────────────────┐ │   │
│  │  │  System Pool (Primary)                                         │ │   │
│  │  │  • SKU: Standard_D32als_v6 (Azure) / m6i.8xlarge (AWS)        │ │   │
│  │  │  • Disk: 512GB OS + 4TB Data                                  │ │   │
│  │  │  • Count: 1-3 nodes                                           │ │   │
│  │  │  • Runs: All Bud services, databases                          │ │   │
│  │  └───────────────────────────────────────────────────────────────┘ │   │
│  │                                                                      │   │
│  │  ┌───────────────────────────────────────────────────────────────┐ │   │
│  │  │  Ingress Pool                                                  │ │   │
│  │  │  • Disk: 256GB                                                │ │   │
│  │  │  • Count: 2+ nodes (HA)                                       │ │   │
│  │  │  • Runs: Ingress controllers, load balancers                  │ │   │
│  │  └───────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Workload Clusters (Managed by Bud)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Workload Cluster Architecture                         │
│                        (Customer's AI/ML compute)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Components Deployed                          │   │
│  │                                                                      │   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐           │   │
│  │  │ Model Runtime │  │    NFD        │  │   HAMI        │           │   │
│  │  │               │  │ (Node Feature │  │ (GPU Time-    │           │   │
│  │  │ • vLLM        │  │  Discovery)   │  │  Slicing)     │           │   │
│  │  │ • SGLang      │  │               │  │               │           │   │
│  │  │ • TensorRT    │  │ Auto-detect:  │  │ Only if NVIDIA│           │   │
│  │  │               │  │ • GPU type    │  │ GPUs detected │           │   │
│  │  │               │  │ • CPU features│  │               │           │   │
│  │  │               │  │ • Memory      │  │               │           │   │
│  │  └───────────────┘  └───────────────┘  └───────────────┘           │   │
│  │                                                                      │   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐           │   │
│  │  │ GPU Operator  │  │  Prometheus   │  │   Ingress     │           │   │
│  │  │               │  │    Stack      │  │               │           │   │
│  │  │ • Drivers     │  │               │  │ • NGINX       │           │   │
│  │  │ • Toolkit     │  │ • Node export │  │ • Traefik     │           │   │
│  │  │ • Device plugin│ │ • Metrics     │  │ • TLS term    │           │   │
│  │  └───────────────┘  └───────────────┘  └───────────────┘           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Node Types (Example)                             │   │
│  │                                                                      │   │
│  │  GPU Nodes:                                                         │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ • p4d.24xlarge (AWS) - 8x A100 40GB                         │   │   │
│  │  │ • Standard_NC24ads_A100_v4 (Azure) - 1x A100 80GB           │   │   │
│  │  │ • Standard_ND96amsr_A100_v4 (Azure) - 8x A100 80GB          │   │   │
│  │  │ • g5.48xlarge (AWS) - 8x A10G 24GB                          │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  CPU Nodes:                                                         │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ • c6i.8xlarge (AWS) - 32 vCPU, 64GB RAM                     │   │   │
│  │  │ • Standard_D32as_v5 (Azure) - 32 vCPU, 128GB RAM            │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Helm Chart Structure

### Chart Dependencies

```
infra/helm/bud/
├── Chart.yaml                 # Main chart definition
├── values.yaml                # Default values
├── values.dev.yaml            # Development overrides
├── values.stage.yaml          # Staging overrides
├── values.pde.yaml            # Production overrides
├── templates/
│   ├── ingress.yaml           # Ingress resources
│   ├── budgateway.yaml        # API gateway deployment
│   ├── microservices/
│   │   ├── common.yaml        # Shared ConfigMaps, PVCs, Secrets
│   │   ├── budapp.yaml
│   │   ├── budcluster.yaml
│   │   ├── budsim.yaml
│   │   ├── budmodel.yaml
│   │   ├── budmetrics.yaml
│   │   ├── budpipeline.yaml
│   │   ├── budeval.yaml
│   │   ├── budnotify.yaml
│   │   ├── askbud.yaml
│   │   ├── budadmin.yaml
│   │   ├── budplayground.yaml
│   │   └── budcustomer.yaml
│   ├── dapr/
│   │   ├── configuration.yaml # Dapr config
│   │   ├── state.yaml         # State store component
│   │   ├── pubsub.yaml        # Pub/sub component
│   │   ├── secretstore.yaml   # Secret store component
│   │   ├── cron.yaml          # Cron bindings
│   │   └── crypto.yaml        # Crypto component
│   └── extra/
│       ├── postgres.yaml      # PostgreSQL overrides
│       ├── clickhouse.yaml    # ClickHouse overrides
│       └── otel-collector.yaml
└── charts/
    ├── novu/                  # Notification service
    └── onyx/                  # Document search
```

### Dependency Versions

| Dependency | Version | Source |
|------------|---------|--------|
| PostgreSQL | 16.7.18 | Bitnami |
| Valkey | 3.0.20 | Bitnami |
| ClickHouse | 9.3.9 | Bitnami |
| MinIO | 17.0.15 | Bitnami |
| Keycloak | 24.7.7 | Bitnami |
| Kafka | 32.3.5 | Bitnami |
| MongoDB | 16.5.31 | Bitnami |
| Prometheus | 25.27.0 | prometheus-community |
| Novu | 0.1.6 | Local chart |
| Onyx | 0.4.4 | Local chart |

---

## Infrastructure as Code

### Terraform/OpenTofu Modules

```
infra/tofu/
├── azure/                     # Azure infrastructure module
│   ├── main.tf               # Resource group, VNet, NSG
│   ├── primary.tf            # Primary node VM
│   ├── worker.tf             # Worker node VMs
│   ├── ingress.tf            # Ingress node VMs
│   ├── nodes.tf              # Node configuration
│   ├── vars.tf               # Input variables
│   ├── output.tf             # Output values
│   └── provider.tf           # Azure provider config
│
├── budk8s/                    # Kubernetes cluster module
│   ├── main.tf               # Cluster setup with NixOS
│   ├── dns.tf                # DNS configuration
│   ├── vars.tf               # Input variables
│   └── output.tf             # Kubeconfig output
│
└── ephemeral/                 # Ephemeral test environments
    ├── main.tf               # Short-lived test clusters
    └── vars.tf
```

### Azure Network Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Azure Network Topology                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Resource Group: budk8s                                                     │
│  Region: Configurable (default: eastus)                                     │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Virtual Network                                   │   │
│  │                    10.177.0.0/16 (IPv4)                             │   │
│  │                    fd12:babe:cafe::/48 (IPv6)                       │   │
│  │                                                                      │   │
│  │  ┌───────────────────────────────────────────────────────────────┐ │   │
│  │  │  Subnet: budk8s-common                                         │ │   │
│  │  │  10.177.2.0/24 (IPv4)                                         │ │   │
│  │  │  fd12:babe:cafe:b00b::/64 (IPv6)                              │ │   │
│  │  │                                                                │ │   │
│  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐          │ │   │
│  │  │  │ Primary │  │ Ingress │  │ Ingress │  │ Worker  │          │ │   │
│  │  │  │  Node   │  │ Node 1  │  │ Node 2  │  │  Nodes  │          │ │   │
│  │  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘          │ │   │
│  │  └───────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Network Security Group                            │   │
│  │                                                                      │   │
│  │  Inbound Rules:                                                     │   │
│  │  ┌────────────────────────────────────────────────────────────┐    │   │
│  │  │ Priority │ Port      │ Protocol │ Source      │ Purpose    │    │   │
│  │  │──────────┼───────────┼──────────┼─────────────┼────────────│    │   │
│  │  │ 100      │ 22        │ TCP      │ *           │ SSH        │    │   │
│  │  │ 200      │ 51820     │ UDP      │ *           │ WireGuard  │    │   │
│  │  │ 300      │ 60000-61k │ UDP      │ *           │ Mosh       │    │   │
│  │  │ 400      │ 80        │ TCP      │ *           │ HTTP       │    │   │
│  │  │ 500      │ 443       │ TCP      │ *           │ HTTPS      │    │   │
│  │  │ 600      │ *         │ *        │ 10.177.0.0/16│ Internal  │    │   │
│  │  │ 700      │ *         │ *        │ fd12::/48   │ Internal   │    │   │
│  │  └────────────────────────────────────────────────────────────┘    │   │
│  │                                                                      │   │
│  │  Outbound: Allow all                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Deployment Pipelines

### CI/CD Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CI/CD Pipeline                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐  │
│  │  Push   │───►│  Build  │───►│  Test   │───►│ Publish │───►│ Deploy  │  │
│  │ to Git  │    │  Image  │    │  Suite  │    │ to Reg  │    │ to K8s  │  │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘  │
│                                                                              │
│  Stages:                                                                    │
│                                                                              │
│  1. Build                                                                   │
│     ├─ Python services: Docker build with pip install                      │
│     ├─ Rust gateway: cargo build --release                                 │
│     └─ Frontend: npm build with NEXT_PUBLIC_* args                         │
│                                                                              │
│  2. Test                                                                    │
│     ├─ Unit tests: pytest / cargo test / jest                              │
│     ├─ Lint: ruff / clippy / eslint                                        │
│     ├─ Type check: mypy                                                    │
│     └─ Security scan: trivy, modelscan                                     │
│                                                                              │
│  3. Publish                                                                 │
│     ├─ Push to Harbor registry                                             │
│     ├─ Tag: nightly (dev) / staging / v{semver} (prod)                     │
│     └─ Sign images with cosign                                             │
│                                                                              │
│  4. Deploy                                                                  │
│     ├─ Dev: Auto via Keel (poll every 1m)                                  │
│     ├─ Staging: Manual approval                                            │
│     └─ Production: Manual approval + rollback plan                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Image Tagging Strategy

| Environment | Tag Pattern | Example | Trigger |
|-------------|-------------|---------|---------|
| Development | nightly | budstudio/budapp:nightly | Every merge to main |
| Staging | staging | budstudio/budapp:staging | Manual promotion |
| Production | v{major}.{minor}.{patch} | budstudio/budapp:v1.2.3 | Release tag |

---

## Storage Architecture

### Persistent Volumes

| PVC Name | Size | Storage Class | Used By |
|----------|------|---------------|---------|
| bud-models-registry | 1Ti | nfs-csi | Model file storage |
| bud-add-dir-budmo | Configurable | nfs-csi | Model uploads |
| postgresql-data | 100Gi | Default | PostgreSQL |
| clickhouse-data | 500Gi | Default | ClickHouse |
| minio-data | 1Ti | Default | MinIO |

### Storage Tiers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Storage Architecture                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Hot Storage (Fast Access)                         │   │
│  │                                                                      │   │
│  │  • Valkey (Redis): Session cache, Dapr state, rate limiting         │   │
│  │  • Local NVMe: Active model weights on GPU nodes                    │   │
│  │  • ClickHouse: Recent inference metrics (< 30 days)                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Warm Storage (Moderate Access)                    │   │
│  │                                                                      │   │
│  │  • PostgreSQL: Application data, model metadata                     │   │
│  │  • MinIO: Model files, artifacts, datasets                          │   │
│  │  • ClickHouse: Historical metrics (30-90 days)                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Cold Storage (Archive)                            │   │
│  │                                                                      │   │
│  │  • S3/Blob: Database backups, audit logs                            │   │
│  │  • Glacier/Archive: Long-term compliance data                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Secrets Management

### Secret Types and Storage

| Secret Type | Storage Location | Rotation |
|-------------|------------------|----------|
| RSA Keys | Kubernetes Secret (bud-rsa-keys) | Manual |
| Database Credentials | Kubernetes Secret | 90 days |
| API Keys | Kubernetes Secret | On demand |
| Keycloak Admin | Kubernetes Secret | 90 days |
| Dapr API Token | Kubernetes Secret | 90 days |
| TLS Certificates | Kubernetes Secret (auto via cert-manager) | Auto (60 days) |

### Secrets Configuration

```yaml
# From common.yaml - RSA keys for credential encryption
apiVersion: v1
kind: Secret
metadata:
  name: {{ .Release.Name }}-rsa-keys
type: Opaque
data:
  rsa-private-key.pem: {{ .Values.microservices.rsaKeys.privateKey | b64enc }}
  private-key-password: {{ .Values.microservices.rsaKeys.privateKeyPassword | b64enc }}
  rsa-public-key.pem: {{ .Values.microservices.rsaKeys.publicKey | b64enc }}
```

---

## Ingress Architecture

### Traffic Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Ingress Architecture                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                              Internet                                        │
│                                  │                                           │
│                                  ▼                                           │
│                     ┌────────────────────────┐                              │
│                     │   Cloud Load Balancer  │                              │
│                     │   (L4 - TCP/UDP)       │                              │
│                     └───────────┬────────────┘                              │
│                                 │                                            │
│                                 ▼                                            │
│           ┌─────────────────────────────────────────────┐                   │
│           │              Ingress Controller              │                   │
│           │              (NGINX / Traefik)               │                   │
│           │                                              │                   │
│           │  • TLS termination (Let's Encrypt)          │                   │
│           │  • Path-based routing                       │                   │
│           │  • Rate limiting                            │                   │
│           │  • CORS handling                            │                   │
│           └───────────────┬─────────────────────────────┘                   │
│                           │                                                  │
│         ┌─────────────────┼─────────────────┐                               │
│         ▼                 ▼                 ▼                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                         │
│  │  /api/*     │  │  /v1/*      │  │  /*         │                         │
│  │  budapp     │  │ budgateway  │  │  budadmin   │                         │
│  │  :9081      │  │  :3000      │  │  :8007      │                         │
│  └─────────────┘  └─────────────┘  └─────────────┘                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Ingress Hosts

| Subdomain | Service | Path | Purpose |
|-----------|---------|------|---------|
| app.{domain} | budadmin | / | Main dashboard |
| api.{domain} | budapp | /api/* | REST API |
| gateway.{domain} | budgateway | /v1/* | Inference API |
| play.{domain} | budplayground | / | Model playground |
| auth.{domain} | keycloak | / | Authentication |
| grafana.{domain} | grafana | / | Monitoring |

---

## High Availability Configuration

### Component Redundancy

| Component | Min Replicas | Strategy | Notes |
|-----------|--------------|----------|-------|
| budgateway | 2 | HPA (CPU 70%) | Critical path for inference |
| budapp | 2 | HPA (CPU 70%) | Core API |
| budadmin | 2 | Fixed | Frontend |
| PostgreSQL | 1 primary + 1 standby | Streaming replication | Automated failover |
| Valkey | 3 | Sentinel | Automatic failover |
| ClickHouse | 2 | Replication | Read replicas |
| Ingress | 2 | Anti-affinity | Spread across nodes |

### Pod Disruption Budgets

```yaml
# Ensure at least 1 replica available during maintenance
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: budapp-pdb
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: budapp
```

---

## Deployment Commands

### Development Deployment

```bash
# Install with dev values
helm install bud infra/helm/bud/ \
  -f infra/helm/bud/values.dev.yaml \
  --namespace bud-system \
  --create-namespace

# Upgrade existing deployment
helm upgrade bud infra/helm/bud/ \
  -f infra/helm/bud/values.dev.yaml \
  --namespace bud-system
```

### Production Deployment

```bash
# Install with production values and secrets
helm install bud infra/helm/bud/ \
  -f infra/helm/bud/values.pde.yaml \
  -f infra/helm/bud/secrets.yaml \
  --namespace bud-system \
  --create-namespace \
  --atomic \
  --timeout 10m

# Rollback if needed
helm rollback bud 1 --namespace bud-system
```

### Infrastructure Provisioning

```bash
# Azure infrastructure
cd infra/tofu/budk8s
tofu init
tofu plan -out=plan.tfplan
tofu apply plan.tfplan

# Get kubeconfig
tofu output -raw kubeconfig > ~/.kube/budk8s.yaml
```

---

## Related Documents

- [High-Level Architecture](./high-level-architecture.md)
- [Network Topology](./network-topology.md)
- [Disaster Recovery](../disaster-recovery/dr-architecture.md)
- [Installation Guide](../infrastructure/installation-guide.md)
