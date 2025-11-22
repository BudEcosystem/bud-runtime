"""add evaluation config fields to exp_datasets

Revision ID: 3ab72e8244b4
Revises: a1b2c3d4e5f7
Create Date: 2025-11-23 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "3ab72e8244b4"
down_revision: Union[str, None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add evaluation configuration fields to exp_datasets table."""
    # Add new columns for evaluation configuration
    op.add_column("exp_datasets", sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("exp_datasets", sa.Column("evaluator", sa.String(), nullable=True))


def downgrade() -> None:
    """Remove evaluation configuration fields from exp_datasets table."""
    # Remove the added columns
    op.drop_column("exp_datasets", "evaluator")
    op.drop_column("exp_datasets", "metrics")
