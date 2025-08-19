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

from budapp.commons.constants import GuardrailDeploymentStatusEnum, GuardrailDeploymentTypeEnum, GuardrailProviderEnum
from budapp.commons.schemas import Tag


# Base schemas
class GuardrailBaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(from_attributes=True)


# Provider schemas
class GuardrailProviderBase(GuardrailBaseSchema):
    """Base schema for guardrail providers."""

    name: str = Field(..., max_length=255)
    display_name: str = Field(..., max_length=255)
    provider_type: GuardrailProviderEnum
    description: Optional[str] = None
    configuration_schema: Optional[Dict] = None
    is_active: bool = True


class GuardrailProviderCreate(GuardrailProviderBase):
    """Schema for creating a guardrail provider."""

    user_id: Optional[UUID] = None
    project_id: Optional[UUID] = None


class GuardrailProviderUpdate(GuardrailBaseSchema):
    """Schema for updating a guardrail provider."""

    name: Optional[str] = Field(None, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    configuration_schema: Optional[Dict] = None
    is_active: Optional[bool] = None


class GuardrailProviderResponse(GuardrailProviderBase):
    """Schema for guardrail provider responses."""

    id: UUID
    created_by: Optional[UUID] = None
    user_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    created_at: datetime
    modified_at: datetime


# Scanner type schemas
class GuardrailScannerTypeBase(GuardrailBaseSchema):
    """Base schema for scanner types."""

    name: str = Field(..., max_length=100)
    display_name: str = Field(..., max_length=255)
    description: Optional[str] = None
    supported_modalities: List[str]
    configuration_schema: Optional[Dict] = None


class GuardrailScannerTypeCreate(GuardrailScannerTypeBase):
    """Schema for creating a scanner type."""

    pass


class GuardrailScannerTypeResponse(GuardrailScannerTypeBase):
    """Schema for scanner type responses."""

    id: UUID
    created_at: datetime
    modified_at: datetime


# Modality type schemas
class GuardrailModalityTypeBase(GuardrailBaseSchema):
    """Base schema for modality types."""

    name: str = Field(..., max_length=100)
    display_name: str = Field(..., max_length=255)
    description: Optional[str] = None


class GuardrailModalityTypeCreate(GuardrailModalityTypeBase):
    """Schema for creating a modality type."""

    pass


class GuardrailModalityTypeResponse(GuardrailModalityTypeBase):
    """Schema for modality type responses."""

    id: UUID
    created_at: datetime
    modified_at: datetime


# Guard type schemas
class GuardrailGuardTypeBase(GuardrailBaseSchema):
    """Base schema for guard types."""

    name: str = Field(..., max_length=100)
    display_name: str = Field(..., max_length=255)
    description: Optional[str] = None


class GuardrailGuardTypeCreate(GuardrailGuardTypeBase):
    """Schema for creating a guard type."""

    pass


class GuardrailGuardTypeResponse(GuardrailGuardTypeBase):
    """Schema for guard type responses."""

    id: UUID
    created_at: datetime
    modified_at: datetime


# Rule schemas
class GuardrailRuleBase(GuardrailBaseSchema):
    """Base schema for guardrail rules."""

    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    scanner_type_ids: List[UUID]
    modality_type_ids: List[UUID]
    guard_type_ids: List[UUID]
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
    scanner_type_ids: Optional[List[UUID]] = None
    modality_type_ids: Optional[List[UUID]] = None
    guard_type_ids: Optional[List[UUID]] = None
    examples: Optional[List[str]] = None
    configuration: Optional[Dict] = None
    is_enabled: Optional[bool] = None


class GuardrailRuleResponse(GuardrailBaseSchema):
    """Schema for guardrail rule responses."""

    id: UUID
    probe_id: UUID
    name: str
    description: Optional[str] = None
    scanner_types: List[GuardrailScannerTypeResponse]
    modality_types: List[GuardrailModalityTypeResponse]
    guard_types: List[GuardrailGuardTypeResponse]
    examples: Optional[List[str]] = None
    configuration: Optional[Dict] = None
    is_enabled: bool
    is_custom: bool
    created_at: datetime
    modified_at: datetime


# Probe schemas
class GuardrailProbeBase(GuardrailBaseSchema):
    """Base schema for guardrail probes."""

    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    tags: Optional[List[Tag]] = None


class GuardrailProbeCreate(GuardrailProbeBase):
    """Schema for creating a guardrail probe."""

    provider_id: UUID
    user_id: Optional[UUID] = None
    project_id: Optional[UUID] = None


class GuardrailProbeUpdate(GuardrailBaseSchema):
    """Schema for updating a guardrail probe."""

    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    tags: Optional[List[Tag]] = None


class GuardrailProbeResponse(GuardrailProbeBase):
    """Schema for guardrail probe responses."""

    id: UUID
    provider_id: UUID
    provider: Optional[GuardrailProviderResponse] = None
    is_custom: bool = False  # Computed from provider type
    created_by: Optional[UUID] = None
    user_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    created_at: datetime
    modified_at: datetime
    rules: List[GuardrailRuleResponse] = []


class GuardrailProbeListResponse(GuardrailBaseSchema):
    """Schema for guardrail probe list responses."""

    id: UUID
    name: str
    description: Optional[str] = None
    tags: Optional[List[Tag]] = None
    provider_id: UUID
    provider_name: Optional[str] = None
    provider_type: Optional[GuardrailProviderEnum] = None
    is_custom: bool = False
    rule_count: int = 0


# Deployment rule configuration schemas
class GuardrailDeploymentRuleConfigBase(GuardrailBaseSchema):
    """Base schema for deployment rule configurations."""

    rule_id: UUID
    is_enabled: bool = True
    configuration: Optional[Dict] = None
    threshold_override: Optional[float] = Field(None, ge=0.0, le=1.0)


class GuardrailDeploymentRuleConfigCreate(GuardrailDeploymentRuleConfigBase):
    """Schema for creating deployment rule configuration."""

    pass


class GuardrailDeploymentRuleConfigResponse(GuardrailDeploymentRuleConfigBase):
    """Schema for deployment rule configuration responses."""

    id: UUID
    deployment_probe_id: UUID
    rule_name: Optional[str] = None
    is_overridden: bool = False
    effective_configuration: Optional[Dict] = None
    created_at: datetime
    modified_at: datetime


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

    rule_configs: Optional[List[GuardrailDeploymentRuleConfigCreate]] = []


class GuardrailDeploymentProbeResponse(GuardrailDeploymentProbeBase):
    """Schema for deployment probe responses."""

    id: UUID
    deployment_id: UUID
    probe_name: Optional[str] = None
    rules: List[GuardrailDeploymentRuleConfigResponse] = []
    created_at: datetime
    modified_at: datetime


# Deployment schemas
class GuardrailDeploymentBase(GuardrailBaseSchema):
    """Base schema for guardrail deployments."""

    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    deployment_type: GuardrailDeploymentTypeEnum
    endpoint_id: Optional[UUID] = None
    deployment_endpoint_url: Optional[str] = None
    configuration: Optional[Dict] = None
    default_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)

    @field_validator("endpoint_id", "deployment_endpoint_url")
    def validate_deployment_fields(cls, v, info):
        """Validate that endpoint_id or deployment_endpoint_url is set based on deployment_type."""
        if "deployment_type" in info.data:
            deployment_type = info.data["deployment_type"]
            field_name = info.field_name

            if (
                deployment_type == GuardrailDeploymentTypeEnum.ENDPOINT_MAPPED
                and field_name == "endpoint_id"
                and not v
            ):
                raise ValueError("endpoint_id is required for endpoint_mapped deployments")
            elif (
                deployment_type == GuardrailDeploymentTypeEnum.STANDALONE
                and field_name == "deployment_endpoint_url"
                and not v
            ):
                raise ValueError("deployment_endpoint_url is required for standalone deployments")

        return v


