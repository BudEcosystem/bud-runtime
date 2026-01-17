"""Aggregate action - combines multiple inputs using various operations.

Useful for collecting outputs from parallel branches, summing values,
joining strings, or merging dictionaries.
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


class AggregateExecutor(BaseActionExecutor):
    """Executor that aggregates multiple inputs."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute the aggregate action."""
        inputs = context.params.get("inputs", [])
        operation = context.params.get("operation", "list")
        separator = context.params.get("separator", ", ")

        logger.debug(
            "aggregate_executing",
            step_id=context.step_id,
            operation=operation,
            input_count=len(inputs) if isinstance(inputs, list) else 0,
        )

        try:
            result = self._apply_operation(inputs, operation, separator)

            logger.info(
                "aggregate_complete",
                step_id=context.step_id,
                execution_id=context.execution_id,
                operation=operation,
                input_count=len(inputs) if isinstance(inputs, list) else 0,
            )

            return ActionResult(
                success=True,
                outputs={
                    "result": result,
                    "count": len(inputs) if isinstance(inputs, list) else 0,
                    "operation": operation,
                },
            )
        except Exception as e:
            logger.error(
                "aggregate_failed",
                step_id=context.step_id,
                operation=operation,
                error=str(e),
            )
            return ActionResult(
                success=False,
                error=f"Aggregate failed: {e}",
            )

    def _apply_operation(self, inputs: Any, operation: str, separator: str) -> Any:
        """Apply the specified aggregation operation."""
        # Ensure inputs is a list
        if not isinstance(inputs, list):
            inputs = [inputs] if inputs is not None else []

        if operation == "list":
            return list(inputs)

        if operation == "sum":
            if all(isinstance(i, int | float) for i in inputs):
                return sum(inputs)
            return 0

        if operation == "join":
            return separator.join(str(i) for i in inputs)

        if operation == "merge":
            result: dict[str, Any] = {}
            for item in inputs:
                if isinstance(item, dict):
                    result.update(item)
            return result

        if operation == "first":
            return inputs[0] if inputs else None

        if operation == "last":
            return inputs[-1] if inputs else None

        if operation == "min":
            if inputs and all(isinstance(i, int | float) for i in inputs):
                return min(inputs)
            return None

        if operation == "max":
            if inputs and all(isinstance(i, int | float) for i in inputs):
                return max(inputs)
            return None

        if operation == "average":
            if inputs and all(isinstance(i, int | float) for i in inputs):
                return sum(inputs) / len(inputs)
            return None

        if operation == "count":
            return len(inputs)

        if operation == "flatten":
            result_list = []
            for item in inputs:
                if isinstance(item, list):
                    result_list.extend(item)
                else:
                    result_list.append(item)
            return result_list

        # Default to list
        return list(inputs)

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate aggregate parameters."""
        errors = []

        inputs = params.get("inputs")
        if inputs is not None and not isinstance(inputs, list):
            errors.append("inputs must be a list")

        operation = params.get("operation", "list")
        valid_operations = {
            "list",
            "sum",
            "join",
            "merge",
            "first",
            "last",
            "min",
            "max",
            "average",
            "count",
            "flatten",
        }
        if operation not in valid_operations:
            errors.append(f"Invalid operation: {operation}. Valid: {', '.join(valid_operations)}")

        return errors


META = ActionMeta(
    type="aggregate",
    name="Aggregate",
    category="Control Flow",
    description="Combines multiple inputs using various operations like sum, join, merge, min, max, etc.",
    icon="stack",
    color="#f59e0b",
    params=[
        ParamDefinition(
            name="inputs",
            label="Inputs",
            type=ParamType.JSON,
            required=False,
            default=[],
            description="List of values to aggregate.",
        ),
        ParamDefinition(
            name="operation",
            label="Operation",
            type=ParamType.SELECT,
            required=False,
            default="list",
            description="The aggregation operation to apply.",
            options=[
                SelectOption(label="List", value="list"),
                SelectOption(label="Sum", value="sum"),
                SelectOption(label="Join Text", value="join"),
                SelectOption(label="Merge Dicts", value="merge"),
                SelectOption(label="First", value="first"),
                SelectOption(label="Last", value="last"),
                SelectOption(label="Min", value="min"),
                SelectOption(label="Max", value="max"),
                SelectOption(label="Average", value="average"),
                SelectOption(label="Count", value="count"),
                SelectOption(label="Flatten", value="flatten"),
            ],
        ),
        ParamDefinition(
            name="separator",
            label="Separator",
            type=ParamType.STRING,
            required=False,
            default=", ",
            description="Separator for join operation.",
            placeholder=", ",
        ),
    ],
    outputs=[
        OutputDefinition(
            name="result",
            type="object",
            description="The aggregated result",
        ),
        OutputDefinition(
            name="count",
            type="number",
            description="Number of inputs aggregated",
        ),
        OutputDefinition(
            name="operation",
            type="string",
            description="The operation that was applied",
        ),
    ],
    execution_mode=ExecutionMode.SYNC,
    idempotent=True,
    examples=[
        ActionExample(
            title="Sum numbers",
            params={
                "inputs": [1, 2, 3, 4, 5],
                "operation": "sum",
            },
            description="Sums the numbers: result = 15",
        ),
        ActionExample(
            title="Join strings",
            params={
                "inputs": ["hello", "world"],
                "operation": "join",
                "separator": " ",
            },
            description="Joins strings: result = 'hello world'",
        ),
        ActionExample(
            title="Merge dictionaries",
            params={
                "inputs": [{"a": 1}, {"b": 2}, {"c": 3}],
                "operation": "merge",
            },
            description="Merges dicts: result = {a: 1, b: 2, c: 3}",
        ),
    ],
)


@register_action(META)
class AggregateAction:
    """Aggregate action class for entry point registration."""

    meta = META
    executor_class = AggregateExecutor
