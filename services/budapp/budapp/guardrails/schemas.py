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

"""Guardrail Pydantic schemas for API validation and serialization."""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from budapp.commons.constants import (
    GuardrailDeploymentStatusEnum,
    GuardrailDeploymentTypeEnum,
    GuardrailProviderTypeEnum,
)
from budapp.commons.schemas import PaginatedSuccessResponse, SuccessResponse, Tag
from budapp.model_ops.schemas import Provider


# Base schemas
class GuardrailBaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(from_attributes=True)


# Extended Provider schema for guardrails
class GuardrailProviderInfo(Provider):
    """Extended provider schema with guardrail-specific fields."""

    is_active: bool = True
    configuration_schema: Optional[Dict] = None
    object: str = "guardrail.provider"


# Rule schemas
class GuardrailRuleBase(GuardrailBaseSchema):
    """Base schema for guardrail rules."""

    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    scanner_types: Optional[List[str]] = None
    modality_types: Optional[List[str]] = None
    guard_types: Optional[List[str]] = None
    examples: Optional[List[str]] = None
    configuration: Optional[Dict] = None
    is_enabled: bool = True
    is_custom: bool = False


class GuardrailRuleCreate(GuardrailRuleBase):
    """Schema for creating a guardrail rule."""

    probe_id: UUID


class GuardrailRuleUpdate(GuardrailBaseSchema):
    """Schema for updating a guardrail rule."""

    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    scanner_types: Optional[List[str]] = None
    modality_types: Optional[List[str]] = None
    guard_types: Optional[List[str]] = None
    examples: Optional[List[str]] = None
    configuration: Optional[Dict] = None
    is_enabled: Optional[bool] = None
    is_custom: Optional[bool] = None


class GuardrailRuleResponse(GuardrailBaseSchema):
    """Schema for guardrail rule responses."""

    id: UUID
    probe_id: UUID
    name: str
    description: Optional[str] = None
    scanner_types: Optional[List[str]] = None
    modality_types: Optional[List[str]] = None
    guard_types: Optional[List[str]] = None
    examples: Optional[List[str]] = None
    configuration: Optional[Dict] = None
    is_enabled: bool
    is_custom: bool
    created_at: datetime
    modified_at: datetime
    object: str = "guardrail.rule"


# Probe schemas
class GuardrailProbeBase(GuardrailBaseSchema):
    """Base schema for guardrail probes."""

    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    tags: Optional[List[Tag]] = None


class GuardrailProbeCreate(GuardrailProbeBase):
    """Schema for creating a guardrail probe."""

    provider_id: Optional[UUID] = None
    provider_type: GuardrailProviderTypeEnum
    user_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    is_custom: Optional[bool] = None  # Optional override, auto-determined from provider if not specified


class GuardrailProbeUpdate(GuardrailBaseSchema):
    """Schema for updating a guardrail probe."""

    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    tags: Optional[List[Tag]] = None
    provider_type: Optional[GuardrailProviderTypeEnum] = None
    is_custom: Optional[bool] = None  # Allow updating is_custom flag


class GuardrailProbeResponse(GuardrailProbeBase):
    """Schema for guardrail probe responses."""

    id: UUID
    provider_id: UUID
    provider_type: GuardrailProviderTypeEnum
    provider: Optional[GuardrailProviderInfo] = None
    is_custom: bool = False  # Computed from provider type
    created_by: Optional[UUID] = None
    user_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    created_at: datetime
    modified_at: datetime
    rules: List[GuardrailRuleResponse] = []
    object: str = "guardrail.probe"


class GuardrailProbeListResponse(GuardrailBaseSchema):
    """Schema for guardrail probe list responses."""

    id: UUID
    name: str
    description: Optional[str] = None
    tags: Optional[List[Tag]] = None
    provider_id: UUID
    provider_name: Optional[str] = None
    provider_type: Optional[GuardrailProviderTypeEnum] = None
    is_custom: bool = False
    rule_count: int = 0
    object: str = "guardrail.probe.summary"


# Deployment rule configuration schemas
class GuardrailDeploymentRuleBase(GuardrailBaseSchema):
    """Base schema for deployment rule configurations."""

    rule_id: UUID
    is_enabled: bool = True
    configuration: Optional[Dict] = None
    threshold_override: Optional[float] = Field(None, ge=0.0, le=1.0)


class GuardrailDeploymentRuleCreate(GuardrailDeploymentRuleBase):
    """Schema for creating deployment rule configuration."""

    pass


