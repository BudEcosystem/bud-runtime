"""remove_runs_model_id_foreign_key

Revision ID: 6e52243f9731
Revises: f39423ac0627
Create Date: 2025-07-18 05:39:01.902817

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "6e52243f9731"
down_revision: Union[str, None] = "f39423ac0627"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the foreign key constraint between runs.model_id and exp_models.id
    # This allows model_id to reference models from external systems
    op.drop_constraint("runs_model_id_fkey", "runs", type_="foreignkey")


def downgrade() -> None:
    # Re-add the foreign key constraint (for rollback purposes)
    op.create_foreign_key("runs_model_id_fkey", "runs", "exp_models", ["model_id"], ["id"])
