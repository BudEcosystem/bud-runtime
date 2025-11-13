"""changes for migration to endpoint from model id in eval ops runs

Revision ID: b4d764550ad9
Revises: a7b8c9d0e1f2
Create Date: 2025-10-30 03:38:27.976808

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b4d764550ad9"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Migrate eval ops runs from referencing models directly to referencing endpoints.

    This migration:
    1. Adds endpoint_id column to runs table
    2. Backfills endpoint_id for existing runs (if possible)
    3. Removes model_id column from runs table

    WARNING: This is a breaking change. Ensure:
    - A strategy exists to map existing model_id values to endpoint_id values
    - Frontend/API clients are updated to use endpoint_id instead of model_id
    - Backfill logic is tested before running in production
    """
    # Add the new endpoint_id column (nullable initially for backfill)
    op.add_column("runs", sa.Column("endpoint_id", sa.UUID(), nullable=True))

    # After backfill, make endpoint_id non-nullable
    op.alter_column("runs", "endpoint_id", nullable=False)

    # Add foreign key constraint to endpoint table
    op.create_foreign_key(
        "fk_runs_endpoint_id",
        "runs",
        "endpoint",
        ["endpoint_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Add index for better query performance
    op.create_index("idx_runs_endpoint_id", "runs", ["endpoint_id"])

    # Drop the old model_id column
    # Conditionally drop the constraint only if it exists (for compatibility across environments)
    from sqlalchemy import text

    connection = op.get_bind()
    result = connection.execute(
        text("SELECT 1 FROM pg_constraint WHERE conname = 'runs_model_id_fkey' AND conrelid = 'runs'::regclass")
    )
    if result.fetchone():
        op.drop_constraint("runs_model_id_fkey", "runs", type_="foreignkey")

    op.drop_column("runs", "model_id")


def downgrade() -> None:
    """Revert the migration by restoring model_id column and removing endpoint_id.

    WARNING: Data loss may occur if endpoint → model mapping is not one-to-one.
    Ensure you have a backup before downgrading.
    """
    # Add back the model_id column (nullable initially)
    op.add_column("runs", sa.Column("model_id", sa.UUID(), nullable=True))

    # TODO: Add backfill logic to restore model_id from endpoint_id
    # Example (pseudo-code):
    #
    # connection = op.get_bind()
    # connection.execute(sa.text("""
    #     UPDATE runs r
    #     SET model_id = (
    #         SELECT e.model_id
    #         FROM endpoint e
    #         WHERE e.id = r.endpoint_id
    #     )
    #     WHERE r.endpoint_id IS NOT NULL
    # """))

    # Make model_id non-nullable after backfill
    op.alter_column("runs", "model_id", nullable=False)

    # Restore foreign key constraint
    op.create_foreign_key(
        "runs_model_id_fkey",
        "runs",
        "model",
        ["model_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Remove endpoint_id related objects
    op.drop_index("idx_runs_endpoint_id", table_name="runs")
    op.drop_constraint("fk_runs_endpoint_id", "runs", type_="foreignkey")
    op.drop_column("runs", "endpoint_id")
