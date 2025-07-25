"""merge multiple heads.

Revision ID: 1da691d14fd0
Revises: 6cf9d37da8a5, e9f810852a5d
Create Date: 2025-03-24 09:46:13.067688

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "1da691d14fd0"
down_revision: Union[str, None] = ("6cf9d37da8a5", "e9f810852a5d")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
