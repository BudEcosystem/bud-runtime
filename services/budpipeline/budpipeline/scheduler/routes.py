"""Scheduler Routes - API endpoints for schedules, webhooks, and event triggers.

Provides RESTful API for managing workflow triggers.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status

from budpipeline.pipeline.service import workflow_service
from budpipeline.scheduler.schemas import (
    EventTriggerCreate,
    EventTriggerResponse,
    EventTriggerUpdate,
    NextRunsPreview,
    ScheduleCreate,
    ScheduleListResponse,
    ScheduleResponse,
    ScheduleUpdate,
    WebhookCreate,
    WebhookResponse,
    WebhookTriggerRequest,
    WebhookTriggerResponse,
    WebhookUpdate,
)
from budpipeline.scheduler.services import (
    ScheduleServiceError,
    event_trigger_service,
    schedule_service,
    webhook_service,
)
from budpipeline.scheduler.storage import schedule_storage

logger = logging.getLogger(__name__)


# ============================================================================
# Schedule Routes
# ============================================================================

schedule_router = APIRouter(prefix="/schedules", tags=["Schedules"])


@schedule_router.post(
    "",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new schedule",
)
async def create_schedule(request: ScheduleCreate) -> ScheduleResponse:
    """Create a new schedule for a workflow.

    Schedules can be cron-based, interval-based, or one-time.
    """
    try:
        return await schedule_service.create_schedule(request)
    except ScheduleServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@schedule_router.get(
    "",
    response_model=ScheduleListResponse,
    summary="List schedules",
)
async def list_schedules(
    workflow_id: str | None = Query(default=None, description="Filter by workflow ID"),
    enabled: bool | None = Query(default=None, description="Filter by enabled status"),
    status_filter: str | None = Query(default=None, alias="status", description="Filter by status"),
) -> ScheduleListResponse:
    """List all schedules with optional filters."""
    schedules = await schedule_service.list_schedules(
        workflow_id=workflow_id,
        enabled=enabled,
        status=status_filter,
    )
    return ScheduleListResponse(schedules=schedules, total=len(schedules))


@schedule_router.get(
    "/{schedule_id}",
    response_model=ScheduleResponse,
    summary="Get schedule details",
)
async def get_schedule(schedule_id: str) -> ScheduleResponse:
    """Get details of a specific schedule."""
    schedule = await schedule_service.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@schedule_router.put(
    "/{schedule_id}",
    response_model=ScheduleResponse,
    summary="Update a schedule",
)
async def update_schedule(
    schedule_id: str,
    request: ScheduleUpdate,
) -> ScheduleResponse:
    """Update a schedule."""
    try:
        schedule = await schedule_service.update_schedule(schedule_id, request)
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        return schedule
    except ScheduleServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@schedule_router.delete(
    "/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a schedule",
)
async def delete_schedule(schedule_id: str) -> None:
    """Delete a schedule."""
    deleted = await schedule_service.delete_schedule(schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schedule not found")


@schedule_router.post(
    "/{schedule_id}/pause",
    response_model=ScheduleResponse,
    summary="Pause a schedule",
)
async def pause_schedule(schedule_id: str) -> ScheduleResponse:
    """Pause a schedule (stop triggering)."""
    schedule = await schedule_service.pause_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@schedule_router.post(
    "/{schedule_id}/resume",
    response_model=ScheduleResponse,
    summary="Resume a schedule",
)
async def resume_schedule(schedule_id: str) -> ScheduleResponse:
    """Resume a paused schedule."""
    try:
        schedule = await schedule_service.resume_schedule(schedule_id)
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        return schedule
    except ScheduleServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@schedule_router.post(
    "/{schedule_id}/trigger",
    summary="Trigger schedule immediately",
)
async def trigger_schedule_now(
    schedule_id: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Manually trigger a scheduled workflow now.

    Optionally override parameters for this execution.
    """
    schedule = await schedule_storage.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Merge params
    merged_params = {
        **schedule.params,
        **(params or {}),
        "_trigger": {
            "type": "scheduled",
            "schedule_id": schedule.id,
            "schedule_name": schedule.name,
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "manual": True,
        },
    }

    # Execute workflow
    try:
        result = await workflow_service.execute_workflow(
            workflow_id=schedule.workflow_id,
            params=merged_params,
        )
        return {
            "execution_id": result.get("execution_id"),
            "workflow_id": schedule.workflow_id,
            "status": result.get("status", "pending"),
        }
    except Exception as e:
        logger.error(f"Failed to trigger schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger: {str(e)}")


