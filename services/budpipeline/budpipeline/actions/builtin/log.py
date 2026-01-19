"""Log action - logs a message at the specified level.

This is a simple action for debugging and monitoring pipeline executions.
"""

from __future__ import annotations

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

logger = structlog.get_logger()


class LogExecutor(BaseActionExecutor):
    """Executor that logs a message."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute the log action."""
        message = context.params.get("message", "No message provided")
        level = context.params.get("level", "info").lower()

        # Map level to structlog method
        log_methods = {
            "debug": logger.debug,
            "info": logger.info,
            "warning": logger.warning,
            "error": logger.error,
        }
        log_func = log_methods.get(level, logger.info)

        log_func(
            "pipeline_log_action",
            step_id=context.step_id,
            execution_id=context.execution_id,
            message=message,
            level=level,
        )

        return ActionResult(
            success=True,
            outputs={
                "logged": True,
                "message": message,
                "level": level,
            },
        )


META = ActionMeta(
    type="log",
    name="Log",
    category="Control Flow",
    description="Logs a message at the specified level. Useful for debugging and monitoring pipeline executions.",
    icon="note",
    color="#6b7280",
    params=[
        ParamDefinition(
            name="message",
            label="Message",
            type=ParamType.TEMPLATE,
            required=False,
            default="",
            description="The message to log. Supports Jinja2 template syntax.",
            placeholder="Enter log message...",
        ),
        ParamDefinition(
            name="level",
            label="Log Level",
            type=ParamType.SELECT,
            required=False,
            default="info",
            description="The log level for the message.",
            options=[
                SelectOption(label="Debug", value="debug"),
                SelectOption(label="Info", value="info"),
                SelectOption(label="Warning", value="warning"),
                SelectOption(label="Error", value="error"),
            ],
        ),
    ],
    outputs=[
        OutputDefinition(
            name="logged",
            type="boolean",
            description="Always true when logging succeeds",
        ),
        OutputDefinition(
            name="message",
            type="string",
            description="The logged message",
        ),
        OutputDefinition(
            name="level",
            type="string",
            description="The log level used",
        ),
    ],
    execution_mode=ExecutionMode.SYNC,
    idempotent=True,
)


@register_action(META)
class LogAction:
    """Log action class for entry point registration."""

    meta = META
    executor_class = LogExecutor
