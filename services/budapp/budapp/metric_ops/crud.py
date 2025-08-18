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

"""CRUD operations for metrics and gateway blocking rules."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, joinedload

from ..commons import logging
from ..commons.constants import BlockingRuleStatus, BlockingRuleType
from ..commons.db_utils import SessionMixin
from .models import GatewayBlockingRule
from .schemas import BlockingRuleCreate, BlockingRuleUpdate


logger = logging.get_logger(__name__)


class BlockingRuleDataManager(SessionMixin):
    """Data manager for gateway blocking rules CRUD operations."""

    def __init__(self, session: Session):
        """Initialize the data manager.

        Args:
            session: Database session
        """
        super().__init__(session)

    async def create_blocking_rule(
        self,
        project_id: Optional[UUID],
        user_id: UUID,
        rule_data: BlockingRuleCreate,
    ) -> GatewayBlockingRule:
        """Create a new blocking rule.

        Args:
            project_id: Project ID (None for global rules)
            user_id: User creating the rule
            rule_data: Rule creation data

        Returns:
            Created blocking rule
        """
        db_rule = GatewayBlockingRule(
            name=rule_data.name,
            description=rule_data.description,
            rule_type=rule_data.rule_type,
            rule_config=rule_data.rule_config,
            reason=rule_data.reason,
            priority=rule_data.priority,
            endpoint_id=rule_data.endpoint_id,
            project_id=project_id,
            model_name=rule_data.model_name,
            created_by=user_id,
            status=BlockingRuleStatus.ACTIVE,
        )

        self.session.add(db_rule)
        self.session.commit()
        self.session.refresh(db_rule)

        if project_id:
            logger.info(f"Created blocking rule {db_rule.id} for project {project_id}")
        elif rule_data.model_name:
            logger.info(f"Created model-specific blocking rule {db_rule.id} for model {rule_data.model_name}")
        else:
            logger.info(f"Created global blocking rule {db_rule.id}")
        return db_rule

    async def get_blocking_rule(
        self,
        rule_id: UUID,
        project_ids: Optional[List[UUID]] = None,
    ) -> Optional[GatewayBlockingRule]:
        """Get a blocking rule by ID.

        Args:
            rule_id: Rule ID
            project_ids: Optional list of project IDs to filter by

        Returns:
            Blocking rule if found
        """
        stmt = select(GatewayBlockingRule).where(GatewayBlockingRule.id == rule_id)

        if project_ids:
            stmt = stmt.where(GatewayBlockingRule.project_id.in_(project_ids))

        stmt = stmt.options(
            joinedload(GatewayBlockingRule.project),
            joinedload(GatewayBlockingRule.endpoint),
            joinedload(GatewayBlockingRule.created_user),
        )

        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_blocking_rules(
        self,
        project_ids: List[UUID],
        rule_type: Optional[BlockingRuleType] = None,
        status: Optional[BlockingRuleStatus] = None,
        endpoint_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[GatewayBlockingRule], int]:
        """List blocking rules with filters.

        Args:
            project_ids: List of project IDs to filter by
            rule_type: Optional rule type filter
            status: Optional status filter
            endpoint_id: Optional endpoint ID filter
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            Tuple of (rules, total_count)
        """
        # Base query - for global rules and endpoint-specific rules
        # Global rules have no project_id, endpoint rules need project access check
        from sqlalchemy import or_

        stmt = select(GatewayBlockingRule).where(
            or_(
                GatewayBlockingRule.project_id.is_(None),  # Global rules (no project)
                GatewayBlockingRule.project_id.in_(project_ids),  # Endpoint rules (need project access)
            )
        )

        # Apply filters
        if rule_type:
            stmt = stmt.where(GatewayBlockingRule.rule_type == rule_type)
        if status:
            stmt = stmt.where(GatewayBlockingRule.status == status)
        if endpoint_id:
            stmt = stmt.where(GatewayBlockingRule.endpoint_id == endpoint_id)

        # Order by priority (descending) and creation date
        stmt = stmt.order_by(
            GatewayBlockingRule.priority.desc(),
            GatewayBlockingRule.created_at.desc(),
        )

        # Get total count - construct count query from the base conditions
        count_stmt = select(func.count(GatewayBlockingRule.id)).where(
            or_(
                GatewayBlockingRule.project_id.is_(None),  # Global rules (no project)
                GatewayBlockingRule.project_id.in_(project_ids),  # Endpoint rules (need project access)
            )
        )

        # Apply same filters as the main query
        if rule_type:
            count_stmt = count_stmt.where(GatewayBlockingRule.rule_type == rule_type)
        if status:
            count_stmt = count_stmt.where(GatewayBlockingRule.status == status)
        if endpoint_id:
            count_stmt = count_stmt.where(GatewayBlockingRule.endpoint_id == endpoint_id)

        count_result = self.session.execute(count_stmt)
        total_count = count_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        # Include relationships
        stmt = stmt.options(
            joinedload(GatewayBlockingRule.project),
            joinedload(GatewayBlockingRule.endpoint),
            joinedload(GatewayBlockingRule.created_user),
        )

        result = self.session.execute(stmt)
        rules = result.scalars().unique().all()

        return rules, total_count

    async def update_blocking_rule(
        self,
        rule_id: UUID,
        update_data: BlockingRuleUpdate,
        project_ids: Optional[List[UUID]] = None,
    ) -> Optional[GatewayBlockingRule]:
        """Update a blocking rule.

        Args:
            rule_id: Rule ID
            update_data: Update data
            project_ids: Optional list of project IDs for access control

        Returns:
            Updated rule if found and updated
        """
        rule = await self.get_blocking_rule(rule_id, project_ids)
        if not rule:
            return None

        # Update fields
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(rule, field, value)

        self.session.commit()
        self.session.refresh(rule)

        logger.info(f"Updated blocking rule {rule_id}")
        return rule

    async def delete_blocking_rule(
        self,
        rule_id: UUID,
        project_ids: Optional[List[UUID]] = None,
    ) -> bool:
        """Delete a blocking rule.

        Args:
            rule_id: Rule ID
            project_ids: Optional list of project IDs for access control

        Returns:
            True if deleted, False if not found
        """
        rule = await self.get_blocking_rule(rule_id, project_ids)
        if not rule:
            return False

        self.session.delete(rule)
        self.session.commit()

        logger.info(f"Deleted blocking rule {rule_id}")
        return True

    async def increment_match_count(
        self,
        rule_id: UUID,
    ) -> None:
        """Increment the match count for a rule and update last matched timestamp.

        Args:
            rule_id: Rule ID
        """
        stmt = select(GatewayBlockingRule).where(GatewayBlockingRule.id == rule_id).with_for_update()

        result = self.session.execute(stmt)
        rule = result.scalar_one_or_none()

        if rule:
            rule.match_count += 1
            rule.last_matched_at = datetime.utcnow()
            self.session.commit()

    async def get_active_rules_for_sync(
        self,
        project_ids: Optional[List[UUID]] = None,
    ) -> List[GatewayBlockingRule]:
        """Get all active rules for syncing to Redis.

        Args:
            project_ids: Optional list of project IDs to sync

        Returns:
            List of active blocking rules
        """
        stmt = select(GatewayBlockingRule).where(GatewayBlockingRule.status == BlockingRuleStatus.ACTIVE)

        if project_ids:
            stmt = stmt.where(GatewayBlockingRule.project_id.in_(project_ids))

        stmt = stmt.options(
            joinedload(GatewayBlockingRule.project),
            joinedload(GatewayBlockingRule.endpoint),
        )

        result = self.session.execute(stmt)
        return result.scalars().unique().all()

    async def check_rule_name_exists(
        self,
        project_id: UUID,
        name: str,
        exclude_id: Optional[UUID] = None,
    ) -> bool:
        """Check if a rule name already exists in the project.

        Args:
            project_id: Project ID
            name: Rule name to check
            exclude_id: Rule ID to exclude (for updates)

        Returns:
            True if name exists
        """
        stmt = select(func.count(GatewayBlockingRule.id)).where(
            and_(
                GatewayBlockingRule.project_id == project_id,
                GatewayBlockingRule.name == name,
            )
        )

        if exclude_id:
            stmt = stmt.where(GatewayBlockingRule.id != exclude_id)

        result = self.session.execute(stmt)
        count = result.scalar() or 0

        return count > 0

    async def check_global_rule_name_exists(
        self,
        name: str,
        exclude_id: Optional[UUID] = None,
    ) -> bool:
        """Check if a global rule name already exists.

        Args:
            name: Rule name to check
            exclude_id: Rule ID to exclude (for updates)

        Returns:
            True if name exists
        """
        stmt = select(func.count(GatewayBlockingRule.id)).where(
            and_(
                GatewayBlockingRule.project_id.is_(None),
                GatewayBlockingRule.model_name.is_(None),
                GatewayBlockingRule.name == name,
            )
        )

        if exclude_id:
            stmt = stmt.where(GatewayBlockingRule.id != exclude_id)

        result = self.session.execute(stmt)
        count = result.scalar() or 0

        return count > 0

    async def check_model_rule_name_exists(
        self,
        model_name: str,
        name: str,
        exclude_id: Optional[UUID] = None,
    ) -> bool:
        """Check if a model-specific rule name already exists.

        Args:
            model_name: Model name
            name: Rule name to check
            exclude_id: Rule ID to exclude (for updates)

        Returns:
            True if name exists
        """
        stmt = select(func.count(GatewayBlockingRule.id)).where(
            and_(
                GatewayBlockingRule.model_name == model_name,
                GatewayBlockingRule.name == name,
            )
        )

        if exclude_id:
            stmt = stmt.where(GatewayBlockingRule.id != exclude_id)

        result = self.session.execute(stmt)
        count = result.scalar() or 0

        return count > 0

    async def get_all_blocking_rules(self) -> List[GatewayBlockingRule]:
        """Get all blocking rules (used for stats sync).

        Returns:
            List of all blocking rules
        """
        stmt = select(GatewayBlockingRule).options(
            joinedload(GatewayBlockingRule.project),
            joinedload(GatewayBlockingRule.endpoint),
            joinedload(GatewayBlockingRule.created_user),
        )

        result = self.session.execute(stmt)
        rules = result.scalars().all()

        logger.debug(f"Retrieved {len(rules)} blocking rules for stats sync")
        return list(rules)

    async def update_blocking_rule_stats(
        self,
        rule_id: UUID,
        update_data: dict,
    ) -> Optional[GatewayBlockingRule]:
        """Update blocking rule statistics fields.

        Args:
            rule_id: Rule ID to update
            update_data: Dictionary with stats fields to update

        Returns:
            Updated rule or None if not found
        """
        stmt = select(GatewayBlockingRule).where(GatewayBlockingRule.id == rule_id)
        result = self.session.execute(stmt)
        rule = result.scalar_one_or_none()

        if not rule:
            logger.warning(f"Blocking rule {rule_id} not found for stats update")
            return None

        # Update only the stats fields
        if "match_count" in update_data:
            rule.match_count = update_data["match_count"]
        if "last_matched_at" in update_data:
            rule.last_matched_at = update_data["last_matched_at"]

        self.session.commit()
        self.session.refresh(rule)

        logger.debug(f"Updated stats for blocking rule {rule_id}: {update_data}")
        return rule
