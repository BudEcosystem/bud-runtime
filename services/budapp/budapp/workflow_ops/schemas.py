from __future__ import annotations

from datetime import datetime

from pydantic import UUID4, BaseModel, ConfigDict, Field

from budapp.commons.schemas import PaginatedSuccessResponse, SuccessResponse, Tag

from ..cluster_ops.schemas import ClusterResponse
from ..commons.constants import (
    AddModelModalityEnum,
    GuardrailProviderTypeEnum,
    ModelProviderTypeEnum,
    PromptTypeEnum,
    RateLimitTypeEnum,
    VisibilityEnum,
    WorkflowStatusEnum,
    WorkflowTypeEnum,
)
from ..core.schemas import ModelTemplateResponse
from ..credential_ops.schemas import ProprietaryCredentialResponse
from ..endpoint_ops.schemas import AddAdapterWorkflowStepData, EndpointResponse
from ..guardrails.schemas import GuardrailProfileProbeSelection, GuardrailProfileResponse
from ..model_ops.schemas import (
    CloudModel,
    Model,
    ModelSecurityScanResult,
    Provider,
    QuantizeModelWorkflowStepData,
    ScalingSpecification,
)
from ..project_ops.schemas import ProjectResponse
from ..prompt_ops.schemas import PromptSchemaConfig


class RetrieveWorkflowStepData(BaseModel):
    """Workflow step data schema."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    experiment_id: UUID4 | None = None
    trait_ids: list[UUID4] | None = None
    traits_details: list[dict] | None = None
    provider_type: ModelProviderTypeEnum | GuardrailProviderTypeEnum | None = None
    provider: Provider | None = None
    cloud_model: CloudModel | None = None
    cloud_model_id: UUID4 | None = None
    provider_id: UUID4 | None = None
    model_id: UUID4 | None = None
    model: Model | None = None
    workflow_execution_status: dict | None = None
    leaderboard: list | dict | None = None
    name: str | None = None
    ingress_url: str | None = None
    create_cluster_events: dict | None = None
    delete_cluster_events: dict | None = None
    delete_endpoint_events: dict | None = None
    delete_worker_events: dict | None = None
    model_security_scan_events: dict | None = None
    bud_simulator_events: dict | None = None
    budserve_cluster_events: dict | None = None
    evaluation_events: dict | None = None
    icon: str | None = None
    uri: str | None = None
    author: str | None = None
    tags: list[Tag] | None = None
    model_extraction_events: dict | None = None
    description: str | None = None
    security_scan_result_id: UUID4 | None = None
    security_scan_result: ModelSecurityScanResult | None = None
    endpoint: EndpointResponse | None = None
    additional_concurrency: int | None = None
    project: ProjectResponse | None = None
    cluster: ClusterResponse | None = None
    quantization_config: QuantizeModelWorkflowStepData | None = None
    quantization_deployment_events: dict | None = None
    quantization_simulation_events: dict | None = None
    eval_with: str | None = None
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    datasets: list | None = None
    nodes: list | None = None
    credential_id: UUID4 | None = None
    user_confirmation: bool | None = None
    run_as_simulation: bool | None = None
    adapter_config: AddAdapterWorkflowStepData | None = None
    adapter_deployment_events: dict | None = None
    credential: ProprietaryCredentialResponse | None = None
    endpoint_name: str | None = None
    deploy_config: dict | None = None
    scaling_specification: ScalingSpecification | None = None
    simulator_id: UUID4 | None = None
    template_id: UUID4 | None = None
    endpoint_details: dict | None = None
    template: ModelTemplateResponse | None = None
    add_model_modality: list[AddModelModalityEnum] | None = None

    guardrail_profile_id: UUID4 | None = None
    guardrail_profile: GuardrailProfileResponse | None = None
    endpoint_ids: list[UUID4] | None = None
    endpoints: list[EndpointResponse] | None = None
    is_standalone: bool | None = None
    probe_selections: list[GuardrailProfileProbeSelection] | None = None
    guard_types: list[str] | None = None
    severity_threshold: float | None = None
    prompt_type: PromptTypeEnum | None = None
    prompt_schema: PromptSchemaConfig | None = None
    auto_scale: bool | None = None
    caching: bool | None = None
    concurrency: list[int] | None = None
    rate_limit: bool | None = None
    rate_limit_value: int | None = None
    bud_prompt_id: str | None = None
    bud_prompt_version: int | str | None = None
    prompt_schema_events: dict | None = None
    # Parser metadata from cluster/simulator
    tool_calling_parser_type: str | None = None
    reasoning_parser_type: str | None = None
    chat_template: str | None = None
    # User preferences for parsers
    enable_tool_calling: bool | None = None
    enable_reasoning: bool | None = None


class RetrieveWorkflowDataResponse(SuccessResponse):
    """Retrieve Workflow Data Response."""

    workflow_id: UUID4
    status: WorkflowStatusEnum
    current_step: int
    total_steps: int
    reason: str | None = None
    workflow_steps: RetrieveWorkflowStepData | None = None


class WorkflowResponse(SuccessResponse):
    """Workflow response schema."""

    model_config = ConfigDict(
        populate_by_name=True,
    )

    id: UUID4 = Field(alias="workflow_id")
    total_steps: int = Field(..., gt=0)
    status: WorkflowStatusEnum
    current_step: int
    reason: str | None = None


class Workflow(BaseModel):
    """Workflow schema."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: UUID4
    title: str | None = None
    icon: str | None = None
    tag: str | None = None
    progress: dict | None = None
    workflow_type: WorkflowTypeEnum
    total_steps: int = Field(..., gt=0)
    status: WorkflowStatusEnum
    current_step: int
    reason: str | None = None
    created_at: datetime
    modified_at: datetime


