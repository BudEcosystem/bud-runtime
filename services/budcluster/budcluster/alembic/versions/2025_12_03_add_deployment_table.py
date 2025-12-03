"""Add deployment table and deployment_id to worker_info.

Revision ID: 6fg0ihf892ei
Revises: 5ef9hgd781dh
Create Date: 2025-12-03 08:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "6fg0ihf892ei"
down_revision: Union[str, None] = "5ef9hgd781dh"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade the database."""
    # Create deployment table
    op.create_table(
        "deployment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cluster_id", sa.Uuid(), nullable=False),
        sa.Column("namespace", sa.String(), nullable=False),
        sa.Column("deployment_name", sa.String(), nullable=False),
        sa.Column("endpoint_name", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("deployment_url", sa.String(), nullable=True),
        sa.Column("supported_endpoints", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("concurrency", sa.Integer(), nullable=False),
        sa.Column("number_of_replicas", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deploy_config", postgresql.JSONB(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "ready",
                "pending",
                "ingress_failed",
                "endpoints_failed",
                "failed",
                name="deployment_status_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("workflow_id", sa.Uuid(), nullable=True),
        sa.Column("simulator_id", sa.Uuid(), nullable=True),
        sa.Column("credential_id", sa.Uuid(), nullable=True),
        sa.Column("last_status_check", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("modified_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["cluster_id"], ["cluster.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("namespace", name="uq_deployment_namespace"),
    )

    # Create indexes for deployment table
    op.create_index("ix_deployment_cluster_id", "deployment", ["cluster_id"])
    op.create_index("ix_deployment_status", "deployment", ["status"])

    # Add deployment_id foreign key to worker_info table
    op.add_column("worker_info", sa.Column("deployment_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_worker_info_deployment",
        "worker_info",
        "deployment",
        ["deployment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_worker_info_deployment_id", "worker_info", ["deployment_id"])


def downgrade() -> None:
    """Downgrade the database."""
    # Drop deployment_id from worker_info
    op.drop_index("ix_worker_info_deployment_id", table_name="worker_info")
    op.drop_constraint("fk_worker_info_deployment", "worker_info", type_="foreignkey")
    op.drop_column("worker_info", "deployment_id")

    # Drop deployment table indexes and table
    op.drop_index("ix_deployment_status", table_name="deployment")
    op.drop_index("ix_deployment_cluster_id", table_name="deployment")
    op.drop_table("deployment")
