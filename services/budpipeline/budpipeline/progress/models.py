"""Progress event models for budpipeline.

This module contains the ProgressEvent entity for tracking pipeline progress
events and time-series analysis (002-pipeline-event-persistence - T008).
"""

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship  # type: ignore[attr-defined]

from budpipeline.commons.database import Base

if TYPE_CHECKING:
    from budpipeline.pipeline.models import PipelineExecution


class EventType(str, enum.Enum):
    """Progress event type values."""

    WORKFLOW_PROGRESS = "workflow_progress"
    STEP_COMPLETED = "step_completed"
    ETA_UPDATE = "eta_update"
    WORKFLOW_COMPLETED = "workflow_completed"


class ProgressEvent(Base):
    """Represents a progress update event during execution.

    Enables time-series analysis of pipeline progression and supports
    event-driven notifications to subscribers (FR-007, FR-012).
    """

    __tablename__ = "progress_event"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique event identifier",
    )

    # Foreign key to parent execution
    execution_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("pipeline_execution.id", ondelete="CASCADE"),
        nullable=False,
        comment="Parent execution reference",
    )

    # Event type
    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType, name="event_type", native_enum=False),
        nullable=False,
        comment="Type of progress event",
    )

    # Progress
    progress_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="Progress at event time (0.00-100.00)",
    )

    # ETA
    eta_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Estimated time to completion (seconds)",
    )

    # Current step description
    current_step_desc: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Description of current step (max 500 chars)",
    )

    # Additional event metadata
    event_details: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional event metadata, free-form JSON",
    )

    # Event timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Event occurrence time, immutable and indexed",
    )

    # Sequence number for ordering
    sequence_number: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Event sequence for ordering, auto-incremented and monotonic",
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
        back_populates="progress_events",
    )

    # Table constraints and indexes
    __table_args__ = (
        CheckConstraint(
            "progress_percentage >= 0.00 AND progress_percentage <= 100.00",
            name="ck_progress_event_progress_range",
        ),
        CheckConstraint(
            "eta_seconds IS NULL OR eta_seconds >= 0",
            name="ck_progress_event_eta_positive",
        ),
        # Query events by execution in chronological order (FR-007)
        Index(
            "idx_progress_event_execution_time",
            "execution_id",
            "timestamp",
            postgresql_using="btree",
        ),
        # Query events by type for analytics
        Index("idx_progress_event_type", "execution_id", "event_type"),
        # Sequence ordering for out-of-order handling
        Index("idx_progress_event_sequence", "execution_id", "sequence_number"),
    )

    def __repr__(self) -> str:
        return f"<ProgressEvent(id={self.id}, type={self.event_type}, progress={self.progress_percentage}%)>"
