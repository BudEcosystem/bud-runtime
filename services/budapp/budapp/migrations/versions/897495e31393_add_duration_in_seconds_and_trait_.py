"""add duration_in_seconds and trait_scores to evaluation

Revision ID: 897495e31393
Revises: b3f4e8a9c2d1
Create Date: 2025-10-01 13:15:10.403285

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "897495e31393"
down_revision: Union[str, None] = "b3f4e8a9c2d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add duration_in_seconds column
    op.add_column("evaluations", sa.Column("duration_in_seconds", sa.Float(), nullable=True))

    # Add trait_scores column (JSON with string keys and values)
    op.add_column("evaluations", sa.Column("trait_scores", sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove columns in reverse order
    op.drop_column("evaluations", "trait_scores")
    op.drop_column("evaluations", "duration_in_seconds")
