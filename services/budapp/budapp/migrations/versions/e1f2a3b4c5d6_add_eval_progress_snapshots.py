"""add eval_progress_snapshots table

Revision ID: e1f2a3b4c5d6
Revises: # 8a9b463c9646
Create Date: 2025-01-13 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "8a9b463c9646"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create eval_progress_snapshots table."""
    op.create_table(
        "eval_progress_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("total_tasks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_tasks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_tasks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("in_progress_tasks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_percentage", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("time_elapsed_seconds", sa.Integer(), nullable=True),
        sa.Column("time_remaining_seconds", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("current_task", sa.String(length=255), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evaluation_id"], ["evaluations.id"], ondelete="CASCADE"),
    )

    # Create indexes
    op.create_index(
        "idx_eval_progress_experiment_timestamp",
        "eval_progress_snapshots",
        ["experiment_id", "event_timestamp"],
    )
    op.create_index(
        "idx_eval_progress_evaluation_timestamp",
        "eval_progress_snapshots",
        ["evaluation_id", "event_timestamp"],
    )
    op.create_index(
        "idx_eval_progress_event_type_timestamp",
        "eval_progress_snapshots",
        ["event_type", "event_timestamp"],
    )
    op.create_index(
        "idx_eval_progress_status",
        "eval_progress_snapshots",
        ["status"],
    )
    op.create_index(
        "idx_eval_progress_experiment_id",
        "eval_progress_snapshots",
        ["experiment_id"],
    )
    op.create_index(
        "idx_eval_progress_evaluation_id",
        "eval_progress_snapshots",
        ["evaluation_id"],
    )


def downgrade() -> None:
    """Drop eval_progress_snapshots table."""
    op.drop_index("idx_eval_progress_evaluation_id", table_name="eval_progress_snapshots")
    op.drop_index("idx_eval_progress_experiment_id", table_name="eval_progress_snapshots")
    op.drop_index("idx_eval_progress_status", table_name="eval_progress_snapshots")
    op.drop_index("idx_eval_progress_event_type_timestamp", table_name="eval_progress_snapshots")
    op.drop_index("idx_eval_progress_evaluation_timestamp", table_name="eval_progress_snapshots")
    op.drop_index("idx_eval_progress_experiment_timestamp", table_name="eval_progress_snapshots")
    op.drop_table("eval_progress_snapshots")
