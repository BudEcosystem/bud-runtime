# Network Security Guide

---

## 1. Overview

This document describes the network security architecture for Bud AI Foundry, including:
- Network segmentation
- Firewall rules
- Service mesh configuration
- TLS/mTLS requirements
- Network policies

---

---

## 3. Network Segmentation

### 3.1 Kubernetes Namespaces

| Namespace | Purpose | Components |
|-----------|---------|------------|
| `bud-system` | Application services | budapp, budcluster, budsim, etc. |
| `bud-frontend` | Frontend services | budadmin, budplayground |
| `bud-data` | Data stores | PostgreSQL, ClickHouse, Redis |
| `bud-infra` | Infrastructure | Dapr, cert-manager, ingress |
| `bud-monitoring` | Observability | Grafana, Loki, Tempo, Mimir |
| `bud-auth` | Identity | Keycloak |

### 3.2 Network Policies

**Default Deny All (Recommended):**

**Allow Dapr Sidecar Communication:**

**Allow Ingress to budapp:**

**Allow Database Access:**

---

## 4. Firewall Rules

### 4.1 Ingress Rules (External to Cluster)

| Source | Destination | Port | Protocol | Purpose |
|--------|-------------|------|----------|---------|
| 0.0.0.0/0 | Load Balancer | 443 | HTTPS | Web/API access |
| 0.0.0.0/0 | Load Balancer | 80 | HTTP | Redirect to HTTPS |
| Admin IPs | Cluster | 6443 | HTTPS | Kubernetes API |
| Monitoring | Cluster | 9090 | HTTPS | Metrics scraping |

### 4.2 Internal Rules (Within Cluster)

| Source | Destination | Port | Protocol | Purpose |
|--------|-------------|------|----------|---------|
| bud-system | bud-data (PostgreSQL) | 5432 | TCP | Database |
| bud-system | bud-data (ClickHouse) | 8123,9000 | TCP | Analytics |
| bud-system | bud-data (Redis) | 6379 | TCP | State/cache |
| bud-system | bud-auth (Keycloak) | 8080 | HTTP | Auth |
| bud-infra | bud-system | 9081 | HTTP | Ingress |
| Dapr sidecars | Dapr sidecars | 3500,50001 | TCP | Service mesh |

### 4.3 Egress Rules (Cluster to External)

| Source | Destination | Port | Protocol | Purpose |
|--------|-------------|------|----------|---------|
| bud-system | External LLM APIs | 443 | HTTPS | Model inference |
| bud-system | Cloud APIs (AWS/Azure) | 443 | HTTPS | Cloud management |
| bud-system | Container registries | 443 | HTTPS | Image pull |
| bud-monitoring | External alerting | 443 | HTTPS | Alert notifications |

---

---

## 6. TLS Configuration

### 6.1 Certificate Management

**cert-manager Configuration:**

**Certificate Request:**

### 6.3 Database TLS

**PostgreSQL Connection:**

**ClickHouse Connection:**

---

---

## 8. Model Inference Network

### 8.2 External Provider Whitelist

**Recommended: Use explicit egress allowlist in production**

---

## 9. Multi-Cluster Networking

### 9.2 Cluster Communication Security

| Channel | Security |
|---------|----------|
| Management → Cluster | kubeconfig with service account token |
| Cluster → Management | Dapr pub/sub over mTLS |
| Cross-cluster data | Not supported (tenant isolation) |

---

## 10. Security Monitoring

### 10.1 Network Monitoring Points

| Component | Metrics | Alerts |
|-----------|---------|--------|
| Ingress | Request rate, errors, latency | Error rate > 5% |
| Dapr | mTLS failures, policy violations | Any policy violation |
| Database | Connection count, TLS errors | Connection refused |
| Egress | External call volume | Unusual egress patterns |

---

## 11. Hardening Checklist

### 11.1 Implemented

- [x] TLS 1.2+ for external connections (ingress-level)
- [x] Namespace isolation (logical separation)
- [x] Dapr sidecar injection

### 11.2 Partially Implemented

- [ ] mTLS for service-to-service (Dapr CRD exists, verify configuration)
- [ ] Database TLS (connection strings support TLS, verify server configuration)
- [ ] Security headers on ingress (requires ingress annotation configuration)

### 11.3 Not Implemented (Production Hardening Required)

- [ ] Network policies (default deny) - **CRITICAL for production** (SEC-005)
- [ ] Web Application Firewall (WAF)
- [ ] DDoS protection (cloud provider)
- [ ] IP allowlisting for admin access
- [ ] Egress allowlist (explicit destinations)
- [ ] Network segmentation at cloud VPC level

> **Note:** Network policies are essential for production deployments. See TECH_DEBT.md SEC-005 for implementation tracking.

---

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-23 | Documentation | Initial version |
| 1.1 | 2026-01-25 | Documentation | Updated implementation status - NetworkPolicies not deployed, Dapr mTLS needs verification |
