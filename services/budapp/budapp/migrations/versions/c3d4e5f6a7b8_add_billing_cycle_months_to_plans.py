"""Add billing cycle months to billing plans

Revision ID: c3d4e5f6a7b8
Revises: c1b2c3d4e5e6
Create Date: 2025-09-11 13:20:00.000000

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b8"
down_revision = "c1b2c3d4e5e6"
branch_labels = None
depends_on = None


def upgrade():
    """Add billing_cycle_months field to billing_plans table."""
    # Add the new column with default value of 1 (monthly cycles)
    op.add_column("billing_plans", sa.Column("billing_cycle_months", sa.Integer(), nullable=False, server_default="1"))


def downgrade():
    """Remove billing_cycle_months field from billing_plans table."""
    op.drop_column("billing_plans", "billing_cycle_months")
