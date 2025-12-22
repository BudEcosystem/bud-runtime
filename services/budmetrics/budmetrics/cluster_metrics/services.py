"""Service layer for cluster metrics business logic.

This module contains the ClusterMetricsService class which orchestrates
data access via the repository and processes results into domain objects.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from budmicroframe.commons.logging import get_logger

from .repository import ClusterMetricsRepository
from .schemas import (
    BudAppClusterSummaryMetrics,
    BudAppCpuMetrics,
    BudAppMemoryMetrics,
    BudAppNetworkBandwidthMetrics,
    BudAppNetworkMetrics,
    BudAppNetworkOutMetrics,
    BudAppNodeMetrics,
    BudAppStorageMetrics,
    ClusterGPUMetricsResponse,
    ClusterGPUSummary,
    ClusterHealthStatus,
    ClusterMetricsQuery,
    ClusterMetricsResponse,
    ClusterResourceSummary,
    GPUDeviceResponse,
    GPUMetricsResponse,
    GPUMetricsSummary,
    GPUTimeSeriesResponse,
    HAMISliceResponse,
    MetricsAggregationRequest,
    MetricsAggregationResponse,
    MetricsTimeSeries,
    NetworkTimeSeriesPoint,
    NodeGPUMetricsResponse,
    NodeGPUSummary,
    NodeGPUSummaryItem,
    NodeMetricsResponse,
    NodeMetricsSummary,
    PodMetricsResponse,
    PodMetricsSummary,
    PrometheusCompatibleMetricsResponse,
    SliceActivityItem,
    TimeSeriesPoint,
)


logger = get_logger(__name__)


class ClusterMetricsService:
    """Service for cluster metrics business logic.

    Orchestrates data access, result processing, and response formatting.
    Separates business logic from data access and API layers.
    """

    def __init__(self, repository: ClusterMetricsRepository):
        """Initialize service with repository.

        Args:
            repository: ClusterMetricsRepository instance for data access
        """
        self.repository = repository

    async def get_cluster_summary(
        self,
        cluster_id: str,
        from_time: datetime,
        to_time: datetime,
    ) -> ClusterResourceSummary:
        """Get cluster resource utilization summary.

        Args:
            cluster_id: Cluster identifier
            from_time: Start time for metrics window
            to_time: End time for metrics window

        Returns:
            ClusterResourceSummary with aggregated cluster metrics

        Raises:
            ValueError: If no metrics found for cluster
        """
        result = await self.repository.get_cluster_summary(cluster_id, from_time, to_time)

        if not result:
            raise ValueError(f"No metrics found for cluster {cluster_id}")

        row = result[0]
        return ClusterResourceSummary(
            cluster_id=row[0],
            cluster_name=row[1] or "Unknown",
            node_count=row[2],
            total_cpu_cores=row[3],
            avg_cpu_usage_percent=row[4],
            max_cpu_usage_percent=row[5],
            total_memory_gb=row[6],
            used_memory_gb=row[7],
            avg_memory_usage_percent=row[8],
            max_memory_usage_percent=row[9],
            total_disk_gb=row[10],
            used_disk_gb=row[11],
            avg_disk_usage_percent=row[12],
            max_disk_usage_percent=row[13],
            avg_load_1=row[14],
            avg_load_5=row[15],
            avg_load_15=row[16],
            timestamp=row[17],
        )

    async def get_node_metrics(
        self,
        cluster_id: str,
        from_time: datetime,
        to_time: datetime,
    ) -> NodeMetricsResponse:
        """Get node-level metrics with network time series.

        Args:
            cluster_id: Cluster identifier
            from_time: Start time for metrics window
            to_time: End time for metrics window

        Returns:
            NodeMetricsResponse with node metrics and time series data
        """
        # Execute queries in parallel for better performance
        result, timeseries_result, gpu_result, cluster_name = await asyncio.gather(
            self.repository.get_node_metrics(cluster_id, from_time, to_time),
            self.repository.get_node_network_timeseries(cluster_id, from_time, to_time),
            self.repository.get_node_gpu_metrics(cluster_id),
            self.repository.get_cluster_name(cluster_id, "NodeMetrics"),
        )

        # Build GPU metrics per node
        # (node_name, gpu_count, avg_gpu_utilization_percent, avg_memory_utilization_percent)
        # Note: HAMIGPUMetrics uses hostname (e.g., "netweb") while NodeMetrics uses IP (e.g., "172.20.20.31")
        # We store by hostname and also compute cluster-level aggregates for fallback
        node_gpu_metrics: Dict[str, Dict[str, float]] = {}
        cluster_gpu_totals = {"gpu_count": 0, "gpu_util_sum": 0.0, "mem_util_sum": 0.0, "node_count": 0}
        for row in gpu_result:
            node_name = row[0]
            gpu_count = int(row[1] or 0)
            gpu_util = float(row[2] or 0)
            mem_util = float(row[3] or 0)
            node_gpu_metrics[node_name] = {
                "gpu_count": gpu_count,
                "gpu_utilization_percent": gpu_util,
                "gpu_memory_utilization_percent": mem_util,
            }
            # Aggregate for cluster-level fallback
            cluster_gpu_totals["gpu_count"] += gpu_count
            cluster_gpu_totals["gpu_util_sum"] += gpu_util * gpu_count
            cluster_gpu_totals["mem_util_sum"] += mem_util * gpu_count
            cluster_gpu_totals["node_count"] += 1

        # Compute cluster-level averages for fallback when node names don't match
        cluster_gpu_avg = {}
        if cluster_gpu_totals["gpu_count"] > 0:
            cluster_gpu_avg = {
                "gpu_count": cluster_gpu_totals["gpu_count"],
                "gpu_utilization_percent": cluster_gpu_totals["gpu_util_sum"] / cluster_gpu_totals["gpu_count"],
                "gpu_memory_utilization_percent": cluster_gpu_totals["mem_util_sum"] / cluster_gpu_totals["gpu_count"],
            }

        # Build time series data per node
        node_timeseries: Dict[str, List[NetworkTimeSeriesPoint]] = {}
        for row in timeseries_result:
            node_name = row[0]
            timestamp = row[1]
            bytes_per_sec = row[2]
            # Convert bytes/sec to Mbps: (bytes/sec * 8) / 1,000,000
            mbps = round((bytes_per_sec * 8) / 1_000_000, 2)

            if node_name not in node_timeseries:
                node_timeseries[node_name] = []

            node_timeseries[node_name].append(NetworkTimeSeriesPoint(timestamp=timestamp, mbps=mbps))

        # Build node metrics with time series and GPU data
        nodes = []
        for row in result:
            node_name = row[0]
            # Try exact match first, then fallback to cluster-level GPU data
            # (HAMIGPUMetrics uses hostname while NodeMetrics uses IP)
            gpu_data = node_gpu_metrics.get(node_name) or cluster_gpu_avg
            nodes.append(
                NodeMetricsSummary(
                    node_name=node_name,
                    cpu_cores=row[1],
                    cpu_usage_percent=row[2],
                    memory_total_gb=row[3],
                    memory_used_gb=row[4],
                    memory_usage_percent=row[5],
                    disk_total_gb=row[6],
                    disk_used_gb=row[7],
                    disk_usage_percent=row[8],
                    load_1=row[9],
                    load_5=row[10],
                    load_15=row[11],
                    network_receive_bytes_per_sec=row[12],
                    network_transmit_bytes_per_sec=row[13],
                    network_bandwidth_time_series=node_timeseries.get(node_name, []),
                    gpu_count=gpu_data.get("gpu_count", 0),
                    gpu_utilization_percent=gpu_data.get("gpu_utilization_percent", 0.0),
                    gpu_memory_utilization_percent=gpu_data.get("gpu_memory_utilization_percent", 0.0),
                    timestamp=row[14],
                )
            )

        return NodeMetricsResponse(
            cluster_id=cluster_id,
            cluster_name=cluster_name,
            nodes=nodes,
            timestamp=datetime.utcnow(),
        )

    async def get_pod_metrics(
        self,
        cluster_id: str,
        from_time: datetime,
        to_time: datetime,
        namespace: Optional[str] = None,
        limit: int = 100,
    ) -> PodMetricsResponse:
        """Get pod-level metrics for a cluster.

        Args:
            cluster_id: Cluster identifier
            from_time: Start time for metrics window
            to_time: End time for metrics window
            namespace: Optional namespace filter
            limit: Maximum number of pods to return

        Returns:
            PodMetricsResponse with pod metrics
        """
        result, cluster_name = await asyncio.gather(
            self.repository.get_pod_metrics(cluster_id, from_time, to_time, namespace, limit),
            self.repository.get_cluster_name(cluster_id, "PodMetrics"),
        )

        pods = []
        for row in result:
            pods.append(
                PodMetricsSummary(
                    namespace=row[0],
                    pod_name=row[1],
                    container_name=row[2],
                    cpu_requests=row[3],
                    cpu_limits=row[4],
                    cpu_usage=row[5],
                    memory_requests_mb=row[6],
                    memory_limits_mb=row[7],
                    memory_usage_mb=row[8],
                    restarts=row[9],
                    status=row[10],
                    timestamp=row[11],
                )
            )

        return PodMetricsResponse(
            cluster_id=cluster_id,
            cluster_name=cluster_name,
            namespace=namespace,
            pods=pods,
            total_pods=len(pods),
            timestamp=datetime.utcnow(),
        )

    async def get_gpu_metrics(
        self,
        cluster_id: str,
        from_time: datetime,
        to_time: datetime,
    ) -> GPUMetricsResponse:
        """Get GPU metrics for a cluster.

        Args:
            cluster_id: Cluster identifier
            from_time: Start time for metrics window
            to_time: End time for metrics window

        Returns:
            GPUMetricsResponse with GPU metrics
        """
        result, cluster_name = await asyncio.gather(
            self.repository.get_gpu_metrics(cluster_id, from_time, to_time),
            self.repository.get_cluster_name(cluster_id, "GPUMetrics"),
        )

        gpus = []
        for row in result:
            gpus.append(
                GPUMetricsSummary(
                    node_name=row[0],
                    gpu_index=row[1],
                    gpu_model=row[2],
                    utilization_percent=row[3],
                    memory_used_gb=row[4],
                    memory_total_gb=row[5],
                    temperature_celsius=row[6],
                    power_watts=row[7],
                    timestamp=row[8],
                )
            )

        return GPUMetricsResponse(
            cluster_id=cluster_id,
            cluster_name=cluster_name,
            gpus=gpus,
            total_gpus=len(gpus),
            timestamp=datetime.utcnow(),
        )

    async def query_metrics(
        self,
        request: ClusterMetricsQuery,
    ) -> ClusterMetricsResponse:
        """Execute custom metrics query for a cluster.

        Args:
            request: Query parameters

        Returns:
            ClusterMetricsResponse with time-series metrics
        """
        result, cluster_name = await asyncio.gather(
            self.repository.query_metrics(
                request.cluster_id,
                request.from_time,
                request.to_time,
                request.metric_names,
                request.aggregation or "avg",
                request.interval or "5m",
            ),
            self.repository.get_cluster_name(request.cluster_id, "ClusterMetrics"),
        )

        # Group results by metric name
        metrics_data: Dict[str, Dict[str, List]] = {}
        for row in result:
            metric_name = row[0]
            timestamp = row[1]
            value = row[2]

            if metric_name not in metrics_data:
                metrics_data[metric_name] = {"timestamps": [], "values": []}

            metrics_data[metric_name]["timestamps"].append(timestamp)
            metrics_data[metric_name]["values"].append(value)

        # Convert to response format
        metrics = []
        for metric_name, data in metrics_data.items():
            metrics.append(
                MetricsTimeSeries(
                    metric_name=metric_name,
                    timestamps=data["timestamps"],
                    values=data["values"],
                )
            )

        return ClusterMetricsResponse(
            cluster_id=request.cluster_id,
            cluster_name=cluster_name,
            from_time=request.from_time,
            to_time=request.to_time,
            metrics=metrics,
        )

    async def aggregate_metrics(
        self,
        request: MetricsAggregationRequest,
    ) -> MetricsAggregationResponse:
        """Perform custom aggregation on cluster metrics.

        Args:
            request: Aggregation parameters

        Returns:
            MetricsAggregationResponse with aggregated results and execution time
        """
        result, execution_time_ms = await self.repository.aggregate_metrics(
            request.cluster_ids,
            request.metric_names,
            request.from_time,
            request.to_time,
            request.group_by,
            request.aggregation,
            request.interval,
        )

        # Convert result tuples to dictionaries
        results = []
        for row in result:
            row_dict: Dict[str, any] = {
                "cluster_id": row[0],
                "metric_name": row[1],
            }
            # Handle optional time bucket
            if request.interval:
                row_dict["time_bucket"] = row[2]
                row_dict["value"] = row[3]
            else:
                row_dict["value"] = row[2]
            results.append(row_dict)

        return MetricsAggregationResponse(
            query=request,
            results=results,
            row_count=len(results),
            execution_time_ms=execution_time_ms,
        )

    async def get_cluster_health(
        self,
        cluster_id: str,
    ) -> ClusterHealthStatus:
        """Get health status of a cluster based on metrics analysis.

        Args:
            cluster_id: Cluster identifier

        Returns:
            ClusterHealthStatus with health analysis and recommendations
        """
        # Get recent cluster summary (last 15 minutes)
        from_time = datetime.utcnow() - timedelta(minutes=15)
        to_time = datetime.utcnow()

        summary = await self.get_cluster_summary(cluster_id, from_time, to_time)

        # Analyze metrics for health status
        issues = []
        recommendations = []
        status = "healthy"

        # CPU checks
        if summary.avg_cpu_usage_percent > 80:
            status = "critical"
            issues.append(f"High CPU usage: {summary.avg_cpu_usage_percent:.1f}%")
            recommendations.append("Consider scaling up CPU resources or adding more nodes")
        elif summary.avg_cpu_usage_percent > 70:
            status = "warning" if status == "healthy" else status
            issues.append(f"Elevated CPU usage: {summary.avg_cpu_usage_percent:.1f}%")
            recommendations.append("Monitor CPU usage trends")

        # Memory checks
        if summary.avg_memory_usage_percent > 90:
            status = "critical"
            issues.append(f"Critical memory usage: {summary.avg_memory_usage_percent:.1f}%")
            recommendations.append("Immediate action required: scale memory or reduce workload")
        elif summary.avg_memory_usage_percent > 80:
            status = "warning" if status == "healthy" else status
            issues.append(f"High memory usage: {summary.avg_memory_usage_percent:.1f}%")
            recommendations.append("Consider increasing memory allocation")

        # Disk checks
        if summary.avg_disk_usage_percent > 90:
            status = "critical"
            issues.append(f"Critical disk usage: {summary.avg_disk_usage_percent:.1f}%")
            recommendations.append("Clean up disk space or expand storage immediately")
        elif summary.avg_disk_usage_percent > 80:
            status = "warning" if status == "healthy" else status
            issues.append(f"High disk usage: {summary.avg_disk_usage_percent:.1f}%")
            recommendations.append("Plan for storage expansion")

        # Load average checks (assuming load per CPU core)
        load_per_core = summary.avg_load_5 / summary.total_cpu_cores if summary.total_cpu_cores > 0 else 0
        if load_per_core > 2:
            status = "warning" if status == "healthy" else status
            issues.append(f"High system load: {summary.avg_load_5:.2f}")
            recommendations.append("Investigate processes causing high load")

        if not issues:
            recommendations.append("Cluster is operating within normal parameters")

        return ClusterHealthStatus(
            cluster_id=cluster_id,
            cluster_name=summary.cluster_name,
            status=status,
            issues=issues,
            recommendations=recommendations,
            last_check=datetime.utcnow(),
            metrics_summary=summary,
        )

    async def get_prometheus_compatible_metrics(
        self,
        cluster_id: str,
        filter: str = "today",
        metric_type: str = "all",
    ) -> PrometheusCompatibleMetricsResponse:
        """Get cluster metrics in Prometheus-compatible format for BudApp.

        This method returns metrics in the same format as the original Prometheus-based
        implementation, allowing BudApp to switch seamlessly between data sources.

        Args:
            cluster_id: Cluster identifier
            filter: Time range filter (today, 7days, month)
            metric_type: Type of metrics to return (all, cpu, memory, disk, network, etc.)

        Returns:
            PrometheusCompatibleMetricsResponse with metrics in Prometheus format
        """
        # Calculate time ranges based on filter
        now = datetime.utcnow()
        if filter == "today":
            from_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            to_time = now
            # For change calculation, compare with yesterday
            prev_from_time = from_time - timedelta(days=1)
            prev_to_time = to_time - timedelta(days=1)
            # Time bucket for time series (hourly for today)
            time_bucket_interval = 3600  # 1 hour
        elif filter == "7days":
            from_time = now - timedelta(days=7)
            to_time = now
            # For change calculation, compare with previous 7 days
            prev_from_time = from_time - timedelta(days=7)
            prev_to_time = to_time - timedelta(days=7)
            # Time bucket for time series (4-hourly for 7 days)
            time_bucket_interval = 14400  # 4 hours
        elif filter == "month":
            from_time = now - timedelta(days=30)
            to_time = now
            # For change calculation, compare with previous 30 days
            prev_from_time = from_time - timedelta(days=30)
            prev_to_time = to_time - timedelta(days=30)
            # Time bucket for time series (daily for month)
            time_bucket_interval = 86400  # 1 day
        else:
            from_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            to_time = now
            prev_from_time = from_time - timedelta(days=1)
            prev_to_time = to_time - timedelta(days=1)
            time_bucket_interval = 3600  # 1 hour

        # Calculate time interval in seconds for rate calculations
        time_interval_seconds = int((to_time - from_time).total_seconds())

        # Determine which queries to run based on metric_type
        need_gauge = metric_type in ["all", "memory", "disk", "storage"]
        need_counter = metric_type in ["all", "cpu"]
        need_network = metric_type in ["all", "network", "network_bandwidth"]

        # Build list of queries to execute in parallel
        queries_to_execute = []
        if need_gauge:
            queries_to_execute.append(self.repository.get_prometheus_gauge_metrics(cluster_id, from_time, to_time))
            queries_to_execute.append(
                self.repository.get_prometheus_prev_gauge_metrics(cluster_id, prev_from_time, prev_to_time)
            )

        if need_counter:
            queries_to_execute.append(
                self.repository.get_prometheus_counter_metrics(cluster_id, from_time, to_time, time_interval_seconds)
            )
            queries_to_execute.append(
                self.repository.get_prometheus_prev_counter_metrics(
                    cluster_id, prev_from_time, prev_to_time, time_interval_seconds
                )
            )

        if need_network:
            queries_to_execute.append(self.repository.get_prometheus_network_metrics(cluster_id, from_time, to_time))
            queries_to_execute.append(
                self.repository.get_prometheus_network_timeseries(cluster_id, from_time, to_time, time_bucket_interval)
            )
            queries_to_execute.append(
                self.repository.get_prometheus_prev_network_metrics(cluster_id, prev_from_time, prev_to_time)
            )

        # Execute selected queries in parallel
        results = await asyncio.gather(*queries_to_execute) if queries_to_execute else []

        # Unpack results based on what was executed
        result_idx = 0
        gauge_results = results[result_idx] if need_gauge else []
        result_idx += 1 if need_gauge else 0
        prev_gauge_results = results[result_idx] if need_gauge else []
        result_idx += 1 if need_gauge else 0

        counter_results = results[result_idx] if need_counter else []
        result_idx += 1 if need_counter else 0
        prev_counter_results = results[result_idx] if need_counter else []
        result_idx += 1 if need_counter else 0

        network_results = results[result_idx] if need_network else []
        result_idx += 1 if need_network else 0
        timeseries_results = results[result_idx] if need_network else []
        result_idx += 1 if need_network else 0
        prev_network_results = results[result_idx] if need_network else []

        # Process results into BudApp format
        nodes = {}
        cluster_totals = {
            "memory_total": 0,
            "memory_available": 0,
            "cpu_cores": 0,  # Track total CPU cores to calculate percentage
            "cpu_usage_seconds": [],  # CPU usage as rate (seconds per second)
            "storage_total": 0,
            "storage_available": 0,
            "network_in": 0,
            "network_out": 0,
        }

        # Process gauge metrics (memory, filesystem)
        for row in gauge_results:
            node_instance = row[1]
            metric_name = row[2]
            avg_value = row[3]

            if node_instance not in nodes:
                nodes[node_instance] = {
                    "memory": BudAppMemoryMetrics(),
                    "cpu": BudAppCpuMetrics(),
                    "storage": BudAppStorageMetrics(),
                    "network_in": BudAppNetworkMetrics(),
                    "network_out": BudAppNetworkOutMetrics(),
                    "network_bandwidth": BudAppNetworkBandwidthMetrics(),
                    "cpu_cores": 0,  # Will be populated from CPU counter metrics
                }

            # Gauge metrics - use average values directly
            if metric_name == "node_memory_MemTotal_bytes":
                nodes[node_instance]["memory"].total_gib = avg_value / (1024**3)
                cluster_totals["memory_total"] += avg_value / (1024**3)
            elif metric_name == "node_memory_MemAvailable_bytes":
                nodes[node_instance]["memory"].available_gib = avg_value / (1024**3)
                cluster_totals["memory_available"] += avg_value / (1024**3)
            elif metric_name == "node_filesystem_size_bytes":
                nodes[node_instance]["storage"].total_gib = avg_value / (1024**3)
                cluster_totals["storage_total"] += avg_value / (1024**3)
            elif metric_name == "node_filesystem_avail_bytes":
                nodes[node_instance]["storage"].available_gib = avg_value / (1024**3)
                cluster_totals["storage_available"] += avg_value / (1024**3)

        # Process counter metrics (CPU, network) - calculate rates
        for row in list(counter_results) + list(network_results):
            node_instance = row[1]
            metric_name = row[2]
            value_delta = row[3]
            time_delta_seconds = row[4]
            # CPU counter results have 6 columns (with cpu_cores), network results have 5
            cpu_cores = row[5] if len(row) > 5 else None

            if node_instance not in nodes:
                nodes[node_instance] = {
                    "memory": BudAppMemoryMetrics(),
                    "cpu": BudAppCpuMetrics(),
                    "storage": BudAppStorageMetrics(),
                    "network_in": BudAppNetworkMetrics(),
                    "network_out": BudAppNetworkOutMetrics(),
                    "network_bandwidth": BudAppNetworkBandwidthMetrics(),
                    "cpu_cores": 0,
                }

            # Calculate rates for counter metrics
            if time_delta_seconds > 0:
                rate = value_delta / time_delta_seconds

                if metric_name == "node_cpu_seconds_total":
                    # CPU rate: CPU seconds accumulated per second
                    # Convert to percentage: (rate / num_cores) * 100
                    if cpu_cores and cpu_cores > 0:
                        nodes[node_instance]["cpu_cores"] = cpu_cores
                        cpu_usage_percent = min(100.0, max(0.0, (rate / cpu_cores) * 100))
                        nodes[node_instance]["cpu"].usage_percent = cpu_usage_percent
                        cluster_totals["cpu_usage_seconds"].append(rate)
                        cluster_totals["cpu_cores"] += cpu_cores

                elif metric_name == "container_network_receive_bytes_total":
                    # Network receive rate: bytes per second
                    # Convert to Mbps: (bytes/s * 8 bits/byte) / (1024^2 bits/MB)
                    mbps = (rate * 8) / (1024**2)
                    nodes[node_instance]["network_in"].inbound_mbps = mbps
                    cluster_totals["network_in"] += mbps

                elif metric_name == "container_network_transmit_bytes_total":
                    # Network transmit rate: bytes per second
                    # Convert to Mbps
                    mbps = (rate * 8) / (1024**2)
                    nodes[node_instance]["network_out"].outbound_mbps = mbps
                    cluster_totals["network_out"] += mbps

        # Calculate derived values (usage percentages, used amounts)
        for node_data in nodes.values():
            if node_data["memory"].total_gib > 0:
                node_data["memory"].used_gib = node_data["memory"].total_gib - node_data["memory"].available_gib
                node_data["memory"].usage_percent = (
                    node_data["memory"].used_gib / node_data["memory"].total_gib
                ) * 100

            if node_data["storage"].total_gib > 0:
                node_data["storage"].used_gib = node_data["storage"].total_gib - node_data["storage"].available_gib
                node_data["storage"].usage_percent = (
                    node_data["storage"].used_gib / node_data["storage"].total_gib
                ) * 100

            # Network bandwidth is sum of in and out
            node_data["network_bandwidth"].total_mbps = (
                node_data["network_in"].inbound_mbps + node_data["network_out"].outbound_mbps
            )

        # Process time-series data for network metrics
        timeseries_data = {}
        for row in timeseries_results:
            node_instance = row[0]
            metric_name = row[1]
            time_bucket = row[2]
            value_delta = row[3]
            time_delta_seconds = row[4]

            if node_instance not in timeseries_data:
                timeseries_data[node_instance] = {}
            if metric_name not in timeseries_data[node_instance]:
                timeseries_data[node_instance][metric_name] = []

            # Calculate rate for this time bucket
            if time_delta_seconds > 0:
                rate = value_delta / time_delta_seconds
                mbps = (rate * 8) / (1024**2)
                timeseries_data[node_instance][metric_name].append(TimeSeriesPoint(timestamp=time_bucket, value=mbps))

        # Populate time_series arrays in nodes
        for node_instance, node_data in nodes.items():
            if node_instance in timeseries_data:
                if "container_network_receive_bytes_total" in timeseries_data[node_instance]:
                    node_data["network_in"].time_series = sorted(
                        timeseries_data[node_instance]["container_network_receive_bytes_total"],
                        key=lambda x: x.timestamp,
                    )
                if "container_network_transmit_bytes_total" in timeseries_data[node_instance]:
                    node_data["network_out"].time_series = sorted(
                        timeseries_data[node_instance]["container_network_transmit_bytes_total"],
                        key=lambda x: x.timestamp,
                    )

                # Calculate bandwidth time series from in + out
                if node_data["network_in"].time_series and node_data["network_out"].time_series:
                    bandwidth_series = []
                    # Create a mapping of timestamp -> values
                    in_map = {point.timestamp: point.value for point in node_data["network_in"].time_series}
                    out_map = {point.timestamp: point.value for point in node_data["network_out"].time_series}
                    all_timestamps = sorted(set(in_map.keys()) | set(out_map.keys()))

                    for ts in all_timestamps:
                        bandwidth = in_map.get(ts, 0) + out_map.get(ts, 0)
                        bandwidth_series.append(TimeSeriesPoint(timestamp=ts, value=bandwidth))
                    node_data["network_bandwidth"].time_series = bandwidth_series

        # Process previous metrics for change calculation
        prev_metrics = {}

        # Process previous gauge metrics
        for row in prev_gauge_results:
            node_instance = row[0]
            metric_name = row[1]
            avg_value = row[2]

            if node_instance not in prev_metrics:
                prev_metrics[node_instance] = {}
            prev_metrics[node_instance][metric_name] = {"type": "gauge", "value": avg_value}

        # Process previous counter metrics
        for row in list(prev_counter_results) + list(prev_network_results):
            node_instance = row[0]
            metric_name = row[1]
            value_delta = row[2]
            time_delta_seconds = row[3]

            if node_instance not in prev_metrics:
                prev_metrics[node_instance] = {}

            # Calculate rate
            rate = value_delta / time_delta_seconds if time_delta_seconds > 0 else 0
            prev_metrics[node_instance][metric_name] = {"type": "counter", "rate": rate}

        # Calculate change percentages
        for node_instance, node_data in nodes.items():
            if node_instance in prev_metrics:
                prev = prev_metrics[node_instance]

                # Memory change
                if "node_memory_MemTotal_bytes" in prev and "node_memory_MemAvailable_bytes" in prev:
                    prev_total = prev["node_memory_MemTotal_bytes"]["value"] / (1024**3)
                    prev_avail = prev["node_memory_MemAvailable_bytes"]["value"] / (1024**3)
                    prev_used = prev_total - prev_avail
                    curr_used = node_data["memory"].used_gib
                    if prev_used > 0:
                        node_data["memory"].change_percent = ((curr_used - prev_used) / prev_used) * 100

                # CPU change
                if "node_cpu_seconds_total" in prev:
                    prev_rate = prev["node_cpu_seconds_total"]["rate"]
                    cpu_cores = node_data.get("cpu_cores", 1)
                    if cpu_cores > 0:
                        prev_cpu_percent = min(100.0, max(0.0, (prev_rate / cpu_cores) * 100))
                        curr_cpu_percent = node_data["cpu"].usage_percent
                        if prev_cpu_percent > 0:
                            node_data["cpu"].change_percent = (
                                (curr_cpu_percent - prev_cpu_percent) / prev_cpu_percent
                            ) * 100

                # Storage change
                if "node_filesystem_size_bytes" in prev and "node_filesystem_avail_bytes" in prev:
                    prev_total = prev["node_filesystem_size_bytes"]["value"] / (1024**3)
                    prev_avail = prev["node_filesystem_avail_bytes"]["value"] / (1024**3)
                    prev_used = prev_total - prev_avail
                    curr_used = node_data["storage"].used_gib
                    if prev_used > 0:
                        node_data["storage"].change_percent = ((curr_used - prev_used) / prev_used) * 100

                # Network change
                if "container_network_receive_bytes_total" in prev:
                    prev_rate = prev["container_network_receive_bytes_total"]["rate"]
                    prev_mbps = (prev_rate * 8) / (1024**2)
                    curr_mbps = node_data["network_in"].inbound_mbps
                    if prev_mbps > 0:
                        node_data["network_in"].change_percent = ((curr_mbps - prev_mbps) / prev_mbps) * 100

                if "container_network_transmit_bytes_total" in prev:
                    prev_rate = prev["container_network_transmit_bytes_total"]["rate"]
                    prev_mbps = (prev_rate * 8) / (1024**2)
                    curr_mbps = node_data["network_out"].outbound_mbps
                    if prev_mbps > 0:
                        node_data["network_out"].change_percent = ((curr_mbps - prev_mbps) / prev_mbps) * 100

        # Create cluster summary
        cluster_summary = BudAppClusterSummaryMetrics()

        if cluster_totals["memory_total"] > 0:
            cluster_summary.memory.total_gib = cluster_totals["memory_total"]
            cluster_summary.memory.available_gib = cluster_totals["memory_available"]
            cluster_summary.memory.used_gib = cluster_totals["memory_total"] - cluster_totals["memory_available"]
            cluster_summary.memory.usage_percent = (
                cluster_summary.memory.used_gib / cluster_summary.memory.total_gib
            ) * 100

        if cluster_totals["cpu_usage_seconds"] and cluster_totals["cpu_cores"] > 0:
            # Cluster CPU usage: sum of all CPU rates / total cores
            total_cpu_rate = sum(cluster_totals["cpu_usage_seconds"])
            cluster_summary.cpu.usage_percent = min(
                100.0, max(0.0, (total_cpu_rate / cluster_totals["cpu_cores"]) * 100)
            )

        if cluster_totals["storage_total"] > 0:
            cluster_summary.storage.total_gib = cluster_totals["storage_total"]
            cluster_summary.storage.available_gib = cluster_totals["storage_available"]
            cluster_summary.storage.used_gib = cluster_totals["storage_total"] - cluster_totals["storage_available"]
            cluster_summary.storage.usage_percent = (
                cluster_summary.storage.used_gib / cluster_summary.storage.total_gib
            ) * 100

        cluster_summary.network_in.inbound_mbps = cluster_totals["network_in"]
        cluster_summary.network_out.outbound_mbps = cluster_totals["network_out"]
        cluster_summary.network_bandwidth.total_mbps = cluster_totals["network_in"] + cluster_totals["network_out"]

        # Aggregate time-series data for cluster summary
        if timeseries_data:
            # Aggregate network time-series across all nodes
            all_in_timestamps = {}
            all_out_timestamps = {}

            for _node_instance, metrics in timeseries_data.items():
                if "container_network_receive_bytes_total" in metrics:
                    for point in metrics["container_network_receive_bytes_total"]:
                        all_in_timestamps[point.timestamp] = all_in_timestamps.get(point.timestamp, 0) + point.value

                if "container_network_transmit_bytes_total" in metrics:
                    for point in metrics["container_network_transmit_bytes_total"]:
                        all_out_timestamps[point.timestamp] = all_out_timestamps.get(point.timestamp, 0) + point.value

            # Create sorted time series
            if all_in_timestamps:
                cluster_summary.network_in.time_series = sorted(
                    [TimeSeriesPoint(timestamp=ts, value=val) for ts, val in all_in_timestamps.items()],
                    key=lambda x: x.timestamp,
                )

            if all_out_timestamps:
                cluster_summary.network_out.time_series = sorted(
                    [TimeSeriesPoint(timestamp=ts, value=val) for ts, val in all_out_timestamps.items()],
                    key=lambda x: x.timestamp,
                )

            # Calculate bandwidth time series
            all_timestamps = sorted(set(all_in_timestamps.keys()) | set(all_out_timestamps.keys()))
            bandwidth_series = []
            for ts in all_timestamps:
                bandwidth = all_in_timestamps.get(ts, 0) + all_out_timestamps.get(ts, 0)
                bandwidth_series.append(TimeSeriesPoint(timestamp=ts, value=bandwidth))
            cluster_summary.network_bandwidth.time_series = bandwidth_series

        # Apply metric type filter if not "all"
        if metric_type != "all":
            filtered_nodes = {}
            for node_instance, node_data in nodes.items():
                filtered_node = BudAppNodeMetrics()
                if metric_type == "cpu":
                    filtered_node.cpu = node_data["cpu"]
                elif metric_type == "memory":
                    filtered_node.memory = node_data["memory"]
                elif metric_type == "disk":
                    filtered_node.storage = node_data["storage"]
                elif metric_type in ["network", "network_bandwidth"]:
                    filtered_node.network_in = node_data["network_in"]
                    filtered_node.network_out = node_data["network_out"]
                    filtered_node.network_bandwidth = node_data["network_bandwidth"]
                filtered_nodes[node_instance] = filtered_node
            nodes = filtered_nodes

            # Filter cluster summary too
            if metric_type != "cpu" and metric_type != "all":
                cluster_summary.cpu = BudAppCpuMetrics()
            if metric_type != "memory" and metric_type != "all":
                cluster_summary.memory = BudAppMemoryMetrics()
            if metric_type != "disk" and metric_type != "all":
                cluster_summary.storage = BudAppStorageMetrics()
            if metric_type not in ["network", "network_bandwidth"] and metric_type != "all":
                cluster_summary.network_in = BudAppNetworkMetrics()
                cluster_summary.network_out = BudAppNetworkOutMetrics()
                cluster_summary.network_bandwidth = BudAppNetworkBandwidthMetrics()

        return PrometheusCompatibleMetricsResponse(
            nodes=nodes,
            cluster_summary=cluster_summary,
            time_range=filter,
            metric_type=metric_type,
            timestamp=datetime.utcnow().isoformat() + "+00:00",
            cluster_id=cluster_id,
        )

    # Node Events methods

    async def store_node_events(
        self,
        cluster_id: str,
        events: List[dict],
    ) -> int:
        """Store node events in ClickHouse.

        Args:
            cluster_id: Cluster identifier
            events: List of event dictionaries

        Returns:
            Number of events stored
        """
        if not events:
            return 0

        logger.info(f"Storing {len(events)} events for cluster {cluster_id}")
        return await self.repository.store_node_events(events)

    async def get_node_events_count(
        self,
        cluster_id: str,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """Get event counts per node for a cluster.

        Args:
            cluster_id: Cluster identifier
            from_time: Start time (default: last 24 hours)
            to_time: End time (default: now)

        Returns:
            Dictionary mapping node names to event counts
        """
        # Default time range: last 24 hours
        if not to_time:
            to_time = datetime.utcnow()
        if not from_time:
            from_time = to_time - timedelta(hours=24)

        result = await self.repository.get_node_events_count(cluster_id, from_time, to_time)

        # Convert to dict
        events_count = {}
        for row in result:
            node_name = row[0]
            count = row[1]
            events_count[node_name] = int(count)

        return events_count

    async def get_node_events(
        self,
        cluster_id: str,
        node_name: str,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[dict]:
        """Get events for a specific node.

        Args:
            cluster_id: Cluster identifier
            node_name: Node name to get events for
            from_time: Start time (default: last 24 hours)
            to_time: End time (default: now)
            limit: Maximum number of events to return

        Returns:
            List of event dictionaries
        """
        # Default time range: last 24 hours
        if not to_time:
            to_time = datetime.utcnow()
        if not from_time:
            from_time = to_time - timedelta(hours=24)

        result = await self.repository.get_node_events(cluster_id, node_name, from_time, to_time, limit)

        # Convert to list of dicts
        events = []
        for row in result:
            events.append(
                {
                    "event_type": row[0],
                    "reason": row[1],
                    "message": row[2],
                    "count": int(row[3]),
                    "first_timestamp": row[4].isoformat() if row[4] else None,
                    "last_timestamp": row[5].isoformat() if row[5] else None,
                    "source_component": row[6],
                    "source_host": row[7],
                }
            )

        return events

    # ============ HAMI GPU Metrics methods ============

    async def get_cluster_hami_gpu_metrics(
        self,
        cluster_id: str,
    ) -> ClusterGPUMetricsResponse:
        """Get cluster-wide HAMI GPU metrics.

        Args:
            cluster_id: Cluster identifier

        Returns:
            ClusterGPUMetricsResponse with devices, slices, and summary
        """
        # Execute queries in parallel
        devices_result, slices_result = await asyncio.gather(
            self.repository.get_cluster_hami_gpu_devices(cluster_id),
            self.repository.get_cluster_hami_gpu_slices(cluster_id),
        )

        # Process slices first to calculate per-device utilization from HAMI
        # (needed because DCGM may show 0% even when GPU is active in time-slicing mode)
        slices = []
        device_slice_utils: Dict[str, list] = {}  # device_uuid -> list of slice utilizations
        nodes_summary: Dict[str, dict] = {}
        for row in slices_result:
            memory_limit_bytes = int(row[6] or 0)
            memory_used_bytes = int(row[7] or 0)
            memory_utilization = 0.0
            if memory_limit_bytes > 0:
                memory_utilization = (memory_used_bytes / memory_limit_bytes) * 100

            slice_item = HAMISliceResponse(
                pod_name=row[0],
                pod_namespace=row[1],
                container_name=row[2] or "",
                device_uuid=row[3],
                device_index=row[4],
                node_name=row[5],
                memory_limit_bytes=memory_limit_bytes,
                memory_limit_gb=memory_limit_bytes / (1024**3),
                memory_used_bytes=memory_used_bytes,
                memory_used_gb=memory_used_bytes / (1024**3),
                memory_utilization_percent=memory_utilization,
                core_limit_percent=float(row[8] or 0),
                core_used_percent=float(row[9] or 0),
                gpu_utilization_percent=float(row[10] or 0),
                status=row[11] or "unknown",
            )
            slices.append(slice_item)

            # Track slice utilization per device and per node
            device_uuid = row[3]
            node_name = row[5]
            if row[11] == "running":
                # Track per-device utilization for device-level aggregation
                if device_uuid not in device_slice_utils:
                    device_slice_utils[device_uuid] = []
                slice_util = float(row[10] or 0)
                if slice_util > 0:
                    device_slice_utils[device_uuid].append(slice_util)

                # Track per-node for node summary
                if node_name in nodes_summary:
                    nodes_summary[node_name]["active_slices"] += 1
                    nodes_summary[node_name]["slice_utils"].append(slice_util)

        # Process devices with HAMI-based utilization fallback
        devices = []
        for row in devices_result:
            device_uuid = row[0]
            node_name = row[3]
            # DCGM hardware metrics
            dcgm_gpu_util = float(row[14]) if len(row) > 14 and row[14] is not None else None

            # Use HAMI slice utilization if DCGM shows 0 but slices are active
            slice_utils = device_slice_utils.get(device_uuid, [])
            hami_gpu_util = max(slice_utils) if slice_utils else 0
            gpu_util = (
                hami_gpu_util if (dcgm_gpu_util == 0 or dcgm_gpu_util is None) and hami_gpu_util > 0 else dcgm_gpu_util
            )

            device = GPUDeviceResponse(
                device_uuid=device_uuid,
                device_index=row[1],
                device_type=row[2] or "Unknown",
                node_name=node_name,
                total_memory_gb=float(row[4] or 0),
                memory_allocated_gb=float(row[5] or 0),
                memory_utilization_percent=float(row[6] or 0),
                core_utilization_percent=float(row[7] or 0),
                cores_allocated_percent=float(row[8] or 0),
                shared_containers_count=int(row[9] or 0),
                hardware_mode=row[10] or "unknown",
                last_metrics_update=row[11],
                temperature_celsius=float(row[12]) if len(row) > 12 and row[12] is not None else None,
                power_watts=float(row[13]) if len(row) > 13 and row[13] is not None else None,
                gpu_utilization_percent=gpu_util,
            )
            devices.append(device)

            # Build node summary structure
            if node_name not in nodes_summary:
                nodes_summary[node_name] = {
                    "gpu_count": 0,
                    "total_memory_gb": 0,
                    "allocated_memory_gb": 0,
                    "active_slices": 0,
                    "slice_utils": [],
                }
            nodes_summary[node_name]["gpu_count"] += 1
            nodes_summary[node_name]["total_memory_gb"] += float(row[4] or 0)
            nodes_summary[node_name]["allocated_memory_gb"] += float(row[5] or 0)

        # Build node summary items
        node_items = []
        for node_name, summary in nodes_summary.items():
            gpu_count = summary["gpu_count"]
            total_mem = summary["total_memory_gb"]
            allocated_mem = summary["allocated_memory_gb"]
            slice_utils = summary["slice_utils"]

            # Use HAMI slice utilization for consistency
            # Only average non-zero slices (active workloads)
            non_zero_slice_utils = [u for u in slice_utils if u > 0]
            avg_util = sum(non_zero_slice_utils) / len(non_zero_slice_utils) if non_zero_slice_utils else 0

            node_items.append(
                NodeGPUSummaryItem(
                    node_name=node_name,
                    gpu_count=gpu_count,
                    total_memory_gb=total_mem,
                    allocated_memory_gb=allocated_mem,
                    memory_utilization_percent=(allocated_mem / total_mem * 100) if total_mem > 0 else 0,
                    avg_gpu_utilization_percent=avg_util,
                    active_slices=summary["active_slices"],
                )
            )

        # Build cluster summary
        total_gpus = len(devices)
        total_memory = sum(d.total_memory_gb for d in devices)
        allocated_memory = sum(d.memory_allocated_gb for d in devices)
        total_slices = len(slices)
        active_slices = sum(1 for s in slices if s.status == "running")

        # Calculate average GPU utilization using HAMI slice values for consistency
        # Only average non-zero running slices (active workloads)
        running_slices_util = [s.gpu_utilization_percent for s in slices if s.status == "running"]
        non_zero_slice_utils = [u for u in running_slices_util if u > 0]
        avg_utilization = sum(non_zero_slice_utils) / len(non_zero_slice_utils) if non_zero_slice_utils else 0

        cluster_summary = ClusterGPUSummary(
            total_gpus=total_gpus,
            total_memory_gb=total_memory,
            allocated_memory_gb=allocated_memory,
            available_memory_gb=total_memory - allocated_memory,
            memory_utilization_percent=(allocated_memory / total_memory * 100) if total_memory > 0 else 0,
            avg_gpu_utilization_percent=avg_utilization,
            total_slices=total_slices,
            active_slices=active_slices,
        )

        return ClusterGPUMetricsResponse(
            cluster_id=cluster_id,
            timestamp=datetime.utcnow(),
            summary=cluster_summary,
            nodes=node_items,
            devices=devices,
            slices=slices,
        )

    async def get_node_hami_gpu_metrics(
        self,
        cluster_id: str,
        node_name: str,
    ) -> NodeGPUMetricsResponse:
        """Get HAMI GPU metrics for a specific node.

        Args:
            cluster_id: Cluster identifier
            node_name: Node hostname

        Returns:
            NodeGPUMetricsResponse with devices, slices, and summary
        """
        # Execute queries in parallel
        devices_result, slices_result = await asyncio.gather(
            self.repository.get_node_hami_gpu_devices(cluster_id, node_name),
            self.repository.get_node_hami_gpu_slices(cluster_id, node_name),
        )

        # Process slices first to calculate per-device utilization from HAMI
        # (needed because DCGM may show 0% even when GPU is active in time-slicing mode)
        slices = []
        active_slices = 0
        device_slice_utils: dict[str, list[float]] = {}  # device_uuid -> list of slice utilizations
        for row in slices_result:
            memory_limit_bytes = int(row[6] or 0)
            memory_used_bytes = int(row[7] or 0)
            memory_utilization = 0.0
            if memory_limit_bytes > 0:
                memory_utilization = (memory_used_bytes / memory_limit_bytes) * 100

            slice_item = HAMISliceResponse(
                pod_name=row[0],
                pod_namespace=row[1],
                container_name=row[2] or "",
                device_uuid=row[3],
                device_index=row[4],
                node_name=row[5],
                memory_limit_bytes=memory_limit_bytes,
                memory_limit_gb=memory_limit_bytes / (1024**3),
                memory_used_bytes=memory_used_bytes,
                memory_used_gb=memory_used_bytes / (1024**3),
                memory_utilization_percent=memory_utilization,
                core_limit_percent=float(row[8] or 0),
                core_used_percent=float(row[9] or 0),
                gpu_utilization_percent=float(row[10] or 0),
                status=row[11] or "unknown",
            )
            slices.append(slice_item)

            if row[11] == "running":
                active_slices += 1
                # Track slice utilization per device for device-level aggregation
                device_uuid = row[3]
                if device_uuid not in device_slice_utils:
                    device_slice_utils[device_uuid] = []
                slice_util = float(row[10] or 0)
                if slice_util > 0:
                    device_slice_utils[device_uuid].append(slice_util)

        # Process devices with HAMI-based utilization fallback
        # Query returns: device_uuid, device_index, device_type, node_name, total_memory_gb,
        # memory_allocated_gb, memory_utilization_percent, core_utilization_percent,
        # total_cores_percent, shared_containers_count, hardware_mode, last_update,
        # temperature_celsius, power_watts, sm_clock_mhz, mem_clock_mhz, gpu_utilization_percent
        devices = []
        for row in devices_result:
            device_uuid = row[0]
            # DCGM hardware metrics (indices 12-16)
            temperature_celsius = float(row[12]) if len(row) > 12 and row[12] is not None else None
            power_watts = float(row[13]) if len(row) > 13 and row[13] is not None else None
            sm_clock_mhz = int(row[14]) if len(row) > 14 and row[14] is not None else None
            mem_clock_mhz = int(row[15]) if len(row) > 15 and row[15] is not None else None
            dcgm_gpu_util = float(row[16]) if len(row) > 16 and row[16] is not None else None

            # Use HAMI slice utilization if DCGM shows 0 but slices are active
            # This handles time-slicing mode where DCGM may miss bursty GPU usage
            slice_utils = device_slice_utils.get(device_uuid, [])
            hami_gpu_util = max(slice_utils) if slice_utils else 0
            gpu_util = (
                hami_gpu_util if (dcgm_gpu_util == 0 or dcgm_gpu_util is None) and hami_gpu_util > 0 else dcgm_gpu_util
            )

            device = GPUDeviceResponse(
                device_uuid=device_uuid,
                device_index=row[1],
                device_type=row[2] or "Unknown",
                node_name=row[3],
                total_memory_gb=float(row[4] or 0),
                memory_allocated_gb=float(row[5] or 0),
                memory_utilization_percent=float(row[6] or 0),
                core_utilization_percent=float(row[7] or 0),
                cores_allocated_percent=float(row[8] or 0),
                shared_containers_count=int(row[9] or 0),
                hardware_mode=row[10] or "unknown",
                last_metrics_update=row[11],
                temperature_celsius=temperature_celsius,
                power_watts=power_watts,
                sm_clock_mhz=sm_clock_mhz,
                memory_clock_mhz=mem_clock_mhz,
                gpu_utilization_percent=gpu_util,
            )
            devices.append(device)

        # Build summary
        gpu_count = len(devices)
        total_memory = sum(d.total_memory_gb for d in devices)
        allocated_memory = sum(d.memory_allocated_gb for d in devices)

        # Calculate average GPU utilization using HAMI slice values for consistency
        # Only average non-zero running slices (active workloads)
        running_slices_util = [s.gpu_utilization_percent for s in slices if s.status == "running"]
        non_zero_slice_utils = [u for u in running_slices_util if u > 0]
        avg_utilization = sum(non_zero_slice_utils) / len(non_zero_slice_utils) if non_zero_slice_utils else 0

        summary = NodeGPUSummary(
            gpu_count=gpu_count,
            total_memory_gb=total_memory,
            allocated_memory_gb=allocated_memory,
            memory_utilization_percent=(allocated_memory / total_memory * 100) if total_memory > 0 else 0,
            avg_gpu_utilization_percent=avg_utilization,
            active_slices=active_slices,
        )

        return NodeGPUMetricsResponse(
            cluster_id=cluster_id,
            node_name=node_name,
            timestamp=datetime.utcnow(),
            devices=devices,
            slices=slices,
            summary=summary,
        )

    async def get_node_gpu_timeseries(
        self,
        cluster_id: str,
        node_name: str,
        hours: int = 6,
    ) -> GPUTimeSeriesResponse:
        """Get GPU timeseries data for a node.

        Args:
            cluster_id: Cluster identifier
            node_name: Node hostname
            hours: Number of hours to look back

        Returns:
            GPUTimeSeriesResponse with timeseries data for charts
        """
        gpu_result, slice_result = await self.repository.get_node_gpu_timeseries(cluster_id, node_name, hours)

        # Process GPU timeseries - organize by timestamp and GPU
        timestamps_set = set()
        gpu_data: Dict[int, Dict[int, Dict[str, float]]] = {}  # gpu_index -> timestamp -> metrics

        for row in gpu_result:
            bucket = int(row[0])
            gpu_index = int(row[1])
            timestamps_set.add(bucket)

            if gpu_index not in gpu_data:
                gpu_data[gpu_index] = {}

            gpu_data[gpu_index][bucket] = {
                "utilization": float(row[2] or 0),
                "memory": float(row[3] or 0),
                "temperature": float(row[4] or 0),
                "power": float(row[5] or 0),
            }

        # Sort timestamps
        timestamps = sorted(timestamps_set)

        # Build per-GPU arrays
        gpu_indices = sorted(gpu_data.keys())
        gpu_utilization = []
        memory_utilization = []
        temperature = []
        power = []

        for gpu_index in gpu_indices:
            util_arr = []
            mem_arr = []
            temp_arr = []
            pow_arr = []

            for ts in timestamps:
                metrics = gpu_data[gpu_index].get(ts, {})
                util_arr.append(metrics.get("utilization", 0))
                mem_arr.append(metrics.get("memory", 0))
                temp_arr.append(metrics.get("temperature", 0))
                pow_arr.append(metrics.get("power", 0))

            gpu_utilization.append(util_arr)
            memory_utilization.append(mem_arr)
            temperature.append(temp_arr)
            power.append(pow_arr)

        # Process slice timeseries
        slice_data: Dict[str, Dict[str, any]] = {}  # slice_key -> {namespace, data_by_ts}

        for row in slice_result:
            bucket = int(row[0])
            pod_name = row[1]
            namespace = row[2]
            utilization = float(row[3] or 0)

            slice_key = f"{namespace}/{pod_name}"
            if slice_key not in slice_data:
                slice_data[slice_key] = {
                    "namespace": namespace,
                    "pod_name": pod_name,
                    "data_by_ts": {},
                }

            slice_data[slice_key]["data_by_ts"][bucket] = utilization

        # Build slice activity items
        slice_activity = []
        for _slice_key, info in slice_data.items():
            data = []
            for ts in timestamps:
                data.append(info["data_by_ts"].get(ts, 0))

            slice_activity.append(
                SliceActivityItem(
                    slice_name=info["pod_name"],
                    namespace=info["namespace"],
                    data=data,
                )
            )

        return GPUTimeSeriesResponse(
            timestamps=timestamps,
            gpu_utilization=gpu_utilization,
            memory_utilization=memory_utilization,
            temperature=temperature,
            power=power,
            slice_activity=slice_activity,
        )
