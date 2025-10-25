# ClickHouse Metrics Integration

## Overview

This document describes the integration of ClickHouse-based metrics collection with the cluster monitoring system, replacing the previous Prometheus-based approach.

## Architecture

### Data Flow

**Note:** This describes the ClickHouse-based metrics storage architecture. For details on how budcluster collects metrics from managed clusters, see `otel-metrics-collection.md`.

1. **Metrics Collection**: Managed clusters run Prometheus to collect system and container metrics
2. **Metrics Forwarding**: BudCluster service scrapes metrics from cluster Prometheus and forwards to central OTel Collector
3. **Data Storage**: OTel Collector exports metrics to ClickHouse
4. **Query Layer**: BudMetrics service provides APIs to query metrics from ClickHouse
5. **API Gateway**: BudApp proxies metrics requests to BudMetrics with access control
6. **Frontend**: BudAdmin displays metrics in the Analytics tab of cluster details

### Components

- **BudCluster**: Scrapes metrics from managed cluster Prometheus instances and forwards to OTel Collector
- **OpenTelemetry Collector**: Central collector deployed via Helm chart with ClickHouse exporter configured
- **ClickHouse**: Stores metrics in `otel_metrics_gauge` table
- **BudMetrics**: Provides `/cluster-metrics/{cluster_id}/prometheus-compatible` endpoint
- **BudApp**: Routes metrics requests based on `USE_BUDMETRICS_BACKEND` flag
- **BudAdmin**: Displays metrics charts and tables

## Configuration

### Enabling ClickHouse Backend

1. **BudApp Configuration**:
   ```bash
   # In services/budapp/.env
   USE_BUDMETRICS_BACKEND=true
   BUDMETRICS_APP_ID=budmetrics
   ```

2. **OTel Collector Configuration**:
   ```yaml
   # In otel-collector-config.yaml
   processors:
     resource:
       attributes:
         - key: cluster_id
           value: "your-cluster-id"
           action: insert
   ```

### Metrics Available

The system collects and provides the following metrics:

- **Node Metrics**:
  - CPU usage percentage and cores
  - Memory usage (GB and percentage)
  - Disk usage (GB and percentage)
  - Load averages (1, 5, 15 minutes)
  - Network I/O (inbound/outbound Mbps)

- **Cluster Summary**:
  - Total and average resource utilization
  - Node count
  - Health status

- **Pod Metrics** (when available):
  - CPU and memory usage
  - Container status
  - Restart counts

## API Endpoints

### BudMetrics Endpoints

- `GET /cluster-metrics/{cluster_id}/prometheus-compatible`
  - Returns metrics in Prometheus-compatible format for backward compatibility
  - Parameters:
    - `filter`: Time range (today, 7days, month)
    - `metric_type`: Filter by metric type (all, cpu, memory, disk, network)

### BudApp Proxy Endpoints

- `GET /clusters/{cluster_id}/metrics` - Main metrics endpoint (uses BudMetrics when enabled)
- `GET /clusters/{cluster_id}/metrics/summary` - Cluster summary statistics
- `GET /clusters/{cluster_id}/metrics/nodes` - Node-level metrics
- `GET /clusters/{cluster_id}/metrics/pods` - Pod-level metrics
- `GET /clusters/{cluster_id}/metrics/health` - Health status check
- `POST /clusters/{cluster_id}/metrics/query` - Custom metrics query

## Testing

### End-to-End Test

Run the test script to verify the complete flow:

```bash
cd services/budcluster
python test_metrics_e2e.py
```

### Manual Testing

1. **Check ClickHouse Data**:
   ```sql
   SELECT DISTINCT ResourceAttributes['cluster_id'] as cluster_id
   FROM otel.otel_metrics_gauge
   WHERE TimeUnix > now() - INTERVAL 1 HOUR;
   ```

2. **Test BudMetrics Directly**:
   ```bash
   curl http://localhost:8003/cluster-metrics/{cluster_id}/prometheus-compatible?filter=today
   ```

3. **Test BudApp with Backend**:
   ```bash
   # Set USE_BUDMETRICS_BACKEND=true and restart BudApp
   curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/clusters/{cluster_id}/metrics?filter=today
   ```

## Troubleshooting

### No Metrics Data

1. **Verify OTel Collector is running**:
   ```bash
   kubectl get pods -n observability | grep otel-collector
   ```

2. **Check ClickHouse has data**:
   ```sql
   SELECT count(*) FROM otel.otel_metrics_gauge
   WHERE ResourceAttributes['cluster_id'] = 'your-cluster-id';
   ```

3. **Verify cluster_id attribute**:
   - Check OTel Collector config has the resource processor
   - Ensure cluster_id is being added to metrics

### All Zeros in Response

- This indicates the query is working but no data matches the cluster_id
- Verify the cluster_id in OTel Collector matches your test cluster
- Check TimeUnix values are recent

### Connection Errors

- Ensure all services are running (BudMetrics, BudApp)
- Check Dapr sidecars are healthy
- Verify network connectivity between services

## Migration from Prometheus

The system maintains backward compatibility during migration:

1. **Default Behavior**: Uses existing Prometheus backend
2. **Opt-in Migration**: Set `USE_BUDMETRICS_BACKEND=true` to use ClickHouse
3. **Fallback**: If BudMetrics fails, automatically falls back to Prometheus
4. **Response Format**: Identical format ensures frontend compatibility

## Future Enhancements

- [ ] Add GPU metrics support
- [ ] Implement historical data aggregation
- [ ] Add alerting based on metrics thresholds
- [ ] Support custom metric queries from frontend
- [ ] Add metric export functionality
