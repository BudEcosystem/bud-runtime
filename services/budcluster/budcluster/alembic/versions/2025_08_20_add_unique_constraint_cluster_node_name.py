"""add_unique_constraint_cluster_node_name.

Revision ID: 0f01fe09dba0
Revises: 3bc055340c00
Create Date: 2025-08-20 13:55:37.359583

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0f01fe09dba0"
down_revision: Union[str, None] = "3bc055340c00"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade the database."""
    # First, clean up any existing duplicates
    # This query keeps the most recent node for each (cluster_id, name) pair
    # and deletes the older duplicates
    op.execute("""
        DELETE FROM cluster_node_info
        WHERE id NOT IN (
            SELECT DISTINCT ON (cluster_id, name) id
            FROM cluster_node_info
            ORDER BY cluster_id, name, modified_at DESC NULLS LAST, created_at DESC NULLS LAST, id DESC
        )
    """)

    # Now add the unique constraint
    op.create_unique_constraint("uq_cluster_node_info_cluster_id_name", "cluster_node_info", ["cluster_id", "name"])


def downgrade() -> None:
    """Downgrade the database."""
    # Remove the unique constraint
    op.drop_constraint("uq_cluster_node_info_cluster_id_name", "cluster_node_info", type_="unique")
