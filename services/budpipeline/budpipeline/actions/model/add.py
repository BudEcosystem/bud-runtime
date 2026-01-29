"""Model Add Action.

Adds a new model to the model repository via budapp local-model-workflow.
Uses event-driven completion - returns immediately after starting workflow
and receives completion event via on_event().
"""

from __future__ import annotations

import httpx
import structlog

from budpipeline.actions.base import (
    ActionContext,
    ActionMeta,
    ActionResult,
    BaseActionExecutor,
    EventAction,
    EventContext,
    EventResult,
    ExecutionMode,
    OutputDefinition,
    ParamDefinition,
    ParamType,
    SelectOption,
    StepStatus,
    ValidationRules,
    register_action,
)
from budpipeline.commons.config import settings
from budpipeline.commons.constants import CALLBACK_TOPIC

logger = structlog.get_logger(__name__)


def _resolve_initiator_user_id(context: ActionContext) -> str | None:
    """Resolve the initiator user ID for downstream service calls."""
    return (
        context.params.get("user_id")
        or context.workflow_params.get("user_id")
        or settings.system_user_id
    )


class ModelAddExecutor(BaseActionExecutor):
    """Executor for adding a model to the repository."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Start model add workflow and return immediately.

        The workflow completion will be signaled via on_event() when
        budcluster publishes the completion event.
        """
        model_source = context.params.get("model_source", "hugging_face")
        model_uri = context.params.get("model_uri", "")
        model_name = context.params.get("model_name", model_uri.split("/")[-1] if model_uri else "")
        description = context.params.get("description", "")
        author = context.params.get("author", "")
        credential_id = context.params.get("credential_id")
        max_wait_seconds = context.params.get("max_wait_seconds", 86400)

        logger.info(
            "model_add_starting",
            step_id=context.step_id,
            model_source=model_source,
            model_uri=model_uri,
            model_name=model_name,
        )

        try:
            # Call budapp endpoint to start the local-model-workflow
            initiator_user_id = _resolve_initiator_user_id(context)

            response = await context.invoke_service(
                app_id=settings.budapp_app_id,
                method_path="models/local-model-workflow",
                http_method="POST",
                params={"user_id": initiator_user_id} if initiator_user_id else None,
                data={
                    "workflow_total_steps": 1,
                    "step_number": 1,
                    "trigger_workflow": True,
                    "provider_type": model_source,
                    "name": model_name,
                    "uri": model_uri,
                    "description": description,
                    "author": author,
                    "proprietary_credential_id": credential_id,
                    "callback_topic": CALLBACK_TOPIC,
                },
                timeout_seconds=60,
            )

            # Extract workflow_id from response
            workflow_id = response.get("data", {}).get("workflow_id") or response.get("workflow_id")

            if not workflow_id:
                error_msg = "No workflow_id returned from budapp"
                logger.error("model_add_no_workflow_id", step_id=context.step_id)
                return ActionResult(
                    success=False,
                    outputs={
                        "success": False,
                        "model_id": None,
                        "model_name": model_name,
                        "workflow_id": None,
                        "status": "failed",
                        "message": error_msg,
                    },
                    error=error_msg,
                )

            logger.info(
                "model_add_workflow_started",
                step_id=context.step_id,
                workflow_id=workflow_id,
            )

            # Return immediately with awaiting_event=True
            return ActionResult(
                success=True,
                outputs={
                    "success": True,
                    "model_id": None,  # Will be set when event arrives
                    "model_name": model_name,
                    "workflow_id": str(workflow_id),
                    "status": "running",
                    "message": f"Model workflow started: {workflow_id}",
                },
                awaiting_event=True,
                external_workflow_id=str(workflow_id),
                timeout_seconds=max_wait_seconds,
            )

        except httpx.HTTPStatusError as e:
            error_msg = f"Failed to start model workflow: HTTP {e.response.status_code}"
            try:
                error_detail = e.response.json()
                error_msg = f"{error_msg} - {error_detail}"
            except Exception:
                pass
            logger.error("model_add_http_error", step_id=context.step_id, error=error_msg)
            return ActionResult(
                success=False,
                outputs={
                    "success": False,
                    "model_id": None,
                    "model_name": model_name,
                    "workflow_id": None,
                    "status": "failed",
                    "message": error_msg,
                },
                error=error_msg,
            )

        except Exception as e:
            error_msg = f"Failed to add model: {e!s}"
            logger.exception("model_add_error", step_id=context.step_id, error=error_msg)
            return ActionResult(
                success=False,
                outputs={
                    "success": False,
                    "model_id": None,
                    "model_name": model_name,
                    "workflow_id": None,
                    "status": "failed",
                    "message": error_msg,
                },
                error=error_msg,
            )

    async def on_event(self, context: EventContext) -> EventResult:
        """Process completion event from model add workflow.

        Called when an event arrives matching this step's external_workflow_id.
        """
        event_type = context.event_data.get("type", "")
        event_name = context.event_data.get("payload", {}).get("event", "")
        payload = context.event_data.get("payload", {})
        content = payload.get("content", {})
        status_str = content.get("status", "")

        logger.info(
            "model_add_event_received",
            step_execution_id=context.step_execution_id,
            event_type=event_type,
            event_name=event_name,
            status=status_str,
        )

        # Check for model extraction completion events
        # budapp sends type="workflow_completed" for model workflows
        if event_type == "workflow_completed":
            result_data = context.event_data.get("result", {})
            status = context.event_data.get("status", "UNKNOWN")

            if status == "COMPLETED":
                model_id = result_data.get("model_id")
                model_name = result_data.get("model_name", "")

                logger.info(
                    "model_add_completed",
                    step_execution_id=context.step_execution_id,
                    model_id=model_id,
                )

                return EventResult(
                    action=EventAction.COMPLETE,
                    status=StepStatus.COMPLETED,
                    outputs={
                        "success": True,
                        "model_id": model_id,
                        "model_name": model_name,
                        "workflow_id": context.external_workflow_id,
                        "status": "completed",
                        "message": f"Model '{model_name}' added successfully",
                    },
                )
            else:
                error_msg = context.event_data.get("reason", "Model workflow failed")
                logger.error(
                    "model_add_workflow_failed",
                    step_execution_id=context.step_execution_id,
                    error=error_msg,
                )

                return EventResult(
                    action=EventAction.COMPLETE,
                    status=StepStatus.FAILED,
                    outputs={
                        "success": False,
                        "model_id": None,
                        "model_name": context.step_outputs.get("model_name", ""),
                        "workflow_id": context.external_workflow_id,
                        "status": "failed",
                        "message": error_msg,
                    },
                    error=error_msg,
                )

        # Check for direct model_extraction events from budcluster
        if event_type == "model_extraction" and event_name == "results":
            if status_str == "COMPLETED":
                result = content.get("result", {})
                model_id = result.get("model_id")
                model_name = result.get("model_name", "")

                return EventResult(
                    action=EventAction.COMPLETE,
                    status=StepStatus.COMPLETED,
                    outputs={
                        "success": True,
                        "model_id": model_id,
                        "model_name": model_name,
                        "workflow_id": context.external_workflow_id,
                        "status": "completed",
                        "message": f"Model '{model_name}' added successfully",
                    },
                )
            elif status_str == "FAILED":
                error_msg = content.get("message", "Model extraction failed")
                return EventResult(
                    action=EventAction.COMPLETE,
                    status=StepStatus.FAILED,
                    outputs={
                        "success": False,
                        "model_id": None,
                        "model_name": context.step_outputs.get("model_name", ""),
                        "workflow_id": context.external_workflow_id,
                        "status": "failed",
                        "message": error_msg,
                    },
                    error=error_msg,
                )

        # Check for notification events from budmodel/budmicroframe
        # These have type="notification" and completion info in payload.content
        if event_type == "notification":
            payload_type = payload.get("type", "")
            # Handle model extraction completion notifications
            # The final step is "save_model" or "results"
            is_completion_event = event_name in ("save_model", "results")

            if payload_type == "perform_model_extraction":
                # Handle FAILED status for ANY step (validation, download, etc.)
                # Failures can occur at any point in the extraction workflow
                if status_str == "FAILED":
                    error_msg = content.get("message", "") or content.get(
                        "error", f"Model extraction failed at step: {event_name}"
                    )
                    logger.error(
                        "model_add_failed_via_notification",
                        step_execution_id=context.step_execution_id,
                        error=error_msg,
                        event_name=event_name,
                    )

                    return EventResult(
                        action=EventAction.COMPLETE,
                        status=StepStatus.FAILED,
                        outputs={
                            "success": False,
                            "model_id": None,
                            "model_name": context.step_outputs.get("model_name", ""),
                            "workflow_id": context.external_workflow_id,
                            "status": "failed",
                            "message": error_msg,
                        },
                        error=error_msg,
                    )

                # Handle COMPLETED status only for final completion events
                if is_completion_event and status_str == "COMPLETED":
                    result = content.get("result", {})
                    model_id = result.get("model_id")
                    model_name = result.get("model_name", "") or context.step_outputs.get(
                        "model_name", ""
                    )

                    logger.info(
                        "model_add_completed_via_notification",
                        step_execution_id=context.step_execution_id,
                        model_id=model_id,
                        event_name=event_name,
                    )

                    return EventResult(
                        action=EventAction.COMPLETE,
                        status=StepStatus.COMPLETED,
                        outputs={
                            "success": True,
                            "model_id": model_id,
                            "model_name": model_name,
                            "workflow_id": context.external_workflow_id,
                            "status": "completed",
                            "message": f"Model '{model_name}' added successfully",
                        },
                    )

        # Event not relevant to completion
        logger.debug(
            "model_add_event_ignored",
            step_execution_id=context.step_execution_id,
            event_type=event_type,
            event_name=event_name,
        )
        return EventResult(action=EventAction.IGNORE)

    def validate_params(self, params: dict) -> list[str]:
        """Validate parameters."""
        errors = []
        source = params.get("model_source", "hugging_face")

        if not params.get("model_uri"):
            errors.append("model_uri is required")

        # Validate URI format based on source
        model_uri = params.get("model_uri", "")
        if source == "hugging_face" and "/" not in model_uri:
            errors.append("HuggingFace model_uri should be in format 'org/model-name'")
        elif source == "url" and not model_uri.startswith(("http://", "https://")):
            errors.append("URL model_uri should start with http:// or https://")
        elif source == "disk" and not model_uri.startswith("/"):
            errors.append("Disk model_uri should be an absolute path starting with /")

        return errors


