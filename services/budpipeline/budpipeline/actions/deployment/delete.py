"""Delete Deployment Action.

Deletes an existing model deployment from a cluster.
Supports both cloud models (sync) and local models (async/event-driven).
"""

from __future__ import annotations

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


class DeploymentDeleteExecutor(BaseActionExecutor):
    """Executor for deleting deployments."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute deployment delete action.

        Calls budapp's delete endpoint workflow which triggers
        budcluster's delete_deployment workflow for local models.
        Cloud models are deleted synchronously.
        """
        endpoint_id = context.params.get("endpoint_id", "")
        force = context.params.get("force", False)

        logger.info(
            "deployment_delete_starting",
            step_id=context.step_id,
            endpoint_id=endpoint_id,
            force=force,
        )

        try:
            initiator_user_id = _resolve_initiator_user_id(context)

            # Call budapp delete endpoint workflow
            # This returns immediately but triggers an async workflow
            # Pass callback_topic so events are published to budpipeline
            response = await context.invoke_service(
                app_id=settings.budapp_app_id,
                method_path=f"endpoints/{endpoint_id}/delete-workflow",
                http_method="POST",
                data={"callback_topic": CALLBACK_TOPIC, "force": force},
                params={"user_id": initiator_user_id} if initiator_user_id else None,
                timeout_seconds=60,
            )

            # Check response status
            status_code = response.get("code", 200)
            message = response.get("message", "")

            if status_code >= 400:
                error_msg = message or f"Delete request failed with code {status_code}"
                logger.error(
                    "deployment_delete_request_failed",
                    step_id=context.step_id,
                    endpoint_id=endpoint_id,
                    error=error_msg,
                )
                return ActionResult(
                    success=False,
                    outputs={
                        "success": False,
                        "endpoint_id": endpoint_id,
                        "status": "failed",
                        "message": error_msg,
                    },
                    error=error_msg,
                )

            # Extract workflow_id from response if available
            # budapp returns {"message": "...", "code": 200, "object": "endpoint.delete"}
            # The actual workflow_id comes from the events
            workflow_id = response.get("workflow_id") or response.get("data", {}).get("workflow_id")

            # If workflow_id is returned, this is an async operation (local model)
            # Otherwise it might have been completed synchronously (cloud model)
            if workflow_id:
                logger.info(
                    "deployment_delete_awaiting",
                    step_id=context.step_id,
                    endpoint_id=endpoint_id,
                    workflow_id=workflow_id,
                )
                return ActionResult(
                    success=True,
                    awaiting_event=True,
                    external_workflow_id=str(workflow_id),
                    timeout_seconds=context.params.get("max_wait_seconds", 300),
                    outputs={
                        "success": True,
                        "endpoint_id": endpoint_id,
                        "workflow_id": str(workflow_id),
                        "status": "deleting",
                        "message": "Deployment deletion in progress...",
                    },
                )

            # Check if this is a sync completion (cloud model without cluster)
            if message and "initiated" in message.lower():
                # The delete was initiated, wait for events
                logger.info(
                    "deployment_delete_initiated_awaiting_events",
                    step_id=context.step_id,
                    endpoint_id=endpoint_id,
                )
                return ActionResult(
                    success=True,
                    awaiting_event=True,
                    external_workflow_id=endpoint_id,  # Use endpoint_id as fallback
                    timeout_seconds=context.params.get("max_wait_seconds", 300),
                    outputs={
                        "success": True,
                        "endpoint_id": endpoint_id,
                        "workflow_id": None,
                        "status": "deleting",
                        "message": message,
                    },
                )

            # Synchronous completion (cloud model deleted immediately)
            logger.info(
                "deployment_delete_completed_sync",
                step_id=context.step_id,
                endpoint_id=endpoint_id,
            )
            return ActionResult(
                success=True,
                outputs={
                    "success": True,
                    "endpoint_id": endpoint_id,
                    "workflow_id": None,
                    "status": "deleted",
                    "message": message or "Deployment deleted successfully",
                },
            )

        except Exception as e:
            error_msg = f"Failed to delete deployment: {e!s}"
            logger.exception(
                "deployment_delete_error",
                step_id=context.step_id,
                endpoint_id=endpoint_id,
                error=error_msg,
            )
            return ActionResult(
                success=False,
                outputs={
                    "success": False,
                    "endpoint_id": endpoint_id,
                    "status": "failed",
                    "message": error_msg,
                },
                error=error_msg,
            )

    async def on_event(self, context: EventContext) -> EventResult:
        """Process completion event from delete workflow.

        Called when an event arrives matching this step's external_workflow_id.
        Handles events from budcluster's delete_deployment workflow.

        Events from budcluster:
        - deployment_deletion_status: STARTED, COMPLETED, FAILED
        - delete_namespace: COMPLETED, FAILED
        - results: COMPLETED (final result with namespace and cluster_id)
        """
        event_type = context.event_data.get("type", "")
        event_name = context.event_data.get("payload", {}).get("event", "")
        payload = context.event_data.get("payload", {})
        content = payload.get("content", {})
        status_str = content.get("status", "")

        logger.info(
            "deployment_delete_event_received",
            step_execution_id=context.step_execution_id,
            event_type=event_type,
            event_name=event_name,
            status=status_str,
        )

        # Handle notification events from budcluster
        if event_type == "notification":
            # Handle results event (final completion)
            if event_name == "results" and status_str == "COMPLETED":
                result = content.get("results", {})
                namespace = result.get("namespace", "")
                cluster_id = result.get("cluster_id", "")
                endpoint_id = context.step_outputs.get("endpoint_id", "")

                logger.info(
                    "deployment_delete_completed",
                    step_execution_id=context.step_execution_id,
                    endpoint_id=endpoint_id,
                    namespace=namespace,
                    cluster_id=cluster_id,
                )

                return EventResult(
                    action=EventAction.COMPLETE,
                    status=StepStatus.COMPLETED,
                    outputs={
                        "success": True,
                        "endpoint_id": endpoint_id,
                        "namespace": namespace,
                        "cluster_id": cluster_id,
                        "status": "deleted",
                        "message": f"Deployment '{namespace}' deleted successfully",
                    },
                )

            # Handle deployment_deletion_status COMPLETED
            if event_name == "deployment_deletion_status" and status_str == "COMPLETED":
                endpoint_id = context.step_outputs.get("endpoint_id", "")
                message = content.get("message", "Deployment deleted successfully")

                logger.info(
                    "deployment_delete_completed_via_status",
                    step_execution_id=context.step_execution_id,
                    endpoint_id=endpoint_id,
                )

                return EventResult(
                    action=EventAction.COMPLETE,
                    status=StepStatus.COMPLETED,
                    outputs={
                        "success": True,
                        "endpoint_id": endpoint_id,
                        "status": "deleted",
                        "message": message,
                    },
                )

            # Handle failure events
            if status_str == "FAILED":
                error_msg = (
                    content.get("message", "")
                    or content.get("error", "")
                    or "Deployment deletion failed"
                )
                endpoint_id = context.step_outputs.get("endpoint_id", "")

                logger.error(
                    "deployment_delete_failed",
                    step_execution_id=context.step_execution_id,
                    endpoint_id=endpoint_id,
                    event_name=event_name,
                    error=error_msg,
                )

                return EventResult(
                    action=EventAction.COMPLETE,
                    status=StepStatus.FAILED,
                    outputs={
                        "success": False,
                        "endpoint_id": endpoint_id,
                        "status": "failed",
                        "message": error_msg,
                    },
                    error=error_msg,
                )

        # Handle workflow_completed events from budapp
        if event_type == "workflow_completed":
            status = context.event_data.get("status", "UNKNOWN")
            endpoint_id = context.step_outputs.get("endpoint_id", "")

            if status == "COMPLETED":
                logger.info(
                    "deployment_delete_workflow_completed",
                    step_execution_id=context.step_execution_id,
                    endpoint_id=endpoint_id,
                )

                return EventResult(
                    action=EventAction.COMPLETE,
                    status=StepStatus.COMPLETED,
                    outputs={
                        "success": True,
                        "endpoint_id": endpoint_id,
                        "status": "deleted",
                        "message": "Deployment deleted successfully",
                    },
                )
            else:
                error_msg = context.event_data.get("reason", "Deletion workflow failed")
                logger.error(
                    "deployment_delete_workflow_failed",
                    step_execution_id=context.step_execution_id,
                    endpoint_id=endpoint_id,
                    error=error_msg,
                )

                return EventResult(
                    action=EventAction.COMPLETE,
                    status=StepStatus.FAILED,
                    outputs={
                        "success": False,
                        "endpoint_id": endpoint_id,
                        "status": "failed",
                        "message": error_msg,
                    },
                    error=error_msg,
                )

        # Event not relevant to completion - ignore and keep waiting
        logger.debug(
            "deployment_delete_event_ignored",
            step_execution_id=context.step_execution_id,
            event_type=event_type,
            event_name=event_name,
        )
        return EventResult(action=EventAction.IGNORE)

    def validate_params(self, params: dict) -> list[str]:
        """Validate parameters."""
        errors = []

        if not params.get("endpoint_id"):
            errors.append("endpoint_id is required")

        max_wait = params.get("max_wait_seconds")
        if max_wait is not None:
            if not isinstance(max_wait, int | float):
                errors.append("max_wait_seconds must be a number")
            elif max_wait < 30 or max_wait > 600:
                errors.append("max_wait_seconds must be between 30 and 600")

        return errors


