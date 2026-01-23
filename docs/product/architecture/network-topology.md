# Bud AI Foundry - Network Topology

---

## Overview

This document describes the network architecture for Bud AI Foundry deployments, including VPC design, subnet layout, security groups, ingress/egress patterns, and network policies.

---

## Network Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            External Traffic                                  │
│                                                                             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│  │   Users     │     │   API       │     │  External   │                   │
│  │ (Dashboard) │     │   Clients   │     │  AI Providers│                  │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘                   │
│         │                   │                   │                           │
└─────────┼───────────────────┼───────────────────┼───────────────────────────┘
          │ HTTPS (443)       │ HTTPS (443)       │ HTTPS (443)
          ▼                   ▼                   ▲
┌─────────────────────────────────────────────────┼───────────────────────────┐
│                       Load Balancer / Ingress   │                           │
│  ┌───────────────────────────────────────────┐  │                           │
│  │           Ingress Controller               │  │                           │
│  │  • TLS termination                        │  │                           │
│  │  • Path-based routing                     │  │                           │
│  │  • Rate limiting                          │  │                           │
│  └───────────────────────────────────────────┘  │                           │
└─────────────────────────────────────────────────┼───────────────────────────┘
          │                                       │
          ▼                                       │
┌─────────────────────────────────────────────────┼───────────────────────────┐
│                    Control Plane VPC            │                           │
│                    (10.0.0.0/16)                │                           │
│                                                 │                           │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    Public Subnet (10.0.1.0/24)                         │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                   │ │
│  │  │   NAT GW    │  │   Bastion   │  │  Load       │                   │ │
│  │  │             │  │   Host      │  │  Balancer   │                   │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                   │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│  ┌───────────────────────────┴───────────────────────────────────────────┐ │
│  │                    Private Subnet - Apps (10.0.10.0/24)               │ │
│  │                                                                        │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │ │
│  │  │ budadmin │  │ budapp   │  │budgateway│  │ budsim   │  ...        │ │
│  │  │ :8007    │  │ :9081    │  │ :3000    │  │ :9083    │             │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘             │ │
│  │                                                                        │ │
│  │  ┌────────────────────────────────────────────────────────────────┐  │ │
│  │  │                    Dapr Service Mesh (mTLS)                     │  │ │
│  │  │  Pod-to-Pod: Internal only, encrypted via Dapr Sentry          │  │ │
│  │  └────────────────────────────────────────────────────────────────┘  │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                              │                                              │
│  ┌───────────────────────────┴───────────────────────────────────────────┐ │
│  │                    Private Subnet - Data (10.0.20.0/24)               │ │
│  │                                                                        │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │ │
│  │  │PostgreSQL│  │ClickHouse│  │  Valkey  │  │  MinIO   │             │ │
│  │  │ :5432    │  │ :9000    │  │ :6379    │  │ :9000    │             │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘             │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                 │                           │
│                                    Outbound     │ Provider APIs             │
│                                    (NAT GW)     ▼                           │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          │ VPC Peering / PrivateLink
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Workload Cluster VPC (10.1.0.0/16)                        │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    Private Subnet - Workloads (10.1.10.0/24)          │  │
│  │                                                                        │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │  │
│  │  │   vLLM       │  │   SGLang     │  │ TensorRT-LLM │                │  │
│  │  │   Runtime    │  │   Runtime    │  │   Runtime    │                │  │
│  │  │   (GPU)      │  │   (GPU)      │  │   (GPU)      │                │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Subnet Design

### Control Plane VPC

| Subnet | CIDR | Purpose | Resources |
|--------|------|---------|-----------|
| **Public** | 10.0.1.0/24 | Internet-facing | Load balancer, NAT Gateway, Bastion |
| **Private - Apps** | 10.0.10.0/24 | Application workloads | All Bud services |
| **Private - Data** | 10.0.20.0/24 | Database tier | PostgreSQL, ClickHouse, Valkey, MinIO |
| **Private - Management** | 10.0.30.0/24 | Observability | Grafana, Loki, Tempo, Mimir |

### Workload Cluster VPC

| Subnet | CIDR | Purpose | Resources |
|--------|------|---------|-----------|
| **Public** | 10.1.1.0/24 | Internet-facing (if needed) | Load balancer for inference endpoints |
| **Private - Workloads** | 10.1.10.0/24 | GPU workloads | Model runtimes (vLLM, SGLang) |
| **Private - System** | 10.1.20.0/24 | System components | Prometheus, NFD, HAMI |

---

## Port Reference

### External Ports (Ingress)

| Port | Protocol | Service | Description |
|------|----------|---------|-------------|
| 443 | HTTPS | Ingress | All external traffic (TLS terminated) |
| 22 | SSH | Bastion | Administrative access (restricted) |

### Internal Service Ports

| Port | Service | Protocol | Description |
|------|---------|----------|-------------|
| 8007 | budadmin | HTTP | Dashboard UI |
| 9081 | budapp | HTTP | Core API |
| 3000 | budgateway | HTTP | Inference gateway |
| 9082 | budcluster | HTTP | Cluster management |
| 9083 | budsim | HTTP | Optimization service |
| 9084 | budmodel | HTTP | Model registry |
| 9085 | budmetrics | HTTP | Observability |
| 9086 | budpipeline | HTTP | Pipeline orchestration |
| 9087 | budeval | HTTP | Model evaluation |
| 9088 | budnotify | HTTP | Notifications |
| 9089 | ask-bud | HTTP | AI assistant |

