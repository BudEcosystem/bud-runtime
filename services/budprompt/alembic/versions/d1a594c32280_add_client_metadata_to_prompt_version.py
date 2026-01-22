"""add client_metadata to prompt_version

Revision ID: d1a594c32280
Revises: 0c908571c791
Create Date: 2026-01-16 06:29:28.579581

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd1a594c32280'
down_revision: Union[str, None] = '0c908571c791'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'prompt_version',
        sa.Column('client_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}')
    )


def downgrade() -> None:
    op.drop_column('prompt_version', 'client_metadata')
