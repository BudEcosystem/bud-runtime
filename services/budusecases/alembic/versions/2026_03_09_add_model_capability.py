"""Add model_capability column to template_components.

Stores an optional model capability filter (e.g. chat, embedding) for
deploy_model type components, enabling templates to specify which model
capabilities are required for a given component slot.

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-09
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "template_components",
        sa.Column("model_capability", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("template_components", "model_capability")