@schedule_router.get(
    "/{schedule_id}/next-runs",
    response_model=NextRunsPreview,
    summary="Preview next runs",
)
async def preview_next_runs(
    schedule_id: str,
    count: int = Query(default=10, ge=1, le=100, description="Number of runs to preview"),
) -> NextRunsPreview:
    """Preview the next N scheduled run times."""
    preview = await schedule_service.get_next_runs(schedule_id, count)
    if not preview:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return preview


# ============================================================================
# Webhook Routes
# ============================================================================

webhook_router = APIRouter(tags=["Webhooks"])


def get_base_url(request: Request) -> str:
    """Get base URL for webhook endpoint URLs."""
    return str(request.base_url).rstrip("/")


@webhook_router.post(
    "/webhooks",
    response_model=WebhookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a webhook",
)
async def create_webhook(
    request_body: WebhookCreate,
    request: Request,
) -> WebhookResponse:
    """Create a new webhook trigger.

    The secret is only returned once in this response. Store it securely.
    """
    response, secret = await webhook_service.create_webhook(request_body)
    response.endpoint_url = f"{get_base_url(request)}/trigger/{response.id}"
    return response


@webhook_router.get(
    "/webhooks",
    response_model=list[WebhookResponse],
    summary="List webhooks",
)
async def list_webhooks(
    request: Request,
    workflow_id: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
) -> list[WebhookResponse]:
    """List all webhooks."""
    return await webhook_service.list_webhooks(
        workflow_id=workflow_id,
        enabled=enabled,
        base_url=get_base_url(request),
    )


@webhook_router.get(
    "/webhooks/{webhook_id}",
    response_model=WebhookResponse,
    summary="Get webhook details",
)
async def get_webhook(webhook_id: str, request: Request) -> WebhookResponse:
    """Get details of a specific webhook."""
    webhook = await webhook_service.get_webhook(webhook_id, get_base_url(request))
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return webhook


@webhook_router.put(
    "/webhooks/{webhook_id}",
    response_model=WebhookResponse,
    summary="Update a webhook",
)
async def update_webhook(
    webhook_id: str,
    request_body: WebhookUpdate,
    request: Request,
) -> WebhookResponse:
    """Update a webhook."""
    webhook = await webhook_service.update_webhook(webhook_id, request_body, get_base_url(request))
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return webhook


