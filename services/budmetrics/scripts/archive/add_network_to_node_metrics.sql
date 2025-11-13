-- Add Network Metrics to NodeMetrics Table
-- This script adds network receive/transmit rate columns to the NodeMetrics table
-- for optimized network metrics queries

-- ============================================================================
-- STEP 1: Add network columns to NodeMetrics table
-- ============================================================================

ALTER TABLE metrics.NodeMetrics
ADD COLUMN IF NOT EXISTS network_receive_bytes_per_sec Float64 DEFAULT 0;

ALTER TABLE metrics.NodeMetrics
ADD COLUMN IF NOT EXISTS network_transmit_bytes_per_sec Float64 DEFAULT 0;

-- ============================================================================
-- STEP 2: Add indexes for network columns
-- ============================================================================

ALTER TABLE metrics.NodeMetrics
ADD INDEX IF NOT EXISTS idx_network_receive (network_receive_bytes_per_sec)
TYPE minmax GRANULARITY 1;

ALTER TABLE metrics.NodeMetrics
ADD INDEX IF NOT EXISTS idx_network_transmit (network_transmit_bytes_per_sec)
TYPE minmax GRANULARITY 1;

-- ============================================================================
-- STEP 3: Recreate materialized view to include network metrics
-- ============================================================================

-- Drop the existing materialized view
DROP VIEW IF EXISTS metrics.mv_populate_node_metrics;

-- Recreate with network metrics aggregation
CREATE MATERIALIZED VIEW metrics.mv_populate_node_metrics
TO metrics.NodeMetrics
AS
SELECT
    toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE) AS ts,
    ResourceAttributes['cluster_id'] AS cluster_id,
    anyLast(ResourceAttributes['cluster_name']) AS cluster_name,
    splitByChar(':', Attributes['instance'])[1] AS node_name,

    -- CPU metrics: Count distinct CPU cores
    countDistinctIf(Attributes['cpu'], MetricName = 'node_cpu_seconds_total') AS cpu_cores,

    -- CPU usage: Calculate percentage from idle time
    100 - (avgIf(Value, MetricName = 'node_cpu_seconds_total' AND Attributes['mode'] = 'idle') * 100 /
           nullIf(sumIf(Value, MetricName = 'node_cpu_seconds_total'), 0) * 100) AS cpu_usage_percent,

    -- Memory metrics
    maxIf(Value, MetricName = 'node_memory_MemTotal_bytes') AS memory_total_bytes,
    (maxIf(Value, MetricName = 'node_memory_MemTotal_bytes') -
     maxIf(Value, MetricName = 'node_memory_MemAvailable_bytes')) AS memory_used_bytes,
    ((maxIf(Value, MetricName = 'node_memory_MemTotal_bytes') -
      maxIf(Value, MetricName = 'node_memory_MemAvailable_bytes')) /
     nullIf(maxIf(Value, MetricName = 'node_memory_MemTotal_bytes'), 0)) * 100 AS memory_usage_percent,

    -- Disk metrics: Sum all non-tmpfs filesystems
    sumIf(Value, MetricName = 'node_filesystem_size_bytes' AND
          Attributes['fstype'] NOT IN ('tmpfs', 'devtmpfs', 'overlay')) AS disk_total_bytes,
    (sumIf(Value, MetricName = 'node_filesystem_size_bytes' AND
           Attributes['fstype'] NOT IN ('tmpfs', 'devtmpfs', 'overlay')) -
     sumIf(Value, MetricName = 'node_filesystem_avail_bytes' AND
           Attributes['fstype'] NOT IN ('tmpfs', 'devtmpfs', 'overlay'))) AS disk_used_bytes,
    ((sumIf(Value, MetricName = 'node_filesystem_size_bytes' AND
            Attributes['fstype'] NOT IN ('tmpfs', 'devtmpfs', 'overlay')) -
      sumIf(Value, MetricName = 'node_filesystem_avail_bytes' AND
            Attributes['fstype'] NOT IN ('tmpfs', 'devtmpfs', 'overlay'))) /
     nullIf(sumIf(Value, MetricName = 'node_filesystem_size_bytes' AND
                  Attributes['fstype'] NOT IN ('tmpfs', 'devtmpfs', 'overlay')), 0)) * 100 AS disk_usage_percent,

    -- Load averages
    avgIf(Value, MetricName = 'node_load1') AS load_1,
    avgIf(Value, MetricName = 'node_load5') AS load_5,
    avgIf(Value, MetricName = 'node_load15') AS load_15,

    -- Network metrics: Sum container network metrics per node (normalized by IP)
    -- Note: These are counter values, will be converted to rates in the API layer
    sumIf(Value, MetricName = 'container_network_receive_bytes_total') AS network_receive_bytes_per_sec,
    sumIf(Value, MetricName = 'container_network_transmit_bytes_total') AS network_transmit_bytes_per_sec

FROM metrics.otel_metrics_gauge
WHERE MetricName IN (
    'node_cpu_seconds_total',
    'node_memory_MemTotal_bytes',
    'node_memory_MemAvailable_bytes',
    'node_filesystem_size_bytes',
    'node_filesystem_avail_bytes',
    'node_load1',
    'node_load5',
    'node_load15',
    'container_network_receive_bytes_total',
    'container_network_transmit_bytes_total'
)
AND ResourceAttributes['cluster_id'] IS NOT NULL
AND ResourceAttributes['cluster_id'] != ''
AND Attributes['instance'] IS NOT NULL
AND Attributes['instance'] != ''
GROUP BY
    toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE),
    ResourceAttributes['cluster_id'],
    splitByChar(':', Attributes['instance'])[1];

-- ============================================================================
-- SUCCESS
-- ============================================================================
-- Network columns added to NodeMetrics table
-- Materialized view recreated to include network metrics
-- All NEW data will automatically populate network columns
--
-- For HISTORICAL data, run the backfill query in this cluster:
--   See backfill section below or run backfill_network_metrics.sql
-- ============================================================================
