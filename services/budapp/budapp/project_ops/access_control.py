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

"""Project access control utilities."""

from uuid import UUID

from fastapi import status
from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.exceptions import ClientException
from budapp.user_ops.schemas import User

from ..commons.constants import ProjectStatusEnum, ProjectTypeEnum, UserTypeEnum
from .crud import ProjectDataManager
from .models import Project as ProjectModel


logger = logging.get_logger(__name__)


async def validate_client_project_access(
    current_user: User, project_id: UUID, session: Session, action: str = "access"
) -> None:
    """Validate that a CLIENT user has proper access to a project.

    This function enforces row-level security by ensuring:
    1. The project exists and is active
    2. CLIENT users can only access CLIENT_APP type projects
    3. CLIENT users can only access projects they are associated with

    Args:
        current_user: The current user making the request
        project_id: The UUID of the project to validate access for
        session: Database session
        action: Description of the action being performed (for error messages)

    Raises:
        ClientException: If access should be denied
    """
    if current_user.user_type != UserTypeEnum.CLIENT:
        # Non-CLIENT users are handled by the regular permission system
        return

    try:
        # First check if project exists and is active
        db_project = await ProjectDataManager(session).retrieve_by_fields(
            ProjectModel, {"id": project_id, "status": ProjectStatusEnum.ACTIVE}
        )

        # CLIENT users can only access CLIENT_APP type projects
        if db_project.project_type != ProjectTypeEnum.CLIENT_APP.value:
            logger.warning(
                f"CLIENT user {current_user.id} attempted to {action} "
                f"non-CLIENT_APP project {project_id} (type: {db_project.project_type})"
            )
            raise ClientException(
                status_code=status.HTTP_403_FORBIDDEN,
                message="Access denied: Client users can only access client application projects",
            )

        # Check if user is associated with this project (row-level security)
        is_user_in_project = await ProjectDataManager(session).is_user_in_project(current_user.id, project_id)
        if not is_user_in_project:
            logger.warning(
                f"CLIENT user {current_user.id} attempted to {action} project {project_id} without proper association"
            )
            raise ClientException(
                status_code=status.HTTP_403_FORBIDDEN,
                message="Access denied: You are not authorized to access this project",
            )

        logger.debug(f"CLIENT user {current_user.id} validated for {action} on project {project_id}")

    except ClientException:
        raise
    except Exception as e:
        logger.exception(f"Failed to validate project access for user {current_user.id}: {e}")
        raise ClientException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to validate project access"
        )
