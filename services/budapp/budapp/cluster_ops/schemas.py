#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------


"""Contains core Pydantic schemas used for data validation and serialization within the cluster ops services."""

import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import (
    UUID4,
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
)

from budapp.commons.constants import ClusterStatusEnum, EndpointStatusEnum
from budapp.commons.schemas import PaginatedSuccessResponse, SuccessResponse

from ..commons.helpers import validate_icon
from ..commons.schemas import BudNotificationMetadata
from ..model_ops.schemas import Model
from ..project_ops.schemas import Project


class ClusterBase(BaseModel):
    """Cluster base schema."""

    name: str
    ingress_url: Optional[str] = None  # Optional URL for cluster ingress since cloud clusters were introduced
    cluster_type: str = Field(default="ON_PERM", description="Type of cluster: ON_PERM or CLOUD")
    icon: str


class ClusterCreate(ClusterBase):
    """Cluster create schema."""

    status: ClusterStatusEnum
    cpu_count: int
    gpu_count: int
    hpu_count: int
    cpu_total_workers: int
    cpu_available_workers: int
    gpu_total_workers: int
    gpu_available_workers: int
    hpu_total_workers: int
    hpu_available_workers: int
    created_by: UUID4
    cluster_id: UUID4
    status_sync_at: datetime
    total_nodes: int
    available_nodes: int

    # Optional
    cloud_provider_id: Optional[UUID4] = None
    credential_id: Optional[UUID4] = None
    region: Optional[str] = None


class ClusterResourcesInfo(BaseModel):
    """Cluster resources schema."""

    cpu_count: int
    gpu_count: int
    hpu_count: int
    cpu_total_workers: int
    cpu_available_workers: int
    gpu_total_workers: int
    gpu_available_workers: int
    hpu_total_workers: int
    hpu_available_workers: int
    total_nodes: int
    available_nodes: int


