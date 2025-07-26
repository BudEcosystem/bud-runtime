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

import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from budmicroframe.commons.schemas import CloudEventBase, ResponseBase
from budmicroframe.commons.types import lowercase_string
from pydantic import BaseModel, Field, RootModel, model_validator

from budsim.commons.config import app_settings


class Device(BaseModel):
    name: str
    type: str
    available_count: int
    mem_per_GPU_in_GB: float
    hbm_bandwidth_in_GB_per_sec: float
    intra_node_bandwidth_in_GB_per_sec: float
    intra_node_min_message_latency: float
    peak_fp16_TFLOPS: float
    peak_i8_TFLOPS: float
    peak_i4_TFLOPS: float
    inter_node_bandwidth_in_GB_per_sec: float


class Node(BaseModel):
    name: str
    id: str
    devices: List[Device]
    status: bool


class Cluster(BaseModel):
    # name: str
    id: str
    nodes: List[Node]


class ClusterInfo(RootModel):
    root: List[Cluster]


class ClusterRecommendationRequest(CloudEventBase):
    """Request schema for cluster recommendations."""

    pretrained_model_uri: str
    is_proprietary_model: bool
    input_tokens: int
    output_tokens: int
    concurrency: int
    target_ttft: Optional[float] = None
    target_throughput_per_user: Optional[float] = None
    target_e2e_latency: Optional[float] = None
    cluster_id: Optional[uuid.UUID] = None
    is_quantization: bool = False
    quantization_method: Optional[str] = None
    quantization_type: Optional[str] = None

    @model_validator(mode="before")
    def validate_pretrained_model_uri(cls, values):
        """Validate and process the pretrained model URI."""
        if not values.get("pretrained_model_uri"):
            raise ValueError("pretrained_model_uri is required")
        if not values.get("is_proprietary_model"):
            local_model_path = Path(app_settings.model_registry_dir, values.get("pretrained_model_uri"))
            if local_model_path.exists():
                values["pretrained_model_uri"] = local_model_path.as_posix()
        return values

    @model_validator(mode="before")
    def validate_target_metrics(cls, values):
        """Validate target metrics for non-proprietary models."""
        if not values.get("is_proprietary_model") and any(
            v is None
            for v in (
                values.get("target_ttft"),
                values.get("target_throughput_per_user"),
                values.get("target_e2e_latency"),
            )
        ):
            raise ValueError(
                "target_ttft, target_throughput_per_user, and target_e2e_latency are required for non-proprietary models"
            )

        return values


class DeviceTypeMetrics(BaseModel):
    device_type: str
    num_replicas: int
    concurrency: int
    cost_per_million_tokens: float


class SimulationMetrics(BaseModel):
    """Response schema for simulation results."""

    device_types: List[DeviceTypeMetrics]
    replica: int
    concurrency: int
    ttft: float
    throughput_per_user: float
    e2e_latency: float
    error_rate: float
    cost_per_million_tokens: float

    def reset(self):
        """Reset all metrics to zero."""
        self.concurrency = 0
        self.ttft = 0
        self.throughput_per_user = 0
        self.e2e_latency = 0
        self.error_rate = 0
        self.num_replicas = 0


class ClusterMetrics(BaseModel):
    cluster_id: str
    metrics: SimulationMetrics
    quantized_metrics: Optional[SimulationMetrics] = None

    def reset(self):
        """Reset cluster metrics."""
        self.metrics.reset()
        self.quantized_metrics.reset() if self.quantized_metrics else None


class ClusterRecommendationResponse(ResponseBase):
    """Response schema for cluster recommendations."""

    object: lowercase_string = "cluster_recommendations"
    workflow_id: uuid.UUID
    recommendations: List[ClusterMetrics]
    created: int = Field(default_factory=lambda: int(time.time()))


class Feedback(BaseModel):
    config_id: str
    failed: bool
    reason: Optional[str] = None


class DeploymentConfigurationRequest(BaseModel):
    workflow_id: uuid.UUID
    cluster_id: Optional[str] = None
    error_rate_threshold: float = 0.5
    concurrency: Optional[int] = None
    feedback: Optional[List[Feedback]] = None


class DeviceConfiguration(BaseModel):
    config_id: str
    name: str
    type: str
    image: str
    memory: float
    num_cpus: int = -1
    args: Dict[str, Any]
    envs: Dict[str, Any]
    tp_size: int
    replica: int
    concurrency: int
    ttft: float
    throughput_per_user: float
    e2e_latency: float
    error_rate: float
    cost_per_million_tokens: float


class NodeConfiguration(BaseModel):
    id: str
    name: str
    devices: List[DeviceConfiguration]


class DeploymentConfigurationResponse(ResponseBase):
    object: lowercase_string = "deployment_configuration"
    id: str
    nodes: List[NodeConfiguration]
    replica: int
    concurrency: int
    ttft: float
    throughput_per_user: float
    e2e_latency: float
    error_rate: float
    cost_per_million_tokens: float

    def reset(self):
        """Reset the simulation state by clearing nodes and replica count."""
        self.nodes = []
        self.num_replicas = 0
        self.concurrency = 0
        self.ttft = 0
        self.throughput_per_user = 0
        self.e2e_latency = 0
        self.error_rate = 0