META = ActionMeta(
    type="deployment_delete",
    version="1.0.0",
    name="Delete Deployment",
    description="Deletes an existing model deployment from a cluster. Removes the endpoint and releases all associated resources including pods, services, and storage.",
    category="Deployment",
    icon="trash",
    color="#EF4444",  # Red
    execution_mode=ExecutionMode.EVENT_DRIVEN,
    timeout_seconds=300,
    idempotent=True,
    required_services=["budapp"],
    params=[
        ParamDefinition(
            name="endpoint_id",
            label="Deployment",
            type=ParamType.ENDPOINT_REF,
            description="The deployment endpoint to delete",
            required=True,
        ),
        ParamDefinition(
            name="force",
            label="Force Delete",
            type=ParamType.BOOLEAN,
            description="Force deletion even if deployment is serving traffic (not yet implemented)",
            default=False,
        ),
        ParamDefinition(
            name="max_wait_seconds",
            label="Max Wait Time",
            type=ParamType.NUMBER,
            description="Maximum time to wait for deletion to complete (seconds)",
            default=300,
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
            name="endpoint_id",
            type="string",
            description="ID of the deleted deployment",
        ),
        OutputDefinition(
            name="namespace",
            type="string",
            description="Kubernetes namespace that was deleted",
        ),
        OutputDefinition(
            name="cluster_id",
            type="string",
            description="ID of the cluster the deployment was removed from",
        ),
        OutputDefinition(
            name="status",
            type="string",
            description="Current status of the deletion (deleting, deleted, failed)",
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
    """Action for deleting deployments."""

    meta = META
    executor_class = DeploymentDeleteExecutor
