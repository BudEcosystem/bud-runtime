"""Workflow API schemas.

This module contains Pydantic schemas for the pipeline API including
new persistence schemas (002-pipeline-event-persistence - T016, T017).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from budpipeline.pipeline.models import ExecutionStatus, PipelineStatus, StepStatus


class PipelineCreateRequest(BaseModel):
    """Request to create/register a pipeline DAG."""

    dag: dict[str, Any] = Field(..., description="The DAG definition")
    name: str | None = Field(None, description="Optional pipeline name override")
    icon: str | None = Field(None, description="Optional icon/emoji for UI representation")
    user_id: str | None = Field(
        None, description="User ID for pipeline ownership (set by service from auth context)"
    )
    system_owned: bool = Field(
        False, description="True if this is a system-owned pipeline visible to all users"
    )


# Backwards compatibility alias
WorkflowCreateRequest = PipelineCreateRequest


class PipelineResponse(BaseModel):
    """Response for pipeline operations."""

    id: str
    name: str
    version: str
    status: str
    created_at: datetime
    step_count: int
    user_id: str | None = None
    system_owned: bool = False
    description: str | None = None
    icon: str | None = None
    dag: dict[str, Any] | None = None
    execution_count: int = 0
    last_execution_at: datetime | None = None


# Backwards compatibility alias
WorkflowResponse = PipelineResponse


class ExecutionCreateRequest(BaseModel):
    """Request to start a workflow execution."""

    workflow_id: str = Field(..., description="Workflow ID to execute")
    params: dict[str, Any] = Field(default_factory=dict, description="Input parameters")
    callback_topics: list[str] | None = Field(
        None, description="Optional callback topics for real-time progress updates"
    )
    user_id: str | None = Field(
        None, description="User ID initiating the execution (for service-to-service auth)"
    )
    initiator: str = Field(default="api", description="Initiator identifier")
    subscriber_ids: str | None = Field(
        None, description="User ID(s) for Novu notifications (enables dual-publish to budnotify)"
    )
    payload_type: str | None = Field(
        None, description="Custom payload.type for event routing (defaults to pipeline_execution)"
    )
    notification_workflow_id: str | None = Field(
        None,
        max_length=255,
        description="Override payload.workflow_id in notifications (defaults to execution_id)",
    )


class ExecutionResponse(BaseModel):
    """Response for execution operations."""

    execution_id: str
    workflow_id: str
    workflow_name: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class StepStatusResponse(BaseModel):
    """Status of a single step in execution."""

    step_id: str
    name: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ExecutionDetailResponse(ExecutionResponse):
    """Detailed execution response with step statuses."""

    steps: list[StepStatusResponse] = Field(default_factory=list)


class DAGValidationRequest(BaseModel):
    """Request to validate a DAG definition."""

    dag: dict[str, Any] = Field(..., description="The DAG definition to validate")


class DAGValidationResponse(BaseModel):
    """Response for DAG validation."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    step_count: int = 0
    has_cycles: bool = False


# ============================================================================
# Pipeline Event Persistence Schemas (002-pipeline-event-persistence)
# ============================================================================


class PipelineExecutionCreate(BaseModel):
    """Request to create a new pipeline execution.

    Maps to POST /executions request body (T016).
    """

    pipeline_definition: dict[str, Any] = Field(..., description="Complete pipeline DAG definition")
    initiator: str = Field(..., description="User or service that initiated execution")
    callback_topics: list[str] | None = Field(
        None, description="Dapr pub/sub topics for event notifications (validated per FR-022)"
    )
    metadata: dict[str, Any] | None = Field(None, description="Additional execution metadata")
    subscriber_ids: str | None = Field(
        None, description="User ID(s) for Novu notifications (enables dual-publish to budnotify)"
    )
    payload_type: str | None = Field(
        None, description="Custom payload.type for event routing (defaults to pipeline_execution)"
    )
    notification_workflow_id: str | None = Field(
        None,
        max_length=255,
        description="Override payload.workflow_id in notifications (defaults to execution_id)",
    )


class PipelineExecutionUpdate(BaseModel):
    """Request to update pipeline execution fields.

    Used for status transitions with optimistic locking (T016).
    """

    version: int = Field(..., description="Expected version for optimistic locking")
    status: ExecutionStatus | None = Field(None, description="New execution status")
    progress_percentage: Decimal | None = Field(
        None, ge=Decimal("0.00"), le=Decimal("100.00"), description="Updated progress"
    )
    start_time: datetime | None = Field(None, description="Execution start time")
    end_time: datetime | None = Field(None, description="Execution end time")
    final_outputs: dict[str, Any] | None = Field(None, description="Final outputs if completed")
    error_info: dict[str, Any] | None = Field(None, description="Error details if failed")


