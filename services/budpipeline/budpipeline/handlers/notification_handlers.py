"""Notification workflow handlers.

Provides handlers for sending notifications via budnotify service
using Dapr pub/sub.
"""

import logging
from typing import Any

import httpx

from budpipeline.commons.config import secrets_settings, settings
from budpipeline.handlers.base import BaseHandler, HandlerContext, HandlerResult
from budpipeline.handlers.registry import register_handler

logger = logging.getLogger(__name__)


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
    url = f"{settings.dapr_http_endpoint}/v1.0/publish/{pubsub_name}/{topic_name}"

    headers = {"Content-Type": "application/json"}
    if secrets_settings.dapr_api_token:
        headers["dapr-api-token"] = secrets_settings.dapr_api_token

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            url=url,
            json=data,
            headers=headers,
        )
        response.raise_for_status()
        return True


@register_handler("notification")
class NotificationHandler(BaseHandler):
    """Handler for sending notifications via budnotify.

    Publishes notification events to the notifications topic which
    is consumed by the budnotify service for delivery via email,
    Slack, Teams, or webhooks.
    """

    action_type = "notification"
    name = "Send Notification"
    description = "Sends notifications via email, Slack, Teams, or webhook"

    def get_required_params(self) -> list[str]:
        """Get list of required parameters."""
        return ["channel", "message"]

    def get_optional_params(self) -> dict[str, Any]:
        """Get optional parameters with defaults."""
        return {
            "title": "Workflow Notification",
            "severity": "info",
            "metadata": {},
            "recipients": [],
        }

    def get_output_names(self) -> list[str]:
        """Get list of output names."""
        return ["sent", "notification_id"]

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters.

        Args:
            params: Parameters to validate

        Returns:
            List of validation error messages
        """
        errors = []

        if "channel" not in params or not params.get("channel"):
            errors.append("channel is required")

        if "message" not in params or not params.get("message"):
            errors.append("message is required")

        channel = params.get("channel", "")
        valid_channels = {"email", "slack", "teams", "webhook"}
        if channel and channel not in valid_channels:
            errors.append(f"channel must be one of: {valid_channels}")

        severity = params.get("severity")
        if severity is not None:
            valid_severities = {"info", "warning", "error", "critical"}
            if severity not in valid_severities:
                errors.append(f"severity must be one of: {valid_severities}")

        return errors

    async def execute(self, context: HandlerContext) -> HandlerResult:
        """Execute notification action.

        Args:
            context: Execution context with parameters

        Returns:
            HandlerResult with notification outputs
        """
        channel = context.params.get("channel")
        message = context.params.get("message")
        title = context.params.get("title", "Workflow Notification")
        severity = context.params.get("severity", "info")
        metadata = context.params.get("metadata", {})
        recipients = context.params.get("recipients", [])

        notification_id = f"{context.execution_id}-{context.step_id}"

        logger.info(f"[{context.step_id}] Sending {severity} notification via {channel}: {title}")

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

            logger.info(f"[{context.step_id}] Notification {notification_id} published")

            return HandlerResult(
                success=True,
                outputs={
                    "sent": True,
                    "notification_id": notification_id,
                },
            )

        except httpx.HTTPStatusError as e:
            error_msg = f"Failed to publish notification: HTTP {e.response.status_code}"
            logger.error(f"[{context.step_id}] {error_msg}")
            return HandlerResult(
                success=False,
                outputs={
                    "sent": False,
                    "notification_id": notification_id,
                },
                error=error_msg,
            )

        except httpx.TimeoutException:
            error_msg = "Notification publish timed out"
            logger.error(f"[{context.step_id}] {error_msg}")
            return HandlerResult(
                success=False,
                outputs={
                    "sent": False,
                    "notification_id": notification_id,
                },
                error=error_msg,
            )

        except Exception as e:
            error_msg = f"Failed to send notification: {str(e)}"
            logger.exception(f"[{context.step_id}] {error_msg}")
            return HandlerResult(
                success=False,
                outputs={
                    "sent": False,
                    "notification_id": notification_id,
                },
                error=error_msg,
            )


@register_handler("webhook")
class WebhookHandler(BaseHandler):
    """Handler for triggering webhooks.

    Makes HTTP POST requests to external webhook URLs with optional
    payload signing and custom headers.
    """

    action_type = "webhook"
    name = "Trigger Webhook"
    description = "Triggers a webhook with payload and optional signing"

    def get_required_params(self) -> list[str]:
        """Get list of required parameters."""
        return ["url"]

    def get_optional_params(self) -> dict[str, Any]:
        """Get optional parameters with defaults."""
        return {
            "payload": {},
            "headers": {},
            "method": "POST",
            "timeout_seconds": 30,
        }

    def get_output_names(self) -> list[str]:
        """Get list of output names."""
        return ["success", "status_code", "response"]

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters.

        Args:
            params: Parameters to validate

        Returns:
            List of validation error messages
        """
        errors = []

        if "url" not in params or not params.get("url"):
            errors.append("url is required")

        url = params.get("url", "")
        if url and not (url.startswith("http://") or url.startswith("https://")):
            errors.append("url must start with http:// or https://")

        method = params.get("method")
        if method is not None:
            valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE"}
            if method.upper() not in valid_methods:
                errors.append(f"method must be one of: {valid_methods}")

        return errors

    async def execute(self, context: HandlerContext) -> HandlerResult:
        """Execute webhook action.

        Args:
            context: Execution context with parameters

        Returns:
            HandlerResult with webhook response
        """
        url = context.params.get("url")
        payload = context.params.get("payload", {})
        headers = context.params.get("headers", {})
        method = context.params.get("method", "POST").upper()
        timeout = context.params.get("timeout_seconds", 30)

        logger.info(f"[{context.step_id}] Triggering webhook: {method} {url}")

        try:
            # Add workflow metadata to payload
            enriched_payload = {
                **payload,
                "_workflow_metadata": {
                    "execution_id": context.execution_id,
                    "step_id": context.step_id,
                },
            }

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=enriched_payload if method in ["POST", "PUT", "PATCH"] else None,
                    params=enriched_payload if method == "GET" else None,
                    headers=headers if headers else None,
                )

                response_body = None
                try:
                    response_body = response.json()
                except Exception:
                    response_body = response.text

                logger.info(f"[{context.step_id}] Webhook response: {response.status_code}")

                return HandlerResult(
                    success=response.is_success,
                    outputs={
                        "success": response.is_success,
                        "status_code": response.status_code,
                        "response": response_body,
                    },
                )

        except httpx.TimeoutException:
            error_msg = f"Webhook timed out after {timeout}s"
            logger.error(f"[{context.step_id}] {error_msg}")
            return HandlerResult(
                success=False,
                outputs={
                    "success": False,
                    "status_code": 0,
                    "response": None,
                },
                error=error_msg,
            )

        except Exception as e:
            error_msg = f"Webhook failed: {str(e)}"
            logger.exception(f"[{context.step_id}] {error_msg}")
            return HandlerResult(
                success=False,
                outputs={
                    "success": False,
                    "status_code": 0,
                    "response": None,
                },
                error=error_msg,
            )
