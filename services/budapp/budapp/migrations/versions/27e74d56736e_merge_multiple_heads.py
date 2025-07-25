"""merge multiple heads.

Revision ID: 27e74d56736e
Revises: 0b6d913f9225, 8d0eb1788e1b
Create Date: 2025-04-04 06:59:10.561318

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "27e74d56736e"
down_revision: Union[str, None] = ("0b6d913f9225", "8d0eb1788e1b")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
