"""rename updated_at to modified_at in eval_tags

Revision ID: a7b8c9d0e1f2
Revises: 65fad5430d50
Create Date: 2025-10-27 04:23:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "65fad5430d50"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename updated_at column to modified_at to match codebase standard
    op.alter_column(
        "eval_tags",
        "updated_at",
        new_column_name="modified_at",
    )


def downgrade() -> None:
    # Rename modified_at back to updated_at
    op.alter_column(
        "eval_tags",
        "modified_at",
        new_column_name="updated_at",
    )
