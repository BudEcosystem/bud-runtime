"""Add historical billing cycle tracking

Revision ID: 44ad5600310c
Revises: 1433e70d23ab
Create Date: 2025-01-22 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "44ad5600310c"
down_revision: Union[str, None] = "1433e70d23ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add fields for historical billing cycle tracking."""
    # Add new columns for historical tracking
    op.add_column("user_billing", sa.Column("is_current", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("user_billing", sa.Column("cycle_number", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("user_billing", sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user_billing", sa.Column("superseded_by_id", postgresql.UUID(as_uuid=True), nullable=True))

    # Add foreign key constraint for superseded_by_id
    op.create_foreign_key(
        "fk_user_billing_superseded_by", "user_billing", "user_billing", ["superseded_by_id"], ["id"]
    )

    # Remove the unique constraint on user_id (we need multiple entries per user now)
    op.drop_constraint("user_billing_user_id_key", "user_billing", type_="unique")

    # Create indexes for performance
    op.create_index("ix_user_billing_user_current", "user_billing", ["user_id", "is_current"])
    op.create_index("ix_user_billing_active", "user_billing", ["user_id", "is_active"])
    op.create_index(
        "ix_user_billing_period", "user_billing", ["user_id", "billing_period_start", "billing_period_end"]
    )
    op.create_index("ix_user_billing_created_current", "user_billing", ["created_at", "is_current"])


def downgrade() -> None:
    """Revert historical billing cycle tracking changes."""
    # Drop indexes
    op.drop_index("ix_user_billing_created_current", table_name="user_billing")
    op.drop_index("ix_user_billing_period", table_name="user_billing")
    op.drop_index("ix_user_billing_active", table_name="user_billing")
    op.drop_index("ix_user_billing_user_current", table_name="user_billing")

    # Drop foreign key constraint
    op.drop_constraint("fk_user_billing_superseded_by", "user_billing", type_="foreignkey")

    # Add back the unique constraint on user_id (this will fail if there are multiple entries per user)
    # Note: This assumes you've cleaned up duplicate entries before downgrading
    op.create_unique_constraint("user_billing_user_id_key", "user_billing", ["user_id"])

    # Remove historical tracking columns
    op.drop_column("user_billing", "superseded_by_id")
    op.drop_column("user_billing", "superseded_at")
    op.drop_column("user_billing", "cycle_number")
    op.drop_column("user_billing", "is_current")
