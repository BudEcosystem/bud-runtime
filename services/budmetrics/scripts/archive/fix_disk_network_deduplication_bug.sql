-- Fix Disk and Network Metrics Deduplication Bug
-- ==================================================
--
-- PROBLEM: Disk and network metrics are 10-11x inflated due to duplicate metric entries
-- being summed without deduplication. The root cause is:
--   1. Prometheus/OTel inserts the same metric 7-11 times per minute into otel_metrics_gauge
--   2. The materialized view uses sumIf() which sums ALL duplicates instead of deduplicating
--
-- EXAMPLE:
--   - Actual disk: 495 GB (verified with df -h)
--   - Database shows: 991 GB (2x due to duplicates)
--   - Network: Shows 650 Gbps instead of realistic 1-10 Gbps
--
-- FIX: Replace sumIf() with subquery that deduplicates by mountpoint/interface before summing
--
-- DATE: 2025-10-23
-- TESTED ON: pde-ditto namespace cluster (f48bae4c-3b3a-490f-bc58-ec856c3e3b97)
--
-- ==================================================

-- STEP 1: Drop the incorrect materialized view
-- ==================================================
DROP VIEW IF EXISTS metrics.mv_populate_node_metrics;

-- STEP 2: Recreate materialized view with corrected deduplication logic
-- ==================================================
CREATE MATERIALIZED VIEW metrics.mv_populate_node_metrics
TO metrics.NodeMetrics
AS
WITH
-- Step 1: Calculate per-core, per-mode CPU rates from counter metrics
-- Rate = (last_value - first_value) / (last_time - first_time)
cpu_core_rates AS (
    SELECT
        toDateTime64(toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE), 3) AS ts,
        ResourceAttributes['cluster_id'] AS cluster_id,
        splitByChar(':', Attributes['instance'])[1] AS node_name,
        Attributes['cpu'] AS cpu_core,
        Attributes['mode'] AS mode,
        toUnixTimestamp(max(TimeUnix)) - toUnixTimestamp(min(TimeUnix)) AS time_delta_seconds,
        -- Calculate rate: handle counter resets (last < first)
        -- No GREATEST protection - we filter invalid data with HAVING instead
        if(argMax(Value, TimeUnix) >= argMin(Value, TimeUnix),
           (argMax(Value, TimeUnix) - argMin(Value, TimeUnix)) / time_delta_seconds,
           0
        ) AS rate
    FROM metrics.otel_metrics_gauge
    WHERE MetricName = 'node_cpu_seconds_total'
      AND ResourceAttributes['cluster_id'] IS NOT NULL
      AND ResourceAttributes['cluster_id'] != ''
      AND Attributes['instance'] IS NOT NULL
      AND Attributes['instance'] != ''
      AND Attributes['cpu'] IS NOT NULL
      AND Attributes['mode'] IS NOT NULL
    GROUP BY ts, cluster_id, node_name, cpu_core, mode
    -- Filter out invalid data: single data points, duplicate timestamps, zero time deltas
    HAVING time_delta_seconds > 0
),
-- Step 2: Aggregate CPU rates per node to calculate overall CPU usage
cpu_metrics AS (
    SELECT
        ts,
        cluster_id,
        node_name,
        countDistinct(cpu_core) AS cpu_cores,
        -- CPU usage = 100 - (idle_rate / total_rate * 100)
        -- Use GREATEST to avoid division by zero
        -- Use LEAST/GREATEST to clamp CPU to 0-100% range (prevents edge case outliers)
        LEAST(100, GREATEST(0,
            round(100 - ((sumIf(rate, mode = 'idle') / GREATEST(sum(rate), 0.01)) * 100), 2)
        )) AS cpu_usage_percent
    FROM cpu_core_rates
    GROUP BY ts, cluster_id, node_name
    -- Filter out cases where all rates are zero (no counter increments)
    HAVING sum(rate) > 0
),
-- Step 3A: Deduplicate disk metrics by mountpoint BEFORE summing
-- FIX: This prevents counting the same filesystem multiple times due to duplicate metric inserts
disk_deduplicated AS (
    SELECT
        toDateTime64(toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE), 3) AS ts,
        ResourceAttributes['cluster_id'] AS cluster_id,
        splitByChar(':', Attributes['instance'])[1] AS node_name,
        Attributes['mountpoint'] AS mountpoint,
        -- Use max() to handle duplicates - all duplicates have same value
        max(if(MetricName = 'node_filesystem_size_bytes', Value, 0)) AS fs_size,
        max(if(MetricName = 'node_filesystem_avail_bytes', Value, 0)) AS fs_avail
    FROM metrics.otel_metrics_gauge
    WHERE MetricName IN ('node_filesystem_size_bytes', 'node_filesystem_avail_bytes')
      AND Attributes['fstype'] NOT IN ('tmpfs', 'devtmpfs', 'overlay')
      AND ResourceAttributes['cluster_id'] IS NOT NULL
      AND ResourceAttributes['cluster_id'] != ''
      AND Attributes['instance'] IS NOT NULL
      AND Attributes['instance'] != ''
      AND Attributes['mountpoint'] IS NOT NULL
      AND Attributes['mountpoint'] != ''
    GROUP BY ts, cluster_id, node_name, mountpoint
),
-- Step 3B: Calculate network rate per container (these are COUNTERS, not gauges!)
-- IMPORTANT: container_network_*_bytes_total are cumulative counters (like node_cpu_seconds_total)
-- We must calculate rate = (delta_bytes) / (delta_time) per container, then sum across containers
-- Previous bug: Summing cumulative totals showed 504 Gbps instead of realistic 10-100 Mbps
network_per_container AS (
    SELECT
        toDateTime64(toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE), 3) AS ts,
        ResourceAttributes['cluster_id'] AS cluster_id,
        splitByChar(':', Attributes['instance'])[1] AS node_name,
        Attributes['id'] AS container_id,
        MetricName,
        toUnixTimestamp(max(TimeUnix)) - toUnixTimestamp(min(TimeUnix)) AS time_delta_seconds,
        -- Calculate rate: (last_value - first_value) / time_delta
        -- Handle counter resets where last < first (return 0)
        if(argMax(Value, TimeUnix) >= argMin(Value, TimeUnix),
           (argMax(Value, TimeUnix) - argMin(Value, TimeUnix)) / GREATEST(time_delta_seconds, 1),
           0
        ) AS bytes_per_second
    FROM metrics.otel_metrics_gauge
    WHERE MetricName IN ('container_network_receive_bytes_total', 'container_network_transmit_bytes_total')
      AND ResourceAttributes['cluster_id'] IS NOT NULL
      AND ResourceAttributes['cluster_id'] != ''
      AND Attributes['instance'] IS NOT NULL
      AND Attributes['instance'] != ''
      AND Attributes['id'] IS NOT NULL
    GROUP BY ts, cluster_id, node_name, container_id, MetricName
    -- Filter out invalid data (single data point or no time delta)
    HAVING time_delta_seconds > 0
),
-- Step 3C: Calculate other (non-CPU, non-disk, non-network) metrics - these are gauges
other_metrics AS (
    SELECT
        toDateTime64(toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE), 3) AS ts,
        ResourceAttributes['cluster_id'] AS cluster_id,
        anyLast(ResourceAttributes['cluster_name']) AS cluster_name,
        splitByChar(':', Attributes['instance'])[1] AS node_name,

        -- Memory metrics (gauges) - maxIf handles duplicates correctly
        maxIf(Value, MetricName = 'node_memory_MemTotal_bytes') AS memory_total_bytes,
        (maxIf(Value, MetricName = 'node_memory_MemTotal_bytes') -
         maxIf(Value, MetricName = 'node_memory_MemAvailable_bytes')) AS memory_used_bytes,
        ((maxIf(Value, MetricName = 'node_memory_MemTotal_bytes') -
          maxIf(Value, MetricName = 'node_memory_MemAvailable_bytes')) /
         nullIf(maxIf(Value, MetricName = 'node_memory_MemTotal_bytes'), 0)) * 100 AS memory_usage_percent,

        -- Load averages (gauges) - avgIf handles duplicates reasonably
        avgIf(Value, MetricName = 'node_load1') AS load_1,
        avgIf(Value, MetricName = 'node_load5') AS load_5,
        avgIf(Value, MetricName = 'node_load15') AS load_15

    FROM metrics.otel_metrics_gauge
    WHERE MetricName IN (
        'node_memory_MemTotal_bytes',
        'node_memory_MemAvailable_bytes',
        'node_load1',
        'node_load5',
        'node_load15'
    )
    AND ResourceAttributes['cluster_id'] IS NOT NULL
    AND ResourceAttributes['cluster_id'] != ''
    AND Attributes['instance'] IS NOT NULL
    AND Attributes['instance'] != ''
    GROUP BY ts, cluster_id, node_name
),
-- Step 3D: Aggregate deduplicated disk metrics per node
disk_aggregated AS (
    SELECT
        ts,
        cluster_id,
        node_name,
        -- Now we can safely sum because each mountpoint appears only once
        sum(fs_size) AS disk_total_bytes,
        sum(fs_size - fs_avail) AS disk_used_bytes,
        (sum(fs_size - fs_avail) / nullIf(sum(fs_size), 0)) * 100 AS disk_usage_percent
    FROM disk_deduplicated
    GROUP BY ts, cluster_id, node_name
),
-- Step 3E: Aggregate network rates per node
network_aggregated AS (
    SELECT
        ts,
        cluster_id,
        node_name,
        -- Sum rates across all containers on this node
        sumIf(bytes_per_second, MetricName = 'container_network_receive_bytes_total') AS network_receive_bytes_per_sec,
        sumIf(bytes_per_second, MetricName = 'container_network_transmit_bytes_total') AS network_transmit_bytes_per_sec
    FROM network_per_container
    GROUP BY ts, cluster_id, node_name
)
-- Step 4: Combine all metrics into final node metrics
SELECT
    COALESCE(cpu.ts, om.ts, disk.ts, net.ts) AS ts,
    COALESCE(cpu.cluster_id, om.cluster_id, disk.cluster_id, net.cluster_id) AS cluster_id,
    om.cluster_name,
    COALESCE(cpu.node_name, om.node_name, disk.node_name, net.node_name) AS node_name,
    COALESCE(cpu.cpu_cores, 0) AS cpu_cores,
    COALESCE(cpu.cpu_usage_percent, 0) AS cpu_usage_percent,
    COALESCE(om.memory_total_bytes, 0) AS memory_total_bytes,
    COALESCE(om.memory_used_bytes, 0) AS memory_used_bytes,
    COALESCE(om.memory_usage_percent, 0) AS memory_usage_percent,
    COALESCE(disk.disk_total_bytes, 0) AS disk_total_bytes,
    COALESCE(disk.disk_used_bytes, 0) AS disk_used_bytes,
    COALESCE(disk.disk_usage_percent, 0) AS disk_usage_percent,
    COALESCE(om.load_1, 0) AS load_1,
    COALESCE(om.load_5, 0) AS load_5,
    COALESCE(om.load_15, 0) AS load_15,
    COALESCE(net.network_receive_bytes_per_sec, 0) AS network_receive_bytes_per_sec,
    COALESCE(net.network_transmit_bytes_per_sec, 0) AS network_transmit_bytes_per_sec
