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

"""Pydantic schemas for BudCluster client."""

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JobType(StrEnum):
    """Types of jobs that can be created in BudCluster.

    Note: All ML model deployments (LLMs, embedders, rerankers) use MODEL_DEPLOYMENT.
    BudCluster determines specific deployment config from model metadata.
    """

    MODEL_DEPLOYMENT = "model_deployment"
    HELM_DEPLOY = "helm_deploy"
    GENERIC = "generic"


class JobStatus(StrEnum):
    """Status of a job in BudCluster."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobSource(StrEnum):
    """Source of a job creation."""

    BUDUSECASES = "BUDUSECASES"
    BUDAPP = "BUDAPP"
    MANUAL = "MANUAL"


class ClusterStatus(StrEnum):
    """Status of a cluster."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    PROVISIONING = "provisioning"
    ERROR = "error"


class JobCreateRequest(BaseModel):
    """Request schema for creating a job."""

    model_config = ConfigDict(use_enum_values=True)

    name: str = Field(..., description="Job name")
    job_type: JobType = Field(..., description="Type of job")
    source: JobSource = Field(..., description="Source of the job")
    source_id: str = Field(..., description="ID from the source system")
    cluster_id: UUID = Field(..., description="Target cluster ID")
    config: dict[str, Any] = Field(default_factory=dict, description="Job configuration")
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata", description="Additional metadata")


class JobResponse(BaseModel):
    """Response schema for a job."""

    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)

    id: UUID = Field(..., description="Job ID")
    name: str = Field(..., description="Job name")
    job_type: JobType = Field(..., description="Type of job")
    status: JobStatus = Field(..., description="Current job status")
    cluster_id: UUID = Field(..., description="Target cluster ID")
    config: dict[str, Any] = Field(default_factory=dict, description="Job configuration")
    error_message: str | None = Field(None, description="Error message if failed")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    started_at: str | None = Field(None, description="Start timestamp")
    completed_at: str | None = Field(None, description="Completion timestamp")


class JobListResponse(BaseModel):
    """Response schema for listing jobs."""

    items: list[JobResponse] = Field(..., description="List of jobs")
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")


class JobStatusUpdateRequest(BaseModel):
    """Request schema for updating job status."""

    model_config = ConfigDict(use_enum_values=True)

    status: JobStatus = Field(..., description="New status")
    message: str | None = Field(None, description="Status message")


class ClusterInfoResponse(BaseModel):
    """Response schema for cluster information."""

    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(..., description="Cluster ID")
    name: str = Field(..., description="Cluster name")
    status: ClusterStatus = Field(..., description="Cluster status")
    provider: str = Field(..., description="Cloud provider")
    region: str = Field(..., description="Region")
    kubernetes_version: str = Field(..., description="K8s version")
    node_count: int = Field(..., description="Number of nodes")
    gpu_available: bool = Field(..., description="Whether GPU is available")
    gpu_count: int = Field(0, description="Number of GPUs")


class ClusterCapacityResponse(BaseModel):
    """Response schema for cluster capacity check."""

    cluster_id: UUID = Field(..., description="Cluster ID")
    has_capacity: bool = Field(..., description="Whether cluster has capacity")
    available_cpu: int = Field(..., description="Available CPU cores")
    available_memory: str = Field(..., description="Available memory")
    available_gpu: int = Field(0, description="Available GPUs")
    available_gpu_memory: str | None = Field(None, description="Available GPU memory")
