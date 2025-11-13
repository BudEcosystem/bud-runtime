# Cluster Metrics Data Pipeline Fix

## Problem

The BudMetrics API was returning empty metrics despite ClickHouse containing millions of metrics from the OTel Collector. This was caused by a data pipeline misconfiguration.

### Root Cause

1. **OTel Collector** writes raw metrics to `otel_metrics_gauge` table ✅
2. **Materialized views** were supposed to transform and populate `NodeMetrics`, `PodMetrics`, `ClusterMetrics` ❌
3. **BudMetrics API** queries `NodeMetrics`, `PodMetrics`, `ClusterMetrics` tables ❌
4. **Result**: API queries empty tables, returns no data ❌

The issue was that the original `create_cluster_metrics_views.sql` created:
- Base tables (`NodeMetrics`, `PodMetrics`, etc.)
- Views for querying (`v_node_metrics`, etc.) - not used by API
- Materialized view (`mv_node_metrics_5m`) - created its own table instead of populating the base tables

**The base tables queried by the API were never populated!**

## Solution

Created proper materialized views that use the `TO` clause to directly populate the base tables that the API queries.

### Architecture Flow (After Fix)

```
Prometheus → BudCluster → OTel Collector → otel_metrics_gauge
                                                    ↓ (materialized views)
                                    NodeMetrics, PodMetrics, ClusterMetrics
                                                    ↓
                                              BudMetrics API
                                                    ↓
                                              BudApp Gateway
                                                    ↓
                                              BudAdmin UI
```

## Files Created

### 1. `fix_cluster_metrics_materialized_views.sql`
- Drops incorrect materialized views
- Creates base tables (NodeMetrics, PodMetrics, GPUMetrics, ClusterMetrics)
- Creates materialized views that populate these tables automatically
- Adds performance indexes

**Key Feature**: Uses `CREATE MATERIALIZED VIEW ... TO metrics.NodeMetrics` syntax to populate base tables.

### 2. `backfill_cluster_metrics.py`
- Python script to backfill historical data from `otel_metrics_gauge`
- Supports filtering by cluster_id, date range
- Includes dry-run mode for safety
- Uses same aggregation logic as materialized views

### 3. Updated `migrate_clickhouse.py`
- Added `setup_cluster_metrics_materialized_views()` method
- Automatically executes SQL fix during migrations
- All new deployments get correct setup automatically

## Usage

### For Existing Environments (One-Time Fix)

#### Step 1: Run Migration (Creates Materialized Views)

```bash
cd services/budmetrics
python scripts/migrate_clickhouse.py
```

This will:
- Create/verify all ClickHouse tables
- Set up materialized views
- **All future metrics will auto-populate from this point forward**

#### Step 2: Backfill Historical Data

For all clusters:
```bash
python scripts/backfill_cluster_metrics.py
```

For specific cluster:
```bash
python scripts/backfill_cluster_metrics.py --cluster-id f48bae4c-3b3a-490f-bc58-ec856c3e3b97
```

With date range:
```bash
python scripts/backfill_cluster_metrics.py \
    --from-date "2025-10-20" \
    --to-date "2025-10-21"
```

Dry run (preview without changes):
```bash
python scripts/backfill_cluster_metrics.py --dry-run
```

### For New Environments

Just run the standard migration:
```bash
cd services/budmetrics
python scripts/migrate_clickhouse.py
```

Everything is set up automatically. No backfill needed since there's no historical data.

## Verification

### 1. Check if Materialized Views Exist

```bash
kubectl exec -it <clickhouse-pod> -- clickhouse-client
```

```sql
-- List materialized views
SELECT name, engine
FROM system.tables
WHERE database = 'metrics'
AND engine = 'MaterializedView'
AND name LIKE 'mv_populate_%';

-- Should show:
-- mv_populate_node_metrics
-- mv_populate_pod_metrics
-- mv_populate_gpu_metrics
-- mv_populate_cluster_metrics
```

### 2. Check if Tables Have Data

```sql
-- Check row counts
SELECT
    'NodeMetrics' as table, count(*) as rows FROM NodeMetrics
UNION ALL
SELECT 'PodMetrics', count(*) FROM PodMetrics
UNION ALL
SELECT 'ClusterMetrics', count(*) FROM ClusterMetrics
FORMAT Pretty;

-- Check specific cluster
SELECT
    cluster_id,
    cluster_name,
    count(*) as metric_count,
    min(ts) as earliest,
    max(ts) as latest
FROM NodeMetrics
WHERE cluster_id = 'f48bae4c-3b3a-490f-bc58-ec856c3e3b97'
GROUP BY cluster_id, cluster_name;
```

### 3. Test BudMetrics API

