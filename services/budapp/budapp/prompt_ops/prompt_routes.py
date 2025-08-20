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

"""API routes for the prompt ops module."""

from typing import Annotated, List, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.constants import PermissionEnum
from budapp.commons.dependencies import (
    get_current_active_user,
    get_session,
    parse_ordering_fields,
)
from budapp.commons.exceptions import ClientException
from budapp.commons.permission_handler import require_permissions
from budapp.commons.schemas import ErrorResponse, SuccessResponse
from budapp.user_ops.schemas import User
from budapp.workflow_ops.schemas import RetrieveWorkflowDataResponse
from budapp.workflow_ops.services import WorkflowService

from .schemas import (
    CreatePromptWorkflowRequest,
    EditPromptRequest,
    PromptFilter,
    PromptListItem,
    PromptListResponse,
    PromptResponse,
    SinglePromptResponse,
)
from .services import PromptService, PromptWorkflowService


logger = logging.get_logger(__name__)

router = APIRouter(prefix="/prompts", tags=["prompt"])


@router.get(
    "",
    responses={
        status.HTTP_200_OK: {
            "model": PromptListResponse,
            "description": "Successfully listed prompts",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request data",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="List all prompts with filtering and sorting",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def list_prompts(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[PromptFilter, Depends()],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[PromptListResponse, ErrorResponse]:
    """List all prompts with pagination, filtering, and sorting."""
    # Calculate offset
    offset = (page - 1) * limit

    # Convert filter to dictionary
    filters_dict = filters.model_dump(exclude_none=True)

    try:
        # Get prompts from service
        prompts_list, count = await PromptService(session).get_all_prompts(
            offset, limit, filters_dict, order_by, search
        )

        return PromptListResponse(
            prompts=prompts_list,
            total_record=count,
            page=page,
            limit=limit,
            object="prompts.list",
            code=status.HTTP_200_OK,
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to list prompts: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to list prompts: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to list prompts"
        ).to_http_response()


@router.delete(
    "/{prompt_id}",
    responses={
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully deleted prompt",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request data",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Prompt not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Delete a prompt by its ID",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def delete_prompt(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    prompt_id: UUID,
) -> Union[SuccessResponse, ErrorResponse]:
    """Delete a prompt by its ID."""
    try:
        _ = await PromptService(session).delete_active_prompt(prompt_id)
        logger.debug(f"Prompt deleted: {prompt_id}")

        return SuccessResponse(
            message="Prompt deleted successfully", code=status.HTTP_200_OK, object="prompt.delete"
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to delete prompt: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to delete prompt: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to delete prompt"
        ).to_http_response()


@router.patch(
    "/{prompt_id}",
    responses={
        status.HTTP_200_OK: {
            "model": SinglePromptResponse,
            "description": "Successfully updated prompt",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request data",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Prompt not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Update a prompt by its ID",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def edit_prompt(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    prompt_id: UUID,
    edit_prompt: EditPromptRequest,
) -> Union[SinglePromptResponse, ErrorResponse]:
    """Edit prompt fields."""
    try:
        prompt_response = await PromptService(session).edit_prompt(
            prompt_id=prompt_id, data=edit_prompt.model_dump(exclude_unset=True, exclude_none=True)
        )

        return SinglePromptResponse(
            prompt=prompt_response,
            message="Prompt updated successfully",
            code=status.HTTP_200_OK,
            object="prompt.edit",
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to edit prompt: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to edit prompt: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to edit prompt"
        ).to_http_response()


@router.post(
    "/prompt-workflow",
    responses={
        status.HTTP_200_OK: {
            "model": RetrieveWorkflowDataResponse,
            "description": "Successfully created prompt workflow",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request data",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Create a prompt workflow",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def create_prompt_workflow(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    request: CreatePromptWorkflowRequest,
) -> Union[RetrieveWorkflowDataResponse, ErrorResponse]:
    """Create a prompt workflow."""
    try:
        db_workflow = await PromptWorkflowService(session).create_prompt_workflow(
            current_user_id=current_user.id,
            request=request,
        )

        return await WorkflowService(session).retrieve_workflow_data(db_workflow.id)
    except ClientException as e:
        logger.error(f"Failed to create prompt workflow: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to create prompt workflow: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to create prompt workflow"
        ).to_http_response()
