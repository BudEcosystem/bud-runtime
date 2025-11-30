"""Add ERROR state tracking fields to cluster table.

Revision ID: 5ef9hgd781dh
Revises: 4df8gfc670cg
Create Date: 2025-11-21 06:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "5ef9hgd781dh"
down_revision: Union[str, None] = "4df8gfc670cg"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade the database."""
    # Add not_available_since column for tracking when cluster became NOT_AVAILABLE
    op.add_column("cluster", sa.Column("not_available_since", sa.DateTime(), nullable=True))

    # Add last_retry_time column for tracking when ERROR clusters were last retried
    op.add_column("cluster", sa.Column("last_retry_time", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade the database."""
    # Drop last_retry_time column
    op.drop_column("cluster", "last_retry_time")

    # Drop not_available_since column
    op.drop_column("cluster", "not_available_since")
