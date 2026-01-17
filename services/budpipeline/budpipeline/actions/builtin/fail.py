"""Fail action - intentionally fails with a specified message.

Useful for error handling testing, conditional failure scenarios,
or signaling that a pipeline should stop.
"""

from __future__ import annotations

import structlog

from budpipeline.actions.base import (
    ActionContext,
    ActionExample,
    ActionMeta,
    ActionResult,
    BaseActionExecutor,
    ExecutionMode,
    OutputDefinition,
    ParamDefinition,
    ParamType,
    register_action,
)

logger = structlog.get_logger()


class FailExecutor(BaseActionExecutor):
    """Executor that always fails with a specified message."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute the fail action."""
        message = context.params.get("message", "Intentional failure")
        error_code = context.params.get("error_code", "INTENTIONAL_FAILURE")

        logger.warning(
            "fail_action_executed",
            step_id=context.step_id,
            execution_id=context.execution_id,
            message=message,
            error_code=error_code,
        )

        return ActionResult(
            success=False,
            outputs={
                "error_code": error_code,
                "message": message,
            },
            error=message,
        )


META = ActionMeta(
    type="fail",
    name="Fail",
    category="Control Flow",
    description="Intentionally fails the pipeline with a specified error message. Useful for error handling testing or conditional stopping.",
    icon="x-circle",
    color="#ef4444",
    params=[
        ParamDefinition(
            name="message",
            label="Error Message",
            type=ParamType.TEMPLATE,
            required=False,
            default="Intentional failure",
            description="The error message to report.",
            placeholder="Something went wrong...",
        ),
        ParamDefinition(
            name="error_code",
            label="Error Code",
            type=ParamType.STRING,
            required=False,
            default="INTENTIONAL_FAILURE",
            description="An error code for programmatic handling.",
            placeholder="ERROR_CODE",
        ),
    ],
    outputs=[
        OutputDefinition(
            name="error_code",
            type="string",
            description="The error code",
        ),
        OutputDefinition(
            name="message",
            type="string",
            description="The error message",
        ),
    ],
    execution_mode=ExecutionMode.SYNC,
    idempotent=True,
    examples=[
        ActionExample(
            title="Simple failure",
            params={
                "message": "This step should not be reached",
            },
            description="Fails with a simple message",
        ),
        ActionExample(
            title="Conditional failure with error code",
            params={
                "message": "Validation failed: {{ steps.validate.outputs.errors | join(', ') }}",
                "error_code": "VALIDATION_ERROR",
            },
            description="Fails with dynamic message and error code",
        ),
    ],
)


@register_action(META)
class FailAction:
    """Fail action class for entry point registration."""

    meta = META
    executor_class = FailExecutor
