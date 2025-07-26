# Deployment Guide

## Overview

This guide covers deployment options for the Bud Serve Metrics application, including:
- Docker deployment
- Docker Compose orchestration
- Kubernetes deployment
- Production configurations
- Monitoring and maintenance

## Deployment Architecture

```
┌─────────────────────┐
│   Load Balancer     │
└──────────┬──────────┘
           │
┌──────────┴──────────┐
│   Application       │
│   (Multiple Pods)   │
└──────────┬──────────┘
           │
┌──────────┴──────────┐
│   ClickHouse        │
│   (Cluster/Single)  │
└─────────────────────┘
```

## Docker Deployment

### Building the Image

```bash
# Production build
docker build -f deploy/Dockerfile -t bud-serve-metrics:latest .

# Development build with hot reload
docker build -f deploy/Dockerfile.dev -t bud-serve-metrics:dev .
```

### Running the Container

```bash
# Basic run
docker run -d \
  --name bud-serve-metrics \
  -p 8000:8000 \
  -e PSQL_HOST=clickhouse.example.com \
  -e PSQL_PORT=9000 \
  -e PSQL_DB_NAME=tensorzero \
  -e SECRETS_PSQL_USER=default \
  -e SECRETS_PSQL_PASSWORD=secure_password \
  bud-serve-metrics:latest

# With all configurations
docker run -d \
  --name bud-serve-metrics \
  -p 8000:8000 \
  --restart unless-stopped \
  --memory 2g \
  --cpus 2 \
  -e PSQL_HOST=clickhouse.example.com \
  -e PSQL_PORT=9000 \
  -e PSQL_DB_NAME=tensorzero \
  -e SECRETS_PSQL_USER=default \
  -e SECRETS_PSQL_PASSWORD=secure_password \
  -e APP_PORT=8000 \
  -e LOG_LEVEL=INFO \
  -e DEBUG=false \
  -e CLICKHOUSE_ENABLE_QUERY_CACHE=true \
  -e CLICKHOUSE_ENABLE_CONNECTION_WARMUP=true \
  bud-serve-metrics:latest
```

## Docker Compose Deployment

### Development Environment

```bash
# Start all services
docker-compose -f deploy/docker-compose-dev.yaml up -d

# View logs
docker-compose -f deploy/docker-compose-dev.yaml logs -f

# Stop services
docker-compose -f deploy/docker-compose-dev.yaml down
```

### Production Environment

Create a `docker-compose.prod.yaml`:

```yaml
version: '3.8'

services:
  app:
    image: bud-serve-metrics:latest
    container_name: bud-serve-metrics
    ports:
      - "8000:8000"
    environment:
      # Database
      PSQL_HOST: clickhouse
      PSQL_PORT: 9000
      PSQL_DB_NAME: ${PSQL_DB_NAME}
      SECRETS_PSQL_USER: ${SECRETS_PSQL_USER}
      SECRETS_PSQL_PASSWORD: ${SECRETS_PSQL_PASSWORD}
      # Application
      APP_PORT: 8000
      LOG_LEVEL: INFO
      DEBUG: "false"
      # Performance
      CLICKHOUSE_ENABLE_QUERY_CACHE: "true"
      CLICKHOUSE_ENABLE_CONNECTION_WARMUP: "true"
    depends_on:
      clickhouse:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  clickhouse:
    image: clickhouse/clickhouse-server:latest
    container_name: clickhouse
    ports:
      - "8123:8123"  # HTTP interface
      - "9000:9000"  # Native protocol
    environment:
      CLICKHOUSE_DB: ${PSQL_DB_NAME}
      CLICKHOUSE_USER: ${SECRETS_PSQL_USER}
      CLICKHOUSE_PASSWORD: ${SECRETS_PSQL_PASSWORD}
      CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT: 1
    volumes:
      - clickhouse_data:/var/lib/clickhouse
      - clickhouse_logs:/var/log/clickhouse-server
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:8123/ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  clickhouse_data:
  clickhouse_logs:
```

## Kubernetes Deployment

### ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: bud-serve-metrics-config
data:
  APP_PORT: "8000"
  LOG_LEVEL: "INFO"
  DEBUG: "false"
  CLICKHOUSE_ENABLE_QUERY_CACHE: "true"
  CLICKHOUSE_ENABLE_CONNECTION_WARMUP: "true"
  PSQL_HOST: "clickhouse-service"
  PSQL_PORT: "9000"
  PSQL_DB_NAME: "tensorzero"
```

### Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: bud-serve-metrics-secrets
type: Opaque
stringData:
  SECRETS_PSQL_USER: "default"
  SECRETS_PSQL_PASSWORD: "secure_password"
```

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bud-serve-metrics
  labels:
    app: bud-serve-metrics
spec:
  replicas: 3
  selector:
    matchLabels:
      app: bud-serve-metrics
  template:
    metadata:
      labels:
        app: bud-serve-metrics
    spec:
      initContainers:
      - name: migrate
        image: bud-serve-metrics:latest
        command: ["python", "scripts/migrate_clickhouse.py", "--max-retries", "30", "--retry-delay", "2"]
        envFrom:
        - configMapRef:
            name: bud-serve-metrics-config
        - secretRef:
            name: bud-serve-metrics-secrets
      containers:
      - name: app
        image: bud-serve-metrics:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: bud-serve-metrics-config
        - secretRef:
            name: bud-serve-metrics-secrets
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: bud-serve-metrics-service
spec:
  selector:
    app: bud-serve-metrics
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

### Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: bud-serve-metrics-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: bud-serve-metrics
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `PSQL_HOST` | ClickHouse host | `clickhouse.example.com` |
| `PSQL_PORT` | ClickHouse native port | `9000` |
| `PSQL_DB_NAME` | Database name | `tensorzero` |
| `SECRETS_PSQL_USER` | Database user | `default` |
| `SECRETS_PSQL_PASSWORD` | Database password | `secure_password` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_PORT` | Application port | `8000` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `DEBUG` | Debug mode | `false` |
| `CLICKHOUSE_ENABLE_QUERY_CACHE` | Enable query caching | `true` |
| `CLICKHOUSE_ENABLE_CONNECTION_WARMUP` | Warm up connections | `true` |
| `ENABLE_PERFORMANCE_PROFILING` | Enable profiling | `false` |

### Connection Pool Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `CLICKHOUSE_POOL_MIN_SIZE` | Minimum pool size | `2` |
| `CLICKHOUSE_POOL_MAX_SIZE` | Maximum pool size | `20` |
| `CLICKHOUSE_QUERY_TIMEOUT` | Query timeout (seconds) | `300` |
| `CLICKHOUSE_MAX_CONCURRENT_QUERIES` | Concurrent query limit | `10` |

## Production Considerations

### 1. Database Setup

#### ClickHouse Cluster

For production, use a ClickHouse cluster:

```xml
<!-- clickhouse/config.d/cluster.xml -->
<clickhouse>
    <remote_servers>
        <metrics_cluster>
            <shard>
                <replica>
                    <host>clickhouse-01</host>
                    <port>9000</port>
                </replica>
                <replica>
                    <host>clickhouse-02</host>
                    <port>9000</port>
                </replica>
            </shard>
        </metrics_cluster>
    </remote_servers>
</clickhouse>
```

#### Distributed Tables

```sql
-- Create local table on each node
CREATE TABLE ModelInferenceDetails_local ON CLUSTER metrics_cluster
(...) ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/ModelInferenceDetails', '{replica}')

-- Create distributed table
CREATE TABLE ModelInferenceDetails ON CLUSTER metrics_cluster
AS ModelInferenceDetails_local
ENGINE = Distributed(metrics_cluster, default, ModelInferenceDetails_local, rand())
```

### 2. Security

#### Network Security

```yaml
# Network Policy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: bud-serve-metrics-netpol
spec:
  podSelector:
    matchLabels:
      app: bud-serve-metrics
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: clickhouse
    ports:
    - protocol: TCP
      port: 9000
