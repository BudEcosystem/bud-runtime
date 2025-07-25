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
    FAILED = "failed"


class WorkerStatusEnum(str, Enum):
    """Worker status enumeration."""

    PENDING = "Pending"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    UNKNOWN = "Unknown"
    DELETING = "Deleting"


class TransferModelRequest(BaseModel):
    """Request body for transferring a model."""

    model_config = ConfigDict(protected_namespaces=())

    model: str
    endpoint_name: str
    cluster_config: str | None = None
    simulator_config: List[Dict[str, Any]] | None = None
    platform: Optional[ClusterPlatformEnum] = None
    existing_deployment_namespace: Optional[str] = None
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


class CommonDeploymentParams(BaseModel):
    cluster_id: UUID
    simulator_id: Optional[UUID] = None
    endpoint_name: str
    model: str
    concurrency: int
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    podscaler: dict | None = None


class DeploymentCreateRequest(CloudEventBase, CommonDeploymentParams, RunBenchmarkParams):
    """Request body for creating a deployment."""

    hf_token: Optional[str] = None
    target_ttft: Optional[int] = None
    target_e2e_latency: Optional[int] = None
    target_throughput_per_user: Optional[int] = None
    credential_id: Optional[UUID] = None
    existing_deployment_namespace: Optional[str] = None
    provider: Optional[str] = None


class LocalDeploymentCreateRequest(CloudEventBase, CommonDeploymentParams, RunBenchmarkParams):
    """Request body for creating a local deployment."""

    hf_token: Optional[str] = None
    target_ttft: Optional[int] = None
    target_e2e_latency: Optional[int] = None
    target_throughput_per_user: Optional[int] = None
    namespace: Optional[str] = None


class CloudDeploymentCreateRequest(CloudEventBase, CommonDeploymentParams, RunBenchmarkParams):
    """Request body for creating a cloud deployment."""

    credential_id: UUID
    namespace: Optional[str] = None


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


class UpdateModelTransferStatusRequest(DeploymentWorkflowRequest):
    """Request body for updating the model transfer status."""

    main_workflow_id: UUID
    workflow_name: str


class VerifyDeploymentHealthRequest(BaseModel):
    """Request body for verifying the engine health."""

    cluster_id: UUID
    cluster_config: str
    namespace: str
    ingress_url: str
    cloud_model: bool = False
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


class WorkflowRunPerformanceBenchmarkRequest(BaseModel):
    """Request body for running the performance benchmark."""

    cluster_config: str
    namespace: str
    benchmark_request: RunPerformanceBenchmarkRequest
    provider_type: Literal["local", "cloud"] = "local"
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


class UpdateDeploymentStatusRequest(BaseModel):
    """Request body for updating the deployment status."""

    deployment_name: str
    cluster_id: UUID
    cloud_model: bool = False


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


class DeployAdapterActivityRequest(BaseModel):
    cluster_config: str
    simulator_config: List[Dict[str, Any]]
    namespace: str
    platform: ClusterPlatformEnum
    adapters: List[Dict[str, Any]]
    endpoint_name: str
    ingress_url: str


class UpdateAdapterStatusRequest(AdapterRequest):
    main_workflow_id: UUID
