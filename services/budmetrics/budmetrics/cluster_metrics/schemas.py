"""Schemas for cluster metrics endpoints."""

from datetime import datetime
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field

from ..commons.sql_validators import (
    ClusterUUID,
    ClusterUUIDList,
    OptionalSafeIdentifierList,
    SafeIdentifierList,
)


class ClusterMetricsQuery(BaseModel):
    """Query parameters for cluster metrics."""

    cluster_id: ClusterUUID = Field(..., description="Cluster identifier (UUID format)")
    from_time: datetime = Field(..., description="Start time for metrics")
    to_time: datetime = Field(..., description="End time for metrics")
    metric_names: OptionalSafeIdentifierList = Field(None, description="Specific metrics to retrieve")
    aggregation: Optional[str] = Field("avg", description="Aggregation method: avg, max, min, sum")
    interval: Optional[str] = Field("5m", description="Time interval for aggregation")


class NetworkTimeSeriesPoint(BaseModel):
    """Single data point in network bandwidth time series."""

    timestamp: int  # Unix timestamp
    mbps: float


class NodeMetricsSummary(BaseModel):
    """Summary of node metrics for a cluster."""

    node_name: str
    cpu_cores: float
    cpu_usage_percent: float
    memory_total_gb: float
    memory_used_gb: float
    memory_usage_percent: float
    disk_total_gb: float
    disk_used_gb: float
    disk_usage_percent: float
    load_1: float
    load_5: float
    load_15: float
    network_receive_bytes_per_sec: float = 0.0
    network_transmit_bytes_per_sec: float = 0.0
    network_bandwidth_time_series: List[NetworkTimeSeriesPoint] = []
    # GPU metrics from DCGM/HAMI
    gpu_count: int = 0
    gpu_utilization_percent: float = 0.0
    gpu_memory_utilization_percent: float = 0.0
    timestamp: datetime


class ClusterResourceSummary(BaseModel):
    """Overall cluster resource utilization summary."""

    cluster_id: str
    cluster_name: str
    timestamp: datetime
    node_count: int
    total_cpu_cores: float
    avg_cpu_usage_percent: float
    max_cpu_usage_percent: float
    total_memory_gb: float
    used_memory_gb: float
    avg_memory_usage_percent: float
    max_memory_usage_percent: float
    total_disk_gb: float
    used_disk_gb: float
    avg_disk_usage_percent: float
    max_disk_usage_percent: float
    avg_load_1: float
    avg_load_5: float
    avg_load_15: float


class PodMetricsSummary(BaseModel):
    """Summary of pod metrics."""

    namespace: str
    pod_name: str
    container_name: str
    cpu_requests: float
    cpu_limits: float
    cpu_usage: float
    memory_requests_mb: float
    memory_limits_mb: float
    memory_usage_mb: float
    restarts: int
    status: str
    timestamp: datetime


class GPUMetricsSummary(BaseModel):
    """Summary of GPU metrics."""

    node_name: str
    gpu_index: int
    gpu_model: str
    utilization_percent: float
    memory_used_gb: float
    memory_total_gb: float
    temperature_celsius: float
    power_watts: float
    timestamp: datetime


class MetricsTimeSeries(BaseModel):
    """Time series data for metrics."""

    metric_name: str
    timestamps: List[datetime]
    values: List[float]
    labels: Optional[Dict[str, str]] = None


class ClusterMetricsResponse(BaseModel):
    """Response for cluster metrics query."""

    cluster_id: str
    cluster_name: Optional[str]
    from_time: datetime
    to_time: datetime
    metrics: List[MetricsTimeSeries]


class NodeMetricsResponse(BaseModel):
    """Response for node metrics query."""

    cluster_id: str
    cluster_name: Optional[str]
    nodes: List[NodeMetricsSummary]
    timestamp: datetime


class PodMetricsResponse(BaseModel):
    """Response for pod metrics query."""

    cluster_id: str
    cluster_name: Optional[str]
    namespace: Optional[str]
    pods: List[PodMetricsSummary]
    total_pods: int
    timestamp: datetime


class GPUMetricsResponse(BaseModel):
    """Response for GPU metrics query."""

    cluster_id: str
    cluster_name: Optional[str]
    gpus: List[GPUMetricsSummary]
    total_gpus: int
    timestamp: datetime


class ClusterHealthStatus(BaseModel):
    """Health status of a cluster based on metrics."""

    cluster_id: str
    cluster_name: str
    status: str  # healthy, warning, critical
    issues: List[str]
    recommendations: List[str]
    last_check: datetime
    metrics_summary: ClusterResourceSummary


