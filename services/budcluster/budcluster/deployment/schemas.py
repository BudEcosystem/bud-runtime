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


"""Contains core Pydantic schemas used for data validation and serialization within the core services."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from budmicroframe.commons.schemas import CloudEventBase, SuccessResponse
from pydantic import BaseModel, ConfigDict, Field

from ..commons.constants import ClusterPlatformEnum
from ..commons.schemas import PaginatedSuccessResponse, WorkflowResponse


class DeploymentStatusEnum(str, Enum):
    READY = "ready"
    PENDING = "pending"
    INGRESS_FAILED = "ingress_failed"
    ENDPOINTS_FAILED = "endpoints_failed"
    FAILED = "failed"
    ERROR = "error"  # Terminal state after 24hrs of failure


class WorkerStatusEnum(str, Enum):
    """Worker status enumeration."""

    PENDING = "Pending"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    UNKNOWN = "Unknown"
    DELETING = "Deleting"


# BudAIScaler Enums
class ScalingStrategyEnum(str, Enum):
    """Scaling strategy types for BudAIScaler."""

    HPA = "HPA"
    KPA = "KPA"
    BUD_SCALER = "BudScaler"


class MetricSourceTypeEnum(str, Enum):
    """Metric source types for BudAIScaler."""

    POD = "pod"
    RESOURCE = "resource"
    PROMETHEUS = "prometheus"
    INFERENCE_ENGINE = "inferenceEngine"
    CUSTOM = "custom"
    EXTERNAL = "external"


class SpotInstancePreferenceEnum(str, Enum):
    """Spot instance preference options."""

    NONE = "none"
    PREFER = "prefer"
    REQUIRE = "require"


class FederationModeEnum(str, Enum):
    """Multi-cluster federation modes."""

    ACTIVE_PASSIVE = "active-passive"
    ACTIVE_ACTIVE = "active-active"
    WEIGHTED = "weighted"


class ScalingPolicyTypeEnum(str, Enum):
    """Scaling policy types."""

    PODS = "Pods"
    PERCENT = "Percent"


class SelectPolicyEnum(str, Enum):
    """Policy selection strategy."""

    MAX = "Max"
    MIN = "Min"
    DISABLED = "Disabled"


# BudAIScaler Configuration Schemas
class GPUConfig(BaseModel):
    """GPU-aware scaling configuration."""

    enabled: bool = False
    memoryThreshold: int = Field(default=80, ge=0, le=100)
    computeThreshold: int = Field(default=80, ge=0, le=100)
    topologyAware: bool = False
    preferredGPUType: Optional[str] = None
    vGPUSupport: bool = False


class CostConfig(BaseModel):
    """Cost-aware scaling configuration."""

    enabled: bool = False
    cloudProvider: Optional[str] = None  # aws, azure, gcp, on-premises
    hourlyBudgetLimit: Optional[float] = None
    dailyBudgetLimit: Optional[float] = None
    spotInstancePreference: SpotInstancePreferenceEnum = SpotInstancePreferenceEnum.NONE


class PredictionConfig(BaseModel):
    """Predictive scaling configuration."""

    enabled: bool = False
    lookAheadMinutes: int = Field(default=15, ge=1, le=1440)
    historyDays: int = Field(default=7, ge=1, le=365)
    minConfidence: float = Field(default=0.7, ge=0.0, le=1.0)
    predictionMetrics: List[str] = Field(default_factory=list)


class ScheduleHint(BaseModel):
    """Schedule-based scaling hint."""

    name: str
    cronExpression: str
    targetReplicas: int = Field(ge=0)
    duration: Optional[str] = None  # e.g., "8h", "30m"


class FailoverThresholds(BaseModel):
    """Multi-cluster failover thresholds."""

    healthCheckFailures: int = Field(default=3, ge=1)
    latencyMs: int = Field(default=5000, ge=100)


class MultiClusterConfig(BaseModel):
    """Multi-cluster federation configuration."""

    enabled: bool = False
    federationMode: FederationModeEnum = FederationModeEnum.ACTIVE_PASSIVE
    clusterWeights: Dict[str, int] = Field(default_factory=dict)
    failoverThresholds: Optional[FailoverThresholds] = None


class ScalingPolicy(BaseModel):
    """Individual scaling policy."""

    type: ScalingPolicyTypeEnum
    value: int = Field(ge=1)
    periodSeconds: int = Field(ge=1, le=1800)


class ScalingRules(BaseModel):
    """Scaling rules for up or down direction."""

    stabilizationWindowSeconds: int = Field(default=0, ge=0, le=3600)
    policies: List[ScalingPolicy] = Field(default_factory=list)
    selectPolicy: SelectPolicyEnum = SelectPolicyEnum.MAX


class ScalingBehavior(BaseModel):
    """Scaling behavior configuration."""

    scaleUp: ScalingRules = Field(
        default_factory=lambda: ScalingRules(stabilizationWindowSeconds=0, selectPolicy=SelectPolicyEnum.MAX)
    )
    scaleDown: ScalingRules = Field(
        default_factory=lambda: ScalingRules(stabilizationWindowSeconds=300, selectPolicy=SelectPolicyEnum.MIN)
    )


class BudAIScalerConfig(BaseModel):
    """Complete BudAIScaler configuration schema."""

    enabled: bool = False
    minReplicas: int = Field(default=1, ge=0)
    maxReplicas: int = Field(default=10, ge=1)
    scalingStrategy: ScalingStrategyEnum = ScalingStrategyEnum.BUD_SCALER

    # Metrics sources - flexible dict list for polymorphic handling
    metricsSources: List[Dict[str, Any]] = Field(default_factory=list)

    # Feature configurations
    gpuConfig: GPUConfig = Field(default_factory=GPUConfig)
    costConfig: CostConfig = Field(default_factory=CostConfig)
    predictionConfig: PredictionConfig = Field(default_factory=PredictionConfig)
    scheduleHints: List[ScheduleHint] = Field(default_factory=list)
    multiCluster: MultiClusterConfig = Field(default_factory=MultiClusterConfig)
    behavior: ScalingBehavior = Field(default_factory=ScalingBehavior)


class TransferModelRequest(BaseModel):
    """Request body for transferring a model."""

    model_config = ConfigDict(protected_namespaces=())

    model: str
    endpoint_name: str
    cluster_config: str | None = None
    simulator_config: List[Dict[str, Any]] | None = None
    platform: Optional[ClusterPlatformEnum] = None
    existing_deployment_namespace: Optional[str] = None
    default_storage_class: Optional[str] = None
    default_access_mode: Optional[str] = None
    storage_size_gb: Optional[float] = None
    operation: Literal["download", "upload"] = "download"


class RunBenchmarkParams(BaseModel):
    user_id: Optional[UUID] = None
    model_id: Optional[UUID] = None
    benchmark_id: Optional[UUID] = None
    # use_cache: Optional[bool] = False
    # embedding_model: Optional[str] = None
    # eviction_policy: Optional[str] = None
    # max_size: Optional[int] = None
    # ttl: Optional[int] = None
    # score_threshold: Optional[float] = None
    nodes: List[Dict[str, Any]] | None = None
    datasets: Optional[list[dict]] = None
    is_performance_benchmark: bool = False
    # Configuration options from benchmark workflow step 6
    hardware_mode: Optional[str] = None
    selected_device_type: Optional[str] = None
    tp_size: Optional[int] = None
    pp_size: Optional[int] = None
    replicas: Optional[int] = None
    num_prompts: Optional[int] = None  # Total prompts to run (defaults to sum of dataset num_samples)


class CommonDeploymentParams(BaseModel):
    cluster_id: UUID
    simulator_id: Optional[UUID] = None
    endpoint_name: str
    model: str
    model_size: Optional[int] = None
    storage_size_gb: Optional[float] = None
    concurrency: int
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    model_max_context_length: Optional[int] = None
    # BudAIScaler configuration
    budaiscaler: BudAIScalerConfig | dict | None = None


class DeploymentCreateRequest(CloudEventBase, CommonDeploymentParams, RunBenchmarkParams):
    """Request body for creating a deployment."""

    hf_token: Optional[str] = None
    target_ttft: Optional[int] = None
    target_e2e_latency: Optional[int] = None
    target_throughput_per_user: Optional[int] = None
    credential_id: Optional[UUID] = None
    existing_deployment_namespace: Optional[str] = None
    provider: Optional[str] = None
    # User preferences for parser features
    enable_tool_calling: Optional[bool] = None
    enable_reasoning: Optional[bool] = None
    default_storage_class: Optional[str] = None  # Added for cluster settings support
    default_access_mode: Optional[str] = None


class LocalDeploymentCreateRequest(CloudEventBase, CommonDeploymentParams, RunBenchmarkParams):
    """Request body for creating a local deployment."""

    hf_token: Optional[str] = None
    target_ttft: Optional[int] = None
    target_e2e_latency: Optional[int] = None
    target_throughput_per_user: Optional[int] = None
    credential_id: Optional[UUID] = None
    namespace: Optional[str] = None
    provider: Optional[str] = None
    default_storage_class: Optional[str] = None  # Added for cluster settings support
    default_access_mode: Optional[str] = None


class DeploymentInfo(BaseModel):
    """Information about a deployment."""

    status: Literal["pending", "running", "completed", "failed"]


class DeploymentResponse(WorkflowResponse):
    """Response body for creating a deployment."""

    deployment_info: DeploymentInfo


class DeploymentWorkflowRequest(DeploymentCreateRequest):
    """Request body for creating a deployment."""

    cluster_config: str | None = None
    simulator_config: List[Dict[str, Any]] | None = None
    ingress_url: str | None = None
    credential_id: UUID | None = None
    provider: str | None = None
    namespace: str | None = None
    platform: Optional[ClusterPlatformEnum] = None
    add_worker: bool = False
    # Parser types fetched from BudSim (internal workflow use only)
    tool_calling_parser_type: Optional[str] = None
    reasoning_parser_type: Optional[str] = None
    chat_template: Optional[str] = None
    default_storage_class: Optional[str] = None  # Added for cluster settings support
    default_access_mode: Optional[str] = None


class UpdateModelTransferStatusRequest(DeploymentWorkflowRequest):
    """Request body for updating the model transfer status."""

    main_workflow_id: UUID
    workflow_name: str
    workflow_start_time: Optional[str] = None  # ISO format timestamp to track overall timeout


class VerifyDeploymentHealthRequest(BaseModel):
    """Request body for verifying the engine health."""

    cluster_id: UUID
    cluster_config: str
    namespace: str
    ingress_url: str
    platform: Optional[ClusterPlatformEnum] = None
    ingress_health: bool = True
    add_worker: bool = False


class RunPerformanceBenchmarkRequest(BaseModel):
    """Request body for running the performance benchmark."""

    deployment_url: str
    model: str
    model_type: Optional[str] = None
    target_ttft: Optional[int] = None
    target_e2e_latency: Optional[int] = None
    target_throughput_per_user: Optional[int] = None
    concurrency: int
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    datasets: Optional[list[dict]] = None
    num_prompts: Optional[int] = None  # Total prompts to run (defaults to sum of dataset num_samples)


class WorkflowRunPerformanceBenchmarkRequest(BaseModel):
    """Request body for running the performance benchmark."""

    cluster_config: str
    namespace: str
    benchmark_request: RunPerformanceBenchmarkRequest
    platform: Optional[ClusterPlatformEnum] = None
    cleanup_namespace: bool = False
    benchmark_id: Optional[UUID] = None
    cluster_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    model_id: Optional[UUID] = None
    nodes: Optional[List[Dict[str, Any]]] = None


class DeployModelWorkflowResult(BaseModel):
    """Result of a deploy model workflow."""

    result: Dict[str, Any] | str
    performance_status: bool
    benchmark_status: bool
    workflow_id: UUID
    cluster_id: UUID
    simulator_id: Optional[UUID] = None
    namespace: str
    deployment_status: Dict[str, Any]
    number_of_nodes: int
    credential_id: UUID | None = None
    deploy_config: List[Dict[str, Any]]
    bud_cluster_benchmark_id: Optional[UUID] = None
    supported_endpoints: List[str]


class GetDeploymentConfigRequest(BaseModel):
    """Request body for getting the deployment config."""

    cluster_id: UUID
    workflow_id: UUID
    error_rate_threshold: float = 0.5
    concurrency: Optional[int] = None
    feedback: Optional[list[dict[str, Any]]] = None


class DeleteNamespaceRequest(BaseModel):
    """Request body for deleting a namespace."""

    cluster_config: Dict[str, Any]
    namespace: str
    platform: Optional[ClusterPlatformEnum] = None


class DeleteDeploymentRequest(CloudEventBase):
    """Request body for deleting a deployment."""

    cluster_id: UUID
    namespace: str


class WorkerData(BaseModel):
    """Worker data."""

    cluster_id: Optional[UUID] = None
    namespace: Optional[str] = None
    name: str
    status: str
    node_name: str
    device_name: str
    utilization: Optional[str] = None
    hardware: str
    uptime: str
    last_restart_datetime: Optional[datetime] = None
    last_updated_datetime: Optional[datetime] = None
    created_datetime: datetime
    node_ip: str
    cores: int
    memory: str
    deployment_name: str
    deployment_status: Optional[DeploymentStatusEnum] = None
    reason: Optional[str] = None
    concurrency: int


class WorkerInfo(WorkerData):
    """Worker info."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID


