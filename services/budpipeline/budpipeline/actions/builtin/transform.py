"""Transform action - transforms input data using various operations.

Provides data transformation capabilities within pipeline flows,
supporting operations like uppercase, lowercase, key extraction, etc.
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
    SelectOption,
    register_action,
)

logger = structlog.get_logger()


class TransformExecutor(BaseActionExecutor):
    """Executor that transforms input data."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute the transform action."""
        input_data = context.params.get("input", {})
        operation = context.params.get("operation", "passthrough")

        logger.debug(
            "transform_executing",
            step_id=context.step_id,
            operation=operation,
            input_type=type(input_data).__name__,
        )

        try:
            result = self._apply_operation(input_data, operation)

            logger.info(
                "transform_complete",
                step_id=context.step_id,
                execution_id=context.execution_id,
                operation=operation,
                result_type=type(result).__name__,
            )

            return ActionResult(
                success=True,
                outputs={
                    "result": result,
                    "operation": operation,
                    "input_type": type(input_data).__name__,
                    "output_type": type(result).__name__,
                },
            )
        except Exception as e:
            logger.error(
                "transform_failed",
                step_id=context.step_id,
                operation=operation,
                error=str(e),
            )
            return ActionResult(
                success=False,
                error=f"Transform failed: {e}",
            )

    def _apply_operation(self, input_data: Any, operation: str) -> Any:
        """Apply the specified transformation operation."""
        if operation == "passthrough":
            return input_data

        if operation == "uppercase":
            if isinstance(input_data, str):
                return input_data.upper()
            if isinstance(input_data, dict):
                return {k: v.upper() if isinstance(v, str) else v for k, v in input_data.items()}
            return input_data

        if operation == "lowercase":
            if isinstance(input_data, str):
                return input_data.lower()
            if isinstance(input_data, dict):
                return {k: v.lower() if isinstance(v, str) else v for k, v in input_data.items()}
            return input_data

        if operation == "keys":
            return list(input_data.keys()) if isinstance(input_data, dict) else []

        if operation == "values":
            return list(input_data.values()) if isinstance(input_data, dict) else []

        if operation == "count":
            return len(input_data) if hasattr(input_data, "__len__") else 0

        if operation == "flatten":
            if isinstance(input_data, list):
                result = []
                for item in input_data:
                    if isinstance(item, list):
                        result.extend(item)
                    else:
                        result.append(item)
                return result
            return input_data

        if operation == "unique":
            if isinstance(input_data, list):
                # Preserve order while removing duplicates
                seen = set()
                result = []
                for item in input_data:
                    key = str(item) if isinstance(item, dict) else item
                    if key not in seen:
                        seen.add(key)
                        result.append(item)
                return result
            return input_data

        if operation == "sort":
            if isinstance(input_data, list):
                try:
                    return sorted(input_data)
                except TypeError:
                    # Mixed types, sort by string representation
                    return sorted(input_data, key=str)
            return input_data

        if operation == "reverse":
            if isinstance(input_data, list):
                return list(reversed(input_data))
            if isinstance(input_data, str):
                return input_data[::-1]
            return input_data

        # Unknown operation - passthrough
        return input_data


META = ActionMeta(
    type="transform",
    name="Transform",
    category="Control Flow",
    description="Transforms input data using various operations like uppercase, lowercase, extract keys/values, count, etc.",
    icon="swap",
    color="#10b981",
    params=[
        ParamDefinition(
            name="input",
            label="Input",
            type=ParamType.JSON,
            required=False,
            default={},
            description="The input data to transform. Can be any JSON value.",
        ),
        ParamDefinition(
            name="operation",
            label="Operation",
            type=ParamType.SELECT,
            required=False,
            default="passthrough",
            description="The transformation operation to apply.",
            options=[
                SelectOption(label="Passthrough", value="passthrough"),
                SelectOption(label="Uppercase", value="uppercase"),
                SelectOption(label="Lowercase", value="lowercase"),
                SelectOption(label="Extract Keys", value="keys"),
                SelectOption(label="Extract Values", value="values"),
                SelectOption(label="Count", value="count"),
                SelectOption(label="Flatten List", value="flatten"),
                SelectOption(label="Remove Duplicates", value="unique"),
                SelectOption(label="Sort", value="sort"),
                SelectOption(label="Reverse", value="reverse"),
            ],
        ),
    ],
    outputs=[
        OutputDefinition(
            name="result",
            type="object",
            description="The transformed data",
        ),
        OutputDefinition(
            name="operation",
            type="string",
            description="The operation that was applied",
        ),
        OutputDefinition(
            name="input_type",
            type="string",
            description="The type of the input data",
        ),
        OutputDefinition(
            name="output_type",
            type="string",
            description="The type of the output data",
        ),
    ],
    execution_mode=ExecutionMode.SYNC,
    idempotent=True,
    examples=[
        ActionExample(
            title="Uppercase transformation",
            params={
                "input": {"name": "hello", "status": "active"},
                "operation": "uppercase",
            },
            description="Transforms string values to uppercase",
        ),
        ActionExample(
            title="Extract dictionary keys",
            params={
                "input": {"a": 1, "b": 2, "c": 3},
                "operation": "keys",
            },
            description="Extracts keys from a dictionary: ['a', 'b', 'c']",
        ),
    ],
)


@register_action(META)
class TransformAction:
    """Transform action class for entry point registration."""

    meta = META
    executor_class = TransformExecutor
