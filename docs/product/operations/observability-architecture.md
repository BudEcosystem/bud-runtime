# Observability Architecture

> **Version:** 1.0
> **Last Updated:** 2026-01-23
> **Status:** Current Implementation
> **Audience:** SREs, platform engineers, administrators

---

## 1. Overview

Bud AI Foundry uses the LGTM stack (Loki, Grafana, Tempo, Mimir) for comprehensive observability:
- **Logs:** Loki for log aggregation and querying
- **Metrics:** Mimir for long-term metrics storage (Prometheus-compatible)
- **Traces:** Tempo for distributed tracing
- **Visualization:** Grafana for dashboards and alerting

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        APPLICATION LAYER                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │   budapp    │  │ budcluster  │  │   budsim    │  │ budgateway  │    │
│  │  (Python)   │  │  (Python)   │  │  (Python)   │  │   (Rust)    │    │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │
│         │                │                │                │           │
│         ▼                ▼                ▼                ▼           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     Dapr Sidecar (per pod)                      │   │
│  │  • Metrics export (OpenTelemetry)                               │   │
│  │  • Trace propagation                                            │   │
│  │  • Structured logging                                           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
         │                │                │                │
         │ Prometheus     │ OTLP           │ stdout/stderr  │
         │ scrape         │ traces         │ logs           │
         ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       COLLECTION LAYER                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │    Prometheus   │  │  OpenTelemetry  │  │    Promtail     │         │
│  │    (scraper)    │  │   Collector     │  │  (log shipper)  │         │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘         │
└───────────┼────────────────────┼────────────────────┼───────────────────┘
            │                    │                    │
            ▼                    ▼                    ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                          STORAGE LAYER                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐           │
│  │      Mimir      │  │      Tempo      │  │      Loki       │           │
│  │   (Metrics)     │  │    (Traces)     │  │     (Logs)      │           │
│  │  • Long-term    │  │  • Distributed  │  │  • Aggregation  │           │
│  │  • HA           │  │  • Sampling     │  │  • Indexing     │           │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘           │
└───────────┼────────────────────┼────────────────────┼─────────────────────┘
            │                    │                    │
            └────────────────────┼────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       VISUALIZATION LAYER                               │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                         GRAFANA                                 │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │    │
│  │  │ Dashboards  │  │  Alerting   │  │   Explore   │             │    │
│  │  │             │  │             │  │             │             │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘             │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                 │                                       │
│                                 ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      Alert Routing                              │    │
│  │  • Slack, PagerDuty, Email, Webhook                             │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Metrics (Mimir)

### 3.1 Configuration

```yaml
# Mimir configuration (simplified)
target: all

multitenancy_enabled: false

blocks_storage:
  backend: s3
  s3:
    bucket_name: bud-mimir
    endpoint: minio:9000
  bucket_store:
    sync_dir: /data/tsdb-sync

compactor:
  data_dir: /data/compactor
  sharding_ring:
    kvstore:
      store: memberlist

limits:
  max_global_series_per_user: 500000
  ingestion_rate: 200000
  ingestion_burst_size: 300000
```

### 3.2 Key Metrics

#### Service Health Metrics

| Metric | Description | Labels |
|--------|-------------|--------|
| `http_requests_total` | Total HTTP requests | service, method, status |
| `http_request_duration_seconds` | Request latency | service, method |
| `process_cpu_seconds_total` | CPU usage | service |
| `process_resident_memory_bytes` | Memory usage | service |

#### Inference Metrics

| Metric | Description | Labels |
|--------|-------------|--------|
| `inference_requests_total` | Inference request count | model, endpoint |
| `inference_latency_seconds` | Inference latency | model, endpoint |
| `inference_tokens_total` | Token count | model, direction |
| `inference_queue_depth` | Queue size | endpoint |

#### Cluster Metrics

| Metric | Description | Labels |
|--------|-------------|--------|
| `cluster_node_count` | Nodes per cluster | cluster |
| `cluster_gpu_available` | Available GPUs | cluster, gpu_type |
| `cluster_gpu_utilization` | GPU utilization | cluster, node |
| `cluster_status` | Cluster state | cluster |

