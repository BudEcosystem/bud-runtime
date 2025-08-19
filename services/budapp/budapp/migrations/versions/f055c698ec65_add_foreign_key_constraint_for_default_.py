"""Add foreign key constraint for default_version_id

Revision ID: f055c698ec65
Revises: 601f108926d4
Create Date: 2025-08-19 07:48:38.630873

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f055c698ec65"
down_revision: Union[str, None] = "601f108926d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add foreign key constraint for default_version_id to prompt_version table
    # Using use_alter=True to handle circular dependency
    op.create_foreign_key(
        "fk_prompt_default_version_id",
        "prompt",
        "prompt_version",
        ["default_version_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )


def downgrade() -> None:
    # Remove the foreign key constraint
    op.drop_constraint("fk_prompt_default_version_id", "prompt", type_="foreignkey")
