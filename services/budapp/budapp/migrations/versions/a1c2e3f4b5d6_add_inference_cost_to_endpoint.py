"""add inference_cost JSONB column to endpoint table

Revision ID: a1c2e3f4b5d6
Revises: a3b4c5d6e7f8
Create Date: 2026-02-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a1c2e3f4b5d6"
down_revision: Union[str, None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add inference_cost JSONB column to endpoint table."""
    op.add_column(
        "endpoint",
        sa.Column("inference_cost", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Remove inference_cost column from endpoint table."""
    op.drop_column("endpoint", "inference_cost")
