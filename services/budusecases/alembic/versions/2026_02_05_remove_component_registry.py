"""Remove component registry tables and component_id FK.

Drop components and component_versions tables since BudModel serves
as the model catalog. Replace component_id FK on component_deployments
with a selected_component text column.

Revision ID: 0002
Revises:
Create Date: 2026-02-05
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add selected_component column
    op.add_column(
        "component_deployments",
        sa.Column("selected_component", sa.String(255), nullable=True),
    )

    # Migrate existing data: copy component name from components table if FK exists
    op.execute(
        """
        UPDATE component_deployments cd
        SET selected_component = c.name
        FROM components c
        WHERE cd.component_id = c.id
        """
    )

    # Drop the foreign key constraint and column
    op.drop_constraint(
        "component_deployments_component_id_fkey",
        "component_deployments",
        type_="foreignkey",
    )
    op.drop_column("component_deployments", "component_id")

    # Drop component registry tables
    op.drop_table("component_versions")
    op.drop_table("components")


def downgrade() -> None:
    # Recreate components table
    op.create_table(
        "components",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("component_type", sa.String(50), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(500), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("config", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("metadata", postgresql.JSON(), nullable=True, server_default="{}"),
        sa.Column("tags", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "modified_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("name", "component_type", name="uq_component_name_type"),
    )

    # Recreate component_versions table
    op.create_table(
        "component_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "component_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("components.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("source_version", sa.String(255), nullable=True),
        sa.Column("config", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("is_default", sa.Boolean(), nullable=False, default=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("component_id", "version", name="uq_component_version"),
    )

    # Re-add component_id column and FK
    op.add_column(
        "component_deployments",
        sa.Column("component_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "component_deployments_component_id_fkey",
        "component_deployments",
        "components",
        ["component_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Drop selected_component column
    op.drop_column("component_deployments", "selected_component")
