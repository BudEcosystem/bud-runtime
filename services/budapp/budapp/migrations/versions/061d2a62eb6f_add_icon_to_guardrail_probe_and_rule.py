"""add icon to guardrail_probe and guardrail_rule

Revision ID: 061d2a62eb6f
Revises: d4e5f6a7b8c9
Create Date: 2026-02-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "061d2a62eb6f"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable icon column to guardrail_probe and guardrail_rule tables."""
    op.add_column("guardrail_probe", sa.Column("icon", sa.String(), nullable=True))
    op.add_column("guardrail_rule", sa.Column("icon", sa.String(), nullable=True))


def downgrade() -> None:
    """Remove icon column from guardrail_probe and guardrail_rule tables."""
    op.drop_column("guardrail_rule", "icon")
    op.drop_column("guardrail_probe", "icon")