class WorkerDetailResponse(SuccessResponse):
    """Worker detail response."""

    worker: WorkerInfo


class LogEntry(BaseModel):
    """Represents a single log entry from a Kubernetes pod."""

    timestamp: Optional[datetime] = Field(None, description="ISO-formatted timestamp when the log entry was created")
    message: Optional[str] = Field(None, description="The actual log message content")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"timestamp": "2023-10-01T12:34:56.789012+00:00", "message": " Starting model..."}
        }
    )


class PodLogs(BaseModel):
    """Container for all logs from a specific Kubernetes pod."""

    pod_name: Optional[str] = Field(None, description="Name of the Kubernetes pod")
    namespace: Optional[str] = Field(None, description="Kubernetes namespace containing the pod")
    logs: Optional[List[LogEntry]] = Field(None, description="List of log entries from the pod")
    retrieved_at: Optional[datetime] = Field(
        default_factory=datetime.now, description="Timestamp when the logs were retrieved"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pod_name": "nginx-pod",
                "namespace": "default",
                "logs": [
                    {"timestamp": "2023-10-01T12:34:56.789012+00:00", "message": " Starting nginx server..."},
                    {"timestamp": "2023-10-01T12:34:57.123456+00:00", "message": " Server started successfully"},
                ],
                "container": "nginx",
                "retrieved_at": "2023-10-01T12:35:00.000000+00:00",
            }
        }
    )


