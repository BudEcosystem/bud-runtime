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

"""The project ops package, containing essential business logic, services, and routing configurations for the project ops."""

from typing import List, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.commons import logging
from budapp.commons.dependencies import (
    get_current_active_user,
    get_session,
    parse_ordering_fields,
)
from budapp.commons.exceptions import ClientException
from budapp.commons.schemas import ErrorResponse, SuccessResponse
from budapp.user_ops.schemas import User

from ..commons.constants import PermissionEnum, ProjectTypeEnum, UserTypeEnum
from ..commons.permission_handler import require_permissions
from ..user_ops.schemas import UserFilter
from .access_control import validate_client_project_access
from .crud import ProjectDataManager
from .models import Project as ProjectModel
from .schemas import (
    EditProjectRequest,
    PagenatedProjectUserResponse,
    PaginatedProjectsResponse,
    PaginatedTagsResponse,
    ProjectClusterFilter,
    ProjectClusterPaginatedResponse,
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectFilter,
    ProjectSuccessResopnse,
    ProjectUserAddList,
    ProjectUserUpdate,
    # ProjectRequest,
    # ProjectResponse,
    SingleProjectResponse,
)
from .services import ProjectService


logger = logging.get_logger(__name__)

project_router = APIRouter(prefix="/projects", tags=["project"])


# @project_router.post(
#     "/",
#     response_model=SingleResponse[ProjectResponse],
#     responses={
#         401: {"model": ErrorResponse},
#         422: {"model": ErrorResponse},
#         400: {"model": ErrorResponse},
#     },
# )
# async def create_project(
#     project: ProjectRequest,
#     current_user: Annotated[User, Depends(get_current_active_user)],
#     session: Annotated[Session, Depends(get_session)],
# ):
#     db_project = await ProjectService(session).create_project(project, current_user.id)
#     logger.info("Project created")

#     return SingleResponse(message="Project created successfully", result=db_project)


@project_router.get(
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
    description="Search tags by name",
)
@require_permissions(permissions=[PermissionEnum.PROJECT_VIEW])
async def search_project_tags(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    search_term: str = Query(..., description="Tag name to search for"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
) -> Union[PaginatedTagsResponse, ErrorResponse]:
    """Search project tags by name."""
    # Calculate offset
    offset = (page - 1) * limit

    try:
        db_tags, count = await ProjectService(session).search_project_tags(search_term, offset, limit)
    except ClientException as e:
        logger.exception(f"Failed to search project tags: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to search project tags: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to search project tags"
        ).to_http_response()

    return PaginatedTagsResponse(
        message="Tags listed successfully",
        tags=db_tags,
        object="project.tag.list",
        code=status.HTTP_200_OK,
        total_record=count,
        page=page,
        limit=limit,
    ).to_http_response()


@project_router.get(
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
    description="List all project tags",
)
@require_permissions(permissions=[PermissionEnum.PROJECT_VIEW])
async def get_project_tags(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Union[PaginatedTagsResponse, ErrorResponse]:
    """List all project tags."""
    page = 1

    try:
        db_tags, count = await ProjectService(session).get_project_tags()
        limit = count
    except ClientException as e:
        logger.exception(f"Failed to retrieve project tags: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to retrieve project tags: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to retrieve project tags"
        ).to_http_response()

    return PaginatedTagsResponse(
        message="Tags listed successfully",
        tags=db_tags,
        object="project.tag.list",
        code=status.HTTP_200_OK,
        total_record=count,
        page=page,
        limit=limit,
    ).to_http_response()


@project_router.post(
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
            "model": ProjectSuccessResopnse,
            "description": "Successfully created project",
        },
    },
    description="Create a new project",
)
@require_permissions(permissions=[PermissionEnum.PROJECT_MANAGE])
async def create_project(
    request: Request,
    project_data: ProjectCreateRequest,
    current_user: Annotated[
        User,
        Depends(get_current_active_user),
        # Security(
        #     perform_authorization,
        #     scopes=[PermissionEnum.PROJECT_MANAGE.value],
        # ),
    ],
    session: Annotated[Session, Depends(get_session)],
) -> Union[ProjectSuccessResopnse, ErrorResponse]:
    """Create a new project."""
    try:
        # Handle project_type based on user type
        project_dict = project_data.model_dump(exclude_unset=True, exclude_none=True)

        # CLIENT users can only create CLIENT_APP projects
        if current_user.user_type == UserTypeEnum.CLIENT:
            project_dict["project_type"] = ProjectTypeEnum.CLIENT_APP.value
        # ADMIN users can create both types, default to ADMIN_APP if not specified
        elif current_user.user_type == UserTypeEnum.ADMIN:
            if "project_type" not in project_dict:
                project_dict["project_type"] = ProjectTypeEnum.ADMIN_APP.value
            # Validate the provided project_type for ADMIN users
            elif project_dict["project_type"] not in [
                ProjectTypeEnum.CLIENT_APP.value,
                ProjectTypeEnum.ADMIN_APP.value,
            ]:
                raise ClientException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message=f"Invalid project type: {project_dict['project_type']}",
                )

        db_project = await ProjectService(session).create_project(project_dict, current_user.id, request)
    except ClientException as e:
        logger.exception(f"Failed to create project: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to create project: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to create project"
        ).to_http_response()

    return ProjectSuccessResopnse(
        message="Project created successfully",
        project=db_project,
        object="project.create",
        code=status.HTTP_200_OK,
    ).to_http_response()


