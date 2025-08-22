"""Finalize encrypted credentials - remove plain columns

Revision ID: 65c3cfbe96c9
Revises: c438aff47613
Create Date: 2025-08-22 18:44:14.026275

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "65c3cfbe96c9"
down_revision: Union[str, None] = "c438aff47613"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make encrypted_key NOT NULL since all credentials should now be encrypted
    op.alter_column("credential", "encrypted_key", existing_type=sa.String(), nullable=False)

    # Make encrypted_credential NOT NULL since all cloud credentials should now be encrypted
    op.alter_column("cloud_credentials", "encrypted_credential", existing_type=JSONB, nullable=False)

    # Drop the plain key column - no longer needed
    op.drop_column("credential", "key")

    # Drop the plain credential column - no longer needed
    op.drop_column("cloud_credentials", "credential")


def downgrade() -> None:
    # Re-add the plain columns for rollback capability
    op.add_column("credential", sa.Column("key", sa.String(), nullable=True, unique=True))
    op.add_column("cloud_credentials", sa.Column("credential", JSONB, nullable=True))

    # Make encrypted columns nullable again
    op.alter_column("credential", "encrypted_key", existing_type=sa.String(), nullable=True)

    op.alter_column("cloud_credentials", "encrypted_credential", existing_type=JSONB, nullable=True)
