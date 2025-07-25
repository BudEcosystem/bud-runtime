"""worker_info timestamps.

Revision ID: bc1ee1faa04d
Revises: 5a6d4ee8ef06
Create Date: 2025-02-19 13:44:26.033536

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "bc1ee1faa04d"
down_revision: Union[str, None] = "5a6d4ee8ef06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade the database."""
    op.alter_column("cluster", "created_at", type_=sa.DateTime(timezone=True), nullable=False)
    op.alter_column("cluster", "modified_at", type_=sa.DateTime(timezone=True), nullable=False)
    op.alter_column("cluster_node_info", "created_at", type_=sa.DateTime(timezone=True), nullable=False)
    op.alter_column("cluster_node_info", "modified_at", type_=sa.DateTime(timezone=True), nullable=False)
    op.alter_column("worker_info", "created_at", type_=sa.DateTime(timezone=True), nullable=False)
    op.alter_column("worker_info", "modified_at", type_=sa.DateTime(timezone=True), nullable=False)
    op.alter_column("worker_info", "created_datetime", type_=sa.DateTime(timezone=True), nullable=False)
    op.alter_column("worker_info", "last_restart_datetime", type_=sa.DateTime(timezone=True), nullable=False)
    op.alter_column("worker_info", "last_updated_datetime", type_=sa.DateTime(timezone=True), nullable=False)


def downgrade() -> None:
    """Downgrade the database."""
    op.alter_column("cluster", "created_at", type_=sa.DateTime(), nullable=False)
    op.alter_column("cluster", "modified_at", type_=sa.DateTime(), nullable=False)
    op.alter_column("cluster_node_info", "created_at", type_=sa.DateTime(), nullable=False)
    op.alter_column("cluster_node_info", "modified_at", type_=sa.DateTime(), nullable=False)
    op.alter_column("worker_info", "created_at", type_=sa.DateTime(), nullable=False)
    op.alter_column("worker_info", "modified_at", type_=sa.DateTime(), nullable=False)
    op.alter_column("worker_info", "created_datetime", type_=sa.DateTime(), nullable=False)
    op.alter_column("worker_info", "last_restart_datetime", type_=sa.DateTime(), nullable=False)
    op.alter_column("worker_info", "last_updated_datetime", type_=sa.DateTime(), nullable=False)
