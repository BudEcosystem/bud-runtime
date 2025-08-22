"""Merge divergent branches

Revision ID: 6bce128f07e1
Revises: 59f0ac264062, b265afde446b
Create Date: 2025-08-22 15:20:03.285176

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "6bce128f07e1"
down_revision: Union[str, None] = ("59f0ac264062", "b265afde446b")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
