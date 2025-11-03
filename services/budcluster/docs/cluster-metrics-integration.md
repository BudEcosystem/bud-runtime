# Cluster Metrics Integration

This document describes the end-to-end integration of cluster metrics from OpenTelemetry Collector to the BudAdmin UI.

## Architecture Overview

```
Prometheus (in cluster)
    ↓ (scrape metrics)
kubectl port-forward
    ↓
BudCluster Service
    ↓ (send to OTel)
OpenTelemetry Collector
    ↓ (export to ClickHouse)
ClickHouse Database
    ↓ (query via views)
BudMetrics Service
    ↓ (Dapr service invocation)
BudApp Service (proxy)
    ↓ (REST API)
BudAdmin UI (React)
```

## Components

### 1. OpenTelemetry Collector Configuration

The OTel Collector receives metrics from BudCluster and exports them to ClickHouse using the `clickhouse` exporter.

**Key tables created by OTel:**
- `metrics.otel_metrics_gauge` - Stores gauge metrics with timestamps
- `metrics.otel_metrics_sum` - Stores counter/sum metrics
- `metrics.otel_metrics_histogram` - Stores histogram metrics

**Data structure:**
```sql
-- Example row in otel_metrics_gauge
TimeUnix: 1699123456
MetricName: 'node_memory_MemTotal_bytes'
Value: 16777216000
ResourceAttributes: {'cluster_id': '28fb01cc-...', 'cluster_name': 'my-cluster'}
Attributes: {'instance': 'node1.example.com:9100', 'job': 'node-exporter'}
```

### 2. ClickHouse Views

Views transform OTel's raw format into structured tables for efficient querying:

**Created views:**
- `v_node_metrics` - Node-level CPU, memory, disk metrics
- `v_pod_metrics` - Pod/container metrics with resource usage
- `v_gpu_metrics` - GPU metrics (when available)
- `v_cluster_metrics` - Generic metrics for custom queries
- `mv_node_metrics_5m` - Materialized view with 5-minute aggregations

**SQL script location:** `/services/budmetrics/scripts/create_cluster_metrics_views.sql`

### 3. BudMetrics Service Endpoints

BudMetrics provides REST endpoints to query cluster metrics:

- `GET /cluster-metrics/clusters/{cluster_id}/summary` - Aggregated summary
- `GET /cluster-metrics/clusters/{cluster_id}/nodes` - Node-level metrics
- `GET /cluster-metrics/clusters/{cluster_id}/pods` - Pod-level metrics
- `GET /cluster-metrics/clusters/{cluster_id}/health` - Health status
- `POST /cluster-metrics/clusters/{cluster_id}/query` - Custom ClickHouse queries

### 4. BudApp Proxy Endpoints

BudApp proxies requests to BudMetrics with authentication and access control:

- `GET /clusters/{cluster_id}/metrics/summary`
- `GET /clusters/{cluster_id}/metrics/nodes`
- `GET /clusters/{cluster_id}/metrics/pods`
- `GET /clusters/{cluster_id}/metrics/health`
- `POST /clusters/{cluster_id}/metrics/query`

**Features:**
- Validates user has access to the cluster
- Forwards requests via Dapr service invocation
- Returns proper error responses

### 5. BudAdmin UI Components

The Analytics component displays metrics with charts and tables:

**Features:**
- Summary cards showing key metrics
- Bar chart for node resource usage
- Detailed tables for nodes and pods
- Auto-refresh every 30 seconds
- Color-coded status indicators

**Component location:** `/services/budadmin/src/pages/home/clusters/[slug]/Analytics/index.tsx`

## Setup Instructions

### 1. Create ClickHouse Views

```bash
# Connect to ClickHouse and run the SQL script
clickhouse-client --host localhost --query "$(cat /services/budmetrics/scripts/create_cluster_metrics_views.sql)"
```

### 2. Verify Metrics Collection

```bash
# Check that metrics are being collected
clickhouse-client --query "SELECT count(*) FROM metrics.otel_metrics_gauge WHERE ResourceAttributes['cluster_id'] IS NOT NULL"
```

### 3. Test End-to-End Flow

```bash
cd /services/budcluster
python test_metrics_flow.py
```

### 4. Access UI

Navigate to: https://admin.ditto.bud.studio/clusters/{cluster_id}

Click on the "Analytics" tab to view cluster metrics.

