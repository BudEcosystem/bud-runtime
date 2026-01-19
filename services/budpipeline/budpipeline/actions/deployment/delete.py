"""Delete Deployment Action.

TODO: Implementation pending.
Deletes an existing model deployment.
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
    ValidationRules,
    register_action,
)

logger = structlog.get_logger(__name__)


class DeploymentDeleteExecutor(BaseActionExecutor):
    """Executor for deleting deployments."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute deployment delete action.

        TODO: Implement actual deployment deletion via budcluster.
        """
        logger.warning(
            "deployment_delete_not_implemented",
            step_id=context.step_id,
        )
        return ActionResult(
            success=False,
            outputs={
                "success": False,
                "deployment_id": context.params.get("deployment_id"),
                "message": "Deployment deletion not yet implemented",
            },
            error="Action not yet implemented. This is a placeholder.",
        )

    def validate_params(self, params: dict) -> list[str]:
        """Validate parameters."""
        errors = []

        if not params.get("deployment_id"):
            errors.append("deployment_id is required")

        return errors


META = ActionMeta(
    type="deployment_delete",
    version="1.0.0",
    name="Delete Deployment",
    description="Deletes an existing model deployment (TODO: implementation pending)",
    category="Deployment",
    icon="trash",
    color="#EF4444",  # Red
    execution_mode=ExecutionMode.EVENT_DRIVEN,
    timeout_seconds=300,
    idempotent=True,
    required_services=["budcluster"],
    params=[
        ParamDefinition(
            name="deployment_id",
            label="Deployment",
            type=ParamType.ENDPOINT_REF,
            description="The deployment to delete",
            required=True,
        ),
        ParamDefinition(
            name="force",
            label="Force Delete",
            type=ParamType.BOOLEAN,
            description="Force deletion even if deployment is serving traffic",
            default=False,
        ),
        ParamDefinition(
            name="max_wait_seconds",
            label="Max Wait",
            type=ParamType.NUMBER,
            description="Maximum time to wait for deletion to complete",
            default=120,
            validation=ValidationRules(min=30, max=600),
        ),
    ],
    outputs=[
        OutputDefinition(
            name="success",
            type="boolean",
            description="Whether deletion was successful",
        ),
        OutputDefinition(
            name="deployment_id",
            type="string",
            description="ID of the deleted deployment",
        ),
        OutputDefinition(
            name="message",
            type="string",
            description="Status message or error details",
        ),
    ],
)


@register_action(META)
class DeploymentDeleteAction:
    """Action for deleting deployments.

    TODO: Implementation pending.
    """

    meta = META
    executor_class = DeploymentDeleteExecutor
