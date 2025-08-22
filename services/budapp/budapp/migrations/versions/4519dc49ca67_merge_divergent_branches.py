"""merge_divergent_branches

Revision ID: 4519dc49ca67
Revises: 65c3cfbe96c9, 6bce128f07e1
Create Date: 2025-08-22 20:37:19.099349

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4519dc49ca67'
down_revision: Union[str, None] = ('d13556621f8a', '65c3cfbe96c9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
