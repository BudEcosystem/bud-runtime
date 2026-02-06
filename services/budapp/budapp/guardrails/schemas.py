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
from enum import Enum
from typing import Any, List, Literal, Optional

from pydantic import UUID4, BaseModel, ConfigDict, Field, field_validator, model_validator

from budapp.commons.constants import (
    GuardrailDeploymentStatusEnum,
    GuardrailProviderTypeEnum,
    GuardrailStatusEnum,
    ModelProviderTypeEnum,
    ProbeTypeEnum,
    ProxyProviderEnum,
    ScannerTypeEnum,
)
from budapp.commons.schemas import PaginatedSuccessResponse, SuccessResponse, Tag
from budapp.endpoint_ops.schemas import ProviderConfig, ProxyModelPricing
from budapp.model_ops.schemas import Provider


class ModelDeploymentStatus(str, Enum):
    """Status for guardrail model deployments.

    Attributes:
        NOT_ONBOARDED: Model is not yet onboarded to the system.
        ONBOARDED: Model has been onboarded but not deployed.
        RUNNING: Model deployment is running and healthy.
        UNHEALTHY: Model deployment is unhealthy.
        DEPLOYING: Model is currently being deployed.
        PENDING: Model deployment is pending.
        FAILURE: Model deployment has failed.
        DELETING: Model deployment is being deleted.
    """

    NOT_ONBOARDED = "not_onboarded"
    ONBOARDED = "onboarded"
    RUNNING = "running"
    UNHEALTHY = "unhealthy"
    DEPLOYING = "deploying"
    PENDING = "pending"
    FAILURE = "failure"
    DELETING = "deleting"


class CustomProbeTypeEnum(str, Enum):
    """Available custom probe type options.

    Each option maps to a specific model_uri, scanner_type, handler, and provider.
    """

    LLM_POLICY = "llm_policy"
    # Future extensions:
    # CLASSIFIER = "classifier"
    # REGEX = "regex"


class GuardrailModelStatus(BaseModel):
    """Status of a model required by guardrail rules."""

    model_config = ConfigDict(from_attributes=True)

    # Rule identification
    rule_id: UUID4
    rule_name: str
    probe_id: UUID4
    probe_name: str

    # Model info
    model_uri: str
    model_id: UUID4 | None = None
    model_provider_type: str | None = None
    tags: list[dict] | None = None  # Rule tags to use for onboarding
    local_path: str | None = None  # Local cached path after onboarding
    supported_endpoints: list[str] | None = None  # Model endpoint types for budsim

    # Status
    status: ModelDeploymentStatus

    # Endpoint details (populated when deployed)
    endpoint_id: UUID4 | None = None
    endpoint_name: str | None = None
    endpoint_url: str | None = None
    cluster_id: UUID4 | None = None
    cluster_name: str | None = None

    # Derived flags for UI
    requires_onboarding: bool
    requires_deployment: bool
    can_reuse: bool
    show_warning: bool = False


class GuardrailModelStatusResponse(SuccessResponse):
    """Response for model status identification step."""

    models: list[GuardrailModelStatus]
    total_models: int
    models_requiring_onboarding: int
    models_requiring_deployment: int
    models_reusable: int
    skip_to_step: int | None = None
    credential_required: bool = False
    object: str = "guardrail.model_status"


class TagsListResponse(PaginatedSuccessResponse):
    """Response schema for tags list."""

    tags: List[Tag] = Field(..., description="List of matching tags")


class GuardrailFilter(BaseModel):
    """Filter guardrail schema for filtering based on specific criteria."""

    name: str | None = None
    status: GuardrailStatusEnum | None = None
    provider_id: UUID4 | None = None


# Model config schemas for custom rules
class HeadMapping(BaseModel):
    """Head mapping for classifier models."""

    head_name: str = "default"
    target_labels: list[str]


class ClassifierConfig(BaseModel):
    """Configuration for classifier-based rules."""

    head_mappings: list[HeadMapping]
    post_processing: list[dict] | None = None


class DefinitionItem(BaseModel):
    """Term definition for policy."""

    term: str
    definition: str


class EvaluationConfig(BaseModel):
    """Evaluation configuration for policy."""

    depiction: str = "Does the content CONTAIN policy violations?"
    request: str = "Is the user ASKING to generate violating content?"
    guidance: str = "Return the HIGHEST severity that applies. Include both aspects in your rationale."


class PolicyExample(BaseModel):
    """Example for policy evaluation."""

    input: str
    rationale: str
    confidence: str = "high"


class ContentItem(BaseModel):
    """Content item for safe_content or violation items."""

    name: str
    description: str
    example: str


class SafeContentConfig(BaseModel):
    """Safe content configuration for policy."""

    category: str = "safe"
    description: str
    items: list[ContentItem]
    examples: list[PolicyExample]


class ViolationCategory(BaseModel):
    """Violation category for policy."""

    category: str
    severity: str  # "Moderate", "High", "Critical", "Maximum"
    description: str
    escalate: bool = False
    items: list[ContentItem]
    examples: list[PolicyExample]


