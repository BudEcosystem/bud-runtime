"""Execution persistence API routes.

This module provides REST endpoints for pipeline execution persistence
with correlation IDs and resilience features
(002-pipeline-event-persistence - T034, T035, T036).
"""

from datetime import datetime
from uuid import UUID

from asgi_correlation_id import correlation_id
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from budpipeline.commons.database import get_db
from budpipeline.commons.observability import get_logger
from budpipeline.commons.resilience import get_staleness_header
from budpipeline.pipeline.models import ExecutionStatus
from budpipeline.pipeline.persistence_service import persistence_service
from budpipeline.pipeline.schemas import (
    AggregatedProgress,
    EphemeralExecutionRequest,
    ExecutionCreateRequest,
    ExecutionListResponse,
    ExecutionResponse,
    PaginationInfo,
    PipelineExecutionResponse,
    StepExecutionResponse,
)
from budpipeline.pipeline.service import pipeline_service
from budpipeline.progress.schemas import (
    ExecutionProgressResponse,
    ProgressEventResponse,
)
from budpipeline.progress.service import progress_service

logger = get_logger(__name__)

router = APIRouter(prefix="/executions", tags=["Executions"])


def _get_correlation_id(
    x_correlation_id: str | None = Header(None, alias="X-Correlation-ID"),
) -> str | None:
    """Get correlation ID from header or context."""
    return x_correlation_id or correlation_id.get()


def _add_response_headers(response: JSONResponse, corr_id: str | None) -> JSONResponse:
    """Add standard response headers."""
    if corr_id:
        response.headers["X-Correlation-ID"] = corr_id

    # Add staleness header if in fallback mode
    staleness_headers = get_staleness_header()
    for key, value in staleness_headers.items():
        response.headers[key] = value

    return response


@router.get("/{execution_id}", response_model=PipelineExecutionResponse)
async def get_execution(
    execution_id: UUID,
    corr_id: str | None = Depends(_get_correlation_id),
    db: AsyncSession = Depends(get_db),
) -> PipelineExecutionResponse:
    """Get pipeline execution by ID.

    Retrieves execution details from database or fallback storage.
    Returns X-Correlation-ID and X-Data-Staleness headers.

    Args:
        execution_id: Execution UUID.
        corr_id: Correlation ID for tracing.
        db: Database session.

    Returns:
        PipelineExecutionResponse with execution details.

    Raises:
        404: Execution not found.
        503: Service unavailable (database error with no fallback).
    """
    logger.info(
        "Getting execution",
        execution_id=str(execution_id),
        correlation_id=corr_id,
    )

    execution = await persistence_service.get_execution(execution_id)

    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {"code": "NOT_FOUND", "message": f"Execution {execution_id} not found"},
                "correlation_id": corr_id,
            },
        )

    return PipelineExecutionResponse.model_validate(execution)


