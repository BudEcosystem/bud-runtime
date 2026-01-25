"""Scale Deployment Action.

Scales a deployment to a specific number of replicas.
Uses the budapp autoscale API to set min/max replicas to the target value,
preserving existing scaling strategy and other autoscale settings.
"""

from __future__ import annotations

from typing import Any

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
from budpipeline.commons.config import settings

logger = structlog.get_logger(__name__)


def _resolve_initiator_user_id(context: ActionContext) -> str | None:
    """Resolve the initiator user ID for downstream service calls."""
    return (
        context.params.get("user_id")
        or context.workflow_params.get("user_id")
        or settings.system_user_id
    )


class DeploymentScaleExecutor(BaseActionExecutor):
    """Executor for scaling deployments."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute scale deployment action.

        This action scales a deployment to a specific number of replicas by:
        1. Getting the current autoscale configuration
        2. Preserving the existing scaling strategy and other settings
        3. Setting minReplicas and maxReplicas to the target value
        """
        endpoint_id = context.params.get("endpoint_id", "")
        target_replicas = context.params.get("target_replicas")

        if target_replicas is None:
            return ActionResult(
                success=False,
                outputs={
                    "success": False,
                    "endpoint_id": endpoint_id,
                    "message": "target_replicas is required",
                },
                error="target_replicas is required",
            )

        target_replicas = int(target_replicas)

        try:
            initiator_user_id = _resolve_initiator_user_id(context)

            # Step 1: Get current autoscale configuration
            logger.info(
                "deployment_scale_get_current_config",
                endpoint_id=endpoint_id,
                target_replicas=target_replicas,
            )

            current_config: dict[str, Any] = {}
            try:
                current_config = await context.invoke_service(
                    app_id=settings.budapp_app_id,
                    method_path=f"endpoints/{endpoint_id}/autoscale",
                    http_method="GET",
                    params={"user_id": initiator_user_id} if initiator_user_id else None,
                    timeout_seconds=30,
                )
            except Exception as e:
                # If we can't get current config, proceed with minimal config
                logger.warning(
                    "deployment_scale_get_config_failed",
                    endpoint_id=endpoint_id,
                    error=str(e),
                )

            # Step 2: Build updated autoscale specification
            # Preserve existing config if available, only update replicas
            existing_budaiscaler = current_config.get("budaiscaler_config") or {}

            # Build the new specification preserving existing settings
            # Note: maxReplicas must be >= 1 per BudAIScalerSpecification schema
            # When scaling to 0, set minReplicas=0, maxReplicas=1 to allow scale-down
            budaiscaler_spec: dict[str, Any] = {
                "enabled": True,  # Must be enabled for scaling to work
                "minReplicas": target_replicas,
                "maxReplicas": max(target_replicas, 1),  # Ensure maxReplicas >= 1
            }

            # Preserve existing scaling strategy if present
            if existing_budaiscaler.get("scalingStrategy"):
                budaiscaler_spec["scalingStrategy"] = existing_budaiscaler["scalingStrategy"]

            # Preserve other existing settings
            preserve_keys = [
                "metricsSources",
                "gpuConfig",
                "costConfig",
                "predictionConfig",
                "scheduleHints",
                "multiCluster",
                "behavior",
            ]
            for key in preserve_keys:
                if key in existing_budaiscaler and existing_budaiscaler[key]:
                    budaiscaler_spec[key] = existing_budaiscaler[key]

            # Step 3: Apply the new autoscale configuration
            logger.info(
                "deployment_scale_applying",
                endpoint_id=endpoint_id,
                target_replicas=target_replicas,
                preserved_strategy=budaiscaler_spec.get("scalingStrategy"),
            )

            request_data = {"budaiscaler_specification": budaiscaler_spec}

            await context.invoke_service(
                app_id=settings.budapp_app_id,
                method_path=f"endpoints/{endpoint_id}/autoscale",
                http_method="PUT",
                params={"user_id": initiator_user_id} if initiator_user_id else None,
                data=request_data,
                timeout_seconds=60,
            )

            logger.info(
                "deployment_scale_success",
                endpoint_id=endpoint_id,
                target_replicas=target_replicas,
            )

            return ActionResult(
                success=True,
                outputs={
                    "success": True,
                    "endpoint_id": endpoint_id,
                    "target_replicas": target_replicas,
                    "previous_min_replicas": existing_budaiscaler.get("minReplicas"),
                    "previous_max_replicas": existing_budaiscaler.get("maxReplicas"),
                    "scaling_strategy": budaiscaler_spec.get("scalingStrategy"),
                    "message": f"Scaled deployment to {target_replicas} replicas",
                },
            )

        except Exception as e:
            error_msg = f"Failed to scale deployment: {e!s}"
            logger.exception(
                "deployment_scale_failed",
                endpoint_id=endpoint_id,
                target_replicas=target_replicas,
                error=str(e),
            )
            return ActionResult(
                success=False,
                outputs={
                    "success": False,
                    "endpoint_id": endpoint_id,
                    "target_replicas": target_replicas,
                    "message": error_msg,
                },
                error=error_msg,
            )

    def validate_params(self, params: dict) -> list[str]:
        """Validate parameters."""
        errors = []

        if not params.get("endpoint_id"):
            errors.append("endpoint_id is required")

        target_replicas = params.get("target_replicas")
        if target_replicas is None:
            errors.append("target_replicas is required")
        else:
            try:
                replicas = int(target_replicas)
                if replicas < 0:
                    errors.append("target_replicas must be non-negative")
                if replicas > 100:
                    errors.append("target_replicas cannot exceed 100")
            except (TypeError, ValueError):
                errors.append("target_replicas must be a valid number")

        return errors