class MetricsAggregationRequest(BaseModel):
    """Request for custom metrics aggregation."""

    cluster_ids: ClusterUUIDList = Field(..., description="List of cluster IDs to aggregate (UUID format)")
    metric_names: SafeIdentifierList = Field(..., description="Metrics to aggregate")
    from_time: datetime = Field(..., description="Start time")
    to_time: datetime = Field(..., description="End time")
    group_by: OptionalSafeIdentifierList = Field(None, description="Fields to group by")
    aggregation: str = Field("avg", description="Aggregation method")
    interval: Optional[str] = Field(None, description="Time bucketing interval")


class MetricsAggregationResponse(BaseModel):
    """Response for metrics aggregation."""

    query: MetricsAggregationRequest
    results: List[Dict[str, Union[str, float, datetime]]]
    row_count: int
    execution_time_ms: float


# BudApp-compatible schemas for Prometheus format
class TimeSeriesPoint(BaseModel):
    """Time series point for metrics."""

    timestamp: int
    value: float


class BudAppMemoryMetrics(BaseModel):
    """Memory metrics in BudApp format."""

    total_gib: float = Field(default=0.0)
    used_gib: float = Field(default=0.0)
    available_gib: float = Field(default=0.0)
    usage_percent: float = Field(default=0.0)
    change_percent: float = Field(default=0.0)


class BudAppCpuMetrics(BaseModel):
    """CPU metrics in BudApp format."""

    usage_percent: float = Field(default=0.0)
    change_percent: float = Field(default=0.0)


class BudAppStorageMetrics(BaseModel):
    """Storage metrics in BudApp format."""

    total_gib: float = Field(default=0.0)
    used_gib: float = Field(default=0.0)
    available_gib: float = Field(default=0.0)
    usage_percent: float = Field(default=0.0)
    change_percent: float = Field(default=0.0)


class BudAppNetworkMetrics(BaseModel):
    """Network inbound metrics in BudApp format."""

    inbound_mbps: float = Field(default=0.0)
    change_percent: float = Field(default=0.0)
    time_series: List[TimeSeriesPoint] = Field(default_factory=list)


class BudAppNetworkOutMetrics(BaseModel):
    """Network outbound metrics in BudApp format."""

    outbound_mbps: float = Field(default=0.0)
    change_percent: float = Field(default=0.0)
    time_series: List[TimeSeriesPoint] = Field(default_factory=list)


class BudAppNetworkBandwidthMetrics(BaseModel):
    """Network bandwidth metrics in BudApp format."""

    total_mbps: float = Field(default=0.0)
    change_percent: float = Field(default=0.0)
    time_series: List[TimeSeriesPoint] = Field(default_factory=list)


class BudAppPowerMetrics(BaseModel):
    """Power metrics in BudApp format."""

    total_watt: float = Field(default=0.0)
    change_percent: float = Field(default=0.0)


class BudAppNodeMetrics(BaseModel):
    """Node-level metrics in BudApp format."""

    memory: BudAppMemoryMetrics = Field(default_factory=BudAppMemoryMetrics)
    cpu: BudAppCpuMetrics = Field(default_factory=BudAppCpuMetrics)
    storage: BudAppStorageMetrics = Field(default_factory=BudAppStorageMetrics)
    network_in: BudAppNetworkMetrics = Field(default_factory=BudAppNetworkMetrics)
    network_out: BudAppNetworkOutMetrics = Field(default_factory=BudAppNetworkOutMetrics)
    network_bandwidth: BudAppNetworkBandwidthMetrics = Field(default_factory=BudAppNetworkBandwidthMetrics)
    power: Optional[BudAppPowerMetrics] = Field(default=None)


class BudAppClusterSummaryMetrics(BaseModel):
    """Cluster summary metrics in BudApp format."""

    memory: BudAppMemoryMetrics = Field(default_factory=BudAppMemoryMetrics)
    cpu: BudAppCpuMetrics = Field(default_factory=BudAppCpuMetrics)
    storage: BudAppStorageMetrics = Field(default_factory=BudAppStorageMetrics)
    network_in: BudAppNetworkMetrics = Field(default_factory=BudAppNetworkMetrics)
    network_out: BudAppNetworkOutMetrics = Field(default_factory=BudAppNetworkOutMetrics)
    network_bandwidth: BudAppNetworkBandwidthMetrics = Field(default_factory=BudAppNetworkBandwidthMetrics)
    power: Optional[BudAppPowerMetrics] = Field(default=None)


class PrometheusCompatibleMetricsResponse(BaseModel):
    """Response in Prometheus-compatible format for BudApp."""

    nodes: Dict[str, BudAppNodeMetrics] = Field(default_factory=dict)
    cluster_summary: BudAppClusterSummaryMetrics = Field(default_factory=BudAppClusterSummaryMetrics)
    time_range: str
    metric_type: str
    timestamp: str
    cluster_id: str