class AmbiguityRule(BaseModel):
    """Ambiguity handling rule for policy."""

    condition: str
    action: str


class PolicyConfig(BaseModel):
    """Policy configuration for LLM-based rules."""

    task: str
    definitions: list[DefinitionItem]
    safe_content: SafeContentConfig
    violations: list[ViolationCategory]
    # Optional fields with defaults
    interpretation: list[str] | None = None
    evaluation: EvaluationConfig | None = None
    ambiguity: list[AmbiguityRule] | None = None


class LLMConfig(BaseModel):
    """Configuration for LLM-based rules."""

    handler: str = "gpt_safeguard"
    policy: PolicyConfig


# Rule schemas
class GuardrailRuleCreate(BaseModel):
    """Schema for creating guardrail rule."""

    name: str
    uri: Optional[str] = None
    probe_id: UUID4
    status: GuardrailStatusEnum
    description: Optional[str] = None
    modality_types: Optional[list[str]] = None
    guard_types: Optional[list[str]] = None
    examples: Optional[list[str]] = None
    # Model-based rule fields
    scanner_type: Optional[ScannerTypeEnum] = None
    model_uri: Optional[str] = None
    model_provider_type: Optional[ModelProviderTypeEnum] = None
    is_gated: Optional[bool] = False
    model_config_json: Optional[dict] = None
    model_id: Optional[UUID4] = None


class GuardrailRuleUpdate(BaseModel):
    """Schema for updating a guardrail rule."""

    name: Optional[str] = None
    description: Optional[str] = None
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
    modality_types: Optional[list[str]] = None
    guard_types: Optional[list[str]] = None
    examples: Optional[list[str]] = None
    # Model-based rule fields
    scanner_type: ScannerTypeEnum | None = None
    model_uri: str | None = None
    model_provider_type: str | None = None
    is_gated: bool = False
    model_config_json: dict | None = None
    model_id: UUID4 | None = None
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
    probe_type: ProbeTypeEnum = ProbeTypeEnum.PROVIDER
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


# Custom probe schemas
class GuardrailCustomProbeCreate(BaseModel):
    """Schema for creating a custom model probe."""

    name: str
    description: str | None = None
    scanner_type: ScannerTypeEnum
    model_id: UUID4  # User's onboarded model
    model_config_data: ClassifierConfig | LLMConfig

    @model_validator(mode="after")
    def validate_config_type(self) -> "GuardrailCustomProbeCreate":
        if self.scanner_type == ScannerTypeEnum.CLASSIFIER:
            if not isinstance(self.model_config_data, ClassifierConfig):
                raise ValueError("Classifier scanner requires ClassifierConfig")
        elif self.scanner_type == ScannerTypeEnum.LLM:
            if not isinstance(self.model_config_data, LLMConfig):
                raise ValueError("LLM scanner requires LLMConfig")
        return self


class GuardrailCustomProbeUpdate(BaseModel):
    """Schema for updating a custom model probe."""

    name: str | None = None
    description: str | None = None
    model_config_data: ClassifierConfig | LLMConfig | None = None


class GuardrailCustomProbeResponse(BaseModel):
    """Response schema for custom probe."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    name: str
    description: str | None = None
    probe_type: ProbeTypeEnum
    scanner_type: ScannerTypeEnum | None = None
    model_id: UUID4 | None = None
    model_uri: str | None = None
    model_config_json: dict | None = None
    guard_types: list[str] | None = None
    modality_types: list[str] | None = None
    status: str
    created_at: datetime
    modified_at: datetime

    @model_validator(mode="before")
    @classmethod
    def extract_rule_data(cls, data: Any) -> Any:
        """Extract rule data from the probe's rules relationship for custom probes."""
        # If data is a dict, it's already been processed
        if isinstance(data, dict):
            return data

        # If data has a rules attribute with at least one rule, extract rule data
        if hasattr(data, "rules") and data.rules:
            rule = data.rules[0]  # Custom probes have exactly one rule
            return {
                "id": data.id,
                "name": data.name,
                "description": data.description,
                "probe_type": data.probe_type,
                "scanner_type": getattr(rule, "scanner_type", None),
                "model_id": getattr(rule, "model_id", None),
                "model_uri": getattr(rule, "model_uri", None),
                "model_config_json": getattr(rule, "model_config_json", None),
                "guard_types": getattr(rule, "guard_types", None),
                "modality_types": getattr(rule, "modality_types", None),
                "status": data.status,
                "created_at": data.created_at,
                "modified_at": data.modified_at,
            }

        return data


class GuardrailCustomProbeDetailResponse(SuccessResponse):
    """Detail response schema for a single custom probe."""

    probe: GuardrailCustomProbeResponse
    object: str = "guardrail.custom_probe"


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
    cluster_config_override: dict | None = None


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
    probe_count: int = 0
    deployment_count: int = 0
    is_standalone: bool = False
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
    endpoint_name: Optional[str] = None
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