class GuardrailDeploymentCreate(GuardrailDeploymentBase):
    """Schema for creating a guardrail deployment.

    Uses sparse probe selection:
    - Empty probe_selections list = enable all probes from selected providers
    - Non-empty probe_selections = apply only specified probe/rule overrides
    """

    project_id: UUID
    probes: Optional[List[GuardrailDeploymentProbeCreate]] = None  # Deprecated, use probe_selections
    probe_selections: Optional[List[ProbeSelection]] = []  # Empty = all probes enabled
    provider_ids: Optional[List[UUID]] = []  # Provider IDs to fetch all probes from when probe_selections is empty


class GuardrailDeploymentUpdate(GuardrailBaseSchema):
    """Schema for updating a guardrail deployment."""

    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    probes: Optional[List[GuardrailDeploymentProbeCreate]] = None
    status: Optional[GuardrailDeploymentStatusEnum] = None
    configuration: Optional[Dict] = None


class GuardrailDeploymentResponse(GuardrailDeploymentBase):
    """Schema for guardrail deployment responses."""

    id: UUID
    status: GuardrailDeploymentStatusEnum
    user_id: UUID
    project_id: UUID
    probes: List[GuardrailDeploymentProbeResponse] = []
    created_at: datetime
    modified_at: datetime


class GuardrailDeploymentListResponse(GuardrailBaseSchema):
    """Schema for guardrail deployment list responses."""

    id: UUID
    name: str
    deployment_type: GuardrailDeploymentTypeEnum
    endpoint_id: Optional[UUID] = None
    status: GuardrailDeploymentStatusEnum
    probe_count: int = 0
    enabled_probe_count: int = 0
    created_at: datetime


