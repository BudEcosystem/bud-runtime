"""Add project_id column to usecase_deployments.

Enables project-scoped API access control for deployed use cases.
The project_id links a deployment to a budapp project, allowing
budgateway to enforce API key → project → deployment access.

Revision ID: 0006
Revises: 0005
Create Date: 2026-02-09
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usecase_deployments",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_usecase_deployments_project_id",
        "usecase_deployments",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_usecase_deployments_project_id", "usecase_deployments")
    op.drop_column("usecase_deployments", "project_id")
