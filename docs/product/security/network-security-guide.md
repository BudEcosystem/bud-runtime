# Network Security Guide

> **Version:** 1.1
> **Last Updated:** 2026-01-25
> **Status:** Reference Architecture (Partial Implementation)
> **Audience:** Network engineers, security engineers, administrators

---

## 1. Overview

This document describes the network security architecture for Bud AI Foundry, including:
- Network segmentation
- Firewall rules
- Service mesh configuration
- TLS/mTLS requirements
- Network policies

> **Implementation Status:** Some network security controls described in this document are reference architecture and not yet implemented. See Section 11 for implementation status.

---

## 2. Network Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              INTERNET                                    │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                          ┌──────────▼──────────┐
                          │    Load Balancer    │
                          │   (TLS Termination) │
                          │    HTTPS (443)      │
                          └──────────┬──────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────┐
│                           DMZ ZONE │                                    │
│                    ┌───────────────▼───────────────┐                    │
│                    │     Ingress Controller        │                    │
│                    │     (NGINX / Traefik)         │                    │
│                    └───────────────┬───────────────┘                    │
└────────────────────────────────────┼────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────┐
│                        APPLICATION ZONE                                 │
│  ┌─────────────────────────────────┼─────────────────────────────────┐  │
│  │                                 │                                 │  │
│  │  ┌───────────┐  ┌───────────┐  │  ┌───────────┐  ┌───────────┐   │  │
│  │  │  budapp   │  │ budadmin  │  │  │budgateway │  │budcluster │   │  │
│  │  │ (+ Dapr)  │  │  (Next.js)│  │  │  (Rust)   │  │ (+ Dapr)  │   │  │
│  │  └─────┬─────┘  └───────────┘  │  └─────┬─────┘  └─────┬─────┘   │  │
│  │        │                       │        │              │         │  │
│  │        └───────────────────────┼────────┴──────────────┘         │  │
│  │                    mTLS (Dapr) │                                 │  │
│  └────────────────────────────────┼─────────────────────────────────┘  │
└────────────────────────────────────┼────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────┐
│                          DATA ZONE │                                    │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                │
│  │  PostgreSQL   │  │   ClickHouse  │  │     Redis     │                │
│  │  (TLS + Auth) │  │  (TLS + Auth) │  │  (TLS + Auth) │                │
│  └───────────────┘  └───────────────┘  └───────────────┘                │
└─────────────────────────────────────────────────────────────────────────┘
```

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

> **Implementation Status:** Network Policies are NOT currently deployed in the Helm charts. The policies below are reference architecture for production hardening. See TECH_DEBT.md SEC-005.

**Default Deny All (Recommended):**

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
  namespace: bud-system
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
```

**Allow Dapr Sidecar Communication:**

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dapr
  namespace: bud-system
spec:
  podSelector:
    matchLabels:
      dapr.io/enabled: "true"
  ingress:
    - from:
        - podSelector:
            matchLabels:
              dapr.io/enabled: "true"
      ports:
        - protocol: TCP
          port: 3500  # Dapr HTTP
        - protocol: TCP
          port: 50001 # Dapr gRPC
  egress:
    - to:
        - podSelector:
            matchLabels:
              dapr.io/enabled: "true"
      ports:
        - protocol: TCP
          port: 3500
        - protocol: TCP
          port: 50001
```

**Allow Ingress to budapp:**

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-ingress-budapp
  namespace: bud-system
spec:
  podSelector:
    matchLabels:
      app: budapp
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: bud-infra
          podSelector:
            matchLabels:
              app: nginx-ingress
      ports:
        - protocol: TCP
          port: 9081
```

**Allow Database Access:**

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-postgres
  namespace: bud-data
spec:
  podSelector:
    matchLabels:
      app: postgresql
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: bud-system
      ports:
        - protocol: TCP
          port: 5432
```

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

## 5. Service Mesh (Dapr)

### 5.1 mTLS Configuration

> **Implementation Status:** The Dapr Configuration CRD exists in the Helm charts but mTLS is not explicitly enabled in all deployments. Verify the actual configuration in your deployment.

```yaml
apiVersion: dapr.io/v1alpha1
kind: Configuration
metadata:
  name: budconfig
  namespace: bud-system
spec:
  mtls:
    enabled: true
    workloadCertTTL: "24h"
    allowedClockSkew: "15m"
```

### 5.2 Access Control Policies

```yaml
apiVersion: dapr.io/v1alpha1
kind: Configuration
metadata:
  name: budconfig
