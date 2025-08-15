"""Add performance indexes for simulation_results JSONB queries

Revision ID: 2f9d64e993a7
Revises: 9bcbbad43111
Create Date: 2025-08-14 12:27:03.715080

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f9d64e993a7'
down_revision: Union[str, None] = '9bcbbad43111'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Note: CONCURRENT index creation requires running outside of a transaction
    # We'll create regular indexes instead for this migration

    # Add composite index for workflow_id and cluster_id (most common query pattern)
    op.create_index(
        'idx_simulation_results_workflow_cluster',
        'simulation_results',
        ['workflow_id', 'cluster_id']
    )

    # Add expression index for the commonly extracted cost_per_million_tokens as float
    # This is more efficient than GIN indexes for direct comparison queries
    op.execute("""
        CREATE INDEX idx_simulation_results_cost_float
        ON simulation_results (CAST(top_k_configs->>'cost_per_million_tokens' AS FLOAT))
        WHERE top_k_configs IS NOT NULL
    """)

    # Add expression index for error_rate as float
    op.execute("""
        CREATE INDEX idx_simulation_results_error_float
        ON simulation_results (CAST(top_k_configs->>'error_rate' AS FLOAT))
        WHERE top_k_configs IS NOT NULL
    """)

    # Add composite index on workflow_id + error_rate for common filter pattern
    op.execute("""
        CREATE INDEX idx_simulation_results_workflow_error
        ON simulation_results (workflow_id, CAST(top_k_configs->>'error_rate' AS FLOAT))
        WHERE top_k_configs IS NOT NULL
    """)


def downgrade() -> None:
    # Drop the indexes in reverse order
    op.execute("DROP INDEX IF EXISTS idx_simulation_results_workflow_error")
    op.execute("DROP INDEX IF EXISTS idx_simulation_results_error_float")
    op.execute("DROP INDEX IF EXISTS idx_simulation_results_cost_float")
    op.drop_index('idx_simulation_results_workflow_cluster')