# List response schemas
class GuardrailProbeListRequestSchema(GuardrailBaseSchema):
    """Schema for probe list request parameters."""

    tags: Optional[List[str]] = None
    provider_id: Optional[UUID] = None
    provider_type: Optional[GuardrailProviderEnum] = None
    user_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    endpoint_id: Optional[UUID] = None
    search: Optional[str] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class GuardrailProbeListResponseSchema(GuardrailBaseSchema):
    """Schema for probe list response."""

    probes: List[GuardrailProbeListResponse]
    total: int
    page: int
    page_size: int


class GuardrailDeploymentListRequestSchema(GuardrailBaseSchema):
    """Schema for deployment list request parameters."""

    project_id: Optional[UUID] = None
    endpoint_id: Optional[UUID] = None
    deployment_type: Optional[GuardrailDeploymentTypeEnum] = None
    status: Optional[GuardrailDeploymentStatusEnum] = None
    search: Optional[str] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class GuardrailDeploymentListResponseSchema(GuardrailBaseSchema):
    """Schema for deployment list response."""

    deployments: List[GuardrailDeploymentListResponse]
    total: int
    page: int
    page_size: int


# Workflow schemas
class GuardrailDeploymentWorkflowStepData(GuardrailBaseSchema):
    """Schema for guardrail deployment workflow step data."""

    # Step 1: Probe selection
    selected_probes: Optional[List[UUID]] = None  # Deprecated
    selected_rules: Optional[Dict[UUID, List[UUID]]] = None  # Deprecated
    probe_selections: Optional[List[ProbeSelection]] = []  # New sparse selection format
    provider_ids: Optional[List[UUID]] = []  # Provider IDs when probe_selections is empty

    # Step 2: Deployment type
    deployment_type: Optional[GuardrailDeploymentTypeEnum] = None

    # Step 3: Project selection
    project_id: Optional[UUID] = None

    # Step 4: Endpoint selection (for endpoint_mapped)
    endpoint_id: Optional[UUID] = None
    deployment_endpoint_url: Optional[str] = None  # for standalone

    # Step 5: Configuration
    guard_types: Optional[Dict[UUID, List[UUID]]] = None  # probe_id -> [guard_type_ids]
    thresholds: Optional[Dict[UUID, float]] = None  # probe_id -> threshold
    probe_configs: Optional[Dict[UUID, Dict]] = None  # probe_id -> configuration
    rule_configs: Optional[Dict[str, Dict]] = None  # f"{probe_id}:{rule_id}" -> configuration

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
    selected_probes: Optional[List[UUID]] = None  # Deprecated, use probe_selections
    selected_rules: Optional[Dict[UUID, List[UUID]]] = None  # Deprecated, use probe_selections
    probe_selections: Optional[List[ProbeSelection]] = []  # New sparse selection format
    provider_ids: Optional[List[UUID]] = []  # Provider IDs when probe_selections is empty
    deployment_type: Optional[GuardrailDeploymentTypeEnum] = None
    project_id: Optional[UUID] = None
    endpoint_id: Optional[UUID] = None
    deployment_endpoint_url: Optional[str] = None
    guard_types: Optional[Dict[UUID, List[UUID]]] = None
    thresholds: Optional[Dict[UUID, float]] = None
    probe_configs: Optional[Dict[UUID, Dict]] = None
    rule_configs: Optional[Dict[str, Dict]] = None

    # Workflow control
    trigger_workflow: bool = Field(default=False)
    deployment_name: Optional[str] = Field(None, max_length=255)
    deployment_description: Optional[str] = None


class ProbeTagSearchResponse(GuardrailBaseSchema):
    """Schema for probe tag search response."""

    tags: List[str]
    total: int
    page: int
    page_size: int


# Rule list schemas for paginated rules within a probe
class GuardrailRuleListRequestSchema(GuardrailBaseSchema):
    """Schema for rule list request parameters within a probe."""

    search: Optional[str] = None
    scanner_type_ids: Optional[List[UUID]] = None
    modality_type_ids: Optional[List[UUID]] = None
    guard_type_ids: Optional[List[UUID]] = None
    is_enabled: Optional[bool] = None
    is_custom: Optional[bool] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class GuardrailRuleListResponseSchema(GuardrailBaseSchema):
    """Schema for paginated rule list response."""

    rules: List[GuardrailRuleResponse]
    total: int
    page: int
    page_size: int
