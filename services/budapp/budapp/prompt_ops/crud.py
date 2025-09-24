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

"""CRUD operations for the prompt ops module."""

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, asc, case, desc, func, or_, select, update
from sqlalchemy.orm import joinedload

from budapp.commons.constants import EndpointStatusEnum, PromptStatusEnum, PromptVersionStatusEnum
from budapp.commons.db_utils import DataManagerUtils
from budapp.endpoint_ops.models import Endpoint as EndpointModel
from budapp.model_ops.models import Model as ModelModel

from .models import Prompt as PromptModel
from .models import PromptVersion as PromptVersionModel


class PromptDataManager(DataManagerUtils):
    """CRUD operations for Prompt model."""

    async def get_all_active_prompts(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: Dict[str, Any] = {},
        order_by: List[Tuple[str, str]] = [],
        search: bool = False,
    ) -> Tuple[List[PromptModel], int]:
        """Get all active prompts from the database with related data."""
        await self.validate_fields(PromptModel, filters)

        # Prepare explicit conditions for order by related fields
        explicit_conditions = []
        for field in order_by:
            if field[0] == "model_name":
                sorting_stmt = await self.generate_sorting_stmt(
                    ModelModel,
                    [("name", field[1])],
                )
                explicit_conditions.append(sorting_stmt[0])
            elif field[0] == "default_version":
                sorting_stmt = await self.generate_sorting_stmt(
                    PromptVersionModel,
                    [("version", field[1])],
                )
                explicit_conditions.append(sorting_stmt[0])
            elif field[0] == "modality":
                sorting_stmt = await self.generate_sorting_stmt(
                    ModelModel,
                    [("modality", field[1])],
                )
                explicit_conditions.append(sorting_stmt[0])
            elif field[0] == "status":
                sorting_stmt = await self.generate_sorting_stmt(
                    EndpointModel,
                    [("status", field[1])],
                )
                explicit_conditions.append(sorting_stmt[0])

        # Generate base query with joins through default_version
        base_query = (
            select(PromptModel)
            .outerjoin(
                PromptVersionModel,
                and_(
                    PromptModel.default_version_id == PromptVersionModel.id,
                    PromptVersionModel.status != PromptVersionStatusEnum.DELETED,
                ),
            )
            .outerjoin(EndpointModel, PromptVersionModel.endpoint_id == EndpointModel.id)
            .outerjoin(ModelModel, PromptVersionModel.model_id == ModelModel.id)
            .options(
                joinedload(PromptModel.default_version)
                .joinedload(PromptVersionModel.endpoint)
                .joinedload(EndpointModel.model),
                joinedload(PromptModel.default_version)
                .joinedload(PromptVersionModel.model)
                .joinedload(ModelModel.provider),
            )
        )

        # Generate statements according to search or filters
        if search:
            search_conditions = await self.generate_search_stmt(PromptModel, filters)
            stmt = base_query.filter(or_(*search_conditions)).filter(PromptModel.status != PromptStatusEnum.DELETED)
            count_stmt = (
                select(func.count(PromptModel.id))
                .select_from(PromptModel)
                .outerjoin(
                    PromptVersionModel,
                    and_(
                        PromptModel.default_version_id == PromptVersionModel.id,
                        PromptVersionModel.status != PromptVersionStatusEnum.DELETED,
                    ),
                )
                .outerjoin(EndpointModel, PromptVersionModel.endpoint_id == EndpointModel.id)
                .outerjoin(ModelModel, PromptVersionModel.model_id == ModelModel.id)
                .filter(or_(*search_conditions))
                .filter(PromptModel.status != PromptStatusEnum.DELETED)
            )
        else:
            stmt = base_query
            count_stmt = (
                select(func.count(PromptModel.id))
                .select_from(PromptModel)
                .outerjoin(
                    PromptVersionModel,
                    and_(
                        PromptModel.default_version_id == PromptVersionModel.id,
                        PromptVersionModel.status != PromptVersionStatusEnum.DELETED,
                    ),
                )
                .outerjoin(EndpointModel, PromptVersionModel.endpoint_id == EndpointModel.id)
                .outerjoin(ModelModel, PromptVersionModel.model_id == ModelModel.id)
            )
            for key, value in filters.items():
                stmt = stmt.filter(getattr(PromptModel, key) == value)
                count_stmt = count_stmt.filter(getattr(PromptModel, key) == value)
            stmt = stmt.filter(PromptModel.status != PromptStatusEnum.DELETED)
            count_stmt = count_stmt.filter(PromptModel.status != PromptStatusEnum.DELETED)

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            # Generate sort conditions for Prompt model fields
            implicit_sort_conditions = []
            for field, direction in order_by:
                if field not in ["model_name", "default_version", "modality", "status"]:
                    implicit_sort_conditions.append((field, direction))

            if implicit_sort_conditions:
                sort_conditions = await self.generate_sorting_stmt(PromptModel, implicit_sort_conditions)
                # Extend sort conditions with explicit conditions
                sort_conditions.extend(explicit_conditions)
                stmt = stmt.order_by(*sort_conditions)
            elif explicit_conditions:
                stmt = stmt.order_by(*explicit_conditions)
        else:
            # Default sorting by created_at desc
            stmt = stmt.order_by(desc(PromptModel.created_at))

        result = self.scalars_all(stmt)

        return result, count


