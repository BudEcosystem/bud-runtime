"""Add billing notification fields

Revision ID: e5b3d2a8f92c
Revises: cc482aaabf0d
Create Date: 2025-02-02 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e5b3d2a8f92c"
down_revision: Union[str, None] = "cc482aaabf0d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add notification tracking fields to billing_alerts table
    op.add_column("billing_alerts", sa.Column("last_notification_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "billing_alerts", sa.Column("notification_failure_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("billing_alerts", sa.Column("last_notification_error", sa.String(length=500), nullable=True))

    # Add notification preferences to user_billing table
    op.add_column(
        "user_billing", sa.Column("enable_email_notifications", sa.Boolean(), nullable=False, server_default="true")
    )
    op.add_column(
        "user_billing", sa.Column("enable_in_app_notifications", sa.Boolean(), nullable=False, server_default="true")
    )


def downgrade() -> None:
    # Remove notification preferences from user_billing table
    op.drop_column("user_billing", "enable_in_app_notifications")
    op.drop_column("user_billing", "enable_email_notifications")

    # Remove notification tracking fields from billing_alerts table
    op.drop_column("billing_alerts", "last_notification_error")
    op.drop_column("billing_alerts", "notification_failure_count")
    op.drop_column("billing_alerts", "last_notification_sent_at")