### 3.3 Recording Rules

```yaml
groups:
  - name: bud-recordings
    rules:
      # Inference error rate
      - record: inference:error_rate:5m
        expr: |
          sum(rate(inference_requests_total{status="error"}[5m])) by (endpoint)
          /
          sum(rate(inference_requests_total[5m])) by (endpoint)

      # P99 latency
      - record: inference:latency_p99:5m
        expr: |
          histogram_quantile(0.99,
            sum(rate(inference_latency_seconds_bucket[5m])) by (le, endpoint)
          )

      # Throughput
      - record: inference:throughput:5m
        expr: |
          sum(rate(inference_requests_total[5m])) by (endpoint)
```

---

## 4. Logs (Loki)

### 4.1 Configuration

```yaml
# Loki configuration (simplified)
auth_enabled: false

server:
  http_listen_port: 3100

ingester:
  lifecycler:
    ring:
      kvstore:
        store: memberlist
      replication_factor: 1
  chunk_idle_period: 5m
  chunk_retain_period: 30s

schema_config:
  configs:
    - from: 2024-01-01
      store: tsdb
      object_store: s3
      schema: v13
      index:
        prefix: index_
        period: 24h

storage_config:
  aws:
    bucketnames: bud-loki
    endpoint: minio:9000
    s3forcepathstyle: true

limits_config:
  retention_period: 720h  # 30 days
  max_query_series: 5000
```

### 4.2 Log Format

All services use structured JSON logging:

```json
{
  "timestamp": "2026-01-23T10:30:00.000Z",
  "level": "info",
  "logger": "budapp.auth.services",
  "event": "user_login",
  "user_id": "uuid",
  "tenant_id": "uuid",
  "request_id": "req-uuid",
  "duration_ms": 150,
  "message": "User logged in successfully"
}
```

### 4.3 Label Strategy

| Label | Description | Cardinality |
|-------|-------------|-------------|
| `app` | Service name | Low (~15) |
| `namespace` | K8s namespace | Low (~5) |
| `pod` | Pod name | Medium |
| `container` | Container name | Low |
| `level` | Log level | Low (5) |

### 4.4 Common Queries

```logql
# All errors in last hour
{app=~"bud.*"} |= "error" | json | __error__=""

# Slow API requests
{app="budapp"} | json | duration_ms > 1000

# Authentication failures
{app="budapp"} | json | event="login_failed"

# Specific user activity
{app="budapp"} | json | user_id="abc123"

# Error rate by service
sum by (app) (rate({app=~"bud.*"} |= "error" [5m]))
```

---

## 5. Traces (Tempo)

### 5.1 Configuration

```yaml
# Tempo configuration (simplified)
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
        http:

ingester:
  trace_idle_period: 30s
  max_block_bytes: 1000000
  max_block_duration: 5m

storage:
  trace:
    backend: s3
    s3:
      bucket: bud-tempo
      endpoint: minio:9000

overrides:
  max_traces_per_user: 50000
```

### 5.2 Trace Propagation

Services propagate trace context via headers:

| Header | Format | Description |
|--------|--------|-------------|
| `traceparent` | W3C Trace Context | Standard trace header |
| `x-request-id` | UUID | Request correlation |
| `x-dapr-trace-id` | Dapr format | Dapr propagation |

### 5.3 Instrumented Operations

| Service | Operations |
|---------|------------|
| budapp | HTTP handlers, DB queries, auth |
| budcluster | Cluster operations, K8s calls |
| budgateway | Inference routing, provider calls |
| budsim | Simulations, optimization |

---

## 6. Alerting

### 6.1 Alert Categories

| Category | Severity | Response Time |
|----------|----------|---------------|
| Critical | P1 | 15 minutes |
| Warning | P2 | 1 hour |
| Info | P3 | Next business day |

### 6.2 Critical Alerts

