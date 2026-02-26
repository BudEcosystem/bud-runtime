"""Add access JSONB column to templates.

Stores access mode configuration (UI and API) for use case templates,
enabling templates to declare how deployed use cases can be accessed
by end users.

Revision ID: 0007
Revises: 0006
Create Date: 2026-02-10
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "templates",
        sa.Column("access", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("templates", "access")
