"""add evaluate_model to workflow_type_enum

Revision ID: 53c43a46147b
Revises: c3d4e5f6a7b8
Create Date: 2025-09-12 00:30:22.607575

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from alembic_postgresql_enum import TableReference


# revision identifiers, used by Alembic.
revision: str = "53c43a46147b"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add evaluate_model to workflow_type_enum."""
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
            "evaluate_model",
            "guardrail_deployment",
        ],
        affected_columns=[TableReference(table_schema="public", table_name="workflow", column_name="workflow_type")],
        enum_values_to_rename=[],
    )


def downgrade() -> None:
    """Remove evaluate_model from workflow_type_enum."""
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
            "guardrail_deployment",
        ],
        affected_columns=[TableReference(table_schema="public", table_name="workflow", column_name="workflow_type")],
        enum_values_to_rename=[],
    )
