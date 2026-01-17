"""Set Output action - sets arbitrary output values.

A simple action for defining static or computed outputs that can be
referenced by subsequent steps in the pipeline.
"""

from __future__ import annotations

from typing import Any

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


class SetOutputExecutor(BaseActionExecutor):
    """Executor that sets arbitrary output values."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute the set_output action."""
        outputs = context.params.get("outputs", {})

        # Ensure outputs is a dictionary
        if not isinstance(outputs, dict):
            logger.warning(
                "set_output_invalid_type",
                step_id=context.step_id,
                type=type(outputs).__name__,
            )
            return ActionResult(
                success=False,
                error=f"outputs must be a dictionary, got {type(outputs).__name__}",
            )

        logger.info(
            "set_output_complete",
            step_id=context.step_id,
            execution_id=context.execution_id,
            output_keys=list(outputs.keys()),
        )

        return ActionResult(
            success=True,
            outputs=outputs,
        )

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate set_output parameters."""
        errors = []

        outputs = params.get("outputs")
        if outputs is not None and not isinstance(outputs, dict):
            errors.append(f"outputs must be a dictionary, got {type(outputs).__name__}")

        return errors


META = ActionMeta(
    type="set_output",
    name="Set Output",
    category="Control Flow",
    description="Sets arbitrary output values that can be referenced by subsequent steps.",
    icon="arrow-square-out",
    color="#06b6d4",
    params=[
        ParamDefinition(
            name="outputs",
            label="Outputs",
            type=ParamType.JSON,
            required=False,
            default={},
            description="Dictionary of key-value pairs to set as outputs.",
            placeholder='{"key": "value"}',
        ),
    ],
    outputs=[
        OutputDefinition(
            name="*",
            type="object",
            description="All keys from the outputs parameter become available as outputs",
        ),
    ],
    execution_mode=ExecutionMode.SYNC,
    idempotent=True,
    examples=[
        ActionExample(
            title="Set configuration values",
            params={
                "outputs": {
                    "api_url": "https://api.example.com",
                    "timeout": 30,
                    "retry_count": 3,
                }
            },
            description="Sets multiple configuration values for downstream steps",
        ),
        ActionExample(
            title="Set computed value",
            params={"outputs": {"full_name": "{{ params.first_name }} {{ params.last_name }}"}},
            description="Sets a computed value using template syntax",
        ),
    ],
)


@register_action(META)
class SetOutputAction:
    """Set Output action class for entry point registration."""

    meta = META
    executor_class = SetOutputExecutor
