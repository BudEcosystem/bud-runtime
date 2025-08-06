"""Merge divergent heads

Revision ID: b6871a6a5429
Revises: 14101fc4400d, 20250730155527
Create Date: 2025-08-05 06:34:54.302065

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b6871a6a5429"
down_revision: Union[str, None] = ("14101fc4400d", "20250730155527")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