```bash
# Port-forward to budmetrics
kubectl port-forward -n pde-ditto svc/ditto-budmetrics 8000:3005

# Test summary endpoint
curl "http://localhost:8000/cluster-metrics/clusters/f48bae4c-3b3a-490f-bc58-ec856-c3e3b97/summary"

# Test nodes endpoint
curl "http://localhost:8000/cluster-metrics/clusters/f48bae4c-3b3a-490f-bc58-ec856-c3e3b97/nodes"
```

Should return actual metrics instead of 404 or empty responses.

### 4. Check Frontend

Navigate to cluster analytics page in BudAdmin:
```
https://app.ditto.bud.studio/clusters/f48bae4c-3b3a-490f-bc58-ec856-c3e3b97/metrics
```

Should show:
- Total nodes, pods counts
- CPU, memory, disk usage percentages
- Node-level metrics table
- Pod-level metrics table

## How It Works

### Materialized Views

A materialized view in ClickHouse can either:
1. **Create its own table** (default): `CREATE MATERIALIZED VIEW mv_name AS SELECT ...`
2. **Populate an existing table** (our fix): `CREATE MATERIALIZED VIEW mv_name TO table_name AS SELECT ...`

We use option #2 to populate the tables that the API queries.

### Automatic Population

Once materialized views are created with the `TO` clause:
- **Every new insert** to `otel_metrics_gauge` triggers the materialized view
- The view applies its `SELECT` query to the new data
- Results are automatically inserted into the target table
- **No manual intervention needed**

### Aggregation Logic

The materialized views aggregate metrics at 1-minute intervals:
- Groups by cluster_id, node_name, timestamp (rounded to minute)
- Aggregates values using `avg()`, `max()`, `sum()` functions
- Filters out irrelevant filesystem types (tmpfs, devtmpfs, overlay)
- Calculates percentages for CPU, memory, disk usage

## Benefits

1. **One-time setup**: Run migration once, works forever
2. **Automatic forever**: All future metrics auto-populate
3. **No data loss**: Backfill script recovers historical data
4. **All environments**: New deployments get correct setup automatically
5. **Performance**: Pre-aggregated data, indexed tables for fast queries

## Troubleshooting

### Problem: Backfill shows "No data found"

**Check**: Verify otel_metrics_gauge has data
```sql
SELECT count(*) FROM otel_metrics_gauge
WHERE ResourceAttributes['cluster_id'] = 'your-cluster-id';
```

### Problem: Materialized views not populating

**Check**: Verify materialized views exist and are attached to tables
```sql
SELECT
    name,
    engine,
    create_table_query
FROM system.tables
WHERE name LIKE 'mv_populate%'
FORMAT Vertical;
```

Look for `TO metrics.NodeMetrics` in the `create_table_query`.

### Problem: Migration fails with "already exists"

**Solution**: This is normal! The migration handles existing objects gracefully. Just warnings, not errors.

### Problem: API still returns empty after backfill

**Check**:
1. Verify tables have data (see verification section)
2. Check BudMetrics logs for errors
3. Verify cluster_id matches exactly (UUIDs are case-sensitive)
4. Check time range - API defaults to last 1 hour

## Technical Details

### Data Retention (TTL)

- `NodeMetrics`: 90 days
- `PodMetrics`: 30 days
- `GPUMetrics`: 30 days
- `ClusterMetrics`: 90 days

Old data is automatically deleted by ClickHouse's TTL mechanism.

### Partition Strategy

All tables use monthly partitioning: `PARTITION BY toYYYYMM(ts)`

This enables:
- Efficient time-range queries
- Fast partition dropping for TTL cleanup
- Optimized storage and compression

### Indexes

Each table has indexes for common query patterns:
- cluster_id + timestamp (for cluster-specific queries)
- node_name + timestamp (for node-specific queries)
- namespace + pod_name (for pod queries)

## Migration Timeline

1. **Before**: Empty tables, API returns no data
2. **Step 1 - Migration**: Materialized views created, **future data flows automatically**
3. **Step 2 - Backfill**: Historical data populated from otel_metrics_gauge
4. **After**: Complete data available, API returns metrics

## Related Files

- `/services/budmetrics/budmetrics/cluster_metrics/routes.py` - API endpoints
- `/services/budapp/budapp/cluster_ops/cluster_routes.py` - Proxy gateway
- `/services/budadmin/src/pages/home/clusters/[slug]/Analytics/index.tsx` - Frontend UI
- `/services/budcluster/budcluster/metrics_collector/` - Metrics collection from clusters

## Support

For issues or questions:
1. Check ClickHouse logs: `kubectl logs -n <namespace> <clickhouse-pod>`
2. Check BudMetrics logs: `kubectl logs -n <namespace> <budmetrics-pod>`
3. Run verification queries above
4. Contact the platform team
