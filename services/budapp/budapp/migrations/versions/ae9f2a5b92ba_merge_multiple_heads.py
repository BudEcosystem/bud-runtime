"""Merge multiple heads.

Revision ID: ae9f2a5b92ba
Revises: 2278bdce773d, cb1af702f194
Create Date: 2025-04-22 00:55:04.980612

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "ae9f2a5b92ba"
down_revision: Union[str, None] = ("2278bdce773d", "cb1af702f194")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
