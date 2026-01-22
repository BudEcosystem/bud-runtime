"""Fix delivery_status check constraint to match SQLAlchemy enum name (uppercase).

Revision ID: 003_fix_delivery_status
Revises: 002
Create Date: 2026-01-16 20:40:00.000000

SQLAlchemy with native_enum=False stores the enum's .name attribute (uppercase)
rather than .value (lowercase). This migration updates the check constraint
to match the actual values being stored.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Update check constraint to use uppercase enum names."""
    # Drop the old constraint using raw SQL
    op.execute(
        'ALTER TABLE execution_subscription DROP CONSTRAINT IF EXISTS "chk_execution_subscription_status"'
    )

    # Create new constraint with uppercase values
    op.execute(
        """
        ALTER TABLE execution_subscription
        ADD CONSTRAINT chk_execution_subscription_status
        CHECK (delivery_status IN ('ACTIVE', 'EXPIRED', 'FAILED'))
        """
    )

    # Update the partial index that uses delivery_status
    op.execute("DROP INDEX IF EXISTS idx_execution_subscription_active")
    op.execute(
        """
        CREATE INDEX idx_execution_subscription_active
        ON execution_subscription (execution_id, delivery_status)
        WHERE delivery_status = 'ACTIVE'
        """
    )


def downgrade() -> None:
    """Revert to lowercase values."""
    # Drop the uppercase constraint using raw SQL
    op.execute(
        'ALTER TABLE execution_subscription DROP CONSTRAINT IF EXISTS "chk_execution_subscription_status"'
    )

    # Create constraint with lowercase values
    op.execute(
        """
        ALTER TABLE execution_subscription
        ADD CONSTRAINT chk_execution_subscription_status
        CHECK (delivery_status IN ('active', 'expired', 'failed'))
        """
    )

    # Recreate partial index with lowercase
    op.execute("DROP INDEX IF EXISTS idx_execution_subscription_active")
    op.execute(
        """
        CREATE INDEX idx_execution_subscription_active
        ON execution_subscription (execution_id, delivery_status)
        WHERE delivery_status = 'active'
        """
    )
