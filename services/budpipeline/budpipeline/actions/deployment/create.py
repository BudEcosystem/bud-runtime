"""Create Deployment Action.

Deploys a model to a cluster, creating an inference endpoint.
Supports both cloud models (sync) and local models (async/event-driven).
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
from budpipeline.commons.config import settings

logger = structlog.get_logger(__name__)


def _resolve_initiator_user_id(context: ActionContext) -> str | None:
    """Resolve the initiator user ID for downstream service calls."""
    return (
        context.params.get("user_id")
        or context.workflow_params.get("user_id")
        or settings.system_user_id
    )


class DeploymentCreateExecutor(BaseActionExecutor):
    """Executor for creating deployments."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute deployment create action.

        Cloud models are deployed synchronously (endpoint created directly).
        Local models are deployed asynchronously via budcluster.
        """
        model_id = context.params.get("model_id", "")
        project_id = context.params.get("project_id", "")
        cluster_id = context.params.get("cluster_id")  # Optional for cloud models
        endpoint_name = context.params.get("endpoint_name", "")
        credential_id = context.params.get("credential_id")  # Required for cloud models
        concurrent_requests = context.params.get("concurrent_requests", 1)
        avg_sequence_length = context.params.get("avg_sequence_length", 512)
        avg_context_length = context.params.get("avg_context_length", 4096)
        # Performance targets for local model simulation
        ttft = context.params.get("ttft")  # [min, max] in ms
        per_session_tokens_per_sec = context.params.get("per_session_tokens_per_sec")  # [min, max]
        e2e_latency = context.params.get("e2e_latency")  # [min, max] in seconds

        logger.info(
            "deployment_create_starting",
            step_id=context.step_id,
            model_id=model_id,
            project_id=project_id,
            endpoint_name=endpoint_name,
        )

        try:
            initiator_user_id = _resolve_initiator_user_id(context)

            # Build deploy_config
            deploy_config: dict = {
                "concurrent_requests": concurrent_requests,
                "avg_sequence_length": avg_sequence_length,
                "avg_context_length": avg_context_length,
            }
            # Add performance targets for local model simulation
            if ttft:
                deploy_config["ttft"] = ttft
            if per_session_tokens_per_sec:
                deploy_config["per_session_tokens_per_sec"] = per_session_tokens_per_sec
            if e2e_latency:
                deploy_config["e2e_latency"] = e2e_latency

            # Build request payload
            request_data: dict = {
                "workflow_total_steps": 1,
                "step_number": 1,
                "trigger_workflow": True,
                "model_id": model_id,
                "project_id": project_id,
                "endpoint_name": endpoint_name,
                "deploy_config": deploy_config,
            }

            # Add optional fields
            if cluster_id:
                request_data["cluster_id"] = cluster_id
            if credential_id:
                request_data["credential_id"] = credential_id

            # Call budapp deploy endpoint
            response = await context.invoke_service(
                app_id=settings.budapp_app_id,
                method_path="models/deploy-workflow",
                http_method="POST",
                params={"user_id": initiator_user_id} if initiator_user_id else None,
                data=request_data,
                timeout_seconds=120,
            )

            # Extract workflow info from response
            workflow_data = response.get("data", {})
            workflow_id = workflow_data.get("workflow_id") or response.get("workflow_id")
            workflow_status = workflow_data.get("status") or response.get("status")

            # Check progress for endpoint info (cloud models complete immediately)
            progress = workflow_data.get("progress", {})
            endpoint_id = progress.get("endpoint_id")
            endpoint_url = progress.get("endpoint_url")

            # Cloud models: workflow is COMPLETED immediately
            if workflow_status in ("completed", "COMPLETED"):
                logger.info(
                    "deployment_create_completed",
                    step_id=context.step_id,
                    endpoint_id=endpoint_id,
                    endpoint_url=endpoint_url,
                )
                return ActionResult(
                    success=True,
                    outputs={
                        "success": True,
                        "endpoint_id": endpoint_id,
                        "endpoint_url": endpoint_url,
                        "endpoint_name": endpoint_name,
                        "workflow_id": str(workflow_id) if workflow_id else None,
                        "status": "completed",
                        "message": f"Endpoint '{endpoint_name}' deployed successfully",
                    },
                )

            # Local models: workflow is still running, wait for events
            logger.info(
                "deployment_create_awaiting",
                step_id=context.step_id,
                workflow_id=workflow_id,
                workflow_status=workflow_status,
            )
            return ActionResult(
                success=True,
                awaiting_event=True,
                external_workflow_id=str(workflow_id) if workflow_id else None,
                timeout_seconds=600,  # 10 minutes for deployment
                outputs={
                    "success": True,
                    "endpoint_id": None,
                    "endpoint_url": None,
                    "endpoint_name": endpoint_name,
                    "workflow_id": str(workflow_id) if workflow_id else None,
                    "status": "deploying",
                    "message": "Model deployment in progress...",
                },
            )

        except Exception as e:
            error_msg = f"Failed to deploy model: {e!s}"
            logger.exception("deployment_create_error", step_id=context.step_id, error=error_msg)
            return ActionResult(
                success=False,
                outputs={
                    "success": False,
                    "endpoint_id": None,
                    "endpoint_url": None,
                    "endpoint_name": endpoint_name,
                    "workflow_id": None,
                    "status": "failed",
                    "message": error_msg,
                },
                error=error_msg,
            )

    def validate_params(self, params: dict) -> list[str]:
        """Validate parameters."""
        errors = []

        if not params.get("model_id"):
            errors.append("model_id is required")

        if not params.get("project_id"):
            errors.append("project_id is required")

        if not params.get("endpoint_name"):
            errors.append("endpoint_name is required")

        # Note: cluster_id is required for local models but optional for cloud models
        # This is validated at runtime by budapp

        return errors


META = ActionMeta(
    type="deployment_create",
    version="1.0.0",
    name="Deploy Model",
    description="Deploy a model to create an inference endpoint. Supports cloud models (OpenAI, Anthropic) and local models (HuggingFace).",
    category="Deployment",
    icon="rocket",
    color="#10B981",  # Emerald
    execution_mode=ExecutionMode.EVENT_DRIVEN,
    timeout_seconds=600,
    idempotent=False,
    required_services=["budapp"],
    params=[
        ParamDefinition(
            name="model_id",
            label="Model",
            type=ParamType.MODEL_REF,
            description="The model to deploy",
            required=True,
        ),
        ParamDefinition(
            name="project_id",
            label="Project",
            type=ParamType.PROJECT_REF,
            description="The project to deploy the endpoint in",
            required=True,
        ),
        ParamDefinition(
            name="endpoint_name",
            label="Endpoint Name",
            type=ParamType.STRING,
            description="Unique name for the deployment endpoint (lowercase, hyphens allowed)",
            required=True,
            placeholder="my-model-endpoint",
        ),
        ParamDefinition(
            name="cluster_id",
            label="Cluster",
            type=ParamType.CLUSTER_REF,
            description="Target cluster for deployment (required for local models, optional for cloud models)",
            required=False,
        ),
        ParamDefinition(
            name="credential_id",
            label="Credential",
            type=ParamType.STRING,
            description="API credential ID (required for cloud models)",
            required=False,
            placeholder="UUID of the credential",
        ),
        ParamDefinition(
            name="concurrent_requests",
            label="Concurrent Requests",
            type=ParamType.NUMBER,
            description="Number of concurrent requests the endpoint should handle",
            default=1,
            required=True,
            validation=ValidationRules(min=1, max=1000),
        ),
        ParamDefinition(
            name="avg_sequence_length",
            label="Avg Sequence Length",
            type=ParamType.NUMBER,
            description="Average output sequence length (tokens)",
            default=512,
            required=True,
            validation=ValidationRules(min=1, max=10000),
        ),
        ParamDefinition(
            name="avg_context_length",
            label="Avg Context Length",
            type=ParamType.NUMBER,
            description="Average input context length (tokens)",
            default=4096,
            required=True,
            validation=ValidationRules(min=1, max=200000),
        ),
        ParamDefinition(
            name="ttft",
            label="Target TTFT",
            type=ParamType.JSON,
            description="Time to first token range [min, max] in milliseconds (required for local models)",
            required=False,
            placeholder="[500, 1000]",
        ),
        ParamDefinition(
            name="per_session_tokens_per_sec",
            label="Tokens/Sec Target",
            type=ParamType.JSON,
            description="Tokens per second range [min, max] (required for local models)",
            required=False,
            placeholder="[10, 100]",
        ),
        ParamDefinition(
            name="e2e_latency",
            label="E2E Latency Target",
            type=ParamType.JSON,
            description="End-to-end latency range [min, max] in seconds (required for local models)",
            required=False,
            placeholder="[10, 60]",
        ),
    ],
    outputs=[
        OutputDefinition(
            name="success",
            type="boolean",
            description="Whether deployment was successful",
        ),
        OutputDefinition(
            name="endpoint_id",
            type="string",
            description="Unique identifier of the created endpoint",
        ),
        OutputDefinition(
            name="endpoint_url",
            type="string",
            description="URL of the deployment endpoint",
        ),
        OutputDefinition(
            name="endpoint_name",
            type="string",
            description="Name of the deployment endpoint",
        ),
        OutputDefinition(
            name="workflow_id",
            type="string",
            description="Workflow ID for tracking the deployment",
        ),
        OutputDefinition(
            name="status",
            type="string",
            description="Current status of the deployment",
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
    """Action for deploying models to create inference endpoints."""

    meta = META
    executor_class = DeploymentCreateExecutor
