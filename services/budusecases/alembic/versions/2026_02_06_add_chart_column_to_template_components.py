"""Add chart JSONB column to template_components.

Stores Helm chart configuration (ref, version, values) for helm-type
template components so that chart data persists to the database alongside
other component metadata.

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-06
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "template_components",
        sa.Column("chart", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("template_components", "chart")
