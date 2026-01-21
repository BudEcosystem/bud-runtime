"""add CLASSIFY to model_endpoint_enum

Revision ID: 9f3c2b1a4d5e
Revises: 42c894042a04
Create Date: 2026-01-21 00:00:00.000000

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "9f3c2b1a4d5e"
down_revision = "42c894042a04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE model_endpoint_enum ADD VALUE IF NOT EXISTS '/v1/classify'")


def downgrade() -> None:
    # PostgreSQL does not support dropping enum values natively without recreating the type.
    # Leaving downgrade as a no-op avoids accidental data loss.
    pass
