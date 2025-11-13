"""Add metrics collection fields to cluster table.

Revision ID: 3cf7feb569bf
Revises: 2bc5feb468ae
Create Date: 2025-09-21 10:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "3cf7feb569bf"
down_revision: Union[str, None] = "2bc5feb468ae"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade the database."""
    # Add last_metrics_collection column
    op.add_column("cluster", sa.Column("last_metrics_collection", sa.DateTime(), nullable=True))

    # Add metrics_collection_status column
    op.add_column("cluster", sa.Column("metrics_collection_status", sa.String(length=50), nullable=True))


def downgrade() -> None:
    """Downgrade the database."""
    # Drop metrics_collection_status column
    op.drop_column("cluster", "metrics_collection_status")

    # Drop last_metrics_collection column
    op.drop_column("cluster", "last_metrics_collection")
