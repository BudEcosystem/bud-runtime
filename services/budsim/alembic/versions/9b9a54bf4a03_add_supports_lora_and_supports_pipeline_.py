"""add_supports_lora_and_supports_pipeline_parallelism_to_simulation_results

Revision ID: 9b9a54bf4a03
Revises: d35ab45bd4ac
Create Date: 2025-11-04 06:57:11.094671

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b9a54bf4a03'
down_revision: Union[str, None] = 'd35ab45bd4ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add supports_lora column
    op.add_column('simulation_results',
        sa.Column('supports_lora', sa.Boolean(), nullable=True, server_default='false'))

    # Add supports_pipeline_parallelism column
    op.add_column('simulation_results',
        sa.Column('supports_pipeline_parallelism', sa.Boolean(), nullable=True, server_default='false'))


def downgrade() -> None:
    # Drop columns in reverse order
    op.drop_column('simulation_results', 'supports_pipeline_parallelism')
    op.drop_column('simulation_results', 'supports_lora')