class ClusterResponse(BaseModel):
    """Cluster response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    icon: str
    ingress_url: Optional[str] = None  # Optional URL for cluster ingress
    cluster_type: Optional[str] = None
    created_at: datetime
    modified_at: datetime
    status: ClusterStatusEnum
    cluster_id: UUID
    cpu_count: int
    gpu_count: int
    hpu_count: int
    cpu_total_workers: int
    cpu_available_workers: int
    gpu_total_workers: int
    gpu_available_workers: int
    hpu_total_workers: int
    hpu_available_workers: int
    total_nodes: int
    available_nodes: int

    # @computed_field
    # @property
    # def total_nodes(self) -> int:
    #     """Total nodes."""
    #     return self.cpu_total_workers + self.gpu_total_workers + self.hpu_total_workers

    # @computed_field
    # @property
    # def available_nodes(self) -> int:
    #     """Available nodes."""
    #     return self.cpu_available_workers + self.gpu_available_workers + self.hpu_available_workers


class ClusterPaginatedResponse(ClusterResponse):
    endpoint_count: int


class ClusterFilter(BaseModel):
    """Filter cluster schema."""

    name: str | None = None


class ClusterListResponse(PaginatedSuccessResponse):
    """Cluster response schema."""

    model_config = ConfigDict(extra="ignore")

    clusters: List[ClusterPaginatedResponse]


class CreateClusterWorkflowRequest(BaseModel):
    """Create cluster workflow request schema."""

    name: str | None = None
    icon: str | None = None
    ingress_url: str | None = None
    workflow_id: UUID4 | None = None
    workflow_total_steps: int | None = None
    step_number: int | None = None
    trigger_workflow: bool | None = None

    cluster_type: str | None = "ON_PREM"

    # Cloud
    credential_id: UUID4 | None = None
    provider_id: UUID4 | None = None
    region: str | None = None

    @field_validator("icon", mode="before")
    @classmethod
    def icon_validate(cls, value: str | None) -> str | None:
        """Validate the icon."""
        if value is not None and not validate_icon(value):
            raise ValueError("invalid icon")
        return value


class CreateClusterWorkflowSteps(BaseModel):
    """Create cluster workflow step data schema."""

    name: str | None = None
    icon: str | None = None
    ingress_url: AnyHttpUrl | None = None
    configuration_yaml: dict | None = None

    # Cloud specific fields
    cluster_type: str = "ON_PREM"  # "ON_PREM" or "CLOUD"
    credential_id: UUID4 | None = None
    provider_id: UUID4 | None = None
    region: str | None = None

    # Cloud Credentials
    credentials: dict | None = None
    cloud_provider_unique_id: str | None = None


class EditClusterRequest(BaseModel):
    name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Name of the cluster, must be non-empty and at most 100 characters.",
    )
    icon: str | None = Field(None, description="URL or path of the cluster icon.")
    ingress_url: AnyHttpUrl | None = Field(None, description="ingress_url.")

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        """Ensure the name is not empty or only whitespace."""
        if value is not None and not value.strip():
            raise ValueError("Cluster name cannot be empty or only whitespace.")
        return value

    @field_validator("ingress_url", mode="after")
    @classmethod
    def convert_url_to_string(cls, value: AnyHttpUrl | None) -> str | None:
        """Convert AnyHttpUrl to string."""
        return str(value) if value is not None else None

    @field_validator("icon", mode="before")
    @classmethod
    def icon_validate(cls, value: str | None) -> str | None:
        """Validate the icon."""
        if value is not None and not validate_icon(value):
            raise ValueError("invalid icon")
        return value


class ClusterDetailResponse(ClusterResponse):
    """Cluster detail response schema."""

    total_workers_count: int
    active_workers_count: int
    total_endpoints_count: int
    running_endpoints_count: int
    hardware_type: list


class SingleClusterResponse(SuccessResponse):
    """Single cluster entity."""

    cluster: Union[ClusterResponse, ClusterDetailResponse]


class CancelClusterOnboardingRequest(BaseModel):
    """Cancel cluster onboarding request schema."""

    workflow_id: UUID4


class ClusterEndpointResponse(BaseModel):
    """Cluster endpoint response schema."""

    id: UUID4
    name: str
    status: EndpointStatusEnum
    created_at: datetime
    project: Project
    model: Model
    active_workers: int
    total_workers: int
    roi: int


class ClusterEndpointPaginatedResponse(PaginatedSuccessResponse):
    """Cluster endpoint paginated response schema."""

    endpoints: list[ClusterEndpointResponse] = []


class ClusterEndpointFilter(BaseModel):
    """Filter schema for endpoints."""

    name: str | None = None
    status: EndpointStatusEnum | None = None


# Cluster Events Schema Paginated Response
class ClusterNodeWiseEventsResponse(SuccessResponse):
    """Cluster node-wise events response schema."""

    events: Optional[list] = []


# Cluster Metrics Schema
class TimeSeriesPoint(BaseModel):
    """Time series data point."""

    timestamp: int
    value: float


class NetworkMetrics(BaseModel):
    """Network metrics schema."""

    inbound_mbps: float = Field(default=0.0)
    change_percent: float = Field(default=0.0)
    time_series: List[TimeSeriesPoint] = Field(default_factory=list)


class NetworkOutMetrics(BaseModel):
    """Network outbound metrics schema."""

    outbound_mbps: float = Field(default=0.0)
    change_percent: float = Field(default=0.0)
    time_series: List[TimeSeriesPoint] = Field(default_factory=list)


class NetworkBandwidthMetrics(BaseModel):
    """Network bandwidth metrics schema."""

    total_mbps: float = Field(default=0.0)
    change_percent: float = Field(default=0.0)
    time_series: List[TimeSeriesPoint] = Field(default_factory=list)


class MemoryMetrics(BaseModel):
    """Memory metrics schema."""

    total_gib: float = Field(default=0.0)
    used_gib: float = Field(default=0.0)
    available_gib: float = Field(default=0.0)
    usage_percent: float = Field(default=0.0)
    change_percent: float = Field(default=0.0)


class CpuMetrics(BaseModel):
    """CPU metrics schema."""

    usage_percent: float = Field(default=0.0)
    change_percent: float = Field(default=0.0)


class StorageMetrics(BaseModel):
    """Storage metrics schema."""

    total_gib: float = Field(default=0.0)
    used_gib: float = Field(default=0.0)
    available_gib: float = Field(default=0.0)
    usage_percent: float = Field(default=0.0)
    change_percent: float = Field(default=0.0)


class PowerMetrics(BaseModel):
    """Power metrics schema."""

    total_kwh: float = Field(default=0.0)
    unit: str = Field(default="kWh")
    change_percent: float = Field(default=0.0)


class NodeMetrics(BaseModel):
    """Node level metrics schema."""

    memory: Optional[MemoryMetrics] = Field(default_factory=MemoryMetrics)
    cpu: Optional[CpuMetrics] = Field(default_factory=CpuMetrics)
    storage: Optional[StorageMetrics] = Field(default_factory=StorageMetrics)
    network_in: Optional[NetworkMetrics] = Field(default_factory=NetworkMetrics)
    network_out: Optional[NetworkOutMetrics] = Field(default_factory=NetworkOutMetrics)
    network_bandwidth: Optional[NetworkBandwidthMetrics] = Field(default_factory=NetworkBandwidthMetrics)
    power: Optional[Any] = Field(default=None)


class ClusterSummaryMetrics(BaseModel):
    """Cluster summary metrics schema."""

    memory: Optional[MemoryMetrics] = Field(default_factory=MemoryMetrics)
    cpu: Optional[CpuMetrics] = Field(default_factory=CpuMetrics)
    storage: Optional[StorageMetrics] = Field(default_factory=StorageMetrics)
    network_in: Optional[NetworkMetrics] = Field(default_factory=NetworkMetrics)
    network_out: Optional[NetworkOutMetrics] = Field(default_factory=NetworkOutMetrics)
    network_bandwidth: Optional[NetworkBandwidthMetrics] = Field(default_factory=NetworkBandwidthMetrics)
    power: Optional[Any] = Field(default=None)


class ClusterMetricsResponse(SuccessResponse):
    """Cluster metrics response schema."""

    nodes: Dict[str, NodeMetrics] = Field(default_factory=dict)
    cluster_summary: ClusterSummaryMetrics = Field(default_factory=ClusterSummaryMetrics)
    time_range: str
    metric_type: str
    timestamp: str
    cluster_id: str

    class Config:
        """Pydantic model config."""

        json_schema_extra = {
            "example": {
                "nodes": {
                    "10.25.30.22:9100": {
                        "memory": {
                            "total_gib": 503.42,
                            "used_gib": 15.83,
                            "available_gib": 487.59,
                            "usage_percent": 3.14,
                            "change_percent": -0.52,
                        },
                        "cpu": {"usage_percent": 25.45, "change_percent": 5.23},
                        "storage": {
                            "total_gib": 876.14,
                            "used_gib": 111.03,
                            "available_gib": 765.11,
                            "usage_percent": 12.67,
                            "change_percent": 0.34,
                        },
                        "network_in": {
                            "inbound_mbps": 45.67,
                            "change_percent": 12.34,
                            "time_series": [{"timestamp": 1738567200, "value": 45.67}],
                        },
                        "network_out": {
                            "outbound_mbps": 32.45,
                            "change_percent": -5.67,
                            "time_series": [{"timestamp": 1738567200, "value": 32.45}],
                        },
                        "network_bandwidth": {
                            "total_mbps": 78.12,
                            "change_percent": 6.67,
                            "time_series": [{"timestamp": 1738567200, "value": 78.12}],
                        },
                    }
                },
                "cluster_summary": {
                    "memory": {
                        "total_gib": 1006.84,
                        "used_gib": 31.66,
                        "available_gib": 975.18,
                        "usage_percent": 3.14,
                        "change_percent": -0.52,
                    },
                    "cpu": {"usage_percent": 25.45, "change_percent": 5.23},
                    "storage": {
                        "total_gib": 1752.28,
                        "used_gib": 222.06,
                        "available_gib": 1530.22,
                        "usage_percent": 12.67,
                        "change_percent": 0.34,
                    },
                    "network_in": {
                        "inbound_mbps": 91.34,
                        "change_percent": 12.34,
                        "time_series": [{"timestamp": 1738567200, "value": 91.34}],
                    },
                    "network_out": {
                        "outbound_mbps": 64.90,
                        "change_percent": -5.67,
                        "time_series": [{"timestamp": 1738567200, "value": 64.90}],
                    },
                    "network_bandwidth": {
                        "total_mbps": 156.24,
                        "change_percent": 6.67,
                        "time_series": [{"timestamp": 1738567200, "value": 156.24}],
                    },
                },
                "time_range": "today",
                "metric_type": "all",
                "timestamp": "2025-02-03T08:58:18.368278+00:00",
                "cluster_id": "12345678-1234-5678-1234-567812345678",
            }
        }


class MetricTypeEnum(Enum):
    """Enum for metric types."""

    ALL = "all"
    MEMORY = "memory"
    CPU = "cpu"
    DISK = "disk"
    GPU = "gpu"
    HPU = "hpu"
    NETWORK_BANDWIDTH = "network_bandwidth"
    POWER = "power"


class PrometheusConfig(BaseModel):
    """Configuration for connecting to Prometheus metrics server.

    Attributes:
        base_url: The base URL of the Prometheus server, defaults to https://metric.bud.studio
        cluster_id: The ID of the cluster to query metrics for, empty string means query all clusters
    """

    base_url: HttpUrl = Field(default="https://metric.bud.studio")
    cluster_id: str = Field()


class NodeMetricsResponse(SuccessResponse):
    """Node metrics response schema."""

    nodes: Dict[str, Dict[str, object]]


# Cloud Cluster Schemas
class CreateCloudClusterRequest(BaseModel):
    """Request schema for creating a cloud cluster."""

    name: str = Field(min_length=1, max_length=100, description="Name of the cloud cluster")
    icon: str = Field(min_length=1, max_length=100, description="Icon URL for the cloud cluster")
    credential_id: UUID4 = Field(description="UUID of the CloudCredentials record to use for this cluster")
    provider_id: UUID4 = Field(description="UUID of the CloudProviders record to use for this cluster")
    region: str = Field(min_length=4, max_length=100, description="Region to create the cluster in")


# class CloudClusterResponse(SuccessResponse):
#     """Cloud cluster response schema."""

#     cluster: CloudCluster


# Bud Simulator Schema
class BudSimulatorRequest(BaseModel):
    """Request schema for Bud Simulator."""

    pretrained_model_uri: str
    model_uri: Optional[str] = Field(None, description="Original cloud/HuggingFace URI of the model")
    input_tokens: int
    output_tokens: int
    concurrency: int
    target_ttft: int
    target_throughput_per_user: int
    target_e2e_latency: int
    notification_metadata: BudNotificationMetadata | None = None
    source_topic: str
    is_proprietary_model: bool


# Model Recommended Cluster Schemas
class ModelClusterRecommendedCreate(BaseModel):
    """Model recommended cluster create schema."""

    model_id: UUID4
    cluster_id: UUID4
    hardware_type: list[str]
    cost_per_million_tokens: float


class ModelClusterRecommendedUpdate(ModelClusterRecommendedCreate):
    """Model recommended cluster update schema."""

    pass


class RecommendedClusterData(BaseModel):
    """Recommended cluster benchmarks schema."""

    replicas: int
    concurrency: dict
    ttft: dict | None = None
    e2e_latency: dict | None = None
    per_session_tokens_per_sec: dict | None = None
    over_all_throughput: dict | None = None


class RecommendedCluster(BaseModel):
    """Recommended cluster response schema."""

    id: UUID
    cluster_id: UUID
    name: str
    cost_per_token: float
    total_resources: int
    resources_used: int
    resource_details: list[dict]
    required_devices: list[dict]
    benchmarks: RecommendedClusterData
    # Parser metadata from simulator
    tool_calling_parser_type: str | None = None
    reasoning_parser_type: str | None = None
    chat_template: str | None = None
    # Engine capability flags from simulator
    supports_lora: bool | None = None
    supports_pipeline_parallelism: bool | None = None


class RecommendedClusterResponse(SuccessResponse):
    """User response to client schema."""

    model_config = ConfigDict(from_attributes=True)

    clusters: list[RecommendedCluster]
    status: Literal["success", "processing"] = "success"
    workflow_id: UUID


class RecommendedClusterRequest(BaseModel):
    """Request to get recommended cluster events."""

    pretrained_model_uri: str
    input_tokens: int
    output_tokens: int
    concurrency: int
    target_ttft: int
    target_throughput_per_user: int
    target_e2e_latency: int
    notification_metadata: BudNotificationMetadata
    source_topic: str
    is_proprietary_model: bool
    hardware_mode: Optional[str] = Field(default="dedicated", description="Hardware mode: dedicated or shared")
    model_endpoints: Optional[str] = Field(
        default=None,
        description="Comma-separated model endpoint types (e.g., 'EMBEDDING', 'LLM') for engine selection",
    )


class GrafanaDashboardResponse(SuccessResponse):
    """Grafana dashboard response schema."""

    url: str


class AnalyticsPanel(BaseModel):
    """Analytics panel schema."""

    id: UUID
    name: str
    iframe_url: str
    status: str


class AnalyticsPanelsResponse(SuccessResponse):
    """Analytics panels response schema."""

    deployment: list[AnalyticsPanel] | None = None
    cluster: list[AnalyticsPanel] | None = None


class AnalyticsPanelResponse(SuccessResponse):
    """Analytics panel response schema."""

    panel: AnalyticsPanel


# Cluster Settings Schemas
VALID_K8S_ACCESS_MODES = {
    "ReadWriteOnce",
    "ReadWriteMany",
    "ReadOnlyMany",
    "ReadWriteOncePod",
}


class ClusterSettingsBase(BaseModel):
    """Base schema for cluster settings."""

    default_storage_class: Optional[str] = Field(None, description="Default storage class for cluster deployments")
    default_access_mode: Optional[str] = Field(None, description="Default access mode for cluster volumes")

    @field_validator("default_storage_class", mode="before")
    @classmethod
    def validate_storage_class(cls, value: str | None) -> str | None:
        """Validate storage class name."""
        if value is None:
            return None

        cleaned_value = value.strip()
        if not cleaned_value:
            return None

        if not re.match(r"^[a-zA-Z0-9.-]*$", cleaned_value):
            raise ValueError("Storage class name can only contain alphanumeric characters, hyphens, and dots")
        if cleaned_value.startswith("-") or cleaned_value.endswith("-"):
            raise ValueError("Storage class name cannot start or end with a hyphen")

        return cleaned_value

    @field_validator("default_access_mode", mode="before")
    @classmethod
    def validate_access_mode(cls, value: str | None) -> str | None:
        """Validate provided access mode."""
        if value is None:
            return None

        cleaned_value = value.strip()
        if not cleaned_value:
            return None

        if cleaned_value not in VALID_K8S_ACCESS_MODES:
            allowed_values = ", ".join(sorted(VALID_K8S_ACCESS_MODES))
            raise ValueError(f"Access mode must be one of: {allowed_values}")

        return cleaned_value


class ClusterSettingsCreate(ClusterSettingsBase):
    """Schema for creating cluster settings."""

    cluster_id: UUID4 = Field(description="UUID of the cluster")
    created_by: UUID4 = Field(description="UUID of the user creating the settings")


class ClusterSettingsUpdate(ClusterSettingsBase):
    """Schema for updating cluster settings."""

    pass


class ClusterSettingsResponse(ClusterSettingsBase):
    """Response schema for cluster settings."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cluster_id: UUID
    created_by: UUID
    created_at: datetime
    modified_at: datetime


class ClusterSettingsDetailResponse(SuccessResponse):
    """Single cluster settings response."""

    settings: ClusterSettingsResponse


class CreateClusterSettingsRequest(ClusterSettingsBase):
    """Request schema for creating cluster settings."""

    pass


class UpdateClusterSettingsRequest(ClusterSettingsBase):
    """Request schema for updating cluster settings."""

    pass
