"""empty message

Revision ID: f01f988c0272
Revises: 9f3c2b1a4d5e, be1c6d69cfa5
Create Date: 2026-01-23 10:53:10.539881

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f01f988c0272"
down_revision: Union[str, None] = ("9f3c2b1a4d5e", "be1c6d69cfa5")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
