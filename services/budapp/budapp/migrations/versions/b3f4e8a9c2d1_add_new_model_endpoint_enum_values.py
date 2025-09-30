"""add new model endpoint enum values

Revision ID: b3f4e8a9c2d1
Revises: aea48f780385
Create Date: 2025-09-30 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b3f4e8a9c2d1"
down_revision: Union[str, None] = "aea48f780385"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add new enum values to model_endpoint_enum type."""
    # Add missing enum values to the existing PostgreSQL enum type
    op.execute("ALTER TYPE model_endpoint_enum ADD VALUE IF NOT EXISTS '/v1/audio/translations'")
    op.execute("ALTER TYPE model_endpoint_enum ADD VALUE IF NOT EXISTS '/v1/images/edits'")
    op.execute("ALTER TYPE model_endpoint_enum ADD VALUE IF NOT EXISTS '/v1/images/variations'")


def downgrade() -> None:
    """Downgrade is not supported for PostgreSQL enum values.

    PostgreSQL does not support removing enum values directly.
    To remove values, the entire enum type would need to be recreated,
    which would require dropping and recreating all dependent columns.
    """
    pass
