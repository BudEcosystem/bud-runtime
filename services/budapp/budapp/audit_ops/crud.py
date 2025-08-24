"""Database operations for audit trail functionality.

This module provides CRUD operations for audit trail records.
Note that audit records are immutable - only create and read operations are supported.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from budapp.audit_ops.hash_utils import generate_audit_hash
from budapp.audit_ops.models import AuditTrail
from budapp.commons.constants import AuditActionEnum, AuditResourceTypeEnum
from budapp.commons.db_utils import DataManagerUtils


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

    def create_audit_record(
        self,
        action: AuditActionEnum,
        resource_type: AuditResourceTypeEnum,
        resource_id: Optional[UUID] = None,
        resource_name: Optional[str] = None,
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
            resource_name: Name of the affected resource for display and search
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

        # Generate hash for the audit record
        record_hash = generate_audit_hash(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            user_id=user_id,
            actioned_by=actioned_by,
            timestamp=timestamp,
            details=details,
            ip_address=ip_address,
            previous_state=previous_state,
            new_state=new_state,
        )

        audit_record = AuditTrail(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            user_id=user_id,
            actioned_by=actioned_by,
            details=details,
            ip_address=ip_address,
            timestamp=timestamp,
            previous_state=previous_state,
            new_state=new_state,
            record_hash=record_hash,
        )

        self.session.add(audit_record)
        self.session.commit()
        self.session.refresh(audit_record)

        return audit_record

    def get_audit_record_by_id(self, audit_id: UUID, include_user: bool = False) -> Optional[AuditTrail]:
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

    def get_audit_records(
        self,
        user_id: Optional[UUID] = None,
        actioned_by: Optional[UUID] = None,
        action: Optional[AuditActionEnum] = None,
        resource_type: Optional[AuditResourceTypeEnum] = None,
        resource_id: Optional[UUID] = None,
        resource_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        ip_address: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
        include_user: bool = True,
    ) -> Tuple[List[AuditTrail], int]:
        """Get audit records with flexible filtering options.

        Args:
            user_id: Filter by user who performed the action
            actioned_by: Filter by admin/user who performed action on behalf
            action: Filter by action type
            resource_type: Filter by resource type
            resource_id: Filter by specific resource ID
            resource_name: Filter by resource name (partial match)
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)
            ip_address: Filter by IP address
            offset: Number of records to skip for pagination
            limit: Maximum number of records to return
            include_user: Whether to include user relationships

        Returns:
            Tuple of (list of audit records, total count)
        """
        # Build conditions based on provided filters
        conditions = []

        if user_id is not None:
            conditions.append(AuditTrail.user_id == user_id)
        if actioned_by is not None:
            conditions.append(AuditTrail.actioned_by == actioned_by)
        if action is not None:
            conditions.append(AuditTrail.action == action)
        if resource_type is not None:
            conditions.append(AuditTrail.resource_type == resource_type)
        if resource_id is not None:
            conditions.append(AuditTrail.resource_id == resource_id)
        if resource_name is not None:
            # Use ILIKE for case-insensitive partial match
            conditions.append(AuditTrail.resource_name.ilike(f"%{resource_name}%"))
        if start_date is not None:
            conditions.append(AuditTrail.timestamp >= start_date)
        if end_date is not None:
            conditions.append(AuditTrail.timestamp <= end_date)
        if ip_address is not None:
            conditions.append(AuditTrail.ip_address == ip_address)

        # Build where clause
        where_clause = and_(*conditions) if conditions else None

        # Count query
        count_stmt = select(func.count()).select_from(AuditTrail)
        if where_clause is not None:
            count_stmt = count_stmt.where(where_clause)
        total_count = self.execute_scalar(count_stmt) or 0

        # Main query with pagination and ordering
        stmt = select(AuditTrail).order_by(AuditTrail.timestamp.desc()).offset(offset).limit(limit)

        if where_clause is not None:
            stmt = stmt.where(where_clause)

        if include_user:
            stmt = stmt.options(selectinload(AuditTrail.user), selectinload(AuditTrail.actioned_by_user))

        records = self.scalars_all(stmt)
        return records, total_count

    def get_audit_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[UUID] = None,
    ) -> dict:
        """Get summary statistics for audit records.

        Args:
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)
            user_id: User ID for filtering (optional, for CLIENT users)

        Returns:
            Dictionary containing summary statistics
        """
        conditions = []

        if user_id:
            conditions.append(AuditTrail.user_id == user_id)
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

        # Count of unique resources that were updated
        unique_updated_resources_stmt = (
            select(func.count(func.distinct(AuditTrail.resource_id)))
            .select_from(AuditTrail)
            .where(AuditTrail.action == AuditActionEnum.UPDATE)
            .where(AuditTrail.resource_id.isnot(None))
        )
        if where_clause is not None:
            unique_updated_resources_stmt = unique_updated_resources_stmt.where(where_clause)
        unique_resources_updated = self.execute_scalar(unique_updated_resources_stmt) or 0

        # Count of failure events
        # Failure events are those with action ending in _FAILED or details containing success=false
        failure_actions = [
            AuditActionEnum.LOGIN_FAILED,
            AuditActionEnum.WORKFLOW_FAILED,
            AuditActionEnum.ACCESS_DENIED,
        ]

        failure_conditions = [
            AuditTrail.action.in_(failure_actions),
            AuditTrail.details.op("->>")("success") == "false",
        ]

        failure_stmt = select(func.count()).select_from(AuditTrail).where(or_(*failure_conditions))
        if where_clause is not None:
            failure_stmt = failure_stmt.where(where_clause)
        failure_events_count = self.execute_scalar(failure_stmt) or 0

        return {
            "total_records": total_records,
            "unique_users": unique_users,
            "unique_resources_updated": unique_resources_updated,
            "failure_events_count": failure_events_count,
            "most_common_actions": most_common_actions,
            "most_active_users": most_active_users,
            "date_range": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
        }
