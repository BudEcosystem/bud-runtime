"""Delay action - introduces a timed delay in pipeline execution.

Useful for rate limiting, waiting for external systems, or creating
time-based patterns in pipeline flows.
"""

from __future__ import annotations

import asyncio

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
    ValidationRules,
    register_action,
)

logger = structlog.get_logger()


class DelayExecutor(BaseActionExecutor):
    """Executor that introduces a delay."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute the delay action."""
        duration = context.params.get("duration_seconds", 1.0)
        reason = context.params.get("reason", "")

        # Ensure duration is a positive number
        try:
            duration = float(duration)
            if duration < 0:
                return ActionResult(
                    success=False,
                    error="Duration must be a non-negative number",
                )
        except (TypeError, ValueError):
            return ActionResult(
                success=False,
                error=f"Invalid duration value: {duration}",
            )

        logger.info(
            "pipeline_delay_start",
            step_id=context.step_id,
            execution_id=context.execution_id,
            duration_seconds=duration,
            reason=reason,
        )

        await asyncio.sleep(duration)

        logger.info(
            "pipeline_delay_complete",
            step_id=context.step_id,
            execution_id=context.execution_id,
            duration_seconds=duration,
        )

        return ActionResult(
            success=True,
            outputs={
                "delayed": True,
                "duration_seconds": duration,
                "reason": reason,
            },
        )

    def validate_params(self, params: dict) -> list[str]:
        """Validate delay parameters."""
        errors = []
        duration = params.get("duration_seconds")

        if duration is not None:
            try:
                duration_val = float(duration)
                if duration_val < 0:
                    errors.append("duration_seconds must be non-negative")
                if duration_val > 3600:  # Max 1 hour
                    errors.append("duration_seconds cannot exceed 3600 (1 hour)")
            except (TypeError, ValueError):
                errors.append(f"duration_seconds must be a number, got: {type(duration).__name__}")

        return errors


META = ActionMeta(
    type="delay",
    name="Delay",
    category="Control Flow",
    description="Introduces a timed delay in pipeline execution. Useful for rate limiting or waiting for external systems.",
    icon="timer",
    color="#6b7280",
    params=[
        ParamDefinition(
            name="duration_seconds",
            label="Duration (seconds)",
            type=ParamType.NUMBER,
            required=False,
            default=1.0,
            description="The number of seconds to wait.",
            placeholder="1.0",
            validation=ValidationRules(min=0, max=3600),
        ),
        ParamDefinition(
            name="reason",
            label="Reason",
            type=ParamType.STRING,
            required=False,
            default="",
            description="Optional reason for the delay (for logging).",
            placeholder="Waiting for rate limit...",
        ),
    ],
    outputs=[
        OutputDefinition(
            name="delayed",
            type="boolean",
            description="Always true when delay completes",
        ),
        OutputDefinition(
            name="duration_seconds",
            type="number",
            description="The actual delay duration",
        ),
        OutputDefinition(
            name="reason",
            type="string",
            description="The delay reason if provided",
        ),
    ],
    execution_mode=ExecutionMode.SYNC,
    timeout_seconds=3660,  # Slightly more than max delay
    idempotent=True,
)


@register_action(META)
class DelayAction:
    """Delay action class for entry point registration."""

    meta = META
    executor_class = DelayExecutor
