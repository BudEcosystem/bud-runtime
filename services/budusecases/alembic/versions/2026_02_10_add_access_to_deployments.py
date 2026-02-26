"""Add access_config and gateway_url columns to usecase_deployments.

Stores a snapshot of the template's access mode configuration at deployment
time, and the Envoy Gateway external endpoint URL on the target cluster.

Revision ID: 0008
Revises: 0007
Create Date: 2026-02-10
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usecase_deployments",
        sa.Column("access_config", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "usecase_deployments",
        sa.Column("gateway_url", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("usecase_deployments", "gateway_url")
    op.drop_column("usecase_deployments", "access_config")
