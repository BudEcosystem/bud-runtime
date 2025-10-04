"""add_device_model_and_raw_name_to_simulation_results

Revision ID: d35ab45bd4ac
Revises: 7e31f2b8c4d9
Create Date: 2025-09-30 11:20:07.075213

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d35ab45bd4ac"
down_revision: Union[str, None] = "7e31f2b8c4d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add device_model and raw_name columns to simulation_results table
    op.add_column("simulation_results", sa.Column("device_model", sa.String(255), nullable=True))
    op.add_column("simulation_results", sa.Column("raw_name", sa.String(255), nullable=True))


def downgrade() -> None:
    # Remove device_model and raw_name columns from simulation_results table
    op.drop_column("simulation_results", "raw_name")
    op.drop_column("simulation_results", "device_model")
