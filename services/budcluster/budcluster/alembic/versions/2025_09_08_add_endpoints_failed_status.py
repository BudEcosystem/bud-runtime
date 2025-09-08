"""add_endpoints_failed_status.

Revision ID: 2bc5feb468ae
Revises: ad3e6203c0f4
Create Date: 2025-09-08 08:09:32.336170

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "2bc5feb468ae"
down_revision: Union[str, None] = "ad3e6203c0f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade the database."""
    # Add the new 'endpoints_failed' value to the existing deployment_status_enum type
    op.execute("ALTER TYPE deployment_status_enum ADD VALUE 'endpoints_failed'")


def downgrade() -> None:
    """Downgrade the database."""
    # Note: PostgreSQL doesn't support removing enum values directly
    # This would require recreating the enum type and updating all references
    # For now, we'll leave the enum value in place during downgrade
    pass
