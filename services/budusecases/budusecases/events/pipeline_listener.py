#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""Pipeline event listener for processing BudPipeline callback events.

This module handles events published by BudPipeline to the ``budusecasesEvents``
Dapr pub/sub topic.  Events are used to update deployment and component
deployment statuses in real time as the pipeline executes each step.

BudPipeline publishes events in NotificationPayload format (for Novu compat).
After Dapr CloudEvent unwrapping, the event looks like::

    {
        "notification_type": "event",
        "name": "bud-notification",
        "subscriber_ids": "...",
        "payload": {
            "type": "usecase_deployment",
            "event": "deploy_ragflow",
            "workflow_id": "<budapp-workflow-uuid>",
            "execution_id": "<pipeline-execution-uuid>",
            "content": {
                "title": "deploy_ragflow",
                "message": "Step 'deploy_ragflow' completed",
                "status": "COMPLETED",
                "result": { ... }
            }
        }
    }

The ``execution_id`` is inside ``payload`` (not at top level) so that the
same payload is accepted by budnotify's ``extra="forbid"`` schema.  The
event type is derived from ``payload.event`` and ``payload.content.status``.
"""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from budusecases.deployments.crud import DeploymentDataManager
from budusecases.deployments.enums import ComponentDeploymentStatus, DeploymentStatus

logger = logging.getLogger(__name__)


# Terminal component statuses that should not be overwritten on cancellation.
_TERMINAL_COMPONENT_STATUSES = {
    ComponentDeploymentStatus.RUNNING,
    ComponentDeploymentStatus.FAILED,
    ComponentDeploymentStatus.STOPPED,
}


def _extract_execution_id(event_data: dict) -> str | None:
    """Extract execution_id from event data.

    Checks ``payload.execution_id`` (NotificationPayload format) first,
    then falls back to top-level or ``data.execution_id``.
    """
    # Primary: nested in payload (NotificationPayload format from EventPublisher)
    nested = event_data.get("payload") or {}
    eid = nested.get("execution_id")
    if eid:
        return str(eid)

    # Fallback: top-level or nested in data
    eid = event_data.get("execution_id")
    if eid:
        return str(eid)

    data = event_data.get("data") or {}
    eid = data.get("execution_id")
    return str(eid) if eid else None


def _extract_event_type(event_data: dict) -> str:
    """Extract the pipeline event type from the event data.

    Derives the event type from the NotificationPayload ``payload.event``
    and ``payload.content.status`` fields.  Falls back to the raw ``type``
    field if derivation is inconclusive.
    """
    # Derive from NotificationPayload format
    inner = event_data.get("payload") or {}
    content = inner.get("content") or {}
    event_name = inner.get("event", "")
    content_status = content.get("status", "")

    if event_name == "results":
        return "workflow_completed" if content_status == "COMPLETED" else "workflow_failed"

    if content_status == "COMPLETED":
        return "step_completed"
    if content_status == "STARTED":
        return "step_started"
    if content_status == "FAILED":
        return "step_failed"

    # Last resort: the raw type (may be com.dapr.event.sent)
    return event_data.get("type", "")


def _build_handler_payload(event_data: dict) -> dict:
    """Build a handler-friendly payload from the NotificationPayload format.

    Translates the nested NotificationPayload structure into the flat dict
    expected by ``_handle_step_event`` and ``_handle_execution_completed``.
    """
    inner = event_data.get("payload") or {}
    content = inner.get("content") or {}
    result_data = content.get("result") or {}

    # Step events include step outputs nested in result_data["outputs"];
    # workflow events put outputs directly in result_data.
    if isinstance(result_data, dict) and "outputs" in result_data:
        outputs = result_data["outputs"] if isinstance(result_data["outputs"], dict) else {}
    else:
        outputs = result_data if isinstance(result_data, dict) else {}

    return {
        "step_name": inner.get("event", ""),
        "step_id": inner.get("event", ""),
        "outputs": outputs,
        "error_message": content.get("message") if content.get("status") == "FAILED" else None,
        "message": content.get("message"),
        "success": result_data.get("success") if isinstance(result_data, dict) else None,
    }


async def handle_pipeline_event(event_data: dict, session: Session) -> None:
    """Process a single pipeline callback event.

    The function looks up the deployment associated with the pipeline execution,
    then dispatches to the appropriate handler based on event type.

    Args:
        event_data: The event payload (already extracted from Dapr CloudEvent
            envelope if applicable).
        session: Active SQLAlchemy database session.  The caller is responsible
            for closing the session; this function will ``commit()`` on success.
    """
    # ------------------------------------------------------------------
    # 1. Extract execution_id
    # ------------------------------------------------------------------
    execution_id = _extract_execution_id(event_data)

    if not execution_id:
        logger.warning(
            "Pipeline event missing execution_id, skipping: %s",
            event_data.get("pipeline_event_type") or event_data.get("type"),
        )
        return

    # ------------------------------------------------------------------
    # 2. Look up the deployment
    # ------------------------------------------------------------------
    manager = DeploymentDataManager(session)
    deployment = manager.get_deployment_by_pipeline_execution(execution_id)

    if deployment is None:
        logger.warning(
            "No deployment found for pipeline execution_id=%s, skipping event",
            execution_id,
        )
        return

    # ------------------------------------------------------------------
    # 3. Determine event type and build handler payload
    # ------------------------------------------------------------------
    event_type = _extract_event_type(event_data)
    payload = _build_handler_payload(event_data)

    logger.info(
        "Processing pipeline event: type=%s, execution_id=%s, deployment=%s",
        event_type,
        execution_id,
        deployment.id,
    )

    # ------------------------------------------------------------------
    # 4. Dispatch by event type
    # ------------------------------------------------------------------
    if event_type in ("step_completed", "step_failed"):
        _handle_step_event(manager, deployment, event_type, payload)

    elif event_type in ("workflow_completed", "workflow_failed"):
        _handle_execution_completed(manager, deployment, event_type, payload)

    elif event_type == "execution_cancelled":
        _handle_execution_cancelled(manager, deployment)

    else:
        logger.debug("Ignoring unhandled pipeline event type: %s", event_type)

    # ------------------------------------------------------------------
    # 5. Commit all changes
    # ------------------------------------------------------------------
    session.commit()


# ======================================================================
# Internal helpers
# ======================================================================


def _handle_step_event(
    manager: DeploymentDataManager,
    deployment,
    event_type: str,
    payload: dict,
) -> None:
    """Handle step_completed / step_failed events.

    Only deployment steps (names starting with ``deploy_``) update component
    statuses.  Infrastructure steps like ``cluster_health`` or
    ``notify_complete`` are silently ignored.
    """
    step_name: str = payload.get("step_name", "")

    if not step_name.startswith("deploy_"):
        logger.debug("Skipping non-deploy step event: %s", step_name)
        return

    comp_name = step_name[len("deploy_") :]

    # Find matching component deployment
    component = None
    for cd in deployment.component_deployments:
        if cd.component_name == comp_name:
            component = cd
            break

    if component is None:
        logger.warning(
            "No component_deployment found for component_name=%s in deployment=%s",
            comp_name,
            deployment.id,
        )
        return

    # Map pipeline step status to component deployment status
    if event_type == "step_completed":
        new_status = ComponentDeploymentStatus.RUNNING
    else:
        new_status = ComponentDeploymentStatus.FAILED

    # Extract optional fields from the payload
    endpoint_url: str | None = (
        payload.get("outputs", {}).get("endpoint_url") if isinstance(payload.get("outputs"), dict) else None
    )
    error_message: str | None = payload.get("error_message") or payload.get("error")
    job_id_str: str | None = (
        payload.get("outputs", {}).get("job_id") if isinstance(payload.get("outputs"), dict) else None
    )

    manager.update_component_deployment_status(
        component_id=component.id,
        status=new_status,
        endpoint_url=endpoint_url,
        error_message=error_message,
    )

    # Link job_id if present
    if job_id_str:
        try:
            job_uuid = UUID(job_id_str)
            manager.update_component_deployment_job(
                component_id=component.id,
                job_id=job_uuid,
            )
        except (ValueError, AttributeError):
            logger.warning("Invalid job_id in step outputs: %s", job_id_str)

    # Store gateway_endpoint on the deployment if present (from helm_deploy HTTPRoute creation)
    gateway_endpoint: str | None = (
        payload.get("outputs", {}).get("gateway_endpoint") if isinstance(payload.get("outputs"), dict) else None
    )
    if gateway_endpoint and event_type == "step_completed":
        manager.update_deployment_gateway_url(
            deployment_id=deployment.id,
            gateway_url=gateway_endpoint,
        )
        logger.info(
            "Updated deployment %s gateway_url=%s",
            deployment.id,
            gateway_endpoint,
        )

    logger.info(
        "Updated component %s (%s) to %s for deployment %s",
        comp_name,
        component.id,
        new_status.value,
        deployment.id,
    )


def _handle_execution_completed(
    manager: DeploymentDataManager,
    deployment,
    event_type: str,
    payload: dict,
) -> None:
    """Handle workflow_completed / workflow_failed events.

    Sets the overall deployment status to RUNNING on success or FAILED on
    failure.
    """
    success = payload.get("success")
    if success is None:
        success = event_type == "workflow_completed"
    error_message: str | None = payload.get("message") if not success else None

    if success:
        new_status = DeploymentStatus.RUNNING
    else:
        new_status = DeploymentStatus.FAILED

    manager.update_deployment_status(
        deployment_id=deployment.id,
        status=new_status,
        error_message=error_message,
    )

    logger.info(
        "Deployment %s execution completed with status=%s",
        deployment.id,
        new_status.value,
    )


def _handle_execution_cancelled(
    manager: DeploymentDataManager,
    deployment,
) -> None:
    """Handle execution_cancelled events.

    Sets the deployment status to STOPPED and marks all non-terminal
    component deployments as STOPPED.
    """
    manager.update_deployment_status(
        deployment_id=deployment.id,
        status=DeploymentStatus.STOPPED,
    )

    for component in deployment.component_deployments:
        if component.status not in _TERMINAL_COMPONENT_STATUSES:
            manager.update_component_deployment_status(
                component_id=component.id,
                status=ComponentDeploymentStatus.STOPPED,
            )

    logger.info("Deployment %s cancelled, set to STOPPED", deployment.id)
