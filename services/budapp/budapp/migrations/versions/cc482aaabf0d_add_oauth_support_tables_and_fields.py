#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""Add OAuth support - tables and fields for SSO integration

Revision ID: cc482aaabf0d
Revises: 7c028d42c0df
Create Date: 2025-07-31 15:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "cc482aaabf0d"
down_revision: Union[str, None] = "7c028d42c0df"  # Need to be updated to new
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add auth_providers JSONB column to user table
    op.add_column("user", sa.Column("auth_providers", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Create index for auth_providers
    op.create_index("idx_users_auth_providers", "user", [sa.text("auth_providers")], postgresql_using="gin")

    # Create oauth_sessions table
    op.create_table(
        "oauth_sessions",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("user_id", postgresql.UUID(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("state", sa.String(length=255), nullable=False),
        sa.Column("code_verifier", sa.String(length=128), nullable=True),
        sa.Column("redirect_uri", sa.Text(), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state"),
    )
    op.create_index(op.f("ix_oauth_sessions_id"), "oauth_sessions", ["id"], unique=False)

    # Create tenant_oauth_configs table
    op.create_table(
        "tenant_oauth_configs",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_secret_encrypted", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=True),
        sa.Column("allowed_domains", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("auto_create_users", sa.Boolean(), nullable=True),
        sa.Column("config_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tenant_oauth_configs_id"), "tenant_oauth_configs", ["id"], unique=False)

    # Create user_oauth_providers table
    op.create_table(
        "user_oauth_providers",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("user_id", postgresql.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("provider_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("linked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_oauth_providers_id"), "user_oauth_providers", ["id"], unique=False)
    op.create_index(
        "idx_user_oauth_providers_user_provider", "user_oauth_providers", ["user_id", "provider"], unique=True
    )


def downgrade() -> None:
    # Drop user_oauth_providers table
    op.drop_index("idx_user_oauth_providers_user_provider", table_name="user_oauth_providers")
    op.drop_index(op.f("ix_user_oauth_providers_id"), table_name="user_oauth_providers")
    op.drop_table("user_oauth_providers")

    # Drop tenant_oauth_configs table
    op.drop_index(op.f("ix_tenant_oauth_configs_id"), table_name="tenant_oauth_configs")
    op.drop_table("tenant_oauth_configs")

    # Drop oauth_sessions table
    op.drop_index(op.f("ix_oauth_sessions_id"), table_name="oauth_sessions")
    op.drop_table("oauth_sessions")

    # Drop auth_providers column and index from user table
    op.drop_index("idx_users_auth_providers", table_name="user")
    op.drop_column("user", "auth_providers")
