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

"""The workflow ops package, containing essential business logic, services, and routing configurations for the workflow ops."""

from typing import List, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.commons import logging
from budapp.commons.dependencies import get_current_active_user, get_session, parse_ordering_fields
from budapp.commons.exceptions import ClientException
from budapp.commons.schemas import ErrorResponse, SuccessResponse
from budapp.user_ops.schemas import User

from .schemas import RetrieveWorkflowDataResponse, WorkflowFilter, WorkflowListResponse, WorkflowResponse
from .services import WorkflowService


logger = logging.get_logger(__name__)

workflow_router = APIRouter(prefix="/workflows", tags=["workflow"])


@workflow_router.get(
    "",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": WorkflowListResponse,
            "description": "Successfully listed all workflows",
        },
    },
    description="List all workflows",
)
async def list_active_workflows(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filters: WorkflowFilter = Depends(),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[WorkflowListResponse, ErrorResponse]:
    """List all workflows."""
    offset = (page - 1) * limit

    filters_dict = filters.model_dump(exclude_none=True)
    filters_dict["created_by"] = current_user.id

    try:
        db_workflows, count = await WorkflowService(session).get_all_active_workflows(
            offset, limit, filters_dict, order_by, search
        )
        return WorkflowListResponse(
            workflows=db_workflows,
            total_record=count,
            page=page,
            limit=limit,
            object="workflow.list",
            code=status.HTTP_200_OK,
        ).to_http_response()
    except ClientException as e:
        logger.exception(f"Failed to list workflows: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to list workflows: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to list workflows"
        ).to_http_response()


@workflow_router.get(
    "/{workflow_id}",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_200_OK: {
            "model": RetrieveWorkflowDataResponse,
            "description": "Successfully retrieve workflow data",
        },
    },
    description="Retrieve workflow data",
)
async def retrieve_workflow_data(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    workflow_id: UUID,
) -> Union[RetrieveWorkflowDataResponse, ErrorResponse]:
    """Retrieve workflow data."""
    try:
        return await WorkflowService(session).retrieve_workflow_data(workflow_id)
    except ClientException as e:
        logger.exception(f"Failed to retrieve workflow data: {e}")
        return ErrorResponse(code=status.HTTP_400_BAD_REQUEST, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to retrieve workflow data: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to retrieve workflow data"
        ).to_http_response()


@workflow_router.patch(
    "/{workflow_id}",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Resource not found",
        },
        status.HTTP_200_OK: {
            "model": WorkflowResponse,
            "description": "Successfully mark workflow as completed",
        },
    },
    description="Mark workflow as completed",
)
async def mark_workflow_as_completed(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    workflow_id: UUID,
) -> Union[WorkflowResponse, ErrorResponse]:
    """Mark workflow as completed."""
    try:
        db_workflow = await WorkflowService(session).mark_workflow_as_completed(workflow_id, current_user.id)
        return WorkflowResponse(
            id=db_workflow.id,
            total_steps=db_workflow.total_steps,
            status=db_workflow.status,
            current_step=db_workflow.current_step,
            reason=db_workflow.reason,
            code=status.HTTP_200_OK,
            object="workflow.get",
            message="Workflow marked as completed",
        ).to_http_response()
    except ClientException as e:
        logger.exception(f"Failed to mark workflow as completed: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to mark workflow as completed: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to mark workflow as completed"
        ).to_http_response()


@workflow_router.delete(
    "/{workflow_id}",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Resource not found",
        },
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully delete workflow",
        },
    },
    description="Delete workflow",
)
async def delete_workflow(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    workflow_id: UUID,
) -> Union[SuccessResponse, ErrorResponse]:
    """Delete workflow."""
    try:
        success_response = await WorkflowService(session).delete_workflow(workflow_id, current_user.id)
        return SuccessResponse(
            code=status.HTTP_200_OK,
            object="workflow.delete",
            message=success_response,
        ).to_http_response()
    except ClientException as e:
        logger.exception(f"Failed to delete workflow: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to delete workflow: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to delete workflow"
        ).to_http_response()
