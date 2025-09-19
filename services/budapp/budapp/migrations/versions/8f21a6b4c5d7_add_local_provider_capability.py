"""Add LOCAL capability to provider enum

Revision ID: 8f21a6b4c5d7
Revises: 7a8b9c0d1e2f
Create Date: 2025-10-31 00:00:00.000000

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "8f21a6b4c5d7"
down_revision = "7a8b9c0d1e2f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE provider_capability_enum ADD VALUE IF NOT EXISTS 'local'")


def downgrade() -> None:
    # PostgreSQL does not support dropping enum values natively without recreating the type.
    # Leaving downgrade as a no-op avoids accidental data loss.
    pass
