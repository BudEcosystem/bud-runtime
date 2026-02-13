#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""BudPipeline proxy routes - bridges budadmin frontend to budpipeline service via Dapr."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.commons import logging
from budapp.commons.dependencies import get_current_active_user, get_session
from budapp.commons.exceptions import ClientException
from budapp.commons.schemas import ErrorResponse
from budapp.user_ops.schemas import User

from .budpipeline_service import BudPipelineService


logger = logging.get_logger(__name__)

budpipeline_router = APIRouter(prefix="/budpipeline", tags=["budpipeline"])


@budpipeline_router.post(
    "/validate",
    response_class=JSONResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid DAG definition",
        },
        status.HTTP_200_OK: {
            "description": "DAG validation result",
        },
    },
    description="Validate a workflow DAG definition without creating it",
)
async def validate_workflow_dag(
    request_body: Dict[str, Any],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Validate a DAG definition without creating it."""
    try:
        result = await BudPipelineService(session).validate_dag(request_body.get("dag", {}))
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        logger.exception(f"Failed to validate DAG: {e}")
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to validate DAG: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to validate DAG"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.post(
    "/run",
    response_class=JSONResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid pipeline definition",
        },
        status.HTTP_201_CREATED: {
            "description": "Ephemeral execution started",
        },
    },
    description="Execute a pipeline inline without saving the pipeline definition",
)
async def run_ephemeral_execution(
    request_body: Dict[str, Any],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Execute a pipeline inline without saving the pipeline definition.

    This endpoint allows executing a pipeline definition without registering it
    in the database. The execution is tracked and persisted, but the pipeline
    definition itself is NOT saved. Useful for:
    - One-off executions
    - Testing pipeline definitions
    - Temporary/ad-hoc workflows

    Request body should include:
    - pipeline_definition: The inline pipeline DAG definition
    - params: Optional input parameters for the execution
    - callback_topics: Optional list of callback topics for real-time updates
    """
    try:
        result = await BudPipelineService(session).run_ephemeral_execution(
            pipeline_definition=request_body.get("pipeline_definition", {}),
            params=request_body.get("params", {}),
            callback_topics=request_body.get("callback_topics"),
            user_id=str(current_user.id),
            payload_type=request_body.get("payload_type"),
            notification_workflow_id=request_body.get("notification_workflow_id"),
        )
        return JSONResponse(content=result, status_code=status.HTTP_201_CREATED)
    except ClientException as e:
        logger.exception(f"Failed to run ephemeral execution: {e}")
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to run ephemeral execution: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to run ephemeral execution"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.post(
    "",
    response_class=JSONResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid pipeline creation request",
        },
        status.HTTP_201_CREATED: {
            "description": "Successfully created pipeline",
        },
    },
    description="Create a new pipeline in budpipeline service",
)
async def create_budpipeline(
    request_body: Dict[str, Any],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Create a new pipeline in budpipeline service."""
    try:
        result = await BudPipelineService(session).create_pipeline(
            dag=request_body.get("dag"),
            name=request_body.get("name"),
            user_id=str(current_user.id),
            system_owned=request_body.get("system_owned", False),
            icon=request_body.get("icon"),
        )
        return JSONResponse(content=result, status_code=status.HTTP_201_CREATED)
    except ClientException as e:
        logger.exception(f"Failed to create pipeline: {e}")
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to create pipeline: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to create pipeline"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.get(
    "",
    response_class=JSONResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_200_OK: {
            "description": "List of pipelines",
        },
    },
    description="List all pipelines from budpipeline service",
)
async def list_budpipelines(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    include_system: bool = Query(False, description="Include system-owned pipelines"),
):
    """List all pipelines from budpipeline service.

    If a user context is present, only returns pipelines owned by that user.
    Use include_system=true to also include system-owned pipelines.
    """
    try:
        result = await BudPipelineService(session).list_pipelines(
            user_id=str(current_user.id),
            include_system=include_system,
        )
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        logger.exception(f"Failed to list pipelines: {e}")
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to list pipelines: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to list pipelines"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.get(
    "/executions",
    response_class=JSONResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_200_OK: {
            "description": "List of workflow executions with pagination",
        },
    },
    description="List workflow executions with filtering and pagination (T059)",
)
async def list_budpipeline_executions(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    workflow_id: Optional[str] = Query(default=None, description="Filter by workflow ID"),
    status_filter: Optional[str] = Query(default=None, alias="status", description="Filter by status"),
    initiator: Optional[str] = Query(default=None, description="Filter by initiator"),
    start_date: Optional[str] = Query(default=None, description="Filter by created_at >= start_date (ISO format)"),
    end_date: Optional[str] = Query(default=None, description="Filter by created_at <= end_date (ISO format)"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
):
    """List workflow executions with filtering and pagination."""
    try:
        result = await BudPipelineService(session).list_executions_paginated(
            workflow_id=workflow_id,
            status=status_filter,
            initiator=initiator,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
        )
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        logger.exception(f"Failed to list executions: {e}")
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to list executions: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to list executions"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.get(
    "/executions/{execution_id}",
    response_class=JSONResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Execution not found",
        },
        status.HTTP_200_OK: {
            "description": "Execution details with step statuses",
        },
    },
    description="Get execution details including step statuses",
)
async def get_budpipeline_execution(
    execution_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Get execution details with step statuses."""
    try:
        result = await BudPipelineService(session).get_execution(execution_id)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        logger.exception(f"Failed to get execution: {e}")
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to get execution: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get execution"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.get(
    "/executions/{execution_id}/progress",
    response_class=JSONResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Execution not found",
        },
        status.HTTP_200_OK: {
            "description": "Execution progress with steps, events, and aggregated progress",
        },
    },
    description="Get detailed execution progress including steps, events, and aggregated progress",
)
async def get_budpipeline_execution_progress(
    execution_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Get detailed execution progress with aggregated progress info.

    Returns step-by-step progress including:
    - Execution details
    - Step executions with status and progress
    - Recent progress events
    - Aggregated progress (overall %, ETA, completed/total steps)
    """
    try:
        result = await BudPipelineService(session).get_execution_progress(execution_id)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        logger.exception(f"Failed to get execution progress: {e}")
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to get execution progress: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get execution progress"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# =============================================================================
# Schedule Routes (MUST be before /{workflow_id} routes)
# =============================================================================


@budpipeline_router.get(
    "/schedules",
    response_class=JSONResponse,
    description="List workflow schedules",
)
async def list_schedules(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    workflow_id: Optional[str] = Query(default=None, description="Filter by workflow ID"),
):
    """List workflow schedules."""
    try:
        result = await BudPipelineService(session).list_schedules(workflow_id)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to list schedules: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to list schedules"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.post(
    "/schedules",
    response_class=JSONResponse,
    description="Create a workflow schedule",
)
async def create_schedule(
    request_body: Dict[str, Any],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Create a workflow schedule."""
    try:
        result = await BudPipelineService(session).create_schedule(request_body)
        return JSONResponse(content=result, status_code=status.HTTP_201_CREATED)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to create schedule: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to create schedule"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.get(
    "/schedules/{schedule_id}",
    response_class=JSONResponse,
    description="Get schedule details",
)
async def get_schedule(
    schedule_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Get schedule details."""
    try:
        result = await BudPipelineService(session).get_schedule(schedule_id)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to get schedule: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get schedule"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.put(
    "/schedules/{schedule_id}",
    response_class=JSONResponse,
    description="Update a schedule",
)
async def update_schedule(
    schedule_id: str,
    request_body: Dict[str, Any],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Update a schedule."""
    try:
        result = await BudPipelineService(session).update_schedule(schedule_id, request_body)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to update schedule: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to update schedule"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.delete(
    "/schedules/{schedule_id}",
    response_class=JSONResponse,
    description="Delete a schedule",
)
async def delete_schedule(
    schedule_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Delete a schedule."""
    try:
        await BudPipelineService(session).delete_schedule(schedule_id)
        return JSONResponse(content={}, status_code=status.HTTP_204_NO_CONTENT)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to delete schedule: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to delete schedule"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.post(
    "/schedules/{schedule_id}/pause",
    response_class=JSONResponse,
    description="Pause a schedule",
)
async def pause_schedule(
    schedule_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Pause a schedule."""
    try:
        result = await BudPipelineService(session).pause_schedule(schedule_id)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to pause schedule: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to pause schedule"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.post(
    "/schedules/{schedule_id}/resume",
    response_class=JSONResponse,
    description="Resume a paused schedule",
)
async def resume_schedule(
    schedule_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Resume a paused schedule."""
    try:
        result = await BudPipelineService(session).resume_schedule(schedule_id)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to resume schedule: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to resume schedule"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.post(
    "/schedules/{schedule_id}/trigger",
    response_class=JSONResponse,
    description="Trigger a schedule immediately",
)
async def trigger_schedule(
    schedule_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Trigger a schedule immediately."""
    try:
        result = await BudPipelineService(session).trigger_schedule(schedule_id)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to trigger schedule: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to trigger schedule"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# =============================================================================
# Webhook Routes (MUST be before /{workflow_id} routes)
# =============================================================================


@budpipeline_router.get(
    "/webhooks",
    response_class=JSONResponse,
    description="List workflow webhooks",
)
async def list_webhooks(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    workflow_id: Optional[str] = Query(default=None, description="Filter by workflow ID"),
):
    """List workflow webhooks."""
    try:
        result = await BudPipelineService(session).list_webhooks(workflow_id)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to list webhooks: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to list webhooks"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.post(
    "/webhooks",
    response_class=JSONResponse,
    description="Create a workflow webhook",
)
async def create_webhook(
    request_body: Dict[str, Any],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Create a workflow webhook."""
    try:
        result = await BudPipelineService(session).create_webhook(request_body)
        return JSONResponse(content=result, status_code=status.HTTP_201_CREATED)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to create webhook: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to create webhook"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.delete(
    "/webhooks/{webhook_id}",
    response_class=JSONResponse,
    description="Delete a webhook",
)
async def delete_webhook(
    webhook_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Delete a webhook."""
    try:
        await BudPipelineService(session).delete_webhook(webhook_id)
        return JSONResponse(content={}, status_code=status.HTTP_204_NO_CONTENT)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to delete webhook: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to delete webhook"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.post(
    "/webhooks/{webhook_id}/rotate-secret",
    response_class=JSONResponse,
    description="Rotate a webhook's secret",
)
async def rotate_webhook_secret(
    webhook_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Rotate a webhook's secret."""
    try:
        result = await BudPipelineService(session).rotate_webhook_secret(webhook_id)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to rotate webhook secret: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to rotate webhook secret"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# =============================================================================
# Event Trigger Routes (MUST be before /{workflow_id} routes)
# =============================================================================


@budpipeline_router.get(
    "/event-triggers",
    response_class=JSONResponse,
    description="List event triggers",
)
async def list_event_triggers(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    workflow_id: Optional[str] = Query(default=None, description="Filter by workflow ID"),
):
    """List event triggers."""
    try:
        result = await BudPipelineService(session).list_event_triggers(workflow_id)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to list event triggers: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to list event triggers"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.post(
    "/event-triggers",
    response_class=JSONResponse,
    description="Create an event trigger",
)
async def create_event_trigger(
    request_body: Dict[str, Any],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Create an event trigger."""
    try:
        result = await BudPipelineService(session).create_event_trigger(request_body)
        return JSONResponse(content=result, status_code=status.HTTP_201_CREATED)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to create event trigger: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to create event trigger"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.delete(
    "/event-triggers/{trigger_id}",
    response_class=JSONResponse,
    description="Delete an event trigger",
)
async def delete_event_trigger(
    trigger_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Delete an event trigger."""
    try:
        await BudPipelineService(session).delete_event_trigger(trigger_id)
        return JSONResponse(content={}, status_code=status.HTTP_204_NO_CONTENT)
    except ClientException as e:
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to delete event trigger: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to delete event trigger"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# =============================================================================
# Actions API Routes (Pluggable Action Architecture)
# =============================================================================


@budpipeline_router.get(
    "/actions",
    response_class=JSONResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_200_OK: {
            "description": "List of available pipeline actions",
        },
    },
    description="List all available pipeline actions with metadata",
)
async def list_actions(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """List all available pipeline actions with metadata.

    Returns actions grouped by category for the pipeline editor.
    """
    try:
        result = await BudPipelineService(session).list_actions()
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        logger.exception(f"Failed to list actions: {e}")
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to list actions: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to list actions"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.get(
    "/actions/{action_type}",
    response_class=JSONResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Action type not found",
        },
        status.HTTP_200_OK: {
            "description": "Action metadata",
        },
    },
    description="Get metadata for a specific action type",
)
async def get_action(
    action_type: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Get metadata for a specific action type.

    Returns complete action metadata including parameters, outputs, and execution mode.
    """
    try:
        result = await BudPipelineService(session).get_action(action_type)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        logger.exception(f"Failed to get action {action_type}: {e}")
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to get action {action_type}: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get action"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.post(
    "/actions/validate",
    response_class=JSONResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_200_OK: {
            "description": "Validation result",
        },
    },
    description="Validate parameters for an action type",
)
async def validate_action_params(
    request_body: Dict[str, Any],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Validate parameters for an action type.

    Request body should contain:
    - action_type: The action type to validate against
    - params: The parameters to validate
    """
    try:
        result = await BudPipelineService(session).validate_action_params(
            action_type=request_body.get("action_type", ""),
            params=request_body.get("params", {}),
        )
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        logger.exception(f"Failed to validate action params: {e}")
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to validate action params: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to validate action params"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# =============================================================================
# Pipeline Routes (parameterized routes MUST come after specific routes)
# =============================================================================


@budpipeline_router.get(
    "/{pipeline_id}",
    response_class=JSONResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Pipeline not found",
        },
        status.HTTP_200_OK: {
            "description": "Pipeline details including DAG",
        },
    },
    description="Get pipeline details including DAG definition",
)
async def get_budpipeline(
    pipeline_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Get pipeline details including DAG."""
    try:
        result = await BudPipelineService(session).get_pipeline(
            pipeline_id=pipeline_id,
            user_id=str(current_user.id),
        )
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        logger.exception(f"Failed to get pipeline: {e}")
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to get pipeline: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get pipeline"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.put(
    "/{pipeline_id}",
    response_class=JSONResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Pipeline not found",
        },
        status.HTTP_200_OK: {
            "description": "Updated pipeline",
        },
    },
    description="Update a pipeline's DAG definition",
)
async def update_budpipeline(
    pipeline_id: str,
    request_body: Dict[str, Any],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Update a pipeline's DAG definition."""
    try:
        result = await BudPipelineService(session).update_pipeline(
            pipeline_id=pipeline_id,
            dag=request_body.get("dag"),
            name=request_body.get("name"),
            user_id=str(current_user.id),
            icon=request_body.get("icon"),
        )
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    except ClientException as e:
        logger.exception(f"Failed to update pipeline: {e}")
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to update pipeline: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to update pipeline"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.delete(
    "/{pipeline_id}",
    response_class=JSONResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Pipeline not found",
        },
        status.HTTP_204_NO_CONTENT: {
            "description": "Pipeline deleted successfully",
        },
    },
    description="Delete a pipeline",
)
async def delete_budpipeline(
    pipeline_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Delete a pipeline."""
    try:
        await BudPipelineService(session).delete_pipeline(
            pipeline_id=pipeline_id,
            user_id=str(current_user.id),
        )
        return JSONResponse(content={}, status_code=status.HTTP_204_NO_CONTENT)
    except ClientException as e:
        logger.exception(f"Failed to delete pipeline: {e}")
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to delete pipeline: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to delete pipeline"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@budpipeline_router.post(
    "/{pipeline_id}/execute",
    response_class=JSONResponse,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Pipeline not found",
        },
        status.HTTP_201_CREATED: {
            "description": "Pipeline execution started",
        },
    },
    description="Start a pipeline execution",
)
async def execute_budpipeline(
    pipeline_id: str,
    request_body: Dict[str, Any],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Start a pipeline execution.

    Request body can include:
    - params: Input parameters for the execution
    - callback_topics: List of callback topics for real-time progress updates (D-004)
    """
    try:
        result = await BudPipelineService(session).execute_pipeline(
            pipeline_id=pipeline_id,
            params=request_body.get("params", {}),
            callback_topics=request_body.get("callback_topics"),
            user_id=str(current_user.id),
            payload_type=request_body.get("payload_type"),
            notification_workflow_id=request_body.get("notification_workflow_id"),
        )
        return JSONResponse(content=result, status_code=status.HTTP_201_CREATED)
    except ClientException as e:
        logger.exception(f"Failed to execute pipeline: {e}")
        return JSONResponse(
            content=ErrorResponse(code=e.status_code, message=e.message).model_dump(mode="json"),
            status_code=e.status_code,
        )
    except Exception as e:
        logger.exception(f"Failed to execute pipeline: {e}")
        return JSONResponse(
            content=ErrorResponse(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to execute pipeline"
            ).model_dump(mode="json"),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
