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
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from budapp.commons.constants import (
    GuardrailDeploymentStatusEnum,
    GuardrailDeploymentTypeEnum,
    GuardrailProviderTypeEnum,
    GuardrailStatusEnum,
)
from budapp.commons.schemas import PaginatedSuccessResponse, SuccessResponse, Tag
from budapp.model_ops.schemas import Provider


class TagsListResponse(PaginatedSuccessResponse):
    """Response schema for tags list."""

    tags: List[Tag] = Field(..., description="List of matching tags")


class GuardrailFilter(BaseModel):
    """Filter guardrail schema for filtering based on specific criteria."""

    name: str | None = None
    status: GuardrailStatusEnum | None = None


# Rule schemas
class GuardrailRuleCreate(BaseModel):
    """Schema for creating guardrail rule."""

    name: str
    probe_id: UUID
    user_id: UUID
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

    id: UUID
    name: str
    probe_id: UUID
    status: GuardrailStatusEnum
    description: Optional[str] = None
    scanner_types: Optional[list[str]] = None
    modality_types: Optional[list[str]] = None
    guard_types: Optional[list[str]] = None
    examples: Optional[list[str]] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    modified_at: datetime


# Probe schemas
class GuardrailProbeCreate(BaseModel):
    """Schema for creating guardrail probe."""

    name: str
    provider_id: UUID
    user_id: UUID
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

    id: UUID
    provider_type: GuardrailProviderTypeEnum
    provider: Provider
    status: GuardrailStatusEnum
    scanner_types: Optional[list[str]] = None
    modality_types: Optional[list[str]] = None
    guard_types: Optional[list[str]] = None
    created_by: Optional[UUID] = None
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
    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None
    status: GuardrailStatusEnum = GuardrailStatusEnum.ACTIVE


class GuardrailProfileUpdate(BaseModel):
    """Schema for updating a guardrail profile."""

    name: Optional[str] = None
    description: Optional[str] = None
    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None
    status: Optional[GuardrailStatusEnum] = None


class GuardrailProfileResponse(BaseModel):
    """Schema for guardrail profile responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: GuardrailStatusEnum
    description: Optional[str] = None
    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    modified_at: datetime


class GuardrailProfilePaginatedResponse(PaginatedSuccessResponse):
    """Schema for guardrail profile list responses."""

    profiles: list[GuardrailProfileResponse] = []
    object: str = "guardrail.profile.list"


class GuardrailProfileDetailResponse(SuccessResponse):
    profile: GuardrailProfileResponse
    probe_count: int
    object: str = "guardrail.profile.get"


# GuardrailProfileEnabledProbes schemas
class GuardrailProfileEnabledProbeCreate(BaseModel):
    """Schema for creating enabled probe in profile."""

    profile_id: UUID
    probe_id: UUID
    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None


class GuardrailProfileEnabledProbeUpdate(BaseModel):
    """Schema for updating enabled probe in profile."""

    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None


class GuardrailProfileEnabledProbeResponse(GuardrailProbeResponse):
    """Schema for enabled probe responses."""

    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None


# GuardrailProfileDisabledRules schemas
class GuardrailProfileDisabledRuleCreate(BaseModel):
    """Schema for creating disabled rule in profile."""

    profile_probe_id: UUID
    rule_id: UUID
    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None


class GuardrailProfileDisabledRuleUpdate(BaseModel):
    """Schema for updating disabled rule in profile."""

    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None


class GuardrailProfileDisabledRuleResponse(GuardrailRuleResponse):
    """Schema for disabled rule responses."""

    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None


# GuardrailDeployments schemas
class GuardrailDeploymentCreate(BaseModel):
    """Schema for creating guardrail deployment."""

    profile_id: UUID
    name: str
    description: Optional[str] = None
    project_id: UUID
    endpoint_id: UUID
    status: GuardrailDeploymentStatusEnum = GuardrailDeploymentStatusEnum.RUNNING
    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None


class GuardrailDeploymentUpdate(BaseModel):
    """Schema for updating a guardrail deployment."""

    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[GuardrailDeploymentStatusEnum] = None
    severity_threshold: Optional[float] = None
    guard_types: Optional[list[str]] = None


class GuardrailDeploymentResponse(BaseModel):
    """Schema for guardrail deployment responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    name: str
    description: Optional[str] = None
    status: GuardrailDeploymentStatusEnum
    created_by: Optional[UUID] = None
    project_id: UUID
    endpoint_id: UUID
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
