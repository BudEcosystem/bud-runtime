"""Add user isolation columns to pipeline_definition.

Revision ID: 005_user_isolation
Revises: 004_event_driven_completion
Create Date: 2026-01-18 10:00:00.000000

This migration adds columns for user-scoped pipeline ownership:
- user_id: UUID of the owning user (nullable for system/anonymous pipelines)
- system_owned: Boolean flag for system-owned pipelines (visible to all users)

Also adds an index on user_id for efficient user filtering.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "005_user_isolation"
down_revision = "004_event_driven_completion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add user isolation columns and index."""

    # Add user_id column (nullable - for backwards compatibility and system pipelines)
    op.add_column(
        "pipeline_definition",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="UUID of the owning user (null for system or legacy pipelines)",
        ),
    )

    # Add system_owned column (defaults to false)
    op.add_column(
        "pipeline_definition",
        sa.Column(
            "system_owned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="True if this is a system-owned pipeline visible to all users",
        ),
    )

    # Create index for efficient user filtering
    op.create_index(
        "idx_pipeline_definition_user_id",
        "pipeline_definition",
        ["user_id"],
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Remove user isolation columns and index."""

    # Drop index first
    op.drop_index("idx_pipeline_definition_user_id", table_name="pipeline_definition")

    # Drop columns
    op.drop_column("pipeline_definition", "system_owned")
    op.drop_column("pipeline_definition", "user_id")
