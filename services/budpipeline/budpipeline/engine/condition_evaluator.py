"""Condition Evaluator - evaluates conditional expressions for step execution.

Supports:
- {{ params.xxx }} for workflow parameters
- {{ steps.xxx.outputs.yyy }} for step outputs
- Comparison operators (==, !=, <, >, <=, >=)
- Logical operators (and, or, not)
- Containment operators (in, not in)
- Jinja2 filters (default, length, lower, upper, etc.)
"""

import re
from typing import Any

from jinja2 import (
    BaseLoader,
    Environment,
    StrictUndefined,
    TemplateSyntaxError,
    Undefined,
    UndefinedError,
)

from budpipeline.commons.exceptions import ConditionEvaluationError
from budpipeline.engine.param_resolver import (
    AttrDict,
    _wrap_for_template,
)


class ConditionEvaluator:
    """Evaluates conditional expressions for workflow step execution.

    Uses Jinja2 to evaluate expressions that determine whether a step
    should execute based on parameters and previous step outputs.
    """

    # Pattern to detect templates
    _TEMPLATE_PATTERN = re.compile(r"\{\{.*?\}\}")

    # Pattern to extract variable names
    _VARIABLE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_.[\]]*)")

    @classmethod
    def _get_environment(cls, strict: bool = True) -> Environment:
        """Get Jinja2 environment.

        Args:
            strict: If True, raise on undefined variables

        Returns:
            Configured Jinja2 Environment
        """
        return Environment(
            loader=BaseLoader(),
            undefined=StrictUndefined if strict else Undefined,
            autoescape=False,
        )

    @classmethod
    def evaluate(
        cls,
        condition: str | None,
        params: dict[str, Any],
        step_outputs: dict[str, dict[str, Any]],
        strict: bool = False,
    ) -> bool:
        """Evaluate a condition expression.

        Args:
            condition: The condition expression (e.g., "{{ params.enabled }}")
            params: Workflow parameters
            step_outputs: Dict mapping step_id to outputs dict
            strict: If True, raise on undefined variables

        Returns:
            True if condition evaluates to truthy, False otherwise

        Raises:
            ConditionEvaluationError: If condition evaluation fails
        """
        # None or empty condition means always execute
        if condition is None or not condition.strip():
            return True

        condition = condition.strip()

        # Handle literal true/false
        if condition.lower() == "true":
            return True
        if condition.lower() == "false":
            return False

        # Check for template syntax
        if not cls._TEMPLATE_PATTERN.search(condition):
            # No template, try to evaluate as literal boolean
            return cls._evaluate_literal(condition)

        # Check for unbalanced braces
        open_count = condition.count("{{")
        close_count = condition.count("}}")
        if open_count != close_count:
            raise ConditionEvaluationError(
                "Unbalanced template braces",
                condition=condition,
            )

        # Build context for template rendering
        steps_dict = AttrDict(
            {
                step_id: AttrDict({"outputs": _wrap_for_template(outputs, strict=strict)})
                for step_id, outputs in step_outputs.items()
            }
        )
        steps_dict._strict = strict
        # Set _strict on nested AttrDicts for step outputs
        for step_id in steps_dict:
            step_dict = dict.__getitem__(steps_dict, step_id)
            if isinstance(step_dict, AttrDict):
                step_dict._strict = strict

        context = {
            "params": _wrap_for_template(params, strict=strict),
            "steps": steps_dict,
            "true": True,
            "false": False,
            "none": None,
        }

        env = cls._get_environment(strict=strict)

        try:
            template = env.from_string(condition)
            rendered = template.render(context)

            # Convert rendered result to boolean
            return cls._to_boolean(rendered.strip())

        except TemplateSyntaxError as e:
            raise ConditionEvaluationError(
                f"Invalid condition syntax: {e}",
                condition=condition,
            ) from e
        except UndefinedError as e:
            if strict:
                raise ConditionEvaluationError(
                    f"Undefined variable in condition: {e}",
                    condition=condition,
                ) from e
            # In non-strict mode, undefined means False
            return False
        except Exception as e:
            raise ConditionEvaluationError(
                f"Condition evaluation failed: {e}",
                condition=condition,
            ) from e

    @classmethod
    def _evaluate_literal(cls, value: str) -> bool:
        """Evaluate a literal value as boolean.

        Args:
            value: String value to evaluate

        Returns:
            Boolean result
        """
        value = value.strip().lower()
        if value in ("true", "1", "yes"):
            return True
        if value in ("false", "0", "no", ""):
            return False
        # Any other non-empty string is truthy
        return bool(value)

    @classmethod
    def _to_boolean(cls, value: str) -> bool:
        """Convert a rendered string value to boolean.

        Args:
            value: Rendered string value

        Returns:
            Boolean result
        """
        # Handle explicit True/False strings
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False

        # Handle empty string
        if not value:
            return False

        # Handle None string
        if value.lower() == "none":
            return False

        # Handle numeric strings
        try:
            num = float(value)
            return bool(num)
        except ValueError:
            pass

        # Handle empty list/dict representations
        if value in ("[]", "{}", "()", "set()"):
            return False

        # Any other non-empty value is truthy
        return True

    @classmethod
    def validate(
        cls,
        condition: str | None,
        available_params: set[str],
        available_steps: set[str],
    ) -> list[str]:
        """Validate that all references in a condition exist.

        Args:
            condition: The condition expression
            available_params: Set of available parameter names
            available_steps: Set of available step IDs

        Returns:
            List of validation errors (empty if valid)
        """
        if condition is None or not condition.strip():
            return []

        errors: list[str] = []
        variables = cls._extract_variables(condition)

        for var in variables:
            if var.startswith("params."):
                param_name = var.split(".")[1]
                if param_name not in available_params:
                    errors.append(f"Unknown parameter: {param_name}")
            elif var.startswith("steps."):
                parts = var.split(".")
                if len(parts) >= 2:
                    step_id = parts[1]
                    if step_id not in available_steps:
                        errors.append(f"Unknown step: {step_id}")

        return errors

    @classmethod
    def _extract_variables(cls, condition: str) -> set[str]:
        """Extract variable references from a condition.

        Args:
            condition: The condition expression

        Returns:
            Set of variable paths (e.g., "params.name", "steps.step1.outputs.x")
        """
        if not condition:
            return set()

        matches = cls._VARIABLE_PATTERN.findall(condition)
        return set(matches)

    @classmethod
    def has_condition(cls, condition: str | None) -> bool:
        """Check if a condition is present and non-trivial.

        A trivial condition is None, empty, or just "true"/"false".

        Args:
            condition: The condition expression

        Returns:
            True if condition is non-trivial
        """
        if condition is None:
            return False

        stripped = condition.strip().lower()
        if not stripped or stripped in ("true", "false"):
            return False

        return True