## Troubleshooting

### No Data in ClickHouse

1. Check OTel Collector is running:
```bash
kubectl -n pde-ditto get pod | grep otel-collector
```

2. Check BudCluster is sending metrics:
```bash
kubectl -n pde-ditto logs <budcluster-pod> | grep "Successfully sent"
```

3. Verify ClickHouse connection in OTel Collector:
```bash
kubectl -n pde-ditto logs <otel-collector-pod>
```

### Views Return No Data

1. Check if raw data exists:
```sql
SELECT count(*) FROM metrics.otel_metrics_gauge;
```

2. Verify cluster_id in ResourceAttributes:
```sql
SELECT DISTINCT ResourceAttributes['cluster_id']
FROM metrics.otel_metrics_gauge
WHERE ResourceAttributes['cluster_id'] IS NOT NULL;
```

3. Recreate views if needed:
```bash
clickhouse-client --query "DROP VIEW IF EXISTS metrics.v_node_metrics"
# Then recreate using the SQL script
```

### Frontend Shows Empty Charts

1. Open browser DevTools Network tab
2. Check for failed API calls to `/metrics/*` endpoints
3. Verify authentication token is valid
4. Check console for JavaScript errors

### BudApp Proxy Returns 500 Error

1. Check BudMetrics service is running:
```bash
kubectl -n pde-ditto get pod | grep budmetrics
```

2. Verify Dapr sidecar is healthy:
```bash
kubectl -n pde-ditto describe pod <budapp-pod>
```

3. Check BudApp logs for errors:
```bash
kubectl -n pde-ditto logs <budapp-pod> -c budapp
```

## Data Retention and Lifecycle

All cluster metrics data has a **30-day retention policy** with automatic cleanup:

### Retention Policy
- **Raw OTel Metrics** (`otel_metrics_*`): 30 days
- **ClusterMetrics** table: 30 days
- **NodeMetrics** table: 30 days
- **PodMetrics** table: 30 days
- **GPUMetrics** table: 30 days

### How It Works
ClickHouse automatically deletes data older than 30 days using TTL (Time To Live) settings:
- **Partition-based**: Data is partitioned by month (`PARTITION BY toYYYYMM(ts)`)
- **Automatic cleanup**: ClickHouse background processes delete expired partitions
- **Grace period**: Cleanup may take hours/days depending on merge frequency
- **No manual intervention**: Once configured, data lifecycle is fully automated

### Configuring Retention
To change the retention period, update the following configurations:

1. **For OTel raw metrics**: Update `otelCollector.clickhouse.ttl` in `infra/helm/bud/values.yaml`
   ```yaml
   otelCollector:
     clickhouse:
       ttl: 720h  # 30 days (in hours)
   ```

2. **For cluster metrics tables**: Update `CLICKHOUSE_TTL_CLUSTER_METRICS` in `infra/helm/bud/values.yaml`
   ```yaml
   budmetrics:
     env:
       CLICKHOUSE_TTL_CLUSTER_METRICS: "30"  # Retention in days
   ```

   This single configuration controls TTL for all cluster metrics tables:
   - ClusterMetrics
   - NodeMetrics
   - PodMetrics
   - GPUMetrics

**For local development**: Set the environment variable in `services/budmetrics/.env`:
```bash
CLICKHOUSE_TTL_CLUSTER_METRICS=30
```

### Storage Impact
30-day retention provides a good balance between storage costs and historical analysis:
- **Recent data** (last 7 days): Ideal for troubleshooting and monitoring
- **Medium-term data** (8-30 days): Useful for trend analysis and capacity planning
- **Automatic cleanup**: Prevents unbounded storage growth

## Performance Considerations

- Views aggregate data on-the-fly; for better performance, use materialized views
- The 5-minute materialized view (`mv_node_metrics_5m`) pre-aggregates data
- ClickHouse automatically drops old data based on TTL settings (30 days for all metrics)
- Frontend refreshes every 30 seconds; adjust if needed for performance
- Monthly partitioning enables efficient data pruning and query optimization

## Future Enhancements

1. **Historical Trends**: Add time-range selection and historical charts
2. **Alerting**: Integrate with BudNotify for threshold-based alerts
3. **GPU Metrics**: Display GPU metrics when available
4. **Custom Dashboards**: Allow users to create custom metric dashboards
5. **Export Options**: Add CSV/JSON export for metrics data
