"""Webhook Action.

Triggers webhooks with payload and optional metadata enrichment.
Similar to HTTP request but designed specifically for webhook patterns.
"""

from __future__ import annotations

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
    ValidationRules,
    register_action,
)

logger = structlog.get_logger(__name__)

VALID_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


class WebhookExecutor(BaseActionExecutor):
    """Executor for triggering webhooks."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute webhook action."""
        url = context.params.get("url", "")
        payload = context.params.get("payload", {})
        headers = context.params.get("headers", {})
        method = context.params.get("method", "POST").upper()
        timeout = context.params.get("timeout_seconds", 30)
        include_metadata = context.params.get("include_metadata", True)

        logger.info(
            "webhook_triggering",
            step_id=context.step_id,
            method=method,
            url=url,
        )

        try:
            # Optionally add workflow metadata to payload
            enriched_payload = dict(payload) if payload else {}
            if include_metadata:
                enriched_payload["_workflow_metadata"] = {
                    "execution_id": context.execution_id,
                    "step_id": context.step_id,
                }

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=enriched_payload if method in ["POST", "PUT", "PATCH"] else None,
                    params=enriched_payload if method == "GET" else None,
                    headers=headers if headers else None,
                )

                # Parse response body
                response_body: Any = None
                try:
                    response_body = response.json()
                except Exception:
                    response_body = response.text

                logger.info(
                    "webhook_completed",
                    step_id=context.step_id,
                    status_code=response.status_code,
                )

                return ActionResult(
                    success=response.is_success,
                    outputs={
                        "success": response.is_success,
                        "status_code": response.status_code,
                        "response": response_body,
                    },
                )

        except httpx.TimeoutException:
            error_msg = f"Webhook timed out after {timeout}s"
            logger.error(
                "webhook_timeout",
                step_id=context.step_id,
                timeout=timeout,
            )
            return ActionResult(
                success=False,
                outputs={
                    "success": False,
                    "status_code": 0,
                    "response": None,
                },
                error=error_msg,
            )

        except Exception as e:
            error_msg = f"Webhook failed: {e!s}"
            logger.exception(
                "webhook_error",
                step_id=context.step_id,
                error=error_msg,
            )
            return ActionResult(
                success=False,
                outputs={
                    "success": False,
                    "status_code": 0,
                    "response": None,
                },
                error=error_msg,
            )

    def validate_params(self, params: dict) -> list[str]:
        """Validate parameters."""
        errors = []

        if not params.get("url"):
            errors.append("url is required")

        url = params.get("url", "")
        if url and not (url.startswith("http://") or url.startswith("https://")):
            errors.append("url must start with http:// or https://")

        method = params.get("method")
        if method is not None:
            if method.upper() not in VALID_METHODS:
                errors.append(f"method must be one of: {VALID_METHODS}")

        return errors


META = ActionMeta(
    type="webhook",
    version="1.0.0",
    name="Trigger Webhook",
    description="Triggers a webhook with payload and optional metadata",
    category="Integration",
    icon="link",
    color="#EC4899",  # Pink
    execution_mode=ExecutionMode.SYNC,
    timeout_seconds=60,
    idempotent=False,
    required_services=[],
    params=[
        ParamDefinition(
            name="url",
            label="Webhook URL",
            type=ParamType.STRING,
            description="The webhook URL to trigger",
            required=True,
            placeholder="https://example.com/webhook",
        ),
        ParamDefinition(
            name="payload",
            label="Payload",
            type=ParamType.JSON,
            description="JSON payload to send with the webhook",
            required=False,
        ),
        ParamDefinition(
            name="headers",
            label="Headers",
            type=ParamType.JSON,
            description="Custom headers to include",
            required=False,
        ),
        ParamDefinition(
            name="method",
            label="Method",
            type=ParamType.SELECT,
            description="HTTP method to use",
            default="POST",
            options=[
                SelectOption(value="GET", label="GET"),
                SelectOption(value="POST", label="POST"),
                SelectOption(value="PUT", label="PUT"),
                SelectOption(value="PATCH", label="PATCH"),
                SelectOption(value="DELETE", label="DELETE"),
            ],
        ),
        ParamDefinition(
            name="include_metadata",
            label="Include Metadata",
            type=ParamType.BOOLEAN,
            description="Include workflow execution metadata in payload",
            default=True,
        ),
        ParamDefinition(
            name="timeout_seconds",
            label="Timeout",
            type=ParamType.NUMBER,
            description="Request timeout in seconds",
            default=30,
            validation=ValidationRules(min=1, max=300),
        ),
    ],
    outputs=[
        OutputDefinition(
            name="success",
            type="boolean",
            description="Whether the webhook was triggered successfully",
        ),
        OutputDefinition(
            name="status_code",
            type="number",
            description="HTTP response status code",
        ),
        OutputDefinition(
            name="response",
            type="any",
            description="Response body from the webhook",
        ),
    ],
)


@register_action(META)
class WebhookAction:
    """Action for triggering webhooks."""

    meta = META
    executor_class = WebhookExecutor
