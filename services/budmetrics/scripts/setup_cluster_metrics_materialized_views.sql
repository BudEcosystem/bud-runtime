-- Fix Cluster Metrics Materialized Views
-- This script corrects the materialized view setup to properly populate NodeMetrics, PodMetrics, and ClusterMetrics tables
--
-- Problem: Original setup created materialized views with their own storage, not populating the base tables
-- Solution: Create materialized views that use TO clause to populate the actual tables the API queries
--
-- Run this once per ClickHouse instance, then all future data will auto-populate

-- ============================================================================
-- STEP 1: Drop incorrect materialized views if they exist
-- ============================================================================

DROP VIEW IF EXISTS metrics.mv_node_metrics_5m;

-- ============================================================================
-- STEP 2: Base tables (created by Python migration script)
-- ============================================================================

-- NOTE: The base tables (NodeMetrics, PodMetrics, GPUMetrics, ClusterMetrics)
-- are created by the Python migration script (migrate_clickhouse.py) with
-- the correct schema, indexes, and partitioning strategy.
--
-- This SQL file ONLY creates the materialized views that populate those tables.
-- Do NOT duplicate table creation here.

-- ============================================================================
-- STEP 3: Create materialized views that populate the base tables
-- ============================================================================

-- Materialized View for Node Metrics
-- This will automatically populate metrics.NodeMetrics with all new data from otel_metrics_gauge
--
-- IMPORTANT: CPU metrics are COUNTERS (node_cpu_seconds_total) and require rate calculation
-- Other metrics (memory, disk) are GAUGES and can be aggregated directly
CREATE MATERIALIZED VIEW IF NOT EXISTS metrics.mv_populate_node_metrics
TO metrics.NodeMetrics
AS
WITH
-- Step 1: Calculate per-core, per-mode CPU rates from counter metrics
-- Rate = (last_value - first_value) / (last_time - first_time)
cpu_core_rates AS (
    SELECT
        toDateTime64(toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE), 3) AS ts,
        ResourceAttributes['cluster_id'] AS cluster_id,
        coalesce(Attributes['node'], splitByChar(':', Attributes['instance'])[1]) AS node_name,
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
-- IMPORTANT: Prometheus/OTel may insert the same metric 7-11 times per minute
-- Using sumIf() directly would multiply disk size by ~10x (e.g., 495 GB shows as 991 GB)
-- FIX: Deduplicate by mountpoint first, then sum
disk_deduplicated AS (
    SELECT
        toDateTime64(toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE), 3) AS ts,
        ResourceAttributes['cluster_id'] AS cluster_id,
        coalesce(Attributes['node'], splitByChar(':', Attributes['instance'])[1]) AS node_name,
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
        coalesce(Attributes['node'], splitByChar(':', Attributes['instance'])[1]) AS node_name,
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
        coalesce(Attributes['node'], splitByChar(':', Attributes['instance'])[1]) AS node_name,

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

-- Materialized View for Pod Metrics
-- This will automatically populate metrics.PodMetrics with all new data
CREATE MATERIALIZED VIEW IF NOT EXISTS metrics.mv_populate_pod_metrics
TO metrics.PodMetrics
AS
SELECT
    toDateTime64(toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE), 3) AS ts,
    ResourceAttributes['cluster_id'] AS cluster_id,
    anyLast(ResourceAttributes['cluster_name']) AS cluster_name,
    Attributes['namespace'] AS namespace,
    Attributes['pod'] AS pod_name,
    Attributes['container'] AS container_name,

    -- Resource requests/limits
    maxIf(Value, MetricName = 'kube_pod_container_resource_requests' AND
          Attributes['resource'] = 'cpu') AS cpu_requests,
    maxIf(Value, MetricName = 'kube_pod_container_resource_limits' AND
          Attributes['resource'] = 'cpu') AS cpu_limits,
    maxIf(Value, MetricName = 'kube_pod_container_resource_requests' AND
          Attributes['resource'] = 'memory') AS memory_requests_bytes,
    maxIf(Value, MetricName = 'kube_pod_container_resource_limits' AND
          Attributes['resource'] = 'memory') AS memory_limits_bytes,

    -- Actual usage
    avgIf(Value, MetricName = 'container_cpu_usage_seconds_total') AS cpu_usage,
    avgIf(Value, MetricName = 'container_memory_working_set_bytes') AS memory_usage_bytes,

    -- Restarts
    toInt32(maxIf(Value, MetricName = 'kube_pod_container_status_restarts_total')) AS restarts,

    -- Status (simplified - extracting from phase)
    CASE
        WHEN maxIf(Value, MetricName = 'kube_pod_status_phase' AND Attributes['phase'] = 'Running') = 1 THEN 'Running'
        WHEN maxIf(Value, MetricName = 'kube_pod_status_phase' AND Attributes['phase'] = 'Pending') = 1 THEN 'Pending'
        WHEN maxIf(Value, MetricName = 'kube_pod_status_phase' AND Attributes['phase'] = 'Failed') = 1 THEN 'Failed'
        WHEN maxIf(Value, MetricName = 'kube_pod_status_phase' AND Attributes['phase'] = 'Succeeded') = 1 THEN 'Succeeded'
        ELSE 'Unknown'
    END AS status

