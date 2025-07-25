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

"""The permissions module, containing essential business logic, services, and routing configurations for the permissions."""

from typing import Annotated, List, Optional, Union

from budmicroframe.commons.schemas import ErrorResponse, SuccessResponse
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from ..commons import logging
from ..commons.constants import PermissionEnum
from ..commons.dependencies import get_current_active_user, get_session, parse_ordering_fields
from ..commons.exceptions import ClientException
from ..commons.permission_handler import require_permissions
from ..project_ops.schemas import ProjectFilter
from ..user_ops.schemas import User
from .schemas import (
    GlobalPermissionUpdateResponse,
    PaginatedUserProjectPermissionsResponse,
    PermissionList,
    ProjectPermissionUpdate,
)
from .service import PermissionService


logger = logging.get_logger(__name__)

permission_router = APIRouter(prefix="/permissions", tags=["permission"])


@permission_router.patch(
    "/project",
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
            "model": SuccessResponse,
            "description": "Successfully updated project permissions",
        },
    },
    description="Update project permissions for a specific user",
)
@require_permissions(permissions=[PermissionEnum.USER_MANAGE])
async def update_project_permissions(
    permissions: List[ProjectPermissionUpdate],
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Union[SuccessResponse, ErrorResponse]:
    """Update project permissions for a specific user.

    Args:
        permissions: List of permissions to update
        db: Database session
        current_user: The authenticated user making the request

    Returns:
        SuccessResponse: Success response with project permissions updated
    """
    try:
        _ = await PermissionService(session).update_project_permissions(permissions)
        return SuccessResponse(
            code=status.HTTP_200_OK,
            message="Project permissions updated successfully",
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Unable to update project permissions: {e.message}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Unable to update project permissions: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to update permissions"
        ).to_http_response()


@permission_router.put(
    "/{user_id}/global",
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
            "model": GlobalPermissionUpdateResponse,
            "description": "Updated list of permissions",
        },
    },
    description="Update global permissions for a specific user",
)
@require_permissions(permissions=[PermissionEnum.USER_MANAGE])
async def update_global_permissions(
    user_id: str,
    permissions: List[PermissionList],
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Union[GlobalPermissionUpdateResponse, ErrorResponse]:
    """Update global permissions for a specific user.

    Args:
        user_id: The ID of the user to update permissions for
        permissions: List of permissions to update
        db: Database session
        current_user: The authenticated user making the request

    Returns:
        List[PermissionList]: Updated list of permissions
    """
    try:
        updated_permissions = await PermissionService(session).update_global_permissions(user_id, permissions)
        return GlobalPermissionUpdateResponse(
            code=status.HTTP_200_OK,
            message="Global permissions updated successfully",
            object="permissions.global",
            permissions=updated_permissions,
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Unable to update global permissions: {e.message}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Unable to update global permissions: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to update permissions"
        ).to_http_response()


@permission_router.get(
    "/{user_id}/projects",
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
            "model": PaginatedUserProjectPermissionsResponse,
            "description": "Successfully listed user project permissions",
        },
    },
    description="Get all project permissions for a specific user",
)
@require_permissions(permissions=[PermissionEnum.USER_MANAGE])
async def get_user_project_permissions(
    user_id: str,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    filters: Annotated[ProjectFilter, Depends()],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[PaginatedUserProjectPermissionsResponse, ErrorResponse]:
    """Get all project permissions for a specific user.

    Args:
        user_id: The ID of the user to get permissions for
        session: Database session
        current_user: The authenticated user making the request
        filters: Project filters
        page: Page number
        limit: Number of items per page
        order_by: Order by fields
        search: Whether to use search

    Returns:
        PaginatedUserProjectPermissionsResponse: List of projects with permissions
    """
    offset = (page - 1) * limit
    filters_dict = filters.model_dump(exclude_none=True)

    try:
        projects, count = await PermissionService(session).get_user_project_permissions(
            user_id, offset, limit, filters_dict, order_by, search
        )

        return PaginatedUserProjectPermissionsResponse(
            message="User project permissions listed successfully",
            projects=projects,
            object="permission.user.projects",
            code=status.HTTP_200_OK,
            total_record=count,
            page=page,
            limit=limit,
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Unable to get user project permissions: {e.message}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Unable to get user project permissions: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get user project permissions"
        ).to_http_response()
