"""Drop stale lowercase delivery_status check constraint.

Revision ID: 009_fix_status_constraint
Revises: 008_add_notification_workflow_id
Create Date: 2026-02-16 12:00:00.000000

Migration 003 intended to replace the lowercase delivery_status constraint
with an uppercase one, but used the wrong constraint name. The SQLAlchemy
naming convention prefixed the original constraint as
'ck_execution_subscription_chk_execution_subscription_status' (lowercase),
while migration 003 only dropped 'chk_execution_subscription_status'.

This left two constraints: the old lowercase one (blocking inserts of 'ACTIVE')
and the new uppercase one. This migration drops the stale lowercase constraint.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "009_fix_status_constraint"
down_revision = "008_add_notification_workflow_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop the stale lowercase constraint that blocks ACTIVE inserts."""
    op.execute(
        'ALTER TABLE execution_subscription DROP CONSTRAINT IF EXISTS "ck_execution_subscription_chk_execution_subscription_status"'
    )


def downgrade() -> None:
    """Re-add the lowercase constraint (not recommended)."""
    op.execute(
        """
        ALTER TABLE execution_subscription
        ADD CONSTRAINT ck_execution_subscription_chk_execution_subscription_status
        CHECK (delivery_status IN ('active', 'expired', 'failed'))
        """
    )
