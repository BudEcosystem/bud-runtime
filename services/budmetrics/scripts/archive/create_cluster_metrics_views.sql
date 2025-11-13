-- Views for transforming OTel raw metrics to optimized cluster metrics format
-- Run this after OTel Collector has created the otel_metrics tables

-- Note: These views work with the actual schema from our OTel Collector setup
-- Data is stored in otel_metrics_gauge, otel_metrics_sum tables

-- First, create the target tables that the views will query

-- Table for node-level metrics
CREATE TABLE IF NOT EXISTS metrics.NodeMetrics (
    ts DateTime64(3),
    cluster_id String,
    cluster_name String,
    node_name String,
    cpu_cores Float64,
    cpu_usage_percent Float64,
    memory_total_bytes Float64,
    memory_used_bytes Float64,
    memory_usage_percent Float64,
    disk_total_bytes Float64,
    disk_used_bytes Float64,
    disk_usage_percent Float64,
    load_1 Float64,
    load_5 Float64,
    load_15 Float64
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)
ORDER BY (cluster_id, node_name, ts)
TTL ts + INTERVAL 90 DAY;

-- Table for pod/container metrics
CREATE TABLE IF NOT EXISTS metrics.PodMetrics (
    ts DateTime64(3),
    cluster_id String,
    cluster_name String,
    namespace String,
    pod_name String,
    container_name String,
    cpu_requests Float64,
    cpu_limits Float64,
    cpu_usage Float64,
    memory_requests_bytes Float64,
    memory_limits_bytes Float64,
    memory_usage_bytes Float64,
    restarts Int32,
    status String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)
ORDER BY (cluster_id, namespace, pod_name, ts)
TTL ts + INTERVAL 30 DAY;

-- Table for GPU metrics (when available)
CREATE TABLE IF NOT EXISTS metrics.GPUMetrics (
    ts DateTime64(3),
    cluster_id String,
    cluster_name String,
    node_name String,
    gpu_index UInt8,
    gpu_model String,
    utilization_percent Float64,
    memory_used_bytes Float64,
    memory_total_bytes Float64,
    temperature_celsius Float64,
    power_watts Float64
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)
ORDER BY (cluster_id, node_name, gpu_index, ts)
TTL ts + INTERVAL 30 DAY;

-- Generic table for all cluster metrics
CREATE TABLE IF NOT EXISTS metrics.ClusterMetrics (
    ts DateTime64(3),
    cluster_id String,
    cluster_name String,
    cluster_platform String,
    metric_name String,
    value Float64,
    labels Map(String, String)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)
ORDER BY (cluster_id, metric_name, ts)
TTL ts + INTERVAL 90 DAY;

-- Now create views that transform OTel data into these tables
-- Note: Using regular views first, can convert to materialized views later if needed

-- View for node metrics aggregation
CREATE VIEW IF NOT EXISTS metrics.v_node_metrics AS
SELECT
    TimeUnix AS ts,
    ResourceAttributes['cluster_id'] AS cluster_id,
    ResourceAttributes['cluster_name'] AS cluster_name,
    splitByChar(':', Attributes['instance'])[1] AS node_name,
    -- CPU metrics (counting distinct CPU cores from node_cpu_seconds_total)
    countDistinctIf(Attributes['cpu'], MetricName = 'node_cpu_seconds_total') AS cpu_cores,
    -- For CPU usage, we need to calculate from node_cpu_seconds_total rate
    -- This is a simplified version - actual CPU usage calculation requires rate calculation
    100 - (avgIf(Value * 100, MetricName = 'node_cpu_seconds_total' AND Attributes['mode'] = 'idle')) AS cpu_usage_percent,
    -- Memory metrics
    maxIf(Value, MetricName = 'node_memory_MemTotal_bytes') AS memory_total_bytes,
    maxIf(Value, MetricName = 'node_memory_MemTotal_bytes') - maxIf(Value, MetricName = 'node_memory_MemAvailable_bytes') AS memory_used_bytes,
    ((maxIf(Value, MetricName = 'node_memory_MemTotal_bytes') - maxIf(Value, MetricName = 'node_memory_MemAvailable_bytes')) /
     nullIf(maxIf(Value, MetricName = 'node_memory_MemTotal_bytes'), 0)) * 100 AS memory_usage_percent,
    -- Disk metrics (summing all non-tmpfs filesystems)
    sumIf(Value, MetricName = 'node_filesystem_size_bytes' AND Attributes['fstype'] NOT IN ('tmpfs', 'devtmpfs')) AS disk_total_bytes,
    sumIf(Value, MetricName = 'node_filesystem_size_bytes' AND Attributes['fstype'] NOT IN ('tmpfs', 'devtmpfs')) -
    sumIf(Value, MetricName = 'node_filesystem_avail_bytes' AND Attributes['fstype'] NOT IN ('tmpfs', 'devtmpfs')) AS disk_used_bytes,
    ((sumIf(Value, MetricName = 'node_filesystem_size_bytes' AND Attributes['fstype'] NOT IN ('tmpfs', 'devtmpfs')) -
      sumIf(Value, MetricName = 'node_filesystem_avail_bytes' AND Attributes['fstype'] NOT IN ('tmpfs', 'devtmpfs'))) /
     nullIf(sumIf(Value, MetricName = 'node_filesystem_size_bytes' AND Attributes['fstype'] NOT IN ('tmpfs', 'devtmpfs')), 0)) * 100 AS disk_usage_percent,
    -- Load averages
    avgIf(Value, MetricName = 'node_load1') AS load_1,
    avgIf(Value, MetricName = 'node_load5') AS load_5,
    avgIf(Value, MetricName = 'node_load15') AS load_15
