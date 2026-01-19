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

import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from budmicroframe.commons.schemas import CloudEventBase, SuccessResponse
from pydantic import BaseModel, ConfigDict, Field, validator

from ..commons.constants import ClusterNodeTypeEnum, ClusterPlatformEnum, ClusterStatusEnum


class PlatformEnum(str, Enum):
    KUBERNETES = "kubernetes"
    OPENSHIFT = "openshift"


class ClusterBase(BaseModel):
    """Cluster base schema."""

    platform: ClusterPlatformEnum
    configuration: str
    host: str
    enable_master_node: bool
    ingress_url: str


class ClusterResponse(ClusterBase, SuccessResponse):
    """Represents a response when cluster is added successfully."""

    id: UUID
    status: ClusterStatusEnum
    reason: str | None

    model_config = ConfigDict(from_attributes=True)


class ClusterCreateRequest(CloudEventBase):
    """Represents a request to create a new cluster."""

    name: str
    enable_master_node: bool
    ingress_url: Optional[str] = None
    configuration: Optional[str] = Field(default=None, description="JSON string containing cluster configuration")

    credential_id: Optional[str] = Field(default=None, description="ID of the credential to use")
    provider_id: Optional[str] = Field(default=None, description="ID of the cloud provider")
    region: Optional[str] = Field(default=None, description="Cloud region for the cluster")
    credentials: Optional[str] = Field(default=None, description="JSON string containing credential details")
    cluster_type: str = Field(default="ON_PREM", description="Type of cluster to create")
    cloud_provider_unique_id: Optional[str] = Field(default=None, description="Unique ID of the cloud provider")

    @validator("credentials", pre=True)
    def ensure_json_string(cls, v):
        """Ensure values are stored as JSON strings."""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                json.loads(v)
                return v
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON string") from None
        else:
            return json.dumps(v)

    @property
    def config_dict(self) -> Dict[str, Any]:
        """Get the config dictionary."""
        return json.loads(self.configuration) if self.configuration else {}

    @property
    def credentials_dict(self) -> Dict[str, Any]:
        """Get the credentials dictionary."""
        return json.loads(self.credentials) if self.credentials else {}


class ClusterCreate(BaseModel):
    """Create cluster schema."""

    platform: ClusterPlatformEnum
    enable_master_node: bool
    configuration: str
    host: str
    status: ClusterStatusEnum
    ingress_url: str
    server_url: str

    @property
    def config_dict(self) -> Dict[str, Any]:
        """Get the config dictionary."""
        return json.loads(self.configuration) if self.configuration else {}


class ClusterNodeInfo(BaseModel):
    """Cluster node info schema."""

    cluster_id: UUID
    name: str
    internal_ip: Optional[str] = None
    type: ClusterNodeTypeEnum
    total_workers: Optional[int] = 0
    available_workers: Optional[int] = 0
    used_workers: Optional[int] = 0
    threads_per_core: Optional[int] = 0
    core_count: Optional[int] = 0
    hardware_info: List[Dict[str, Any]]
    status: bool
    status_sync_at: datetime


class ClusterNodeInfoResponse(ClusterNodeInfo):
    id: UUID
    created_at: Optional[datetime]
    modified_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ClusterStatusUpdate(BaseModel):
    """Update cluster request schema."""

    status: ClusterStatusEnum
    reason: str | None


class VerifyClusterConnection(BaseModel):
    """Verify cluster connection schema."""

    cluster_config: str
    platform: ClusterPlatformEnum

    @property
    def config_dict(self) -> Dict[str, Any]:
        """Get the config dictionary."""
        return json.loads(self.cluster_config) if self.cluster_config else {}


class ConfigureCluster(BaseModel):
    """Configure cluster schema."""

    config_dict: Dict[str, Any]
    platform: ClusterPlatformEnum
    hostname: str
    enable_master_node: bool
    ingress_url: str
    server_url: str


class FetchClusterInfo(ConfigureCluster):
    """Fetch cluster info schema."""

    name: str
    platform: ClusterPlatformEnum
    hostname: str
    enable_master_node: bool
    ingress_url: str
    server_url: str
    cluster_id: UUID


class ClusterDeleteRequest(CloudEventBase):
    """Represents a request to delete a cluster."""

    cluster_id: UUID
    cluster_config: Optional[dict] = None
    platform: Optional[ClusterPlatformEnum] = None

    # Cloud Specific
    cluster_type: Optional[str] = "ON_PREM"
    cloud_payload: Optional[str] = None

    @property
    def cloud_payload_dict(self) -> Dict[str, Any]:
        """Get the cloud_payload."""
        return json.loads(self.cloud_payload) if self.cloud_payload else {}


class DeleteCluster(BaseModel):
    """Delete cluster schema."""

    platform: Optional[ClusterPlatformEnum] = None
    cluster_config: Optional[dict] = None


class DetermineClusterPlatformRequest(BaseModel):
    """Represents a request to determine the cluster platform."""

    enable_master_node: bool
    cluster_config: str


class CheckDuplicateConfig(BaseModel):
    """Check duplicate config schema."""

    server_url: str
    platform: ClusterPlatformEnum


class NodeEventsCountSuccessResponse(SuccessResponse):
    """Node events count success response schema."""

    data: Dict[str, Any]


class NodeEventData(BaseModel):
    """Node event data schema."""

    type: str
    reason: str
    message: str
    count: int
    first_timestamp: str | None
    last_timestamp: str | None
    source: Dict[str, str]


class NodeEventsResponse(SuccessResponse):
    """Node events response schema."""

    data: Dict[str, Any] = {
        "events": [],
    }


class EditClusterRequest(BaseModel):
    """Edit cluster request schema."""

    ingress_url: str


# Cloud Managed Cluster Creator schemas
class CreateCloudProviderClusterRequest(CloudEventBase):
    """Request body for creating a cloud provider cluster."""

    name: str
    credential_id: str | None = None
    provider_id: str | None = None
    region: str
    credentials: str
    cluster_type: str | None = None

    # Allow extra fields
    model_config = ConfigDict(extra="allow")

    @property
    def config_dict(self) -> Dict[str, Any]:
        """Get the config dictionary."""
        return json.loads(self.credentials) if self.credentials else {}


class CreateCloudProviderClusterActivityRequest(BaseModel):
    """Response body for creating a cloud provider cluster."""

    name: str
    credential_id: str | None = None
    provider_id: str | None = None
    region: str | None = None
    credentials: str | None = None
    cluster_type: str | None = None
    cloud_provider_unique_id: str = ""

    # Allow extra fields
    model_config = ConfigDict(extra="allow")

    # JSON Conversion
    @property
    def config_credentials(self) -> Dict[str, Any]:
        """Get the config dictionary."""
        return json.loads(self.credentials) if self.credentials else {}


class HealthCheckStatus(BaseModel):
    """Individual health check status."""

    healthy: bool
    message: str
    count: Optional[int] = None
    details: Optional[Dict[str, Any]] = None


class ClusterHealthResponse(SuccessResponse):
    """Cluster health check response schema."""

    data: Dict[str, HealthCheckStatus]
