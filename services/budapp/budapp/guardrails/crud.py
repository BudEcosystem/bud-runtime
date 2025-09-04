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

"""CRUD operations for guardrail models."""

from typing import Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import status
from sqlalchemy import and_, delete, func, or_, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.sql import select

from budapp.commons import logging
from budapp.commons.constants import GuardrailDeploymentStatusEnum, GuardrailStatusEnum
from budapp.commons.db_utils import DataManagerUtils
from budapp.commons.exceptions import ClientException, DatabaseException
from budapp.guardrails.models import (
    GuardrailDeployments,
    GuardrailProbe,
    GuardrailProfileDisabledRules,
    GuardrailProfileEnabledProbes,
    GuardrailProfiles,
    GuardrailRule,
)


logger = logging.get_logger(__name__)


class GuardrailsProbeRulesDataManager(DataManagerUtils):
    """Data manager for guardrail probes and rules."""

    async def list_probe_tags(
        self,
        search_value: str = "",
        offset: int = 0,
        limit: int = 10,
    ) -> Tuple[List[GuardrailProbe], int]:
        """Search tags by name with pagination, or fetch all tags if no search value is provided."""
        # Ensure only valid JSON arrays are processed
        tags_subquery = (
            select(func.jsonb_array_elements(GuardrailProbe.tags).label("tag"))
            .where(GuardrailProbe.status == GuardrailStatusEnum.ACTIVE)
            .where(GuardrailProbe.tags.is_not(None))  # Exclude null tags
            .where(func.jsonb_typeof(GuardrailProbe.tags) == "array")  # Ensure tags is a JSON array
        ).subquery()

        # Extract name and color as jsonb
        distinct_tags_query = (
            select(
                func.jsonb_extract_path_text(tags_subquery.c.tag, "name").label("name"),
                func.jsonb_extract_path_text(tags_subquery.c.tag, "color").label("color"),
            )
            .where(func.jsonb_typeof(tags_subquery.c.tag) == "object")  # Ensure valid JSONB objects
            .where(func.jsonb_extract_path_text(tags_subquery.c.tag, "name").is_not(None))  # Valid names
            .where(func.jsonb_extract_path_text(tags_subquery.c.tag, "color").is_not(None))  # Valid colors
        ).subquery()

        # Apply DISTINCT to get unique tags by name, selecting the first color
        distinct_on_name_query = (
            select(
                distinct_tags_query.c.name,
                distinct_tags_query.c.color,
            )
            .distinct(distinct_tags_query.c.name)
            .order_by(distinct_tags_query.c.name, distinct_tags_query.c.color)  # Ensure deterministic order
        )

        # Apply search filter if provided
        if search_value:
            distinct_on_name_query = distinct_on_name_query.where(distinct_tags_query.c.name.ilike(f"{search_value}%"))

        # Add pagination
        distinct_tags_with_pagination = distinct_on_name_query.offset(offset).limit(limit)

        # Execute the paginated query
        tags_result = self.session.execute(distinct_tags_with_pagination)

        # Count total distinct tag names
        distinct_count_query = (
            select(func.count(func.distinct(distinct_tags_query.c.name)))
            .where(func.jsonb_typeof(tags_subquery.c.tag) == "object")  # Ensure valid JSONB objects
            .where(func.jsonb_extract_path_text(tags_subquery.c.tag, "name").is_not(None))  # Valid names
            .where(func.jsonb_extract_path_text(tags_subquery.c.tag, "color").is_not(None))  # Valid colors
        )

        # Apply search filter to the count query
        if search_value:
            distinct_count_query = distinct_count_query.where(
                func.jsonb_extract_path_text(tags_subquery.c.tag, "name").ilike(f"{search_value}%")
            )

        # Execute the count query
        distinct_count_result = self.session.execute(distinct_count_query)
        total_count = distinct_count_result.scalar()

        return tags_result, total_count

    async def get_all_probes(
        self,
        offset: int,
        limit: int,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[GuardrailProbe], int]:
        """List all probes in the database."""
        # Tags are not filterable
        # Also remove from filters dict
        explicit_conditions = []
        json_filters = {"tags": filters.pop("tags", [])}

        # Validate the remaining filters
        await self.validate_fields(GuardrailProbe, filters)

        if json_filters["tags"]:
            # Either TagA or TagB exist in tag field
            tag_conditions = or_(
                *[GuardrailProbe.tags.cast(JSONB).contains([{"name": tag_name}]) for tag_name in json_filters["tags"]]
            )
            explicit_conditions.append(tag_conditions)

        # Generate statements according to search or filters
        if search:
            search_conditions = await self.generate_search_stmt(GuardrailProbe, filters)
            stmt = (
                select(
                    GuardrailProbe,
                    func.count(GuardrailRule.id)
                    .filter(GuardrailRule.status == GuardrailStatusEnum.ACTIVE)
                    .label("rules_count"),
                )
                .select_from(GuardrailProbe)
                .filter(or_(*search_conditions, *explicit_conditions))
                .filter(GuardrailProbe.status == GuardrailStatusEnum.ACTIVE)
                .outerjoin(GuardrailRule, GuardrailRule.probe_id == GuardrailProbe.id)
                .group_by(GuardrailProbe.id)
            )
            count_stmt = (
                select(func.count())
                .select_from(GuardrailProbe)
                .filter(or_(*search_conditions, *explicit_conditions))
                .filter(GuardrailProbe.status == GuardrailStatusEnum.ACTIVE)
            )
        else:
            stmt = (
                select(
                    GuardrailProbe,
                    func.count(GuardrailRule.id)
                    .filter(GuardrailRule.status == GuardrailStatusEnum.ACTIVE)
                    .label("rules_count"),
                )
                .select_from(GuardrailProbe)
                .filter_by(**filters)
                .where(and_(*explicit_conditions))
                .filter(GuardrailProbe.status == GuardrailStatusEnum.ACTIVE)
                .outerjoin(GuardrailRule, GuardrailRule.probe_id == GuardrailProbe.id)
                .group_by(GuardrailProbe.id)
            )
            count_stmt = (
                select(func.count())
                .select_from(GuardrailProbe)
                .filter_by(**filters)
                .where(and_(*explicit_conditions))
                .filter(GuardrailProbe.status == GuardrailStatusEnum.ACTIVE)
            )

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(GuardrailProbe, order_by)
            stmt = stmt.order_by(*sort_conditions)

        result = self.execute_all(stmt)

        return result, count

    async def get_all_probe_rules(
        self,
        probe_id: UUID,
        offset: int,
        limit: int,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[GuardrailRule], int]:
        """List all rules for a specific probe."""
        # Add probe_id to filters
        filters["probe_id"] = probe_id

        # Validate the remaining filters
        await self.validate_fields(GuardrailRule, filters)

        # Generate statements according to search or filters
        if search:
            search_conditions = await self.generate_search_stmt(GuardrailRule, filters)
            stmt = (
                select(GuardrailRule)
                .filter(or_(*search_conditions))
                .filter(GuardrailRule.status == GuardrailStatusEnum.ACTIVE)
            )
            count_stmt = (
                select(func.count())
                .select_from(GuardrailRule)
                .filter(or_(*search_conditions))
                .filter(GuardrailRule.status == GuardrailStatusEnum.ACTIVE)
            )
        else:
            stmt = (
                select(GuardrailRule).filter_by(**filters).filter(GuardrailRule.status == GuardrailStatusEnum.ACTIVE)
            )
            count_stmt = (
                select(func.count())
                .select_from(GuardrailRule)
                .filter_by(**filters)
                .filter(GuardrailRule.status == GuardrailStatusEnum.ACTIVE)
            )

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(GuardrailRule, order_by)
            stmt = stmt.order_by(*sort_conditions)

        result = self.execute_all(stmt)

        return result, count

    async def soft_delete_deprecated_probes(self, ids: List[str]) -> None:
        """Soft delete deprecated probes and their associated rules.

        Args:
            ids (List[str]): List of probe ids to soft delete.

        Returns:
            None
        """
        try:
            # First, soft delete all rules associated with these probes
            rules_stmt = (
                update(GuardrailRule).where(GuardrailRule.probe_id.in_(ids)).values(status=GuardrailStatusEnum.DELETED)
            )
            self.session.execute(rules_stmt)

            # Then, soft delete the probes themselves
            probes_stmt = (
                update(GuardrailProbe).where(GuardrailProbe.id.in_(ids)).values(status=GuardrailStatusEnum.DELETED)
            )
            self.session.execute(probes_stmt)

            self.session.commit()
            logger.info(f"Successfully soft deleted {len(ids)} probes and their associated rules")
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.exception(f"Failed to soft delete deprecated probes: {e}")
            raise DatabaseException("Unable to soft delete deprecated probes") from e

    async def soft_delete_deprecated_rules(self, ids: List[str]) -> None:
        """Soft delete deprecated rules.

        Args:
            ids (List[str]): List of rule ids to soft delete.

        Returns:
            None
        """
        try:
            stmt = update(GuardrailRule).where(GuardrailRule.id.in_(ids)).values(status=GuardrailStatusEnum.DELETED)
            self.session.execute(stmt)
            self.session.commit()
            logger.info(f"Successfully soft deleted {len(ids)} rules")
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.exception(f"Failed to soft delete deprecated rules: {e}")
            raise DatabaseException("Unable to soft delete deprecated rules") from e


