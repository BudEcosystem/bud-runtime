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

from datetime import datetime
from typing import Annotated, List, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
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
    AddToolRequest,
    AddToolResponse,
    ConnectorFilter,
    ConnectorListResponse,
    ConnectorResponse,
    CreatePromptVersionRequest,
    CreatePromptWorkflowRequest,
    DisconnectConnectorResponse,
    EditPromptRequest,
    EditPromptVersionRequest,
    GatewayResponse,
    GetPromptVersionResponse,
    OAuthCallbackRequest,
    OAuthCallbackResponse,
    OAuthFetchToolsRequest,
    OAuthInitiateRequest,
    OAuthInitiateResponse,
    OAuthStatusResponse,
    PaginatedTagsResponse,
    PromptCleanupRequest,
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
    RegisterConnectorRequest,
    RegisterConnectorResponse,
    SinglePromptResponse,
    SinglePromptVersionResponse,
    ToolFilter,
    ToolListResponse,
    ToolResponse,
    TraceDetailResponse,
    TraceListResponse,
)
from .services import PromptService, PromptVersionService, PromptWorkflowService


logger = logging.get_logger(__name__)

router = APIRouter(prefix="/prompts", tags=["prompt"])
security = HTTPBearer()


@router.get(
    "/tags/search",
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
            "model": PaginatedTagsResponse,
            "description": "Successfully listed tags",
        },
    },
    description="Search prompt tags by name",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def search_prompt_tags(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    search_term: str = Query(..., description="Tag name to search for"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
) -> Union[PaginatedTagsResponse, ErrorResponse]:
    """Search prompt tags by name."""
    # Calculate offset
    offset = (page - 1) * limit

    try:
        db_tags, count = await PromptService(session).search_prompt_tags(search_term, offset, limit)
    except ClientException as e:
        logger.exception(f"Failed to search prompt tags: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to search prompt tags: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to search prompt tags"
        ).to_http_response()

    return PaginatedTagsResponse(
        message="Tags listed successfully",
        tags=db_tags,
        object="prompt.tag.list",
        code=status.HTTP_200_OK,
        total_record=count,
        page=page,
        limit=limit,
    ).to_http_response()


@router.get(
    "/tags",
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
            "model": PaginatedTagsResponse,
            "description": "Successfully listed tags",
        },
    },
    description="List all prompt tags with pagination",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_prompt_tags(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
) -> Union[PaginatedTagsResponse, ErrorResponse]:
    """List all prompt tags with pagination."""
    # Calculate offset
    offset = (page - 1) * limit

    try:
        db_tags, count = await PromptService(session).get_prompt_tags(offset, limit)
    except ClientException as e:
        logger.exception(f"Failed to retrieve prompt tags: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to retrieve prompt tags: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to retrieve prompt tags"
        ).to_http_response()

    return PaginatedTagsResponse(
        message="Tags listed successfully",
        tags=db_tags,
        object="prompt.tag.list",
        code=status.HTTP_200_OK,
        total_record=count,
        page=page,
        limit=limit,
    ).to_http_response()


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
    token: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> Union[RetrieveWorkflowDataResponse, ErrorResponse]:
    """Create a prompt workflow."""
    try:
        db_workflow = await PromptWorkflowService(session).create_prompt_schema_workflow(
            current_user_id=current_user.id,
            request=request,
            access_token=token.credentials,
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
        response = await prompt_service.save_prompt_config(request, current_user.id)

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
    version: int = Query(1, description="Version of the configuration to retrieve", ge=1),
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
    "/connectors",
    responses={
        status.HTTP_200_OK: {
            "model": ConnectorListResponse,
            "description": "Successfully listed connectors",
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
    description="List all connectors with optional filtering by prompt_id",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def list_connectors(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[ConnectorFilter, Depends()],
    version: int = Query(default=1, ge=1, description="Version of prompt config (defaults to 1)"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[ConnectorListResponse, ErrorResponse]:
    """List all connectors with optional filtering.

    This endpoint returns a list of available connectors. When prompt_id is provided,
    you can also use is_registered to filter:
    - is_registered=true: Show only registered connectors
    - is_registered=false: Show only non-registered connectors
    - is_registered not set: Show all connectors

    Args:
        current_user: The authenticated user
        session: Database session
        filters: Filter parameters including prompt_id, is_registered, and name
        version: Optional version number. If not specified, uses default version
        page: Page number for pagination
        limit: Number of items per page

    Returns:
        ConnectorListResponse with the list of connectors or ErrorResponse on failure
    """
    # Calculate offset
    offset = (page - 1) * limit

    # Convert filter to dictionary
    filters_dict = filters.model_dump(exclude_none=True)

    # Extract prompt_id and is_registered from filters
    prompt_id = filters.prompt_id
    is_registered = filters.is_registered

    try:
        # Get connectors from service
        connectors_list, count = await PromptService(session).get_connectors(
            prompt_id=prompt_id,
            is_registered=is_registered,
            version=version,
            offset=offset,
            limit=limit,
            filters=filters_dict,
            order_by=order_by,
            search=search,
        )

        return ConnectorListResponse(
            connectors=connectors_list,
            total_record=count,
            page=page,
            limit=limit,
            object="connectors.list",
            code=status.HTTP_200_OK,
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to list connectors: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to list connectors: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to list connectors"
        ).to_http_response()


@router.get(
    "/connectors/{connector_id}",
    responses={
        status.HTTP_200_OK: {
            "model": ConnectorResponse,
            "description": "Successfully retrieved connector",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Connector not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Retrieve a single connector by ID",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_connector(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    connector_id: str,
) -> Union[ConnectorResponse, ErrorResponse]:
    """Retrieve a single connector with its full details from MCP Foundry.

    This endpoint returns complete connector information including the
    credential schema needed to render authentication forms dynamically.

    Args:
        current_user: The authenticated user
        session: Database session
        connector_id: String ID of the connector (e.g., "github", "slack")

    Returns:
        ConnectorResponse with full connector details or ErrorResponse on failure
    """
    try:
        # Get the connector from service
        connector = await PromptService(session).get_connector_by_id(connector_id)

        return ConnectorResponse(
            connector=connector,
            message="Connector retrieved successfully",
            code=status.HTTP_200_OK,
            object="connector.get",
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to retrieve connector: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to retrieve connector: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to retrieve connector"
        ).to_http_response()


@router.post(
    "/{budprompt_id}/connectors/{connector_id}/register",
    responses={
        status.HTTP_200_OK: {
            "model": RegisterConnectorResponse,
            "description": "Successfully registered connector",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Connector not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Register a connector for a prompt by creating gateway in MCP Foundry",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def register_connector(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    budprompt_id: str,
    connector_id: str,
    request: RegisterConnectorRequest,
) -> Union[RegisterConnectorResponse, ErrorResponse]:
    """Register a connector for a prompt.

    This endpoint creates a gateway in MCP Foundry to connect the specified
    connector to the prompt. The gateway name will be in the format:
    {budprompt_id}__v{version}__{connector_id}

    Each prompt version gets its own gateway in MCP Foundry, ensuring proper
    version isolation.

    Args:
        current_user: The authenticated user
        session: Database session
        budprompt_id: The bud prompt ID (can be UUID or draft prompt ID)
        connector_id: The connector ID to register
        request: RegisterConnectorRequest containing credentials and optional version

    Returns:
        RegisterConnectorResponse with gateway details or ErrorResponse on failure
    """
    try:
        # Register the connector
        gateway = await PromptService(session).register_connector_for_prompt(
            budprompt_id=budprompt_id,
            connector_id=connector_id,
            credentials=request.credentials,
            version=request.version,
            permanent=request.permanent,
        )

        return RegisterConnectorResponse(
            gateway=gateway,
            connector_id=connector_id,
            budprompt_id=budprompt_id,
            message="Connector registered successfully",
            code=status.HTTP_200_OK,
            object="connector.register",
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to register connector: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to register connector: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to register connector"
        ).to_http_response()


@router.delete(
    "/{budprompt_id}/connectors/{connector_id}/disconnect",
    responses={
        status.HTTP_200_OK: {
            "model": DisconnectConnectorResponse,
            "description": "Successfully disconnected connector",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Prompt or connector not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Disconnect a connector from a prompt by deleting gateway and cleaning configuration",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def disconnect_connector(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    budprompt_id: str,
    connector_id: str,
    version: Optional[int] = Query(default=1, ge=1, description="Version of prompt config (defaults to 1)"),
    permanent: bool = Query(
        False, description="Store configuration permanently without expiration (default: False, uses configured TTL)"
    ),
) -> Union[DisconnectConnectorResponse, ErrorResponse]:
    """Disconnect a connector from a prompt.

    This endpoint:
    1. Fetches tool originalNames before deletion
    2. Deletes the gateway in MCP Foundry (which auto-removes tools from virtual server)
    3. Removes connector from gateway_config and server_config
    4. Updates allowed_tools list
    5. If last connector: deletes virtual server and removes entire MCP config
    6. Saves updated configuration to Redis

    Args:
        current_user: The authenticated user
        session: Database session
        budprompt_id: The bud prompt ID (can be UUID or draft prompt ID)
        connector_id: The connector ID to disconnect
        version: Optional version number. If not specified, uses default version
        permanent: Store configuration permanently without expiration

    Returns:
        DisconnectConnectorResponse with deletion details or ErrorResponse on failure
    """
    try:
        result = await PromptService(session).disconnect_connector_from_prompt(
            budprompt_id=budprompt_id,
            connector_id=connector_id,
            version=version,
            permanent=permanent,
        )

        return DisconnectConnectorResponse(
            prompt_id=result["prompt_id"],
            connector_id=result["connector_id"],
            deleted_gateway_id=result["deleted_gateway_id"],
            success=True,
            message="Connector disconnected successfully",
            code=status.HTTP_200_OK,
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Failed to disconnect connector: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to disconnect connector: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to disconnect connector"
        ).to_http_response()


@router.post(
    "/prompt-config/add-tool",
    responses={
        status.HTTP_200_OK: {
            "model": AddToolResponse,
            "description": "Tool added successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Prompt not found",
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
    description="Add tools for a prompt by creating/updating virtual server in MCP Foundry",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def add_tool(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    request: AddToolRequest,
) -> Union[AddToolResponse, ErrorResponse]:
    """Add tools for a prompt by creating/updating virtual server.

    This endpoint:
    1. Validates that the prompt exists in Redis
    2. Checks if a virtual server already exists for the connector
    3. If exists: Updates the virtual server with new tools (replaces existing)
    4. If not exists: Creates a new virtual server in MCP Foundry with name format: {prompt_id}__v{version}
    5. Stores the updated configuration in Redis
    6. Returns virtual server details

    Each prompt version gets its own virtual server in MCP Foundry, ensuring proper
    version isolation.

    Args:
        current_user: The authenticated user
        session: Database session
        request: AddToolRequest with prompt_id, connector_id, tool_ids, and optional version

    Returns:
        AddToolResponse with virtual server details (virtual_server_name format: {prompt_id}__v{version})
        or ErrorResponse on failure
    """
    try:
        # Add tools via service
        result = await PromptService(session).add_tool_for_prompt(
            prompt_id=request.prompt_id,
            connector_id=request.connector_id,
            tool_ids=request.tool_ids,
            version=request.version,
            permanent=request.permanent,
        )

        return AddToolResponse(
            virtual_server_id=result["virtual_server_id"],
            virtual_server_name=result["virtual_server_name"],
            added_tools=result["added_tools"],
            success=True,
            message="Tools added successfully",
            code=status.HTTP_200_OK,
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Failed to add tool: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to add tool: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to add tool"
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
    description="List tools filtered by connector type",
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
    """List tools filtered by prompt_id and connector_id.

    Fetches prompt configuration from Redis, extracts gateway_id for the connector,
    and retrieves tools from MCP Foundry API filtered by server_id (gateway_id).

    Args:
        current_user: The authenticated user
        session: Database session
        filters: Tool filters including mandatory prompt_id and connector_id
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

    try:
        # Get tools from service
        tools_list, count = await PromptService(session).get_tools(
            prompt_id=filters.prompt_id,
            connector_id=filters.connector_id,
            version=filters.version,
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


@router.get("/tools/{tool_id}", response_model=ToolResponse)
async def get_tool(
    current_user: Annotated[User, Depends(get_current_active_user)],
    tool_id: UUID,
    session: Session = Depends(get_session),
) -> ToolResponse:
    """Get a single tool by ID.

    Args:
        tool_id: Tool ID to retrieve
        session: Database session
        current_user: Authenticated user

    Returns:
        Tool details with complete schema
    """
    try:
        prompt_service = PromptService(session)
        tool = await prompt_service.get_tool_by_id(tool_id)

        return ToolResponse(
            tool=tool,
            success=True,
            message="Tool retrieved successfully",
            code=status.HTTP_200_OK,
        )
    except ClientException as e:
        logger.error(f"Failed to get tool: {e}")
        raise ClientException(message=e.message, status_code=e.status_code)
    except Exception as e:
        logger.exception(f"Failed to get tool: {e}")
        raise ClientException(
            message="Failed to get tool",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.post(
    "/prompt-cleanup",
    responses={
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully cleaned up prompts",
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
    description="Trigger cleanup of temporary prompt resources (MCP gateways, virtual servers, etc.)",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def cleanup_prompts(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    request: PromptCleanupRequest,
) -> Union[SuccessResponse, ErrorResponse]:
    """Cleanup temporary prompt resources.

    This endpoint triggers cleanup of MCP resources (gateways, virtual servers)
    for temporary prompts.

    Execution modes:
    - debug=false: Runs cleanup asynchronously via Dapr workflow in budprompt
    - debug=true: Runs cleanup synchronously for immediate feedback

    Args:
        current_user: The authenticated user
        session: Database session
        request: Cleanup request with list of prompts and debug flag

    Returns:
        SuccessResponse with status code and message, or ErrorResponse on failure
    """
    try:
        logger.debug(
            f"Cleanup request received for {len(request.prompts)} prompts (debug={request.debug}, user={current_user.id})"
        )

        prompt_service = PromptService(session)

        # Call cleanup with debug flag
        prompt_ids = [prompt.model_dump() for prompt in request.prompts]
        await prompt_service._perform_cleanup_request(prompt_ids=prompt_ids, debug=request.debug)

        return SuccessResponse(
            message=f"Successfully triggered cleanup for {len(request.prompts)} prompts",
            code=status.HTTP_200_OK,
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Failed to cleanup prompts: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to cleanup prompts: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to cleanup prompts"
        ).to_http_response()


@router.post(
    "/oauth/initiate",
    responses={
        status.HTTP_200_OK: {
            "model": OAuthInitiateResponse,
            "description": "Successfully initiated OAuth flow",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Prompt or connector not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Initiate OAuth flow for a connector",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def initiate_oauth(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    request: OAuthInitiateRequest,
) -> Union[OAuthInitiateResponse, ErrorResponse]:
    """Initiate OAuth flow for a connector.

    This endpoint:
    1. Fetches prompt configuration from Redis
    2. Extracts gateway_id for the specified connector
    3. Calls MCP Foundry OAuth initiate endpoint
    4. Returns authorization URL for user redirection

    Args:
        current_user: The authenticated user
        session: Database session
        request: OAuth initiation request with prompt_id, connector_id, and version

    Returns:
        OAuthInitiateResponse with authorization_url and state, or ErrorResponse on failure
    """
    try:
        logger.debug(
            f"OAuth initiation requested for prompt {request.prompt_id}, "
            f"connector {request.connector_id}, version {request.version}"
        )

        prompt_service = PromptService(session)

        # Initiate OAuth flow
        oauth_data = await prompt_service.initiate_oauth_for_connector(
            prompt_id=request.prompt_id,
            connector_id=request.connector_id,
            version=request.version,
        )

        return OAuthInitiateResponse(
            authorization_url=oauth_data["authorization_url"],
            state=oauth_data["state"],
            expires_in=oauth_data["expires_in"],
            gateway_id=oauth_data["gateway_id"],
            message="OAuth flow initiated successfully",
            code=status.HTTP_200_OK,
            object="oauth.initiate",
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Failed to initiate OAuth: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to initiate OAuth: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to initiate OAuth flow"
        ).to_http_response()


@router.get(
    "/oauth/status",
    responses={
        status.HTTP_200_OK: {
            "model": OAuthStatusResponse,
            "description": "Successfully retrieved OAuth status",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Prompt or connector not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Get OAuth status for a connector",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def get_oauth_status(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    prompt_id: str = Query(..., description="Prompt id"),
    connector_id: str = Query(..., description="Connector id to check OAuth status for"),
    version: Optional[int] = Query(default=1, ge=1, description="Version of prompt config (defaults to 1)"),
) -> Union[OAuthStatusResponse, ErrorResponse]:
    """Get OAuth status for a connector.

    This endpoint:
    1. Fetches prompt configuration from Redis
    2. Extracts gateway_id for the specified connector
    3. Calls MCP Foundry OAuth status endpoint
    4. Returns OAuth configuration details

    Args:
        current_user: The authenticated user
        session: Database session
        prompt_id: Prompt ID (UUID or draft ID)
        connector_id: Connector ID to check status for
        version: Version of prompt config (defaults to 1)

    Returns:
        OAuthStatusResponse with OAuth configuration details, or ErrorResponse on failure
    """
    try:
        logger.debug(f"OAuth status requested for prompt {prompt_id}, connector {connector_id}, version {version}")

        prompt_service = PromptService(session)

        # Get OAuth status
        oauth_status = await prompt_service.get_oauth_status_for_connector(
            prompt_id=prompt_id,
            connector_id=connector_id,
            version=version,
        )

        return OAuthStatusResponse(
            oauth_enabled=oauth_status["oauth_enabled"],
            grant_type=oauth_status["grant_type"],
            client_id=oauth_status["client_id"],
            scopes=oauth_status.get("scopes", []),
            authorization_url=oauth_status["authorization_url"],
            redirect_uri=oauth_status["redirect_uri"],
            status_message=oauth_status.get("message", "OAuth status retrieved successfully"),
            message="OAuth status retrieved successfully",
            code=status.HTTP_200_OK,
            object="oauth.status",
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Failed to get OAuth status: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get OAuth status: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get OAuth status"
        ).to_http_response()


@router.post(
    "/oauth/fetch-tools",
    responses={
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Successfully fetched tools after OAuth",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Prompt or connector not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Fetch tools after OAuth completion for a connector",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def fetch_tools_after_oauth(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    request: OAuthFetchToolsRequest,
) -> Union[SuccessResponse, ErrorResponse]:
    """Fetch tools after OAuth completion for a connector."""
    try:
        logger.debug(
            f"Fetch tools requested for prompt {request.prompt_id}, "
            f"connector {request.connector_id}, version {request.version}"
        )

        prompt_service = PromptService(session)

        # Fetch tools after OAuth
        fetch_data = await prompt_service.fetch_tools_after_oauth_for_connector(
            prompt_id=request.prompt_id,
            connector_id=request.connector_id,
            version=request.version,
        )

        return SuccessResponse(
            message=fetch_data["message"],
            code=status.HTTP_200_OK,
            object="oauth.fetch_tools",
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Client error fetching tools: {e.message}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to fetch tools after OAuth: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to fetch tools after OAuth"
        ).to_http_response()


@router.post(
    "/oauth/callback",
    responses={
        status.HTTP_200_OK: {
            "model": OAuthCallbackResponse,
            "description": "Successfully handled OAuth callback",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Handle OAuth callback from provider",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def oauth_callback(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    request: OAuthCallbackRequest,
) -> Union[OAuthCallbackResponse, ErrorResponse]:
    """Handle OAuth callback from provider."""
    try:
        logger.debug("OAuth callback received")

        prompt_service = PromptService(session)

        # Handle OAuth callback
        callback_data = await prompt_service.handle_oauth_callback(
            code=request.code,
            state=request.state,
        )

        return OAuthCallbackResponse(
            gateway_id=callback_data["gateway_id"],
            user_id=callback_data["user_id"],
            expires_at=callback_data["expires_at"],
            message=callback_data["message"],
            code=status.HTTP_200_OK,
            object="oauth.callback",
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Client error handling OAuth callback: {e.message}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to handle OAuth callback: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to handle OAuth callback"
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


@router.get(
    "/{prompt_id}",
    responses={
        status.HTTP_200_OK: {
            "model": SinglePromptResponse,
            "description": "Successfully retrieved prompt",
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
    description="Retrieve a single prompt by its ID",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_prompt(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    prompt_id: UUID,
) -> Union[SinglePromptResponse, ErrorResponse]:
    """Retrieve a single prompt by its ID."""
    try:
        # Get the prompt from service
        prompt_response = await PromptService(session).get_prompt(prompt_id=prompt_id)

        return SinglePromptResponse(
            prompt=prompt_response,
            message="Prompt retrieved successfully",
            code=status.HTTP_200_OK,
            object="prompt.get",
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to retrieve prompt: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to retrieve prompt: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to retrieve prompt"
        ).to_http_response()


@router.get(
    "/{bud_prompt_id}/traces",
    responses={
        status.HTTP_200_OK: {
            "model": TraceListResponse,
            "description": "Successfully retrieved traces",
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
    description="List OTel traces for a specific prompt",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def list_prompt_traces(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    bud_prompt_id: str,
    project_id: UUID = Query(..., description="Project ID to validate prompt ownership"),
    from_date: datetime = Query(..., description="Start date for filtering traces"),
    to_date: datetime = Query(..., description="End date for filtering traces"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(50, ge=1, le=1000, description="Number of results per page"),
) -> Union[TraceListResponse, ErrorResponse]:
    """List OTel traces for a prompt."""
    try:
        result = await PromptService(session).list_traces(
            bud_prompt_id=bud_prompt_id,
            project_id=project_id,
            from_date=from_date,
            to_date=to_date,
            page=page,
            limit=limit,
        )
        return TraceListResponse(**result).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to list traces: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to list traces: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to list traces"
        ).to_http_response()


@router.get(
    "/{bud_prompt_id}/traces/{trace_id}",
    responses={
        status.HTTP_200_OK: {
            "model": TraceDetailResponse,
            "description": "Successfully retrieved trace",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Prompt or trace not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Get all spans for a single trace",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_prompt_trace(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    bud_prompt_id: str,
    trace_id: str,
    project_id: UUID = Query(..., description="Project ID to validate prompt ownership"),
) -> Union[TraceDetailResponse, ErrorResponse]:
    """Get all spans for a single trace."""
    try:
        result = await PromptService(session).get_trace(
            bud_prompt_id=bud_prompt_id,
            trace_id=trace_id,
            project_id=project_id,
        )
        return TraceDetailResponse(**result).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to get trace: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get trace: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get trace"
        ).to_http_response()
