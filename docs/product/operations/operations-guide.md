# Operations Guide

> **Version:** 1.0
> **Last Updated:** 2026-01-23
> **Status:** Reference Documentation
> **Audience:** DevOps, Platform Engineers, SREs

---

## 1. Database Maintenance

### 1.1 PostgreSQL Maintenance

**Vacuum Operations:**
```bash
# Check for bloat
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) as size,
    n_dead_tup,
    last_vacuum,
    last_autovacuum
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 10;

# Manual vacuum (if autovacuum is behind)
VACUUM ANALYZE simulation_results;
VACUUM ANALYZE audit_trail;
```

**Reindex Operations:**
```bash
# Check index bloat
SELECT
    indexrelname,
    pg_size_pretty(pg_relation_size(indexrelid)) as size,
    idx_scan,
    idx_tup_read
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY pg_relation_size(indexrelid) DESC;

# Concurrent reindex (no locks)
REINDEX INDEX CONCURRENTLY idx_simulation_workflow_id;
```

**Health Checks:**
```sql
-- Connection count
SELECT count(*) FROM pg_stat_activity;

-- Long-running queries
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active' AND now() - pg_stat_activity.query_start > interval '5 minutes';

-- Table sizes
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
```

### 1.2 ClickHouse Maintenance

```sql
-- Check table sizes
SELECT
    database,
    table,
    formatReadableSize(sum(bytes_on_disk)) as size,
    sum(rows) as rows
FROM system.parts
WHERE active
GROUP BY database, table
ORDER BY sum(bytes_on_disk) DESC;

-- Optimize partitions
OPTIMIZE TABLE budmetrics.inference_metrics FINAL;

-- Check replication status
SELECT * FROM system.replicas WHERE is_readonly = 1;
```

### 1.3 Redis Maintenance

```bash
# Memory usage
redis-cli INFO memory | grep used_memory_human

# Key count
redis-cli DBSIZE

# Slow log
redis-cli SLOWLOG GET 10

# Clear expired keys (background)
redis-cli CONFIG SET activedefrag yes
```

---

## 2. Troubleshooting

### 2.1 Performance Troubleshooting

**Symptom: High API Latency**

```bash
# Check service response times
kubectl top pods -n bud-system

# Check database connections
kubectl exec -n bud-data postgresql-0 -- psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Check network latency
kubectl exec -n bud-system deployment/budapp -- curl -w "@curl-format.txt" -s -o /dev/null http://postgresql:5432

# Review slow queries
kubectl logs -n bud-system deployment/budapp | grep "slow query"
```

**Symptom: High Memory Usage**

```bash
# Check pod memory
kubectl top pods -n bud-system --containers

# Check for memory leaks
kubectl exec -n bud-system deployment/budapp -- python -c "import tracemalloc; tracemalloc.start()"

# Review garbage collection
kubectl logs -n bud-system deployment/budapp | grep "gc"
```

**Symptom: Inference Slowdown**

```bash
# Check GPU utilization
kubectl exec -n bud-inference deployment/endpoint-xxx -- nvidia-smi

# Check model loading
kubectl logs -n bud-inference deployment/endpoint-xxx | grep "model loaded"

# Check request queue
kubectl exec -n bud-inference deployment/endpoint-xxx -- curl localhost:8000/metrics | grep queue
```

### 2.2 Network Troubleshooting

**DNS Issues:**
```bash
# Test DNS resolution
kubectl run -it --rm debug --image=busybox -- nslookup budapp.bud-system.svc.cluster.local

# Check CoreDNS
kubectl logs -n kube-system -l k8s-app=kube-dns

# Check service endpoints
kubectl get endpoints -n bud-system
```

**Connectivity Issues:**
```bash
# Test service connectivity
kubectl run -it --rm debug --image=curlimages/curl -- curl -v http://budapp.bud-system:8080/health

# Check network policies
kubectl get networkpolicies -n bud-system

# Test cross-namespace connectivity
kubectl exec -n bud-system deployment/budapp -- curl http://postgresql.bud-data:5432
```