spec:
  accessControl:
    defaultAction: deny
    trustDomain: "bud.local"
    policies:
      - appId: budapp
        defaultAction: allow
        trustDomain: "bud.local"
        namespace: "bud-system"
        operations:
          - name: /invoke/*
            httpVerb: ["*"]
            action: allow

      - appId: budcluster
        defaultAction: deny
        trustDomain: "bud.local"
        namespace: "bud-system"
        operations:
          - name: /invoke/budapp/*
            httpVerb: ["GET", "POST"]
            action: allow
          - name: /publish/*
            httpVerb: ["POST"]
            action: allow
```

### 5.3 Service Invocation Flow

```
┌─────────────┐          ┌─────────────┐          ┌─────────────┐
│  budapp     │          │   Dapr      │          │ budcluster  │
│  Container  │          │   Sidecar   │          │   Sidecar   │
└──────┬──────┘          └──────┬──────┘          └──────┬──────┘
       │                        │                        │
       │ 1. Call localhost:3500 │                        │
       │───────────────────────▶│                        │
       │                        │                        │
       │                        │ 2. mTLS Connection     │
       │                        │───────────────────────▶│
       │                        │                        │
       │                        │                        │ 3. Forward to
       │                        │                        │    localhost:port
       │                        │                        │───────────────▶
       │                        │                        │
       │                        │ 4. Response (mTLS)     │
       │                        │◀───────────────────────│
       │                        │                        │
       │ 5. Response            │                        │
       │◀───────────────────────│                        │
```

---

## 6. TLS Configuration

### 6.1 Certificate Management

**cert-manager Configuration:**

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: ops@example.com
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
      - http01:
          ingress:
            class: nginx
```

**Certificate Request:**

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: bud-tls
  namespace: bud-infra
spec:
  secretName: bud-tls-secret
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - bud.example.com
    - api.bud.example.com
    - admin.bud.example.com
```

### 6.2 Ingress TLS

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: bud-ingress
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
spec:
  tls:
    - hosts:
        - bud.example.com
        - api.bud.example.com
      secretName: bud-tls-secret
  rules:
    - host: api.bud.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: budapp
                port:
                  number: 9081
```

### 6.3 Database TLS

**PostgreSQL Connection:**

```python
DATABASE_URL = (
    "postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    "?ssl=require"
    "&sslrootcert=/etc/ssl/certs/ca.crt"
)
```

**ClickHouse Connection:**

```python
CLICKHOUSE_SETTINGS = {
    "secure": True,
    "verify": True,
    "ca_certs": "/etc/ssl/certs/ca.crt"
}
```

---

## 7. API Gateway Security

### 7.1 Rate Limiting

```yaml
# NGINX Ingress rate limiting
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  annotations:
    nginx.ingress.kubernetes.io/limit-rps: "100"
    nginx.ingress.kubernetes.io/limit-connections: "50"
```

### 7.2 Request Size Limits

```yaml
nginx.ingress.kubernetes.io/proxy-body-size: "10m"
nginx.ingress.kubernetes.io/proxy-buffer-size: "128k"
```

### 7.3 Security Headers

```yaml
nginx.ingress.kubernetes.io/configuration-snippet: |
  add_header X-Frame-Options "DENY" always;
  add_header X-Content-Type-Options "nosniff" always;
  add_header X-XSS-Protection "1; mode=block" always;
  add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
  add_header Content-Security-Policy "default-src 'self'" always;
  add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

---

## 8. Model Inference Network

### 8.1 budgateway Network Path

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────────┐
│   Client    │────▶│ budgateway  │────▶│  Model Provider     │
│             │HTTPS│   (Rust)    │HTTPS│  (OpenAI, etc.)     │
└─────────────┘     └─────────────┘     └─────────────────────┘
                           │
                           │ Internal
                           ▼
                    ┌─────────────┐
                    │  Deployed   │
                    │   vLLM      │
                    │  Endpoint   │
                    └─────────────┘
```

### 8.2 External Provider Whitelist

```yaml
# Egress network policy for model providers
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-model-providers
  namespace: bud-system
spec:
  podSelector:
    matchLabels:
      app: budgateway
  egress:
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
      ports:
        - protocol: TCP
          port: 443
```

**Recommended: Use explicit egress allowlist in production**

---

## 9. Multi-Cluster Networking

### 9.1 Cluster Registration

```
┌───────────────────────────────────────────────────────────────┐
│                    MANAGEMENT CLUSTER                          │
│                        (budcluster)                            │
│  ┌────────────────┐         ┌────────────────┐                │
│  │  API Server    │────────▶│   kubeconfig   │                │
│  │                │         │   (encrypted)  │                │
│  └────────────────┘         └────────────────┘                │
└───────────────────────────────────┬───────────────────────────┘
                                    │ HTTPS
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
            ┌───────────┐   ┌───────────┐   ┌───────────┐
            │ Cluster A │   │ Cluster B │   │ Cluster C │
            │ (AWS EKS) │   │ (Azure)   │   │ (On-Prem) │
            └───────────┘   └───────────┘   └───────────┘
```

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

### 10.2 Network Audit Logging

```yaml
# Enable audit logging for network events
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
  - level: Metadata
    resources:
      - group: "networking.k8s.io"
        resources: ["networkpolicies", "ingresses"]
  - level: Request
    verbs: ["create", "update", "delete"]
    resources:
      - group: ""
        resources: ["services", "endpoints"]
```

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

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-23 | Documentation | Initial version |
| 1.1 | 2026-01-25 | Documentation | Updated implementation status - NetworkPolicies not deployed, Dapr mTLS needs verification |