```yaml
groups:
  - name: critical-alerts
    rules:
      - alert: ServiceDown
        expr: up{job=~"bud.*"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Service {{ $labels.job }} is down"

      - alert: HighErrorRate
        expr: inference:error_rate:5m > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Error rate above 5% for {{ $labels.endpoint }}"

      - alert: HighLatency
        expr: inference:latency_p99:5m > 5
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "P99 latency above 5s for {{ $labels.endpoint }}"

      - alert: DatabaseConnectionFailure
        expr: pg_up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "PostgreSQL is unreachable"
```

### 6.3 Warning Alerts

```yaml
groups:
  - name: warning-alerts
    rules:
      - alert: HighCPU
        expr: process_cpu_seconds_total > 0.8
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High CPU for {{ $labels.job }}"

      - alert: HighMemory
        expr: process_resident_memory_bytes / node_memory_MemTotal_bytes > 0.8
        for: 10m
        labels:
          severity: warning

      - alert: QueueBacklog
        expr: inference_queue_depth > 100
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Inference queue building up"
```

### 6.4 Alert Routing

```yaml
# Alertmanager configuration
route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty-critical'
    - match:
        severity: warning
      receiver: 'slack-warning'

receivers:
  - name: 'default'
    email_configs:
      - to: 'ops@example.com'

  - name: 'pagerduty-critical'
    pagerduty_configs:
      - routing_key: '<key>'
        severity: critical

  - name: 'slack-warning'
    slack_configs:
      - api_url: 'https://hooks.slack.com/...'
        channel: '#alerts'
```

---

## 7. Dashboards

### 7.1 Pre-built Dashboards

| Dashboard | UID | Description |
|-----------|-----|-------------|
| Platform Overview | `platform-overview` | High-level health |
| Inference Metrics | `inference-metrics` | Model performance |
| Resource Utilization | `resource-util` | CPU/GPU/Memory |
| Error Tracking | `error-tracking` | Error rates |
| Cluster Status | `cluster-status` | Multi-cluster view |
| Audit Activity | `audit-activity` | User actions |

### 7.2 Dashboard Variables

| Variable | Type | Usage |
|----------|------|-------|
| `$namespace` | Query | Filter by K8s namespace |
| `$service` | Query | Filter by service |
| `$cluster` | Query | Filter by cluster |
| `$endpoint` | Query | Filter by endpoint |
| `$interval` | Interval | Time aggregation |

### 7.3 Dashboard Access

| Role | Dashboard Access |
|------|-----------------|
| Admin | All dashboards, edit |
| Operator | All dashboards, view |
| User | Project dashboards, view |

---

## 8. Retention Policies

| Data Type | Hot Storage | Warm Storage | Archive | Total |
|-----------|-------------|--------------|---------|-------|
| Metrics | 14 days | 90 days | - | 90 days |
| Logs | 7 days | 30 days | 1 year | 1 year |
| Traces | 7 days | - | - | 7 days |

---

## 9. Performance Considerations

### 9.1 Metrics Cardinality

| Rule | Guidance |
|------|----------|
| Avoid high-cardinality labels | Don't use user_id, request_id as labels |
| Use recording rules | Pre-aggregate expensive queries |
| Set series limits | Prevent runaway cardinality |

### 9.2 Log Volume Management

| Strategy | Implementation |
|----------|----------------|
| Sampling | Sample debug logs in production |
| Rate limiting | Drop excess logs |
| Aggregation | Aggregate repetitive messages |
| Retention | Shorter retention for verbose logs |

### 9.3 Trace Sampling

```yaml
# Sampling configuration
sampling:
  default:
    type: probabilistic
    value: 0.1  # 10% sampling

  overrides:
    # Always trace errors
    - condition:
        status_code: "error"
      sampling_rate: 1.0

    # Always trace slow requests
    - condition:
        min_duration: "2s"
      sampling_rate: 1.0
```

---

## 10. Access and Security

### 10.1 Grafana Authentication

| Method | Configuration |
|--------|---------------|
| SSO | OIDC with Keycloak |
| RBAC | Org-based permissions |
| Teams | Map to tenant groups |

### 10.2 Data Access Control

| Role | Metrics | Logs | Traces |
|------|---------|------|--------|
| Admin | All | All | All |
| Operator | All | All | All |
| User | Own project | Own project | Own project |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-23 | Documentation | Initial version |
