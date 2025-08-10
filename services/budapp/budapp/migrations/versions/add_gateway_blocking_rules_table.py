"""Add gateway blocking rules table

Revision ID: add_gateway_blocking_rules
Revises: 5eb2774a802e
Create Date: 2025-08-04 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "add_gateway_blocking_rules"
down_revision = "5eb2774a802e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create blocking rule type enum
    op.execute(
        "CREATE TYPE blocking_rule_type_enum AS ENUM ('ip_blocking', 'country_blocking', 'user_agent_blocking', 'rate_based_blocking')"
    )

    # Create blocking rule status enum
    op.execute("CREATE TYPE blocking_rule_status_enum AS ENUM ('active', 'inactive', 'expired')")

    # Create gateway_blocking_rule table
    op.create_table(
        "gateway_blocking_rule",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column(
            "rule_type",
            postgresql.ENUM(
                "ip_blocking",
                "country_blocking",
                "user_agent_blocking",
                "rate_based_blocking",
                name="blocking_rule_type_enum",
            ),
            nullable=False,
        ),
        sa.Column("rule_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("active", "inactive", "expired", name="blocking_rule_status_enum"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("endpoint_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("match_count", sa.Integer(), nullable=False),
        sa.Column("last_matched_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], name=op.f("fk_gateway_blocking_rule_created_by_user")),
        sa.ForeignKeyConstraint(
            ["endpoint_id"], ["endpoint.id"], name=op.f("fk_gateway_blocking_rule_endpoint_id_endpoint")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_gateway_blocking_rule_project_id_project")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gateway_blocking_rule")),
    )

    # Create indexes
    op.create_index(
        "idx_blocking_rule_project_status", "gateway_blocking_rule", ["project_id", "status"], unique=False
    )
    op.create_index("idx_blocking_rule_type_status", "gateway_blocking_rule", ["rule_type", "status"], unique=False)
    op.create_index("idx_blocking_rule_endpoint", "gateway_blocking_rule", ["endpoint_id"], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index("idx_blocking_rule_endpoint", table_name="gateway_blocking_rule")
    op.drop_index("idx_blocking_rule_type_status", table_name="gateway_blocking_rule")
    op.drop_index("idx_blocking_rule_project_status", table_name="gateway_blocking_rule")

    # Drop table
    op.drop_table("gateway_blocking_rule")

    # Drop enums
    op.execute("DROP TYPE blocking_rule_status_enum")
    op.execute("DROP TYPE blocking_rule_type_enum")
