"""add_cores_column_to_simulation_results

Revision ID: a1b2c3d4e5f6
Revises: 9b9a54bf4a03
Create Date: 2025-11-28 10:55:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9b9a54bf4a03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add cores column to simulation_results table for CPU/cpu_high devices
    op.add_column("simulation_results", sa.Column("cores", sa.Integer(), nullable=True))


def downgrade() -> None:
    # Remove cores column from simulation_results table
    op.drop_column("simulation_results", "cores")
