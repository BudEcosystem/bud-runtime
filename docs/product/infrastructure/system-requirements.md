# System Requirements

> **Version:** 1.1
> **Last Updated:** 2026-01-25
> **Status:** Reference Documentation
> **Audience:** Architects, platform engineers, procurement

---

## 1. Overview

This document specifies the minimum and recommended hardware, software, and network requirements for deploying Bud AI Foundry. Requirements are aligned with the [bud-runtime Hardware Requirements](https://github.com/BudEcosystem/bud-runtime/blob/docs/hardware-requirements/docs/HARDWARE_REQUIREMENTS.md).

---

## 2. Deployment Tiers

| Tier | Use Case | Max Concurrent Users |
|------|----------|----------------------|
| **AI-In-A-Box (OEM)** | Evaluation, dev/test, small teams | Up to 100 |
| **Enterprise** | Production, enterprise teams | Up to 1,000 |
| **Cloud Service Provider** | Multi-tenant, SaaS | 10,000+ |

### 2.1 Infrastructure Sizing Summary

| Tier | CPU | RAM | Storage | Network |
|------|-----|-----|---------|---------|
| **AI-In-A-Box** | 32 cores | 64 GiB | 200 GiB SSD | - |
| **Enterprise** | 96 cores | 384 GiB | 5 TiB SSD | 10 Gbps |
| **CSP** | 120-200 cores | 0.5-1 TiB | 10-20 TiB SSD | 10-40 Gbps |

---

## 3. Management Cluster Requirements

### 3.1 Kubernetes Cluster

| Component | AI-In-A-Box | Enterprise | CSP |
|-----------|-------------|------------|-----|
| **Kubernetes Version** | 1.29+ | 1.29+ | 1.29+ |
| **OS** | Ubuntu 22.04+, RHEL 8+, OpenShift 4.12+ | Same | Same |

### 3.2 Node Pool Specifications

| Pool | Purpose | Per-Node Spec | Node Count | Total Resources |
|------|---------|---------------|------------|-----------------|
| **Control Plane** | Databases, state | 8 vCPU, 32GB RAM, 500GB SSD | 3-5 | 24-40 vCPU, 96-160GB RAM |
| **Application** | Microservices, APIs | 16 vCPU, 32GB RAM, 200GB SSD | 5-10 | 80-160 vCPU, 160-320GB RAM |
| **Data Plane** | Analytics, storage | 16 vCPU, 64GB RAM, 1TB SSD | 3-5 | 48-80 vCPU, 192-320GB RAM |
| **Gateway** | API gateway, ingress | 8 vCPU, 16GB RAM, 100GB SSD | 2-3 | 16-24 vCPU, 32-48GB RAM |

### 3.3 Minimum Cluster Sizing by Tier

| Component | AI-In-A-Box | Enterprise | CSP |
|-----------|-------------|------------|-----|
| **Total Nodes** | 3-4 | 13-23 | 20+ |
| **Total vCPU** | 32 | 96+ | 168+ |
| **Total Memory** | 64 GB | 384+ GB | 480+ GB |
| **Total Storage** | 200 GB | 5 TB | 10+ TB |

### 3.4 Platform Services Breakdown

| Service | CPU (requests) | Memory (requests) | Replicas (HA) |
|---------|---------------|-------------------|---------------|
| budapp | 500m | 1 GB | 3 |
| budcluster | 500m | 1 GB | 2 |
| budsim | 1000m | 2 GB | 2 |
| budmodel | 250m | 512 MB | 2 |
| budmetrics | 500m | 1 GB | 2 |
| budgateway | 1000m | 2 GB | 3 |
| budnotify | 250m | 512 MB | 2 |
| askbud | 500m | 1 GB | 2 |
| budeval | 500m | 1 GB | 2 |
| buddoc | 250m | 512 MB | 1 |
| budprompt | 500m | 1 GB | 2 |
| budpipeline | 500m | 1 GB | 1 |
| mcpgateway | 500m | 1 GB | 2 |
| budadmin | 500m | 1 GB | 2 |
| budcustomer | 250m | 512 MB | 2 |
| budplayground | 250m | 512 MB | 2 |
| **Subtotal** | ~8 cores | ~16 GB | - |

### 3.5 Data Layer Requirements

| Component | Minimum | Recommended | Performance |
|-----------|---------|-------------|-------------|
| **PostgreSQL Databases** | 10 GiB | 100-200 GiB | 3,000-10,000 IOPS, <10ms latency |
| **ClickHouse Analytics** | 30 GiB | 200-500 GiB | 5,000-20,000 IOPS, <5ms latency |
| **Object Storage (MinIO)** | 50 GiB | 500 GiB-1 TiB | 1,000-5,000 IOPS, <20ms latency |
| **Kafka Message Queue** | 20 GiB | 100-200 GiB | 2,000-10,000 IOPS, <10ms latency |
| **Application Data** | 50 GiB | 100-200 GiB | Standard SSD |
| **Backups** | — | 500 GiB-1 TiB | Standard/Archive |

**Total Storage:** Minimum 256 GiB; Recommended 2 TiB

**Storage Types:**
- Premium SSD/NVMe for databases (PostgreSQL, ClickHouse)
- Standard SSD acceptable for application data
- Network Storage (NFS, Azure Files, EFS) supported for object storage

### 3.6 Supporting Services

| Component | CPU | Memory | Storage |
|-----------|-----|--------|---------|
| Keycloak | 1 core | 2 GB | - |
| Dapr | 100m per sidecar | 128 MB | - |
| Prometheus | 500m | 1 GB | 20 GB |
| OTel Collector | 500m | 1 GB | - |
| Grafana | 500m | 1 GB | 10 GB |
| Loki | 1 core | 2 GB | 100 GB |
| Tempo | 500m | 1 GB | 50 GB |
| Mimir | 1 core | 2 GB | 100 GB |

---

## 5. Storage Requirements

### 5.1 Storage Classes

| Type | Use Case | Performance |
|------|----------|-------------|
| SSD (gp3/Premium SSD) | Databases, application | 3000+ IOPS |
| High-IOPS SSD (io2) | PostgreSQL primary | 10000+ IOPS |
| Standard (gp2/Standard) | Backups, archives | 100-3000 IOPS |
| Object Storage (S3) | Models, artifacts | N/A |

### 5.2 Storage Sizing Guide

| Component | Formula | Example (Medium) |
|-----------|---------|------------------|
| PostgreSQL | Users × 50MB + Base 10GB | 500 × 50MB + 10GB = 35GB |
| ClickHouse | Requests/day × 1KB × Retention | 1M × 1KB × 30 = 30GB |
| MinIO (Models) | Models × Avg Size | 20 × 10GB = 200GB |
| MinIO (Backups) | DB Size × 30 days | 35GB × 30 = 1TB |
| Logs (Loki) | Services × 1GB/day × Retention | 12 × 1GB × 7 = 84GB |

---

## 6. Network Requirements

### 6.1 Bandwidth

| Traffic Type | Minimum | Recommended | Notes |
|--------------|---------|-------------|-------|
| Inter-Node | 5 Gbps | 10 Gbps | Between cluster nodes |
| Internet Ingress | 1 Gbps | 5 Gbps | API traffic, model uploads |
| Internet Egress | 1 Gbps | 5 Gbps | Model downloads, webhooks |
| DR Replication | 100 Mbps | 1 Gbps | Cross-region |

### 6.2 Latency

| Path | Maximum |
|------|---------|
| User → Load Balancer | 100ms |
| Load Balancer → Service | 5ms |
| Service → Database | 2ms |
| Management → Compute Cluster | 100ms |
| Cross-Region (DR) | 100ms |

### 6.3 Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 443 | HTTPS | External API/UI |
| 6443 | HTTPS | Kubernetes API |
| 5432 | TCP | PostgreSQL |
| 6379 | TCP | Redis |
| 9000 | TCP | MinIO |
| 8123 | TCP | ClickHouse HTTP |
| 9090 | TCP | Prometheus |
| 3000 | TCP | Grafana |

---

## 7. Software Requirements

### 7.1 Required Software

| Component | Version | Notes |
|-----------|---------|-------|
| Kubernetes | 1.29+ | EKS, AKS, OpenShift 4.12+, or self-managed |
| OS | Ubuntu 22.04+, RHEL 8+ | Linux required |
| Helm | 3.12+ | Chart deployment |
| Container Runtime | containerd 1.6+ | Or Docker 24+ |
| Linux Kernel | 5.4+ | For containers |
| NVIDIA Driver | 535+ | For GPU nodes |
| CUDA | 12.0+ | For GPU inference |

### 7.2 Kubernetes Add-ons

| Add-on | Required | Purpose |
|--------|----------|---------|
| Ingress Controller | Yes | External access |
| cert-manager | Yes | TLS certificates |
| metrics-server | Yes | HPA, resource metrics |
| NVIDIA device plugin | GPU nodes | GPU scheduling |
| CSI driver | Yes | Storage provisioning |
| Dapr | Yes | Service mesh |

### 7.3 Optional Components

| Component | Purpose |
|-----------|---------|
| Velero | Kubernetes backup |
| External Secrets | Secret management |
| Kyverno/OPA | Policy enforcement |
| Istio | Advanced service mesh |

---

## 8. High Availability Configuration

| Component | HA Setup | Failover Time |
|-----------|----------|---------------|
| Kubernetes Masters | 3 nodes (multi-zone) | <30 seconds |
| PostgreSQL | 1 master + 2 replicas | <1 minute |
| ClickHouse | 3-node cluster | <2 minutes |
| Valkey (Redis) | 3-node Sentinel | <10 seconds |
| Microservices | 3+ replicas | Immediate |
| Gateway | 3+ replicas | Immediate |