@project_router.get(
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
            "model": PaginatedProjectsResponse,
            "description": "Successfully listed active projects",
        },
    },
    description="Get all active projects from the database",
)
@require_permissions(permissions=[PermissionEnum.PROJECT_VIEW])
async def get_all_projects(
    current_user: Annotated[
        User,
        Depends(get_current_active_user),
        # Security(
        #     perform_authorization,
        #     scopes=[
        #         PermissionEnum.PROJECT_VIEW.value,
        #         PermissionEnum.PROJECT_MANAGE.value,
        #     ],
        # ),
    ],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[ProjectFilter, Depends()],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[PaginatedProjectsResponse, ErrorResponse]:
    """Get all active projects."""
    offset = (page - 1) * limit
    filters_dict = filters.model_dump(exclude_none=True)

    # All access control logic is now handled in the service layer
    try:
        db_projects, count = await ProjectService(session).get_all_active_projects(
            current_user, offset, limit, filters_dict, order_by, search
        )
    except ClientException as e:
        logger.exception(f"Failed to retrieve projects: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to retrieve projects: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to retrieve projects"
        ).to_http_response()

    return PaginatedProjectsResponse(
        message="Projects listed successfully",
        projects=db_projects,
        object="project.list",
        code=status.HTTP_200_OK,
        total_record=count,
        page=page,
        limit=limit,
    ).to_http_response()


@project_router.patch(
    "/{project_id}",
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
            "model": SingleProjectResponse,
            "description": "Successfully edited project",
        },
    },
    description="Edit project",
)
@require_permissions(permissions=[PermissionEnum.PROJECT_MANAGE])
async def edit_project(
    request: Request,
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    edit_project: EditProjectRequest,
) -> Union[SingleProjectResponse, ErrorResponse]:
    """Edit project."""
    try:
        db_project = await ProjectService(session).edit_project(
            project_id=project_id,
            data=edit_project.model_dump(exclude_unset=True, exclude_none=True),
            current_user_id=current_user.id,
            request=request,
        )
        return SingleProjectResponse(
            project=db_project,
            message="Project details updated successfully",
            code=status.HTTP_200_OK,
            object="project.edit",
        )
    except ClientException as e:
        logger.exception(f"Failed to edit project: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to edit project: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to edit project"
        ).to_http_response()


