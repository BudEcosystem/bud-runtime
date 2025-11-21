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
    dataset_ids: list | None = None
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
    discarded_prompt_ids: list[dict] | None = None
    prompt_schema_events: dict | None = None
    # Hardware resource mode (dedicated vs shared/time-slicing)
    hardware_mode: str | None = None
    # Parser metadata from cluster/simulator
    tool_calling_parser_type: str | None = None
    reasoning_parser_type: str | None = None
    chat_template: str | None = None
    # User preferences for parsers
    enable_tool_calling: bool | None = None
    enable_reasoning: bool | None = None
    # Engine capability flags from simulator
    supports_lora: bool | None = None
    supports_pipeline_parallelism: bool | None = None


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