class ErrorInfo(BaseModel):
    """Error information structure."""

    error_type: str = Field(..., description="Type of error")
    message: str = Field(..., description="Error message")
    stack_trace: str | None = Field(None, description="Stack trace if available")


class PipelineExecutionResponse(BaseModel):
    """Pipeline execution response schema.

    Maps to API response for GET /executions/{id} (T016).
    Includes both database field names and frontend-compatible aliases.
    """

    model_config = {"from_attributes": True}

    id: UUID = Field(..., description="Unique execution identifier")
    version: int = Field(..., description="Optimistic locking version")
    pipeline_definition: dict[str, Any] = Field(..., description="Complete pipeline DAG definition")
    initiator: str = Field(..., description="User or service that initiated execution")
    start_time: datetime | None = Field(None, description="Execution start timestamp")
    end_time: datetime | None = Field(None, description="Execution end timestamp")
    status: ExecutionStatus = Field(..., description="Current execution status")
    progress_percentage: Decimal = Field(..., description="Overall progress (0.00-100.00)")
    final_outputs: dict[str, Any] | None = Field(
        None, description="Results from completed execution"
    )
    error_info: dict[str, Any] | None = Field(None, description="Error details if failed")
    created_at: datetime = Field(..., description="Record creation time")
    updated_at: datetime = Field(..., description="Last update time")


class StepExecutionCreate(BaseModel):
    """Request to create a step execution.

    Used internally for batch step creation (T017).
    """

    step_id: str = Field(..., description="Step identifier from pipeline definition")
    step_name: str = Field(..., description="Human-readable step name")
    sequence_number: int = Field(..., gt=0, description="Execution order within pipeline")


class StepExecutionUpdate(BaseModel):
    """Request to update step execution fields.

    Used for status transitions with optimistic locking (T017).
    """

    version: int = Field(..., description="Expected version for optimistic locking")
    status: StepStatus | None = Field(None, description="New step status")
    progress_percentage: Decimal | None = Field(
        None, ge=Decimal("0.00"), le=Decimal("100.00"), description="Updated progress"
    )
    start_time: datetime | None = Field(None, description="Step start time")
    end_time: datetime | None = Field(None, description="Step end time")
    outputs: dict[str, Any] | None = Field(None, description="Step outputs (credentials sanitized)")
    error_message: str | None = Field(
        None, description="Error description (sensitive data redacted)"
    )
    # Event-driven completion tracking fields
    awaiting_event: bool | None = Field(
        None, description="Whether step is waiting for external event"
    )
    external_workflow_id: str | None = Field(
        None, description="External workflow ID for event correlation"
    )
    handler_type: str | None = Field(None, description="Handler type for event routing")
    timeout_at: datetime | None = Field(None, description="When step should timeout")


class StepExecutionResponse(BaseModel):
    """Step execution response schema.

    Maps to API response for step data (T017).
    """

    model_config = {"from_attributes": True}

    id: UUID = Field(..., description="Unique step execution identifier")
    execution_id: UUID = Field(..., description="Parent execution reference")
    version: int = Field(..., description="Optimistic locking version")
    step_id: str = Field(..., description="Step identifier")
    step_name: str = Field(..., description="Human-readable step name")
    status: StepStatus = Field(..., description="Current step status")
    start_time: datetime | None = Field(None, description="Step start timestamp")
    end_time: datetime | None = Field(None, description="Step end timestamp")
    progress_percentage: Decimal = Field(..., description="Step-level progress (0.00-100.00)")
    outputs: dict[str, Any] | None = Field(None, description="Step outputs (credentials sanitized)")
    error_message: str | None = Field(
        None, description="Error description (sensitive data redacted)"
    )
    retry_count: int = Field(..., description="Number of retry attempts")
    sequence_number: int = Field(..., description="Execution order within pipeline")
    # Event-driven completion tracking fields
    awaiting_event: bool = Field(False, description="Whether step is waiting for external event")
    external_workflow_id: str | None = Field(
        None, description="External workflow ID for event correlation"
    )
    handler_type: str | None = Field(None, description="Handler type for event routing")
    timeout_at: datetime | None = Field(None, description="When step should timeout")
    created_at: datetime = Field(..., description="Record creation time")
    updated_at: datetime = Field(..., description="Last update time")


class ExecutionListQuery(BaseModel):
    """Query parameters for listing executions (T016)."""

    start_date: datetime | None = Field(None, description="Filter by created_at >= start_date")
    end_date: datetime | None = Field(None, description="Filter by created_at <= end_date")
    status: ExecutionStatus | None = Field(None, description="Filter by status")
    initiator: str | None = Field(None, description="Filter by initiator")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")


class PaginationInfo(BaseModel):
    """Pagination information for list responses."""

    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_count: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")


