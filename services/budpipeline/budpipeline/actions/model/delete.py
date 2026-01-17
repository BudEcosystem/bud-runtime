"""Model Delete Action.

Deletes a model from the model repository via budapp.
This is a synchronous operation that doesn't require waiting for events.
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


class ModelDeleteExecutor(BaseActionExecutor):
    """Executor for deleting a model from the repository."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute model delete action."""
        model_id = context.params.get("model_id", "")
        force = context.params.get("force", False)
        initiator_user_id = _resolve_initiator_user_id(context)

        logger.info(
            "model_delete_starting",
            step_id=context.step_id,
            model_id=model_id,
            force=force,
        )

        try:
            params: dict[str, str] = {"force": str(force).lower()}
            if initiator_user_id:
                params["user_id"] = initiator_user_id

            await context.invoke_service(
                app_id=settings.budapp_app_id,
                method_path=f"models/{model_id}",
                http_method="DELETE",
                params=params,
                timeout_seconds=30,
            )

            logger.info(
                "model_delete_completed",
                step_id=context.step_id,
                model_id=model_id,
            )

            return ActionResult(
                success=True,
                outputs={
                    "success": True,
                    "model_id": model_id,
                    "message": f"Model {model_id} deleted successfully",
                },
            )

        except httpx.HTTPStatusError as e:
            error_msg = f"Failed to delete model: HTTP {e.response.status_code}"
            try:
                error_detail = e.response.json()
                error_msg = f"{error_msg} - {error_detail}"
            except Exception:
                pass
            logger.error("model_delete_http_error", step_id=context.step_id, error=error_msg)
            return ActionResult(
                success=False,
                outputs={
                    "success": False,
                    "model_id": model_id,
                    "message": error_msg,
                },
                error=error_msg,
            )

        except Exception as e:
            error_msg = f"Failed to delete model: {e!s}"
            logger.exception("model_delete_error", step_id=context.step_id, error=error_msg)
            return ActionResult(
                success=False,
                outputs={
                    "success": False,
                    "model_id": model_id,
                    "message": error_msg,
                },
                error=error_msg,
            )

    def validate_params(self, params: dict) -> list[str]:
        """Validate parameters."""
        errors = []
        if not params.get("model_id"):
            errors.append("model_id is required for deletion")
        return errors


META = ActionMeta(
    type="model_delete",
    version="1.0.0",
    name="Delete Model",
    description="Delete a model from the model repository",
    category="Model Operations",
    icon="trash",
    color="#EF4444",  # Red
    execution_mode=ExecutionMode.SYNC,
    timeout_seconds=60,
    idempotent=True,
    required_services=["budapp"],
    params=[
        ParamDefinition(
            name="model_id",
            label="Model ID",
            type=ParamType.MODEL_REF,
            description="The unique identifier of the model to delete",
            required=True,
        ),
        ParamDefinition(
            name="force",
            label="Force Delete",
            type=ParamType.BOOLEAN,
            description="Force deletion even if model is in use",
            default=False,
        ),
    ],
    outputs=[
        OutputDefinition(
            name="success",
            type="boolean",
            description="Whether the model was deleted successfully",
        ),
        OutputDefinition(
            name="model_id",
            type="string",
            description="The ID of the deleted model",
        ),
        OutputDefinition(
            name="message",
            type="string",
            description="Status message or error description",
        ),
    ],
)


@register_action(META)
class ModelDeleteAction:
    """Action for deleting a model from the repository."""

    meta = META
    executor_class = ModelDeleteExecutor
