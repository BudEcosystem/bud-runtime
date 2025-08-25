"""SQLAlchemy models for audit trail functionality.

This module defines the database models for tracking audit events
and user actions throughout the system for compliance and security purposes.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budapp.commons.database import Base, TimestampMixin


class AuditTrail(Base, TimestampMixin):
    """Model for tracking all audit events and user actions in the system.

    This table is designed to be immutable - records should only be created,
    never updated or deleted. Database constraints enforce this requirement.

    Attributes:
        id: Unique identifier for the audit record
        user_id: ID of the user who performed the action (nullable for system actions)
        actioned_by: ID of the admin/user who performed the action on behalf of another user
        action: Type of action performed (from AuditActionEnum)
        resource_type: Type of resource affected (from AuditResourceTypeEnum)
        resource_id: ID of the affected resource
        resource_name: Name of the affected resource for display and search
        timestamp: When the action occurred
        details: Additional context about the action in JSON format
        ip_address: IP address from which the action was performed
        previous_state: State of the resource before the action (for updates)
        new_state: State of the resource after the action (for creates/updates)
        record_hash: SHA256 hash of record data for integrity verification
        created_at: When the audit record was created (from TimestampMixin)
        modified_at: When the audit record was last modified (from TimestampMixin)
    """

    __tablename__ = "audit_trail"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid4, comment="Unique identifier for the audit record"
    )

    # User who performed the action (nullable for system actions)
    user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="ID of the user who performed the action",
    )

    # User on whose behalf the action was performed (for admin actions)
    actioned_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="ID of the admin/user who performed the action on behalf of another user",
    )

    # Action details
    action: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="Type of action performed (e.g., create, update, delete)"
    )

    # Resource information
    resource_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="Type of resource affected (e.g., project, model, endpoint)"
    )

    resource_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid, nullable=True, index=True, comment="ID of the affected resource"
    )

    resource_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True, comment="Name of the affected resource for display and search"
    )

    # Timestamp when the action occurred
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="When the action occurred",
    )

    # Additional context
    details: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="Additional context about the action in JSON format"
    )

    # Request information
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # Supports both IPv4 and IPv6
        nullable=True,
        comment="IP address from which the action was performed",
    )

    # State tracking for changes
    previous_state: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="State of the resource before the action (for updates)"
    )

    new_state: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="State of the resource after the action (for creates/updates)"
    )

    # Data integrity hash - SHA256 hash of record fields for tamper detection
    record_hash: Mapped[str] = mapped_column(
        String(64),  # SHA256 produces 64 character hex string
        nullable=False,
        index=True,
        comment="SHA256 hash of record data for integrity verification",
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id], lazy="select")

    actioned_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[actioned_by], lazy="select")

    def __repr__(self) -> str:
        """String representation of the audit record."""
        return (
            f"<AuditTrail(id={self.id}, action={self.action}, "
            f"resource_type={self.resource_type}, resource_id={self.resource_id}, "
            f"resource_name={self.resource_name}, user_id={self.user_id}, "
            f"actioned_by={self.actioned_by}, timestamp={self.timestamp})>"
        )


# Event listener to prevent updates to audit records
@event.listens_for(AuditTrail, "before_update", propagate=True)
def receive_before_update(mapper, connection, target):
    """Prevent updates to audit trail records.

    Audit trail records should be immutable. This event listener
    raises an exception if an update is attempted.
    """
    raise ValueError("Audit trail records cannot be updated. They are immutable.")
