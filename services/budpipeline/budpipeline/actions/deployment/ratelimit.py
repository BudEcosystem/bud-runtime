"""Rate Limit Deployment Action.

Configures rate limiting for an existing deployment endpoint.
Uses the budapp deployment settings API to apply rate limit configuration.
"""

from __future__ import annotations

from typing import Any

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
from budpipeline.commons.config import settings

logger = structlog.get_logger(__name__)


def _resolve_initiator_user_id(context: ActionContext) -> str | None:
    """Resolve the initiator user ID for downstream service calls."""
    return (
        context.params.get("user_id")
        or context.workflow_params.get("user_id")
        or settings.system_user_id
    )


class DeploymentRateLimitExecutor(BaseActionExecutor):
    """Executor for configuring rate limiting."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute rate limit configuration action.

        Calls budapp to update the deployment settings with rate limiting config.
        This is a sync action - the rate limit configuration is applied immediately.
        """
        # Get parameters
        endpoint_id = context.params.get("endpoint_id", "")
        algorithm = context.params.get("algorithm", "token_bucket")
        requests_per_second = context.params.get("requests_per_second")
        requests_per_minute = context.params.get("requests_per_minute")
        requests_per_hour = context.params.get("requests_per_hour")
        burst_size = context.params.get("burst_size")
        enabled = context.params.get("enabled", True)

        logger.info(
            "deployment_ratelimit_starting",
            step_id=context.step_id,
            endpoint_id=endpoint_id,
            algorithm=algorithm,
            enabled=enabled,
        )

        try:
            initiator_user_id = _resolve_initiator_user_id(context)

            # Build rate limit configuration
            rate_limit_config: dict[str, Any] = {
                "algorithm": algorithm,
                "enabled": enabled,
            }

            # Add optional rate limit values
            if requests_per_second is not None:
                rate_limit_config["requests_per_second"] = int(requests_per_second)
            if requests_per_minute is not None:
                rate_limit_config["requests_per_minute"] = int(requests_per_minute)
            if requests_per_hour is not None:
                rate_limit_config["requests_per_hour"] = int(requests_per_hour)
            if burst_size is not None:
                rate_limit_config["burst_size"] = int(burst_size)

            # Build request payload for deployment settings update
            request_data = {
                "rate_limits": rate_limit_config,
            }

            logger.info(
                "deployment_ratelimit_calling_api",
                step_id=context.step_id,
                endpoint_id=endpoint_id,
                rate_limit_config=rate_limit_config,
            )

            # Call budapp deployment settings endpoint
            response = await context.invoke_service(
                app_id=settings.budapp_app_id,
                method_path=f"endpoints/{endpoint_id}/deployment-settings",
                http_method="PUT",
                params={"user_id": initiator_user_id} if initiator_user_id else None,
                data=request_data,
                timeout_seconds=30,
            )

            # Extract response data
            deployment_settings = response.get("deployment_settings", {})
            applied_rate_limits = deployment_settings.get("rate_limits", rate_limit_config)

            logger.info(
                "deployment_ratelimit_completed",
                step_id=context.step_id,
                endpoint_id=endpoint_id,
                applied_config=applied_rate_limits,
            )

            return ActionResult(
                success=True,
                outputs={
                    "success": True,
                    "endpoint_id": endpoint_id,
                    "config": applied_rate_limits,
                    "message": f"Rate limiting {'enabled' if enabled else 'disabled'} for endpoint",
                },
            )

        except Exception as e:
            error_msg = f"Failed to configure rate limiting: {e!s}"
            logger.exception(
                "deployment_ratelimit_error",
                step_id=context.step_id,
                endpoint_id=endpoint_id,
                error=error_msg,
            )
            return ActionResult(
                success=False,
                outputs={
                    "success": False,
                    "endpoint_id": endpoint_id,
                    "config": None,
                    "message": error_msg,
                },
                error=error_msg,
            )

    def validate_params(self, params: dict) -> list[str]:
        """Validate parameters."""
        errors = []

        if not params.get("endpoint_id"):
            errors.append("endpoint_id is required")

        # Check that at least one rate limit value is provided
        has_rate_limit = any(
            [
                params.get("requests_per_second"),
                params.get("requests_per_minute"),
                params.get("requests_per_hour"),
            ]
        )
        if not has_rate_limit:
            errors.append(
                "At least one rate limit must be specified: "
                "requests_per_second, requests_per_minute, or requests_per_hour"
            )

        # Validate positive values
        for param_name in [
            "requests_per_second",
            "requests_per_minute",
            "requests_per_hour",
            "burst_size",
        ]:
            value = params.get(param_name)
            if value is not None and value <= 0:
                errors.append(f"{param_name} must be a positive number")

        # Validate algorithm
        algorithm = params.get("algorithm", "token_bucket")
        valid_algorithms = ["token_bucket", "fixed_window", "sliding_window"]
        if algorithm not in valid_algorithms:
            errors.append(f"algorithm must be one of: {', '.join(valid_algorithms)}")

        return errors


