"""remove tool_creation from workflow_type_enum

Revision ID: a3b4c5d6e7f8
Revises: 061d2a62eb6f
Create Date: 2026-02-14

"""

from typing import Sequence, Union

from alembic import op
from alembic_postgresql_enum import TableReference


# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "061d2a62eb6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove tool_creation from workflow_type_enum."""
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
            "prompt_creation",
            "prompt_schema_creation",
            "custom_probe_creation",
        ],
        affected_columns=[TableReference(table_schema="public", table_name="workflow", column_name="workflow_type")],
        enum_values_to_rename=[],
    )


def downgrade() -> None:
    """Re-add tool_creation to workflow_type_enum."""
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
            "prompt_creation",
            "prompt_schema_creation",
            "tool_creation",
            "custom_probe_creation",
        ],
        affected_columns=[TableReference(table_schema="public", table_name="workflow", column_name="workflow_type")],
        enum_values_to_rename=[],
    )
