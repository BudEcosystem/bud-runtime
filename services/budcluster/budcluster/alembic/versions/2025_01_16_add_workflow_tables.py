"""add workflow tables.

Revision ID: 61ec9c92298f
Revises: 93e068c23299
Create Date: 2025-01-16 10:17:30.518880

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "61ec9c92298f"
down_revision: Union[str, None] = "93e068c23299"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade the database."""
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("workflow_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.String(length=255), nullable=True),
        sa.Column("notification_status", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("num_retries", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id"),
    )
    op.create_table(
        "workflow_steps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("step_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("notification_status", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("num_retries", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_runs.workflow_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade the database."""
    op.drop_table("workflow_steps")
    op.drop_table("workflow_runs")