### Dapr Sidecar Ports

| Port | Purpose |
|------|---------|
| 3500 | Dapr HTTP API |
| 50001 | Dapr gRPC API |
| 9090 | Dapr metrics |

### Database Ports

| Port | Service | Protocol |
|------|---------|----------|
| 5432 | PostgreSQL | TCP |
| 9000 | ClickHouse HTTP | TCP |
| 8123 | ClickHouse Native | TCP |
| 6379 | Valkey | TCP |
| 9000 | MinIO API | TCP |
| 9001 | MinIO Console | TCP |
| 27017 | MongoDB | TCP |

### Observability Ports

| Port | Service | Purpose |
|------|---------|---------|
| 3000 | Grafana | Dashboards |
| 3100 | Loki | Log ingestion |
| 4317 | OTLP gRPC | OpenTelemetry |
| 4318 | OTLP HTTP | OpenTelemetry |
| 9090 | Prometheus | Metrics |

---

## Security Groups / Network Policies

### Ingress Controller

```yaml
Inbound:
  - 443/tcp from 0.0.0.0/0  # HTTPS traffic
  - 80/tcp from 0.0.0.0/0   # HTTP redirect
Outbound:
  - All to Private Subnets   # Route to services
```

### Application Services

```yaml
Inbound:
  - Service ports from Ingress Controller
  - 3500/tcp from Pod network (Dapr sidecar)
  - 50001/tcp from Pod network (Dapr gRPC)
Outbound:
  - Database ports to Data subnet
  - 3500/tcp to Pod network (Dapr)
  - 443/tcp to NAT Gateway (external APIs)
```

### Database Tier

```yaml
Inbound:
  - Database ports from Apps subnet only
  - No direct external access
Outbound:
  - None (or backup destinations only)
```

### Kubernetes Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: bud-system
spec:
  podSelector: {}
  policyTypes:
  - Ingress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dapr-sidecar
  namespace: bud-system
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector: {}
    ports:
    - protocol: TCP
      port: 3500
    - protocol: TCP
      port: 50001
```

---

## Cross-Cluster Connectivity

### Control Plane to Workload Clusters

| Method | Use Case | Configuration |
|--------|----------|---------------|
| **VPC Peering** | Same region, same cloud | Non-overlapping CIDRs |
| **AWS PrivateLink** | Cross-region AWS | Endpoint services |
| **Azure Private Link** | Cross-region Azure | Private endpoints |
| **VPN** | Cross-cloud or on-prem | Site-to-site or client VPN |
| **Public Internet** | When private not possible | TLS + API authentication |

### Communication Pattern

```
Control Plane                          Workload Cluster
┌─────────────┐                       ┌─────────────┐
│ budcluster  │ ──── Kubeconfig ────► │ K8s API     │
│             │      (encrypted)      │ Server      │
└─────────────┘                       └─────────────┘
                                              │
┌─────────────┐                               ▼
│ budgateway  │ ──── HTTP/gRPC ──────► ┌─────────────┐
│             │      (inference)       │ Model       │
└─────────────┘                        │ Runtime     │
                                       └─────────────┘
                                              │
┌─────────────┐                               │
│ budmetrics  │ ◄──── Prometheus ─────────────┘
│             │       (scrape)
└─────────────┘
```

---

## DNS Configuration

### Internal DNS

| Record | Target | Purpose |
|--------|--------|---------|
| `budapp.bud-system.svc.cluster.local` | Service ClusterIP | Internal service discovery |
| `postgresql.bud-system.svc.cluster.local` | Service ClusterIP | Database access |
| `valkey.bud-system.svc.cluster.local` | Service ClusterIP | Cache access |

### External DNS

| Record | Target | Purpose |
|--------|--------|---------|
| `admin.example.com` | Load Balancer | Dashboard access |
| `api.example.com` | Load Balancer | Management API |
| `inference.example.com` | Load Balancer | Inference gateway |

---

## Egress Requirements

### Required Outbound Access

| Destination | Port | Purpose |
|-------------|------|---------|
| Cloud Provider APIs | 443 | Cluster provisioning |
| Container Registries | 443 | Image pulls |
| HuggingFace | 443 | Model downloads |
| AI Provider APIs | 443 | External inference |
| Keycloak (if external) | 443 | Authentication |
| NTP servers | 123 | Time sync |

### Air-Gapped Deployment

For air-gapped environments:
- Internal container registry mirror required
- Model artifacts pre-staged to internal storage
- No external AI provider access
- All dependencies bundled in deployment

---

## TLS Configuration

### Certificate Management

| Layer | Certificate | Issuer |
|-------|-------------|--------|
| **Ingress** | Wildcard for domain | Let's Encrypt / Internal CA |
| **Service Mesh** | Per-pod certificates | Dapr Sentry (auto-rotated) |
| **Database** | Server certificates | Internal CA |

### TLS Versions

| Connection | Minimum Version | Cipher Suites |
|------------|-----------------|---------------|
| External | TLS 1.2 | ECDHE-RSA-AES256-GCM-SHA384 |
| Internal (Dapr) | TLS 1.3 | Managed by Dapr |
| Database | TLS 1.2 | AES256-GCM-SHA384 |

---

## Related Documents

- [Security Architecture](../security/security-architecture.md) - Security controls
- [Deployment Architecture](./deployment-architecture.md) - Infrastructure topology
- [High-Level Architecture](./high-level-architecture.md) - System overview
