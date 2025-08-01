"""name removed in cluster model.

Revision ID: 276d4815b7e8
Revises: f502efba4ac3
Create Date: 2024-12-06 15:40:36.778427

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "276d4815b7e8"
down_revision: Union[str, None] = "f502efba4ac3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade the database."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("cluster", schema=None) as batch_op:
        batch_op.drop_column("name")

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade the database."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("cluster", schema=None) as batch_op:
        batch_op.add_column(sa.Column("name", sa.VARCHAR(), autoincrement=False, nullable=False))

    # ### end Alembic commands ###
