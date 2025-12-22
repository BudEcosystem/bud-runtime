"""Add display_name column to dataset table

Revision ID: c4d5e6f7a8b9
Revises: bf37ac5c03c7
Create Date: 2025-12-15 13:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "bf37ac5c03c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add display_name column to dataset table."""
    op.add_column("dataset", sa.Column("display_name", sa.String(), nullable=True))


def downgrade() -> None:
    """Remove display_name column from dataset table."""
    op.drop_column("dataset", "display_name")
