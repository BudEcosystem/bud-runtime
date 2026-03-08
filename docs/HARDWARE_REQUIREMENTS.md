# Hardware Requirements for Bud-Stack Platform

## Executive Summary

Bud-Stack is a comprehensive multi-service platform for AI/ML model deployment and cluster management. This document provides infrastructure requirements for Cloud Service Providers (CSPs) and organizations planning to deploy the platform.

### Platform Overview

The platform consists of:
- **14 Microservices** (Application, cluster management, ML optimization, model registry, etc.)
- **Core Infrastructure** (Databases, message queues, object storage, authentication)
- **Observability Stack** (Metrics, logging, distributed tracing)
- **High-Performance Gateway** (Rust-based API routing)

---

## Infrastructure Requirements Summary

### AI-In-A-Box - OEM

| Resource | Requirement |
|----------|-------------|
| **CPU Cores** | 32 cores |
| **Memory (RAM)** | 64 GiB |
| **Storage (SSD)** | 200 GiB |
| **Operating System** | Linux (Ubuntu 22.04+, RHEL 8+, or OpenShift 4.12+) |
| **Kubernetes** | Version 1.29+ |

**Max concurrency**: Upto 100 concurrent users

---

### Enterprise deployment

| Resource | Requirement |
|----------|-------------|
| **CPU Cores** | 96 cores |
| **Memory (RAM)** | 384 GiB |
| **Storage (SSD)** | 5 TiB |
| **Network Bandwidth** | 10 Gbps |
| **Operating System** | Linux (Ubuntu 22.04+, RHEL 8+, or OpenShift 4.12+) |
| **Kubernetes** | Version 1.29+ |

**Max concurreny**: Upto 1000 concurrent users

---

### CSP Deployment

| Resource | Requirement |
|----------|-------------|
| **CPU Cores** | 120-200 cores |
| **Memory (RAM)** | 0.5 - 1 TiB |
| **Storage (SSD)** | 10 - 20 TiB |
| **Network Bandwidth** | 10-40 Gbps |
| **Operating System** | Linux (Ubuntu 22.04+, RHEL 8+, or OpenShift 4.12+) |
| **Kubernetes** | Version 1.29+ |

**Concurrency**: 10000+

---

## Detailed Architecture

### Node Pool Breakdown

Production deployments use specialized node pools for optimal resource allocation:

| Node Pool | Purpose | Node Spec | Count | Total Resources |
|-----------|---------|-----------|-------|-----------------|
| **Control Plane** | Databases, state management | 8 vCPU, 32GB RAM, 500GB SSD | 3-5 | 24-40 vCPU, 96-160GB RAM |
| **Application** | Microservices, APIs | 16 vCPU, 32GB RAM, 200GB SSD | 5-10 | 80-160 vCPU, 160-320GB RAM |
| **Data Plane** | Analytics, storage, messaging | 16 vCPU, 64GB RAM, 1TB SSD | 3-5 | 48-80 vCPU, 192-320GB RAM |
| **Gateway** | API gateway, ingress | 8 vCPU, 16GB RAM, 100GB SSD | 2-3 | 16-24 vCPU, 32-48GB RAM |


---

### Persistent Storage Breakdown

| Component | Size (Min) | Size (Recommended) | Performance |
|-----------|------------|-------------------|-------------|
| **Databases** (PostgreSQL) | 10 GiB | 100-200 GiB | 3,000-10,000 IOPS, <10ms latency |
| **Analytics** (ClickHouse) | 30 GiB | 200-500 GiB | 5,000-20,000 IOPS, <5ms latency |
| **Object Storage** (Models, Datasets) | 50 GiB | 500 GiB-1 TiB | 1,000-5,000 IOPS, <20ms latency |
| **Message Queue** (Kafka) | 20 GiB | 100-200 GiB | 2,000-10,000 IOPS, <10ms latency |
| **Application Data** | 50 GiB | 100-200 GiB | Standard SSD |
| **Backups** | - | 500 GiB-1 TiB | Standard/Archive |

**Total Storage**:
- **Minimum**: 256 GiB
- **Recommended**: 2 TiB

### Storage Type Requirements

- **Premium SSD/NVMe**: Required for databases (PostgreSQL, ClickHouse)
- **Standard SSD**: Acceptable for application data, metrics
- **Network Storage**: Supported for shared volumes (NFS, Azure Files, EFS)

---

## Network Requirements

| Traffic Type | Minimum | Recommended | Notes |
|--------------|---------|-------------|-------|
| **Inter-Node** | 5 Gbps | 10 Gbps | Between cluster nodes |
| **Internet Ingress** | 1 Gbps | 5 Gbps | API traffic, model uploads |
| **Internet Egress** | 1 Gbps | 5 Gbps | Model downloads, webhooks |

---

## High Availability Scenarios

### Standard HA Configuration

| Component | Configuration | Failover Time |
|-----------|--------------|---------------|
| **Kubernetes Masters** | 3 nodes (multi-zone) | <30 seconds |
| **PostgreSQL** | 1 master + 2 replicas | <1 minute |
| **ClickHouse** | 3-node cluster | <2 minutes |
| **Redis** | 3-node Sentinel | <10 seconds |
| **Microservices** | 3+ replicas | Immediate |
| **Gateway** | 3+ replicas | Immediate |


### Key HA Features

- **Auto-Scaling**: HPA enabled for all stateless services (CPU/memory threshold: 75%)
- **Health Checks**: Liveness/readiness probes on all pods (5-second intervals)
- **Anti-Affinity**: Pods distributed across zones to prevent single point of failure
- **PodDisruptionBudget**: Minimum 50% pods available during updates
- **Backup Schedule**: Daily database backups, 30-day retention, WAL archiving



## Required Software

- **Kubernetes**: Version 1.29+
- **Helm**: Version 3.10 or higher
- **Container Runtime**: containerd 1.6+
- **kubectl**: Matching Kubernetes version
- **Operating System**: Ubuntu 22.04+, RHEL 8+, or OpenShift 4.12+