```

#### TLS Configuration

```yaml
# Ingress with TLS
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: bud-serve-metrics-ingress
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - metrics.example.com
    secretName: metrics-tls
  rules:
  - host: metrics.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: bud-serve-metrics-service
            port:
              number: 80
```

### 3. Monitoring

#### Prometheus Metrics

```yaml
# ServiceMonitor for Prometheus
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: bud-serve-metrics
spec:
  selector:
    matchLabels:
      app: bud-serve-metrics
  endpoints:
  - port: metrics
    interval: 30s
```

#### Grafana Dashboard

Key metrics to monitor:
- Request rate
- Response time (p50, p95, p99)
- Error rate
- Database query time
- Connection pool usage
- Memory and CPU usage

### 4. Backup and Recovery

#### ClickHouse Backup

```bash
# Backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/clickhouse/${DATE}"

# Create backup
clickhouse-client --query="ALTER TABLE ModelInferenceDetails FREEZE"

# Copy to backup location
cp -r /var/lib/clickhouse/shadow/* ${BACKUP_DIR}/

# Clean shadow
rm -rf /var/lib/clickhouse/shadow/*
```

#### Restore Process

```bash
# Stop ClickHouse
systemctl stop clickhouse-server

# Copy backup data
cp -r /backups/clickhouse/20240101_120000/* /var/lib/clickhouse/data/

# Fix permissions
chown -R clickhouse:clickhouse /var/lib/clickhouse/data/

# Start ClickHouse
systemctl start clickhouse-server
```

### 5. Performance Tuning

#### Application Tuning

```python
# In config.py
@dataclass
class ProductionConfig:
    # Connection pool
    pool_min_size: int = 5
    pool_max_size: int = 50

    # Query settings
    query_timeout: int = 60
    max_concurrent_queries: int = 20

    # Cache settings
    enable_query_cache: bool = True
    query_cache_ttl: int = 300
    query_cache_max_size: int = 10000
```

#### ClickHouse Tuning

```xml
<!-- users.xml -->
<profiles>
    <default>
        <max_memory_usage>10000000000</max_memory_usage>
        <max_threads>16</max_threads>
        <max_execution_time>300</max_execution_time>
        <max_rows_to_read>1000000000</max_rows_to_read>
    </default>
</profiles>
```

## Maintenance

### Health Checks

The application provides health endpoints:

```bash
# Basic health check
curl http://localhost:8000/health

# Detailed health check
curl http://localhost:8000/health/detailed
```

### Log Management

Configure log rotation:

```yaml
# logrotate configuration
/var/log/bud-serve-metrics/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 app app
}
```

### Database Maintenance

```sql
-- Optimize tables
OPTIMIZE TABLE ModelInferenceDetails FINAL;

-- Check table health
CHECK TABLE ModelInferenceDetails;

-- View table size
SELECT
    table,
    formatReadableSize(sum(bytes)) AS size,
    sum(rows) AS rows
FROM system.parts
WHERE active
GROUP BY table;
```

## Troubleshooting

### Common Issues

1. **Connection Pool Exhaustion**
   ```bash
   # Increase pool size
   export CLICKHOUSE_POOL_MAX_SIZE=50
   ```

2. **Slow Queries**
   ```sql
   -- Find slow queries
   SELECT
       query,
       query_duration_ms,
       memory_usage
   FROM system.query_log
   WHERE query_duration_ms > 5000
   ORDER BY query_duration_ms DESC
   LIMIT 10;
   ```

3. **Memory Issues**
   ```bash
   # Adjust memory limits
   docker run --memory=4g --memory-swap=4g
   ```

### Debugging Production Issues

1. **Enable debug logging temporarily**
   ```bash
   kubectl set env deployment/bud-serve-metrics DEBUG=true LOG_LEVEL=DEBUG
   ```

2. **Access container logs**
   ```bash
   kubectl logs -f deployment/bud-serve-metrics
   ```

3. **Execute commands in container**
   ```bash
   kubectl exec -it deployment/bud-serve-metrics -- /bin/bash
   ```
