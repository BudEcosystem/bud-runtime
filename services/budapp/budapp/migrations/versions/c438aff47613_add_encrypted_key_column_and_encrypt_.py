"""Add encrypted_key column and encrypt credentials

Revision ID: c438aff47613
Revises: 6bce128f07e1
Create Date: 2025-08-22 18:12:02.238311

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "c438aff47613"
down_revision: Union[str, None] = "6bce128f07e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add encrypted_key column to credential table
    op.add_column("credential", sa.Column("encrypted_key", sa.String(), nullable=True))

    # Add encrypted_credential column to cloud_credentials table
    op.add_column("cloud_credentials", sa.Column("encrypted_credential", JSONB, nullable=True))

    # Note: After deployment, run the data migration script to encrypt existing keys
    # Then make encrypted_key NOT NULL and drop the plain key column


def downgrade() -> None:
    # Remove encrypted columns
    op.drop_column("credential", "encrypted_key")
    op.drop_column("cloud_credentials", "encrypted_credential")
