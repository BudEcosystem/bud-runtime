"""Subscription models for budpipeline.

This module contains the ExecutionSubscription entity for callback topics
and pub/sub subscriptions (002-pipeline-event-persistence - T009).
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship  # type: ignore[attr-defined]

from budpipeline.commons.database import Base

if TYPE_CHECKING:
    from budpipeline.pipeline.models import PipelineExecution


class DeliveryStatus(str, enum.Enum):
    """Subscription delivery status values."""

    ACTIVE = "active"
    EXPIRED = "expired"
    FAILED = "failed"


class ExecutionSubscription(Base):
    """Represents a client's subscription to execution events via pub/sub.

    Enables callback topic registration for real-time event delivery
    to subscribing services (FR-011, FR-013, FR-022).
    """

    __tablename__ = "execution_subscription"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique subscription identifier",
    )

    # Foreign key to parent execution
    execution_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("pipeline_execution.id", ondelete="CASCADE"),
        nullable=False,
        comment="Parent execution reference",
    )

    # Callback topic
    callback_topic: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Dapr pub/sub topic name, validated via Dapr (FR-022)",
    )

    # Subscription timestamps
    subscription_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When subscription created, immutable",
    )
    expiry_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When subscription expires (NULL = no expiry)",
    )

    # Delivery status
    delivery_status: Mapped[DeliveryStatus] = mapped_column(
        Enum(DeliveryStatus, name="delivery_status", native_enum=False),
        nullable=False,
        default=DeliveryStatus.ACTIVE,
        comment="Current subscription status",
    )

    # Audit timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Record creation time, immutable",
    )

    # Relationships
    execution: Mapped["PipelineExecution"] = relationship(
        "PipelineExecution",
        back_populates="subscriptions",
    )

    # Table constraints and indexes
    __table_args__ = (
        CheckConstraint(
            "expiry_time IS NULL OR expiry_time > subscription_time",
            name="ck_execution_subscription_expiry",
        ),
        # Unique constraint for execution + callback_topic
        UniqueConstraint(
            "execution_id",
            "callback_topic",
            name="uq_execution_subscription_topic",
        ),
        # Query subscriptions by execution (FR-013)
        Index("idx_execution_subscription_execution", "execution_id"),
        # Query active subscriptions for event publishing
        Index(
            "idx_execution_subscription_active",
            "execution_id",
            "delivery_status",
            postgresql_where="delivery_status = 'active'",
        ),
        # Cleanup expired subscriptions
        Index(
            "idx_execution_subscription_expiry",
            "expiry_time",
            postgresql_where="expiry_time IS NOT NULL",
        ),
    )

    def __repr__(self) -> str:
        return f"<ExecutionSubscription(id={self.id}, topic={self.callback_topic}, status={self.delivery_status})>"
