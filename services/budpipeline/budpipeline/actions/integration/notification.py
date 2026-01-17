"""Notification Action.

Sends notifications via budnotify service using Dapr pub/sub.
Supports email, Slack, Teams, and webhook channels.
"""

from __future__ import annotations

import os
from typing import Any

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
    SelectOption,
    register_action,
)
from budpipeline.commons.config import settings

logger = structlog.get_logger(__name__)

VALID_CHANNELS = {"email", "slack", "teams", "webhook"}
VALID_SEVERITIES = {"info", "warning", "error", "critical"}


async def publish_to_pubsub(
    pubsub_name: str,
    topic_name: str,
    data: dict[str, Any],
    timeout: int = 10,
) -> bool:
    """Publish a message to Dapr pub/sub.

    Args:
        pubsub_name: Name of the pub/sub component
        topic_name: Topic to publish to
        data: Message data
        timeout: Request timeout in seconds

    Returns:
        True if published successfully
    """
    dapr_endpoint = os.environ.get("DAPR_HTTP_ENDPOINT", "http://localhost:3500")
    url = f"{dapr_endpoint}/v1.0/publish/{pubsub_name}/{topic_name}"

    headers = {"Content-Type": "application/json"}
    dapr_token = os.environ.get("DAPR_API_TOKEN")
    if dapr_token:
        headers["dapr-api-token"] = dapr_token

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url=url, json=data, headers=headers)
        response.raise_for_status()
        return True


class NotificationExecutor(BaseActionExecutor):
    """Executor for sending notifications."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute notification action."""
        channel = context.params.get("channel")
        message = context.params.get("message")
        title = context.params.get("title", "Workflow Notification")
        severity = context.params.get("severity", "info")
        metadata = context.params.get("metadata", {})
        recipients = context.params.get("recipients", [])

        notification_id = f"{context.execution_id}-{context.step_id}"

        logger.info(
            "notification_sending",
            step_id=context.step_id,
            channel=channel,
            severity=severity,
            notification_id=notification_id,
        )

        try:
            # Build notification payload
            notification_data = {
                "notification_id": notification_id,
                "channel": channel,
                "title": title,
                "message": message,
                "severity": severity,
                "metadata": {
                    **metadata,
                    "source": "budpipeline",
                    "workflow_execution_id": context.execution_id,
                    "step_id": context.step_id,
                },
                "recipients": recipients,
            }

            # Publish to notifications topic
            await publish_to_pubsub(
                pubsub_name=settings.pubsub_name,
                topic_name="notifications",
                data=notification_data,
            )

            logger.info(
                "notification_published",
                step_id=context.step_id,
                notification_id=notification_id,
            )

            return ActionResult(
                success=True,
                outputs={
                    "sent": True,
                    "notification_id": notification_id,
                },
            )

        except httpx.HTTPStatusError as e:
            error_msg = f"Failed to publish notification: HTTP {e.response.status_code}"
            logger.error(
                "notification_http_error",
                step_id=context.step_id,
                error=error_msg,
            )
            return ActionResult(
                success=False,
                outputs={
                    "sent": False,
                    "notification_id": notification_id,
                },
                error=error_msg,
            )

        except httpx.TimeoutException:
            error_msg = "Notification publish timed out"
            logger.error(
                "notification_timeout",
                step_id=context.step_id,
            )
            return ActionResult(
                success=False,
                outputs={
                    "sent": False,
                    "notification_id": notification_id,
                },
                error=error_msg,
            )

        except Exception as e:
            error_msg = f"Failed to send notification: {e!s}"
            logger.exception(
                "notification_error",
                step_id=context.step_id,
                error=error_msg,
            )
            return ActionResult(
                success=False,
                outputs={
                    "sent": False,
                    "notification_id": notification_id,
                },
                error=error_msg,
            )

    def validate_params(self, params: dict) -> list[str]:
        """Validate parameters."""
        errors = []

        if not params.get("channel"):
            errors.append("channel is required")

        if not params.get("message"):
            errors.append("message is required")

        channel = params.get("channel", "")
        if channel and channel not in VALID_CHANNELS:
            errors.append(f"channel must be one of: {VALID_CHANNELS}")

        severity = params.get("severity")
        if severity is not None and severity not in VALID_SEVERITIES:
            errors.append(f"severity must be one of: {VALID_SEVERITIES}")

        return errors


META = ActionMeta(
    type="notification",
    version="1.0.0",
    name="Send Notification",
    description="Sends notifications via email, Slack, Teams, or webhook",
    category="Integration",
    icon="bell",
    color="#F59E0B",  # Amber
    execution_mode=ExecutionMode.SYNC,
    timeout_seconds=30,
    idempotent=False,
    required_services=["budnotify"],
    params=[
        ParamDefinition(
            name="channel",
            label="Channel",
            type=ParamType.SELECT,
            description="Notification channel to use",
            required=True,
            options=[
                SelectOption(value="email", label="Email"),
                SelectOption(value="slack", label="Slack"),
                SelectOption(value="teams", label="Microsoft Teams"),
                SelectOption(value="webhook", label="Webhook"),
            ],
        ),
        ParamDefinition(
            name="title",
            label="Title",
            type=ParamType.STRING,
            description="Notification title",
            default="Workflow Notification",
        ),
        ParamDefinition(
            name="message",
            label="Message",
            type=ParamType.TEMPLATE,
            description="Notification message (supports template variables)",
            required=True,
        ),
        ParamDefinition(
            name="severity",
            label="Severity",
            type=ParamType.SELECT,
            description="Notification severity level",
            default="info",
            options=[
                SelectOption(value="info", label="Info"),
                SelectOption(value="warning", label="Warning"),
                SelectOption(value="error", label="Error"),
                SelectOption(value="critical", label="Critical"),
            ],
        ),
        ParamDefinition(
            name="recipients",
            label="Recipients",
            type=ParamType.JSON,
            description="List of recipients (channel-specific format)",
            required=False,
        ),
        ParamDefinition(
            name="metadata",
            label="Metadata",
            type=ParamType.JSON,
            description="Additional metadata to include",
            required=False,
        ),
    ],
    outputs=[
        OutputDefinition(
            name="sent",
            type="boolean",
            description="Whether the notification was sent successfully",
        ),
        OutputDefinition(
            name="notification_id",
            type="string",
            description="Unique identifier for tracking the notification",
        ),
    ],
)


@register_action(META)
class NotificationAction:
    """Action for sending notifications."""

    meta = META
    executor_class = NotificationExecutor
