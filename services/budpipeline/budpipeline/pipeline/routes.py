"""Workflow API routes."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status

from budpipeline.commons.exceptions import (
    DAGValidationError,
    ExecutionNotFoundError,
    WorkflowNotFoundError,
)
from budpipeline.pipeline.schemas import (
    DAGValidationRequest,
    DAGValidationResponse,
    ExecutionCreateRequest,
    ExecutionDetailResponse,
    ExecutionResponse,
    StepStatusResponse,
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
async def create_workflow(request: WorkflowCreateRequest) -> WorkflowResponse:
    """Create/register a new workflow from DAG definition."""
    try:
        workflow = workflow_service.create_workflow(request.dag, request.name)
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
async def list_workflows() -> list[WorkflowResponse]:
    """List all registered workflows."""
    workflows = workflow_service.list_workflows()
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
async def get_workflow(workflow_id: str) -> dict[str, Any]:
    """Get workflow details including DAG definition."""
    try:
        return workflow_service.get_workflow(workflow_id)
    except WorkflowNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}",
        )


@router.delete("/workflows/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(workflow_id: str) -> None:
    """Delete a workflow."""
    if not workflow_service.delete_workflow(workflow_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}",
        )


@router.put("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(workflow_id: str, request: WorkflowCreateRequest) -> WorkflowResponse:
    """Update an existing workflow."""
    try:
        workflow = workflow_service.update_workflow(workflow_id, request.dag, request.name)
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


@router.post("/executions", response_model=ExecutionResponse, status_code=status.HTTP_201_CREATED)
async def create_execution(request: ExecutionCreateRequest) -> ExecutionResponse:
    """Start a new workflow execution."""
    try:
        result = await workflow_service.execute_workflow(request.workflow_id, request.params)
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
    except ExecutionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {request.workflow_id}",
        )
    except Exception as e:
        logger.error(f"Execution error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/executions", response_model=list[ExecutionResponse])
async def list_executions(workflow_id: str | None = None) -> list[ExecutionResponse]:
    """List executions, optionally filtered by workflow ID."""
    executions = workflow_service.list_executions(workflow_id)
    return [
        ExecutionResponse(
            execution_id=e["execution_id"],
            workflow_id=e["workflow_id"],
            workflow_name=e["workflow_name"],
            status=e["status"],
            started_at=e["started_at"],
            completed_at=e.get("completed_at"),
            params=e["params"],
            outputs=e.get("outputs", {}),
            error=e.get("error"),
        )
        for e in executions
    ]


@router.get("/executions/{execution_id}", response_model=ExecutionDetailResponse)
async def get_execution(execution_id: str) -> ExecutionDetailResponse:
    """Get detailed execution status including step statuses."""
    try:
        e = workflow_service.get_execution(execution_id)
        steps = [
            StepStatusResponse(
                step_id=s["step_id"],
                name=s["name"],
                status=s["status"],
                started_at=s.get("started_at"),
                completed_at=s.get("completed_at"),
                outputs=s.get("outputs", {}),
                error=s.get("error"),
            )
            for s in e.get("steps", {}).values()
        ]
        return ExecutionDetailResponse(
            execution_id=e["execution_id"],
            workflow_id=e["workflow_id"],
            workflow_name=e["workflow_name"],
            status=e["status"],
            started_at=e["started_at"],
            completed_at=e.get("completed_at"),
            params=e["params"],
            outputs=e.get("outputs", {}),
            error=e.get("error"),
            steps=steps,
        )
    except ExecutionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution not found: {execution_id}",
        )