**Dapr Sidecar Issues:**
```bash
# Check Dapr sidecar status
kubectl get pods -n bud-system -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.containerStatuses[?(@.name=="daprd")].ready}{"\n"}{end}'

# Check Dapr logs
kubectl logs -n bud-system deployment/budapp -c daprd

# Test Dapr service invocation
kubectl exec -n bud-system deployment/budapp -- curl http://localhost:3500/v1.0/invoke/budcluster/method/health
```

---

## 3. Monitoring

### 3.1 SLI/SLO Definitions

**Service Level Indicators:**

| SLI | Measurement | Source |
|-----|-------------|--------|
| Availability | % successful requests | Prometheus |
| Latency | P50, P90, P99 response time | Prometheus |
| Error Rate | % 5xx responses | Prometheus |
| Throughput | Requests per second | Prometheus |

**Service Level Objectives:**

| Service | Availability | P99 Latency | Error Rate |
|---------|--------------|-------------|------------|
| API Gateway | 99.9% | 500ms | < 0.1% |
| Inference | 99.5% | 5s | < 1% |
| Dashboard | 99.9% | 2s | < 0.1% |

**SLO Burn Rate Alerting:**
```yaml
# Prometheus rule for SLO burn rate
groups:
  - name: slo-burn-rate
    rules:
      - alert: HighErrorBurnRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m]))
          / sum(rate(http_requests_total[5m])) > 14.4 * 0.001
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High error burn rate"
```

### 3.2 Distributed Tracing

**Tempo Configuration:**
```yaml
# Trace sampling configuration
tempo:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317
        http:
          endpoint: 0.0.0.0:4318
  sampling:
    rate: 0.1  # 10% sampling for high-volume services
```

**Tracing in Services:**
```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

tracer = trace.get_tracer(__name__)

@tracer.start_as_current_span("process_request")
def process_request(request):
    span = trace.get_current_span()
    span.set_attribute("request.id", request.id)
    span.set_attribute("model.name", request.model_name)
    # ... process
```

**Querying Traces:**
```
# Grafana Tempo query examples
# Find slow requests
{duration > 5s}

# Find errors
{status = error}

# Find by service
{service.name = "budapp"}
```

### 3.3 Custom Metrics

**Adding Application Metrics:**
```python
from prometheus_client import Counter, Histogram, Gauge

# Request counter
requests_total = Counter(
    'inference_requests_total',
    'Total inference requests',
    ['model', 'status']
)

# Latency histogram
latency_histogram = Histogram(
    'inference_latency_seconds',
    'Inference latency',
    ['model'],
    buckets=[0.1, 0.5, 1, 2, 5, 10]
)

# GPU utilization gauge
gpu_utilization = Gauge(
    'gpu_utilization_percent',
    'GPU utilization percentage',
    ['gpu_id', 'model']
)
```

---

## 4. Capacity Planning

### 4.1 Capacity Planning Guide

**Resource Estimation:**
```
# CPU estimation
cpu_needed = (requests_per_sec * avg_processing_time) / utilization_target

# Memory estimation
memory_needed = (concurrent_requests * memory_per_request) + base_memory

# GPU estimation
gpus_needed = ceil(model_memory / gpu_memory) * replicas
```

**Growth Projections:**
| Metric | Current | +3 months | +6 months | +12 months |
|--------|---------|-----------|-----------|------------|
| Requests/day | 100K | 250K | 500K | 1M |
| Models deployed | 10 | 25 | 50 | 100 |
| Storage (TB) | 5 | 12 | 25 | 50 |
| GPU hours/day | 100 | 250 | 500 | 1000 |

### 4.2 Performance Tuning

**Application Tuning:**
```yaml
# Gunicorn workers
workers: 4  # 2-4 x CPU cores
worker_class: uvicorn.workers.UvicornWorker
worker_connections: 1000
timeout: 120
keepalive: 5
```

