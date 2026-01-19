"""Cloud Model Add Action.

Adds a cloud-hosted model (OpenAI, Anthropic, etc.) to the model repository
via budapp cloud-model-workflow. This is a synchronous operation since cloud
models don't require downloading/extraction.
"""

from __future__ import annotations

import httpx
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
from budpipeline.commons.config import settings

logger = structlog.get_logger(__name__)


def _resolve_initiator_user_id(context: ActionContext) -> str | None:
    """Resolve the initiator user ID for downstream service calls."""
    return (
        context.params.get("user_id")
        or context.workflow_params.get("user_id")
        or settings.system_user_id
    )


class CloudModelAddExecutor(BaseActionExecutor):
    """Executor for adding a cloud model to the repository."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Add cloud model via budapp cloud-model-workflow.

        Cloud models are added synchronously since they don't require
        downloading or extraction - just registration in the model registry.
        """
        provider_id = context.params.get("provider_id", "")
        cloud_model_id = context.params.get("cloud_model_id")
        model_name = context.params.get("model_name", "")
        model_uri = context.params.get("model_uri", "")

        logger.info(
            "cloud_model_add_starting",
            step_id=context.step_id,
            provider_id=provider_id,
            model_name=model_name,
        )

        try:
            initiator_user_id = _resolve_initiator_user_id(context)

            # Cloud model workflow is a single-step workflow
            # Pass provider_id as UUID directly (selected from provider_ref dropdown)
            response = await context.invoke_service(
                app_id=settings.budapp_app_id,
                method_path="models/cloud-model-workflow",
                http_method="POST",
                params={"user_id": initiator_user_id} if initiator_user_id else None,
                data={
                    "workflow_total_steps": 1,
                    "step_number": 1,
                    "trigger_workflow": True,
                    "provider_type": "cloud_model",
                    "provider_id": provider_id,  # Provider UUID from provider_ref
                    "cloud_model_id": cloud_model_id,
                    "name": model_name,
                    "uri": model_uri,
                    "tags": [],  # Required by budapp, empty for cloud models
                    "modality": ["text_input", "text_output"],  # Default modality for cloud LLMs
                },
                timeout_seconds=60,
            )

            # Extract model_id from response
            # budapp returns model_id in workflow_steps.model_id after successful cloud model creation
            model_id = (
                response.get("workflow_steps", {}).get("model_id")
                or response.get("data", {}).get("model_id")
                or response.get("model_id")
                or response.get("data", {}).get("id")
            )
            workflow_id = response.get("data", {}).get("workflow_id") or response.get("workflow_id")

            if not model_id:
                # Check if the workflow completed successfully even without model_id in response
                status = response.get("data", {}).get("status") or response.get("status")
                if status in ("completed", "COMPLETED"):
                    logger.info(
                        "cloud_model_add_completed_no_id",
                        step_id=context.step_id,
                        response=response,
                    )
                    return ActionResult(
                        success=True,
                        outputs={
                            "success": True,
                            "model_id": None,
                            "model_name": model_name,
                            "provider_id": provider_id,
                            "workflow_id": str(workflow_id) if workflow_id else None,
                            "status": "completed",
                            "message": f"Cloud model '{model_name}' added successfully",
                        },
                    )

                error_msg = "No model_id returned from cloud-model-workflow"
                logger.error(
                    "cloud_model_add_no_model_id", step_id=context.step_id, response=response
                )
                return ActionResult(
                    success=False,
                    outputs={
                        "success": False,
                        "model_id": None,
                        "model_name": model_name,
                        "provider_id": provider_id,
                        "workflow_id": str(workflow_id) if workflow_id else None,
                        "status": "failed",
                        "message": error_msg,
                    },
                    error=error_msg,
                )

            logger.info(
                "cloud_model_add_completed",
                step_id=context.step_id,
                model_id=model_id,
            )

            return ActionResult(
                success=True,
                outputs={
                    "success": True,
                    "model_id": str(model_id),
                    "model_name": model_name,
                    "provider_id": provider_id,
                    "workflow_id": str(workflow_id) if workflow_id else None,
                    "status": "completed",
                    "message": f"Cloud model '{model_name}' added successfully",
                },
            )

        except httpx.HTTPStatusError as e:
            error_msg = f"Failed to add cloud model: HTTP {e.response.status_code}"
            try:
                error_detail = e.response.json()
                error_msg = f"{error_msg} - {error_detail}"
            except Exception:
                pass
            logger.error("cloud_model_add_http_error", step_id=context.step_id, error=error_msg)
            return ActionResult(
                success=False,
                outputs={
                    "success": False,
                    "model_id": None,
                    "model_name": model_name,
                    "provider_id": provider_id,
                    "workflow_id": None,
                    "status": "failed",
                    "message": error_msg,
                },
                error=error_msg,
            )

        except Exception as e:
            error_msg = f"Failed to add cloud model: {e!s}"
            logger.exception("cloud_model_add_error", step_id=context.step_id, error=error_msg)
            return ActionResult(
                success=False,
                outputs={
                    "success": False,
                    "model_id": None,
                    "model_name": model_name,
                    "provider_id": provider_id,
                    "workflow_id": None,
                    "status": "failed",
                    "message": error_msg,
                },
                error=error_msg,
            )

    def validate_params(self, params: dict) -> list[str]:
        """Validate parameters."""
        errors = []

        if not params.get("provider_id"):
            errors.append("provider_id is required")

        if not params.get("model_name"):
            errors.append("model_name is required")

        return errors


