"""Add pipeline definition table.

Revision ID: 002
Revises: 001
Create Date: 2026-01-16 14:00:00.000000

Creates the pipeline_definition table for persistent workflow storage and adds
pipeline_id foreign key to pipeline_execution for linking executions to their
definitions (002-pipeline-event-persistence).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create pipeline_definition table and add FK to pipeline_execution."""
    # Create pipeline_definition table
    op.create_table(
        "pipeline_definition",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Unique pipeline identifier",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
            comment="Optimistic locking version, incremented on each update",
        ),
        sa.Column(
            "name",
            sa.String(255),
            nullable=False,
            comment="Human-readable pipeline name",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Optional pipeline description",
        ),
        sa.Column(
            "dag_definition",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Complete pipeline DAG definition with steps, parameters, outputs",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="draft",
            comment="Current pipeline status (draft, active, archived)",
        ),
        sa.Column(
            "step_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Number of steps in the pipeline DAG",
        ),
        sa.Column(
            "created_by",
            sa.String(255),
            nullable=False,
            comment="User or service that created the pipeline",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Record creation time, immutable",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Last update time, auto-updated on modification",
        ),
        sa.CheckConstraint(
            "step_count >= 0",
            name="ck_pipeline_definition_step_count",
        ),
    )

    # Create indexes for pipeline_definition
    op.create_index(
        "idx_pipeline_definition_name",
        "pipeline_definition",
        ["name"],
    )
    op.create_index(
        "idx_pipeline_definition_status",
        "pipeline_definition",
        ["status"],
    )
    op.create_index(
        "idx_pipeline_definition_created_by",
        "pipeline_definition",
        ["created_by"],
    )
    op.create_index(
        "idx_pipeline_definition_created_at",
        "pipeline_definition",
        [sa.text("created_at DESC")],
    )

    # Add pipeline_id column to pipeline_execution
    op.add_column(
        "pipeline_execution",
        sa.Column(
            "pipeline_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Reference to parent pipeline definition (optional for legacy executions)",
        ),
    )

    # Create foreign key constraint
    op.create_foreign_key(
        "fk_pipeline_execution_pipeline_id_pipeline_definition",
        "pipeline_execution",
        "pipeline_definition",
        ["pipeline_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Create index for pipeline_id
    op.create_index(
        "idx_pipeline_execution_pipeline_id",
        "pipeline_execution",
        ["pipeline_id"],
    )


def downgrade() -> None:
    """Remove pipeline_definition table and FK from pipeline_execution."""
    # Drop index on pipeline_id
    op.drop_index(
        "idx_pipeline_execution_pipeline_id",
        table_name="pipeline_execution",
    )

    # Drop foreign key constraint
    op.drop_constraint(
        "fk_pipeline_execution_pipeline_id_pipeline_definition",
        "pipeline_execution",
        type_="foreignkey",
    )

    # Drop pipeline_id column from pipeline_execution
    op.drop_column("pipeline_execution", "pipeline_id")

    # Drop pipeline_definition table (drops indexes automatically)
    op.drop_table("pipeline_definition")
