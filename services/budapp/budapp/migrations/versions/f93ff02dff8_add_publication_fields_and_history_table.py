"""add publication fields and history table

Revision ID: f93ff02dff8
Revises: 375eb22cb3af
Create Date: 2025-07-28 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f93ff02dff8"
down_revision: Union[str, None] = "375eb22cb3af"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add publication fields to endpoint table
    op.add_column("endpoint", sa.Column("is_published", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("endpoint", sa.Column("published_date", sa.DateTime(), nullable=True))
    op.add_column("endpoint", sa.Column("published_by", sa.UUID(), nullable=True))

    # Create foreign key for published_by
    op.create_foreign_key("fk_endpoint_published_by_user", "endpoint", "user", ["published_by"], ["id"])

    # Create publication_history table
    op.create_table(
        "publication_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deployment_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("performed_by", sa.UUID(), nullable=False),
        sa.Column("performed_at", sa.DateTime(), nullable=False),
        sa.Column("action_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("previous_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("modified_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["deployment_id"], ["endpoint.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["performed_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for better query performance
    op.create_index("ix_endpoint_is_published", "endpoint", ["is_published"])
    op.create_index("ix_endpoint_is_published_published_date", "endpoint", ["is_published", "published_date"])
    op.create_index("ix_publication_history_deployment_id", "publication_history", ["deployment_id"])
    op.create_index("ix_publication_history_performed_at", "publication_history", ["performed_at"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_publication_history_performed_at", table_name="publication_history")
    op.drop_index("ix_publication_history_deployment_id", table_name="publication_history")
    op.drop_index("ix_endpoint_is_published_published_date", table_name="endpoint")
    op.drop_index("ix_endpoint_is_published", table_name="endpoint")

    # Drop publication_history table
    op.drop_table("publication_history")

    # Drop foreign key constraint
    op.drop_constraint("fk_endpoint_published_by_user", "endpoint", type_="foreignkey")

    # Drop columns from endpoint table
    op.drop_column("endpoint", "published_by")
    op.drop_column("endpoint", "published_date")
    op.drop_column("endpoint", "is_published")
