"""Merge heads 056eebcf35b0 and e82a355aae6f

Revision ID: 14101fc4400d
Revises: 056eebcf35b0, e82a355aae6f
Create Date: 2025-07-30 08:10:15.252839

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '14101fc4400d'
down_revision: Union[str, None] = ('056eebcf35b0', 'e82a355aae6f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