class GuardrailsDeploymentDataManager(DataManagerUtils):
    """Data manager for guardrail deployments including probes and rules overrides."""

    async def soft_delete_profile(self, profile_id: UUID) -> None:
        """Soft delete a guardrail profile.

        Args:
            profile_id (UUID): The profile id to soft delete.

        Returns:
            None
        """
        # Check for active deployments using this profile
        active_deployment_stmt = (
            select(func.count(GuardrailDeployments.id))
            .where(GuardrailDeployments.profile_id == profile_id)
            .where(GuardrailDeployments.status != GuardrailDeploymentStatusEnum.DELETED)
        )
        active_deployment_count = self.session.execute(active_deployment_stmt).scalar()

        if active_deployment_count > 0:
            logger.error(f"Cannot delete profile {profile_id}: {active_deployment_count} active deployment(s) found")
            raise ClientException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Cannot delete guardrail profile because it has {active_deployment_count} active deployment(s). Please delete or update the deployments first.",
            )

        try:
            # Soft delete the profile (keep associations for audit trail)
            stmt = (
                update(GuardrailProfiles)
                .where(GuardrailProfiles.id == profile_id)
                .values(status=GuardrailStatusEnum.DELETED)
            )
            self.session.execute(stmt)
            self.session.commit()
            logger.info(f"Successfully soft deleted profile {profile_id}")
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.exception(f"Failed to soft delete profile {profile_id}: {e}")
            raise DatabaseException("Unable to soft delete guardrail profile") from e

    async def soft_delete_deployment(self, deployment_id: UUID) -> None:
        """Soft delete a guardrail deployment.

        Args:
            deployment_id (UUID): The deployment id to soft delete.

        Returns:
            None
        """
        try:
            # Soft delete the deployment
            stmt = (
                update(GuardrailDeployments)
                .where(GuardrailDeployments.id == deployment_id)
                .values(status=GuardrailDeploymentStatusEnum.DELETED)
            )
            self.session.execute(stmt)
            self.session.commit()
            logger.info(f"Successfully soft deleted deployment {deployment_id}")
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.exception(f"Failed to soft delete deployment {deployment_id}: {e}")
            raise DatabaseException("Unable to soft delete guardrail deployment") from e
