"""Progress event schemas for budpipeline.

This module contains Pydantic schemas for progress events API
(002-pipeline-event-persistence - T018).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from budpipeline.pipeline.schemas import (
    AggregatedProgress,
    PipelineExecutionResponse,
    StepExecutionResponse,
)
from budpipeline.progress.models import EventType


class ProgressEventCreate(BaseModel):
    """Request to create a new progress event (T018)."""

    execution_id: UUID = Field(..., description="Parent execution reference")
    event_type: EventType = Field(..., description="Type of progress event")
    progress_percentage: Decimal = Field(
        ...,
        ge=Decimal("0.00"),
        le=Decimal("100.00"),
        description="Progress at event time (0.00-100.00)",
    )
    eta_seconds: int | None = Field(
        None, ge=0, description="Estimated time to completion (seconds)"
    )
    current_step_desc: str | None = Field(
        None, max_length=500, description="Description of current step"
    )
    event_details: dict[str, Any] | None = Field(None, description="Additional event metadata")


class ProgressEventResponse(BaseModel):
    """Progress event response schema (T018)."""

    model_config = {"from_attributes": True}

    id: UUID = Field(..., description="Unique event identifier")
    execution_id: UUID = Field(..., description="Parent execution reference")
    event_type: EventType = Field(..., description="Type of progress event")
    progress_percentage: Decimal = Field(..., description="Progress at event time (0.00-100.00)")
    eta_seconds: int | None = Field(None, description="Estimated time to completion (seconds)")
    current_step_desc: str | None = Field(None, description="Description of current step")
    event_details: dict[str, Any] | None = Field(None, description="Additional event metadata")
    timestamp: datetime = Field(..., description="Event occurrence time")
    sequence_number: int = Field(..., description="Event sequence for ordering")
    created_at: datetime = Field(..., description="Record creation time")


class ProgressEventListQuery(BaseModel):
    """Query parameters for listing progress events."""

    event_type: EventType | None = Field(None, description="Filter by event type")
    since: datetime | None = Field(None, description="Return events after this timestamp")


class ProgressEventListResponse(BaseModel):
    """Response for listing progress events with pagination."""

    events: list[ProgressEventResponse] = Field(..., description="List of progress events")
    total_count: int = Field(..., description="Total number of events matching filters")
    limit: int = Field(..., description="Maximum events returned")
    offset: int = Field(..., description="Number of events skipped")


class ExecutionProgressResponse(BaseModel):
    """Combined execution progress response.

    Used for GET /executions/{id}/progress endpoint.
    """

    execution: PipelineExecutionResponse = Field(..., description="Execution details")
    steps: list[StepExecutionResponse] = Field(..., description="Step execution details")
    recent_events: list[ProgressEventResponse] = Field(..., description="Last 20 progress events")
    aggregated_progress: AggregatedProgress = Field(
        ..., description="Aggregated progress information"
    )
