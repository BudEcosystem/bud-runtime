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

"""The core package, containing essential business logic, services, and routing configurations for the permissions."""

from typing import Dict, List, Optional
from uuid import UUID

from fastapi import status
from fastapi.exceptions import HTTPException
from sqlalchemy import delete, select

from budapp.commons import logging
from budapp.commons.db_utils import DataManagerUtils

from .models import Permission, ProjectPermission


logger = logging.get_logger(__name__)


class PermissionDataManager(DataManagerUtils):
    """Data manager for the Permission model."""

    async def retrieve_permission_by_fields(self, fields: Dict, missing_ok: bool = False) -> Optional[Permission]:
        """Retrieve permission by fields."""
        await self.validate_fields(Permission, fields)

        stmt = select(Permission).filter_by(**fields)
        db_permission = self.scalar_one_or_none(stmt)

        if not missing_ok and db_permission is None:
            logger.info("Permission not found in database")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")

        return db_permission if db_permission else None


class ProjectPermissionDataManager(DataManagerUtils):
    """Project Permission data manager class responsible for operations over database."""

    async def retrieve_project_permission_by_fields(
        self, fields: Dict, missing_ok: bool = False
    ) -> Optional[ProjectPermission]:
        """Retrieve project permission by fields."""
        await self.validate_fields(ProjectPermission, fields)

        stmt = select(ProjectPermission).filter_by(**fields)
        db_project_permission = self.scalar_one_or_none(stmt)

        if not missing_ok and db_project_permission is None:
            logger.info("Permission not found in database")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")

        return db_project_permission if db_project_permission else None

    async def delete_project_permissions_by_user_ids(
        self, user_ids: List[UUID], project_id: UUID
    ) -> List[ProjectPermission]:
        """Delete all project permissions by user ids."""
        stmt = delete(ProjectPermission).where(
            ProjectPermission.user_id.in_(user_ids),
            ProjectPermission.project_id == project_id,
        )
        return await self.execute_commit(stmt)
