"""Add pipeline persistence tables.

Revision ID: 001
Revises:
Create Date: 2026-01-16 12:00:00.000000

Creates tables for pipeline event persistence feature (002-pipeline-event-persistence):
- pipeline_execution: Main execution records with optimistic locking
- step_execution: Individual step records with retry tracking
- progress_event: Progress update events for time-series analysis
- execution_subscription: Pub/sub callback topic subscriptions
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create pipeline persistence tables with indexes."""
    # Create pipeline_execution table
    op.create_table(
        "pipeline_execution",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Unique execution identifier",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
            comment="Optimistic locking version, incremented on each update",
        ),
        sa.Column(
            "pipeline_definition",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Complete pipeline DAG definition with nodes/edges",
        ),
        sa.Column(
            "initiator",
            sa.String(255),
            nullable=False,
            comment="User or service that initiated execution",
        ),
        sa.Column(
            "start_time",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Execution start timestamp, set when status → RUNNING",
        ),
        sa.Column(
            "end_time",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Execution end timestamp, set when status → COMPLETED/FAILED/INTERRUPTED",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="PENDING",
            comment="Current execution status",
        ),
        sa.Column(
            "progress_percentage",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0.00",
            comment="Overall progress (0.00-100.00), monotonically increasing",
        ),
        sa.Column(
            "final_outputs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Results from completed execution",
        ),
        sa.Column(
            "error_info",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Error details if failed (error_type, message, stack_trace)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Record creation time, immutable",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Last update time, auto-updated on modification",
        ),
        sa.CheckConstraint(
            "progress_percentage >= 0.00 AND progress_percentage <= 100.00",
            name="ck_pipeline_execution_progress_range",
        ),
    )

    # Create indexes for pipeline_execution
    op.create_index(
        "idx_pipeline_execution_status",
        "pipeline_execution",
        ["status"],
    )
    op.create_index(
        "idx_pipeline_execution_initiator",
        "pipeline_execution",
        ["initiator"],
    )
    op.create_index(
        "idx_pipeline_execution_created_at",
        "pipeline_execution",
        [sa.text("created_at DESC")],
    )
    # Partial index for cleanup job
    op.execute(
        """
        CREATE INDEX idx_pipeline_execution_cleanup
        ON pipeline_execution (created_at, status)
        WHERE status IN ('COMPLETED', 'FAILED', 'INTERRUPTED')
        """
    )

    # Create step_execution table
    op.create_table(
        "step_execution",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Unique step execution identifier",
        ),
        sa.Column(
            "execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_execution.id", ondelete="CASCADE"),
            nullable=False,
            comment="Parent execution reference",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
            comment="Optimistic locking version, incremented on each update",
        ),
        sa.Column(
            "step_id",
            sa.String(255),
            nullable=False,
            comment="Step identifier from pipeline definition",
        ),
        sa.Column(
            "step_name",
            sa.String(255),
            nullable=False,
            comment="Human-readable step name",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="PENDING",
            comment="Current step status",
        ),
        sa.Column(
            "start_time",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Step start timestamp, set when status → RUNNING",
        ),
        sa.Column(
            "end_time",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Step end timestamp, set when status → COMPLETED/FAILED/SKIPPED",
        ),
        sa.Column(
            "progress_percentage",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0.00",
            comment="Step-level progress (0.00-100.00)",
        ),
        sa.Column(
            "outputs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Step output data, sanitized to remove credentials (FR-039)",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
            comment="Error description if failed, sanitized to remove sensitive data",
        ),
        sa.Column(
            "retry_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Number of retry attempts",
        ),
        sa.Column(
            "sequence_number",
            sa.Integer(),
            nullable=False,
            comment="Execution order within pipeline, determines dependency resolution",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Record creation time, immutable",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Last update time, auto-updated on modification",
        ),
        sa.CheckConstraint(
            "progress_percentage >= 0.00 AND progress_percentage <= 100.00",
            name="ck_step_execution_progress_range",
        ),
        sa.CheckConstraint("retry_count >= 0", name="ck_step_execution_retry_count"),
        sa.CheckConstraint("sequence_number > 0", name="ck_step_execution_sequence_number"),
        sa.UniqueConstraint("execution_id", "step_id", name="uq_step_execution_step_id"),
    )

    # Create indexes for step_execution
    op.create_index(
        "idx_step_execution_execution_id",
        "step_execution",
        ["execution_id"],
    )
    op.create_index(
        "idx_step_execution_sequence",
        "step_execution",
        ["execution_id", "sequence_number"],
    )
    op.create_index(
        "idx_step_execution_status",
        "step_execution",
        ["execution_id", "status"],
    )

    # Create progress_event table
    op.create_table(
        "progress_event",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Unique event identifier",
        ),
        sa.Column(
            "execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_execution.id", ondelete="CASCADE"),
            nullable=False,
            comment="Parent execution reference",
        ),
        sa.Column(
            "event_type",
            sa.String(50),
            nullable=False,
            comment="Type of progress event",
        ),
        sa.Column(
            "progress_percentage",
            sa.Numeric(5, 2),
            nullable=False,
            comment="Progress at event time (0.00-100.00)",
        ),
        sa.Column(
            "eta_seconds",
            sa.Integer(),
            nullable=True,
            comment="Estimated time to completion (seconds)",
        ),
        sa.Column(
            "current_step_desc",
            sa.String(500),
            nullable=True,
            comment="Description of current step (max 500 chars)",
        ),
        sa.Column(
            "event_details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Additional event metadata, free-form JSON",
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Event occurrence time, immutable and indexed",
        ),
        sa.Column(
            "sequence_number",
            sa.BigInteger(),
            nullable=False,
            comment="Event sequence for ordering, auto-incremented and monotonic",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Record creation time, immutable",
        ),
        sa.CheckConstraint(
            "progress_percentage >= 0.00 AND progress_percentage <= 100.00",
            name="ck_progress_event_progress_range",
        ),
        sa.CheckConstraint(
            "eta_seconds IS NULL OR eta_seconds >= 0",
            name="ck_progress_event_eta_positive",
        ),
        sa.CheckConstraint(
            "event_type IN ('workflow_progress', 'step_completed', 'eta_update', 'workflow_completed')",
            name="chk_progress_event_type",
        ),
    )

    # Create indexes for progress_event
    op.create_index(
        "idx_progress_event_execution_time",
        "progress_event",
        ["execution_id", sa.text("timestamp DESC")],
    )
    op.create_index(
        "idx_progress_event_type",
        "progress_event",
        ["execution_id", "event_type"],
    )
    op.create_index(
        "idx_progress_event_sequence",
        "progress_event",
        ["execution_id", "sequence_number"],
    )

    # Create execution_subscription table
    op.create_table(
        "execution_subscription",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Unique subscription identifier",
        ),
        sa.Column(
            "execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_execution.id", ondelete="CASCADE"),
            nullable=False,
            comment="Parent execution reference",
        ),
        sa.Column(
            "callback_topic",
            sa.String(255),
            nullable=False,
            comment="Dapr pub/sub topic name, validated via Dapr (FR-022)",
        ),
        sa.Column(
            "subscription_time",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="When subscription created, immutable",
        ),
        sa.Column(
            "expiry_time",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When subscription expires (NULL = no expiry)",
        ),
        sa.Column(
            "delivery_status",
            sa.String(20),
            nullable=False,
            server_default="active",
            comment="Current subscription status",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Record creation time, immutable",
        ),
        sa.CheckConstraint(
            "expiry_time IS NULL OR expiry_time > subscription_time",
            name="ck_execution_subscription_expiry",
        ),
        sa.CheckConstraint(
            "delivery_status IN ('active', 'expired', 'failed')",
            name="chk_execution_subscription_status",
        ),
        sa.UniqueConstraint(
            "execution_id", "callback_topic", name="uq_execution_subscription_topic"
        ),
    )

    # Create indexes for execution_subscription
    op.create_index(
        "idx_execution_subscription_execution",
        "execution_subscription",
        ["execution_id"],
    )
    # Partial index for active subscriptions
    op.execute(
        """
        CREATE INDEX idx_execution_subscription_active
        ON execution_subscription (execution_id, delivery_status)
        WHERE delivery_status = 'active'
        """
    )
    # Partial index for expired subscriptions
    op.execute(
        """
        CREATE INDEX idx_execution_subscription_expiry
        ON execution_subscription (expiry_time)
        WHERE expiry_time IS NOT NULL
        """
    )


def downgrade() -> None:
    """Drop pipeline persistence tables in reverse dependency order."""
    op.drop_table("execution_subscription")
    op.drop_table("progress_event")
    op.drop_table("step_execution")
    op.drop_table("pipeline_execution")
