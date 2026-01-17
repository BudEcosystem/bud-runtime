"""Add event-driven completion tracking columns to step_execution.

Revision ID: 004_event_driven_completion
Revises: 003_fix_delivery_status_constraint
Create Date: 2026-01-17 10:00:00.000000

This migration adds columns to support event-driven completion tracking:
- awaiting_event: Boolean flag for steps waiting on external events
- external_workflow_id: Correlation ID for routing events to steps
- handler_type: Handler type for event routing
- timeout_at: When the step should timeout

Also adds TIMEOUT to the step_status enum.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "004_event_driven_completion"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add event-driven completion tracking columns and indexes."""

    # Note: TIMEOUT value for step status is already supported since status
    # is stored as VARCHAR(20), not a PostgreSQL enum. The Python enum in
    # models.py handles validation.

    # Add new columns to step_execution table
    op.add_column(
        "step_execution",
        sa.Column(
            "awaiting_event",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="True if step is waiting for external event to complete",
        ),
    )

    op.add_column(
        "step_execution",
        sa.Column(
            "external_workflow_id",
            sa.String(255),
            nullable=True,
            comment="External workflow ID for event correlation (e.g., budapp workflow ID)",
        ),
    )

    op.add_column(
        "step_execution",
        sa.Column(
            "handler_type",
            sa.String(255),
            nullable=True,
            comment="Handler type for routing events to correct handler",
        ),
    )

    op.add_column(
        "step_execution",
        sa.Column(
            "timeout_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When this step should timeout if still awaiting event",
        ),
    )

    # Create indexes for efficient event routing and timeout queries
    op.create_index(
        "idx_step_execution_external_workflow",
        "step_execution",
        ["external_workflow_id", "status"],
        postgresql_where=sa.text("external_workflow_id IS NOT NULL"),
    )

    op.create_index(
        "idx_step_execution_timeout",
        "step_execution",
        ["status", "timeout_at"],
        postgresql_where=sa.text("awaiting_event = true AND timeout_at IS NOT NULL"),
    )


def downgrade() -> None:
    """Remove event-driven completion tracking columns and indexes."""

    # Drop indexes first
    op.drop_index("idx_step_execution_timeout", table_name="step_execution")
    op.drop_index("idx_step_execution_external_workflow", table_name="step_execution")

    # Drop columns
    op.drop_column("step_execution", "timeout_at")
    op.drop_column("step_execution", "handler_type")
    op.drop_column("step_execution", "external_workflow_id")
    op.drop_column("step_execution", "awaiting_event")
