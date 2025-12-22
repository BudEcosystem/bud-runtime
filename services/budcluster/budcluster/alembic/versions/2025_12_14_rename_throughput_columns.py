"""Rename throughput columns to match llm_benchmark output.

Revision ID: 7a8b9c0d1e2f
Revises: 2025_12_03_add_error_status_to_enum
Create Date: 2025-12-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7a8b9c0d1e2f"
down_revision: str | None = "7gh1jig903fj"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename throughput columns and add mean_output_throughput_per_user."""
    # Rename throughput columns to match llm_benchmark output format
    op.alter_column("benchmark_result", "p25_throughput", new_column_name="p25_output_throughput_per_user")
    op.alter_column("benchmark_result", "p75_throughput", new_column_name="p75_output_throughput_per_user")
    op.alter_column("benchmark_result", "p95_throughput", new_column_name="p95_output_throughput_per_user")
    op.alter_column("benchmark_result", "p99_throughput", new_column_name="p99_output_throughput_per_user")
    op.alter_column("benchmark_result", "min_throughput", new_column_name="min_output_throughput_per_user")
    op.alter_column("benchmark_result", "max_throughput", new_column_name="max_output_throughput_per_user")

    # Add new mean_output_throughput_per_user column
    op.add_column("benchmark_result", sa.Column("mean_output_throughput_per_user", sa.Float(), nullable=True))


def downgrade() -> None:
    """Revert throughput column renames and remove mean_output_throughput_per_user."""
    # Remove mean_output_throughput_per_user column
    op.drop_column("benchmark_result", "mean_output_throughput_per_user")

    # Rename columns back to original names
    op.alter_column("benchmark_result", "p25_output_throughput_per_user", new_column_name="p25_throughput")
    op.alter_column("benchmark_result", "p75_output_throughput_per_user", new_column_name="p75_throughput")
    op.alter_column("benchmark_result", "p95_output_throughput_per_user", new_column_name="p95_throughput")
    op.alter_column("benchmark_result", "p99_output_throughput_per_user", new_column_name="p99_throughput")
    op.alter_column("benchmark_result", "min_output_throughput_per_user", new_column_name="min_throughput")
    op.alter_column("benchmark_result", "max_output_throughput_per_user", new_column_name="max_throughput")
