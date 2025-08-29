"""Update cluster_node_type_enum to include cuda and rocm.

Revision ID: ad3e6203c0f4
Revises: 0f01fe09dba0
Create Date: 2025-08-21 12:36:52.628828

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "ad3e6203c0f4"
down_revision: Union[str, None] = "0f01fe09dba0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade the database."""
    # Add new enum values first
    op.execute("ALTER TYPE cluster_node_type_enum ADD VALUE IF NOT EXISTS 'cuda'")
    op.execute("ALTER TYPE cluster_node_type_enum ADD VALUE IF NOT EXISTS 'rocm'")

    # Note: We keep 'gpu' as legacy for backward compatibility
    # New entries will use the specific types (cuda, rocm)
    # Existing 'gpu' entries can be migrated later if needed


def downgrade() -> None:
    """Downgrade the database."""
    # Convert cuda and rocm back to gpu before removing the enum values
    op.execute("UPDATE cluster_node_info SET type = 'gpu' WHERE type IN ('cuda', 'rocm')")

    # Note: PostgreSQL doesn't support removing values from enums easily
    # So we just convert the data back but leave the enum values in place
