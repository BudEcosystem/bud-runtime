"""change_guardrail_rule_provider_type_to_enum_and_cleanup_scanner_types

Revision ID: c1a2b3d4e5f6
Revises: f01f988c0272
Create Date: 2025-01-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, None] = "f01f988c0272"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Change model_provider_type from String(50) to model_provider_type_enum
    # The enum already exists from the model table
    op.execute(
        """
        ALTER TABLE guardrail_rule
        ALTER COLUMN model_provider_type
        TYPE model_provider_type_enum
        USING model_provider_type::model_provider_type_enum
        """
    )

    # 2. Add new values to scanner_type_enum
    op.execute("ALTER TYPE scanner_type_enum ADD VALUE IF NOT EXISTS 'pattern'")
    op.execute("ALTER TYPE scanner_type_enum ADD VALUE IF NOT EXISTS 'static_classifier'")

    # 3. Drop scanner_types column (array field, replaced by scanner_type enum)
    op.drop_column("guardrail_rule", "scanner_types")


def downgrade() -> None:
    # 1. Re-add scanner_types column
    op.add_column(
        "guardrail_rule",
        sa.Column("scanner_types", postgresql.ARRAY(sa.String()), nullable=True),
    )

    # 2. Cannot remove enum values in PostgreSQL, so we skip that

    # 3. Change model_provider_type back to String(50)
    op.execute(
        """
        ALTER TABLE guardrail_rule
        ALTER COLUMN model_provider_type
        TYPE VARCHAR(50)
        USING model_provider_type::text
        """
    )
