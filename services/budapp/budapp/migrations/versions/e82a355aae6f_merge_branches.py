"""Merge branches

Revision ID: e82a355aae6f
Revises: 5f8cf497ed7b, f93ff02dff8
Create Date: 2025-07-29 01:47:59.080310

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e82a355aae6f'
down_revision: Union[str, None] = ('5f8cf497ed7b', 'f93ff02dff8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
