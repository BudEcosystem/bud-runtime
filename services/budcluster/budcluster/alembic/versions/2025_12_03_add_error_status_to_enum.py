"""Add error status to deployment_status_enum.

Revision ID: 7gh1jig903fj
Revises: 6fg0ihf892ei
Create Date: 2025-12-03 11:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7gh1jig903fj"
down_revision: Union[str, None] = "6fg0ihf892ei"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 'error' value to deployment_status_enum."""
    op.execute("ALTER TYPE deployment_status_enum ADD VALUE IF NOT EXISTS 'error'")


def downgrade() -> None:
    """Remove 'error' value from deployment_status_enum.

    Note: PostgreSQL doesn't support removing enum values directly.
    This would require recreating the enum type and updating all columns.
    For safety, we leave this as a no-op.
    """
    pass
