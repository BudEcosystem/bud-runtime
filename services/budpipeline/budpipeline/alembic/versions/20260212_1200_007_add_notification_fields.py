"""Add notification fields to pipeline_execution.

Revision ID: 007_add_notification_fields
Revises: 006_add_icon
Create Date: 2026-02-12 12:00:00.000000

This migration adds subscriber_ids and payload_type columns to pipeline_execution
for NotificationPayload format support and dual-publish to budnotify.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "007_add_notification_fields"
down_revision = "006_add_icon"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pipeline_execution",
        sa.Column(
            "subscriber_ids",
            sa.String(500),
            nullable=True,
            comment="User ID(s) for Novu delivery (enables dual-publish to budnotify)",
        ),
    )
    op.add_column(
        "pipeline_execution",
        sa.Column(
            "payload_type",
            sa.String(100),
            nullable=True,
            comment="Custom payload.type for budadmin routing (defaults to pipeline_execution)",
        ),
    )


def downgrade() -> None:
    op.drop_column("pipeline_execution", "payload_type")
    op.drop_column("pipeline_execution", "subscriber_ids")
