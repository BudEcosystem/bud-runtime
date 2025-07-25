import dapr.ext.workflow as wf
from budmicroframe.commons import logging
from budmicroframe.shared.dapr_workflow import DaprWorkflow

from .schemas import NotificationActivityRequest


logger = logging.get_logger(__name__)

dapr_workflows = DaprWorkflow()


@dapr_workflows.register_activity
def notify_activity(ctx: wf.WorkflowActivityContext, notification: str) -> dict:
    """Define Notify Activity.

    This is used by the workflow to send out a notification

    Args:
        ctx (DaprWorkflowContext): The context of the Dapr workflow, providing
        access to workflow instance information.
        notification (str): The notification message to be sent.
    """
    # Create a logger
    logger = logging.get_logger("NotifyActivity")
    workflow_id = str(ctx.workflow_id)
    task_id = ctx.task_id
    logger.info(f"Notification for workflow_id: {workflow_id} and task_id: {task_id}")

    notification_json = NotificationActivityRequest.model_validate_json(notification)
    notification_request = notification_json.notification_request
    notification_request.payload.event = notification_json.activity_event
    notification_request.payload.content = notification_json.content
    target_topic_name = notification_json.source_topic
    target_name = notification_json.source

    dapr_workflows.publish_notification(
        workflow_id=workflow_id,
        notification=notification_request,
        target_topic_name=target_topic_name,
        target_name=target_name,
    )
