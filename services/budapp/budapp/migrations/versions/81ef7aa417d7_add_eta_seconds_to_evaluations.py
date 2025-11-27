"""add eta_seconds to evaluations

Revision ID: 81ef7aa417d7
Revises: 3ab72e8244b4
Create Date: 2025-11-27 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "81ef7aa417d7"
down_revision: Union[str, None] = "3ab72e8244b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add eta_seconds column to evaluations table."""
    op.add_column("evaluations", sa.Column("eta_seconds", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove eta_seconds column from evaluations table."""
    op.drop_column("evaluations", "eta_seconds")
