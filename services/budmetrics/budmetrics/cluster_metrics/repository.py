"""Repository for cluster metrics data access.

This module encapsulates all ClickHouse query logic for cluster metrics,
providing a clean separation between data access and business logic.
"""

import time
from datetime import datetime
from typing import List, Optional, Tuple

from budmicroframe.commons.logging import get_logger

from ..commons.sql_validators import safe_sql_list
from ..observability.models import ClickHouseClient


logger = get_logger(__name__)


class ClusterMetricsRepository:
    """Repository for cluster metrics data access.

    Encapsulates all ClickHouse query logic for cluster metrics operations.
    Methods return raw query results (tuples/lists) which are then processed
    by the service layer into domain objects.
    """

    def __init__(self, client: ClickHouseClient):
        """Initialize repository with ClickHouse client.

        Args:
            client: Initialized ClickHouseClient instance
        """
        self.client = client

    async def get_cluster_summary(
        self,
        cluster_id: str,
        from_time: datetime,
        to_time: datetime,
    ) -> List[Tuple]:
        """Get cluster resource utilization summary from NodeMetrics table.

        Args:
            cluster_id: Cluster identifier
            from_time: Start time for metrics window
            to_time: End time for metrics window

        Returns:
            List of tuples containing aggregated cluster metrics:
            (cluster_id, cluster_name, node_count, total_cpu_cores,
             avg_cpu_usage_percent, max_cpu_usage_percent, total_memory_gb,
             used_memory_gb, avg_memory_usage_percent, max_memory_usage_percent,
             total_disk_gb, used_disk_gb, avg_disk_usage_percent,
             max_disk_usage_percent, avg_load_1, avg_load_5, avg_load_15, timestamp)
        """
        query = """
        SELECT
            cluster_id,
            anyLast(cluster_name) AS cluster_name,
            count(DISTINCT node_name) AS node_count,
            sum(cpu_cores) AS total_cpu_cores,
            avg(cpu_usage_percent) AS avg_cpu_usage_percent,
            max(cpu_usage_percent) AS max_cpu_usage_percent,
            sum(memory_total_bytes) / (1024 * 1024 * 1024) AS total_memory_gb,
            sum(memory_used_bytes) / (1024 * 1024 * 1024) AS used_memory_gb,
            avg(memory_usage_percent) AS avg_memory_usage_percent,
            max(memory_usage_percent) AS max_memory_usage_percent,
            sum(disk_total_bytes) / (1024 * 1024 * 1024) AS total_disk_gb,
            sum(disk_used_bytes) / (1024 * 1024 * 1024) AS used_disk_gb,
            avg(disk_usage_percent) AS avg_disk_usage_percent,
            max(disk_usage_percent) AS max_disk_usage_percent,
            avg(load_1) AS avg_load_1,
            avg(load_5) AS avg_load_5,
            avg(load_15) AS avg_load_15,
            max(ts) AS timestamp
        FROM metrics.NodeMetrics
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN %(from_time)s AND %(to_time)s
        GROUP BY cluster_id
        """

        return await self.client.execute_query(
            query,
            params={
                "cluster_id": cluster_id,
                "from_time": from_time,
                "to_time": to_time,
            },
        )

    async def get_node_metrics(
        self,
        cluster_id: str,
        from_time: datetime,
        to_time: datetime,
    ) -> List[Tuple]:
        """Get aggregated node-level metrics for a cluster.

        Args:
            cluster_id: Cluster identifier
            from_time: Start time for metrics window
            to_time: End time for metrics window

        Returns:
            List of tuples containing per-node metrics:
            (node_name, cpu_cores, cpu_usage_percent, memory_total_gb,
             memory_used_gb, memory_usage_percent, disk_total_gb, disk_used_gb,
             disk_usage_percent, load_1, load_5, load_15, network_receive_bytes_per_sec,
             network_transmit_bytes_per_sec, timestamp)
        """
        query = """
        SELECT
            node_name,
            avg(cpu_cores) AS cpu_cores,
            avg(cpu_usage_percent) AS cpu_usage_percent,
            avg(memory_total_bytes) / (1024 * 1024 * 1024) AS memory_total_gb,
            avg(memory_used_bytes) / (1024 * 1024 * 1024) AS memory_used_gb,
            avg(memory_usage_percent) AS memory_usage_percent,
            avg(disk_total_bytes) / (1024 * 1024 * 1024) AS disk_total_gb,
            avg(disk_used_bytes) / (1024 * 1024 * 1024) AS disk_used_gb,
            avg(disk_usage_percent) AS disk_usage_percent,
            avg(load_1) AS load_1,
            avg(load_5) AS load_5,
            avg(load_15) AS load_15,
            COALESCE(avg(network_receive_bytes_per_sec), 0) AS network_receive_bytes_per_sec,
            COALESCE(avg(network_transmit_bytes_per_sec), 0) AS network_transmit_bytes_per_sec,
            max(ts) AS timestamp
        FROM metrics.NodeMetrics
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN %(from_time)s AND %(to_time)s
        GROUP BY node_name
        ORDER BY node_name
        """

        return await self.client.execute_query(
            query,
            params={
                "cluster_id": cluster_id,
                "from_time": from_time,
                "to_time": to_time,
            },
        )

    async def get_node_network_timeseries(
        self,
        cluster_id: str,
        from_time: datetime,
        to_time: datetime,
    ) -> List[Tuple]:
        """Get network bandwidth time series data for all nodes.

        Args:
            cluster_id: Cluster identifier
            from_time: Start time for metrics window
            to_time: End time for metrics window

        Returns:
            List of tuples containing time series data:
            (node_name, time_bucket, total_bandwidth_bytes_per_sec)
        """
        query = """
        SELECT
            node_name,
            toUnixTimestamp(toStartOfFiveMinutes(ts)) AS time_bucket,
            COALESCE(avg(network_receive_bytes_per_sec), 0) +
                COALESCE(avg(network_transmit_bytes_per_sec), 0) AS total_bandwidth_bytes_per_sec
        FROM metrics.NodeMetrics
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN %(from_time)s AND %(to_time)s
        GROUP BY node_name, time_bucket
        ORDER BY node_name, time_bucket
        """

        return await self.client.execute_query(
            query,
            params={
                "cluster_id": cluster_id,
                "from_time": from_time,
                "to_time": to_time,
            },
        )

    async def get_pod_metrics(
        self,
        cluster_id: str,
        from_time: datetime,
        to_time: datetime,
        namespace: Optional[str] = None,
        limit: int = 100,
    ) -> List[Tuple]:
        """Get pod-level metrics for a cluster.

        Args:
            cluster_id: Cluster identifier
            from_time: Start time for metrics window
            to_time: End time for metrics window
            namespace: Optional namespace filter
            limit: Maximum number of pods to return

        Returns:
            List of tuples containing pod metrics:
            (namespace, pod_name, container_name, cpu_requests, cpu_limits,
             cpu_usage, memory_requests_mb, memory_limits_mb, memory_usage_mb,
             restarts, status, timestamp)
        """
        # Build query with optional namespace filter
        namespace_filter = ""
        params = {
            "cluster_id": cluster_id,
            "from_time": from_time,
            "to_time": to_time,
            "limit": limit,
        }
        if namespace:
            namespace_filter = "AND namespace = %(namespace)s"
            params["namespace"] = namespace

        query = f"""
        SELECT
            namespace,
            pod_name,
            container_name,
            avg(cpu_requests) AS cpu_requests,
            avg(cpu_limits) AS cpu_limits,
            avg(cpu_usage) AS cpu_usage,
            avg(memory_requests_bytes) / (1024 * 1024) AS memory_requests_mb,
            avg(memory_limits_bytes) / (1024 * 1024) AS memory_limits_mb,
            avg(memory_usage_bytes) / (1024 * 1024) AS memory_usage_mb,
            max(restarts) AS restarts,
            anyLast(status) AS status,
            max(ts) AS timestamp
        FROM metrics.PodMetrics
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN %(from_time)s AND %(to_time)s
          {namespace_filter}
        GROUP BY namespace, pod_name, container_name
        ORDER BY namespace, pod_name, container_name
        LIMIT %(limit)s
        """

        return await self.client.execute_query(query, params=params)

    async def get_gpu_metrics(
        self,
        cluster_id: str,
        from_time: datetime,
        to_time: datetime,
    ) -> List[Tuple]:
        """Get GPU metrics for a cluster.

        Args:
            cluster_id: Cluster identifier
            from_time: Start time for metrics window
            to_time: End time for metrics window

        Returns:
            List of tuples containing GPU metrics:
            (node_name, gpu_index, gpu_model, utilization_percent, memory_used_gb,
             memory_total_gb, temperature_celsius, power_watts, timestamp)
        """
        query = """
        SELECT
            node_name,
            gpu_index,
            anyLast(gpu_model) AS gpu_model,
            avg(utilization_percent) AS utilization_percent,
            avg(memory_used_bytes) / (1024 * 1024 * 1024) AS memory_used_gb,
            avg(memory_total_bytes) / (1024 * 1024 * 1024) AS memory_total_gb,
            avg(temperature_celsius) AS temperature_celsius,
            avg(power_watts) AS power_watts,
            max(ts) AS timestamp
        FROM metrics.GPUMetrics
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN %(from_time)s AND %(to_time)s
        GROUP BY node_name, gpu_index
        ORDER BY node_name, gpu_index
        """

        return await self.client.execute_query(
            query,
            params={
                "cluster_id": cluster_id,
                "from_time": from_time,
                "to_time": to_time,
            },
        )

    async def query_metrics(
        self,
        cluster_id: str,
        from_time: datetime,
        to_time: datetime,
        metric_names: Optional[List[str]] = None,
        aggregation: str = "avg",
        interval: str = "5m",
    ) -> List[Tuple]:
        """Execute custom metrics query for a cluster.

        Args:
            cluster_id: Cluster identifier
            from_time: Start time for metrics window
            to_time: End time for metrics window
            metric_names: Optional list of specific metrics to retrieve
            aggregation: Aggregation method (avg, max, min, sum)
            interval: Time interval for bucketing (1m, 5m, 15m, 1h, 1d)

        Returns:
            List of tuples containing time-series metrics:
            (metric_name, time_bucket, value)
        """
        # Build time bucketing based on interval
        interval_map = {
            "1m": "toStartOfMinute(ts)",
            "5m": "toStartOfFiveMinutes(ts)",
            "15m": "toStartOfFifteenMinutes(ts)",
            "1h": "toStartOfHour(ts)",
            "1d": "toStartOfDay(ts)",
        }
        time_bucket = interval_map.get(interval, "toStartOfFiveMinutes(ts)")

        # Build metric filter - values already validated by Pydantic schema
        metric_filter = ""
        if metric_names:
            metric_names_str = safe_sql_list(metric_names)
            metric_filter = f"AND metric_name IN ({metric_names_str})"

        # Build aggregation function
        agg_func = {
            "avg": "avg",
            "max": "max",
            "min": "min",
            "sum": "sum",
        }.get(aggregation, "avg")

        query = f"""
        SELECT
            metric_name,
            {time_bucket} AS time_bucket,
            {agg_func}(value) AS value
        FROM metrics.ClusterMetrics
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN %(from_time)s AND %(to_time)s
          {metric_filter}
        GROUP BY metric_name, time_bucket
        ORDER BY metric_name, time_bucket
        """

        return await self.client.execute_query(
            query,
            params={
                "cluster_id": cluster_id,
                "from_time": from_time,
                "to_time": to_time,
            },
        )

    async def aggregate_metrics(
        self,
        cluster_ids: List[str],
        metric_names: List[str],
        from_time: datetime,
        to_time: datetime,
        group_by: Optional[List[str]] = None,
        aggregation: str = "avg",
        interval: Optional[str] = None,
    ) -> Tuple[List[Tuple], float]:
        """Perform custom aggregation on cluster metrics.

        Args:
            cluster_ids: List of cluster identifiers
            metric_names: List of metrics to aggregate
            from_time: Start time for metrics window
            to_time: End time for metrics window
            group_by: Optional list of fields to group by
            aggregation: Aggregation method (avg, max, min, sum)
            interval: Optional time interval for bucketing

        Returns:
            Tuple of (results, execution_time_ms):
            - results: List of tuples containing aggregated metrics
            - execution_time_ms: Query execution time in milliseconds
        """
        start_time = time.time()

        # Build cluster filter - values already validated by Pydantic schema
        cluster_ids_str = safe_sql_list(cluster_ids)

        # Build metric filter - values already validated by Pydantic schema
        metric_names_str = safe_sql_list(metric_names)

        # Build group by clause - values already validated by Pydantic schema
        group_by_fields = ["metric_name"]
        if group_by:
            group_by_fields.extend(group_by)

        # Build aggregation function
        agg_func = {
            "avg": "avg",
            "max": "max",
            "min": "min",
            "sum": "sum",
        }.get(aggregation, "avg")

        # Build time bucketing if interval specified
        time_bucket_select = ""
        time_bucket_group = ""
        if interval:
            interval_map = {
                "1m": "toStartOfMinute(ts)",
                "5m": "toStartOfFiveMinutes(ts)",
                "15m": "toStartOfFifteenMinutes(ts)",
                "1h": "toStartOfHour(ts)",
                "1d": "toStartOfDay(ts)",
            }
            time_bucket_expr = interval_map.get(interval, "toStartOfFiveMinutes(ts)")
            time_bucket_select = f", {time_bucket_expr} AS time_bucket"
            time_bucket_group = ", time_bucket"
            group_by_fields.append("time_bucket")

        query = f"""
        SELECT
            cluster_id,
            metric_name
            {time_bucket_select},
            {agg_func}(value) AS value
        FROM metrics.ClusterMetrics
        WHERE cluster_id IN ({cluster_ids_str})
          AND metric_name IN ({metric_names_str})
          AND ts BETWEEN %(from_time)s AND %(to_time)s
        GROUP BY cluster_id, metric_name{time_bucket_group}
        ORDER BY cluster_id, metric_name{time_bucket_group}
        """

        result = await self.client.execute_query(
            query,
            params={
                "from_time": from_time,
                "to_time": to_time,
            },
        )

        execution_time_ms = (time.time() - start_time) * 1000
        return result, execution_time_ms

    async def get_cluster_health_metrics(
        self,
        cluster_id: str,
        from_time: datetime,
        to_time: datetime,
    ) -> List[Tuple]:
        """Get metrics for calculating cluster health status.

        Args:
            cluster_id: Cluster identifier
            from_time: Start time for metrics window
            to_time: End time for metrics window

        Returns:
            List of tuples containing health-related metrics
        """
        query = """
        SELECT
            avg(cpu_usage_percent) AS avg_cpu,
            max(cpu_usage_percent) AS max_cpu,
            avg(memory_usage_percent) AS avg_memory,
            max(memory_usage_percent) AS max_memory,
            avg(disk_usage_percent) AS avg_disk,
            max(disk_usage_percent) AS max_disk
        FROM metrics.NodeMetrics
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN %(from_time)s AND %(to_time)s
        """

        return await self.client.execute_query(
            query,
            params={
                "cluster_id": cluster_id,
                "from_time": from_time,
                "to_time": to_time,
            },
        )

    async def get_prometheus_gauge_metrics(
        self,
        cluster_id: str,
        from_time: datetime,
        to_time: datetime,
    ) -> List[Tuple]:
        """Get gauge metrics (memory, disk) for Prometheus format.

        Queries NodeMetrics materialized view for gauge-type metrics.
        Much faster than raw otel_metrics_gauge table.

        Args:
            cluster_id: Cluster identifier
            from_time: Start time for metrics window
            to_time: End time for metrics window

        Returns:
            List of tuples with columns: (cluster_id, node_instance, MetricName, avg_value)
        """
        query = """
        SELECT
            cluster_id,
            node_name AS node_instance,
            'node_memory_MemTotal_bytes' AS MetricName,
            avg(memory_total_bytes) AS avg_value
        FROM metrics.NodeMetrics FINAL
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN toDateTime(%(from_time)s) AND toDateTime(%(to_time)s)
        GROUP BY cluster_id, node_instance

        UNION ALL

        SELECT
            cluster_id,
            node_name AS node_instance,
            'node_memory_MemAvailable_bytes' AS MetricName,
            avg(memory_total_bytes - memory_used_bytes) AS avg_value
        FROM metrics.NodeMetrics FINAL
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN toDateTime(%(from_time)s) AND toDateTime(%(to_time)s)
        GROUP BY cluster_id, node_instance

        UNION ALL

        SELECT
            cluster_id,
            node_name AS node_instance,
            'node_filesystem_size_bytes' AS MetricName,
            avg(disk_total_bytes) AS avg_value
        FROM metrics.NodeMetrics FINAL
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN toDateTime(%(from_time)s) AND toDateTime(%(to_time)s)
        GROUP BY cluster_id, node_instance

        UNION ALL

        SELECT
            cluster_id,
            node_name AS node_instance,
            'node_filesystem_avail_bytes' AS MetricName,
            avg(disk_total_bytes - disk_used_bytes) AS avg_value
        FROM metrics.NodeMetrics FINAL
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN toDateTime(%(from_time)s) AND toDateTime(%(to_time)s)
        GROUP BY cluster_id, node_instance
        """

        return await self.client.execute_query(
            query,
            params={
                "cluster_id": cluster_id,
                "from_time": from_time,
                "to_time": to_time,
            },
        )

    async def get_prometheus_counter_metrics(
        self,
        cluster_id: str,
        from_time: datetime,
        to_time: datetime,
        time_interval_seconds: int,
    ) -> List[Tuple]:
        """Get counter metrics (CPU) for Prometheus format.

        Queries NodeMetrics materialized view for counter-type metrics.
        Converts cpu_usage_percent back to counter format for compatibility.

        Args:
            cluster_id: Cluster identifier
            from_time: Start time for metrics window
            to_time: End time for metrics window
            time_interval_seconds: Time interval in seconds for rate calculation

        Returns:
            List of tuples with columns: (cluster_id, node_instance, MetricName,
                                         value_delta, time_delta_seconds, cpu_cores)
        """
        query = """
        SELECT
            cluster_id,
            node_instance,
            'node_cpu_seconds_total' AS MetricName,
            -- Convert average cpu_usage_percent back to value_delta format
            -- value_delta = (avg_cpu_usage_percent / 100) * cpu_cores * time_interval_seconds
            -- This represents total CPU seconds accumulated over the period
            (avg_cpu_usage / 100) * cpu_cores * %(time_interval_seconds)s AS value_delta,
            %(time_interval_seconds)s AS time_delta_seconds,
            cpu_cores
        FROM (
            SELECT
                cluster_id,
                node_name AS node_instance,
                avg(cpu_usage_percent) AS avg_cpu_usage,
                any(cpu_cores) AS cpu_cores
            FROM metrics.NodeMetrics FINAL
            WHERE cluster_id = %(cluster_id)s
              AND ts BETWEEN toDateTime(%(from_time)s) AND toDateTime(%(to_time)s)
            GROUP BY cluster_id, node_instance
        )
        """

        return await self.client.execute_query(
            query,
            params={
                "cluster_id": cluster_id,
                "from_time": from_time,
                "to_time": to_time,
                "time_interval_seconds": time_interval_seconds,
            },
        )

    async def get_prometheus_network_metrics(
        self,
        cluster_id: str,
        from_time: datetime,
        to_time: datetime,
    ) -> List[Tuple]:
        """Get network metrics for Prometheus format.

        Queries NodeMetrics materialized view for network metrics.
        Network metrics are already RATES (bytes/second), not cumulative counters.

        Args:
            cluster_id: Cluster identifier
            from_time: Start time for metrics window
            to_time: End time for metrics window

        Returns:
            List of tuples with columns: (cluster_id, node_instance, MetricName,
                                         value_delta, time_delta_seconds)
        """
        query = """
        SELECT
            cluster_id,
            node_name AS node_instance,
            'container_network_receive_bytes_total' AS MetricName,
            avg(network_receive_bytes_per_sec) AS value_delta,
            1 AS time_delta_seconds
        FROM metrics.NodeMetrics FINAL
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN toDateTime(%(from_time)s) AND toDateTime(%(to_time)s)
        GROUP BY cluster_id, node_instance

        UNION ALL

        SELECT
            cluster_id,
            node_name AS node_instance,
            'container_network_transmit_bytes_total' AS MetricName,
            avg(network_transmit_bytes_per_sec) AS value_delta,
            1 AS time_delta_seconds
        FROM metrics.NodeMetrics FINAL
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN toDateTime(%(from_time)s) AND toDateTime(%(to_time)s)
        GROUP BY cluster_id, node_instance
        """

        return await self.client.execute_query(
            query,
            params={
                "cluster_id": cluster_id,
                "from_time": from_time,
                "to_time": to_time,
            },
        )

    async def get_prometheus_network_timeseries(
        self,
        cluster_id: str,
        from_time: datetime,
        to_time: datetime,
        interval: int,
    ) -> List[Tuple]:
        """Get network time-series metrics for Prometheus format.

        Queries NodeMetrics materialized view for network time series data.
        Used for graphing network bandwidth over time.

        Args:
            cluster_id: Cluster identifier
            from_time: Start time for metrics window
            to_time: End time for metrics window
            interval: Time bucket interval in seconds

        Returns:
            List of tuples with columns: (node_instance, MetricName, time_bucket,
                                         value_delta, time_delta_seconds)
        """
        query = """
        SELECT
            node_name AS node_instance,
            'container_network_receive_bytes_total' AS MetricName,
            toUnixTimestamp(toStartOfInterval(ts, INTERVAL %(interval)s SECOND)) AS time_bucket,
            avg(network_receive_bytes_per_sec) AS value_delta,
            1 AS time_delta_seconds
        FROM metrics.NodeMetrics FINAL
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN toDateTime(%(from_time)s) AND toDateTime(%(to_time)s)
        GROUP BY node_instance, MetricName, time_bucket

        UNION ALL

        SELECT
            node_name AS node_instance,
            'container_network_transmit_bytes_total' AS MetricName,
            toUnixTimestamp(toStartOfInterval(ts, INTERVAL %(interval)s SECOND)) AS time_bucket,
            avg(network_transmit_bytes_per_sec) AS value_delta,
            1 AS time_delta_seconds
        FROM metrics.NodeMetrics FINAL
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN toDateTime(%(from_time)s) AND toDateTime(%(to_time)s)
        GROUP BY node_instance, MetricName, time_bucket

        ORDER BY node_instance, MetricName, time_bucket
        """

        return await self.client.execute_query(
            query,
            params={
                "cluster_id": cluster_id,
                "from_time": from_time,
                "to_time": to_time,
                "interval": interval,
            },
        )

    async def get_prometheus_prev_gauge_metrics(
        self,
        cluster_id: str,
        from_time: datetime,
        to_time: datetime,
    ) -> List[Tuple]:
        """Get previous period gauge metrics for change percentage calculation.

        Queries NodeMetrics materialized view for gauge-type metrics
        from a previous time period for comparison.

        Args:
            cluster_id: Cluster identifier
            from_time: Start time for previous period metrics window
            to_time: End time for previous period metrics window

        Returns:
            List of tuples with columns: (node_instance, MetricName, avg_value)
        """
        query = """
        SELECT
            node_name AS node_instance,
            'node_memory_MemTotal_bytes' AS MetricName,
            avg(memory_total_bytes) AS avg_value
        FROM metrics.NodeMetrics FINAL
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN toDateTime(%(from_time)s) AND toDateTime(%(to_time)s)
        GROUP BY node_instance

        UNION ALL

        SELECT
            node_name AS node_instance,
            'node_memory_MemAvailable_bytes' AS MetricName,
            avg(memory_total_bytes - memory_used_bytes) AS avg_value
        FROM metrics.NodeMetrics FINAL
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN toDateTime(%(from_time)s) AND toDateTime(%(to_time)s)
        GROUP BY node_instance

        UNION ALL

        SELECT
            node_name AS node_instance,
            'node_filesystem_size_bytes' AS MetricName,
            avg(disk_total_bytes) AS avg_value
        FROM metrics.NodeMetrics FINAL
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN toDateTime(%(from_time)s) AND toDateTime(%(to_time)s)
        GROUP BY node_instance

        UNION ALL

        SELECT
            node_name AS node_instance,
            'node_filesystem_avail_bytes' AS MetricName,
            avg(disk_total_bytes - disk_used_bytes) AS avg_value
        FROM metrics.NodeMetrics FINAL
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN toDateTime(%(from_time)s) AND toDateTime(%(to_time)s)
        GROUP BY node_instance
        """

        return await self.client.execute_query(
            query,
            params={
                "cluster_id": cluster_id,
                "from_time": from_time,
                "to_time": to_time,
            },
        )

    async def get_prometheus_prev_counter_metrics(
        self,
        cluster_id: str,
        from_time: datetime,
        to_time: datetime,
        time_interval_seconds: int,
    ) -> List[Tuple]:
        """Get previous period counter metrics for change percentage calculation.

        Queries NodeMetrics materialized view for counter-type metrics
        from a previous time period for comparison.

        Args:
            cluster_id: Cluster identifier
            from_time: Start time for previous period metrics window
            to_time: End time for previous period metrics window
            time_interval_seconds: Time interval in seconds for rate calculation

        Returns:
            List of tuples with columns: (node_instance, MetricName, value_delta,
                                         time_delta_seconds, cpu_cores)
        """
        query = """
        SELECT
            node_instance,
            'node_cpu_seconds_total' AS MetricName,
            -- Convert average cpu_usage_percent back to value_delta format
            (avg_cpu_usage / 100) * cpu_cores * %(time_interval_seconds)s AS value_delta,
            %(time_interval_seconds)s AS time_delta_seconds,
            cpu_cores
        FROM (
            SELECT
                node_name AS node_instance,
                avg(cpu_usage_percent) AS avg_cpu_usage,
                any(cpu_cores) AS cpu_cores
            FROM metrics.NodeMetrics FINAL
            WHERE cluster_id = %(cluster_id)s
              AND ts BETWEEN toDateTime(%(from_time)s) AND toDateTime(%(to_time)s)
            GROUP BY node_instance
        )
        """

        return await self.client.execute_query(
            query,
            params={
                "cluster_id": cluster_id,
                "from_time": from_time,
                "to_time": to_time,
                "time_interval_seconds": time_interval_seconds,
            },
        )

    async def get_prometheus_prev_network_metrics(
        self,
        cluster_id: str,
        from_time: datetime,
        to_time: datetime,
    ) -> List[Tuple]:
        """Get previous period network metrics for change percentage calculation.

        Queries NodeMetrics materialized view for network metrics
        from a previous time period for comparison.

        Args:
            cluster_id: Cluster identifier
            from_time: Start time for previous period metrics window
            to_time: End time for previous period metrics window

        Returns:
            List of tuples with columns: (node_instance, MetricName, value_delta,
                                         time_delta_seconds)
        """
        query = """
        SELECT
            node_name AS node_instance,
            'container_network_receive_bytes_total' AS MetricName,
            avg(network_receive_bytes_per_sec) AS value_delta,
            1 AS time_delta_seconds
        FROM metrics.NodeMetrics FINAL
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN toDateTime(%(from_time)s) AND toDateTime(%(to_time)s)
        GROUP BY node_instance

        UNION ALL

        SELECT
            node_name AS node_instance,
            'container_network_transmit_bytes_total' AS MetricName,
            avg(network_transmit_bytes_per_sec) AS value_delta,
            1 AS time_delta_seconds
        FROM metrics.NodeMetrics FINAL
        WHERE cluster_id = %(cluster_id)s
          AND ts BETWEEN toDateTime(%(from_time)s) AND toDateTime(%(to_time)s)
        GROUP BY node_instance
        """

        return await self.client.execute_query(
            query,
            params={
                "cluster_id": cluster_id,
                "from_time": from_time,
                "to_time": to_time,
            },
        )

    async def get_cluster_name(self, cluster_id: str, table: str = "NodeMetrics") -> Optional[str]:
        """Get cluster name from metrics table.

        Args:
            cluster_id: Cluster identifier
            table: Table name to query (NodeMetrics, PodMetrics, ClusterMetrics, etc.)

        Returns:
            Cluster name if found, None otherwise
        """
        query = f"""
        SELECT anyLast(cluster_name)
        FROM metrics.{table}
        WHERE cluster_id = %(cluster_id)s
        """

        result = await self.client.execute_query(query, params={"cluster_id": cluster_id})
        return result[0][0] if result and result[0][0] else None
