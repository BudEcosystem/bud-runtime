# Helm Chart Documentation

> **Version:** 1.0
> **Last Updated:** 2026-01-23
> **Status:** Reference Documentation
> **Audience:** DevOps engineers, platform engineers

---

## 1. Overview

The Bud AI Foundry Helm chart deploys the complete platform stack including all services, databases, and supporting infrastructure.

**Chart Location:** `infra/helm/bud/`

---

## 2. Chart Structure

```
infra/helm/bud/
├── Chart.yaml              # Chart metadata
├── values.yaml             # Default values
├── values-dev.yaml         # Development overrides
├── values-staging.yaml     # Staging overrides
├── values-prod.yaml        # Production overrides
├── templates/
│   ├── _helpers.tpl        # Template helpers
│   ├── budapp/             # budapp resources
│   ├── budcluster/         # budcluster resources
│   ├── budgateway/         # budgateway resources
│   ├── budsim/             # budsim resources
│   ├── budmetrics/         # budmetrics resources
│   ├── budadmin/           # budadmin resources
│   ├── configmaps/         # Shared configmaps
│   └── secrets/            # Secret templates
└── charts/                 # Dependencies
    ├── postgresql/
    ├── redis/
    ├── keycloak/
    ├── minio/
    └── ...
```

---

## 3. Quick Start

### 3.1 Prerequisites

- Kubernetes 1.26+
- Helm 3.12+
- kubectl configured
- Storage class available
- (Optional) GPU nodes for inference

### 3.2 Installation

```bash
# Add Helm repository (if external)
helm repo add bud https://charts.bud.example.com
helm repo update

# Install with default values
helm install bud bud/bud -n bud-system --create-namespace

# Install with custom values
helm install bud bud/bud -n bud-system \
  --create-namespace \
  -f values-prod.yaml

# Install from local chart
helm install bud ./infra/helm/bud -n bud-system \
  --create-namespace \
  -f custom-values.yaml
```

### 3.3 Upgrade

```bash
# Update dependencies
helm dependency update ./infra/helm/bud

# Upgrade deployment
helm upgrade bud ./infra/helm/bud -n bud-system \
  -f custom-values.yaml

# Upgrade with rollback on failure
helm upgrade bud ./infra/helm/bud -n bud-system \
  -f custom-values.yaml \
  --atomic --timeout 10m
```

### 3.4 Uninstall

```bash
# Uninstall (keeps PVCs)
helm uninstall bud -n bud-system

# Full cleanup including PVCs
helm uninstall bud -n bud-system
kubectl delete pvc -n bud-system --all
kubectl delete namespace bud-system
```

---

## 4. Values Reference

### 4.1 Global Settings

```yaml
global:
  # Image registry (for air-gapped)
  imageRegistry: ""

  # Image pull secrets
  imagePullSecrets: []

  # Storage class
  storageClass: ""

  # Environment name
  environment: production

  # Domain for ingress
  domain: bud.example.com

  # TLS settings
  tls:
    enabled: true
    secretName: bud-tls
```

### 4.2 budapp Configuration

```yaml
budapp:
  # Enable/disable
  enabled: true

  # Replica count
  replicaCount: 2

  # Image settings
  image:
    repository: bud/budapp
    tag: latest
    pullPolicy: IfNotPresent

  # Resource limits
  resources:
    limits:
      cpu: "2"
      memory: 4Gi
    requests:
      cpu: "500m"
      memory: 1Gi

  # Service settings
  service:
    type: ClusterIP
    port: 9081

  # Ingress settings
  ingress:
    enabled: true
    className: nginx
    annotations:
      nginx.ingress.kubernetes.io/proxy-body-size: "10m"
    hosts:
      - host: api.bud.example.com
        paths:
          - path: /
            pathType: Prefix

  # Environment variables
  env:
    DATABASE_URL: ""  # Set via secret
    KEYCLOAK_URL: "http://keycloak:8080"
    LOG_LEVEL: "INFO"

  # Dapr settings
  dapr:
    enabled: true
    appId: budapp
    appPort: 9081

  # Health checks
  livenessProbe:
    httpGet:
      path: /health
      port: 9081
    initialDelaySeconds: 30
    periodSeconds: 10

  readinessProbe:
    httpGet:
      path: /health/ready
      port: 9081
    initialDelaySeconds: 10
    periodSeconds: 5
```

### 4.3 budcluster Configuration

```yaml
budcluster:
  enabled: true
  replicaCount: 1

  image:
    repository: bud/budcluster
    tag: latest

  resources:
    limits:
      cpu: "2"
      memory: 4Gi
    requests:
      cpu: "500m"
      memory: 1Gi

  # Crypto keys for credential encryption
  cryptoKeys:
    # Use existing secret
    existingSecret: ""
    # Or generate new keys
    generate: true

  env:
    NFD_DETECTION_TIMEOUT: "30"
```

### 4.4 budgateway Configuration

```yaml
budgateway:
  enabled: true
  replicaCount: 2

  image:
    repository: bud/budgateway
    tag: latest

  resources:
    limits:
      cpu: "4"
      memory: 8Gi
    requests:
      cpu: "1"
      memory: 2Gi

  # TOML configuration
  config:
    # Provider configurations
    providers:
      openai:
        enabled: true
        apiKey: ""  # From secret
      anthropic:
        enabled: true
        apiKey: ""  # From secret
```

### 4.5 budsim Configuration

```yaml
budsim:
  enabled: true
  replicaCount: 1

  image:
    repository: bud/budsim
    tag: latest

  resources:
    limits:
      cpu: "4"
      memory: 8Gi
    requests:
      cpu: "1"
      memory: 2Gi

  # Simulation settings
  config:
    defaultMethod: "REGRESSOR"
    maxIterations: 100
```

