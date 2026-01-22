"""Scheduler schemas for schedules, webhooks, and event triggers.

Defines Pydantic models for API requests/responses and internal state.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from budpipeline.commons.constants import ScheduleType

# ============================================================================
# Schedule Schemas
# ============================================================================


class ScheduleConfig(BaseModel):
    """Configuration for a schedule trigger."""

    type: ScheduleType = Field(description="Type of schedule (cron, interval, one_time)")
    expression: str | None = Field(
        default=None,
        description="Cron expression (e.g., '0 9 * * 1-5') or interval (e.g., '@every 30m')",
    )
    timezone: str = Field(default="UTC", description="Timezone for cron expressions")
    run_at: datetime | None = Field(
        default=None,
        description="Specific datetime for one_time schedules",
    )

    @field_validator("expression")
    @classmethod
    def validate_expression(cls, v: str | None, info) -> str | None:
        """Validate expression based on schedule type."""
        schedule_type = info.data.get("type")
        if schedule_type in (ScheduleType.CRON, ScheduleType.INTERVAL) and not v:
            raise ValueError(f"expression is required for {schedule_type} schedules")
        return v

    @field_validator("run_at")
    @classmethod
    def validate_run_at(cls, v: datetime | None, info) -> datetime | None:
        """Validate run_at for one_time schedules."""
        schedule_type = info.data.get("type")
        if schedule_type == ScheduleType.ONE_TIME and not v:
            raise ValueError("run_at is required for one_time schedules")
        return v


class ScheduleCreate(BaseModel):
    """Request to create a new schedule."""

    workflow_id: str = Field(description="ID of the workflow to schedule")
    name: str = Field(min_length=1, max_length=255, description="Name of the schedule")
    schedule: ScheduleConfig = Field(description="Schedule configuration")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Default parameters for scheduled runs",
    )
    enabled: bool = Field(default=True, description="Whether the schedule is active")
    description: str | None = Field(default=None, max_length=1000)
    max_runs: int | None = Field(
        default=None,
        ge=1,
        description="Maximum number of runs (optional)",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="When the schedule expires (optional)",
    )


class ScheduleUpdate(BaseModel):
    """Request to update a schedule."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    schedule: ScheduleConfig | None = None
    params: dict[str, Any] | None = None
    enabled: bool | None = None
    description: str | None = Field(default=None, max_length=1000)
    max_runs: int | None = Field(default=None, ge=1)
    expires_at: datetime | None = None


class ScheduleResponse(BaseModel):
    """Response for schedule operations."""

    id: str = Field(description="Unique schedule ID")
    workflow_id: str = Field(description="ID of the scheduled workflow")
    name: str
    schedule: ScheduleConfig
    params: dict[str, Any]
    enabled: bool
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    next_run_at: datetime | None = Field(description="Next scheduled execution time")
    last_run_at: datetime | None = Field(description="Last execution time")
    last_execution_id: str | None = Field(description="ID of the last execution")
    last_execution_status: str | None = Field(description="Status of the last execution")
    run_count: int = Field(description="Total number of runs")
    max_runs: int | None = None
    expires_at: datetime | None = None
    status: str = Field(description="Schedule status: active, paused, expired, completed")


class ScheduleListResponse(BaseModel):
    """Response for listing schedules."""

    schedules: list[ScheduleResponse]
    total: int


# ============================================================================
# Internal Schedule State (for Dapr state store)
# ============================================================================


class ScheduleState(BaseModel):
    """Internal schedule state stored in Dapr state store."""

    id: str
    workflow_id: str
    name: str
    description: str | None = None
    schedule_type: ScheduleType
    expression: str | None = None
    timezone: str = "UTC"
    run_at: datetime | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    created_at: datetime
    updated_at: datetime
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_execution_id: str | None = None
    last_execution_status: str | None = None
    run_count: int = 0
    max_runs: int | None = None
    expires_at: datetime | None = None
    status: str = "active"  # active, paused, expired, completed
    created_by: str | None = None

    def to_response(self) -> ScheduleResponse:
        """Convert to API response."""
        # Use model_construct to bypass validation since data is already valid
        schedule_config = ScheduleConfig.model_construct(
            type=self.schedule_type,
            expression=self.expression,
            timezone=self.timezone,
            run_at=self.run_at,
        )
        return ScheduleResponse(
            id=self.id,
            workflow_id=self.workflow_id,
            name=self.name,
            schedule=schedule_config,
            params=self.params,
            enabled=self.enabled,
            description=self.description,
            created_at=self.created_at,
            updated_at=self.updated_at,
            next_run_at=self.next_run_at,
            last_run_at=self.last_run_at,
            last_execution_id=self.last_execution_id,
            last_execution_status=self.last_execution_status,
            run_count=self.run_count,
            max_runs=self.max_runs,
            expires_at=self.expires_at,
            status=self.status,
        )


# ============================================================================
# Webhook Schemas
# ============================================================================


class WebhookConfig(BaseModel):
    """Configuration for a webhook trigger."""

    require_secret: bool = Field(
        default=True,
        description="Whether to require secret validation",
    )
    allowed_ips: list[str] | None = Field(
        default=None,
        description="IP addresses/ranges allowed to trigger (optional)",
    )
    headers_to_include: list[str] = Field(
        default_factory=list,
        description="Request headers to pass as params",
    )


