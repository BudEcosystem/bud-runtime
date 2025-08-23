"""Database operations for audit trail functionality.

This module provides CRUD operations for audit trail records.
Note that audit records are immutable - only create and read operations are supported.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from budapp.audit_ops.models import AuditTrail
from budapp.commons.constants import AuditActionEnum, AuditResourceTypeEnum
from budapp.commons.database_utils import DataManagerUtils


class AuditTrailDataManager(DataManagerUtils):
    """Data manager for audit trail operations.

    Provides methods for creating and querying audit records.
    Update and delete operations are not supported as audit records are immutable.
    """

    def __init__(self, session: Session):
        """Initialize the audit trail data manager.

        Args:
            session: SQLAlchemy database session
        """
        super().__init__(session)

    async def create_audit_record(
        self,
        action: AuditActionEnum,
        resource_type: AuditResourceTypeEnum,
        resource_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        actioned_by: Optional[UUID] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        previous_state: Optional[dict] = None,
        new_state: Optional[dict] = None,
    ) -> AuditTrail:
        """Create a new audit trail record.

        Args:
            action: Type of action performed
            resource_type: Type of resource affected
            resource_id: ID of the affected resource
            user_id: ID of the user who performed the action
            actioned_by: ID of the admin/user who performed the action on behalf of another user
            details: Additional context about the action
            ip_address: IP address from which the action was performed
            timestamp: When the action occurred (defaults to current time)
            previous_state: State of the resource before the action
            new_state: State of the resource after the action

        Returns:
            Created audit trail record
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        audit_record = AuditTrail(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            actioned_by=actioned_by,
            details=details,
            ip_address=ip_address,
            timestamp=timestamp,
            previous_state=previous_state,
            new_state=new_state,
        )

        self.session.add(audit_record)
        self.session.commit()
        self.session.refresh(audit_record)

        return audit_record

    async def get_audit_record_by_id(self, audit_id: UUID, include_user: bool = False) -> Optional[AuditTrail]:
        """Get a single audit record by ID.

        Args:
            audit_id: ID of the audit record
            include_user: Whether to include user relationship

        Returns:
            Audit record if found, None otherwise
        """
        stmt = select(AuditTrail).where(AuditTrail.id == audit_id)

        if include_user:
            stmt = stmt.options(selectinload(AuditTrail.user), selectinload(AuditTrail.actioned_by_user))

        return self.scalar_one_or_none(stmt)

    async def get_audit_records_by_user(
        self,
        user_id: UUID,
        offset: int = 0,
        limit: int = 20,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        action: Optional[AuditActionEnum] = None,
        resource_type: Optional[AuditResourceTypeEnum] = None,
    ) -> Tuple[List[AuditTrail], int]:
        """Get audit records for a specific user with pagination.

        Args:
            user_id: ID of the user
            offset: Number of records to skip
            limit: Maximum number of records to return
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)
            action: Filter by action type
            resource_type: Filter by resource type

        Returns:
            Tuple of (list of audit records, total count)
        """
        # Build the base query
        conditions = [AuditTrail.user_id == user_id]

        if start_date:
            conditions.append(AuditTrail.timestamp >= start_date)
        if end_date:
            conditions.append(AuditTrail.timestamp <= end_date)
        if action:
            conditions.append(AuditTrail.action == action)
        if resource_type:
            conditions.append(AuditTrail.resource_type == resource_type)

        where_clause = and_(*conditions)

        # Count query
        count_stmt = select(func.count()).select_from(AuditTrail).where(where_clause)
        total_count = self.execute_scalar(count_stmt) or 0

        # Main query with pagination and ordering
        stmt = (
            select(AuditTrail)
            .where(where_clause)
            .order_by(AuditTrail.timestamp.desc())
            .offset(offset)
            .limit(limit)
            .options(selectinload(AuditTrail.user), selectinload(AuditTrail.actioned_by_user))
        )

        records = self.scalars_all(stmt)

        return records, total_count

    async def get_audit_records_by_resource(
        self,
        resource_type: AuditResourceTypeEnum,
        resource_id: UUID,
        offset: int = 0,
        limit: int = 20,
        include_user: bool = True,
    ) -> Tuple[List[AuditTrail], int]:
        """Get audit records for a specific resource with pagination.

        Args:
            resource_type: Type of resource
            resource_id: ID of the resource
            offset: Number of records to skip
            limit: Maximum number of records to return
            include_user: Whether to include user relationship

        Returns:
            Tuple of (list of audit records, total count)
        """
        where_clause = and_(AuditTrail.resource_type == resource_type, AuditTrail.resource_id == resource_id)

        # Count query
        count_stmt = select(func.count()).select_from(AuditTrail).where(where_clause)
        total_count = self.execute_scalar(count_stmt) or 0

        # Main query with pagination and ordering
        stmt = select(AuditTrail).where(where_clause).order_by(AuditTrail.timestamp.desc()).offset(offset).limit(limit)

        if include_user:
            stmt = stmt.options(selectinload(AuditTrail.user), selectinload(AuditTrail.actioned_by_user))

        records = self.scalars_all(stmt)

        return records, total_count

    async def get_audit_records_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        action: Optional[AuditActionEnum] = None,
        resource_type: Optional[AuditResourceTypeEnum] = None,
        user_id: Optional[UUID] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> Tuple[List[AuditTrail], int]:
        """Get audit records within a date range with pagination.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            action: Filter by action type
            resource_type: Filter by resource type
            user_id: Filter by user ID
            offset: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (list of audit records, total count)
        """
        conditions = [AuditTrail.timestamp >= start_date, AuditTrail.timestamp <= end_date]

        if action:
            conditions.append(AuditTrail.action == action)
        if resource_type:
            conditions.append(AuditTrail.resource_type == resource_type)
        if user_id:
            conditions.append(AuditTrail.user_id == user_id)

        where_clause = and_(*conditions)

        # Count query
        count_stmt = select(func.count()).select_from(AuditTrail).where(where_clause)
        total_count = self.execute_scalar(count_stmt) or 0

        # Main query with pagination and ordering
        stmt = (
            select(AuditTrail)
            .where(where_clause)
            .order_by(AuditTrail.timestamp.desc())
            .offset(offset)
            .limit(limit)
            .options(selectinload(AuditTrail.user), selectinload(AuditTrail.actioned_by_user))
        )

        records = self.scalars_all(stmt)

        return records, total_count

    async def get_recent_audit_records(
        self,
        limit: int = 20,
        action: Optional[AuditActionEnum] = None,
        resource_type: Optional[AuditResourceTypeEnum] = None,
    ) -> List[AuditTrail]:
        """Get the most recent audit records.

        Args:
            limit: Maximum number of records to return
            action: Filter by action type
            resource_type: Filter by resource type

        Returns:
            List of recent audit records
        """
        conditions = []

        if action:
            conditions.append(AuditTrail.action == action)
        if resource_type:
            conditions.append(AuditTrail.resource_type == resource_type)

        stmt = (
            select(AuditTrail)
            .order_by(AuditTrail.timestamp.desc())
            .limit(limit)
            .options(selectinload(AuditTrail.user), selectinload(AuditTrail.actioned_by_user))
        )

        if conditions:
            stmt = stmt.where(and_(*conditions))

        return self.scalars_all(stmt)

    async def get_audit_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict:
        """Get summary statistics for audit records.

        Args:
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)

        Returns:
            Dictionary containing summary statistics
        """
        conditions = []

        if start_date:
            conditions.append(AuditTrail.timestamp >= start_date)
        if end_date:
            conditions.append(AuditTrail.timestamp <= end_date)

        where_clause = and_(*conditions) if conditions else None

        # Total records count
        total_stmt = select(func.count()).select_from(AuditTrail)
        if where_clause is not None:
            total_stmt = total_stmt.where(where_clause)
        total_records = self.execute_scalar(total_stmt) or 0

        # Unique users count
        users_stmt = select(func.count(func.distinct(AuditTrail.user_id))).select_from(AuditTrail)
        if where_clause is not None:
            users_stmt = users_stmt.where(where_clause)
        unique_users = self.execute_scalar(users_stmt) or 0

        # Most common actions
        actions_stmt = (
            select(AuditTrail.action, func.count(AuditTrail.action).label("count"))
            .select_from(AuditTrail)
            .group_by(AuditTrail.action)
            .order_by(func.count(AuditTrail.action).desc())
            .limit(10)
        )
        if where_clause is not None:
            actions_stmt = actions_stmt.where(where_clause)

        action_results = self.session.execute(actions_stmt).all()
        most_common_actions = [{"action": action, "count": count} for action, count in action_results]

        # Most active users
        users_activity_stmt = (
            select(AuditTrail.user_id, func.count(AuditTrail.user_id).label("count"))
            .select_from(AuditTrail)
            .where(AuditTrail.user_id.isnot(None))
            .group_by(AuditTrail.user_id)
            .order_by(func.count(AuditTrail.user_id).desc())
            .limit(10)
        )
        if where_clause is not None:
            users_activity_stmt = users_activity_stmt.where(where_clause)

        user_results = self.session.execute(users_activity_stmt).all()
        most_active_users = [{"user_id": str(user_id), "count": count} for user_id, count in user_results]

        return {
            "total_records": total_records,
            "unique_users": unique_users,
            "most_common_actions": most_common_actions,
            "most_active_users": most_active_users,
            "date_range": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
        }