META = ActionMeta(
    type="deployment_scale",
    version="1.0.0",
    name="Scale Deployment",
    description=(
        "Scale a deployment to a specific number of replicas. "
        "This sets both minimum and maximum replicas to the target value, "
        "effectively fixing the replica count. Existing scaling strategy "
        "and other autoscale settings are preserved."
    ),
    category="Deployment",
    icon="arrows-alt",
    color="#722ED1",  # Purple
    execution_mode=ExecutionMode.SYNC,
    timeout_seconds=120,
    idempotent=True,
    required_services=["budapp"],
    params=[
        ParamDefinition(
            name="endpoint_id",
            label="Deployment Endpoint",
            type=ParamType.ENDPOINT_REF,
            description="The deployment endpoint to scale",
            required=True,
        ),
        ParamDefinition(
            name="target_replicas",
            label="Target Replicas",
            type=ParamType.NUMBER,
            description="Number of replicas to scale to (0 to scale down completely)",
            required=True,
            default=1,
            validation=ValidationRules(min=0, max=100),
        ),
    ],
    outputs=[
        OutputDefinition(
            name="success",
            type="boolean",
            description="Whether scaling was successful",
        ),
        OutputDefinition(
            name="endpoint_id",
            type="string",
            description="ID of the scaled deployment",
        ),
        OutputDefinition(
            name="target_replicas",
            type="number",
            description="Target number of replicas",
        ),
        OutputDefinition(
            name="previous_min_replicas",
            type="number",
            description="Previous minimum replicas (if available)",
        ),
        OutputDefinition(
            name="previous_max_replicas",
            type="number",
            description="Previous maximum replicas (if available)",
        ),
        OutputDefinition(
            name="scaling_strategy",
            type="string",
            description="Preserved scaling strategy",
        ),
        OutputDefinition(
            name="message",
            type="string",
            description="Status message or error details",
        ),
    ],
)


@register_action(META)
class DeploymentScaleAction:
    """Action for scaling deployments.

    Scales a deployment to a specific number of replicas by setting
    minReplicas = maxReplicas = target_replicas in the BudAIScaler config.
    Preserves existing scaling strategy and other autoscale settings.
    """

    meta = META
    executor_class = DeploymentScaleExecutor