FROM metrics.otel_metrics_gauge
WHERE MetricName IN (
    'kube_pod_container_resource_requests',
    'kube_pod_container_resource_limits',
    'container_cpu_usage_seconds_total',
    'container_memory_usage_bytes',
    'container_memory_working_set_bytes',
    'kube_pod_container_status_restarts_total',
    'kube_pod_status_phase'
)
AND ResourceAttributes['cluster_id'] IS NOT NULL
AND ResourceAttributes['cluster_id'] != ''
AND Attributes['pod'] IS NOT NULL
AND Attributes['pod'] != ''
GROUP BY
    toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE),
    ResourceAttributes['cluster_id'],
    Attributes['namespace'],
    Attributes['pod'],
    Attributes['container'];

-- Materialized View for GPU Metrics
-- This will automatically populate metrics.GPUMetrics with all new data
CREATE MATERIALIZED VIEW IF NOT EXISTS metrics.mv_populate_gpu_metrics
TO metrics.GPUMetrics
AS
SELECT
    toDateTime64(toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE), 3) AS ts,
    ResourceAttributes['cluster_id'] AS cluster_id,
    anyLast(ResourceAttributes['cluster_name']) AS cluster_name,
    Attributes['node'] AS node_name,
    toUInt8OrZero(Attributes['gpu']) AS gpu_index,
    anyLast(Attributes['gpu_model']) AS gpu_model,

    -- GPU utilization and memory
    avgIf(Value, MetricName = 'DCGM_FI_DEV_GPU_UTIL') AS utilization_percent,
    maxIf(Value, MetricName = 'DCGM_FI_DEV_FB_USED') * 1024 * 1024 AS memory_used_bytes,
    (maxIf(Value, MetricName = 'DCGM_FI_DEV_FB_USED') +
     maxIf(Value, MetricName = 'DCGM_FI_DEV_FB_FREE')) * 1024 * 1024 AS memory_total_bytes,

    -- Temperature and power
    avgIf(Value, MetricName = 'DCGM_FI_DEV_GPU_TEMP') AS temperature_celsius,
    avgIf(Value, MetricName = 'DCGM_FI_DEV_POWER_USAGE') AS power_watts

FROM metrics.otel_metrics_gauge
WHERE MetricName IN (
    'DCGM_FI_DEV_GPU_UTIL',
    'DCGM_FI_DEV_MEM_COPY_UTIL',
    'DCGM_FI_DEV_FB_FREE',
    'DCGM_FI_DEV_FB_USED',
    'DCGM_FI_DEV_GPU_TEMP',
    'DCGM_FI_DEV_POWER_USAGE'
)
AND ResourceAttributes['cluster_id'] IS NOT NULL
AND ResourceAttributes['cluster_id'] != ''
GROUP BY
    toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE),
    ResourceAttributes['cluster_id'],
    Attributes['node'],
    toUInt8OrZero(Attributes['gpu']);

