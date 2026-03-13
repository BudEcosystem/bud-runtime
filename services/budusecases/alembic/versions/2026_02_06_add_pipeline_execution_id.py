"""Add pipeline_execution_id to usecase_deployments.

Links UseCase deployments to BudPipeline executions for tracking
and status synchronization.

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-06
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add pipeline_execution_id column
    op.add_column(
        "usecase_deployments",
        sa.Column("pipeline_execution_id", sa.String(255), nullable=True),
    )

    # Add index on pipeline_execution_id
    op.create_index(
        "ix_usecase_deployments_pipeline_execution_id",
        "usecase_deployments",
        ["pipeline_execution_id"],
    )


def downgrade() -> None:
    # Drop index
    op.drop_index("ix_usecase_deployments_pipeline_execution_id", "usecase_deployments")

    # Drop column
    op.drop_column("usecase_deployments", "pipeline_execution_id")
