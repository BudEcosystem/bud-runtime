"""add enriched fields to exp_datasets

Revision ID: a1b2c3d4e5f7
Revises: 8a9b463c9646
Create Date: 2025-11-17 14:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, None] = "8a9b463c9646"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add enriched fields to exp_datasets table for storing evaluation metadata."""
    # Add why_run_this_eval field
    op.add_column(
        "exp_datasets",
        sa.Column("why_run_this_eval", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # Add what_to_expect field
    op.add_column(
        "exp_datasets",
        sa.Column("what_to_expect", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # Add additional_info JSONB field for flexible metadata storage
    op.add_column(
        "exp_datasets",
        sa.Column("additional_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Remove enriched fields from exp_datasets table."""
    op.drop_column("exp_datasets", "additional_info")
    op.drop_column("exp_datasets", "what_to_expect")
    op.drop_column("exp_datasets", "why_run_this_eval")