-- Materialized View for HAMI GPU Metrics (Time-Slicing)
-- This will automatically populate metrics.HAMIGPUMetrics from HAMI scheduler metrics
-- HAMI provides GPU time-slicing metrics different from DCGM hardware metrics
CREATE MATERIALIZED VIEW IF NOT EXISTS metrics.mv_populate_hami_gpu_metrics
TO metrics.HAMIGPUMetrics
AS
WITH
-- Get device overview (metadata) from nodeGPUOverview metric
-- nodeGPUOverview contains device UUID, type, index, and memory limit in labels
device_overview AS (
    SELECT
        toDateTime64(toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE), 3) AS ts,
        ResourceAttributes['cluster_id'] AS cluster_id,
        anyLast(ResourceAttributes['cluster_name']) AS cluster_name,
        Attributes['nodeid'] AS node_name,
        Attributes['deviceuuid'] AS device_uuid,
        anyLast(Attributes['devicetype']) AS device_type,
        toUInt8OrZero(Attributes['deviceidx']) AS device_index,
        -- devicememorylimit is in MiB, convert to GB
        max(toFloat64OrZero(Attributes['devicememorylimit'])) / 1024.0 AS total_memory_gb
    FROM metrics.otel_metrics_gauge
    WHERE MetricName = 'nodeGPUOverview'
      AND ResourceAttributes['cluster_id'] IS NOT NULL
      AND ResourceAttributes['cluster_id'] != ''
      AND Attributes['deviceuuid'] IS NOT NULL
      AND Attributes['deviceuuid'] != ''
    GROUP BY ts, cluster_id, node_name, device_uuid, device_index
),
-- Get core allocation percentage from GPUDeviceCoreAllocated
core_allocated AS (
    SELECT
        toDateTime64(toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE), 3) AS ts,
        ResourceAttributes['cluster_id'] AS cluster_id,
        Attributes['deviceuuid'] AS device_uuid,
        avg(Value) AS core_allocated_percent
    FROM metrics.otel_metrics_gauge
    WHERE MetricName = 'GPUDeviceCoreAllocated'
      AND ResourceAttributes['cluster_id'] IS NOT NULL
      AND ResourceAttributes['cluster_id'] != ''
      AND Attributes['deviceuuid'] IS NOT NULL
    GROUP BY ts, cluster_id, device_uuid
),
-- Get memory allocation (in bytes, convert to GB)
memory_allocated AS (
    SELECT
        toDateTime64(toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE), 3) AS ts,
        ResourceAttributes['cluster_id'] AS cluster_id,
        Attributes['deviceuuid'] AS device_uuid,
        avg(Value) / (1024 * 1024 * 1024) AS memory_allocated_gb
    FROM metrics.otel_metrics_gauge
    WHERE MetricName = 'GPUDeviceMemoryAllocated'
      AND ResourceAttributes['cluster_id'] IS NOT NULL
      AND ResourceAttributes['cluster_id'] != ''
      AND Attributes['deviceuuid'] IS NOT NULL
    GROUP BY ts, cluster_id, device_uuid
),
-- Get shared container count (number of pods sharing this GPU)
shared_count AS (
    SELECT
        toDateTime64(toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE), 3) AS ts,
        ResourceAttributes['cluster_id'] AS cluster_id,
        Attributes['deviceuuid'] AS device_uuid,
        max(toUInt16(Value)) AS shared_containers_count
    FROM metrics.otel_metrics_gauge
    WHERE MetricName = 'GPUDeviceSharedNum'
      AND ResourceAttributes['cluster_id'] IS NOT NULL
      AND ResourceAttributes['cluster_id'] != ''
      AND Attributes['deviceuuid'] IS NOT NULL
    GROUP BY ts, cluster_id, device_uuid
),
-- Get DCGM hardware metrics (temperature, power, utilization, clocks)
-- DCGM metrics use 'UUID' label instead of 'deviceuuid'
dcgm_metrics AS (
    SELECT
        toDateTime64(toStartOfInterval(TimeUnix, INTERVAL 1 MINUTE), 3) AS ts,
        ResourceAttributes['cluster_id'] AS cluster_id,
        Attributes['UUID'] AS device_uuid,
        avgIf(Value, MetricName = 'DCGM_FI_DEV_GPU_TEMP') AS temperature_celsius,
        avgIf(Value, MetricName = 'DCGM_FI_DEV_POWER_USAGE') AS power_watts,
        avgIf(Value, MetricName = 'DCGM_FI_DEV_SM_CLOCK') AS sm_clock_mhz,
        avgIf(Value, MetricName = 'DCGM_FI_DEV_MEM_CLOCK') AS mem_clock_mhz,
        avgIf(Value, MetricName = 'DCGM_FI_DEV_GPU_UTIL') AS gpu_utilization_percent
    FROM metrics.otel_metrics_gauge
    WHERE MetricName IN (
        'DCGM_FI_DEV_GPU_TEMP',
        'DCGM_FI_DEV_POWER_USAGE',
        'DCGM_FI_DEV_SM_CLOCK',
        'DCGM_FI_DEV_MEM_CLOCK',
        'DCGM_FI_DEV_GPU_UTIL'
    )
      AND ResourceAttributes['cluster_id'] IS NOT NULL
      AND ResourceAttributes['cluster_id'] != ''
      AND Attributes['UUID'] IS NOT NULL
      AND Attributes['UUID'] != ''
    GROUP BY ts, cluster_id, device_uuid
)
-- Combine all HAMI metrics with DCGM hardware data into final HAMIGPUMetrics table
SELECT
    d.ts AS ts,
    d.cluster_id AS cluster_id,
    d.cluster_name AS cluster_name,
    d.node_name AS node_name,
    d.device_uuid AS device_uuid,
    d.device_type AS device_type,
    d.device_index AS device_index,
    COALESCE(c.core_allocated_percent, 0) AS core_allocated_percent,
    COALESCE(m.memory_allocated_gb, 0) AS memory_allocated_gb,
    COALESCE(s.shared_containers_count, 0) AS shared_containers_count,
    d.total_memory_gb AS total_memory_gb,
    100.0 AS total_cores_percent,
    -- Core utilization is same as allocation in HAMI (time-slicing model)
    COALESCE(c.core_allocated_percent, 0) AS core_utilization_percent,
    -- Memory utilization percentage (allocated / total * 100)
    CASE
        WHEN d.total_memory_gb > 0 THEN LEAST(100, (COALESCE(m.memory_allocated_gb, 0) / d.total_memory_gb) * 100)
        ELSE 0
    END AS memory_utilization_percent,
    'time-slicing' AS hardware_mode,
    -- DCGM hardware metrics (enriched from DCGM Exporter)
    COALESCE(dcgm.temperature_celsius, 0) AS temperature_celsius,
    COALESCE(dcgm.power_watts, 0) AS power_watts,
    toUInt32(COALESCE(dcgm.sm_clock_mhz, 0)) AS sm_clock_mhz,
    toUInt32(COALESCE(dcgm.mem_clock_mhz, 0)) AS mem_clock_mhz,
    COALESCE(dcgm.gpu_utilization_percent, 0) AS gpu_utilization_percent
