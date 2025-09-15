"""add DOCUMENT to model_endpoint_enum

Revision ID: 7a8b9c0d1e2f
Revises: 53c43a46147b
Create Date: 2025-09-15 20:35:00.000000

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "7a8b9c0d1e2f"
down_revision = "53c43a46147b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add DOCUMENT value to model_endpoint_enum
    op.execute("ALTER TYPE model_endpoint_enum ADD VALUE IF NOT EXISTS '/v1/documents'")


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values directly
    # This would require recreating the enum type which is complex
    # For simplicity, we'll leave this as a no-op
    pass
