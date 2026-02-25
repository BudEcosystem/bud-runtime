"""Pipeline API routes.

This module provides endpoints for managing pipeline definitions.
Pipeline definitions are stored in the PostgreSQL database for persistence
across pod restarts (002-pipeline-event-persistence).

Routes have been renamed from /workflows to /pipelines.
User isolation is enforced via X-User-ID header.
"""

import contextlib
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from budpipeline.commons.database import get_db
from budpipeline.commons.dependencies import UserContext, get_user_context
from budpipeline.commons.exceptions import (
    DAGValidationError,
    DuplicatePipelineNameError,
    WorkflowNotFoundError,
)
from budpipeline.pipeline.crud import OptimisticLockError
from budpipeline.pipeline.schemas import (
    DAGValidationRequest,
    DAGValidationResponse,
    PipelineCreateRequest,
    PipelineResponse,
)
from budpipeline.pipeline.service import pipeline_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/validate", response_model=DAGValidationResponse)
async def validate_dag(request: DAGValidationRequest) -> DAGValidationResponse:
    """Validate a DAG definition without registering it."""
    try:
        is_valid, errors, warnings = pipeline_service.validate_dag(request.dag)

        step_count = 0
        has_cycles = False

        if is_valid:
            from budpipeline.engine.dag_parser import DAGParser

            dag = DAGParser.parse(request.dag)
            step_count = len(dag.steps)
        else:
            has_cycles = any("cycle" in e.lower() for e in errors)

        return DAGValidationResponse(
            valid=is_valid,
            errors=errors,
            warnings=warnings,
            step_count=step_count,
            has_cycles=has_cycles,
        )
    except Exception as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/pipelines", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    request: PipelineCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_context: UserContext = Depends(get_user_context),
) -> PipelineResponse:
    """Create/register a new pipeline from DAG definition.

    Pipelines are persisted to the database for durability across pod restarts.
    If a user_id is provided in the request body, it takes precedence over the header.
    """
    try:
        # Determine user_id: request body takes precedence, then header, then None
        user_id: UUID | None = None
        if request.user_id:
            with contextlib.suppress(ValueError):
                user_id = UUID(request.user_id)
        if user_id is None and user_context.user_id:
            user_id = user_context.user_id

        # Use async database method for persistence
        pipeline = await pipeline_service.create_pipeline_async(
            session=db,
            dag_dict=request.dag,
            name_override=request.name,
            created_by="api",  # TODO: Get from auth context
            description=None,
            icon=request.icon,
            user_id=user_id,
            system_owned=request.system_owned,
        )
        return PipelineResponse(
            id=pipeline["id"],
            name=pipeline["name"],
            version=pipeline["version"],
            status=pipeline["status"],
            created_at=pipeline["created_at"],
            step_count=pipeline["step_count"],
            user_id=pipeline.get("user_id"),
            system_owned=pipeline.get("system_owned", False),
            description=pipeline.get("description"),
            icon=pipeline.get("icon"),
            dag=pipeline.get("dag"),
        )
    except DuplicatePipelineNameError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "Duplicate pipeline name", "message": str(e.message)},
        )
    except DAGValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Validation failed", "errors": e.errors},
        )
    except Exception as e:
        logger.error(f"Create pipeline error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/pipelines", response_model=list[PipelineResponse])
async def list_pipelines(
    db: AsyncSession = Depends(get_db),
    user_context: UserContext = Depends(get_user_context),
    include_system: bool = Query(False, description="Include system-owned pipelines"),
) -> list[PipelineResponse]:
    """List pipelines from database.

    If a user context is present (via X-User-ID header), only returns pipelines
    owned by that user. Use include_system=true to also include system-owned pipelines.
    """
    pipelines = await pipeline_service.list_pipelines_async(
        session=db,
        user_id=user_context.user_id,
        include_system=include_system,
    )
    return [
        PipelineResponse(
            id=p["id"],
            name=p["name"],
            version=p["version"],
            status=p["status"],
            created_at=p["created_at"],
            step_count=p["step_count"],
            user_id=p.get("user_id"),
            system_owned=p.get("system_owned", False),
            description=p.get("description"),
            icon=p.get("icon"),
            dag=p.get("dag"),
            execution_count=p.get("execution_count", 0),
            last_execution_at=p.get("last_execution_at"),
        )
        for p in pipelines
    ]


@router.get("/pipelines/{pipeline_id}")
async def get_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
    user_context: UserContext = Depends(get_user_context),
) -> dict[str, Any]:
    """Get pipeline details including DAG definition.

    If a user context is present, checks that the user has permission to view the pipeline.
    """
    try:
        return await pipeline_service.get_pipeline_async_for_user(
            session=db,
            pipeline_id=pipeline_id,
            user_id=user_context.user_id,
        )
    except WorkflowNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline not found: {pipeline_id}",
        )


@router.delete("/pipelines/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
    user_context: UserContext = Depends(get_user_context),
) -> None:
    """Delete a pipeline from database.

    Users can only delete pipelines they own (or system-owned if they're admin).
    """
    # First check that user has permission to access this pipeline
    try:
        await pipeline_service.get_pipeline_async_for_user(
            session=db,
            pipeline_id=pipeline_id,
            user_id=user_context.user_id,
        )
    except WorkflowNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline not found: {pipeline_id}",
        )

    deleted = await pipeline_service.delete_pipeline_async(session=db, pipeline_id=pipeline_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline not found: {pipeline_id}",
        )


@router.put("/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: str,
    request: PipelineCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_context: UserContext = Depends(get_user_context),
) -> PipelineResponse:
    """Update an existing pipeline in database.

    Users can only update pipelines they own.
    """
    # First check that user has permission to access this pipeline
    try:
        await pipeline_service.get_pipeline_async_for_user(
            session=db,
            pipeline_id=pipeline_id,
            user_id=user_context.user_id,
        )
    except WorkflowNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline not found: {pipeline_id}",
        )

    try:
        pipeline = await pipeline_service.update_pipeline_async(
            session=db,
            pipeline_id=pipeline_id,
            dag_dict=request.dag,
            name_override=request.name,
            icon=request.icon,
        )
        return PipelineResponse(
            id=pipeline["id"],
            name=pipeline["name"],
            version=pipeline["version"],
            status=pipeline["status"],
            created_at=pipeline["created_at"],
            step_count=pipeline["step_count"],
            user_id=pipeline.get("user_id"),
            system_owned=pipeline.get("system_owned", False),
            description=pipeline.get("description"),
            icon=pipeline.get("icon"),
            dag=pipeline.get("dag"),
            execution_count=pipeline.get("execution_count", 0),
            last_execution_at=pipeline.get("last_execution_at"),
        )
    except WorkflowNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline not found: {pipeline_id}",
        )
    except OptimisticLockError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Concurrent modification detected: {e}",
        )
    except DuplicatePipelineNameError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "Duplicate pipeline name", "message": str(e.message)},
        )
    except DAGValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Validation failed", "errors": e.errors},
        )
    except Exception as e:
        logger.error(f"Update pipeline error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# NOTE: Execution endpoints are in execution_routes.py
# to support database persistence (002-pipeline-event-persistence).
# The following endpoints are available from execution_routes.py:
# - POST /executions - Create execution with DB persistence
# - POST /executions/run - Ephemeral execution (no saved pipeline)
# - GET /executions - List executions with filtering and pagination
# - GET /executions/{execution_id} - Get execution details
# - GET /executions/{execution_id}/progress - Get execution progress
