"""add_guardrail_model_fields

Revision ID: be1c6d69cfa5
Revises: 42c894042a04
Create Date: 2025-01-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "be1c6d69cfa5"
down_revision: Union[str, None] = "42c894042a04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create new enum types
    probe_type_enum = postgresql.ENUM(
        "provider",
        "model_scanner",
        "custom",
        name="probe_type_enum",
        create_type=False,
    )
    probe_type_enum.create(op.get_bind(), checkfirst=True)

    scanner_type_enum = postgresql.ENUM(
        "classifier",
        "llm",
        name="scanner_type_enum",
        create_type=False,
    )
    scanner_type_enum.create(op.get_bind(), checkfirst=True)

    # Add probe_type to guardrail_probe
    op.add_column(
        "guardrail_probe",
        sa.Column(
            "probe_type",
            postgresql.ENUM(
                "provider",
                "model_scanner",
                "custom",
                name="probe_type_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="provider",
        ),
    )

    # Add model fields to guardrail_rule
    op.add_column(
        "guardrail_rule",
        sa.Column(
            "scanner_type",
            postgresql.ENUM(
                "classifier",
                "llm",
                name="scanner_type_enum",
                create_type=False,
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "guardrail_rule",
        sa.Column("model_uri", sa.String(255), nullable=True),
    )
    op.add_column(
        "guardrail_rule",
        sa.Column("model_provider_type", sa.String(50), nullable=True),
    )
    op.add_column(
        "guardrail_rule",
        sa.Column("is_gated", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "guardrail_rule",
        sa.Column("model_config_json", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "guardrail_rule",
        sa.Column("model_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Add foreign key for model_id
    op.create_foreign_key(
        "fk_guardrail_rule_model_id",
        "guardrail_rule",
        "model",
        ["model_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Create guardrail_rule_deployment table
    op.create_table(
        "guardrail_rule_deployment",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "guardrail_deployment_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "rule_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "model_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "endpoint_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "cluster_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "config_override_json",
            postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "modified_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["guardrail_deployment_id"],
            ["guardrail_deployment.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["guardrail_rule.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["model.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["endpoint_id"],
            ["endpoint.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["cluster.id"],
            ondelete="CASCADE",
        ),
    )

    # Create indexes
    op.create_index(
        "idx_guardrail_rule_deployment_deployment",
        "guardrail_rule_deployment",
        ["guardrail_deployment_id"],
    )
    op.create_index(
        "idx_guardrail_rule_deployment_rule",
        "guardrail_rule_deployment",
        ["rule_id"],
    )
    op.create_index(
        "idx_guardrail_rule_deployment_endpoint",
        "guardrail_rule_deployment",
        ["endpoint_id"],
    )


def downgrade() -> None:
    # Drop guardrail_rule_deployment table
    op.drop_index("idx_guardrail_rule_deployment_endpoint", "guardrail_rule_deployment")
    op.drop_index("idx_guardrail_rule_deployment_rule", "guardrail_rule_deployment")
    op.drop_index("idx_guardrail_rule_deployment_deployment", "guardrail_rule_deployment")
    op.drop_table("guardrail_rule_deployment")

    # Drop model fields from guardrail_rule
    op.drop_constraint("fk_guardrail_rule_model_id", "guardrail_rule", type_="foreignkey")
    op.drop_column("guardrail_rule", "model_id")
    op.drop_column("guardrail_rule", "model_config_json")
    op.drop_column("guardrail_rule", "is_gated")
    op.drop_column("guardrail_rule", "model_provider_type")
    op.drop_column("guardrail_rule", "model_uri")
    op.drop_column("guardrail_rule", "scanner_type")

    # Drop probe_type from guardrail_probe
    op.drop_column("guardrail_probe", "probe_type")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS scanner_type_enum")
    op.execute("DROP TYPE IF EXISTS probe_type_enum")
