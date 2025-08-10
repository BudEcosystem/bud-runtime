"""Merge project_type migration branches

Revision ID: 3c1e5f3016b0
Revises: 20250806170226_6c153255, b6871a6a5429
Create Date: 2025-08-07 00:27:50.041933

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "3c1e5f3016b0"
down_revision: Union[str, None] = ("20250806170226_6c153255", "b6871a6a5429")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