@router.get("/{execution_id}/progress", response_model=ExecutionProgressResponse)
async def get_execution_progress(
    execution_id: UUID,
    detail: str = Query(
        "full", description="Level of detail: 'summary', 'steps', or 'full' (T067)"
    ),
    include_events: bool = Query(True, description="Include recent progress events (T067)"),
    events_limit: int = Query(20, ge=1, le=100, description="Max events to include"),
    corr_id: str | None = Depends(_get_correlation_id),
    db: AsyncSession = Depends(get_db),
) -> ExecutionProgressResponse:
    """Get detailed execution progress with granularity options (T067, T070).

    Returns step-by-step progress including StepExecution and ProgressEvent records.
    Aggregates progress using weighted averaging across concurrent steps.

    Granularity options:
    - summary: Only execution status and aggregated progress
    - steps: Include step details
    - full: Include step details and progress events

    Late-joining clients (T070): Always returns complete current state from DB,
    including final status and outputs for completed executions.

    Args:
        execution_id: Execution UUID.
        detail: Level of detail ('summary', 'steps', or 'full').
        include_events: Whether to include recent events.
        events_limit: Maximum events to return.
        corr_id: Correlation ID for tracing.
        db: Database session.

    Returns:
        ExecutionProgressResponse with execution, steps, events, and aggregated progress.

    Raises:
        404: Execution not found.
    """
    logger.info(
        "Getting execution progress",
        execution_id=str(execution_id),
        detail=detail,
        include_events=include_events,
        correlation_id=corr_id,
    )

    # Always get execution with full state (T070 - late joining clients)
    execution = await persistence_service.get_execution(
        execution_id,
        include_steps=True,
        include_events=include_events and detail == "full",
    )

    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {"code": "NOT_FOUND", "message": f"Execution {execution_id} not found"},
                "correlation_id": corr_id,
            },
        )

    # Get steps based on detail level
    step_responses = []
    if detail in ("steps", "full"):
        steps = await persistence_service.get_execution_steps(execution_id)
        step_responses = [StepExecutionResponse.model_validate(s) for s in steps]

    # Get recent events based on detail level and flag
    event_responses = []
    if include_events and detail == "full":
        recent_events = await progress_service.get_recent_events(execution_id, limit=events_limit)
        event_responses = [ProgressEventResponse.model_validate(e) for e in recent_events]

    # Calculate aggregated progress (always included)
    aggregated = await progress_service.calculate_aggregate_progress(execution_id)

    return ExecutionProgressResponse(
        execution=PipelineExecutionResponse.model_validate(execution),
        steps=step_responses,
        recent_events=event_responses,
        aggregated_progress=AggregatedProgress(
            overall_progress=aggregated["overall_progress"],
            eta_seconds=aggregated["eta_seconds"],
            completed_steps=aggregated["completed_steps"],
            total_steps=aggregated["total_steps"],
            current_step=aggregated["current_step"],
        ),
    )


