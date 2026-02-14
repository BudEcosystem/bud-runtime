"""Add icon column to pipeline_definition.

Revision ID: 006_add_icon
Revises: 005_user_isolation
Create Date: 2026-02-10 12:00:00.000000

This migration adds an optional icon column to pipeline_definition
for storing a user-selected emoji/icon for UI representation.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "006_add_icon"
down_revision = "005_user_isolation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pipeline_definition",
        sa.Column(
            "icon",
            sa.String(255),
            nullable=True,
            comment="Optional icon/emoji for UI representation",
        ),
    )


def downgrade() -> None:
    op.drop_column("pipeline_definition", "icon")