@project_router.get(
    "/{project_id}/clusters",
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
            "model": ProjectClusterPaginatedResponse,
            "description": "Successfully list all clusters in a project",
        },
    },
    description="List all clusters in a project.\n\nOrder by values are: name, endpoint_count, hardware_type, node_count, worker_count, status, created_at, modified_at",
)
@require_permissions(permissions=[PermissionEnum.PROJECT_VIEW])
async def list_all_clusters(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[ProjectClusterFilter, Depends()],
    project_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[ProjectClusterPaginatedResponse, ErrorResponse]:
    """List all clusters in a project."""
    # Validate CLIENT user access to this project
    await validate_client_project_access(current_user, project_id, session, "list clusters in")

    # Calculate offset
    offset = (page - 1) * limit

    # Construct filters
    filters_dict = filters.model_dump(exclude_none=True, exclude_unset=True)

    try:
        result, count = await ProjectService(session).get_all_clusters_in_project(
            project_id, offset, limit, filters_dict, order_by, search
        )
    except ClientException as e:
        logger.exception(f"Failed to get all clusters: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get all clusters: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to get all clusters"
        ).to_http_response()

    return ProjectClusterPaginatedResponse(
        clusters=result,
        total_record=count,
        page=page,
        limit=limit,
        object="project.clusters.list",
        code=status.HTTP_200_OK,
        message="Successfully list all clusters in a project",
    ).to_http_response()


@project_router.get(
    "/{project_id}",
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
            "model": ProjectDetailResponse,
            "description": "Successfully retrieved project",
        },
    },
    description="Get a single active project from the database",
)
@require_permissions(permissions=[PermissionEnum.PROJECT_VIEW])
async def retrieve_project(
    project_id: UUID,
    current_user: Annotated[
        User,
        Depends(get_current_active_user),
        # Security(
        #     perform_authorization,
        #     scopes=[
        #         PermissionEnum.PROJECT_VIEW.value,
        #         PermissionEnum.PROJECT_MANAGE.value,
        #     ],
        # ),
    ],
    session: Annotated[Session, Depends(get_session)],
) -> Union[ProjectDetailResponse, ErrorResponse]:
    """Retrieve a single active project."""
    try:
        db_project, endpoints_count = await ProjectService(session).retrieve_active_project_details(project_id)

        # Check if client user is trying to access non-CLIENT_APP project
        if (
            current_user.user_type == UserTypeEnum.CLIENT
            and db_project.project_type != ProjectTypeEnum.CLIENT_APP.value
        ):
            raise ClientException(
                status_code=status.HTTP_403_FORBIDDEN,
                message="Access denied: Client users can only access client application projects",
            )

        # Validate CLIENT user access (includes project type and association checks)
        await validate_client_project_access(current_user, project_id, session, "retrieve")

        logger.info(f"Project retrieved: {project_id}")
    except ClientException as e:
        logger.exception(f"Failed to retrieve project: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to retrieve project: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to retrieve project"
        ).to_http_response()

    return ProjectDetailResponse(
        message="Project retrieved successfully",
        project=db_project,
        endpoints_count=endpoints_count,
        object="project.retrieve",
        code=status.HTTP_200_OK,
    ).to_http_response()


@project_router.delete(
    "/{project_id}",
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
            "description": "Successfully deleted project",
        },
    },
    description="Delete an active project from the database",
)
@require_permissions(permissions=[PermissionEnum.PROJECT_MANAGE])
async def delete_project(
    request: Request,
    project_id: UUID,
    current_user: Annotated[
        User,
        Depends(get_current_active_user),
        # Security(
        #     perform_authorization,
        #     scopes=[PermissionEnum.PROJECT_MANAGE.value],
        # ),
    ],
    session: Annotated[Session, Depends(get_session)],
    remove_credential: bool = True,
) -> Union[SuccessResponse, ErrorResponse]:
    """Delete an active project."""
    try:
        _ = await ProjectService(session).delete_active_project(
            project_id, remove_credential, current_user_id=current_user.id, request=request
        )
        logger.info(f"Project deleted: {project_id}")
    except ClientException as e:
        logger.exception(f"Failed to delete project: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to delete project: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to delete project"
        ).to_http_response()

    return SuccessResponse(
        message="Project deleted successfully",
        object="project.delete",
        code=status.HTTP_200_OK,
    ).to_http_response()


