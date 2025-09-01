"""Add prompt and prompt_version tables with workflow enum

Revision ID: f5f6ee3eb2d6
Revises: b265afde446b
Create Date: 2025-08-20 06:08:58.690229

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from alembic_postgresql_enum import TableReference
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f5f6ee3eb2d6"
down_revision: Union[str, None] = "cc482aaabf0d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ENUMs for prompt tables
    sa.Enum("active", "deleted", name="prompt_version_status_enum").create(op.get_bind())
    sa.Enum("active", "deleted", name="prompt_status_enum").create(op.get_bind())
    sa.Enum("enabled", "disabled", "auto", "custom", name="rate_limit_type_enum").create(op.get_bind())
    sa.Enum("simple_prompt", name="prompt_type_enum").create(op.get_bind())

    # Create prompt table (without endpoint_id, model_id, cluster_id)
    op.create_table(
        "prompt",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "prompt_type", postgresql.ENUM("simple_prompt", name="prompt_type_enum", create_type=False), nullable=False
        ),
        sa.Column("auto_scale", sa.Boolean(), nullable=False),
        sa.Column("caching", sa.Boolean(), nullable=False),
        sa.Column("concurrency", postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column(
            "rate_limit_type",
            postgresql.ENUM("enabled", "disabled", "auto", "custom", name="rate_limit_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("rate_limit_value", sa.Integer(), nullable=True),
        sa.Column("default_version_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("active", "deleted", name="prompt_status_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["user.id"],
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create prompt_version table (with endpoint_id, model_id, cluster_id)
    op.create_table(
        "prompt_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("prompt_id", sa.Uuid(), nullable=False),
        sa.Column("endpoint_id", sa.Uuid(), nullable=False),
        sa.Column("model_id", sa.Uuid(), nullable=False),
        sa.Column("cluster_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("prompt_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("active", "deleted", name="prompt_version_status_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cluster_id"], ["cluster.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["user.id"],
        ),
        sa.ForeignKeyConstraint(["endpoint_id"], ["endpoint.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_id"], ["model.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prompt_id"], ["prompt.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prompt_id", "version", name="uq_prompt_version_prompt_id_version"),
    )

    # Add foreign key constraint for default_version_id (circular reference)
    op.create_foreign_key(
        "fk_prompt_default_version_id", "prompt", "prompt_version", ["default_version_id"], ["id"], ondelete="SET NULL"
    )

    # Add PROMPT_CREATION to workflow_type_enum
    op.sync_enum_values(
        enum_schema="public",
        enum_name="workflow_type_enum",
        new_values=[
            "model_deployment",
            "model_security_scan",
            "cluster_onboarding",
            "cluster_deletion",
            "endpoint_deletion",
            "endpoint_worker_deletion",
            "cloud_model_onboarding",
            "local_model_onboarding",
            "add_worker_to_endpoint",
            "license_faq_fetch",
            "local_model_quantization",
            "model_benchmark",
            "add_adapter",
            "delete_adapter",
            "evaluation_creation",
            "prompt_creation",
        ],
        affected_columns=[
            TableReference(
                table_schema="public",
                table_name="workflow",
                column_name="workflow_type",
            ),
        ],
    )


def downgrade() -> None:
    # Remove PROMPT_CREATION from workflow_type_enum
    op.sync_enum_values(
        enum_schema="public",
        enum_name="workflow_type_enum",
        new_values=[
            "model_deployment",
            "model_security_scan",
            "cluster_onboarding",
            "cluster_deletion",
            "endpoint_deletion",
            "endpoint_worker_deletion",
            "cloud_model_onboarding",
            "local_model_onboarding",
            "add_worker_to_endpoint",
            "license_faq_fetch",
            "local_model_quantization",
            "model_benchmark",
            "add_adapter",
            "delete_adapter",
            "evaluation_creation",
        ],
        affected_columns=[
            TableReference(
                table_schema="public",
                table_name="workflow",
                column_name="workflow_type",
            ),
        ],
    )

    # Drop foreign key constraint for default_version_id
    op.drop_constraint("fk_prompt_default_version_id", "prompt", type_="foreignkey")

    # Drop tables
    op.drop_table("prompt_version")
    op.drop_table("prompt")

    # Drop ENUMs
    sa.Enum("simple_prompt", name="prompt_type_enum").drop(op.get_bind())
    sa.Enum("enabled", "disabled", "auto", "custom", name="rate_limit_type_enum").drop(op.get_bind())
    sa.Enum("active", "deleted", name="prompt_status_enum").drop(op.get_bind())
    sa.Enum("active", "deleted", name="prompt_version_status_enum").drop(op.get_bind())
