"""Change billing_alerts foreign key from user_billing_id to user_id

Revision ID: a1b2c3d4e5f6
Revises: e5b3d2a8f92c
Create Date: 2025-09-06 16:50:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "e5b3d2a8f92c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the new user_id column
    op.add_column("billing_alerts", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))

    # Populate user_id from user_billing table
    op.execute("""
        UPDATE billing_alerts
        SET user_id = ub.user_id
        FROM user_billing ub
        WHERE billing_alerts.user_billing_id = ub.id
    """)

    # Make user_id not nullable
    op.alter_column("billing_alerts", "user_id", nullable=False)

    # Add unique constraint for user_id and name combination
    op.create_unique_constraint("uq_billing_alert_user_name", "billing_alerts", ["user_id", "name"])

    # Add foreign key constraint to user table
    op.create_foreign_key("fk_billing_alerts_user_id", "billing_alerts", "user", ["user_id"], ["id"])

    # Drop old foreign key constraint and column
    op.drop_constraint("billing_alerts_user_billing_id_fkey", "billing_alerts", type_="foreignkey")
    op.drop_column("billing_alerts", "user_billing_id")


def downgrade() -> None:
    # Add back the user_billing_id column
    op.add_column("billing_alerts", sa.Column("user_billing_id", postgresql.UUID(as_uuid=True), nullable=True))

    # Populate user_billing_id from user_billing table (get first billing record for user)
    op.execute("""
        UPDATE billing_alerts
        SET user_billing_id = ub.id
        FROM user_billing ub
        WHERE billing_alerts.user_id = ub.user_id
    """)

    # Make user_billing_id not nullable
    op.alter_column("billing_alerts", "user_billing_id", nullable=False)

    # Drop the unique constraint
    op.drop_constraint("uq_billing_alert_user_name", "billing_alerts", type_="unique")

    # Add foreign key constraint back to user_billing table
    op.create_foreign_key(
        "billing_alerts_user_billing_id_fkey", "billing_alerts", "user_billing", ["user_billing_id"], ["id"]
    )

    # Drop new foreign key constraint and column
    op.drop_constraint("fk_billing_alerts_user_id", "billing_alerts", type_="foreignkey")
    op.drop_column("billing_alerts", "user_id")