class GuardrailRuleDeploymentResponse(BaseModel):
    """Response schema for rule deployment.

    Status is derived from the linked endpoint's status.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    guardrail_deployment_id: UUID4
    rule_id: UUID4
    model_id: UUID4
    endpoint_id: UUID4
    cluster_id: UUID4
    config_override_json: dict | None = None
    status: str | None = None  # Derived from endpoint.status
    created_at: datetime
    modified_at: datetime

    @model_validator(mode="before")
    @classmethod
    def derive_status_from_endpoint(cls, data: Any) -> Any:
        """Derive status from the endpoint relationship."""
        if hasattr(data, "endpoint") and data.endpoint is not None:
            # SQLAlchemy model - get status from endpoint relationship
            if not hasattr(data, "status") or data.status is None:
                object.__setattr__(data, "status", data.endpoint.status)
        elif isinstance(data, dict) and "endpoint" in data and data["endpoint"]:
            # Dict input - get status from endpoint dict
            if "status" not in data or data["status"] is None:
                data["status"] = data["endpoint"].get("status")
        return data


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
    # Model deployment fields
    cluster_id: UUID4 | None = None
    hardware_mode: Literal["dedicated", "shared"] | None = None
    deploy_config: dict | None = None  # Default config applied to all models
    per_model_deployment_configs: list[dict] | None = None  # Per-model configs: [{model_id/model_uri, deploy_config}]
    callback_topics: list[str] | None = None

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
    # Model deployment fields
    hardware_mode: Literal["dedicated", "shared"] | None = None
    deploy_config: dict | None = None  # Default config for all models
    per_model_deployment_configs: list[dict] | None = None  # Per-model configs
    cluster_id: UUID4 | None = None  # Global cluster_id for deployment
    # Model status fields (populated when derive_model_statuses=True)
    model_statuses: list[dict] | None = None
    total_models: int | None = None
    models_requiring_onboarding: int | None = None
    models_requiring_deployment: int | None = None
    models_reusable: int | None = None
    skip_to_step: int | None = None
    credential_required: bool | None = None
    # Cluster selection fields
    selected_cluster_id: UUID4 | None = None
    cluster_recommendations: list[dict] | None = None
    # Onboarding events: {execution_id, status, results}
    onboarding_events: dict | None = None
    # Simulation events: {results: [{model_id, model_uri, workflow_id, status}], total_models, successful, failed}
    simulation_events: dict | None = None
    # Deployment events: {execution_id, results: [{model_id, model_uri, cluster_id, status, endpoint_id}], total, successful, failed, running}
    deployment_events: dict | None = None
    # Pending profile data: stored when deployment is in progress, used to create profile after deployment completes
    pending_profile_data: dict | None = None


class CustomProbeWorkflowRequest(BaseModel):
    """Custom probe workflow request schema (multi-step).

    Similar to GuardrailDeploymentWorkflowRequest but for creating custom probes.
    Follows the probe-first pattern where the probe is created with model_uri only,
    and model_id gets assigned later during deployment (or immediately if model is already onboarded).

    Workflow Steps:
    - Step 1: Select probe type (llm_policy, etc.) - system auto-derives model_uri, scanner_type, etc.
    - Step 2: Configure policy (PolicyConfig)
    - Step 3: Probe metadata + trigger_workflow=true creates probe
    """

    # Workflow management
    workflow_id: UUID4 | None = None
    workflow_total_steps: int | None = None  # Should be 3 for new workflows
    step_number: int = Field(..., gt=0)
    trigger_workflow: bool = False

    # Step 1: Probe type selection
    probe_type_option: CustomProbeTypeEnum | None = None

    # Step 2: Policy configuration
    policy: PolicyConfig | None = None

    # Step 3: Probe metadata
    name: str | None = None
    description: str | None = None
    guard_types: list[str] | None = None
    modality_types: list[str] | None = None

    @model_validator(mode="after")
    def validate_fields(self) -> "CustomProbeWorkflowRequest":
        """Validate workflow request fields.

        Either workflow_id OR workflow_total_steps must be provided, but not both.
        """
        if self.workflow_id is None and self.workflow_total_steps is None:
            raise ValueError("workflow_total_steps is required when workflow_id is not provided")

        if self.workflow_id is not None and self.workflow_total_steps is not None:
            raise ValueError("workflow_total_steps and workflow_id cannot be provided together")

        return self


class CustomProbeWorkflowSteps(BaseModel):
    """Custom probe workflow step data schema.

    Tracks accumulated data across workflow steps for custom probe creation.
    """

    # Step 1 data
    probe_type_option: CustomProbeTypeEnum | None = None
    # Auto-derived from probe_type_option
    model_uri: str | None = None
    scanner_type: str | None = None
    handler: str | None = None
    model_provider_type: str | None = None

    # Step 2 data
    policy: dict | None = None  # PolicyConfig as dict

    # Step 3 data
    name: str | None = None
    description: str | None = None
    guard_types: list[str] | None = None
    modality_types: list[str] | None = None

    # Result data (after trigger_workflow)
    probe_id: UUID4 | None = None
    model_id: UUID4 | None = None  # Assigned if model exists
    workflow_execution_status: dict | None = None


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