FROM metrics.otel_metrics_gauge
WHERE MetricName IN (
    'node_cpu_seconds_total',
    'node_memory_MemTotal_bytes',
    'node_memory_MemAvailable_bytes',
    'node_filesystem_size_bytes',
    'node_filesystem_avail_bytes',
    'node_load1',
    'node_load5',
    'node_load15'
)
  AND ResourceAttributes['cluster_id'] IS NOT NULL
  AND Attributes['instance'] IS NOT NULL
GROUP BY ts, cluster_id, cluster_name, node_name;

-- View for pod/container metrics
CREATE VIEW IF NOT EXISTS metrics.v_pod_metrics AS
SELECT
    TimeUnix AS ts,
    ResourceAttributes['cluster_id'] AS cluster_id,
    ResourceAttributes['cluster_name'] AS cluster_name,
    Attributes['namespace'] AS namespace,
    Attributes['pod'] AS pod_name,
    Attributes['container'] AS container_name,
    -- Resource requests/limits
    maxIf(Value, MetricName = 'kube_pod_container_resource_requests' AND Attributes['resource'] = 'cpu') AS cpu_requests,
    maxIf(Value, MetricName = 'kube_pod_container_resource_limits' AND Attributes['resource'] = 'cpu') AS cpu_limits,
    maxIf(Value, MetricName = 'kube_pod_container_resource_requests' AND Attributes['resource'] = 'memory') AS memory_requests_bytes,
    maxIf(Value, MetricName = 'kube_pod_container_resource_limits' AND Attributes['resource'] = 'memory') AS memory_limits_bytes,
    -- Actual usage
    avgIf(Value, MetricName = 'container_cpu_usage_seconds_total') AS cpu_usage,
    avgIf(Value, MetricName = 'container_memory_working_set_bytes') AS memory_usage_bytes,
    -- Restarts
    maxIf(Value, MetricName = 'kube_pod_container_status_restarts_total') AS restarts,
    -- Status (simplified - extracting from phase)
    CASE
        WHEN maxIf(Value, MetricName = 'kube_pod_status_phase' AND Attributes['phase'] = 'Running') = 1 THEN 'Running'
        WHEN maxIf(Value, MetricName = 'kube_pod_status_phase' AND Attributes['phase'] = 'Pending') = 1 THEN 'Pending'
        WHEN maxIf(Value, MetricName = 'kube_pod_status_phase' AND Attributes['phase'] = 'Failed') = 1 THEN 'Failed'
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
  AND Attributes['pod'] IS NOT NULL
GROUP BY ts, cluster_id, cluster_name, namespace, pod_name, container_name;

-- View for GPU metrics (when available)
CREATE VIEW IF NOT EXISTS metrics.v_gpu_metrics AS
SELECT
    TimeUnix AS ts,
    ResourceAttributes['cluster_id'] AS cluster_id,
    ResourceAttributes['cluster_name'] AS cluster_name,
    Attributes['node'] AS node_name,
    toUInt8OrZero(Attributes['gpu']) AS gpu_index,
    Attributes['gpu_model'] AS gpu_model,
    -- GPU utilization and memory
    avgIf(Value, MetricName = 'DCGM_FI_DEV_GPU_UTIL') AS utilization_percent,
    maxIf(Value, MetricName = 'DCGM_FI_DEV_FB_USED') * 1024 * 1024 AS memory_used_bytes,
    (maxIf(Value, MetricName = 'DCGM_FI_DEV_FB_USED') + maxIf(Value, MetricName = 'DCGM_FI_DEV_FB_FREE')) * 1024 * 1024 AS memory_total_bytes,
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
GROUP BY ts, cluster_id, cluster_name, node_name, gpu_index, gpu_model;

