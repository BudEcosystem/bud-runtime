"""Progress event API routes.

This module provides REST endpoints for progress event history
(002-pipeline-event-persistence - T058).
"""

from datetime import datetime
from uuid import UUID

from asgi_correlation_id import correlation_id
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from budpipeline.commons.database import get_db
from budpipeline.commons.observability import get_logger
from budpipeline.pipeline.persistence_service import persistence_service
from budpipeline.progress.crud import ProgressEventCRUD
from budpipeline.progress.schemas import (
    ProgressEventListResponse,
    ProgressEventResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/executions", tags=["Progress Events"])


def _get_correlation_id(
    x_correlation_id: str | None = Header(None, alias="X-Correlation-ID"),
) -> str | None:
    """Get correlation ID from header or context."""
    return x_correlation_id or correlation_id.get()


@router.get("/{execution_id}/events", response_model=ProgressEventListResponse)
async def get_execution_events(
    execution_id: UUID,
    event_type: str | None = Query(None, description="Filter by event type"),
    start_time: datetime | None = Query(None, description="Filter by timestamp >= start_time"),
    end_time: datetime | None = Query(None, description="Filter by timestamp <= end_time"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    corr_id: str | None = Depends(_get_correlation_id),
    db: AsyncSession = Depends(get_db),
) -> ProgressEventListResponse:
    """Get progress events for an execution.

    Returns progress events with optional filtering by type and time range.
    Events are ordered by timestamp descending (most recent first).

    Args:
        execution_id: Execution UUID.
        event_type: Filter by event type (workflow_progress, step_completed, etc.).
        start_time: Filter events with timestamp >= start_time.
        end_time: Filter events with timestamp <= end_time.
        limit: Maximum events to return.
        offset: Number of events to skip.
        corr_id: Correlation ID for tracing.
        db: Database session.

    Returns:
        ProgressEventListResponse with events and total count.

    Raises:
        404: Execution not found.
    """
    logger.info(
        "Getting execution events",
        execution_id=str(execution_id),
        event_type=event_type,
        start_time=str(start_time) if start_time else None,
        end_time=str(end_time) if end_time else None,
        limit=limit,
        offset=offset,
        correlation_id=corr_id,
    )

    # Verify execution exists
    execution = await persistence_service.get_execution(execution_id)
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {"code": "NOT_FOUND", "message": f"Execution {execution_id} not found"},
                "correlation_id": corr_id,
            },
        )

    # Get events with filters
    crud = ProgressEventCRUD(db)
    events, total = await crud.list_with_filters(
        execution_id=execution_id,
        event_type=event_type,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )

    return ProgressEventListResponse(
        events=[ProgressEventResponse.model_validate(e) for e in events],
        total_count=total,
        limit=limit,
        offset=offset,
    )
