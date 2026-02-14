"""Add notification_workflow_id to pipeline_execution.

Revision ID: 008_add_notification_workflow_id
Revises: 007_add_notification_fields
Create Date: 2026-02-13 12:00:00.000000

This migration adds the notification_workflow_id column to pipeline_execution
so callers can override payload.workflow_id in notifications instead of always
using the execution_id.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "008_add_notification_workflow_id"
down_revision = "007_add_notification_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pipeline_execution",
        sa.Column(
            "notification_workflow_id",
            sa.String(255),
            nullable=True,
            comment="Override payload.workflow_id in notifications (defaults to execution_id)",
        ),
    )


def downgrade() -> None:
    op.drop_column("pipeline_execution", "notification_workflow_id")