-- Generic view for all cluster metrics (for raw metric storage and custom queries)
CREATE VIEW IF NOT EXISTS metrics.v_cluster_metrics AS
SELECT
    TimeUnix AS ts,
    ResourceAttributes['cluster_id'] AS cluster_id,
    ResourceAttributes['cluster_name'] AS cluster_name,
    ResourceAttributes['cluster_platform'] AS cluster_platform,
    MetricName AS metric_name,
    Value AS value,
    Attributes AS labels
FROM metrics.otel_metrics_gauge
WHERE ResourceAttributes['cluster_id'] IS NOT NULL;

-- Create materialized views for better performance
-- These will pre-aggregate data at 5-minute intervals

CREATE MATERIALIZED VIEW IF NOT EXISTS metrics.mv_node_metrics_5m
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(ts)
ORDER BY (cluster_id, node_name, ts)
TTL ts + INTERVAL 30 DAY
AS SELECT
    toStartOfFiveMinutes(TimeUnix) AS ts,
    ResourceAttributes['cluster_id'] AS cluster_id,
    ResourceAttributes['cluster_name'] AS cluster_name,
    splitByChar(':', Attributes['instance'])[1] AS node_name,
    -- Averages for the 5-minute window
    avg(countDistinctIf(Attributes['cpu'], MetricName = 'node_cpu_seconds_total')) AS cpu_cores,
    avg(100 - avgIf(Value * 100, MetricName = 'node_cpu_seconds_total' AND Attributes['mode'] = 'idle')) AS cpu_usage_percent,
    avg(maxIf(Value, MetricName = 'node_memory_MemTotal_bytes')) AS memory_total_bytes,
    avg(maxIf(Value, MetricName = 'node_memory_MemTotal_bytes') - maxIf(Value, MetricName = 'node_memory_MemAvailable_bytes')) AS memory_used_bytes,
    avg(((maxIf(Value, MetricName = 'node_memory_MemTotal_bytes') - maxIf(Value, MetricName = 'node_memory_MemAvailable_bytes')) /
         nullIf(maxIf(Value, MetricName = 'node_memory_MemTotal_bytes'), 0)) * 100) AS memory_usage_percent,
    avg(sumIf(Value, MetricName = 'node_filesystem_size_bytes')) AS disk_total_bytes,
    avg(sumIf(Value, MetricName = 'node_filesystem_size_bytes') - sumIf(Value, MetricName = 'node_filesystem_avail_bytes')) AS disk_used_bytes,
    avg(((sumIf(Value, MetricName = 'node_filesystem_size_bytes') - sumIf(Value, MetricName = 'node_filesystem_avail_bytes')) /
         nullIf(sumIf(Value, MetricName = 'node_filesystem_size_bytes'), 0)) * 100) AS disk_usage_percent,
    avg(avgIf(Value, MetricName = 'node_load1')) AS load_1,
    avg(avgIf(Value, MetricName = 'node_load5')) AS load_5,
    avg(avgIf(Value, MetricName = 'node_load15')) AS load_15
FROM metrics.otel_metrics_gauge
WHERE MetricName IN (
    'node_cpu_seconds_total',
    'node_memory_MemTotal_bytes',
    'node_memory_MemAvailable_bytes',
    'node_filesystem_size_bytes',
    'node_filesystem_avail_bytes',
    'node_load1',
    'node_load5',
    'node_load15'
)
  AND ResourceAttributes['cluster_id'] IS NOT NULL
  AND Attributes['instance'] IS NOT NULL
GROUP BY
    toStartOfFiveMinutes(TimeUnix),
    ResourceAttributes['cluster_id'],
    ResourceAttributes['cluster_name'],
    splitByChar(':', Attributes['instance'])[1];

-- Add indexes for better query performance
ALTER TABLE metrics.NodeMetrics ADD INDEX IF NOT EXISTS idx_cluster_node_time (cluster_id, node_name, ts) TYPE minmax GRANULARITY 1;
ALTER TABLE metrics.PodMetrics ADD INDEX IF NOT EXISTS idx_cluster_ns_pod_time (cluster_id, namespace, pod_name, ts) TYPE minmax GRANULARITY 1;
ALTER TABLE metrics.GPUMetrics ADD INDEX IF NOT EXISTS idx_cluster_gpu_time (cluster_id, node_name, gpu_index, ts) TYPE minmax GRANULARITY 1;
ALTER TABLE metrics.ClusterMetrics ADD INDEX IF NOT EXISTS idx_cluster_metric_time (cluster_id, metric_name, ts) TYPE minmax GRANULARITY 1;
