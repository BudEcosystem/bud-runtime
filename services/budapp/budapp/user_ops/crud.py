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

"""The crud package, containing essential business logic, services, and routing configurations for the user ops."""

from typing import Dict, List, Tuple
from uuid import UUID

from fastapi import status
from sqlalchemy import and_, func, or_, select, update

from budapp.commons import logging
from budapp.commons.constants import UserStatusEnum
from budapp.commons.db_utils import DataManagerUtils
from budapp.commons.exceptions import ClientException

from .models import User


logger = logging.get_logger(__name__)


class UserDataManager(DataManagerUtils):
    """Data manager for the User model."""

    async def get_active_invited_users_by_ids(self, user_ids: List[UUID]) -> List[User]:
        """Get users by ids from database."""
        stmt = select(User).filter(
            User.id.in_(user_ids),
            or_(
                User.status == UserStatusEnum.ACTIVE,
                User.status == UserStatusEnum.INVITED,
            ),
        )
        return self.scalars_all(stmt)

    async def get_users_by_emails(self, emails: List[str]) -> List[User]:
        """Get users by emails from database."""
        stmt = select(User).filter(User.email.in_(emails))
        return self.scalars_all(stmt)

    async def update_subscriber_status(self, user_ids: List[int], is_subscriber: bool) -> None:
        """Update the is_subscriber status for a list of user IDs."""
        if not user_ids:
            raise ValueError("The list of user IDs must not be empty.")

        stmt = update(User).where(User.id.in_(user_ids)).values(is_subscriber=is_subscriber)

        self.session.execute(stmt)
        self.session.commit()

        logger.info(f"Updated is_subscriber status for {len(user_ids)} users.")
        return

    async def get_all_users(
        self,
        offset: int,
        limit: int,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[User], int]:
        """List all users in the database."""
        await self.validate_fields(User, filters)

        # Generate statements according to search or filters
        if search:
            search_conditions = await self.generate_search_stmt(User, filters)
            stmt = select(User).filter(or_(*search_conditions))
            count_stmt = select(func.count()).select_from(User).filter(and_(*search_conditions))
        else:
            stmt = select(User).filter_by(**filters)
            count_stmt = select(func.count()).select_from(User).filter_by(**filters)

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(User, order_by)
            stmt = stmt.order_by(*sort_conditions)

        result = self.scalars_all(stmt)

        return result, count

    async def retrieve_active_or_invited_user(self, user_id: UUID, missing_ok: bool = False) -> User:
        """Retrieve active or invited user by id."""
        stmt = select(User).filter(
            User.id == user_id, or_(User.status == UserStatusEnum.ACTIVE, User.status == UserStatusEnum.INVITED)
        )
        db_user = self.scalar_one_or_none(stmt)

        if not missing_ok and db_user is None:
            logger.error("User not found in database")
            raise ClientException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        return db_user if db_user else None