META = ActionMeta(
    type="model_add",
    version="1.2.0",
    name="Add Model",
    description="Add a new model to the model repository from HuggingFace, URL, or local disk",
    category="Model Operations",
    icon="database-plus",
    color="#10B981",  # Green
    execution_mode=ExecutionMode.EVENT_DRIVEN,
    timeout_seconds=86400,  # 1 day
    idempotent=False,
    required_services=["budapp", "budmodel"],
    params=[
        ParamDefinition(
            name="model_source",
            label="Model Source",
            type=ParamType.SELECT,
            description="Source of the model",
            default="hugging_face",
            options=[
                SelectOption(value="hugging_face", label="HuggingFace"),
                SelectOption(value="url", label="URL (Direct Download)"),
                SelectOption(value="disk", label="Disk (Local Path)"),
            ],
        ),
        ParamDefinition(
            name="model_uri",
            label="Model URI",
            type=ParamType.STRING,
            description="Model location: HuggingFace ID (org/model), URL, or disk path",
            required=True,
            placeholder="meta-llama/Llama-2-7b or https://... or /path/to/model",
        ),
        ParamDefinition(
            name="credential_id",
            label="HuggingFace Credential",
            type=ParamType.CREDENTIAL_REF,
            description="Credential for accessing gated HuggingFace models (optional for public models)",
            required=False,
        ),
        ParamDefinition(
            name="model_name",
            label="Model Name",
            type=ParamType.STRING,
            description="Display name for the model (defaults to name from URI)",
            required=False,
        ),
        ParamDefinition(
            name="description",
            label="Description",
            type=ParamType.STRING,
            description="Description of the model",
            required=False,
        ),
        ParamDefinition(
            name="author",
            label="Author",
            type=ParamType.STRING,
            description="Author or organization",
            required=False,
        ),
        ParamDefinition(
            name="max_wait_seconds",
            label="Max Wait Time",
            type=ParamType.NUMBER,
            description="Maximum time to wait for model extraction (seconds)",
            default=86400,
            validation=ValidationRules(min=300, max=172800),
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
class ModelAddAction:
    """Action for adding a model to the repository."""

    meta = META
    executor_class = ModelAddExecutor
