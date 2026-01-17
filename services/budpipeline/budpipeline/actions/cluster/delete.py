"""Cluster Delete Action.

TODO: Implement cluster deletion action.
This is a placeholder for future implementation.
"""

from __future__ import annotations

import structlog

from budpipeline.actions.base import (
    ActionContext,
    ActionMeta,
    ActionResult,
    BaseActionExecutor,
    ExecutionMode,
    OutputDefinition,
    ParamDefinition,
    ParamType,
    register_action,
)

logger = structlog.get_logger(__name__)


class ClusterDeleteExecutor(BaseActionExecutor):
    """Executor for cluster deletion.

    TODO: Implement actual cluster deletion logic.
    """

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute cluster deletion.

        TODO: Implement cluster deletion via budcluster API.
        """
        cluster_id = context.params.get("cluster_id", "")

        logger.warning(
            "cluster_delete_not_implemented",
            step_id=context.step_id,
            cluster_id=cluster_id,
        )

        return ActionResult(
            success=False,
            outputs={
                "success": False,
                "cluster_id": cluster_id,
                "message": "Cluster deletion is not yet implemented",
            },
            error="Cluster deletion is not yet implemented",
        )

    def validate_params(self, params: dict) -> list[str]:
        """Validate parameters."""
        errors = []
        if not params.get("cluster_id"):
            errors.append("cluster_id is required")
        return errors


META = ActionMeta(
    type="cluster_delete",
    version="1.0.0",
    name="Delete Cluster",
    description="Delete a Kubernetes cluster (not yet implemented)",
    category="Cluster Operations",
    icon="server-x",
    color="#DC2626",  # Red
    execution_mode=ExecutionMode.EVENT_DRIVEN,
    timeout_seconds=1200,  # 20 minutes
    idempotent=True,
    required_services=["budcluster"],
    params=[
        ParamDefinition(
            name="cluster_id",
            label="Cluster",
            type=ParamType.CLUSTER_REF,
            description="The cluster to delete",
            required=True,
        ),
        ParamDefinition(
            name="force",
            label="Force Delete",
            type=ParamType.BOOLEAN,
            description="Force deletion even if resources are still running",
            default=False,
        ),
    ],
    outputs=[
        OutputDefinition(
            name="success",
            type="boolean",
            description="Whether the cluster was deleted successfully",
        ),
        OutputDefinition(
            name="cluster_id",
            type="string",
            description="The ID of the deleted cluster",
        ),
        OutputDefinition(
            name="message",
            type="string",
            description="Status message or error description",
        ),
    ],
)


@register_action(META)
class ClusterDeleteAction:
    """Action for deleting a cluster.

    TODO: This action is not yet implemented.
    """

    meta = META
    executor_class = ClusterDeleteExecutor