@router.get("/{execution_id}/steps")
async def get_execution_steps(
    execution_id: UUID,
    corr_id: str | None = Depends(_get_correlation_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get all steps for an execution.

    Returns all StepExecution records ordered by sequence_number.

    Args:
        execution_id: Execution UUID.
        corr_id: Correlation ID for tracing.
        db: Database session.

    Returns:
        Dictionary with steps list.

    Raises:
        404: Execution not found.
    """
    logger.info(
        "Getting execution steps",
        execution_id=str(execution_id),
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

    steps = await persistence_service.get_execution_steps(execution_id)
    step_responses = [StepExecutionResponse.model_validate(s) for s in steps]

    return {"steps": step_responses}


@router.get("", response_model=ExecutionListResponse)
async def list_executions(
    start_date: datetime | None = Query(None, description="Filter by created_at >= start_date"),
    end_date: datetime | None = Query(None, description="Filter by created_at <= end_date"),
    status_filter: ExecutionStatus | None = Query(
        None, alias="status", description="Filter by status"
    ),
    initiator: str | None = Query(None, description="Filter by initiator"),
    workflow_id: UUID | None = Query(None, description="Filter by pipeline definition ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    corr_id: str | None = Depends(_get_correlation_id),
    db: AsyncSession = Depends(get_db),
) -> ExecutionListResponse:
    """List pipeline executions with filters.

    Query executions with filtering by date range, status, initiator, pipeline.
    Supports pagination. Optimized with composite indexes for <500ms response.

    Args:
        start_date: Filter by created_at >= start_date.
        end_date: Filter by created_at <= end_date.
        status_filter: Filter by execution status.
        initiator: Filter by initiator.
        workflow_id: Filter by pipeline definition ID.
        page: Page number (1-indexed).
        page_size: Items per page.
        corr_id: Correlation ID for tracing.
        db: Database session.

    Returns:
        ExecutionListResponse with executions and pagination info.
    """
    logger.info(
        "Listing executions",
        start_date=str(start_date) if start_date else None,
        end_date=str(end_date) if end_date else None,
        status=status_filter.value if status_filter else None,
        initiator=initiator,
        workflow_id=str(workflow_id) if workflow_id else None,
        page=page,
        page_size=page_size,
        correlation_id=corr_id,
    )

    executions, total_count = await persistence_service.list_executions(
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        status=status_filter,
        initiator=initiator,
        pipeline_id=workflow_id,
    )

    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0

    return ExecutionListResponse(
        executions=[PipelineExecutionResponse.model_validate(e) for e in executions],
        pagination=PaginationInfo(
            page=page,
            page_size=page_size,
            total_count=total_count,
            total_pages=total_pages,
        ),
    )


@router.post("", response_model=ExecutionResponse, status_code=status.HTTP_201_CREATED)
async def create_execution(
    request: ExecutionCreateRequest,
    corr_id: str | None = Depends(_get_correlation_id),
    db: AsyncSession = Depends(get_db),
) -> ExecutionResponse:
    """Start a new pipeline execution with database persistence.

    This endpoint accepts pipeline_id (or workflow_id for backwards compatibility)
    and params, executes the pipeline, and persists execution state to PostgreSQL.

    Args:
        request: Execution request with workflow_id and params.
        corr_id: Correlation ID for tracing.
        db: Database session.

    Returns:
        ExecutionResponse with execution details.

    Raises:
        404: Pipeline not found.
        500: Execution failed.
    """
    logger.info(
        "Starting execution",
        workflow_id=request.workflow_id,
        correlation_id=corr_id,
    )

    try:
        # Merge user_id into params for downstream action use
        execution_params = request.params.copy()
        if request.user_id:
            execution_params["user_id"] = request.user_id

        # Execute pipeline from database - uses execute_pipeline_async to look up
        # pipeline from PostgreSQL and link execution to pipeline_id
        result = await pipeline_service.execute_pipeline_async(
            session=db,
            pipeline_id=request.workflow_id,
            params=execution_params,
            callback_topics=request.callback_topics,
            initiator=request.initiator or "api",
        )

        return ExecutionResponse(
            execution_id=result["execution_id"],
            workflow_id=result["workflow_id"],
            workflow_name=result["workflow_name"],
            status=result["status"],
            started_at=result["started_at"],
            completed_at=result.get("completed_at"),
            params=result["params"],
            outputs=result.get("outputs", {}),
            error=result.get("error"),
        )
    except Exception as e:
        logger.error(f"Execution error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/run", response_model=ExecutionResponse, status_code=status.HTTP_201_CREATED)
async def run_ephemeral_execution(
    request: EphemeralExecutionRequest,
    corr_id: str | None = Depends(_get_correlation_id),
    db: AsyncSession = Depends(get_db),
) -> ExecutionResponse:
    """Execute a pipeline inline without saving the pipeline definition.

    This endpoint allows executing a pipeline definition without registering it
    in the database. The execution is tracked and persisted, but the pipeline
    definition itself is NOT saved. Useful for:
    - One-off executions
    - Testing pipeline definitions
    - Temporary/ad-hoc workflows

    The execution will have pipeline_id=None (ephemeral marker).

    Args:
        request: Ephemeral execution request with inline pipeline_definition.
        corr_id: Correlation ID for tracing.
        db: Database session.

    Returns:
        ExecutionResponse with execution details.

    Raises:
        400: Invalid pipeline definition.
        500: Execution failed.
    """
    logger.info(
        "Starting ephemeral execution",
        pipeline_name=request.pipeline_definition.get("name", "ephemeral"),
        user_id=request.user_id,
        correlation_id=corr_id,
    )

    try:
        # Validate the inline pipeline definition
        is_valid, errors, warnings = pipeline_service.validate_dag(request.pipeline_definition)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid pipeline definition", "errors": errors},
            )

        # Merge user_id into params for downstream action use
        execution_params = request.params.copy()
        if request.user_id:
            execution_params["user_id"] = request.user_id

        # Create ephemeral pipeline data (not saved to database)
        ephemeral_pipeline = {
            "id": "ephemeral",
            "name": request.pipeline_definition.get("name", "Ephemeral Pipeline"),
            "dag": request.pipeline_definition,
        }

        # Execute the ephemeral pipeline (pipeline_id=None marks it as ephemeral)
        result = await pipeline_service._execute_pipeline_impl(
            pipeline=ephemeral_pipeline,
            params=execution_params,
            callback_topics=request.callback_topics,
            initiator=request.initiator,
            pipeline_id=None,  # None marks this as an ephemeral execution
        )

        return ExecutionResponse(
            execution_id=result["execution_id"],
            workflow_id=result["workflow_id"],
            workflow_name=result["workflow_name"],
            status=result["status"],
            started_at=result["started_at"],
            completed_at=result.get("completed_at"),
            params=result["params"],
            outputs=result.get("outputs", {}),
            error=result.get("error"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ephemeral execution error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
