"""Add a2a_contexts table for A2A protocol conversation persistence.

Revision ID: a2a1_add_a2a_contexts
Revises: d1a594c32280
Create Date: 2026-03-13

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a2a1_add_a2a_contexts"
down_revision: Union[str, None] = "d1a594c32280"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create a2a_contexts table and indexes."""
    op.create_table(
        "a2a_contexts",
        sa.Column("context_id", sa.String(255), primary_key=True),
        sa.Column("agent_id", sa.String(255), nullable=True),
        sa.Column("messages", sa.Text, nullable=False, server_default="[]"),
        sa.Column("message_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_a2a_contexts_agent_id", "a2a_contexts", ["agent_id"])
    op.create_index("idx_a2a_contexts_modified_at", "a2a_contexts", ["modified_at"])


def downgrade() -> None:
    """Drop a2a_contexts table and indexes."""
    op.drop_index("idx_a2a_contexts_modified_at", table_name="a2a_contexts")
    op.drop_index("idx_a2a_contexts_agent_id", table_name="a2a_contexts")
    op.drop_table("a2a_contexts")
