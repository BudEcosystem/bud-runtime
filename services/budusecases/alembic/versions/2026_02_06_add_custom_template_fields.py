"""Add source, user_id, is_public columns for custom templates.

Adds support for user-created templates with visibility control.
System templates (from YAML sync) continue to work as before.
User templates have a user_id and can be public or private.

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-06
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns
    op.add_column(
        "templates",
        sa.Column("source", sa.String(50), nullable=False, server_default="system"),
    )
    op.add_column(
        "templates",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "templates",
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="true"),
    )

    # Backfill existing rows
    op.execute("UPDATE templates SET source = 'system', is_public = true")

    # Add indexes
    op.create_index("ix_templates_source", "templates", ["source"])
    op.create_index("ix_templates_user_id", "templates", ["user_id"])
    op.create_index("ix_templates_is_public", "templates", ["is_public"])

    # Drop old unique constraint on name
    op.drop_constraint("templates_name_key", "templates", type_="unique")

    # Create composite unique constraint (name + user_id)
    op.create_unique_constraint("uq_template_name_user_id", "templates", ["name", "user_id"])

    # Create partial unique index for system templates (name must be unique where source='system')
    op.execute("CREATE UNIQUE INDEX ix_template_name_system_unique ON templates (name) WHERE source = 'system'")


def downgrade() -> None:
    # Drop partial unique index
    op.execute("DROP INDEX IF EXISTS ix_template_name_system_unique")

    # Drop composite unique constraint
    op.drop_constraint("uq_template_name_user_id", "templates", type_="unique")

    # Restore original unique constraint on name
    op.create_unique_constraint("templates_name_key", "templates", ["name"])

    # Drop indexes
    op.drop_index("ix_templates_is_public", "templates")
    op.drop_index("ix_templates_user_id", "templates")
    op.drop_index("ix_templates_source", "templates")

    # Drop columns
    op.drop_column("templates", "is_public")
    op.drop_column("templates", "user_id")
    op.drop_column("templates", "source")