META = ActionMeta(
    type="deployment_ratelimit",
    version="1.1.0",
    name="Configure Rate Limiting",
    description="Configure rate limiting for an existing deployment endpoint. Supports token bucket, fixed window, and sliding window algorithms with per-second, per-minute, or per-hour limits.",
    category="Deployment",
    icon="shield",
    color="#6366F1",  # Indigo
    execution_mode=ExecutionMode.SYNC,
    timeout_seconds=60,
    idempotent=True,
    required_services=["budapp"],
    params=[
        ParamDefinition(
            name="endpoint_id",
            label="Endpoint",
            type=ParamType.ENDPOINT_REF,
            description="The deployment endpoint to configure rate limiting for",
            required=True,
        ),
        ParamDefinition(
            name="algorithm",
            label="Algorithm",
            type=ParamType.SELECT,
            description="Rate limiting algorithm to use",
            default="token_bucket",
            options=[
                SelectOption(
                    value="token_bucket",
                    label="Token Bucket (Recommended)",
                ),
                SelectOption(
                    value="fixed_window",
                    label="Fixed Window",
                ),
                SelectOption(
                    value="sliding_window",
                    label="Sliding Window",
                ),
            ],
        ),
        ParamDefinition(
            name="requests_per_second",
            label="Requests per Second",
            type=ParamType.NUMBER,
            description="Maximum requests per second allowed (leave empty to skip)",
            required=False,
            validation=ValidationRules(min=1, max=100000),
        ),
        ParamDefinition(
            name="requests_per_minute",
            label="Requests per Minute",
            type=ParamType.NUMBER,
            description="Maximum requests per minute allowed (leave empty to skip)",
            required=False,
            validation=ValidationRules(min=1, max=1000000),
        ),
        ParamDefinition(
            name="requests_per_hour",
            label="Requests per Hour",
            type=ParamType.NUMBER,
            description="Maximum requests per hour allowed (leave empty to skip)",
            required=False,
            validation=ValidationRules(min=1, max=10000000),
        ),
        ParamDefinition(
            name="burst_size",
            label="Burst Size",
            type=ParamType.NUMBER,
            description="Maximum burst size for rate limiting (token bucket algorithm)",
            default=100,
            required=False,
            validation=ValidationRules(min=1, max=10000),
        ),
        ParamDefinition(
            name="enabled",
            label="Enabled",
            type=ParamType.BOOLEAN,
            description="Whether rate limiting is enabled",
            default=True,
        ),
    ],
    outputs=[
        OutputDefinition(
            name="success",
            type="boolean",
            description="Whether configuration was successful",
        ),
        OutputDefinition(
            name="endpoint_id",
            type="string",
            description="ID of the configured endpoint",
        ),
        OutputDefinition(
            name="config",
            type="object",
            description="Applied rate limiting configuration",
        ),
        OutputDefinition(
            name="message",
            type="string",
            description="Status message or error details",
        ),
    ],
)


@register_action(META)
class DeploymentRateLimitAction:
    """Action for configuring deployment rate limiting.

    Applies rate limiting configuration to an existing deployment endpoint
    via the budapp deployment settings API.
    """

    meta = META
    executor_class = DeploymentRateLimitExecutor
