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
    CreatePromptVersionRequest,
    CreatePromptWorkflowRequest,
    EditPromptRequest,
    EditPromptVersionRequest,
    GetPromptVersionResponse,
    IntegrationFilter,
    IntegrationListResponse,
    IntegrationResponse,
    PromptConfigGetResponse,
    PromptConfigRequest,
    PromptConfigResponse,
    PromptFilter,
    PromptListItem,
    PromptListResponse,
    PromptResponse,
    PromptSchemaRequest,
    PromptVersionFilter,
    PromptVersionListItem,
    PromptVersionListResponse,
    PromptVersionResponse,
    SinglePromptResponse,
    SinglePromptVersionResponse,
    ToolFilter,
    ToolListResponse,
)
from .services import PromptService, PromptVersionService, PromptWorkflowService


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


@router.get(
    "/{prompt_id}/versions",
    responses={
        status.HTTP_200_OK: {
            "model": PromptVersionListResponse,
            "description": "Successfully listed prompt versions",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Prompt not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal Server error",
        },
    },
    description="List all versions for a specific prompt.",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def list_prompt_versions(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    prompt_id: UUID,
    filters: Annotated[PromptVersionFilter, Depends()],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[PromptVersionListResponse, ErrorResponse]:
    """List all versions for a specific prompt with pagination, filtering, and sorting."""
    # Calculate offset
    offset = (page - 1) * limit

    # Convert filter to dictionary
    filters_dict = filters.model_dump(exclude_none=True)

    try:
        # Get prompt versions from service
        versions_list, count = await PromptService(session).get_all_prompt_versions(
            prompt_id, offset, limit, filters_dict, order_by, search
        )

        return PromptVersionListResponse(
            versions=versions_list,
            total_record=count,
            page=page,
            limit=limit,
            object="prompt.versions.list",
            code=status.HTTP_200_OK,
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to list prompt versions: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to list prompt versions: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to list prompt versions"
        ).to_http_response()


@router.get(
    "/{prompt_id}/versions/{version_id}",
    responses={
        status.HTTP_200_OK: {
            "model": GetPromptVersionResponse,
            "description": "Successfully retrieved prompt version",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Prompt or version not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal Server error",
        },
    },
    description="Retrieve a specific prompt version with its prompt schema",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_prompt_version(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    prompt_id: UUID,
    version_id: UUID,
) -> Union[GetPromptVersionResponse, ErrorResponse]:
    """Retrieve a specific prompt version with its prompt schema."""
    try:
        # Get the prompt version and config data
        version_detail, config_data = await PromptVersionService(session).get_prompt_version(
            prompt_id=prompt_id,
            version_id=version_id,
        )

        return GetPromptVersionResponse(
            version=version_detail,
            config_data=config_data,
            message="Prompt version retrieved successfully",
            code=status.HTTP_200_OK,
            object="prompt.version.get",
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to retrieve prompt version: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to retrieve prompt version: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to retrieve prompt version"
        ).to_http_response()


@router.post(
    "/{prompt_id}/versions",
    responses={
        status.HTTP_200_OK: {
            "model": SinglePromptVersionResponse,
            "description": "Successfully created prompt version",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request data",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Prompt or endpoint not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal Server error",
        },
    },
    description="Create a new version for a specific prompt",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def create_prompt_version(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    prompt_id: UUID,
    request: CreatePromptVersionRequest,
) -> Union[SinglePromptVersionResponse, ErrorResponse]:
    """Create a new version for a specific prompt."""
    try:
        # Create the prompt version
        version_response = await PromptVersionService(session).create_prompt_version(
            prompt_id=prompt_id,
            endpoint_id=request.endpoint_id,
            bud_prompt_id=request.bud_prompt_id,
            set_as_default=request.set_as_default,
            current_user_id=current_user.id,
        )

        return SinglePromptVersionResponse(
            version=version_response,
            message="Prompt version created successfully",
            code=status.HTTP_200_OK,
            object="prompt.version.create",
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to create prompt version: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to create prompt version: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to create prompt version"
        ).to_http_response()


@router.patch(
    "/{prompt_id}/versions/{version_id}",
    responses={
        status.HTTP_200_OK: {
            "model": SinglePromptVersionResponse,
            "description": "Successfully updated prompt version",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request data",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Prompt or version not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Update a prompt version by its ID",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def edit_prompt_version(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    prompt_id: UUID,
    version_id: UUID,
    edit_version: EditPromptVersionRequest,
) -> Union[SinglePromptVersionResponse, ErrorResponse]:
    """Edit prompt version fields."""
    try:
        # Prepare update data - exclude_unset and exclude_none for proper PATCH behavior
        update_data = edit_version.model_dump(exclude_unset=True, exclude_none=True)

        version_response = await PromptVersionService(session).edit_prompt_version(
            prompt_id=prompt_id, version_id=version_id, data=update_data
        )

        return SinglePromptVersionResponse(
            version=version_response,
            message="Prompt version updated successfully",
            code=status.HTTP_200_OK,
            object="prompt.version.edit",
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to edit prompt version: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to edit prompt version: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to edit prompt version"
        ).to_http_response()


@router.delete(
    "/{prompt_id}/versions/{version_id}",
    responses={
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully deleted prompt version",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Cannot delete default version",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Prompt or version not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Delete a prompt version by its ID",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def delete_prompt_version(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    prompt_id: UUID,
    version_id: UUID,
) -> Union[SuccessResponse, ErrorResponse]:
    """Delete a prompt version by its ID. Cannot delete the default version."""
    try:
        await PromptVersionService(session).delete_prompt_version(prompt_id, version_id)
        logger.debug(f"Prompt version deleted: {version_id} for prompt {prompt_id}")

        return SuccessResponse(
            message="Prompt version deleted successfully", code=status.HTTP_200_OK, object="prompt.version.delete"
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to delete prompt version: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to delete prompt version: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to delete prompt version"
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


@router.post(
    "/prompt-schema",
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
async def create_prompt_schema_workflow(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    request: PromptSchemaRequest,
) -> Union[RetrieveWorkflowDataResponse, ErrorResponse]:
    """Create a prompt workflow."""
    try:
        db_workflow = await PromptWorkflowService(session).create_prompt_schema_workflow(
            current_user_id=current_user.id,
            request=request,
        )

        return await WorkflowService(session).retrieve_workflow_data(db_workflow.id)
    except ClientException as e:
        logger.error(f"Failed to create prompt schema workflow: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to create prompt schema workflow: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to create prompt schema workflow"
        ).to_http_response()


@router.post(
    "/prompt-config",
    responses={
        status.HTTP_200_OK: {
            "model": PromptConfigResponse,
            "description": "Successfully saved prompt configuration",
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
    description="Save or update prompt configuration in Redis via budprompt service",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def save_prompt_config(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    request: PromptConfigRequest,
) -> Union[PromptConfigResponse, ErrorResponse]:
    """Save or update prompt configuration.

    This endpoint forwards the configuration request to the budprompt service
    which stores the configuration in Redis. The configuration can be used
    for structured prompt execution with validation and retry capabilities.

    Args:
        current_user: The authenticated user
        session: Database session
        request: The prompt configuration request containing messages, model settings, etc.

    Returns:
        PromptConfigResponse with the prompt_id or ErrorResponse on failure
    """
    try:
        # Create service instance and save prompt config
        prompt_service = PromptService(session)
        response = await prompt_service.save_prompt_config(request)

        return response.to_http_response()

    except ClientException as e:
        logger.error(f"Failed to save prompt configuration: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to save prompt configuration: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to save prompt configuration"
        ).to_http_response()


@router.get(
    "/prompt-config/{prompt_id}",
    responses={
        status.HTTP_200_OK: {
            "model": PromptConfigGetResponse,
            "description": "Successfully retrieved prompt configuration",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Configuration not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Retrieve prompt configuration from Redis via budprompt service",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_prompt_config(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    prompt_id: str,
    version: Optional[int] = Query(None, description="Version of the configuration to retrieve", ge=1),
) -> Union[PromptConfigGetResponse, ErrorResponse]:
    """Get prompt configuration by ID.

    This endpoint retrieves the configuration from the budprompt service
    which fetches it from Redis. Optionally specify a version number.

    Args:
        current_user: The authenticated user
        session: Database session
        prompt_id: The unique identifier of the prompt configuration
        version: Optional version number to retrieve specific version

    Returns:
        PromptConfigGetResponse with the configuration data or ErrorResponse on failure
    """
    try:
        # Create service instance and get prompt config
        prompt_service = PromptService(session)
        response = await prompt_service.get_prompt_config(prompt_id, version)

        return response.to_http_response()

    except ClientException as e:
        logger.error(f"Failed to retrieve prompt configuration: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to retrieve prompt configuration: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to retrieve prompt configuration"
        ).to_http_response()


@router.get(
    "/integrations",
    responses={
        status.HTTP_200_OK: {
            "model": IntegrationListResponse,
            "description": "Successfully listed integrations",
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
    description="List all integrations with optional filtering by prompt_id",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def list_integrations(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[IntegrationFilter, Depends()],
    prompt_id: Optional[UUID] = Query(None, description="Filter integrations connected to a specific prompt"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[IntegrationListResponse, ErrorResponse]:
    """List all integrations with optional filtering by prompt_id.

    This endpoint returns a list of available integrations. When prompt_id is provided,
    it filters to show only integrations connected to that specific prompt.
    Currently returns hardcoded data until mcp_foundry service is available.

    Args:
        current_user: The authenticated user
        session: Database session
        prompt_id: Optional UUID to filter integrations for a specific prompt
        page: Page number for pagination
        limit: Number of items per page

    Returns:
        IntegrationListResponse with the list of integrations or ErrorResponse on failure
    """
    # Calculate offset
    offset = (page - 1) * limit

    # Convert filter to dictionary
    filters_dict = filters.model_dump(exclude_none=True)

    try:
        # Get integrations from service
        integrations_list, count = await PromptService(session).get_integrations(
            prompt_id=prompt_id, offset=offset, limit=limit, filters=filters_dict, order_by=order_by, search=search
        )

        return IntegrationListResponse(
            integrations=integrations_list,
            total_record=count,
            page=page,
            limit=limit,
            object="integrations.list",
            code=status.HTTP_200_OK,
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to list integrations: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to list integrations: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to list integrations"
        ).to_http_response()


@router.get(
    "/integrations/{integration_id}",
    responses={
        status.HTTP_200_OK: {
            "model": IntegrationResponse,
            "description": "Successfully retrieved integration",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Integration not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Retrieve a single integration by ID",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_integration(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    integration_id: UUID,
) -> Union[IntegrationResponse, ErrorResponse]:
    """Retrieve a single integration with its full details.

    This endpoint returns complete integration information including the
    credential schema needed to render authentication forms dynamically.
    Currently returns hardcoded data until mcp_foundry service is available.

    Args:
        current_user: The authenticated user
        session: Database session
        integration_id: UUID of the integration to retrieve

    Returns:
        IntegrationResponse with full integration details or ErrorResponse on failure
    """
    try:
        # Get the integration from service
        integration = await PromptService(session).get_integration_by_id(integration_id)

        return IntegrationResponse(
            integration=integration,
            message="Integration retrieved successfully",
            code=status.HTTP_200_OK,
            object="integration.get",
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to retrieve integration: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to retrieve integration: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to retrieve integration"
        ).to_http_response()


@router.get(
    "/tools",
    responses={
        status.HTTP_200_OK: {
            "model": ToolListResponse,
            "description": "Successfully listed tools",
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
    description="List tools filtered by integration type",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def list_tools(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[ToolFilter, Depends()],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[ToolListResponse, ErrorResponse]:
    """List all tools filtered by integration type.

    This endpoint returns a list of available tools for a specific integration type.
    The integration_type parameter is MANDATORY.
    Currently returns hardcoded data until mcp_foundry service is available.

    Args:
        current_user: The authenticated user
        session: Database session
        filters: Tool filters including mandatory integration_type
        page: Page number for pagination
        limit: Number of items per page
        order_by: Ordering fields
        search: Enable search functionality

    Returns:
        ToolListResponse with the list of tools or ErrorResponse on failure
    """
    # Calculate offset
    offset = (page - 1) * limit

    # Convert filter to dictionary
    filters_dict = filters.model_dump(exclude_none=True)

    # Validate that integration_type is provided (it's mandatory in the schema)
    if not filters.integration_type:
        return ErrorResponse(
            code=status.HTTP_400_BAD_REQUEST, message="integration_type is required"
        ).to_http_response()

    try:
        # Get tools from service
        tools_list, count = await PromptService(session).get_tools(
            integration_type=filters.integration_type,
            offset=offset,
            limit=limit,
            filters=filters_dict,
            order_by=order_by,
            search=search,
        )

        return ToolListResponse(
            tools=tools_list,
            total_record=count,
            page=page,
            limit=limit,
            object="tools.list",
            code=status.HTTP_200_OK,
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to list tools: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to list tools: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to list tools"
        ).to_http_response()