**Database Tuning:**
```sql
-- PostgreSQL tuning for write-heavy workloads
ALTER SYSTEM SET shared_buffers = '4GB';
ALTER SYSTEM SET effective_cache_size = '12GB';
ALTER SYSTEM SET maintenance_work_mem = '1GB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '64MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET work_mem = '50MB';
ALTER SYSTEM SET min_wal_size = '2GB';
ALTER SYSTEM SET max_wal_size = '8GB';
```

---

## 5. Load Testing

### 5.1 Load Test Guide

**Test Types:**
| Type | Purpose | Duration | Load |
|------|---------|----------|------|
| Smoke | Basic functionality | 1-5 min | 1-5 users |
| Load | Normal operation | 30-60 min | Expected load |
| Stress | Find breaking point | 30-60 min | 2-3x expected |
| Soak | Stability over time | 4-24 hours | Normal load |

**k6 Load Test Example:**
```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
    stages: [
        { duration: '2m', target: 10 },   // Ramp up
        { duration: '5m', target: 10 },   // Steady state
        { duration: '2m', target: 50 },   // Stress
        { duration: '5m', target: 50 },   // Steady at stress
        { duration: '2m', target: 0 },    // Ramp down
    ],
    thresholds: {
        http_req_duration: ['p(99)<500'],  // 99% under 500ms
        http_req_failed: ['rate<0.01'],    // Error rate < 1%
    },
};

export default function () {
    const res = http.post(
        'https://api.bud.example.com/v1/chat/completions',
        JSON.stringify({
            model: 'test-endpoint',
            messages: [{ role: 'user', content: 'Hello' }],
            max_tokens: 50,
        }),
        {
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': __ENV.API_KEY,
            },
        }
    );

    check(res, {
        'status is 200': (r) => r.status === 200,
        'response has choices': (r) => JSON.parse(r.body).choices.length > 0,
    });

    sleep(1);
}
```

### 5.2 Load Test Report

```markdown
# Load Test Report

## Summary
- Date: 2026-01-23
- Duration: 60 minutes
- Peak Load: 50 concurrent users
- Total Requests: 180,000

## Results
| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Availability | 99.9% | 99.95% | ✅ |
| P50 Latency | 200ms | 150ms | ✅ |
| P99 Latency | 500ms | 420ms | ✅ |
| Error Rate | < 1% | 0.05% | ✅ |
| Throughput | 50 RPS | 55 RPS | ✅ |

## Observations
- GPU utilization peaked at 85%
- Memory usage stable at 75%
- No connection pool exhaustion

## Recommendations
- Current capacity supports 50 concurrent users
- Scale to 3 replicas for 100+ users
```

---

## 6. CI/CD Operations

### 6.1 CI/CD Pipeline Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Commit    │───▶│    Build    │───▶│    Test     │───▶│   Deploy    │
│             │    │             │    │             │    │             │
│ - Lint      │    │ - Docker    │    │ - Unit      │    │ - Staging   │
│ - Format    │    │ - Helm      │    │ - Integration│   │ - Prod      │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### 6.2 GitOps Workflow

**ArgoCD Application:**
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: bud-platform
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/org/bud-platform
    targetRevision: HEAD
    path: infra/helm/bud
    helm:
      valueFiles:
        - values-production.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: bud-system
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

### 6.3 Container Registry

**Image Signing:**
```bash
# Sign image with Cosign
cosign sign --key cosign.key ghcr.io/org/budapp:v1.2.3

# Verify signature
cosign verify --key cosign.pub ghcr.io/org/budapp:v1.2.3
```

**Vulnerability Scanning:**
```bash
# Scan with Trivy
trivy image ghcr.io/org/budapp:v1.2.3

# Policy enforcement
trivy image --severity CRITICAL,HIGH --exit-code 1 ghcr.io/org/budapp:v1.2.3
```

### 6.4 Release Management

**Versioning:**
- Semantic versioning (MAJOR.MINOR.PATCH)
- Git tags for releases
- Changelog generated from conventional commits

**Release Process:**
1. Create release branch from main
2. Run full test suite
3. Generate changelog
4. Tag release
5. Build and push images
6. Deploy to staging
7. Smoke tests
8. Deploy to production
9. Monitor for issues

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-23 | Documentation | Initial version |