@project_router.post(
    "/{project_id}/add-users",
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
            "description": "Users successfully added to project",
        },
    },
    description="For existing users, user_id must be provided. For new users, email must be provided.",
)
@require_permissions(permissions=[PermissionEnum.PROJECT_MANAGE])
async def add_users_to_project(
    project_id: UUID,
    users_to_add: ProjectUserAddList,
    current_user: Annotated[
        User,
        Depends(get_current_active_user),
        # Security(
        #     perform_authorization,
        #     scopes=[PermissionEnum.PROJECT_MANAGE.value],
        # ),
    ],
    session: Annotated[Session, Depends(get_session)],
) -> Union[SuccessResponse, ErrorResponse]:
    """Add users to an active project."""
    try:
        _ = await ProjectService(session).add_users_to_project(project_id, users_to_add.users)
        logger.info(f"Users added to project: {project_id}")
    except ClientException as e:
        logger.exception(f"Failed to add users to project: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to add users to project: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to add users to project"
        ).to_http_response()

    return SuccessResponse(
        message="Invite sent successfully",
        object="project.add_users",
        code=status.HTTP_200_OK,
    ).to_http_response()


@project_router.post(
    "/{project_id}/remove-users",
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
            "description": "Users successfully removed from project",
        },
    },
    description="Remove users from an active project",
)
@require_permissions(permissions=[PermissionEnum.PROJECT_MANAGE])
async def remove_users_from_project(
    project_id: UUID,
    users: ProjectUserUpdate,
    current_user: Annotated[
        User,
        Depends(get_current_active_user),
        # Security(
        #     perform_authorization,
        #     scopes=[PermissionEnum.PROJECT_MANAGE.value],
        # ),
    ],
    session: Annotated[Session, Depends(get_session)],
    remove_credential: bool = True,
) -> Union[SuccessResponse, ErrorResponse]:
    """Remove users from an active project."""
    try:
        _ = await ProjectService(session).remove_users_from_project(project_id, users.user_ids, remove_credential)
        logger.info(f"Users removed from project: {project_id}")
    except ClientException as e:
        logger.exception(f"Failed to remove users from project: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to remove users from project: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to remove users from project"
        ).to_http_response()

    return SuccessResponse(
        message="Users removed from project successfully",
        object="project.remove_users",
        code=status.HTTP_200_OK,
    ).to_http_response()


@project_router.get(
    "/{project_id}/users",
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
            "model": PagenatedProjectUserResponse,
            "description": "Successfully listed project users",
        },
    },
    description="Get all active users in a project. Additional Sorting: project_role",
)
@require_permissions(permissions=[PermissionEnum.PROJECT_VIEW])
async def list_project_users(
    project_id: UUID,
    current_user: Annotated[
        User,
        Depends(get_current_active_user),
        # Security(
        #     perform_authorization,
        #     scopes=[
        #         PermissionEnum.PROJECT_VIEW.value,
        #         PermissionEnum.PROJECT_MANAGE.value,
        #     ],
        # ),
    ],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[UserFilter, Depends()],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=0),
    order_by: Optional[List[str]] = Depends(parse_ordering_fields),
    search: bool = False,
) -> Union[PagenatedProjectUserResponse, ErrorResponse]:
    """Get all active users in a project."""
    # Validate CLIENT user access to this project
    await validate_client_project_access(current_user, project_id, session, "list users in")

    offset = (page - 1) * limit
    filters_dict = filters.model_dump(exclude_none=True)

    try:
        db_users, count = await ProjectService(session).get_all_project_users(
            project_id, offset, limit, filters_dict, order_by, search
        )
    except ClientException as e:
        logger.exception(f"Failed to retrieve project users: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to retrieve project users: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to retrieve project users"
        ).to_http_response()

    return PagenatedProjectUserResponse(
        message="Users listed successfully",
        users=db_users,
        object="project.list_users",
        code=status.HTTP_200_OK,
        total_record=count,
        page=page,
        limit=limit,
    ).to_http_response()
