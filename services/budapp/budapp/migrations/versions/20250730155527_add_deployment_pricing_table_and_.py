"""add deployment pricing table and catalog indexes

Revision ID: 20250730155527
Revises: e82a355aae6f
Create Date: 2025-07-30 15:55:27.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20250730155527"
down_revision: Union[str, None] = "e82a355aae6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create deployment_pricing table
    op.create_table(
        "deployment_pricing",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("endpoint_id", sa.UUID(), nullable=False),
        sa.Column("input_cost", sa.DECIMAL(precision=10, scale=6), nullable=False),
        sa.Column("output_cost", sa.DECIMAL(precision=10, scale=6), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("per_tokens", sa.Integer(), server_default="1000", nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["endpoint_id"], ["endpoint.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for deployment_pricing table
    op.create_index("idx_deployment_pricing_endpoint_id", "deployment_pricing", ["endpoint_id"])
    op.create_index("idx_deployment_pricing_is_current", "deployment_pricing", ["is_current"])
    op.create_index(
        "idx_deployment_pricing_created_at",
        "deployment_pricing",
        ["created_at"],
        postgresql_using="btree",
        postgresql_ops={"created_at": "DESC"},
    )

    # Create unique index to ensure only one current pricing per endpoint
    op.create_index(
        "idx_deployment_pricing_current_unique",
        "deployment_pricing",
        ["endpoint_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )

    # Add performance indexes for model catalog filtering
    op.create_index("idx_model_modality_gin", "model", ["modality"], postgresql_using="gin")
    op.create_index("idx_model_status", "model", ["status"])
    op.create_index("idx_model_use_cases_gin", "model", ["use_cases"], postgresql_using="gin")

    # Add full-text search indexes
    op.execute("""
        CREATE INDEX idx_model_name_search ON model
        USING gin(to_tsvector('english', name));
    """)

    op.execute("""
        CREATE INDEX idx_model_description_search ON model
        USING gin(to_tsvector('english', COALESCE(description, '')));
    """)

    # Add composite index for published endpoints
    op.create_index(
        "idx_endpoint_published_composite",
        "endpoint",
        ["is_published", "status", "published_date"],
        postgresql_using="btree",
        postgresql_ops={"published_date": "DESC"},
    )

    # Check if token_limit field exists, add if missing
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='model' AND column_name='token_limit'
            ) THEN
                ALTER TABLE model ADD COLUMN token_limit INTEGER;
            END IF;
        END$$;
    """)

    # Check if max_input_tokens exists in model table, add if missing
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='model' AND column_name='max_input_tokens'
            ) THEN
                ALTER TABLE model ADD COLUMN max_input_tokens INTEGER;
            END IF;
        END$$;
    """)


def downgrade() -> None:
    # Drop composite indexes
    op.drop_index("idx_endpoint_published_composite", table_name="endpoint")

    # Drop full-text search indexes
    op.execute("DROP INDEX IF EXISTS idx_model_description_search;")
    op.execute("DROP INDEX IF EXISTS idx_model_name_search;")

    # Drop model indexes
    op.drop_index("idx_model_use_cases_gin", table_name="model")
    op.drop_index("idx_model_status", table_name="model")
    op.drop_index("idx_model_modality_gin", table_name="model")

    # Drop deployment_pricing indexes
    op.drop_index("idx_deployment_pricing_current_unique", table_name="deployment_pricing")
    op.drop_index("idx_deployment_pricing_created_at", table_name="deployment_pricing")
    op.drop_index("idx_deployment_pricing_is_current", table_name="deployment_pricing")
    op.drop_index("idx_deployment_pricing_endpoint_id", table_name="deployment_pricing")

    # Drop deployment_pricing table
    op.drop_table("deployment_pricing")

    # Note: We don't drop token_limit and max_input_tokens columns as they might be used elsewhere
