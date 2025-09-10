"""add_unique_constraint_experiment_name_per_user

Revision ID: b8f6b3853ed0
Revises: 7c028d42c0df
Create Date: 2025-08-26 04:52:46.653322

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b8f6b3853ed0"
down_revision: Union[str, None] = "7c028d42c0df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # First, rename duplicate experiment names by appending a number
    # This ensures we can create the unique constraint
    op.execute("""
        WITH duplicates AS (
            SELECT id, name, created_by,
                   ROW_NUMBER() OVER (PARTITION BY name, created_by ORDER BY created_at) AS rn
            FROM experiments
            WHERE status != 'deleted'
        )
        UPDATE experiments
        SET name = CONCAT(experiments.name, ' (', duplicates.rn, ')')
        FROM duplicates
        WHERE experiments.id = duplicates.id
        AND duplicates.rn > 1;
    """)

    # Add unique constraint on (name, created_by) for non-deleted experiments
    # This ensures each user has unique experiment names
    # Using partial unique index for PostgreSQL
    op.execute("""
        CREATE UNIQUE INDEX uq_experiment_name_created_by
        ON experiments (name, created_by)
        WHERE status != 'deleted'
    """)

    # Add index on name column for faster lookups
    op.create_index("idx_experiment_name", "experiments", ["name"], unique=False)


def downgrade() -> None:
    # Remove the index
    op.drop_index("idx_experiment_name", table_name="experiments")

    # Remove the unique constraint (drop as index since we created it as an index)
    op.drop_index("uq_experiment_name_created_by", table_name="experiments")
