"""worker_status_enum update.

Revision ID: c663e0764e12
Revises: 61ec9c92298f
Create Date: 2025-01-21 13:40:10.978695

"""

from typing import Sequence, Union

from alembic import op
from alembic_postgresql_enum import TableReference


# revision identifiers, used by Alembic.
revision: str = "c663e0764e12"
down_revision: Union[str, None] = "61ec9c92298f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade the database."""
    op.sync_enum_values(
        "public",
        "worker_status_enum",
        ["Pending", "Running", "Succeeded", "Failed", "Unknown", "Deleting"],
        [TableReference(table_schema="public", table_name="worker_info", column_name="status")],
        enum_values_to_rename=[],
    )


def downgrade() -> None:
    """Downgrade the database."""
    op.sync_enum_values(
        "public",
        "worker_status_enum",
        ["Pending", "Running", "Succeeded", "Failed", "Unknown"],
        [TableReference(table_schema="public", table_name="worker_info", column_name="status")],
        enum_values_to_rename=[],
    )
