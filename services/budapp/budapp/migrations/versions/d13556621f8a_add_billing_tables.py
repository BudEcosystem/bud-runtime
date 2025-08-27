"""Add billing tables

Revision ID: d13556621f8a
Revises: b265afde446b
Create Date: 2025-01-22 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d13556621f8a"
down_revision: Union[str, None] = "b265afde446b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create billing_plans table
    op.create_table(
        "billing_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("monthly_token_quota", sa.Integer(), nullable=True),
        sa.Column("monthly_cost_quota", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("max_projects", sa.Integer(), nullable=True),
        sa.Column("max_endpoints_per_project", sa.Integer(), nullable=True),
        sa.Column("base_monthly_price", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
        sa.Column("overage_token_price", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("features", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Create user_billing table
    op.create_table(
        "user_billing",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("billing_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("billing_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("billing_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("custom_token_quota", sa.Integer(), nullable=True),
        sa.Column("custom_cost_quota", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_suspended", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("suspension_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["billing_plan_id"],
            ["billing_plans.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    # Create billing_alerts table
    op.create_table(
        "billing_alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_billing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("alert_type", sa.String(length=50), nullable=False),
        sa.Column("threshold_percent", sa.Integer(), nullable=False),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_triggered_value", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_billing_id"],
            ["user_billing.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index(op.f("ix_user_billing_user_id"), "user_billing", ["user_id"], unique=True)
    op.create_index(op.f("ix_user_billing_billing_plan_id"), "user_billing", ["billing_plan_id"], unique=False)
    op.create_index(op.f("ix_billing_alerts_user_billing_id"), "billing_alerts", ["user_billing_id"], unique=False)

    # Insert default billing plans with explicit UUIDs
    op.execute("""
        INSERT INTO billing_plans (id, name, description, monthly_token_quota, monthly_cost_quota, max_projects, max_endpoints_per_project, base_monthly_price, overage_token_price, features, created_at, modified_at)
        VALUES
        ('00000000-0000-0000-0000-000000000001'::uuid, 'Free', 'Free tier with basic features', 100000, 10.00, 2, 5, 0.00, NULL, '{"support": "community", "api_rate_limit": 100}', NOW(), NOW()),
        ('00000000-0000-0000-0000-000000000002'::uuid, 'Starter', 'For individual developers', 1000000, 100.00, 10, 20, 29.00, 0.005, '{"support": "email", "api_rate_limit": 1000}', NOW(), NOW()),
        ('00000000-0000-0000-0000-000000000003'::uuid, 'Professional', 'For teams and production use', 10000000, 1000.00, 50, 100, 299.00, 0.004, '{"support": "priority", "api_rate_limit": 10000, "custom_models": true}', NOW(), NOW()),
        ('00000000-0000-0000-0000-000000000004'::uuid, 'Enterprise', 'Custom solutions for large organizations', NULL, NULL, NULL, NULL, 999.00, 0.003, '{"support": "dedicated", "api_rate_limit": null, "custom_models": true, "sla": true}', NOW(), NOW())
    """)

    # Assign free plan to all existing client users
    # Using a deterministic UUID generation approach since gen_random_uuid() may not be available
    op.execute("""
        INSERT INTO user_billing (id, user_id, billing_plan_id, billing_period_start, billing_period_end, is_active, created_at, modified_at)
        SELECT
            ('10000000-0000-0000-0000-' || LPAD(ROW_NUMBER() OVER (ORDER BY u.id)::text, 12, '0'))::uuid,
            u.id,
            '00000000-0000-0000-0000-000000000001'::uuid,  -- Free plan ID
            date_trunc('month', CURRENT_DATE)::timestamp with time zone,
            (date_trunc('month', CURRENT_DATE) + interval '1 month')::timestamp with time zone,
            true,
            NOW(),
            NOW()
        FROM "user" u
        WHERE u.user_type = 'client'
        AND NOT EXISTS (
            SELECT 1 FROM user_billing ub WHERE ub.user_id = u.id
        )
    """)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f("ix_billing_alerts_user_billing_id"), table_name="billing_alerts")
    op.drop_index(op.f("ix_user_billing_billing_plan_id"), table_name="user_billing")
    op.drop_index(op.f("ix_user_billing_user_id"), table_name="user_billing")

    # Drop tables
    op.drop_table("billing_alerts")
    op.drop_table("user_billing")
    op.drop_table("billing_plans")