class PromptVersionDataManager(DataManagerUtils):
    """CRUD operations for PromptVersion model."""

    async def get_next_version(self, prompt_id: UUID) -> int:
        """Get the next version number for a prompt."""
        result = self.session.execute(
            select(func.max(PromptVersionModel.version)).where(PromptVersionModel.prompt_id == prompt_id)
        )
        max_version = result.scalar()
        return (max_version or 0) + 1

    async def soft_delete_by_prompt_id(self, prompt_id: UUID) -> int:
        """Soft delete all prompt versions for a given prompt."""
        stmt = (
            update(PromptVersionModel)
            .where(
                and_(
                    PromptVersionModel.prompt_id == prompt_id,
                    PromptVersionModel.status != PromptVersionStatusEnum.DELETED,
                )
            )
            .values(status=PromptVersionStatusEnum.DELETED)
        )
        result = self.session.execute(stmt)
        self.session.commit()
        return result.rowcount

    async def get_all_prompt_versions(
        self,
        prompt_id: UUID,
        offset: int = 0,
        limit: int = 10,
        filters: dict = {},
        order_by: list = [],
        search: bool = False,
    ) -> tuple[list, int]:
        """Get all prompt versions for a specific prompt with pagination and filtering."""
        await self.validate_fields(PromptVersionModel, filters)

        # Generate base query with eager loading and computed is_default_version
        base_query = (
            select(
                PromptVersionModel,
                case((PromptVersionModel.id == PromptModel.default_version_id, True), else_=False).label(
                    "is_default_version"
                ),
            )
            .join(PromptModel, PromptVersionModel.prompt_id == PromptModel.id)
            .filter(PromptVersionModel.prompt_id == prompt_id)
            .filter(PromptVersionModel.status != PromptVersionStatusEnum.DELETED)
            .options(
                joinedload(PromptVersionModel.endpoint),
                joinedload(PromptVersionModel.prompt),
            )
        )

        # Generate statements according to search or filters
        if search:
            search_conditions = await self.generate_search_stmt(PromptVersionModel, filters)
            stmt = base_query.filter(or_(*search_conditions)) if search_conditions else base_query

            count_stmt = (
                select(func.count(PromptVersionModel.id))
                .select_from(PromptVersionModel)
                .filter(PromptVersionModel.prompt_id == prompt_id)
                .filter(PromptVersionModel.status != PromptVersionStatusEnum.DELETED)
            )
            if search_conditions:
                count_stmt = count_stmt.filter(or_(*search_conditions))
        else:
            stmt = base_query
            count_stmt = (
                select(func.count(PromptVersionModel.id))
                .select_from(PromptVersionModel)
                .filter(PromptVersionModel.prompt_id == prompt_id)
                .filter(PromptVersionModel.status != PromptVersionStatusEnum.DELETED)
            )

            # Apply filters
            for key, value in filters.items():
                stmt = stmt.filter(getattr(PromptVersionModel, key) == value)
                count_stmt = count_stmt.filter(getattr(PromptVersionModel, key) == value)

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(PromptVersionModel, order_by)
            stmt = stmt.order_by(*sort_conditions)
        else:
            # Default sorting by version desc
            stmt = stmt.order_by(desc(PromptVersionModel.version))

        # Execute query and get all results including computed fields
        result = self.session.execute(stmt)
        rows = result.all()

        return rows, count
