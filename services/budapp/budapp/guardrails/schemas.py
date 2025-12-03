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
from typing import List, Optional

from pydantic import UUID4, BaseModel, ConfigDict, Field, field_validator, model_validator

from budapp.commons.constants import (
    GuardrailDeploymentStatusEnum,
    GuardrailProviderTypeEnum,
    GuardrailStatusEnum,
    ProxyProviderEnum,
)
from budapp.commons.schemas import PaginatedSuccessResponse, SuccessResponse, Tag
from budapp.endpoint_ops.schemas import ProviderConfig, ProxyModelPricing
from budapp.model_ops.schemas import Provider


class TagsListResponse(PaginatedSuccessResponse):
    """Response schema for tags list."""

    tags: List[Tag] = Field(..., description="List of matching tags")


class GuardrailFilter(BaseModel):
    """Filter guardrail schema for filtering based on specific criteria."""

    name: str | None = None
    status: GuardrailStatusEnum | None = None
    provider_id: UUID4 | None = None


# Rule schemas
class GuardrailRuleCreate(BaseModel):
    """Schema for creating guardrail rule."""

    name: str
    uri: Optional[str] = None
    probe_id: UUID4
    status: GuardrailStatusEnum
    description: Optional[str] = None
    scanner_types: Optional[list[str]] = None
    modality_types: Optional[list[str]] = None
    guard_types: Optional[list[str]] = None
    examples: Optional[list[str]] = None


class GuardrailRuleUpdate(BaseModel):
    """Schema for updating a guardrail rule."""

    name: Optional[str] = None
    description: Optional[str] = None
    scanner_types: Optional[list[str]] = None
    modality_types: Optional[list[str]] = None
    guard_types: Optional[list[str]] = None
    examples: Optional[list[str]] = None
    status: Optional[GuardrailStatusEnum] = None


class GuardrailRuleResponse(BaseModel):
    """Schema for guardrail rule responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    name: str
    probe_id: UUID4
    status: GuardrailStatusEnum
    description: Optional[str] = None
    scanner_types: Optional[list[str]] = None
    modality_types: Optional[list[str]] = None
    guard_types: Optional[list[str]] = None
    examples: Optional[list[str]] = None
    created_by: Optional[UUID4] = None
    created_at: datetime
    modified_at: datetime


# Probe schemas
class GuardrailProbeCreate(BaseModel):
    """Schema for creating guardrail probe."""

    name: str
    uri: Optional[str] = None
    provider_id: UUID4
    provider_type: GuardrailProviderTypeEnum
    status: GuardrailStatusEnum
    description: Optional[str] = None
    tags: Optional[list[Tag]] = None


class GuardrailProbeUpdate(BaseModel):
    """Schema for updating a guardrail probe."""

    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[Tag]] = None
    status: Optional[GuardrailStatusEnum] = None


class GuardrailProbeResponse(BaseModel):
    """Schema for guardrail probe responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    name: str
    uri: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[Tag]] = None
    provider_type: GuardrailProviderTypeEnum
    provider: Provider
    status: GuardrailStatusEnum
    scanner_types: Optional[list[str]] = None
    modality_types: Optional[list[str]] = None
    guard_types: Optional[list[str]] = None
    examples: Optional[list[str]] = None
    created_by: Optional[UUID4] = None
    created_at: datetime
    modified_at: datetime


class GuardrailProbePaginatedResponse(PaginatedSuccessResponse):
    """Schema for guardrail probe list responses."""

    probes: list[GuardrailProbeResponse] = []
    object: str = "guardrail.probe.list"


class GuardrailProbeDetailResponse(SuccessResponse):
    probe: GuardrailProbeResponse
    rule_count: int
    object: str = "guardrail.probe.get"


class GuardrailRulePaginatedResponse(PaginatedSuccessResponse):
    """Schema for guardrail probe rules list responses."""

    rules: list[GuardrailRuleResponse] = []
    object: str = "guardrail.probe.rule.list"


class GuardrailRuleDetailResponse(SuccessResponse):
    rule: GuardrailRuleResponse
    object: str = "guardrail.probe.rule.get"


# GuardrailProfile schemas
class GuardrailProfileCreate(BaseModel):
    """Schema for creating guardrail profile."""

    name: str
    description: Optional[str] = None
    tags: Optional[list[Tag]] = None
    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None
    status: GuardrailStatusEnum = GuardrailStatusEnum.ACTIVE
    project_id: Optional[UUID4] = None


class GuardrailProfileUpdate(BaseModel):
    """Schema for updating a guardrail profile."""

    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[Tag]] = None
    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None
    # status: Optional[GuardrailStatusEnum] = None


class GuardrailProbeRuleSelection(BaseModel):
    id: UUID4
    status: GuardrailStatusEnum
    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None


class GuardrailProfileProbeSelection(BaseModel):
    id: UUID4
    rules: Optional[list[GuardrailProbeRuleSelection]] = None
    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None


class GuardrailProfileUpdateWithProbes(GuardrailProfileUpdate):
    """Schema for updating a guardrail profile with probe selections."""

    probe_selections: Optional[list[GuardrailProfileProbeSelection]] = None


