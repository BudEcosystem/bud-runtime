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

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.sql import select

from budapp.commons import logging
from budapp.commons.constants import (
    GuardrailDeploymentStatusEnum,
    GuardrailProviderTypeEnum,
    GuardrailStatusEnum,
    ProbeTypeEnum,
)
from budapp.commons.db_utils import DataManagerUtils
from budapp.commons.exceptions import ClientException, DatabaseException
from budapp.guardrails.models import (
    GuardrailDeployment,
    GuardrailProbe,
    GuardrailProfile,
    GuardrailProfileProbe,
    GuardrailProfileRule,
    GuardrailRule,
    GuardrailRuleDeployment,
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

    async def get_probes_with_rules(self, probe_ids: list[UUID]) -> list[GuardrailProbe]:
        """Get probes by IDs with their rules eagerly loaded.

        Args:
            probe_ids: List of probe IDs to fetch

        Returns:
            List of GuardrailProbe objects with rules relationship loaded
        """
        # Query probes
        probe_stmt = (
            select(GuardrailProbe)
            .where(GuardrailProbe.id.in_(probe_ids))
            .where(GuardrailProbe.status == GuardrailStatusEnum.ACTIVE)
        )
        probe_result = self.session.execute(probe_stmt)
        probes = list(probe_result.scalars().all())

        if not probes:
            return []

        # Query rules for these probes
        probe_id_list = [p.id for p in probes]
        rule_stmt = (
            select(GuardrailRule)
            .where(GuardrailRule.probe_id.in_(probe_id_list))
            .where(GuardrailRule.status == GuardrailStatusEnum.ACTIVE)
        )
        rule_result = self.session.execute(rule_stmt)
        rules = list(rule_result.scalars().all())

        # Group rules by probe_id
        rules_by_probe: dict[UUID, list[GuardrailRule]] = {}
        for rule in rules:
            if rule.probe_id not in rules_by_probe:
                rules_by_probe[rule.probe_id] = []
            rules_by_probe[rule.probe_id].append(rule)

        # Attach rules to probes
        for probe in probes:
            probe.rules = rules_by_probe.get(probe.id, [])

        return probes

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

    async def get_missing_probes_and_rules(
        self,
        probe_ids: List[UUID],
        provider_id: UUID,
        rule_selections: Optional[Dict[UUID, List[UUID]]] = None,
    ) -> Tuple[List[UUID], List[UUID]]:
        """Validate that all probe and rule IDs exist with the given filters.

        This method efficiently validates multiple probe and rule IDs in a single query
        to ensure they all exist with the specified provider and status.

        Args:
            probe_ids: List of probe IDs to validate
            provider_id: Provider ID that probes must belong to
            rule_selections: Optional dict mapping probe_id to list of rule_ids

        Returns:
            Tuple of (invalid_probe_ids, invalid_rule_ids)
        """
        invalid_probe_ids = []
        invalid_rule_ids = []

        # Validate probes if provided
        if probe_ids:
            # Query to find all valid probe IDs
            valid_probes_stmt = (
                select(GuardrailProbe.id)
                .where(GuardrailProbe.id.in_(probe_ids))
                .where(GuardrailProbe.provider_id == provider_id)
                .where(GuardrailProbe.status == GuardrailStatusEnum.ACTIVE)
            )
            valid_probe_ids = set(self.session.scalars(valid_probes_stmt).all())

            # Find invalid probe IDs
            invalid_probe_ids = [pid for pid in probe_ids if pid not in valid_probe_ids]

            if invalid_probe_ids:
                logger.warning(f"Invalid probe IDs found: {invalid_probe_ids}")

        # Validate rules if provided
        if rule_selections:
            all_rule_ids = []
            probe_rule_mapping = []

            for probe_id, rule_ids in rule_selections.items():
                for rule_id in rule_ids:
                    all_rule_ids.append(rule_id)
                    probe_rule_mapping.append((probe_id, rule_id))

            if all_rule_ids:
                # Query to find all valid rule IDs with their probe associations
                valid_rules_stmt = (
                    select(GuardrailRule.id, GuardrailRule.probe_id)
                    .where(GuardrailRule.id.in_(all_rule_ids))
                    .where(GuardrailRule.status == GuardrailStatusEnum.ACTIVE)
                )
                valid_rules = self.session.execute(valid_rules_stmt).all()

                # Create a set of valid (probe_id, rule_id) tuples
                valid_probe_rule_pairs = {(rule.probe_id, rule.id) for rule in valid_rules}

                # Find invalid rule IDs (either don't exist or don't belong to the correct probe)
                for probe_id, rule_id in probe_rule_mapping:
                    if (probe_id, rule_id) not in valid_probe_rule_pairs:
                        invalid_rule_ids.append(rule_id)

                if invalid_rule_ids:
                    logger.warning(f"Invalid rule IDs found: {invalid_rule_ids}")

        return invalid_probe_ids, invalid_rule_ids


class GuardrailsDeploymentDataManager(DataManagerUtils):
    """Data manager for guardrail deployments including probes and rules overrides."""

    async def list_profile_tags(
        self,
        search_value: str = "",
        offset: int = 0,
        limit: int = 10,
    ) -> Tuple[List[GuardrailProfile], int]:
        """Search tags by name with pagination for profiles, or fetch all tags if no search value is provided."""
        # Ensure only valid JSON arrays are processed
        tags_subquery = (
            select(func.jsonb_array_elements(GuardrailProfile.tags).label("tag"))
            .where(GuardrailProfile.status == GuardrailStatusEnum.ACTIVE)
            .where(GuardrailProfile.tags.is_not(None))  # Exclude null tags
            .where(func.jsonb_typeof(GuardrailProfile.tags) == "array")  # Ensure tags is a JSON array
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

    async def get_profile_counts(self, profile_id: UUID) -> Tuple[int, int, bool]:
        """Return probe count, deployment count, and standalone flag for a profile."""
        deployment_counts_subquery = (
            select(
                func.count(GuardrailDeployment.id).label("deployment_count"),
                func.count().filter(GuardrailDeployment.endpoint_id.is_(None)).label("standalone_count"),
            )
            .where(GuardrailDeployment.profile_id == profile_id)
            .where(GuardrailDeployment.status != GuardrailDeploymentStatusEnum.DELETED)
        ).subquery()

        probe_count_subquery = (
            select(func.count(GuardrailProfileProbe.id)).where(GuardrailProfileProbe.profile_id == profile_id)
        ).scalar_subquery()

        counts = self.session.execute(
            select(
                func.coalesce(probe_count_subquery, 0).label("probe_count"),
                func.coalesce(deployment_counts_subquery.c.deployment_count, 0).label("deployment_count"),
                func.coalesce(deployment_counts_subquery.c.standalone_count, 0).label("standalone_count"),
            ).select_from(deployment_counts_subquery)
        ).one()

        return counts.probe_count, counts.deployment_count, counts.standalone_count > 0

    async def add_profile_with_selections(
        self,
        name: str,
        current_user_id: UUID,
        probe_selections: List[Dict[str, Any]],
        description: Optional[str] = None,
        tags: Optional[List[Dict[str, str]]] = None,
        severity_threshold: Optional[float] = None,
        guard_types: Optional[List[str]] = None,
        status: GuardrailStatusEnum = GuardrailStatusEnum.ACTIVE,
        project_id: Optional[UUID] = None,
    ) -> GuardrailProfile:
        """Create guardrail profile with probe and rule selections atomically.

        This method creates:
        1. GuardrailProfile
        2. GuardrailProfileProbe records for each selected probe
        3. GuardrailProfileRule records for each rule with specific overrides

        All operations are performed within a single database transaction.
        If any operation fails, all changes are rolled back.

        Args:
            name: Profile name
            current_user_id: ID of the user creating the profile
            probe_selections: List of probe configurations with optional rule overrides
            description: Profile description
            tags: List of tags with 'name' and 'color' keys
            severity_threshold: Default severity threshold for the profile
            guard_types: List of guard types
            status: Profile status (default: ACTIVE)

        Returns:
            The created GuardrailProfile instance

        Raises:
            DatabaseException: If any database operation fails
        """
        savepoint = None

        try:
            # Start a new transaction savepoint
            savepoint = self.session.begin_nested()

            # Create the profile
            db_profile = GuardrailProfile(
                name=name,
                created_by=current_user_id,
                status=status,
                description=description or "",
                tags=tags,
                severity_threshold=severity_threshold,
                guard_types=guard_types,
                project_id=project_id,
            )
            self.session.add(db_profile)

            # Flush to get the profile ID without committing
            self.session.flush()

            # Process probe selections
            for probe_selection in probe_selections:
                probe_id = probe_selection["id"]

                # Create GuardrailProfileProbe
                db_profile_probe = GuardrailProfileProbe(
                    profile_id=db_profile.id,
                    probe_id=probe_id,
                    severity_threshold=probe_selection.get("severity_threshold"),
                    guard_types=probe_selection.get("guard_types"),
                    created_by=current_user_id,
                )
                self.session.add(db_profile_probe)

                # Flush to get the profile_probe ID
                self.session.flush()

                # Process rule selections if present
                for rule_selection in probe_selection.get("rules", []):
                    # Only create GuardrailProfileRule if the rule has specific overrides
                    # or if it's explicitly disabled (status != ACTIVE)
                    if (
                        rule_selection.get("status") == GuardrailStatusEnum.DISABLED
                        or rule_selection.get("severity_threshold") is not None
                        or rule_selection.get("guard_types") is not None
                    ):
                        db_profile_rule = GuardrailProfileRule(
                            profile_probe_id=db_profile_probe.id,
                            rule_id=rule_selection["id"],
                            status=rule_selection.get("status", GuardrailStatusEnum.ACTIVE),
                            severity_threshold=rule_selection.get("severity_threshold"),
                            guard_types=rule_selection.get("guard_types"),
                            created_by=current_user_id,
                        )
                        self.session.add(db_profile_rule)

            # Commit the savepoint
            savepoint.commit()

            # Refresh the profile to get all relationships
            self.session.refresh(db_profile)

            return db_profile

        except SQLAlchemyError as e:
            # Rollback the savepoint on any database error
            if savepoint and savepoint.is_active:
                savepoint.rollback()
            logger.exception(f"Failed to create guardrail profile with selections: {e}")
            raise DatabaseException("Unable to create guardrail profile") from e
        except Exception as e:
            # Rollback on any other error
            if savepoint and savepoint.is_active:
                savepoint.rollback()
            logger.exception(f"Unexpected error creating guardrail profile: {e}")
            raise

    async def get_all_profiles(
        self,
        offset: int,
        limit: int,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[GuardrailProfile], int]:
        """List all profiles in the database.

        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return
            filters: Dictionary of filters to apply
            order_by: List of fields to order by
            search: Whether to use search filters

        Returns:
            Tuple of list of profiles and total count
        """
        # Validate the filters
        await self.validate_fields(GuardrailProfile, filters)

        # Generate statements according to search or filters
        if search:
            search_conditions = await self.generate_search_stmt(GuardrailProfile, filters)
            stmt = select(GuardrailProfile).filter(or_(*search_conditions))
            count_stmt = select(func.count()).select_from(GuardrailProfile).filter(or_(*search_conditions))
        else:
            stmt = select(GuardrailProfile).filter_by(**filters)
            count_stmt = select(func.count()).select_from(GuardrailProfile).filter_by(**filters)

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(GuardrailProfile, order_by)
            stmt = stmt.order_by(*sort_conditions)

        result = self.execute_all(stmt)

        return result, count

    async def soft_delete_profile(self, profile_id: UUID) -> None:
        """Soft delete a guardrail profile.

        Args:
            profile_id (UUID): The profile id to soft delete.

        Returns:
            None
        """
        # Check for active (non-deleted) deployments that are linked to endpoints
        active_endpoint_deployment_stmt = (
            select(func.count(GuardrailDeployment.id))
            .where(GuardrailDeployment.profile_id == profile_id)
            .where(GuardrailDeployment.endpoint_id.is_not(None))
            .where(GuardrailDeployment.status != GuardrailDeploymentStatusEnum.DELETED)
        )
        active_endpoint_deployment_count = self.session.execute(active_endpoint_deployment_stmt).scalar()

        if active_endpoint_deployment_count > 0:
            logger.error(
                f"Cannot delete profile {profile_id}: {active_endpoint_deployment_count} active deployment(s) with endpoints found"
            )
            raise ValueError(
                f"Cannot delete guardrail profile because it has {active_endpoint_deployment_count} active deployment(s) with endpoints. Please delete or update the deployments first."
            )

        try:
            # Soft delete standalone deployments (no endpoint) before deleting the profile
            standalone_delete_stmt = (
                update(GuardrailDeployment)
                .where(GuardrailDeployment.profile_id == profile_id)
                .where(GuardrailDeployment.endpoint_id.is_(None))
                .where(GuardrailDeployment.status != GuardrailDeploymentStatusEnum.DELETED)
                .values(status=GuardrailDeploymentStatusEnum.DELETED)
            )
            self.session.execute(standalone_delete_stmt)

            # Soft delete the profile (keep associations for audit trail)
            stmt = (
                update(GuardrailProfile)
                .where(GuardrailProfile.id == profile_id)
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
                update(GuardrailDeployment)
                .where(GuardrailDeployment.id == deployment_id)
                .values(status=GuardrailDeploymentStatusEnum.DELETED)
            )
            self.session.execute(stmt)
            self.session.commit()
            logger.info(f"Successfully soft deleted deployment {deployment_id}")
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.exception(f"Failed to soft delete deployment {deployment_id}: {e}")
            raise DatabaseException("Unable to soft delete guardrail deployment") from e

    async def get_profile_probes(
        self,
        profile_id: UUID,
        offset: int,
        limit: int,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[Tuple[GuardrailProfileProbe, GuardrailProbe]], int]:
        """Get probes enabled in a profile with pagination and filtering.

        This method performs an efficient join between GuardrailProfileProbe and GuardrailProbe
        to get all probes that are enabled in a specific profile, with support for filtering,
        searching, and pagination.

        Args:
            profile_id: The profile ID to get probes for
            offset: Number of records to skip
            limit: Maximum number of records to return
            filters: Dictionary of filters to apply on GuardrailProbe fields
            order_by: List of fields to order by
            search: Whether to use search filters

        Returns:
            Tuple of list of (GuardrailProfileProbe, GuardrailProbe) and total count
        """
        # Tags are not filterable
        # Also remove from filters dict
        explicit_conditions = []
        json_filters = {"tags": filters.pop("tags", [])}

        # Validate filters for GuardrailProbe model
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
                select(GuardrailProfileProbe, GuardrailProbe)
                .select_from(GuardrailProfileProbe)
                .join(GuardrailProbe, GuardrailProfileProbe.probe_id == GuardrailProbe.id)
                .where(GuardrailProfileProbe.profile_id == profile_id)
                .filter(or_(*search_conditions, *explicit_conditions))
                .filter(GuardrailProbe.status == GuardrailStatusEnum.ACTIVE)
            )
            count_stmt = (
                select(func.count())
                .select_from(GuardrailProfileProbe)
                .join(GuardrailProbe, GuardrailProfileProbe.probe_id == GuardrailProbe.id)
                .where(GuardrailProfileProbe.profile_id == profile_id)
                .filter(or_(*search_conditions, *explicit_conditions))
                .filter(GuardrailProbe.status == GuardrailStatusEnum.ACTIVE)
            )
        else:
            stmt = (
                select(GuardrailProfileProbe, GuardrailProbe)
                .select_from(GuardrailProfileProbe)
                .join(GuardrailProbe, GuardrailProfileProbe.probe_id == GuardrailProbe.id)
                .where(GuardrailProfileProbe.profile_id == profile_id)
                .where(GuardrailProbe.status == GuardrailStatusEnum.ACTIVE)
            )
            # Apply filters using filter_by for exact matches
            if filters:
                stmt = stmt.where(
                    GuardrailProbe.id.in_(
                        select(GuardrailProbe.id)
                        .filter_by(**filters)
                        .where(and_(*explicit_conditions) if explicit_conditions else True)
                    )
                )
            elif explicit_conditions:
                stmt = stmt.where(and_(*explicit_conditions))

            count_stmt = (
                select(func.count())
                .select_from(GuardrailProfileProbe)
                .join(GuardrailProbe, GuardrailProfileProbe.probe_id == GuardrailProbe.id)
                .where(GuardrailProfileProbe.profile_id == profile_id)
                .where(GuardrailProbe.status == GuardrailStatusEnum.ACTIVE)
            )
            # Apply same filter logic to count
            if filters:
                count_stmt = count_stmt.where(
                    GuardrailProbe.id.in_(
                        select(GuardrailProbe.id)
                        .filter_by(**filters)
                        .where(and_(*explicit_conditions) if explicit_conditions else True)
                    )
                )
            elif explicit_conditions:
                count_stmt = count_stmt.where(and_(*explicit_conditions))

        # Get total count
        count = self.execute_scalar(count_stmt) or 0

        # Apply ordering
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(GuardrailProbe, order_by)
            stmt = stmt.order_by(*sort_conditions)
        else:
            # Default ordering by probe name
            stmt = stmt.order_by(GuardrailProbe.name)

        # Apply pagination
        stmt = stmt.offset(offset).limit(limit)

        # Execute query
        results = self.session.execute(stmt).all()

        return results, count

    async def get_profile_probe_rules(
        self,
        profile_id: UUID,
        probe_id: UUID,
        offset: int,
        limit: int,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[Tuple[GuardrailRule, Optional[GuardrailProfileRule]]], int]:
        """Get rules for a specific probe in a profile with status overrides.

        This method efficiently retrieves all active rules for a probe and joins them
        with any profile-specific rule overrides (disabled rules or custom settings).

        Args:
            profile_id: The profile ID
            probe_id: The probe ID
            offset: Number of records to skip
            limit: Maximum number of records to return
            filters: Dictionary of filters to apply on GuardrailRule fields
            order_by: List of fields to order by
            search: Whether to use search filters

        Returns:
            Tuple of list of (GuardrailRule, Optional[GuardrailProfileRule]) and total count
        """
        # First verify the probe is enabled in the profile
        profile_probe_stmt = (
            select(GuardrailProfileProbe)
            .where(GuardrailProfileProbe.profile_id == profile_id)
            .where(GuardrailProfileProbe.probe_id == probe_id)
        )
        profile_probe = self.scalar_one_or_none(profile_probe_stmt)

        if not profile_probe:
            # Probe not enabled in this profile
            return [], 0

        # Validate filters for GuardrailRule model (excluding probe_id which is handled separately)
        await self.validate_fields(GuardrailRule, filters)

        # Generate statements according to search or filters
        if search:
            search_conditions = await self.generate_search_stmt(GuardrailRule, filters)
            stmt = (
                select(GuardrailRule, GuardrailProfileRule)
                .select_from(GuardrailRule)
                .outerjoin(
                    GuardrailProfileRule,
                    and_(
                        GuardrailProfileRule.rule_id == GuardrailRule.id,
                        GuardrailProfileRule.profile_probe_id == profile_probe.id,
                    ),
                )
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
                select(GuardrailRule, GuardrailProfileRule)
                .select_from(GuardrailRule)
                .outerjoin(
                    GuardrailProfileRule,
                    and_(
                        GuardrailProfileRule.rule_id == GuardrailRule.id,
                        GuardrailProfileRule.profile_probe_id == profile_probe.id,
                    ),
                )
                .filter(GuardrailRule.probe_id == probe_id)
                .filter(GuardrailRule.status == GuardrailStatusEnum.ACTIVE)
            )
            count_stmt = (
                select(func.count())
                .select_from(GuardrailRule)
                .filter(GuardrailRule.probe_id == probe_id)
                .filter(GuardrailRule.status == GuardrailStatusEnum.ACTIVE)
            )

            # Apply additional filters if any
            if filters:
                stmt = stmt.filter_by(**filters)
                count_stmt = count_stmt.filter_by(**filters)

        # Get total count
        count = self.execute_scalar(count_stmt) or 0

        # Apply ordering
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(GuardrailRule, order_by)
            stmt = stmt.order_by(*sort_conditions)
        else:
            # Default ordering by rule name
            stmt = stmt.order_by(GuardrailRule.name)

        # Apply pagination
        stmt = stmt.offset(offset).limit(limit)

        # Execute query
        results = self.session.execute(stmt).all()

        return results, count

    async def get_all_deployments(
        self,
        offset: int,
        limit: int,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[GuardrailDeployment], int]:
        """List all deployments in the database with pagination.

        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return
            filters: Dictionary of filters to apply
            order_by: List of fields to order by
            search: Whether to use search filters

        Returns:
            Tuple of list of deployments and total count
        """
        # Validate the filters
        await self.validate_fields(GuardrailDeployment, filters)

        # Generate statements according to search or filters
        if search:
            search_conditions = await self.generate_search_stmt(GuardrailDeployment, filters)
            stmt = (
                select(GuardrailDeployment)
                .filter(or_(*search_conditions))
                .filter(GuardrailDeployment.status != GuardrailDeploymentStatusEnum.DELETED)
            )
            count_stmt = (
                select(func.count())
                .select_from(GuardrailDeployment)
                .filter(or_(*search_conditions))
                .filter(GuardrailDeployment.status != GuardrailDeploymentStatusEnum.DELETED)
            )
        else:
            stmt = (
                select(GuardrailDeployment)
                .filter_by(**filters)
                .filter(GuardrailDeployment.status != GuardrailDeploymentStatusEnum.DELETED)
            )
            count_stmt = (
                select(func.count())
                .select_from(GuardrailDeployment)
                .filter_by(**filters)
                .filter(GuardrailDeployment.status != GuardrailDeploymentStatusEnum.DELETED)
            )

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(GuardrailDeployment, order_by)
            stmt = stmt.order_by(*sort_conditions)
        else:
            # Default ordering by created_at desc
            stmt = stmt.order_by(GuardrailDeployment.created_at.desc())

        result = self.execute_all(stmt)

        return result, count

    async def get_existing_deployments_for_endpoints(
        self, endpoint_ids: List[UUID]
    ) -> Dict[UUID, GuardrailDeployment]:
        """Get existing guardrail deployments for given endpoint IDs.

        Returns a dictionary mapping endpoint_id to deployment for endpoints that have
        non-deleted guardrail deployments. The deployment objects include the related
        endpoint and profile data via eager loading.

        Args:
            endpoint_ids: List of endpoint IDs to check

        Returns:
            Dict mapping endpoint_id to GuardrailDeployment for endpoints with existing deployments
        """
        if not endpoint_ids:
            return {}

        stmt = (
            select(GuardrailDeployment)
            .where(GuardrailDeployment.endpoint_id.in_(endpoint_ids))
            .where(GuardrailDeployment.status != GuardrailDeploymentStatusEnum.DELETED)
            .options(joinedload(GuardrailDeployment.profile), joinedload(GuardrailDeployment.endpoint))
        )

        result = self.execute_all(stmt)

        # Convert to dictionary keyed by endpoint_id
        existing_deployments = {}
        for deployment in result:
            if deployment[0].endpoint_id:
                existing_deployments[deployment[0].endpoint_id] = deployment[0]

        return existing_deployments

    async def create_custom_probe_with_rule(
        self,
        name: str,
        description: str | None,
        scanner_type: str,
        model_id: UUID,
        model_config: dict,
        model_uri: str,
        model_provider_type: str,
        is_gated: bool,
        project_id: UUID,
        user_id: UUID,
        provider_id: UUID,
    ) -> GuardrailProbe:
        """Create a custom probe with a single model-based rule atomically."""
        # Generate URI for uniqueness check
        probe_uri = f"custom.{user_id}.{name.lower().replace(' ', '_')}"

        # Check for existing probe with same URI (same user + same name)
        existing = self.session.query(GuardrailProbe).filter_by(uri=probe_uri).first()
        if existing:
            raise ClientException(
                message=f"A custom probe with name '{name}' already exists for this user",
                status_code=409,
            )

        savepoint = None
        try:
            # Start a new transaction savepoint
            savepoint = self.session.begin_nested()

            # Create probe
            probe = GuardrailProbe(
                name=name,
                uri=probe_uri,
                description=description,
                probe_type=ProbeTypeEnum.CUSTOM,
                provider_type=GuardrailProviderTypeEnum.BUD,
                provider_id=provider_id,
                created_by=user_id,
                status=GuardrailStatusEnum.ACTIVE,
            )
            self.session.add(probe)
            self.session.flush()

            # Create single rule for the probe
            rule = GuardrailRule(
                probe_id=probe.id,
                name=name,
                uri=f"{probe_uri}.rule",
                description=description,
                scanner_type=scanner_type,
                model_uri=model_uri,
                model_provider_type=model_provider_type,
                is_gated=is_gated,
                model_config_json=model_config,
                model_id=model_id,
                created_by=user_id,
                status=GuardrailStatusEnum.ACTIVE,
            )
            self.session.add(rule)
            self.session.flush()

            # Commit the savepoint and the session
            if savepoint:
                savepoint.commit()
            self.session.commit()

            # Refresh probe to load the rules relationship
            self.session.refresh(probe)

            return probe

        except Exception as e:
            # Rollback the savepoint on any error
            if savepoint and savepoint.is_active:
                savepoint.rollback()
            self.session.rollback()
            logger.exception(f"Failed to create custom probe with rule: {e}")
            raise

    async def get_custom_probes(
        self,
        user_id: UUID,
        project_id: UUID | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[GuardrailProbe], int]:
        """Get custom probes created by user."""
        query = (
            select(GuardrailProbe)
            .options(selectinload(GuardrailProbe.rules))
            .where(GuardrailProbe.probe_type == ProbeTypeEnum.CUSTOM)
            .where(GuardrailProbe.created_by == user_id)
            .where(GuardrailProbe.status == GuardrailStatusEnum.ACTIVE)
        )
        count_query = (
            select(func.count())
            .select_from(GuardrailProbe)
            .where(GuardrailProbe.probe_type == ProbeTypeEnum.CUSTOM)
            .where(GuardrailProbe.created_by == user_id)
            .where(GuardrailProbe.status == GuardrailStatusEnum.ACTIVE)
        )

        total = self.session.scalar(count_query)
        result = self.session.execute(query.offset(offset).limit(limit))
        probes = result.scalars().all()

        return list(probes), total or 0

    async def get_model_probes_from_selections(
        self,
        probe_ids: list[UUID],
    ) -> list[GuardrailProbe]:
        """Get probes that are model-based (model_scanner or custom) from selection."""
        query = (
            select(GuardrailProbe)
            .where(GuardrailProbe.id.in_(probe_ids))
            .where(GuardrailProbe.probe_type.in_([ProbeTypeEnum.MODEL_SCANNER, ProbeTypeEnum.CUSTOM]))
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_rule_deployment(
        self,
        guardrail_deployment_id: UUID,
        rule_id: UUID,
        model_id: UUID,
        endpoint_id: UUID,
        cluster_id: UUID,
        config_override: dict | None = None,
    ) -> GuardrailRuleDeployment:
        """Create a rule deployment record."""
        deployment = GuardrailRuleDeployment(
            guardrail_deployment_id=guardrail_deployment_id,
            rule_id=rule_id,
            model_id=model_id,
            endpoint_id=endpoint_id,
            cluster_id=cluster_id,
            config_override_json=config_override,
        )
        self.session.add(deployment)
        await self.session.flush()
        return deployment

    async def get_rule_deployments_for_guardrail(
        self,
        guardrail_deployment_id: UUID,
    ) -> list[GuardrailRuleDeployment]:
        """Get all rule deployments for a guardrail deployment."""
        query = select(GuardrailRuleDeployment).where(
            GuardrailRuleDeployment.guardrail_deployment_id == guardrail_deployment_id
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