class WorkflowListResponse(PaginatedSuccessResponse):
    """Workflow list response schema."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    workflows: list[Workflow]


class WorkflowFilter(BaseModel):
    """Workflow filter schema."""

    workflow_type: WorkflowTypeEnum | None = None


class WorkflowUtilCreate(BaseModel):
    """Workflow create schema."""

    workflow_type: WorkflowTypeEnum
    title: str
    icon: str | None = None
    total_steps: int | None = None
    tag: str | None = None
    visibility: VisibilityEnum = VisibilityEnum.PUBLIC


# Workflow Cleanup Schemas


class OldWorkflowItem(BaseModel):
    """Schema for a single old workflow item."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: UUID4
    workflow_type: WorkflowTypeEnum
    title: str | None = None
    status: WorkflowStatusEnum
    current_step: int
    total_steps: int
    created_at: datetime
    updated_at: datetime
    reason: str | None = None
    age_days: int = Field(..., description="Number of days since last update")


class OldWorkflowsListRequest(BaseModel):
    """Request schema for listing old workflows."""

    retention_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="List workflows older than this many days",
    )
    page: int = Field(default=1, ge=1, description="Page number")
    limit: int = Field(default=50, ge=1, le=500, description="Items per page")


class OldWorkflowsListResponse(PaginatedSuccessResponse):
    """Response schema for listing old workflows."""

    workflows: list[OldWorkflowItem]
    retention_days: int = Field(..., description="Retention period used for filtering")
    total_size_estimate: str | None = Field(None, description="Estimated storage size of old workflows in Redis")


class ManualCleanupRequest(BaseModel):
    """Request schema for manual cleanup trigger."""

    retention_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Clean workflows older than this many days",
    )
    batch_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of workflows to clean in this run",
    )
    delete_from_db: bool = Field(
        default=False,
        description="Whether to also delete workflow records from database (not recommended)",
    )
    dry_run: bool = Field(
        default=False,
        description="If true, only simulate cleanup without actually purging",
    )


class ManualCleanupResponse(SuccessResponse):
    """Response schema for manual cleanup trigger."""

    cleanup_id: str = Field(..., description="Unique identifier for this cleanup operation")
    processed: int = Field(..., description="Number of workflows processed")
    purged_from_dapr: int = Field(..., description="Number of workflows purged from Dapr/Redis")
    failed_purge: int = Field(..., description="Number of workflows that failed to purge")
    deleted_from_db: int = Field(..., description="Number of workflows deleted from database")
    retention_days: int = Field(..., description="Retention period used")
    batch_size: int = Field(..., description="Batch size used")
    dry_run: bool = Field(..., description="Whether this was a dry run")
    started_at: datetime = Field(..., description="When the cleanup started")
    completed_at: datetime = Field(..., description="When the cleanup completed")
