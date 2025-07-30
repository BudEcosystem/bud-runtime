"""merge_heads_033bac35a684_and_34c89ff1662c

Revision ID: f826784fa103
Revises: 033bac35a684, 34c89ff1662c
Create Date: 2025-07-25 22:43:54.401618

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f826784fa103"
down_revision: Union[str, None] = ("033bac35a684", "34c89ff1662c")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