class GuardrailDeploymentRuleResponse(GuardrailDeploymentRuleBase):
    """Schema for deployment rule configuration responses."""

    id: UUID
    rule_name: Optional[str] = None
    object: str = "guardrail.deployment.rule"


# Selection schemas for sparse probe/rule selection
class RuleSelection(GuardrailBaseSchema):
    """Schema for sparse rule selection."""

    rule_id: UUID
    enabled: bool


class ProbeSelection(GuardrailBaseSchema):
    """Schema for sparse probe selection."""

    probe_id: UUID
    enabled: bool
    rule_selections: Optional[List[RuleSelection]] = []


# Deployment probe schemas
class GuardrailDeploymentProbeBase(GuardrailBaseSchema):
    """Base schema for deployment probe associations."""

    probe_id: UUID
    is_enabled: bool = True
    configuration: Optional[Dict] = None
    threshold_override: Optional[float] = Field(None, ge=0.0, le=1.0)


class GuardrailDeploymentProbeCreate(GuardrailDeploymentProbeBase):
    """Schema for creating deployment probe association."""

    rules: Optional[List[GuardrailDeploymentRuleCreate]] = []


class GuardrailDeploymentProbeResponse(GuardrailDeploymentProbeBase):
    """Schema for deployment probe responses."""

    id: UUID
    deployment_id: UUID
    probe_name: Optional[str] = None
    rules: List[GuardrailDeploymentRuleResponse] = []
    object: str = "guardrail.deployment.probe"


# Deployment schemas
class GuardrailDeploymentBase(GuardrailBaseSchema):
    """Base schema for guardrail deployments."""

    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    deployment_type: GuardrailDeploymentTypeEnum
    endpoint_id: Optional[UUID] = None
    configuration: Optional[Dict] = None
    default_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    guardrail_types: Optional[List[str]] = None

    @field_validator("endpoint_id")
    def validate_deployment_fields(cls, v, info):
        """Validate that endpoint_id is set based on deployment_type."""
        if "deployment_type" in info.data:
            deployment_type = info.data["deployment_type"]
            field_name = info.field_name

            if (
                deployment_type == GuardrailDeploymentTypeEnum.ENDPOINT_MAPPED
                and field_name == "endpoint_id"
                and not v
            ):
                raise ValueError("endpoint_id is required for endpoint_mapped deployments")

        return v


class GuardrailDeploymentCreate(GuardrailDeploymentBase):
    """Schema for creating a guardrail deployment.

    Uses sparse probe selection:
    - Empty probe_selections list = enable all probes from selected provider
    - Non-empty probe_selections = apply only specified probe/rule overrides
    """

    project_id: UUID
    guardrail_types: Optional[List[str]] = None
    probe_selections: Optional[List[ProbeSelection]] = []  # Empty = all probes enabled


class GuardrailDeploymentUpdate(GuardrailBaseSchema):
    """Schema for updating a guardrail deployment."""

    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    probes: Optional[List[GuardrailDeploymentProbeCreate]] = None
    status: Optional[GuardrailDeploymentStatusEnum] = None
    configuration: Optional[Dict] = None
    guardrail_types: Optional[List[str]] = None


class GuardrailDeploymentResponse(GuardrailDeploymentBase):
    """Schema for guardrail deployment responses."""

    id: UUID
    status: GuardrailDeploymentStatusEnum
    user_id: UUID
    project_id: UUID
    guardrail_types: Optional[List[str]] = None
    probes: List[GuardrailDeploymentProbeResponse] = []
    created_at: datetime
    modified_at: datetime
    object: str = "guardrail.deployment"


class GuardrailDeploymentListResponse(GuardrailBaseSchema):
    """Schema for guardrail deployment list responses."""

    id: UUID
    name: str
    deployment_type: GuardrailDeploymentTypeEnum
    endpoint_id: Optional[UUID] = None
    status: GuardrailDeploymentStatusEnum
    guardrail_types: Optional[List[str]] = None
    probe_count: int = 0
    enabled_probe_count: int = 0
    created_at: datetime
    object: str = "guardrail.deployment.summary"


# List response schemas
class GuardrailProbeListRequestSchema(GuardrailBaseSchema):
    """Schema for probe list request parameters."""

    tags: Optional[List[str]] = None
    provider_id: Optional[UUID] = None
    provider_type: Optional[GuardrailProviderTypeEnum] = None
    user_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    endpoint_id: Optional[UUID] = None
    search: Optional[str] = None


