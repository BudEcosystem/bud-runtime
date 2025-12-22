"""Add CANCELLED value to benchmark_status_enum.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2025-12-15 19:30:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add CANCELLED value to benchmark_status_enum."""
    op.execute("ALTER TYPE benchmark_status_enum ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade() -> None:
    """Remove CANCELLED from benchmark_status_enum - not easily reversible in PostgreSQL."""
    # PostgreSQL doesn't support removing enum values easily
    # Would need to recreate the type and update all references
    pass
