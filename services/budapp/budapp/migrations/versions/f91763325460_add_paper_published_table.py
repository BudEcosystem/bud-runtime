"""add paper published table.

Revision ID: f91763325460
Revises: f759834112e2
Create Date: 2024-11-04 17:55:27.987795

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f91763325460"
down_revision: Union[str, None] = "f759834112e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "paper_published",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("model_id", sa.Uuid(), sa.ForeignKey("model.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("modified_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("paper_published")
