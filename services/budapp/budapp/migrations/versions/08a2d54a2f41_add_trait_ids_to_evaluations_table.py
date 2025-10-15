"""add_trait_ids_to_evaluations_table

Revision ID: 08a2d54a2f41
Revises: 99436ce65916
Create Date: 2025-09-22 16:22:14.981023

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "08a2d54a2f41"
down_revision: Union[str, None] = "99436ce65916"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add trait_ids column to evaluations table
    op.add_column("evaluations", sa.Column("trait_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    # Remove trait_ids column from evaluations table
    op.drop_column("evaluations", "trait_ids")