class WebhookCreate(BaseModel):
    """Request to create a webhook."""

    workflow_id: str = Field(description="ID of the workflow to trigger")
    name: str = Field(min_length=1, max_length=255, description="Name of the webhook")
    config: WebhookConfig = Field(
        default_factory=WebhookConfig,
        description="Webhook configuration",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Default parameters merged with trigger payload",
    )
    enabled: bool = Field(default=True)


class WebhookUpdate(BaseModel):
    """Request to update a webhook."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    config: WebhookConfig | None = None
    params: dict[str, Any] | None = None
    enabled: bool | None = None


class WebhookResponse(BaseModel):
    """Response for webhook operations."""

    id: str = Field(description="Unique webhook ID")
    workflow_id: str
    name: str
    endpoint_url: str = Field(description="URL to trigger the webhook")
    config: WebhookConfig
    params: dict[str, Any]
    enabled: bool
    created_at: datetime
    updated_at: datetime
    last_triggered_at: datetime | None = None
    trigger_count: int = 0
    secret: str | None = Field(
        default=None,
        description="Secret (only returned on create/rotate)",
    )


class WebhookState(BaseModel):
    """Internal webhook state stored in Dapr state store."""

    id: str
    workflow_id: str
    name: str
    secret_hash: str | None = None
    allowed_ips: list[str] | None = None
    headers_to_include: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    created_at: datetime
    updated_at: datetime
    last_triggered_at: datetime | None = None
    trigger_count: int = 0

    def to_response(self, base_url: str = "") -> WebhookResponse:
        """Convert to API response."""
        return WebhookResponse(
            id=self.id,
            workflow_id=self.workflow_id,
            name=self.name,
            endpoint_url=f"{base_url}/trigger/{self.id}",
            config=WebhookConfig(
                require_secret=self.secret_hash is not None,
                allowed_ips=self.allowed_ips,
                headers_to_include=self.headers_to_include,
            ),
            params=self.params,
            enabled=self.enabled,
            created_at=self.created_at,
            updated_at=self.updated_at,
            last_triggered_at=self.last_triggered_at,
            trigger_count=self.trigger_count,
        )


class WebhookTriggerRequest(BaseModel):
    """Request body for webhook trigger."""

    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters to pass to the workflow",
    )


class WebhookTriggerResponse(BaseModel):
    """Response for webhook trigger."""

    execution_id: str
    workflow_id: str
    status: str


# ============================================================================
# Event Trigger Schemas
# ============================================================================


class EventTriggerConfig(BaseModel):
    """Configuration for event-driven triggers."""

    event_type: str = Field(
        description="Event type to listen for (e.g., 'model.onboarded')",
    )
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Filter conditions on event data (dot notation supported)",
    )


class EventTriggerCreate(BaseModel):
    """Request to create an event trigger."""

    workflow_id: str = Field(description="ID of the workflow to trigger")
    name: str = Field(min_length=1, max_length=255)
    config: EventTriggerConfig = Field(description="Event trigger configuration")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Default parameters merged with event data",
    )
    enabled: bool = Field(default=True)


class EventTriggerUpdate(BaseModel):
    """Request to update an event trigger."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    config: EventTriggerConfig | None = None
    params: dict[str, Any] | None = None
    enabled: bool | None = None


class EventTriggerResponse(BaseModel):
    """Response for event trigger operations."""

    id: str
    workflow_id: str
    name: str
    config: EventTriggerConfig
    params: dict[str, Any]
    enabled: bool
    created_at: datetime
    updated_at: datetime
    last_triggered_at: datetime | None = None
    trigger_count: int = 0


class EventTriggerState(BaseModel):
    """Internal event trigger state stored in Dapr state store."""

    id: str
    workflow_id: str
    name: str
    event_type: str
    filters: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    created_at: datetime
    updated_at: datetime
    last_triggered_at: datetime | None = None
    trigger_count: int = 0

    def to_response(self) -> EventTriggerResponse:
        """Convert to API response."""
        return EventTriggerResponse(
            id=self.id,
            workflow_id=self.workflow_id,
            name=self.name,
            config=EventTriggerConfig(
                event_type=self.event_type,
                filters=self.filters,
            ),
            params=self.params,
            enabled=self.enabled,
            created_at=self.created_at,
            updated_at=self.updated_at,
            last_triggered_at=self.last_triggered_at,
            trigger_count=self.trigger_count,
        )


# ============================================================================
# Common Types
# ============================================================================


class TriggerInfo(BaseModel):
    """Information about what triggered a workflow execution."""

    type: str = Field(description="Trigger type: manual, scheduled, webhook, event")
    trigger_id: str | None = Field(
        default=None,
        description="ID of the schedule/webhook/event trigger",
    )
    trigger_name: str | None = Field(default=None, description="Name of the trigger")
    scheduled_at: datetime | None = Field(
        default=None,
        description="When the execution was scheduled for",
    )
    triggered_at: datetime = Field(description="When the execution was triggered")
    event_type: str | None = Field(
        default=None,
        description="Event type for event triggers",
    )


class NextRunsPreview(BaseModel):
    """Preview of upcoming scheduled runs."""

    schedule_id: str
    next_runs: list[datetime]