META = ActionMeta(
    type="cloud_model_add",
    version="1.0.0",
    name="Add Cloud Model",
    description="Add a cloud-hosted model (OpenAI, Anthropic, etc.) to the model repository",
    category="Model Operations",
    icon="cloud-upload",
    color="#6366F1",  # Indigo
    execution_mode=ExecutionMode.SYNC,
    timeout_seconds=120,
    idempotent=False,
    required_services=["budapp"],
    params=[
        ParamDefinition(
            name="provider_id",
            label="Provider",
            type=ParamType.PROVIDER_REF,
            description="Cloud provider (OpenAI, Anthropic, Azure, etc.)",
            required=True,
        ),
        ParamDefinition(
            name="cloud_model_id",
            label="Pre-seeded Model ID",
            type=ParamType.STRING,
            description="ID of a pre-seeded cloud model (optional - leave empty for custom)",
            required=False,
            placeholder="Leave empty to add custom model",
        ),
        ParamDefinition(
            name="model_name",
            label="Model Name",
            type=ParamType.STRING,
            description="Display name for the model",
            required=True,
            placeholder="gpt-4o-mini",
        ),
        ParamDefinition(
            name="model_uri",
            label="Model Identifier",
            type=ParamType.STRING,
            description="Model identifier on the provider (e.g., 'gpt-4o-mini', 'claude-3-opus')",
            required=False,
            placeholder="gpt-4o-mini",
        ),
    ],
    outputs=[
        OutputDefinition(
            name="success",
            type="boolean",
            description="Whether the model was added successfully",
        ),
        OutputDefinition(
            name="model_id",
            type="string",
            description="The unique identifier of the added model",
        ),
        OutputDefinition(
            name="model_name",
            type="string",
            description="The name of the added model",
        ),
        OutputDefinition(
            name="provider_id",
            type="string",
            description="The cloud provider ID",
        ),
        OutputDefinition(
            name="workflow_id",
            type="string",
            description="The workflow ID for tracking the operation",
        ),
        OutputDefinition(
            name="status",
            type="string",
            description="Current status of the operation",
        ),
        OutputDefinition(
            name="message",
            type="string",
            description="Status message or error description",
        ),
    ],
)


@register_action(META)
class CloudModelAddAction:
    """Action for adding a cloud model to the repository."""

    meta = META
    executor_class = CloudModelAddExecutor
