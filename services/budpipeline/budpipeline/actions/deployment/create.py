"""Create Deployment Action.

TODO: Implementation pending.
Creates a new model deployment on a cluster.
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


class DeploymentCreateExecutor(BaseActionExecutor):
    """Executor for creating deployments."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute deployment create action.

        TODO: Implement actual deployment creation via budcluster.
        """
        logger.warning(
            "deployment_create_not_implemented",
            step_id=context.step_id,
        )
        return ActionResult(
            success=False,
            outputs={
                "success": False,
                "deployment_id": None,
                "message": "Deployment creation not yet implemented",
            },
            error="Action not yet implemented. This is a placeholder.",
        )

    def validate_params(self, params: dict) -> list[str]:
        """Validate parameters."""
        errors = []

        if not params.get("model_id"):
            errors.append("model_id is required")

        if not params.get("cluster_id"):
            errors.append("cluster_id is required")

        return errors


META = ActionMeta(
    type="deployment_create",
    version="1.0.0",
    name="Create Deployment",
    description="Creates a new model deployment on a cluster (TODO: implementation pending)",
    category="Deployment",
    icon="rocket",
    color="#10B981",  # Emerald
    execution_mode=ExecutionMode.EVENT_DRIVEN,
    timeout_seconds=600,
    idempotent=False,
    required_services=["budcluster"],
    params=[
        ParamDefinition(
            name="model_id",
            label="Model",
            type=ParamType.MODEL_REF,
            description="The model to deploy",
            required=True,
        ),
        ParamDefinition(
            name="cluster_id",
            label="Cluster",
            type=ParamType.CLUSTER_REF,
            description="The cluster to deploy to",
            required=True,
        ),
        ParamDefinition(
            name="deployment_name",
            label="Deployment Name",
            type=ParamType.STRING,
            description="Name for the deployment",
            required=False,
            placeholder="my-deployment",
        ),
        ParamDefinition(
            name="replicas",
            label="Replicas",
            type=ParamType.NUMBER,
            description="Number of replicas to deploy",
            default=1,
            validation={"min": 1, "max": 100},
        ),
        ParamDefinition(
            name="max_wait_seconds",
            label="Max Wait",
            type=ParamType.NUMBER,
            description="Maximum time to wait for deployment to be ready",
            default=300,
            validation={"min": 60, "max": 1800},
        ),
    ],
    outputs=[
        OutputDefinition(
            name="success",
            type="boolean",
            description="Whether deployment was successful",
        ),
        OutputDefinition(
            name="deployment_id",
            type="string",
            description="Unique identifier of the created deployment",
        ),
        OutputDefinition(
            name="endpoint_url",
            type="string",
            description="URL of the deployment endpoint",
        ),
        OutputDefinition(
            name="message",
            type="string",
            description="Status message or error details",
        ),
    ],
)


@register_action(META)
class DeploymentCreateAction:
    """Action for creating deployments.

    TODO: Implementation pending.
    """

    meta = META
    executor_class = DeploymentCreateExecutor
