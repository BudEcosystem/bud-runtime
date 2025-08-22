"""setting eval project to null

Revision ID: b265afde446b
Revises: cb7835c3be15
Create Date: 2025-08-21 01:59:23.682131

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b265afde446b"
down_revision: Union[str, None] = "cb7835c3be15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Minimal migration: allow NULL values for experiments.project_id
    op.alter_column("experiments", "project_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    # Revert: disallow NULL values for experiments.project_id
    op.alter_column("experiments", "project_id", existing_type=sa.UUID(), nullable=False)
