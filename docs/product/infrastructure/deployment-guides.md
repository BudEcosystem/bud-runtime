# Deployment Guides

> **Audience:** DevOps engineers, platform administrators

---

## 1. Quick Start Guide (Evaluation)

### 1.1 Prerequisites

| Requirement | Minimum |
|-------------|---------|
| Kubernetes | 1.27+ |
| Helm | 3.12+ |
| kubectl | Configured |
| CPU | 16 cores |
| Memory | 64 GB |
| Storage | 200 GB SSD |

### 1.2 Installation Steps

```bash
# 1. Create namespace
kubectl create namespace bud

# 2. Clone the repository (chart is not in public repo)
git clone https://github.com/budecosystem/bud-runtime.git
cd bud-runtime

# 3. Update Helm dependencies
helm dependency update ./infra/helm/bud

# 4. Install with development values
helm install bud ./infra/helm/bud -n bud \
  -f ./infra/helm/bud/values.dev.yaml

# 5. Wait for pods
kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=bud \
  -n bud --timeout=600s

# 6. Get Keycloak admin credentials (default: bud/bud)
echo "Username: bud"
echo "Password: bud"

# 7. Access UI via port-forward
kubectl port-forward svc/bud-budadmin 8007:8007 -n bud
```

**Access:** http://localhost:8007

---

## 2. Production Installation Guide

### 2.1 Prerequisites Checklist