class WorkerLogsResponse(SuccessResponse):
    """Worker logs response."""

    logs: Any


class WorkerInfoResponse(PaginatedSuccessResponse):
    """Response body for getting worker info."""

    workers: List[WorkerInfo]


class WorkerInfoFilter(BaseModel):
    """Filter for worker info."""

    status: str | None = None
    hardware: str | None = None
    utilization_min: int | None = None
    utilization_max: int | None = None


class DeleteWorkerRequest(CloudEventBase):
    """Request body for deleting a worker."""

    worker_id: UUID


class DeleteWorkerActivityRequest(BaseModel):
    """Request body for deleting a worker."""

    cluster_id: UUID
    worker_name: str
    namespace: str
    cluster_config: dict[str, Any]
    platform: ClusterPlatformEnum
    deployment_name: str
    ingress_url: str


class DeployQuantizationRequest(CloudEventBase):
    """Request body for deploying quantization."""

    cluster_id: UUID
    simulator_id: UUID
    model: str
    model_size: int
    device_type: str
    quantization_name: str
    quantization_config: dict[str, Any]
    hf_token: Optional[str] = None
    platform: Optional[ClusterPlatformEnum] = None
    cluster_config: dict[str, Any] | None = None
    simulator_config: List[Dict[str, Any]] | None = None
    namespace: str | None = None


