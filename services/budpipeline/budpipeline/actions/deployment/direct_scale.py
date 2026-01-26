"""Direct Scale Deployment Action.

Scales a deployment directly via budcluster, bypassing budapp authentication.
Use this when you have the cluster_id, namespace, and release_name available.
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


class DirectScaleExecutor(BaseActionExecutor):
    """Executor for directly scaling deployments via budcluster."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute direct scale deployment action.

        This action scales a deployment by calling budcluster's update_autoscale
        endpoint directly, bypassing budapp authentication requirements.
        """
        cluster_id = context.params.get("cluster_id", "")
        namespace = context.params.get("namespace", "")
        release_name = context.params.get("release_name", "")
        target_replicas = context.params.get("target_replicas")
        engine_type = context.params.get("engine_type", "vllm")

        if target_replicas is None:
            return ActionResult(
                success=False,
                outputs={
                    "success": False,
                    "release_name": release_name,
                    "message": "target_replicas is required",
                },
                error="target_replicas is required",
            )

        target_replicas = int(target_replicas)

        try:
            logger.info(
                "direct_scale_applying",
                cluster_id=cluster_id,
                namespace=namespace,
                release_name=release_name,
                target_replicas=target_replicas,
            )

            # Build budaiscaler config for scaling
            budaiscaler_config: dict[str, Any] = {
                "enabled": True,
                "minReplicas": target_replicas,
                "maxReplicas": target_replicas,
            }

            # Call budcluster directly
            request_data = {
                "cluster_id": cluster_id,
                "namespace": namespace,
                "release_name": release_name,
                "budaiscaler": budaiscaler_config,
                "engine_type": engine_type,
            }

            response = await context.invoke_service(
                app_id=settings.budcluster_app_id,
                method_path="deployment/autoscale",
                http_method="PUT",
                data=request_data,
                timeout_seconds=60,
            )

            logger.info(
                "direct_scale_success",
                cluster_id=cluster_id,
                namespace=namespace,
                release_name=release_name,
                target_replicas=target_replicas,
                response=response,
            )

            return ActionResult(
                success=True,
                outputs={
                    "success": True,
                    "cluster_id": cluster_id,
                    "namespace": namespace,
                    "release_name": release_name,
                    "target_replicas": target_replicas,
                    "autoscale_enabled": response.get("autoscale_enabled", True),
                    "message": f"Scaled deployment to {target_replicas} replicas",
                },
            )

        except Exception as e:
            error_msg = f"Failed to scale deployment: {e!s}"
            logger.exception(
                "direct_scale_failed",
                cluster_id=cluster_id,
                namespace=namespace,
                release_name=release_name,
                target_replicas=target_replicas,
                error=str(e),
            )
            return ActionResult(
                success=False,
                outputs={
                    "success": False,
                    "cluster_id": cluster_id,
                    "namespace": namespace,
                    "release_name": release_name,
                    "target_replicas": target_replicas,
                    "message": error_msg,
                },
                error=error_msg,
            )

    def validate_params(self, params: dict) -> list[str]:
        """Validate parameters."""
        errors = []

        if not params.get("cluster_id"):
            errors.append("cluster_id is required")

        if not params.get("namespace"):
            errors.append("namespace is required")

        if not params.get("release_name"):
            errors.append("release_name is required")

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
    type="direct_deployment_scale",
    version="1.0.0",
    name="Direct Scale Deployment",
    description=(
        "Scale a deployment directly via budcluster by specifying cluster details. "
        "Use this when you have cluster_id, namespace, and release_name. "
        "This bypasses budapp authentication requirements for internal service calls."
    ),
    category="Deployment",
    icon="arrows-alt",
    color="#722ED1",  # Purple
    execution_mode=ExecutionMode.SYNC,
    timeout_seconds=120,
    idempotent=True,
    required_services=["budcluster"],
    params=[
        ParamDefinition(
            name="cluster_id",
            label="Cluster ID",
            type=ParamType.CLUSTER_REF,
            description="The cluster UUID where the deployment is running",
            required=True,
        ),
        ParamDefinition(
            name="namespace",
            label="Namespace",
            type=ParamType.STRING,
            description="Kubernetes namespace of the deployment",
            required=True,
        ),
        ParamDefinition(
            name="release_name",
            label="Release Name",
            type=ParamType.STRING,
            description="Helm release name of the deployment",
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
        ParamDefinition(
            name="engine_type",
            label="Engine Type",
            type=ParamType.STRING,
            description="Inference engine type (default: vllm)",
            required=False,
            default="vllm",
        ),
    ],
    outputs=[
        OutputDefinition(
            name="success",
            type="boolean",
            description="Whether scaling was successful",
        ),
        OutputDefinition(
            name="cluster_id",
            type="string",
            description="Cluster ID",
        ),
        OutputDefinition(
            name="namespace",
            type="string",
            description="Kubernetes namespace",
        ),
        OutputDefinition(
            name="release_name",
            type="string",
            description="Helm release name",
        ),
        OutputDefinition(
            name="target_replicas",
            type="number",
            description="Target number of replicas",
        ),
        OutputDefinition(
            name="autoscale_enabled",
            type="boolean",
            description="Whether autoscaling is enabled",
        ),
        OutputDefinition(
            name="message",
            type="string",
            description="Status message or error details",
        ),
    ],
)


@register_action(META)
class DirectDeploymentScaleAction:
    """Action for scaling deployments directly via budcluster.

    Scales a deployment by setting minReplicas = maxReplicas = target_replicas
    in the BudAIScaler config, calling budcluster directly.
    """

    meta = META
    executor_class = DirectScaleExecutor