### 4.6 Database Configuration

```yaml
postgresql:
  enabled: true
  auth:
    username: bud
    database: bud
    existingSecret: postgresql-secret

  primary:
    persistence:
      enabled: true
      size: 50Gi
      storageClass: ""

    resources:
      limits:
        cpu: "4"
        memory: 8Gi
      requests:
        cpu: "1"
        memory: 2Gi

  # High availability
  replication:
    enabled: true
    readReplicas: 1

clickhouse:
  enabled: true
  shards: 1
  replicas: 1
  persistence:
    size: 100Gi

redis:
  enabled: true
  auth:
    enabled: true
    existingSecret: redis-secret
  master:
    persistence:
      size: 10Gi
  replica:
    replicaCount: 1
```

### 4.7 Keycloak Configuration

```yaml
keycloak:
  enabled: true
  auth:
    adminUser: admin
    existingSecret: keycloak-secret

  postgresql:
    enabled: false  # Use external PostgreSQL
    existingDatabase: keycloak
    existingHost: postgresql

  ingress:
    enabled: true
    hostname: auth.bud.example.com
```

### 4.8 MinIO Configuration

```yaml
minio:
  enabled: true
  mode: distributed
  replicas: 4

  persistence:
    size: 100Gi

  resources:
    limits:
      cpu: "2"
      memory: 4Gi

  buckets:
    - name: bud-models
      policy: none
    - name: bud-backups
      policy: none
```

### 4.9 Monitoring Stack

```yaml
monitoring:
  enabled: true

  grafana:
    enabled: true
    adminPassword: ""  # From secret
    ingress:
      enabled: true
      hosts:
        - grafana.bud.example.com

  loki:
    enabled: true
    persistence:
      size: 50Gi

  tempo:
    enabled: true
    persistence:
      size: 50Gi

  mimir:
    enabled: true
    persistence:
      size: 100Gi
```

---

## 5. Environment-Specific Values

### 5.1 Development

```yaml
# values-dev.yaml
global:
  environment: development
  domain: dev.bud.local

budapp:
  replicaCount: 1
  resources:
    limits:
      cpu: "1"
      memory: 2Gi

postgresql:
  primary:
    persistence:
      size: 10Gi
  replication:
    enabled: false

monitoring:
  enabled: false
```

### 5.2 Staging

```yaml
# values-staging.yaml
global:
  environment: staging
  domain: staging.bud.example.com

budapp:
  replicaCount: 2

postgresql:
  primary:
    persistence:
      size: 25Gi

monitoring:
  enabled: true
```

### 5.3 Production

```yaml
# values-prod.yaml
global:
  environment: production
  domain: bud.example.com
  tls:
    enabled: true

budapp:
  replicaCount: 3
  resources:
    limits:
      cpu: "4"
      memory: 8Gi

budgateway:
  replicaCount: 3

postgresql:
  primary:
    persistence:
      size: 100Gi
  replication:
    enabled: true
    readReplicas: 2

redis:
  replica:
    replicaCount: 2

monitoring:
  enabled: true
```

---

## 6. Secrets Management

### 6.1 Required Secrets

| Secret | Keys | Used By |
|--------|------|---------|
| `postgresql-secret` | `postgres-password`, `password` | PostgreSQL, services |
| `redis-secret` | `redis-password` | Redis, services |
| `keycloak-secret` | `admin-password` | Keycloak |
| `crypto-keys` | `rsa-private-key`, `aes-key` | budcluster |
| `provider-secrets` | `openai-api-key`, etc. | budgateway |

### 6.2 Creating Secrets

```bash
# PostgreSQL
kubectl create secret generic postgresql-secret \
  --from-literal=postgres-password=<password> \
  --from-literal=password=<password> \
  -n bud-system

# Redis
kubectl create secret generic redis-secret \
  --from-literal=redis-password=<password> \
  -n bud-system

# Crypto keys
kubectl create secret generic crypto-keys \
  --from-file=rsa-private-key=./crypto-keys/rsa-private-key.pem \
  --from-file=aes-key=./crypto-keys/symmetric-key-256 \
  -n bud-system

# Provider API keys
kubectl create secret generic provider-secrets \
  --from-literal=openai-api-key=<key> \
  --from-literal=anthropic-api-key=<key> \
  -n bud-system
```

---

## 7. Common Operations

### 7.1 Scale Services

```bash
# Scale via Helm
helm upgrade bud ./infra/helm/bud -n bud-system \
  --set budapp.replicaCount=5

# Scale directly (temporary)
kubectl scale deployment budapp -n bud-system --replicas=5
```

### 7.2 View Deployed Values

```bash
# Get all values
helm get values bud -n bud-system

# Get specific value
helm get values bud -n bud-system -o json | jq '.budapp.replicaCount'
```

### 7.3 Rollback

```bash
# View history
helm history bud -n bud-system

# Rollback to previous
helm rollback bud -n bud-system

# Rollback to specific revision
helm rollback bud 3 -n bud-system
```

### 7.4 Debug

```bash
# Dry run
helm upgrade bud ./infra/helm/bud -n bud-system \
  --dry-run --debug

# Template output
helm template bud ./infra/helm/bud -n bud-system \
  -f custom-values.yaml > rendered.yaml
```

---

## 8. Troubleshooting

### 8.1 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Pending PVC | No storage class | Set `global.storageClass` |
| Image pull error | Registry access | Configure `imagePullSecrets` |
| Service unavailable | Not ready | Check pod logs |
| TLS error | Missing cert | Create TLS secret |

### 8.2 Validation

```bash
# Lint chart
helm lint ./infra/helm/bud

# Validate templates
helm template bud ./infra/helm/bud --validate

# Test installation
helm test bud -n bud-system
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-23 | Documentation | Initial version |
