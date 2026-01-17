"""Workflow API routes.

This module provides endpoints for managing pipeline definitions (workflows).
Pipeline definitions are now stored in the PostgreSQL database for persistence
across pod restarts (002-pipeline-event-persistence).
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from budpipeline.commons.database import get_db
from budpipeline.commons.exceptions import (
    DAGValidationError,
    WorkflowNotFoundError,
)
from budpipeline.pipeline.crud import OptimisticLockError
from budpipeline.pipeline.schemas import (
    DAGValidationRequest,
    DAGValidationResponse,
    WorkflowCreateRequest,
    WorkflowResponse,
)
from budpipeline.pipeline.service import workflow_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/validate", response_model=DAGValidationResponse)
async def validate_dag(request: DAGValidationRequest) -> DAGValidationResponse:
    """Validate a DAG definition without registering it."""
    try:
        is_valid, errors, warnings = workflow_service.validate_dag(request.dag)

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


@router.post("/workflows", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    request: WorkflowCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    """Create/register a new workflow from DAG definition.

    Workflows are persisted to the database for durability across pod restarts.
    """
    try:
        # Use async database method for persistence
        workflow = await workflow_service.create_workflow_async(
            session=db,
            dag_dict=request.dag,
            name_override=request.name,
            created_by="api",  # TODO: Get from auth context
            description=None,
        )
        return WorkflowResponse(
            id=workflow["id"],
            name=workflow["name"],
            version=workflow["version"],
            status=workflow["status"],
            created_at=workflow["created_at"],
            step_count=workflow["step_count"],
        )
    except DAGValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Validation failed", "errors": e.errors},
        )
    except Exception as e:
        logger.error(f"Create workflow error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/workflows", response_model=list[WorkflowResponse])
async def list_workflows(
    db: AsyncSession = Depends(get_db),
) -> list[WorkflowResponse]:
    """List all registered workflows from database."""
    workflows = await workflow_service.list_workflows_async(session=db)
    return [
        WorkflowResponse(
            id=w["id"],
            name=w["name"],
            version=w["version"],
            status=w["status"],
            created_at=w["created_at"],
            step_count=w["step_count"],
        )
        for w in workflows
    ]


@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get workflow details including DAG definition."""
    try:
        return await workflow_service.get_workflow_async(session=db, workflow_id=workflow_id)
    except WorkflowNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}",
        )


@router.delete("/workflows/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a workflow from database."""
    deleted = await workflow_service.delete_workflow_async(session=db, workflow_id=workflow_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}",
        )


@router.put("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    request: WorkflowCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    """Update an existing workflow in database."""
    try:
        workflow = await workflow_service.update_workflow_async(
            session=db,
            workflow_id=workflow_id,
            dag_dict=request.dag,
            name_override=request.name,
        )
        return WorkflowResponse(
            id=workflow["id"],
            name=workflow["name"],
            version=workflow["version"],
            status=workflow["status"],
            created_at=workflow["created_at"],
            step_count=workflow["step_count"],
        )
    except WorkflowNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}",
        )
    except OptimisticLockError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Concurrent modification detected: {e}",
        )
    except DAGValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Validation failed", "errors": e.errors},
        )
    except Exception as e:
        logger.error(f"Update workflow error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# NOTE: Execution endpoints have been moved to execution_routes.py
# to support database persistence (002-pipeline-event-persistence).
# The following endpoints are now available from execution_routes.py:
# - POST /executions - Create execution with DB persistence
# - GET /executions - List executions with filtering and pagination
# - GET /executions/{execution_id} - Get execution details
# - GET /executions/{execution_id}/progress - Get execution progress
