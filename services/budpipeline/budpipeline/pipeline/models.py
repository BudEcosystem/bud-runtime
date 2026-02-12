"""Pipeline execution models for budpipeline.

This module contains the PipelineDefinition, PipelineExecution, and StepExecution
entities with optimistic locking for concurrent update handling
(002-pipeline-event-persistence - T006, T007).
"""

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship  # type: ignore[attr-defined]

from budpipeline.commons.database import Base

if TYPE_CHECKING:
    from budpipeline.progress.models import ProgressEvent
    from budpipeline.subscriptions.models import ExecutionSubscription


class PipelineStatus(str, enum.Enum):
    """Pipeline definition status values."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ExecutionStatus(str, enum.Enum):
    """Pipeline execution status values."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"


class StepStatus(str, enum.Enum):
    """Step execution status values."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    RETRYING = "RETRYING"
    TIMEOUT = "TIMEOUT"  # Step timed out waiting for external event


class PipelineDefinition(Base):
    """Represents a pipeline definition (workflow DAG).

    Stores the persistent pipeline/workflow configuration that can be executed multiple times.
    Replaces in-memory WorkflowStorage with durable persistence.
    Uses optimistic locking via version_id_col for concurrent update handling.
    """

    __tablename__ = "pipeline_definition"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique pipeline identifier",
    )

    # Optimistic locking version
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Optimistic locking version, incremented on each update",
    )

    # Pipeline metadata
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable pipeline name",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional pipeline description",
    )
    icon: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Optional icon/emoji for UI representation",
    )

    # DAG definition
    dag_definition: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Complete pipeline DAG definition with steps, parameters, outputs",
    )

    # Status
    status: Mapped[PipelineStatus] = mapped_column(
        Enum(PipelineStatus, name="pipeline_status", native_enum=False),
        nullable=False,
        default=PipelineStatus.DRAFT,
        comment="Current pipeline status (draft, active, archived)",
    )

    # User isolation
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="UUID of the owning user (null for system or legacy pipelines)",
    )
    system_owned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if this is a system-owned pipeline visible to all users",
    )

    # Metadata
    step_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of steps in the pipeline DAG",
    )
    created_by: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="User or service that created the pipeline",
    )

    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Record creation time, immutable",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="Last update time, auto-updated on modification",
    )

    # Relationships
    executions: Mapped[list["PipelineExecution"]] = relationship(
        "PipelineExecution",
        back_populates="pipeline",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Optimistic locking configuration
    __mapper_args__ = {"version_id_col": version}

    # Table constraints and indexes
    __table_args__ = (
        CheckConstraint(
            "step_count >= 0",
            name="ck_pipeline_definition_step_count",
        ),
        # Query by name for lookup
        Index("idx_pipeline_definition_name", "name"),
        # Query by status for filtering
        Index("idx_pipeline_definition_status", "status"),
        # Query by creator for filtering
        Index("idx_pipeline_definition_created_by", "created_by"),
        # Query by date for sorting
        Index("idx_pipeline_definition_created_at", "created_at", postgresql_using="btree"),
        # Query by user_id for user isolation (partial index for non-null values)
        Index(
            "idx_pipeline_definition_user_id",
            "user_id",
            postgresql_where="user_id IS NOT NULL",
        ),
    )

    def __repr__(self) -> str:
        return f"<PipelineDefinition(id={self.id}, name={self.name}, status={self.status})>"


class PipelineExecution(Base):
    """Represents a single execution instance of a pipeline DAG.

    Uses optimistic locking via version_id_col to handle concurrent updates
    from multiple services while maintaining eventual consistency (FR-005a).
    """

    __tablename__ = "pipeline_execution"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique execution identifier",
    )

    # Optimistic locking version
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Optimistic locking version, incremented on each update",
    )

    # Foreign key to pipeline definition (optional for backwards compatibility)
    pipeline_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("pipeline_definition.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to parent pipeline definition (optional for legacy executions)",
    )

    # Pipeline definition (snapshot at time of execution)
    pipeline_definition: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Complete pipeline DAG definition with nodes/edges (snapshot for history)",
    )

    # Initiator
    initiator: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="User or service that initiated execution",
    )

    # Timestamps
    start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Execution start timestamp, set when status → RUNNING",
    )
    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Execution end timestamp, set when status → COMPLETED/FAILED/INTERRUPTED",
    )

    # Status
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus, name="execution_status", native_enum=False),
        nullable=False,
        default=ExecutionStatus.PENDING,
        comment="Current execution status",
    )

    # Progress
    progress_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Overall progress (0.00-100.00), monotonically increasing",
    )

    # Outputs and errors
    final_outputs: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Results from completed execution",
    )
    error_info: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Error details if failed (error_type, message, stack_trace)",
    )

    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Record creation time, immutable",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="Last update time, auto-updated on modification",
    )

    # Relationships
    pipeline: Mapped["PipelineDefinition | None"] = relationship(
        "PipelineDefinition",
        back_populates="executions",
    )
    steps: Mapped[list["StepExecution"]] = relationship(
        "StepExecution",
        back_populates="execution",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    progress_events: Mapped[list["ProgressEvent"]] = relationship(
        "ProgressEvent",
        back_populates="execution",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    subscriptions: Mapped[list["ExecutionSubscription"]] = relationship(
        "ExecutionSubscription",
        back_populates="execution",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Optimistic locking configuration
    __mapper_args__ = {"version_id_col": version}

    # Table constraints and indexes
    __table_args__ = (
        CheckConstraint(
            "progress_percentage >= 0.00 AND progress_percentage <= 100.00",
            name="ck_pipeline_execution_progress_range",
        ),
        # Query by pipeline_id for filtering executions by pipeline
        Index("idx_pipeline_execution_pipeline_id", "pipeline_id"),
        # Query by status for filtering (FR-008)
        Index("idx_pipeline_execution_status", "status"),
        # Query by initiator for filtering (FR-008)
        Index("idx_pipeline_execution_initiator", "initiator"),
        # Query by date range for historical queries (FR-008, SC-006)
        Index("idx_pipeline_execution_created_at", "created_at", postgresql_using="btree"),
        # Compound index for cleanup job (FR-048)
        Index(
            "idx_pipeline_execution_cleanup",
            "created_at",
            "status",
            postgresql_where="status IN ('COMPLETED', 'FAILED', 'INTERRUPTED')",
        ),
    )

    def __repr__(self) -> str:
        return f"<PipelineExecution(id={self.id}, status={self.status}, progress={self.progress_percentage}%)>"


class StepExecution(Base):
    """Represents execution state of a single step within a pipeline.

    Uses optimistic locking via version_id_col to handle concurrent updates.
    Includes retry tracking and sequence ordering (FR-005a).
    """

    __tablename__ = "step_execution"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique step execution identifier",
    )

    # Foreign key to parent execution
    execution_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("pipeline_execution.id", ondelete="CASCADE"),
        nullable=False,
        comment="Parent execution reference",
    )

    # Optimistic locking version
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Optimistic locking version, incremented on each update",
    )

    # Step identification
    step_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Step identifier from pipeline definition",
    )
    step_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable step name",
    )

    # Status
    status: Mapped[StepStatus] = mapped_column(
        Enum(StepStatus, name="step_status", native_enum=False),
        nullable=False,
        default=StepStatus.PENDING,
        comment="Current step status",
    )

    # Timestamps
    start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Step start timestamp, set when status → RUNNING",
    )
    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Step end timestamp, set when status → COMPLETED/FAILED/SKIPPED",
    )

    # Progress
    progress_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Step-level progress (0.00-100.00)",
    )

    # Outputs and errors
    outputs: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Step output data, sanitized to remove credentials (FR-039)",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error description if failed, sanitized to remove sensitive data",
    )

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of retry attempts",
    )

    # Sequence ordering
    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Execution order within pipeline, determines dependency resolution",
    )

    # Event-driven completion tracking (event-driven-completion architecture)
    awaiting_event: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if step is waiting for external event to complete",
    )
    external_workflow_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="External workflow ID for event correlation (e.g., budapp workflow ID)",
    )
    handler_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Handler type for routing events to correct handler",
    )
    timeout_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When this step should timeout if still awaiting event",
    )

    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Record creation time, immutable",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="Last update time, auto-updated on modification",
    )

    # Relationships
    execution: Mapped["PipelineExecution"] = relationship(
        "PipelineExecution",
        back_populates="steps",
    )

    # Optimistic locking configuration
    __mapper_args__ = {"version_id_col": version}

    # Table constraints and indexes
    __table_args__ = (
        CheckConstraint(
            "progress_percentage >= 0.00 AND progress_percentage <= 100.00",
            name="ck_step_execution_progress_range",
        ),
        CheckConstraint(
            "retry_count >= 0",
            name="ck_step_execution_retry_count",
        ),
        CheckConstraint(
            "sequence_number > 0",
            name="ck_step_execution_sequence_number",
        ),
        # Unique constraint for step_id within execution
        UniqueConstraint("execution_id", "step_id", name="uq_step_execution_step_id"),
        # Query steps by execution (FR-007)
        Index("idx_step_execution_execution_id", "execution_id"),
        # Order steps by sequence (FR-007)
        Index("idx_step_execution_sequence", "execution_id", "sequence_number"),
        # Query by status for progress aggregation (FR-016)
        Index("idx_step_execution_status", "execution_id", "status"),
        # Event-driven completion tracking indexes
        Index(
            "idx_step_execution_external_workflow",
            "external_workflow_id",
            "status",
            postgresql_where="external_workflow_id IS NOT NULL",
        ),
        Index(
            "idx_step_execution_timeout",
            "status",
            "timeout_at",
            postgresql_where="awaiting_event = true AND timeout_at IS NOT NULL",
        ),
    )

    def __repr__(self) -> str:
        return f"<StepExecution(id={self.id}, step_id={self.step_id}, status={self.status})>"