class ExecutionListResponse(BaseModel):
    """Response for listing executions (T016)."""

    executions: list[PipelineExecutionResponse] = Field(..., description="List of executions")
    pagination: PaginationInfo = Field(..., description="Pagination information")


class AggregatedProgress(BaseModel):
    """Aggregated progress information for an execution."""

    overall_progress: Decimal = Field(
        ...,
        ge=Decimal("0.00"),
        le=Decimal("100.00"),
        description="Weighted average across all steps",
    )
    eta_seconds: int | None = Field(None, description="Estimated time to completion")
    completed_steps: int = Field(..., description="Number of completed steps")
    total_steps: int = Field(..., description="Total number of steps")
    current_step: str | None = Field(None, description="Name of current step")


class CreateExecutionResponse(BaseModel):
    """Response for creating a new execution."""

    execution_id: UUID = Field(..., description="Created execution ID")
    status: ExecutionStatus = Field(..., description="Initial status (PENDING)")
    created_at: datetime = Field(..., description="Creation timestamp")
    subscriptions: list[dict[str, Any]] | None = Field(
        None, description="Created ExecutionSubscription records"
    )


# ============================================================================
# Pipeline Definition Schemas (002-pipeline-event-persistence)
# ============================================================================


class PipelineDefinitionCreate(BaseModel):
    """Request to create a new pipeline definition.

    Maps to POST /workflows request body for persistent pipeline storage.
    """

    name: str = Field(..., description="Human-readable pipeline name")
    dag: dict[str, Any] = Field(..., description="Complete pipeline DAG definition")
    description: str | None = Field(None, description="Optional pipeline description")


class PipelineDefinitionUpdate(BaseModel):
    """Request to update a pipeline definition.

    Used for updating pipeline definitions with optimistic locking.
    """

    version: int = Field(..., description="Expected version for optimistic locking")
    name: str | None = Field(None, description="Updated pipeline name")
    dag: dict[str, Any] | None = Field(None, description="Updated DAG definition")
    description: str | None = Field(None, description="Updated description")
    status: PipelineStatus | None = Field(None, description="Updated status")


class PipelineDefinitionResponse(BaseModel):
    """Pipeline definition response schema.

    Maps to API response for GET /workflows/{id}.
    Includes both database field names and frontend-compatible aliases.
    """

    model_config = {"from_attributes": True}

    id: UUID = Field(..., description="Unique pipeline identifier")
    version: int = Field(..., description="Optimistic locking version")
    name: str = Field(..., description="Human-readable pipeline name")
    description: str | None = Field(None, description="Optional pipeline description")
    icon: str | None = Field(None, description="Optional icon/emoji for UI representation")
    status: PipelineStatus = Field(..., description="Current pipeline status")
    step_count: int = Field(..., description="Number of steps in the pipeline DAG")
    dag: dict[str, Any] = Field(..., alias="dag_definition", description="Pipeline DAG definition")
    created_by: str = Field(..., description="User or service that created the pipeline")
    user_id: UUID | None = Field(None, description="UUID of the owning user")
    system_owned: bool = Field(False, description="True if system-owned pipeline")
    created_at: datetime = Field(..., description="Record creation time")
    updated_at: datetime = Field(..., description="Last update time")
    execution_count: int | None = Field(None, description="Number of executions (computed)")


class PipelineDefinitionListResponse(BaseModel):
    """Response for listing pipeline definitions."""

    pipelines: list[PipelineDefinitionResponse] = Field(
        ..., description="List of pipeline definitions"
    )
    total_count: int = Field(..., description="Total number of pipelines")


# ============================================================================
# Ephemeral Execution Schemas
# ============================================================================


class EphemeralExecutionRequest(BaseModel):
    """Request for ephemeral pipeline execution without saving the pipeline.

    This allows executing a pipeline definition inline without registering it
    in the database. The execution is tracked but the pipeline itself is not saved.
    """

    pipeline_definition: dict[str, Any] = Field(
        ..., description="Complete pipeline DAG definition to execute"
    )
    params: dict[str, Any] = Field(
        default_factory=dict, description="Input parameters for the execution"
    )
    user_id: str | None = Field(None, description="User ID for tracking execution ownership")
    initiator: str = Field(default="api", description="Initiator identifier")
    callback_topics: list[str] | None = Field(
        None, description="Optional callback topics for real-time progress updates"
    )
    subscriber_ids: str | None = Field(
        None, description="User ID(s) for Novu notifications (enables dual-publish to budnotify)"
    )
    payload_type: str | None = Field(
        None, description="Custom payload.type for event routing (defaults to pipeline_execution)"
    )
    notification_workflow_id: str | None = Field(
        None,
        max_length=255,
        description="Override payload.workflow_id in notifications (defaults to execution_id)",
    )