# Node Events schemas
class NodeEventSchema(BaseModel):
    """Schema for a single Kubernetes node event."""

    cluster_id: str
    cluster_name: str
    node_name: str
    event_uid: str
    event_type: str  # Normal, Warning
    reason: str
    message: str
    source_component: str
    source_host: str
    first_timestamp: Optional[str] = None
    last_timestamp: Optional[str] = None
    event_count: int = 1


class NodeEventsStoreRequest(BaseModel):
    """Request to store node events."""

    cluster_id: str
    events: List[NodeEventSchema]


class NodeEventsCountResponse(BaseModel):
    """Response for node events count query."""

    cluster_id: str
    events_count: Dict[str, int]  # node_name -> count
    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None


class NodeEventDetail(BaseModel):
    """Detailed event information for display."""

    event_type: str
    reason: str
    message: str
    count: int
    first_timestamp: Optional[datetime] = None
    last_timestamp: Optional[datetime] = None
    source_component: str
    source_host: str


class NodeEventsListResponse(BaseModel):
    """Response for node events list query."""

    cluster_id: str
    node_name: str
    events: List[NodeEventDetail]
    total_events: int
    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None


# ============ GPU Metrics Schemas for HAMI ============


class GPUDeviceResponse(BaseModel):
    """Detailed GPU device metrics response."""

    device_uuid: str
    device_index: int
    device_type: str
    node_name: str
    total_memory_gb: float
    memory_allocated_gb: float
    memory_utilization_percent: float
    core_utilization_percent: float  # HAMI allocation percentage
    cores_allocated_percent: float
    shared_containers_count: int
    hardware_mode: str
    last_metrics_update: datetime
    temperature_celsius: Optional[float] = None
    power_watts: Optional[float] = None
    sm_clock_mhz: Optional[int] = None
    memory_clock_mhz: Optional[int] = None
    gpu_utilization_percent: Optional[float] = None  # Actual GPU utilization from DCGM


class HAMISliceResponse(BaseModel):
    """HAMI slice (container GPU allocation) metrics response."""

    pod_name: str
    pod_namespace: str
    container_name: str
    device_uuid: str
    device_index: int
    node_name: str
    memory_limit_bytes: int
    memory_limit_gb: float
    memory_used_bytes: int
    memory_used_gb: float
    memory_utilization_percent: float
    core_limit_percent: float
    core_used_percent: float
    gpu_utilization_percent: float
    status: str  # "running", "pending", "terminated", "unknown"


class NodeGPUSummary(BaseModel):
    """Summary of GPU metrics for a single node."""

    gpu_count: int
    total_memory_gb: float
    allocated_memory_gb: float
    memory_utilization_percent: float
    avg_gpu_utilization_percent: float
    active_slices: int


class NodeGPUMetricsResponse(BaseModel):
    """Response for node-specific GPU metrics."""

    cluster_id: str
    node_name: str
    timestamp: datetime
    devices: List[GPUDeviceResponse]
    slices: List[HAMISliceResponse]
    summary: NodeGPUSummary


class ClusterGPUSummary(BaseModel):
    """Summary of GPU metrics for entire cluster."""

    total_gpus: int
    total_memory_gb: float
    allocated_memory_gb: float
    available_memory_gb: float
    memory_utilization_percent: float
    avg_gpu_utilization_percent: float
    total_slices: int
    active_slices: int
    avg_temperature_celsius: Optional[float] = None
    total_power_watts: Optional[float] = None


class NodeGPUSummaryItem(BaseModel):
    """Summary of GPU metrics for a node within cluster response."""

    node_name: str
    gpu_count: int
    total_memory_gb: float
    allocated_memory_gb: float
    memory_utilization_percent: float
    avg_gpu_utilization_percent: float
    active_slices: int


class ClusterGPUMetricsResponse(BaseModel):
    """Response for cluster-wide GPU metrics."""

    cluster_id: str
    timestamp: datetime
    summary: ClusterGPUSummary
    nodes: List[NodeGPUSummaryItem]
    devices: List[GPUDeviceResponse]
    slices: List[HAMISliceResponse]


class SliceActivityItem(BaseModel):
    """Slice activity data for timeseries charts."""

    slice_name: str
    namespace: str
    data: List[float]


class GPUTimeSeriesResponse(BaseModel):
    """Response for GPU timeseries data."""

    timestamps: List[int]  # Unix milliseconds
    gpu_utilization: List[List[float]]  # Per GPU utilization over time
    memory_utilization: List[List[float]]  # Per GPU memory over time
    temperature: List[List[float]]  # Per GPU temperature over time
    power: List[List[float]]  # Per GPU power over time
    slice_activity: List[SliceActivityItem]  # Per slice activity over time
