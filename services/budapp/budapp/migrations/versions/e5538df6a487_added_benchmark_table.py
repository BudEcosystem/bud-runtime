"""added benchmark table.

Revision ID: e5538df6a487
Revises: e9f810852a5d
Create Date: 2025-03-21 08:02:23.012619

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from alembic_postgresql_enum import TableReference


# revision identifiers, used by Alembic.
revision: str = "e5538df6a487"
down_revision: Union[str, None] = "e9f810852a5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.sync_enum_values(
        "public",
        "workflow_type_enum",
        [
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
        ],
        [TableReference(table_schema="public", table_name="workflow", column_name="workflow_type")],
        enum_values_to_rename=[],
    )
    op.create_table(
        "benchmark",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bud_cluster_benchmark_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("eval_with", sa.String(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("model_id", sa.Uuid(), nullable=True),
        sa.Column("cluster_id", sa.Uuid(), nullable=True),
        sa.Column("nodes", sa.JSON(), nullable=True),
        sa.Column("concurrency", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum("success", "failed", "processing", name="benchmark_status_enum"), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("modified_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["cluster_id"], ["cluster.id"], name=op.f("fk_benchmark_cluster_id_cluster")),
        sa.ForeignKeyConstraint(["model_id"], ["model.id"], name=op.f("fk_benchmark_model_id_model")),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], name=op.f("fk_benchmark_user_id_user")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_benchmark")),
    )


def downgrade() -> None:
    op.sync_enum_values(
        "public",
        "workflow_type_enum",
        [
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
        ],
        [TableReference(table_schema="public", table_name="workflow", column_name="workflow_type")],
        enum_values_to_rename=[],
    )
    op.drop_table("benchmark")
