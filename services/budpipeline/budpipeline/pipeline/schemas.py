"""Workflow API schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkflowCreateRequest(BaseModel):
    """Request to create/register a workflow DAG."""

    dag: dict[str, Any] = Field(..., description="The DAG definition")
    name: str | None = Field(None, description="Optional workflow name override")


class WorkflowResponse(BaseModel):
    """Response for workflow operations."""

    id: str
    name: str
    version: str
    status: str
    created_at: datetime
    step_count: int


class ExecutionCreateRequest(BaseModel):
    """Request to start a workflow execution."""

    workflow_id: str = Field(..., description="Workflow ID to execute")
    params: dict[str, Any] = Field(default_factory=dict, description="Input parameters")


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
