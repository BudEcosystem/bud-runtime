"""add_endpoints_failed_status.

Revision ID: 2bc5feb468ae
Revises: ad3e6203c0f4
Create Date: 2025-09-08 08:09:32.336170

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "2bc5feb468ae"
down_revision: Union[str, None] = "ad3e6203c0f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade the database."""
    # Add the new 'endpoints_failed' value to the existing deployment_status_enum type
    op.execute("ALTER TYPE deployment_status_enum ADD VALUE 'endpoints_failed'")


def downgrade() -> None:
    """Downgrade the database."""
    # IMPORTANT: PostgreSQL doesn't support removing enum values directly.
    # This migration is designed to be non-reversible for production safety.
    #
    # If you need to remove 'endpoints_failed' status in development:
    # 1. Ensure no records use this status value
    # 2. Manually recreate the enum without this value:
    #    - CREATE TYPE deployment_status_enum_new AS ENUM ('ready', 'pending', 'ingress_failed', 'failed');
    #    - ALTER TABLE deployment ALTER COLUMN deployment_status TYPE deployment_status_enum_new USING deployment_status::text::deployment_status_enum_new;
    #    - DROP TYPE deployment_status_enum;
    #    - ALTER TYPE deployment_status_enum_new RENAME TO deployment_status_enum;
    #
    # For production environments, consider this a forward-only migration.

    # Check if any records use the 'endpoints_failed' status
    from sqlalchemy import text

    result = (
        op.get_bind()
        .execute(text("SELECT COUNT(*) FROM deployment WHERE deployment_status = 'endpoints_failed'"))
        .scalar()
    )

    if result > 0:
        raise Exception(
            f"Cannot downgrade: {result} deployment(s) currently have 'endpoints_failed' status. "
            "Please update these records before downgrading."
        )