class GuardrailProbeListResponseSchema(PaginatedSuccessResponse):
    """Schema for probe list response."""

    model_config = ConfigDict(extra="ignore")

    probes: List[GuardrailProbeListResponse] = []
    object: str = "guardrail.probe.list"


class GuardrailDeploymentListRequestSchema(GuardrailBaseSchema):
    """Schema for deployment list request parameters."""

    project_id: Optional[UUID] = None
    endpoint_id: Optional[UUID] = None
    deployment_type: Optional[GuardrailDeploymentTypeEnum] = None
    status: Optional[GuardrailDeploymentStatusEnum] = None
    search: Optional[str] = None


class GuardrailDeploymentListResponseSchema(PaginatedSuccessResponse):
    """Schema for deployment list response."""

    model_config = ConfigDict(extra="ignore")

    deployments: List[GuardrailDeploymentListResponse] = []
    object: str = "guardrail.deployment.list"


# Workflow schemas
class GuardrailDeploymentWorkflowStepData(GuardrailBaseSchema):
    """Schema for guardrail deployment workflow step data."""

    # Step 1: Probe selection
    probe_selections: Optional[List[ProbeSelection]] = []  # New sparse selection format
    provider_id: Optional[UUID] = None  # Provider ID when probe_selections is empty

    # Step 2: Deployment type
    deployment_type: Optional[GuardrailDeploymentTypeEnum] = None

    # Step 3: Project selection
    project_id: Optional[UUID] = None

    # Step 4: Endpoint selection (for endpoint_mapped)
    endpoint_id: Optional[UUID] = None

    # Step 5: Configuration
    guard_types: Optional[List[str]] = None
    threshold: Optional[float] = None

    # Step 6: ETA
    estimated_deployment_time: Optional[int] = None  # seconds

    # Step 7: Deployment status
    deployment_status: Optional[str] = None
    deployment_message: Optional[str] = None
    deployment_id: Optional[UUID] = None


class CreateGuardrailDeploymentWorkflowRequest(GuardrailBaseSchema):
    """Request schema for creating/updating guardrail deployment workflow."""

    workflow_id: Optional[UUID] = None
    step_number: int = Field(..., ge=1, le=7)
    workflow_total_steps: int = Field(default=7)

    # Step-specific data
    probe_selections: Optional[List[ProbeSelection]] = []  # New sparse selection format
    provider_id: Optional[UUID] = None  # Provider ID when probe_selections is empty (optional for workflow)
    deployment_type: Optional[GuardrailDeploymentTypeEnum] = None
    project_id: Optional[UUID] = None
    endpoint_id: Optional[UUID] = None
    guard_types: Optional[List[str]] = None
    threshold: Optional[float] = None

    # Workflow control
    trigger_workflow: bool = Field(default=False)
    deployment_name: Optional[str] = Field(None, max_length=255)
    deployment_description: Optional[str] = None


class CreateGuardrailDeploymentWorkflowResponse(SuccessResponse):
    """Response schema for creating/updating guardrail deployment workflow."""

    workflow_id: UUID
    status: str
    current_step: int
    total_steps: int
    reason: Optional[str] = None
    workflow_steps: Optional[GuardrailDeploymentWorkflowStepData] = None
    object: str = "guardrail.deployment.workflow"


class GuardrailProbeDetailResponse(SuccessResponse):
    """Detailed response schema for single probe."""

    probe: GuardrailProbeResponse
    object: str = "guardrail.probe.detail"


class GuardrailDeploymentDetailResponse(SuccessResponse):
    """Detailed response schema for single deployment."""

    deployment: GuardrailDeploymentResponse
    object: str = "guardrail.deployment.detail"


class ProbeTagSearchResponse(PaginatedSuccessResponse):
    """Schema for probe tag search response."""

    model_config = ConfigDict(extra="ignore")

    tags: List[str] = []
    object: str = "guardrail.probe.tags"


# Rule list schemas for paginated rules within a probe
class GuardrailRuleListRequestSchema(GuardrailBaseSchema):
    """Schema for rule list request parameters within a probe."""

    search: Optional[str] = None
    scanner_types: Optional[List[str]] = None
    modality_types: Optional[List[str]] = None
    guard_types: Optional[List[str]] = None
    is_enabled: Optional[bool] = None
    is_custom: Optional[bool] = None


class GuardrailRuleListResponseSchema(PaginatedSuccessResponse):
    """Schema for paginated rule list response."""

    model_config = ConfigDict(extra="ignore")

    rules: List[GuardrailRuleResponse] = []
    object: str = "guardrail.rule.list"