FROM device_overview d
LEFT JOIN core_allocated c ON d.ts = c.ts AND d.cluster_id = c.cluster_id AND d.device_uuid = c.device_uuid
LEFT JOIN memory_allocated m ON d.ts = m.ts AND d.cluster_id = m.cluster_id AND d.device_uuid = m.device_uuid
LEFT JOIN shared_count s ON d.ts = s.ts AND d.cluster_id = s.cluster_id AND d.device_uuid = s.device_uuid
LEFT JOIN dcgm_metrics dcgm ON d.ts = dcgm.ts AND d.cluster_id = dcgm.cluster_id AND d.device_uuid = dcgm.device_uuid;

-- NOTE: mv_populate_hami_slice_metrics is created in migrate_clickhouse.py
-- via create_hami_slice_metrics_materialized_view() method to ensure proper DROP/CREATE handling

-- Materialized View for Generic Cluster Metrics
-- This stores all metrics in a generic format for custom queries
CREATE MATERIALIZED VIEW IF NOT EXISTS metrics.mv_populate_cluster_metrics
TO metrics.ClusterMetrics
AS
SELECT
    TimeUnix AS ts,
    ResourceAttributes['cluster_id'] AS cluster_id,
    anyLast(ResourceAttributes['cluster_name']) AS cluster_name,
    anyLast(ResourceAttributes['cluster_platform']) AS cluster_platform,
    MetricName AS metric_name,
    avg(Value) AS value,
    Attributes AS labels
FROM metrics.otel_metrics_gauge
WHERE ResourceAttributes['cluster_id'] IS NOT NULL
AND ResourceAttributes['cluster_id'] != ''
GROUP BY
    TimeUnix,
    ResourceAttributes['cluster_id'],
    MetricName,
    Attributes;

-- ============================================================================
-- STEP 4: Indexes (created by Python migration script)
-- ============================================================================

-- NOTE: Indexes are now created by the Python migration script (migrate_clickhouse.py)
-- during table creation. No need to duplicate index creation here.

-- ============================================================================
-- SUCCESS
-- ============================================================================
-- Materialized views are now created and will automatically populate tables
-- with all NEW data arriving in otel_metrics_gauge.
-- ============================================================================
