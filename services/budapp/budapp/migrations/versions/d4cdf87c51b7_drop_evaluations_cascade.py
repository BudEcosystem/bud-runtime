"""drop_evaluations_cascade

Revision ID: d4cdf87c51b7
Revises: d9d86856930b
Create Date: 2025-07-18 03:10:13.739170

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d4cdf87c51b7"
down_revision: Union[str, None] = "d9d86856930b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop evaluations table with CASCADE to remove all dependencies
    op.execute("DROP TABLE evaluations CASCADE")

    # Drop the evaluation_status_enum
    op.execute("DROP TYPE evaluation_status_enum")


def downgrade() -> None:
    pass