FROM cpu_metrics cpu
FULL OUTER JOIN other_metrics om
    ON cpu.ts = om.ts
    AND cpu.cluster_id = om.cluster_id
    AND cpu.node_name = om.node_name
FULL OUTER JOIN disk_aggregated disk
    ON COALESCE(cpu.ts, om.ts) = disk.ts
    AND COALESCE(cpu.cluster_id, om.cluster_id) = disk.cluster_id
    AND COALESCE(cpu.node_name, om.node_name) = disk.node_name
FULL OUTER JOIN network_aggregated net
    ON COALESCE(cpu.ts, om.ts, disk.ts) = net.ts
    AND COALESCE(cpu.cluster_id, om.cluster_id, disk.cluster_id) = net.cluster_id
    AND COALESCE(cpu.node_name, om.node_name, disk.node_name) = net.node_name;

-- ==================================================
-- VERIFICATION QUERIES
-- ==================================================
-- Run these queries to verify the fix worked:
--
-- 1. Check disk size for a specific cluster (should show ~495 GB, not 991 GB):
--    SELECT node_name, round(disk_total_bytes/1024/1024/1024, 2) as disk_gb
--    FROM metrics.NodeMetrics
--    WHERE cluster_id = 'YOUR_CLUSTER_ID'
--    ORDER BY ts DESC LIMIT 10;
--
-- 2. Check network metrics (should be < 10 Gbps, not 650 Gbps):
--    SELECT node_name,
--           round(network_receive_bytes_per_sec * 8 / 1024 / 1024, 2) as rx_mbps,
--           round(network_transmit_bytes_per_sec * 8 / 1024 / 1024, 2) as tx_mbps
--    FROM metrics.NodeMetrics
--    WHERE cluster_id = 'YOUR_CLUSTER_ID'
--    ORDER BY ts DESC LIMIT 10;
--
-- ==================================================
-- SUCCESS
-- ==================================================
-- Materialized view is now fixed. New data will be correctly deduplicated.
-- For HISTORICAL data, run: python scripts/backfill_cluster_metrics.py
-- ==================================================