@webhook_router.delete(
    "/webhooks/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a webhook",
)
async def delete_webhook(webhook_id: str) -> None:
    """Delete a webhook."""
    deleted = await webhook_service.delete_webhook(webhook_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook not found")


@webhook_router.post(
    "/webhooks/{webhook_id}/rotate-secret",
    response_model=WebhookResponse,
    summary="Rotate webhook secret",
)
async def rotate_webhook_secret(
    webhook_id: str,
    request: Request,
) -> WebhookResponse:
    """Generate a new secret for a webhook.

    The new secret is only returned once in this response.
    """
    response, _ = await webhook_service.rotate_secret(webhook_id, get_base_url(request))
    if not response:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return response


@webhook_router.post(
    "/trigger/{webhook_id}",
    response_model=WebhookTriggerResponse,
    summary="Trigger webhook",
)
async def trigger_webhook(
    webhook_id: str,
    request: Request,
    payload: WebhookTriggerRequest | None = None,
) -> WebhookTriggerResponse:
    """Trigger a workflow via webhook.

    Validates:
    - X-Webhook-Secret header if secret is configured
    - Client IP if IP whitelist is configured
    """
    # Get webhook
    webhook = await schedule_storage.get_webhook(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    if not webhook.enabled:
        raise HTTPException(status_code=403, detail="Webhook is disabled")

    # Validate secret
    if webhook.secret_hash:
        provided_secret = request.headers.get("X-Webhook-Secret", "")
        if not webhook_service.validate_secret(webhook, provided_secret):
            raise HTTPException(status_code=401, detail="Invalid secret")

    # Validate IP
    client_ip = request.client.host if request.client else ""
    if not webhook_service.validate_ip(webhook, client_ip):
        raise HTTPException(status_code=403, detail="IP not allowed")

    # Extract headers to include
    extra_params: dict[str, Any] = {}
    for header in webhook.headers_to_include:
        if header in request.headers:
            extra_params[f"header_{header.lower().replace('-', '_')}"] = request.headers[header]

    # Merge params
    payload_params = payload.params if payload else {}
    merged_params = {
        **webhook.params,
        **payload_params,
        **extra_params,
        "_trigger": {
            "type": "webhook",
            "webhook_id": webhook.id,
            "webhook_name": webhook.name,
            "triggered_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    # Execute workflow
    try:
        result = await workflow_service.execute_workflow(
            workflow_id=webhook.workflow_id,
            params=merged_params,
        )

        # Update webhook stats
        await schedule_storage.update_webhook_triggered(webhook_id)

        return WebhookTriggerResponse(
            execution_id=result.get("execution_id", ""),
            workflow_id=webhook.workflow_id,
            status=result.get("status", "pending"),
        )

    except Exception as e:
        logger.error(f"Failed to trigger webhook {webhook_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger: {str(e)}")


# ============================================================================
# Event Trigger Routes
# ============================================================================

event_trigger_router = APIRouter(prefix="/event-triggers", tags=["Event Triggers"])


@event_trigger_router.post(
    "",
    response_model=EventTriggerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an event trigger",
)
async def create_event_trigger(request: EventTriggerCreate) -> EventTriggerResponse:
    """Create an event-driven trigger."""
    try:
        return await event_trigger_service.create_event_trigger(request)
    except ScheduleServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@event_trigger_router.get(
    "",
    response_model=list[EventTriggerResponse],
    summary="List event triggers",
)
async def list_event_triggers(
    event_type: str | None = Query(default=None),
    workflow_id: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
) -> list[EventTriggerResponse]:
    """List all event triggers."""
    return await event_trigger_service.list_event_triggers(
        event_type=event_type,
        workflow_id=workflow_id,
        enabled=enabled,
    )


@event_trigger_router.get(
    "/event-types",
    summary="List supported event types",
)
async def list_event_types() -> list[dict[str, str]]:
    """List all supported event types that can trigger workflows."""
    return event_trigger_service.get_supported_events()


@event_trigger_router.get(
    "/{trigger_id}",
    response_model=EventTriggerResponse,
    summary="Get event trigger details",
)
async def get_event_trigger(trigger_id: str) -> EventTriggerResponse:
    """Get details of a specific event trigger."""
    trigger = await event_trigger_service.get_event_trigger(trigger_id)
    if not trigger:
        raise HTTPException(status_code=404, detail="Event trigger not found")
    return trigger


@event_trigger_router.put(
    "/{trigger_id}",
    response_model=EventTriggerResponse,
    summary="Update an event trigger",
)
async def update_event_trigger(
    trigger_id: str,
    request: EventTriggerUpdate,
) -> EventTriggerResponse:
    """Update an event trigger."""
    try:
        trigger = await event_trigger_service.update_event_trigger(trigger_id, request)
        if not trigger:
            raise HTTPException(status_code=404, detail="Event trigger not found")
        return trigger
    except ScheduleServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@event_trigger_router.delete(
    "/{trigger_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an event trigger",
)
async def delete_event_trigger(trigger_id: str) -> None:
    """Delete an event trigger."""
    deleted = await event_trigger_service.delete_event_trigger(trigger_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Event trigger not found")