class GuardrailProfileResponse(BaseModel):
    """Schema for guardrail profile responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    name: str
    status: GuardrailStatusEnum
    description: Optional[str] = None
    tags: Optional[list[Tag]] = None
    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None
    created_by: Optional[UUID4] = None
    project_id: Optional[UUID4] = None
    created_at: datetime
    modified_at: datetime


class GuardrailProfilePaginatedResponse(PaginatedSuccessResponse):
    """Schema for guardrail profile list responses."""

    profiles: list[GuardrailProfileResponse] = []
    object: str = "guardrail.profile.list"


class GuardrailProfileDetailResponse(SuccessResponse):
    profile: GuardrailProfileResponse
    probe_count: int
    deployment_count: int
    is_standalone: bool
    object: str = "guardrail.profile.get"


# GuardrailProfileProbes schemas
class GuardrailProfileProbeCreate(BaseModel):
    """Schema for creating enabled probe in profile."""

    profile_id: UUID4
    probe_id: UUID4
    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None


class GuardrailProfileProbeUpdate(BaseModel):
    """Schema for updating enabled probe in profile."""

    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None


class GuardrailProfileProbeResponse(GuardrailProbeResponse):
    """Schema for enabled probe responses."""

    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None


# GuardrailProfileRules schemas
class GuardrailProfileRuleCreate(BaseModel):
    """Schema for creating disabled rule in profile."""

    profile_probe_id: UUID4
    rule_id: UUID4
    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None


class GuardrailProfileRuleUpdate(BaseModel):
    """Schema for updating disabled rule in profile."""

    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None


class GuardrailProfileRuleResponse(GuardrailRuleResponse):
    """Schema for disabled rule responses."""

    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None


# GuardrailDeployments schemas
class GuardrailDeploymentCreate(BaseModel):
    """Schema for creating guardrail deployment."""

    profile_id: UUID4
    name: str
    description: Optional[str] = None
    project_id: UUID4
    endpoint_id: Optional[UUID4] = None
    credential_id: Optional[UUID4] = None
    status: GuardrailDeploymentStatusEnum
    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None


class GuardrailDeploymentUpdate(BaseModel):
    """Schema for updating a guardrail deployment."""

    name: Optional[str] = None
    description: Optional[str] = None
    # status: Optional[GuardrailDeploymentStatusEnum] = None
    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None


class GuardrailDeploymentResponse(BaseModel):
    """Schema for guardrail deployment responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    profile_id: UUID4
    name: str
    description: Optional[str] = None
    status: GuardrailDeploymentStatusEnum
    created_by: Optional[UUID4] = None
    project_id: UUID4
    endpoint_id: Optional[UUID4] = None
    credential_id: Optional[UUID4] = None
    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None
    created_at: datetime
    modified_at: datetime


class GuardrailDeploymentPaginatedResponse(PaginatedSuccessResponse):
    """Schema for guardrail deployment list responses."""

    deployments: list[GuardrailDeploymentResponse] = []
    object: str = "guardrail.deployments"


class GuardrailDeploymentDetailResponse(SuccessResponse):
    deployment: GuardrailDeploymentResponse
    object: str = "guardrail.deployment"


class GuardrailDeploymentWorkflowRequest(BaseModel):
    """Guardrail deployment workflow request schema."""

    workflow_id: UUID4 | None = None
    workflow_total_steps: int | None = None
    step_number: int = Field(..., gt=0)
    trigger_workflow: bool = False
    provider_type: GuardrailProviderTypeEnum | None = None
    provider_id: UUID4 | None = None
    guardrail_profile_id: UUID4 | None = None
    name: str | None = None
    description: Optional[str] = None
    tags: list[Tag] | None = None
    project_id: UUID4 | None = None
    endpoint_ids: list[UUID4] | None = None
    credential_id: UUID4 | None = None
    is_standalone: bool | None = None
    probe_selections: list[GuardrailProfileProbeSelection] | None = None
    guard_types: list[str] | None = None
    severity_threshold: float | None = None

    @model_validator(mode="after")
    def validate_fields(self) -> "GuardrailDeploymentWorkflowRequest":
        """Validate the fields of the request."""
        if self.workflow_id is None and self.workflow_total_steps is None:
            raise ValueError("workflow_total_steps is required when workflow_id is not provided")

        if self.workflow_id is not None and self.workflow_total_steps is not None:
            raise ValueError("workflow_total_steps and workflow_id cannot be provided together")

        # Check if at least one of the required fields is provided
        required_fields = [
            "provider_type",
            "provider_id",
            "name",
            "project_id",
            "endpoint_ids",
            "is_standalone",
            "credential_id",
            "probe_selections",
            "guard_types",
            "severity_threshold",
        ]
        if not any(getattr(self, field) for field in required_fields):
            input_data = self.model_dump(exclude_unset=True)
            if "guardrail_profile_id" in input_data:
                return self
            raise ValueError(f"At least one of {', '.join(required_fields)} is required when workflow_id is provided")

        if self.endpoint_ids and self.is_standalone:
            raise ValueError("endpoint_ids and is_standalone can't be used together, choose either one.")

        return self


class GuardrailDeploymentWorkflowSteps(BaseModel):
    """Create cluster workflow step data schema."""

    provider_id: UUID4 | None
    provider_type: GuardrailProviderTypeEnum | None = None
    guardrail_profile_id: UUID4 | None = None
    name: str | None = None
    description: Optional[str] = None
    tags: list[Tag] | None = None
    project_id: UUID4 | None = None
    endpoint_ids: list[UUID4] | None = None
    credential_id: UUID4 | None = None
    is_standalone: bool | None = None
    probe_selections: list[GuardrailProfileProbeSelection] | None = None
    guard_types: list[str] | None = None
    severity_threshold: float | None = None


class BudSentinelConfig(BaseModel):
    """BudSentinel config."""

    type: str = "bud_sentinel"
    model_name: str
    api_base: str
    api_key_location: str


class ProxyGuardrailConfig(BaseModel):
    """Proxy guardrail config with pricing information."""

    routing: list[ProxyProviderEnum]
    providers: dict[ProxyProviderEnum, ProviderConfig | BudSentinelConfig]
    endpoints: list[str]
    api_key: Optional[str] = None
    pricing: Optional[ProxyModelPricing] = None
