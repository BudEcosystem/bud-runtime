"""Business logic for audit trail functionality.

This module provides high-level service methods for working with audit trails,
including helper methods for different types of auditing scenarios.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from budapp.audit_ops.crud import AuditTrailDataManager
from budapp.audit_ops.hash_utils import verify_audit_hash, verify_audit_integrity
from budapp.audit_ops.models import AuditTrail
from budapp.audit_ops.schemas import (
    AuditRecordCreate,
    AuditRecordEntry,
    AuditRecordFilter,
)
from budapp.commons.constants import AuditActionEnum, AuditResourceTypeEnum


class AuditService:
    """Service class for audit trail operations.

    Provides high-level methods for creating and querying audit records,
    with specific methods for different auditing scenarios.
    """

    def __init__(self, session: Session):
        """Initialize the audit service.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.data_manager = AuditTrailDataManager(session)

    def create_audit_record(
        self,
        audit_data: AuditRecordCreate,
    ) -> AuditTrail:
        """Create a new audit record from schema data.

        Args:
            audit_data: Pydantic schema with audit record data

        Returns:
            Created audit trail record
        """
        return self.data_manager.create_audit_record(
            action=audit_data.action,
            resource_type=audit_data.resource_type,
            resource_id=audit_data.resource_id,
            user_id=audit_data.user_id,
            actioned_by=audit_data.actioned_by,
            details=audit_data.details,
            ip_address=audit_data.ip_address,
            timestamp=audit_data.timestamp or datetime.now(timezone.utc),
            previous_state=audit_data.previous_state,
            new_state=audit_data.new_state,
        )

    def audit_create(
        self,
        resource_type: AuditResourceTypeEnum,
        resource_id: UUID,
        resource_data: Dict[str, Any],
        user_id: Optional[UUID] = None,
        actioned_by: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        additional_details: Optional[Dict[str, Any]] = None,
    ) -> AuditTrail:
        """Audit a resource creation action.

        Args:
            resource_type: Type of resource created
            resource_id: ID of the created resource
            resource_data: Data of the created resource
            user_id: ID of the user who created the resource
            actioned_by: ID of the admin/user who performed the action on behalf of another user
            ip_address: IP address from which the action was performed
            additional_details: Any additional context to include

        Returns:
            Created audit trail record
        """
        details = {"operation": "create"}
        if additional_details:
            details.update(additional_details)

        return self.data_manager.create_audit_record(
            action=AuditActionEnum.CREATE,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            actioned_by=actioned_by,
            details=details,
            ip_address=ip_address,
            new_state=resource_data,
        )

    def audit_update(
        self,
        resource_type: AuditResourceTypeEnum,
        resource_id: UUID,
        previous_data: Dict[str, Any],
        new_data: Dict[str, Any],
        user_id: Optional[UUID] = None,
        actioned_by: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        additional_details: Optional[Dict[str, Any]] = None,
    ) -> AuditTrail:
        """Audit a resource update action.

        Args:
            resource_type: Type of resource updated
            resource_id: ID of the updated resource
            previous_data: Data before the update
            new_data: Data after the update
            user_id: ID of the user who updated the resource
            actioned_by: ID of the admin/user who performed the action on behalf of another user
            ip_address: IP address from which the action was performed
            additional_details: Any additional context to include

        Returns:
            Created audit trail record
        """
        # Calculate what fields changed
        changed_fields = self._calculate_changes(previous_data, new_data)

        details = {
            "operation": "update",
            "changed_fields": list(changed_fields.keys()),
            "changes": changed_fields,
        }
        if additional_details:
            details.update(additional_details)

        return self.data_manager.create_audit_record(
            action=AuditActionEnum.UPDATE,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            actioned_by=actioned_by,
            details=details,
            ip_address=ip_address,
            previous_state=previous_data,
            new_state=new_data,
        )

    def audit_delete(
        self,
        resource_type: AuditResourceTypeEnum,
        resource_id: UUID,
        resource_data: Dict[str, Any],
        user_id: Optional[UUID] = None,
        actioned_by: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        additional_details: Optional[Dict[str, Any]] = None,
    ) -> AuditTrail:
        """Audit a resource deletion action.

        Args:
            resource_type: Type of resource deleted
            resource_id: ID of the deleted resource
            resource_data: Data of the deleted resource
            user_id: ID of the user who deleted the resource
            actioned_by: ID of the admin/user who performed the action on behalf of another user
            ip_address: IP address from which the action was performed
            additional_details: Any additional context to include

        Returns:
            Created audit trail record
        """
        details = {"operation": "delete"}
        if additional_details:
            details.update(additional_details)

        return self.data_manager.create_audit_record(
            action=AuditActionEnum.DELETE,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            actioned_by=actioned_by,
            details=details,
            ip_address=ip_address,
            previous_state=resource_data,
        )

    def audit_access(
        self,
        resource_type: AuditResourceTypeEnum,
        resource_id: UUID,
        access_type: str,
        granted: bool,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> AuditTrail:
        """Audit a resource access attempt.

        Args:
            resource_type: Type of resource accessed
            resource_id: ID of the resource
            access_type: Type of access (read, write, execute, etc.)
            granted: Whether access was granted or denied
            user_id: ID of the user who attempted access
            ip_address: IP address from which the action was performed
            reason: Reason for granting/denying access

        Returns:
            Created audit trail record
        """
        action = AuditActionEnum.ACCESS_GRANTED if granted else AuditActionEnum.ACCESS_DENIED

        details = {
            "access_type": access_type,
            "granted": granted,
        }
        if reason:
            details["reason"] = reason

        return self.data_manager.create_audit_record(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            details=details,
            ip_address=ip_address,
        )

    def audit_authentication(
        self,
        action: AuditActionEnum,
        user_id: Optional[UUID] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        success: bool = True,
        reason: Optional[str] = None,
    ) -> AuditTrail:
        """Audit an authentication event.

        Args:
            action: Authentication action (login, logout, etc.)
            user_id: ID of the user (if known)
            username: Username attempted (for failed logins)
            ip_address: IP address from which the action was performed
            success: Whether the authentication was successful
            reason: Reason for failure (if applicable)

        Returns:
            Created audit trail record
        """
        details = {
            "success": success,
        }
        if username:
            details["username"] = username
        if reason:
            details["reason"] = reason

        return self.data_manager.create_audit_record(
            action=action,
            resource_type=AuditResourceTypeEnum.SESSION,
            user_id=user_id,
            details=details,
            ip_address=ip_address,
        )

    def audit_workflow(
        self,
        workflow_id: UUID,
        workflow_type: str,
        action: AuditActionEnum,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        status: Optional[str] = None,
        error: Optional[str] = None,
    ) -> AuditTrail:
        """Audit a workflow event.

        Args:
            workflow_id: ID of the workflow
            workflow_type: Type of workflow
            action: Workflow action (started, completed, failed)
            user_id: ID of the user who initiated the workflow
            ip_address: IP address from which the action was performed
            status: Current workflow status
            error: Error message if workflow failed

        Returns:
            Created audit trail record
        """
        details = {
            "workflow_type": workflow_type,
        }
        if status:
            details["status"] = status
        if error:
            details["error"] = error

        return self.data_manager.create_audit_record(
            action=action,
            resource_type=AuditResourceTypeEnum.WORKFLOW,
            resource_id=workflow_id,
            user_id=user_id,
            details=details,
            ip_address=ip_address,
        )

    def get_audit_records(
        self,
        filter_params: AuditRecordFilter,
        offset: int = 0,
        limit: int = 20,
    ) -> Tuple[List[AuditRecordEntry], int]:
        """Get audit records based on filter parameters.

        Args:
            filter_params: Filter parameters for querying
            offset: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (list of audit record entries, total count)
        """
        # Use the consolidated get_audit_records method with all filters
        records, total = self.data_manager.get_audit_records(
            user_id=filter_params.user_id,
            actioned_by=filter_params.actioned_by,
            action=filter_params.action,
            resource_type=filter_params.resource_type,
            resource_id=filter_params.resource_id,
            start_date=filter_params.start_date,
            end_date=filter_params.end_date,
            ip_address=filter_params.ip_address,
            offset=offset,
            limit=limit,
            include_user=True,
        )

        # Convert to response schemas
        entries = []
        for record in records:
            entry = AuditRecordEntry.model_validate(record)
            # Add user information if available
            if record.user:
                entry.user_email = record.user.email
                entry.user_name = record.user.name
            # Add actioned_by user information if available
            if record.actioned_by_user:
                entry.actioned_by_email = record.actioned_by_user.email
                entry.actioned_by_name = record.actioned_by_user.name
            entries.append(entry)

        return entries, total

    def get_audit_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Get summary statistics for audit records.

        Args:
            start_date: Start date for filtering
            end_date: End date for filtering
            user_id: User ID for filtering (optional, for CLIENT users)

        Returns:
            Dictionary containing summary statistics
        """
        return self.data_manager.get_audit_summary(
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
        )

    def _calculate_changes(
        self,
        previous_data: Dict[str, Any],
        new_data: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """Calculate the differences between two data dictionaries.

        Args:
            previous_data: Data before changes
            new_data: Data after changes

        Returns:
            Dictionary of changed fields with old and new values
        """
        changes = {}

        # Check for modified and added fields
        for key, new_value in new_data.items():
            if key not in previous_data:
                changes[key] = {"old": None, "new": new_value}
            elif previous_data[key] != new_value:
                changes[key] = {"old": previous_data[key], "new": new_value}

        # Check for removed fields
        for key, old_value in previous_data.items():
            if key not in new_data:
                changes[key] = {"old": old_value, "new": None}

        return changes

    def _sanitize_sensitive_data(
        self,
        data: Dict[str, Any],
        sensitive_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Remove or mask sensitive data before storing in audit logs.

        Args:
            data: Data to sanitize
            sensitive_fields: List of field names to mask

        Returns:
            Sanitized data dictionary
        """
        if not sensitive_fields:
            sensitive_fields = ["password", "secret", "token", "api_key", "private_key", "credential", "auth"]

        sanitized = {}
        for key, value in data.items():
            # Check if field name contains sensitive keywords
            is_sensitive = any(sensitive_word in key.lower() for sensitive_word in sensitive_fields)

            if is_sensitive:
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                # Recursively sanitize nested dictionaries
                sanitized[key] = self._sanitize_sensitive_data(value, sensitive_fields)
            else:
                sanitized[key] = value

        return sanitized

    def verify_audit_record_integrity(self, audit_id: UUID) -> Tuple[bool, str]:
        """Verify the integrity of an audit record using its hash.

        Args:
            audit_id: ID of the audit record to verify

        Returns:
            Tuple of (is_valid, message) indicating verification status
        """
        record = self.data_manager.get_audit_record_by_id(audit_id)
        if not record:
            return False, f"Audit record with ID {audit_id} not found"

        return verify_audit_integrity(record)

    def verify_batch_integrity(
        self,
        audit_ids: List[UUID],
    ) -> Dict[UUID, Tuple[bool, str]]:
        """Verify the integrity of multiple audit records.

        Args:
            audit_ids: List of audit record IDs to verify

        Returns:
            Dictionary mapping audit IDs to verification results
        """
        results = {}
        for audit_id in audit_ids:
            is_valid, message = self.verify_audit_record_integrity(audit_id)
            results[audit_id] = (is_valid, message)

        return results

    def find_tampered_records(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Find audit records that may have been tampered with.

        Args:
            start_date: Start date for search range
            end_date: End date for search range
            limit: Maximum number of records to check

        Returns:
            List of potentially tampered records with details
        """
        # Get records to check
        filter_params = AuditRecordFilter(
            start_date=start_date,
            end_date=end_date,
        )

        records, _ = self.get_audit_records(
            filter_params=filter_params,
            offset=0,
            limit=limit,
        )

        tampered = []
        for record in records:
            audit_record = self.data_manager.get_audit_record_by_id(record.id)
            is_valid, message = verify_audit_integrity(audit_record)

            if not is_valid:
                tampered.append(
                    {
                        "id": str(record.id),
                        "timestamp": record.timestamp.isoformat(),
                        "action": record.action,
                        "resource_type": record.resource_type,
                        "resource_id": str(record.resource_id) if record.resource_id else None,
                        "user_id": str(record.user_id) if record.user_id else None,
                        "verification_message": message,
                    }
                )

        return tampered
