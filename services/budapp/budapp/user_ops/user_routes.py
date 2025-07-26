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

"""The model ops package, containing essential business logic, services, and routing configurations for the user ops."""

from typing import Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing_extensions import Annotated, List, Optional

from budapp.auth.services import AuthService
from budapp.commons import logging
from budapp.commons.constants import PermissionEnum
from budapp.commons.dependencies import (
    get_current_active_invite_user,
    get_current_active_user,
    get_session,
    get_user_realm,
    parse_ordering_fields,
)
from budapp.commons.exceptions import ClientException
from budapp.commons.permission_handler import require_permissions
from budapp.commons.schemas import ErrorResponse, SuccessResponse
from budapp.user_ops.schemas import (
    MyPermissions,
    ResetPasswordRequest,
    ResetPasswordResponse,
    User,
    UserCreate,
    UserListFilter,
    UserListResponse,
    UserPermissions,
    UserResponse,
    UserUpdate,
)
from budapp.user_ops.services import UserService

from ..permissions.schemas import CheckUserResourceScope
from ..permissions.service import PermissionService


logger = logging.get_logger(__name__)

user_router = APIRouter(prefix="/users", tags=["user"])


@user_router.get(
    "/me",
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
            "model": UserResponse,
            "description": "Successfully get current user",
        },
    },
    description="Get current user",
)
# @require_permissions(permissions=[PermissionEnum.CLUSTER_VIEW])
async def get_current_user(
    current_user: Annotated[User, Depends(get_current_active_invite_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Union[UserResponse, ErrorResponse]:
    """Get current user."""
    try:
        logger.debug(f"Active user retrieved: {current_user.email}")
        return UserResponse(
            object="user.me", code=status.HTTP_200_OK, message="Successfully get current user", user=current_user
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get current user: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get current user"
        ).to_http_response()


@user_router.patch(
    "/onboard",
    responses={
        status.HTTP_200_OK: {
            "model": UserResponse,
            "description": "Set user onboarding status to completed",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
    },
    description="Api to set user onboarding status to completed",
)
async def complete_user_onboarding(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> Union[UserResponse, ErrorResponse]:
    """Complete user onboarding."""
    try:
        db_user = await UserService(session).complete_user_onboarding(current_user)
        logger.info(f"User onboarding completed: {current_user.id}")

        return UserResponse(
            object="user.retrieve",
            code=status.HTTP_200_OK,
            message="Successfully set user onboarding status to completed",
            user=db_user,
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to complete user onboarding: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to complete user onboarding: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to complete user onboarding"
        ).to_http_response()


@user_router.post(
    "/reset-password",
    responses={
        status.HTTP_200_OK: {
            "model": ResetPasswordResponse,
            "description": "Set user onboarding status to completed",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
    },
    description="Trigger a reset password email notification",
)
async def reset_password(
    request: ResetPasswordRequest,
    session: Session = Depends(get_session),
) -> Union[ResetPasswordResponse, ErrorResponse]:
    """Trigger a reset password email notification."""
    try:
        response = await UserService(session).reset_password_email(request)
        logger.debug("Email notification triggered for reset password. %s", response)

        return ResetPasswordResponse(
            object="user.reset-password",
            code=status.HTTP_200_OK,
            message="Email notification triggered for reset password",
            acknowledged=response["acknowledged"],
            status=response["status"],
            transaction_id=response["transaction_id"],
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to trigger reset password email: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to trigger reset password email: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to trigger reset password email"
        ).to_http_response()


@user_router.patch(
    "/{user_id}",
    responses={
        status.HTTP_200_OK: {
            "model": UserResponse,
            "description": "Successfully update current user",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Unauthorized",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
    },
    description="Update current user",
)
async def update_current_user(
    user_id: UUID,
    user: UserUpdate,
    current_user: Annotated[User, Depends(get_current_active_invite_user)],
    realm_name: Annotated[str, Depends(get_user_realm)],
    session: Annotated[Session, Depends(get_session)],
) -> Union[UserResponse, ErrorResponse]:
    """Update current user."""
    try:
        # Check if user is updating another user's profile
        if str(user_id) != str(current_user.id):
            try:
                # Check if current user has USER_MANAGE permission
                has_permission = await PermissionService(session).check_resource_permission_by_user(
                    current_user,
                    CheckUserResourceScope(
                        resource_type="user",
                        scope="manage",
                        entity_id=None,  # Global permission check
                    ),
                )

                if not has_permission:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions for this operation"
                    )
            except HTTPException as e:
                raise e
            except Exception as e:
                logger.exception(f"Failed to check user permission: {e}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions for this operation"
                )

        db_user = await UserService(session).update_active_user(
            user_id, user.model_dump(exclude_unset=True, exclude_none=True), current_user, realm_name
        )
        return UserResponse(
            object="user.me", code=status.HTTP_200_OK, message="Successfully update current user", user=db_user
        ).to_http_response()
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(f"Failed to update current user: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to update current user"
        ).to_http_response()


@user_router.get(
    "/me/permissions",
    responses={
        status.HTTP_200_OK: {
            "model": MyPermissions,
            "description": "Successfully get user permissions",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Authentication failed or token expired",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
    },
    description="Get user roles and permissions",
)
async def get_user_roles(
    current_user: Annotated[User, Depends(get_current_active_invite_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Union[MyPermissions, ErrorResponse]:
    """Get user roles and permissions."""
    try:
        kc_user = await UserService(session).get_user_roles_and_permissions(current_user)
        permissions_list = kc_user.get("permissions", [])
        return MyPermissions(
            object="user.permissions",
            code=status.HTTP_200_OK,
            message="Successfully get user permissions",
            permissions=permissions_list,
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Client error getting user permissions: {e.message}")
        return ErrorResponse(code=e.status_code or status.HTTP_401_UNAUTHORIZED, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Unexpected error getting user permissions: {e}")
        return ErrorResponse(
            code=status.HTTP_401_UNAUTHORIZED, message="Authentication failed or token expired"
        ).to_http_response()


@user_router.get(
    "/",
    responses={
        status.HTTP_200_OK: {
            "model": UserListResponse,
            "description": "Successfully get user list",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
    },
    description="Get all active users from the database",
)
@require_permissions(permissions=[PermissionEnum.USER_MANAGE])
async def get_all_users(
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    filters: UserListFilter = Depends(),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = False,
    session: Session = Depends(get_session),
) -> Union[MyPermissions, ErrorResponse]:
    """Get all active users from the database."""
    # Calculate offset
    offset = (page - 1) * limit

    # Convert UserFilter to dictionary
    filters_dict = filters.model_dump(exclude_none=True)

    try:
        db_users, count = await UserService(session).get_all_users(offset, limit, filters_dict, order_by, search)
    except ClientException as e:
        logger.error(f"Failed to get user list: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get user list: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get all users"
        ).to_http_response()

    return UserListResponse(
        users=db_users,
        total_record=count,
        page=page,
        limit=limit,
        object="users.list",
        code=status.HTTP_200_OK,
    ).to_http_response()


@user_router.post(
    "/",
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
            "model": UserResponse,
            "description": "Successfully created user",
        },
    },
    description="Create a new user with email and password",
)
@require_permissions(permissions=[PermissionEnum.USER_MANAGE])
async def create_user(
    user: UserCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Union[UserResponse, ErrorResponse]:
    """Create a new user with email and password."""
    try:
        db_user = await AuthService(session).register_user(user)
        return UserResponse(
            object="user.create", code=status.HTTP_200_OK, message="User created successfully", user=db_user
        ).to_http_response()
    except ClientException as e:
        logger.error(f"ClientException: {e}")
        return ErrorResponse(code=status.HTTP_400_BAD_REQUEST, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Exception: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Something went wrong"
        ).to_http_response()


@user_router.get(
    "/{user_id}",
    responses={
        status.HTTP_200_OK: {
            "model": UserResponse,
            "description": "Successfully get user by id",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
    },
    description="Get a single active user from the database",
)
@require_permissions(permissions=[PermissionEnum.USER_MANAGE])
async def retrieve_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> Union[UserResponse, ErrorResponse]:
    """Get a single active user from the database."""
    try:
        db_user = await UserService(session).retrieve_active_user(user_id)
        return UserResponse(
            object="user.retrieve", code=status.HTTP_200_OK, message="Successfully get user by id", user=db_user
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to get user by id: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get user by id: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get user by id"
        ).to_http_response()


@user_router.get(
    "/{user_id}/permissions",
    responses={
        status.HTTP_200_OK: {
            "model": UserPermissions,
            "description": "Successfully get user permissions",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
    },
    description="Get user roles",
)
@require_permissions(permissions=[PermissionEnum.USER_MANAGE])
async def get_user_permissions_by_id(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_invite_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Union[UserPermissions, ErrorResponse]:
    """Get user roles."""
    try:
        kc_user = await UserService(session).get_user_permissions_by_id(user_id)
        permissions_list = kc_user.get("result", [])
        return UserPermissions(
            object="user.permissions",
            code=status.HTTP_200_OK,
            message="Successfully get user permissions",
            result=permissions_list,
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get user permissions: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get user roles"
        ).to_http_response()


@user_router.delete(
    "/{user_id}",
    responses={
        status.HTTP_200_OK: {
            "model": SuccessResponse,
            "description": "Delete an active user from the database",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
    },
    description="Delete an active user from the database",
)
@require_permissions(permissions=[PermissionEnum.USER_MANAGE])
async def delete_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    remove_credential: bool = True,
    session: Session = Depends(get_session),
) -> Union[SuccessResponse, ErrorResponse]:
    """Delete an active user from the database."""
    try:
        _ = await UserService(session).delete_active_user(user_id, remove_credential)
        logger.debug(f"User deleted: {user_id}")
        return SuccessResponse(message="User deleted successfully", code=status.HTTP_200_OK).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to delete user: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to delete user: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to delete user"
        ).to_http_response()


@user_router.patch(
    "/{user_id}/reactivate",
    responses={
        status.HTTP_200_OK: {
            "model": UserResponse,
            "description": "Reactivate an inactive user from the database",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to client error",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Service is unavailable due to server error",
        },
    },
    description="Reactivate an inactive user from the database",
)
@require_permissions(permissions=[PermissionEnum.USER_MANAGE])
async def reactivate_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> Union[SuccessResponse, ErrorResponse]:
    """Reactivate an inactive user from the database."""
    try:
        db_user = await UserService(session).reactivate_user(user_id)
        logger.debug(f"User reactivated: {user_id}")
        return UserResponse(
            object="user.retrieve", code=status.HTTP_200_OK, message="Successfully reactivate user", user=db_user
        ).to_http_response()
    except ClientException as e:
        logger.error(f"Failed to reactivate user: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to reactivate user: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to reactivate user"
        ).to_http_response()
