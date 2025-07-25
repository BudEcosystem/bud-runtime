"""added concurrency field to worker_info table.

Revision ID: 3e54b2221a62
Revises: c663e0764e12
Create Date: 2025-01-27 16:01:34.327572

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "3e54b2221a62"
down_revision: Union[str, None] = "c663e0764e12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade the database."""
    op.add_column("worker_info", sa.Column("concurrency", sa.Integer(), nullable=False, server_default="100"))


def downgrade() -> None:
    """Downgrade the database."""
    op.drop_column("worker_info", "concurrency")
