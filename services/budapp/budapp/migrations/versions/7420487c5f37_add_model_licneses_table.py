"""add model licneses table.

Revision ID: 7420487c5f37
Revises: f91763325460
Create Date: 2024-11-04 18:01:06.341718

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7420487c5f37"
down_revision: Union[str, None] = "f91763325460"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "model_licenses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("path", sa.String(), nullable=True),
        sa.Column("model_id", sa.Uuid(), sa.ForeignKey("model.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("modified_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("model_licenses")