- [ ] Kubernetes cluster (1.27+) with 5+ nodes
- [ ] GPU nodes for inference (optional)
- [ ] Storage class with dynamic provisioning
- [ ] Load balancer or Ingress controller
- [ ] TLS certificates or cert-manager
- [ ] DNS entries configured
- [ ] Dapr installed cluster-wide (see [Dapr Installation](https://docs.dapr.io/operations/hosting/kubernetes/kubernetes-deploy/))

### 2.2 Pre-Installation

**Create Namespace:**
```bash
kubectl create namespace bud
```

**Generate Encryption Keys (for budcluster):**
```bash
mkdir -p crypto-keys
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 \
  -out crypto-keys/rsa-private-key.pem
openssl rand -out crypto-keys/symmetric-key-256 32

kubectl create secret generic crypto-keys \
  --from-file=rsa-private-key=crypto-keys/rsa-private-key.pem \
  --from-file=aes-key=crypto-keys/symmetric-key-256 \
  -n bud
```

### 2.3 Production Values File

```yaml
# values-production.yaml
global:
  ingress:
    hosts:
      root: "bud.example.com"
      # Subdomains auto-derived: admin.bud.example.com, app.bud.example.com, etc.
  nodeSelector:
    environment: production

ingress:
  enabled: true
  https: external  # Enable HTTPS for client-side URLs

# Frontend services
microservices:
  budadmin:
    enabled: true
    autoscaling:
      enabled: true
      minReplicas: 2
      maxReplicas: 5
      targetCPUUtilizationPercentage: 70

  budcustomer:
    enabled: true
    autoscaling:
      enabled: true
      minReplicas: 2
      maxReplicas: 3

  budplayground:
    enabled: true
    autoscaling:
      enabled: true
      minReplicas: 1
      maxReplicas: 3

  # High-performance gateway with custom metrics HPA
  budgateway:
    enabled: true
    autoscaling:
      enabled: true
      minReplicas: 3
      maxReplicas: 20
      targetCPUUtilizationPercentage: 70
      prometheusMetrics:
        enabled: true
        metricName: gateway_processing_seconds_p95
        targetValue: "2m"  # 2ms target
      scaleDownStabilizationSeconds: 300
      scaleUpStabilizationSeconds: 0

  # Core API service
  budapp:
    enabled: true
    autoscaling:
      enabled: true
      minReplicas: 3
      maxReplicas: 10
      targetCPUUtilizationPercentage: 70

  # Cluster management (longer stabilization for workflows)
  budcluster:
    enabled: true
    autoscaling:
      enabled: true
      minReplicas: 2
      maxReplicas: 5
      targetCPUUtilizationPercentage: 80
      scaleDownStabilizationSeconds: 600

  # ML optimization service
  budsim:
    enabled: true
    autoscaling:
      enabled: true
      minReplicas: 2
      maxReplicas: 5
      targetCPUUtilizationPercentage: 75
      scaleDownStabilizationSeconds: 600

  budmodel:
    enabled: true
    autoscaling:
      enabled: true
      minReplicas: 2
      maxReplicas: 4

  budmetrics:
    enabled: true
    autoscaling:
      enabled: true
      minReplicas: 2
      maxReplicas: 5

  budeval:
    enabled: true
    autoscaling:
      enabled: true
      minReplicas: 1
      maxReplicas: 3
      scaleDownStabilizationSeconds: 600

  buddoc:
    enabled: true
    autoscaling:
      enabled: true
      minReplicas: 1
      maxReplicas: 3

  budnotify:
    enabled: true
    autoscaling:
      enabled: true
      minReplicas: 2
      maxReplicas: 5
      scaleUpStabilizationSeconds: 0

  budprompt:
    enabled: true
    autoscaling:
      enabled: true
      minReplicas: 2
      maxReplicas: 8

  budpipeline:
    enabled: true

  askbud:
    enabled: true
    autoscaling:
      enabled: true
      minReplicas: 2
      maxReplicas: 5

  mcpgateway:
    enabled: true
    autoscaling:
      enabled: true
      minReplicas: 2
      maxReplicas: 5

# PostgreSQL with replication
postgresql:
  enabled: true
  architecture: replication
  auth:
    postgresPassword: "<STRONG_PASSWORD>"
    username: bud
    password: "<STRONG_PASSWORD>"
  primary:
    resources:
      requests:
        memory: 2Gi
        cpu: 1000m
      limits:
        memory: 8Gi
        cpu: 4000m
    persistence:
      size: 100Gi
      storageClass: gp3-io2
  readReplicas:
    replicaCount: 2

# Valkey (Redis replacement) with replication
valkey:
  enabled: true
  architecture: replication
  auth:
    password: "<STRONG_PASSWORD>"
  master:
    resources:
      requests:
        memory: 1Gi
        cpu: 500m
      limits:
        memory: 4Gi
        cpu: 2000m
    persistence:
      size: 20Gi

# ClickHouse for time-series metrics
clickhouse:
  enabled: true
  shards: 2
  replicaCount: 2
  auth:
    username: bud
    password: "<STRONG_PASSWORD>"
  resources:
    requests:
      memory: 8Gi
      cpu: 2000m
    limits:
      memory: 32Gi
      cpu: 8000m

# Keycloak for authentication
keycloak:
  enabled: true
  auth:
    adminUser: admin
    adminPassword: "<STRONG_PASSWORD>"
  resources:
    limits:
      memory: 4Gi

# Kafka for event streaming
kafka:
  enabled: true
  controller:
    resources:
      requests:
        memory: 2Gi
      limits:
        memory: 4Gi

# MongoDB for notifications (Novu)
mongodb:
  enabled: true
  auth:
    enabled: true
    usernames:
      - novu_user
    passwords:
      - "<STRONG_PASSWORD>"
    databases:
      - novu_db

# MinIO for object storage
minio:
  enabled: true
  resources:
    requests:
      memory: 1Gi
    limits:
      memory: 4Gi
  provisioning:
    enabled: true
    buckets:
      - name: novu-local
      - name: models-registry
      - name: model-info

# Prometheus for HPA custom metrics
prometheus:
  enabled: true
  server:
    retention: "24h"
    resources:
      requests:
        cpu: 500m
        memory: 2Gi
      limits:
        cpu: 2000m
        memory: 8Gi

prometheus-adapter:
  enabled: true

# OpenTelemetry Collector
otelCollector:
  enabled: true
  replicas: 2
  resources:
    requests:
      memory: 1Gi
      cpu: 500m
    limits:
      memory: 4Gi
      cpu: 2000m
```

### 2.4 Installation

```bash
# Clone repository
git clone https://github.com/budecosystem/bud-tools.git
cd bud-tools

# Update Helm dependencies
helm dependency update ./infra/helm/bud

# Dry run to verify
helm upgrade --install bud ./infra/helm/bud \
  -n bud \
  -f values-production.yaml \
  --dry-run

# Install
helm upgrade --install bud ./infra/helm/bud \
  -n bud \
  -f values-production.yaml \
  --atomic \
  --timeout 15m

# Verify deployment
kubectl get pods -n bud
kubectl get hpa -n bud
```

### 2.5 Post-Installation

```bash
# Get Keycloak admin URL
echo "https://auth.$(kubectl get cm -n bud bud-config -o jsonpath='{.data.root}')"

# Verify services
curl -k https://app.bud.example.com/health
curl -k https://auth.bud.example.com/realms/bud-keycloak/.well-known/openid-configuration

# Access admin dashboard
echo "https://admin.bud.example.com"
```

---

## 3. Configuration Reference

### 3.1 Global Environment Variables

These variables are set under `microservices.global.env` and shared across all services:

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging level | `INFO` |
| `DAPR_BASE_URL` | Dapr sidecar URL | `http://localhost:3500` |
| `REDIS_HOST` | Valkey/Redis host | `<release>-valkey-primary` |
| `REDIS_PORT` | Valkey/Redis port | `6379` |
| `REDIS_PASSWORD` | Valkey/Redis password | From `valkey.auth.password` |
| `MINIO_ENDPOINT` | MinIO/S3 endpoint | Auto-derived from ingress |
| `MINIO_ACCESS_KEY` | MinIO access key | From `minio.auth.rootUser` |
| `MINIO_SECRET_KEY` | MinIO secret key | From `minio.auth.rootPassword` |
| `CLICKHOUSE_USER` | ClickHouse username | From `clickhouse.auth.username` |
| `CLICKHOUSE_PASSWORD` | ClickHouse password | From `clickhouse.auth.password` |
| `MONGO_URL` | MongoDB connection string | Auto-templated |

### 3.2 Service-Specific Configuration

**budapp:**
```yaml
microservices:
  budapp:
    env:
      KEYCLOAK_SERVER_URL: "http://<release>-keycloak/"
      KEYCLOAK_REALM_NAME: "master"
      KEYCLOAK_ADMIN_USERNAME: "bud"
      KEYCLOAK_ADMIN_PASSWORD: "bud"
      DEFAULT_REALM_NAME: "bud-keycloak"
      GRAFANA_SCHEME: "http"
      GRAFANA_URL: "<release>-grafana"
      BUD_DOC_SERVICE_URL: "http://<release>-buddoc:9081"
      BUD_PROMPT_SERVICE_URL: "http://<release>-budprompt:3015/v1/"
```

**budcluster:**
```yaml
microservices:
  budcluster:
    env:
      LOG_LEVEL: "INFO"
      RSA_KEY_NAME: "rsa-private-key.pem"
      VOLUME_TYPE: "local"
      VALIDATE_CERTS: "false"
      # Node info collector images
      NODE_INFO_COLLECTOR_IMAGE_CPU: "budstudio/node-info-collector-cpu:0.1.0"
      NODE_INFO_COLLECTOR_IMAGE_CUDA: "budimages.azurecr.io/budecosystem/node-info-collector-cuda:latest"
      NODE_INFO_COLLECTOR_IMAGE_HPU: "budimages.azurecr.io/budecosystem/node-info-collector-hpu:latest"
      # Metrics collection
      METRICS_COLLECTION_ENABLED: "true"
      METRICS_COLLECTION_TIMEOUT: "30"
      METRICS_BATCH_SIZE: "20000"
      # OpenTelemetry
      OTEL_COLLECTOR_ENDPOINT: "http://<release>-otel-collector:4318"
```

**budgateway:**
```yaml
microservices:
  budgateway:
    env:
      OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: "http://<release>-otel-collector:4317"
    # HPA with Prometheus custom metrics
    autoscaling:
      prometheusMetrics:
        enabled: true
        metricName: "gateway_processing_seconds_p95"
        targetValue: "2m"  # 2ms P95 latency target
```

**budmetrics:**
```yaml
microservices:
  budmetrics:
    env:
      CLICKHOUSE_HOST: "<release>-clickhouse"
      CLICKHOUSE_PORT: "9000"
      CLICKHOUSE_DB_NAME: "budproxy"
      CLICKHOUSE_TTL_CLUSTER_METRICS: "30"  # Days
```

**budsim:**
```yaml
microservices:
  budsim:
    env:
      LOG_LEVEL: "INFO"
      # Optimization defaults configured in service
      # POPULATION_SIZE: "50"
      # GENERATION_COUNT: "10"
```

**budprompt:**
```yaml
microservices:
  budprompt:
    env:
      BUD_GATEWAY_BASE_URL: "http://<release>-budgateway:3000/v1"
      REDIS_HOST: "<release>-valkey-primary"
      REDIS_DB_INDEX: "10"
      OTEL_SDK_DISABLED: "false"
      OTEL_EXPORTER_OTLP_ENDPOINT: "http://<release>-otel-collector:4318"
```

**askbud:**
```yaml
microservices:
  askbud:
    model: "bud-gpt-oss-20b-ada28b58"
    env:
      INFERENCE_API_KEY: "<API_KEY>"
      INFERENCE_URL: "http://<inference-endpoint>/v1/"
```

---

## 4. Multi-Environment Setup

### 4.1 Environment Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                        Development                               │
│  - Single replicas (autoscaling disabled)                        │
│  - Minimal resources                                             │
│  - Standalone databases                                          │
│  - Prometheus HPA metrics disabled                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                          Staging                                 │
│  - Production-like config                                        │
│  - Autoscaling enabled (reduced max)                             │
│  - Full observability stack                                      │
│  - Smaller storage allocations                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Production                               │
│  - Full autoscaling with custom metrics                          │
│  - Database replication enabled                                  │
│  - Large storage, backups                                        │
│  - Multi-zone node affinity                                      │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Environment-Specific Values

**Development (`values.dev.yaml`):**
```yaml
global:
  ingress:
    hosts:
      root: "localhost"

ingress:
  https: disabled

microservices:
  budadmin:
    autoscaling:
      enabled: false
  budgateway:
    autoscaling:
      enabled: false
  budapp:
    autoscaling:
      enabled: false
  budcluster:
    autoscaling:
      enabled: false
  budsim:
    autoscaling:
      enabled: false

postgresql:
  architecture: standalone
  primary:
    resources:
      requests:
        memory: 256Mi
      limits:
        memory: 512Mi

valkey:
  architecture: standalone
  primary:
    resources:
      requests:
        memory: 512Mi
      limits:
        memory: 1Gi

clickhouse:
  replicaCount: 1
  shards: 1
  resources:
    requests:
      memory: 4Gi
    limits:
      memory: 8Gi

prometheus:
  enabled: true
  server:
    retention: "2h"

prometheus-adapter:
  enabled: true

otelCollector:
  enabled: true
  replicas: 1
```

**Staging (`values-staging.yaml`):**
```yaml
global:
  ingress:
    hosts:
      root: "staging.bud.example.com"

ingress:
  https: external

microservices:
  budadmin:
    autoscaling:
      enabled: true
      maxReplicas: 2
  budgateway:
    autoscaling:
      enabled: true
      maxReplicas: 5
      prometheusMetrics:
        enabled: true
  budapp:
    autoscaling:
      enabled: true
      maxReplicas: 3

postgresql:
  architecture: standalone
  primary:
    persistence:
      size: 50Gi

valkey:
  architecture: standalone

clickhouse:
  replicaCount: 1
  shards: 1

prometheus:
  enabled: true
  server:
    retention: "12h"

prometheus-adapter:
  enabled: true

otelCollector:
  enabled: true
  replicas: 1
```

---

## 5. Upgrade & Migration Guide

### 5.1 Pre-Upgrade Checklist

- [ ] Review release notes for breaking changes
- [ ] Backup PostgreSQL and ClickHouse databases
- [ ] Test upgrade in staging environment
- [ ] Schedule maintenance window
- [ ] Notify stakeholders
- [ ] Verify Dapr is up to date (if cluster-wide)

### 5.2 Upgrade Procedure

```bash
# 1. Check current version
helm list -n bud

# 2. Pull latest chart
cd bud-runtime && git pull
helm dependency update ./infra/helm/bud

# 3. Review changes (requires helm-diff plugin)
helm diff upgrade bud ./infra/helm/bud -n bud -f values-production.yaml

# 4. Backup databases
kubectl exec -n bud deployment/bud-postgresql -- \
  pg_dumpall -U postgres > backup-$(date +%Y%m%d).sql

# 5. Perform upgrade
helm upgrade bud ./infra/helm/bud -n bud \
  -f values-production.yaml \
  --atomic \
  --timeout 15m

# 6. Verify
kubectl get pods -n bud
kubectl get hpa -n bud
curl https://app.bud.example.com/health
```

### 5.3 Database Migrations

```bash
# Migrations run automatically on pod startup via init containers
# To run manually for a specific service:

# budapp
kubectl exec -n bud deployment/bud-budapp -- \
  alembic -c ./budapp/alembic.ini upgrade head

# budcluster
kubectl exec -n bud deployment/bud-budcluster -- \
  alembic upgrade head

# budmodel
kubectl exec -n bud deployment/bud-budmodel -- \
  alembic upgrade head

# ClickHouse migrations (budmetrics)
kubectl exec -n bud deployment/bud-budmetrics -- \
  python scripts/migrate_clickhouse.py
```

### 5.4 Rollback Procedure

```bash
# View history
helm history bud -n bud

# Rollback to previous
helm rollback bud -n bud

# Rollback to specific revision
helm rollback bud 5 -n bud

# Verify rollback
kubectl get pods -n bud
kubectl rollout status deployment -n bud
```

### 5.5 Dapr Component Updates

```bash
# If Dapr components change, restart affected services
kubectl rollout restart deployment -n bud -l dapr.io/enabled=true
```

---

## 6. Scaling Procedures

### 6.1 Horizontal Pod Autoscaling (HPA)

The chart provides built-in HPA configuration for all services under `microservices.<service>.autoscaling`.

**Enable/Configure HPA via Helm:**
```bash
# Enable autoscaling for budapp with custom limits
helm upgrade bud ./infra/helm/bud -n bud \
  --set microservices.budapp.autoscaling.enabled=true \
  --set microservices.budapp.autoscaling.minReplicas=3 \
  --set microservices.budapp.autoscaling.maxReplicas=10 \
  --set microservices.budapp.autoscaling.targetCPUUtilizationPercentage=70 \
  --reuse-values
```

**Check HPA status:**
```bash
kubectl get hpa -n bud
kubectl describe hpa bud-budapp -n bud
```

**Manual scaling (temporary, overridden by HPA):**
```bash
kubectl scale deployment bud-budapp -n bud --replicas=5
```

### 6.2 Custom Metrics Scaling (budgateway)

The budgateway supports Prometheus-based custom metrics HPA using `gateway_processing_seconds_p95`:

```yaml
microservices:
  budgateway:
    autoscaling:
      enabled: true
      minReplicas: 3
      maxReplicas: 20
      prometheusMetrics:
        enabled: true
        metricName: gateway_processing_seconds_p95
        targetValue: "2m"  # 2ms P95 target
      scaleDownStabilizationSeconds: 300
      scaleUpStabilizationSeconds: 0  # Fast scale-up
```

**Verify custom metrics:**
```bash
# Check prometheus-adapter is exposing metrics
kubectl get --raw "/apis/custom.metrics.k8s.io/v1beta1/namespaces/bud/pods/*/gateway_processing_seconds_p95"
```

### 6.3 Stabilization Windows

Services have different stabilization windows based on workload patterns:

| Service | Scale Down | Scale Up | Reason |
|---------|------------|----------|--------|
| budgateway | 300s | 0s | Fast response to traffic spikes |
| budnotify | 300s | 0s | Fast scale-up for notifications |
| budcluster | 600s | 60s | Long-running workflows |
| budsim | 600s | 60s | ML optimization workflows |
| budeval | 600s | 60s | Evaluation workflows |
| Others | 300s | 30s | Standard workloads |

### 6.4 Database Scaling

**PostgreSQL Replication:**
```bash
helm upgrade bud ./infra/helm/bud -n bud \
  --set postgresql.architecture=replication \
  --set postgresql.readReplicas.replicaCount=2 \
  --reuse-values
```

**Valkey Replication:**
```bash
helm upgrade bud ./infra/helm/bud -n bud \
  --set valkey.architecture=replication \
  --reuse-values
```

**ClickHouse Sharding:**
```bash
helm upgrade bud ./infra/helm/bud -n bud \
  --set clickhouse.shards=2 \
  --set clickhouse.replicaCount=2 \
  --reuse-values
```

### 6.5 Node Scheduling

Use global or per-service node selectors and affinity rules:

```yaml
# Global (all services)
global:
  nodeSelector:
    environment: production
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: kubernetes.io/arch
            operator: In
            values:
            - amd64

# Per-service override
microservices:
  budgateway:
    nodeSelector:
      workload: high-performance
```

---

## 7. Terraform/OpenTofu Reference

### 7.1 Module Structure

```
infra/tofu/
├── modules/
│   ├── eks/           # AWS EKS cluster
│   ├── aks/           # Azure AKS cluster
│   ├── networking/    # VPC, subnets
│   ├── storage/       # S3, EBS
│   └── iam/           # IAM roles
├── environments/
│   ├── dev/
│   ├── staging/
│   └── production/
└── main.tf
```

### 7.2 AWS EKS Module

```hcl
module "eks" {
  source = "./modules/eks"

  cluster_name    = "bud-production"
  cluster_version = "1.28"

  vpc_id     = module.networking.vpc_id
  subnet_ids = module.networking.private_subnet_ids

  node_groups = {
    platform = {
      instance_types = ["m5.2xlarge"]
      min_size       = 3
      max_size       = 10
      desired_size   = 5
    }
    gpu = {
      instance_types = ["p4d.24xlarge"]
      min_size       = 0
      max_size       = 4
      desired_size   = 2
      ami_type       = "AL2_x86_64_GPU"
    }
  }
}
```

### 7.3 Key Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `cluster_name` | K8s cluster name | `bud-production` |
| `cluster_version` | K8s version | `1.28` |
| `node_instance_types` | EC2 instance types | `["m5.2xlarge"]` |
| `gpu_instance_types` | GPU instance types | `["p4d.24xlarge"]` |
| `vpc_cidr` | VPC CIDR block | `10.0.0.0/16` |

---

## 8. Service Reference

### 8.1 All Available Services

| Service | Type | Dapr | Description |
|---------|------|------|-------------|
| `budadmin` | Frontend | No | Admin dashboard (Next.js) |
| `budcustomer` | Frontend | No | Customer portal |
| `budplayground` | Frontend | No | Model testing interface |
| `budgateway` | Backend | No | High-performance API gateway (Rust) |
| `budapp` | Backend | Yes | Core API, auth, users, projects |
| `budcluster` | Backend | Yes | Cluster lifecycle management |
| `budsim` | Backend | Yes | Performance simulation |
| `budmodel` | Backend | Yes | Model registry |
| `budmetrics` | Backend | Yes | Observability, ClickHouse analytics |
| `budeval` | Backend | Yes | Model evaluation |
| `buddoc` | Backend | Yes | Document processing |
| `budnotify` | Backend | Yes | Notifications (Novu) |
| `budprompt` | Backend | Yes | Prompt management |
| `budpipeline` | Backend | Yes | Workflow orchestration |
| `askbud` | Backend | Yes | AI assistant |
| `mcpgateway` | Backend | No | MCP protocol gateway |
| `budsentinel` | Backend | No | Closed-source monitoring (disabled by default) |

### 8.2 Dependencies

| Dependency | Purpose | Default |
|------------|---------|---------|
| `postgresql` | Primary database | Enabled |
| `valkey` | Cache, pub/sub, Dapr state | Enabled |
| `clickhouse` | Time-series metrics | Enabled |
| `keycloak` | Authentication | Enabled |
| `kafka` | Event streaming | Enabled |
| `mongodb` | Novu notifications | Enabled |
| `minio` | Object storage | Enabled |
| `novu` | Notification infrastructure | Enabled |
| `prometheus` | HPA custom metrics | Enabled |
| `prometheus-adapter` | K8s metrics API | Enabled |
| `otelCollector` | OpenTelemetry | Enabled |
| `onyx` | Knowledge assistant | Disabled |
| `dapr` | Service mesh | Disabled (install cluster-wide) |

---


| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-23 | Documentation | Initial version |
| 1.1 | 2026-01-25 | Documentation | Aligned with actual Helm chart structure; updated services, dependencies, autoscaling, Valkey references |