class DeployQuantizationActivityRequest(BaseModel):
    """Request body for deploying quantization."""

    cluster_config: str
    simulator_config: List[Dict[str, Any]] | None = None
    namespace: str
    platform: ClusterPlatformEnum
    model: str
    quantization_name: str
    quantization_config: dict[str, Any] | None = None


class UpdateQuantizationStatusRequest(DeployQuantizationRequest):
    """Request body for updating the quantization status."""

    main_workflow_id: UUID


class WorkerMetricsResponse(SuccessResponse):
    """Worker metrics response."""

    data: Dict[str, Any]


class AdapterRequest(CloudEventBase):
    """Request body for adding an adapter."""

    cluster_id: UUID
    namespace: str
    adapters: List[Dict[str, Any]]
    adapter_path: str
    adapter_name: str
    ingress_url: str
    endpoint_name: str
    action: Literal["add", "delete"]
    adapter_id: Optional[UUID] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    model_max_context_length: Optional[int] = None


class DeployAdapterActivityRequest(BaseModel):
    cluster_config: str
    simulator_config: List[Dict[str, Any]]
    namespace: str
    platform: ClusterPlatformEnum
    adapters: List[Dict[str, Any]]
    endpoint_name: str
    ingress_url: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    model_max_context_length: Optional[int] = None


