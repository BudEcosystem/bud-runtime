"""Fix user_billing unique constraint to allow multiple billing records per user

Revision ID: c1b2c3d4e5e6
Revises: 44ad5600310c
Create Date: 2025-09-11 08:45:00.000000

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "c1b2c3d4e5e6"
down_revision = "44ad5600310c"
branch_labels = None
depends_on = None


def upgrade():
    """Drop the problematic unique index and replace with a partial unique index."""
    # Drop the existing unique index that prevents multiple billing records per user
    op.drop_index("ix_user_billing_user_id", table_name="user_billing")

    # Create a partial unique index to ensure only one current billing record per user
    # This allows multiple billing records per user but only one with is_current=True
    op.create_index(
        "ix_user_billing_user_current_unique",
        "user_billing",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )


def downgrade():
    """Restore the original unique index (this may fail if multiple records exist)."""
    # Drop the partial unique index
    op.drop_index("ix_user_billing_user_current_unique", table_name="user_billing")

    # WARNING: This may fail if there are multiple billing records per user
    # In that case, data cleanup would be required before running this downgrade
    op.create_index("ix_user_billing_user_id", "user_billing", ["user_id"], unique=True)
