"""add_credential_type_and_ip_whitelist

Revision ID: 47f73a835ad9
Revises: c82d259d07ce
Create Date: 2025-08-04 17:36:21.911783

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "47f73a835ad9"
down_revision: Union[str, None] = "c82d259d07ce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the API credential type enum
    op.execute("CREATE TYPE api_credential_type_enum AS ENUM ('client_app', 'admin_app')")

    # Add new columns to credential table
    op.add_column(
        "credential",
        sa.Column(
            "credential_type",
            sa.Enum("client_app", "admin_app", name="api_credential_type_enum"),
            nullable=False,
            server_default="client_app",
        ),
    )
    op.add_column("credential", sa.Column("ip_whitelist", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Create indexes for better performance
    op.create_index("ix_credential_credential_type", "credential", ["credential_type"])
    op.create_index("ix_credential_hashed_key", "credential", ["hashed_key"])

    # Remove the server default after setting all existing rows
    op.alter_column("credential", "credential_type", server_default=None)


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_credential_hashed_key", table_name="credential")
    op.drop_index("ix_credential_credential_type", table_name="credential")

    # Remove columns
    op.drop_column("credential", "ip_whitelist")
    op.drop_column("credential", "credential_type")

    # Drop the enum type
    op.execute("DROP TYPE api_credential_type_enum")