class UpdateAdapterStatusRequest(AdapterRequest):
    main_workflow_id: UUID


# Deployment table schemas (for deployment tracking)
class DeploymentRecordCreate(BaseModel):
    """Schema for creating a deployment record in the database."""

    model_config = ConfigDict(protected_namespaces=())

    cluster_id: UUID
    namespace: str
    deployment_name: str
    endpoint_name: str
    model: str
    deployment_url: Optional[str] = None
    supported_endpoints: Optional[List[str]] = None
    concurrency: int
    number_of_replicas: int = 1
    deploy_config: Optional[List[Dict[str, Any]]] = None
    status: DeploymentStatusEnum
    workflow_id: Optional[UUID] = None
    simulator_id: Optional[UUID] = None
    credential_id: Optional[UUID] = None


class DeploymentRecordUpdate(BaseModel):
    """Schema for updating a deployment record in the database."""

    status: Optional[DeploymentStatusEnum] = None
    last_status_check: Optional[datetime] = None
    number_of_replicas: Optional[int] = None
    deployment_url: Optional[str] = None
    supported_endpoints: Optional[List[str]] = None


class DeploymentRecordResponse(BaseModel):
    """Schema for deployment record response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cluster_id: UUID
    namespace: str
    deployment_name: str
    endpoint_name: str
    model: str
    deployment_url: Optional[str]
    supported_endpoints: Optional[List[str]]
    concurrency: int
    number_of_replicas: int
    deploy_config: Optional[List[Dict[str, Any]]]
    status: DeploymentStatusEnum
    workflow_id: Optional[UUID]
    simulator_id: Optional[UUID]
    credential_id: Optional[UUID]
    last_status_check: Optional[datetime]
    created_at: datetime
    modified_at: datetime


# Activity request schemas for deployment record operations
class CreateDeploymentRecordActivityRequest(BaseModel):
    """Schema for create deployment record activity request."""

    model_config = ConfigDict(protected_namespaces=())

    cluster_id: UUID
    namespace: str
    deployment_name: str
    endpoint_name: str
    model: str
    deployment_url: Optional[str] = None
    supported_endpoints: Optional[List[str]] = None
    concurrency: int
    number_of_replicas: int = 1
    deploy_config: Optional[List[Dict[str, Any]]] = None
    status: DeploymentStatusEnum
    workflow_id: Optional[UUID] = None
    simulator_id: Optional[UUID] = None
    credential_id: Optional[UUID] = None


class DeleteDeploymentRecordActivityRequest(BaseModel):
    """Schema for delete deployment record activity request."""

    namespace: str


class UpdateAutoscaleRequest(BaseModel):
    """Request to update autoscale configuration for an existing deployment."""

    cluster_id: UUID
    namespace: str
    release_name: str
    budaiscaler: BudAIScalerConfig
    engine_type: str = "vllm"


class UpdateAutoscaleResponse(SuccessResponse):
    """Response for autoscale update operation."""

    namespace: str
    release_name: str
    autoscale_enabled: bool
    message: str
