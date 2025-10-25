"""Add internal_ip field to cluster_node_info table.

Revision ID: 4df8gfc670cg
Revises: 3cf7feb569bf
Create Date: 2025-10-24 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "4df8gfc670cg"
down_revision: Union[str, None] = "3cf7feb569bf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade the database."""
    # Add internal_ip column to cluster_node_info table
    op.add_column("cluster_node_info", sa.Column("internal_ip", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade the database."""
    # Drop internal_ip column from cluster_node_info table
    op.drop_column("cluster_node_info", "internal_ip")
