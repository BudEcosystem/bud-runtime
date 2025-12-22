"""rename filename to file_name in dataset table

Revision ID: bf37ac5c03c7
Revises: 81ef7aa417d7
Create Date: 2025-12-15 07:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "bf37ac5c03c7"
down_revision: Union[str, None] = "81ef7aa417d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename filename column to file_name in dataset table."""
    op.alter_column("dataset", "filename", new_column_name="file_name")


def downgrade() -> None:
    """Rename file_name column back to filename in dataset table."""
    op.alter_column("dataset", "file_name", new_column_name="filename")
