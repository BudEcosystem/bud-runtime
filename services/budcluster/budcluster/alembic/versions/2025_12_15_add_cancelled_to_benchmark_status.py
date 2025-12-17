"""Add CANCELLED value to benchmark_status_enum.

Revision ID: 8b9c0d1e2f3g
Revises: 7a8b9c0d1e2f
Create Date: 2025-12-15

"""

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "8b9c0d1e2f3g"
down_revision: str | None = "7a8b9c0d1e2f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add CANCELLED value to benchmark_status_enum."""
    op.execute("ALTER TYPE benchmark_status_enum ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade() -> None:
    """Remove CANCELLED from benchmark_status_enum - not easily reversible in PostgreSQL."""
    # PostgreSQL doesn't support removing enum values easily
    # Would need to recreate the type and update all references
    pass
