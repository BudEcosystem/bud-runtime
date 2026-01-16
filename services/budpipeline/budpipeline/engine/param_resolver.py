"""Parameter Resolver - resolves Jinja2 templates in workflow parameters.

Supports:
- {{ params.xxx }} for workflow parameters
- {{ steps.xxx.outputs.yyy }} for step outputs
- Jinja2 filters (default, upper, lower, etc.)
- Nested object/array access
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

from budpipeline.commons.exceptions import ParameterResolutionError


class _ChainableUndefined(Undefined):
    """Undefined that allows chained attribute access.

    Extends Jinja2's Undefined to allow expressions like
    steps.missing.outputs.x to work without raising AttributeError,
    while still supporting the default filter and strict mode.
    """

    def __getattr__(self, name: str) -> "_ChainableUndefined":
        # Return another ChainableUndefined for chained access
        return _ChainableUndefined(name=f"{self._undefined_name}.{name}")

    def __getitem__(self, key: Any) -> "_ChainableUndefined":
        return _ChainableUndefined(name=f"{self._undefined_name}[{key!r}]")


class _StrictChainableUndefined(StrictUndefined):
    """Strict undefined that allows chained attribute access.

    Like _ChainableUndefined but raises UndefinedError when rendered,
    matching StrictUndefined behavior.
    """

    def __getattr__(self, name: str) -> "_StrictChainableUndefined":
        # Return another StrictChainableUndefined for chained access
        return _StrictChainableUndefined(name=f"{self._undefined_name}.{name}")

    def __getitem__(self, key: Any) -> "_StrictChainableUndefined":
        return _StrictChainableUndefined(name=f"{self._undefined_name}[{key!r}]")


class AttrDict(dict):
    """Dict that prioritizes key access over method access for attribute lookup.

    This allows templates like {{ params.items }} to access params["items"]
    instead of the dict.items() method.
    """

    _strict: bool = False

    def __getattribute__(self, name: str) -> Any:
        # Don't intercept special/private methods
        if name.startswith("_"):
            return super().__getattribute__(name)

        # First check if this name exists as a key in the dict
        try:
            if dict.__contains__(self, name):
                value = dict.__getitem__(self, name)
                # Propagate strict mode to nested AttrDicts
                strict = object.__getattribute__(self, "_strict")
                return _wrap_for_template(value, strict=strict)
        except (KeyError, TypeError):
            pass

        # For missing keys, return ChainableUndefined to allow chained access
        # and support default filter / strict mode
        strict = object.__getattribute__(self, "_strict")
        if strict:
            return _StrictChainableUndefined(name=name)
        return _ChainableUndefined(name=name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_strict":
            object.__setattr__(self, name, value)
        else:
            self[name] = value


def _wrap_for_template(value: Any, strict: bool = False) -> Any:
    """Wrap values for template access, converting dicts to AttrDict.

    Args:
        value: The value to wrap
        strict: If True, use strict undefined handling
    """
    if isinstance(value, dict) and not isinstance(value, AttrDict):
        wrapped = AttrDict(value)
        wrapped._strict = strict
        return wrapped
    elif isinstance(value, list):
        return [_wrap_for_template(item, strict=strict) for item in value]
    return value


class ParamResolver:
    """Resolves Jinja2 templates in workflow parameters.

    Provides template resolution for:
    - Workflow parameters (params.xxx)
    - Step outputs (steps.xxx.outputs.yyy)
    - Default values and filters
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
        env = Environment(
            loader=BaseLoader(),
            undefined=StrictUndefined if strict else Undefined,
            autoescape=False,
        )
        return env

    @classmethod
    def resolve(
        cls,
        value: Any,
        params: dict[str, Any],
        step_outputs: dict[str, dict[str, Any]],
        strict: bool = False,
    ) -> Any:
        """Resolve templates in a value.

        Args:
            value: The value containing templates (string, dict, list, or primitive)
            params: Workflow parameters
            step_outputs: Dict mapping step_id to outputs dict
            strict: If True, raise on undefined variables

        Returns:
            Resolved value with templates replaced

        Raises:
            ParameterResolutionError: If template resolution fails
        """
        if value is None:
            return None

        if isinstance(value, str):
            return cls._resolve_string(value, params, step_outputs, strict)
        elif isinstance(value, dict):
            return cls.resolve_dict(value, params, step_outputs, strict)
        elif isinstance(value, list):
            return cls.resolve_list(value, params, step_outputs, strict)
        else:
            # Primitive types (int, float, bool) pass through unchanged
            return value

    @classmethod
    def _resolve_string(
        cls,
        value: str,
        params: dict[str, Any],
        step_outputs: dict[str, dict[str, Any]],
        strict: bool = False,
    ) -> Any:
        """Resolve templates in a string value.

        Args:
            value: String potentially containing templates
            params: Workflow parameters
            step_outputs: Step outputs
            strict: If True, raise on undefined

        Returns:
            Resolved value (may be non-string if template is the entire value)
        """
        if not value:
            return value

        # Check for unbalanced templates (opening {{ without closing }})
        open_count = value.count("{{")
        close_count = value.count("}}")
        if open_count != close_count:
            raise ParameterResolutionError(
                "Unbalanced template braces",
                template=value,
            )

        if not cls._TEMPLATE_PATTERN.search(value):
            return value

        # Build context for template rendering with AttrDict wrappers
        # This allows attribute-style access (params.name) to work on dicts
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
        }

        env = cls._get_environment(strict=strict)

        try:
            template = env.from_string(value)
            rendered = template.render(context)

            # If the original was a pure template (just {{ ... }}),
            # try to preserve the original type
            stripped = value.strip()
            if stripped.startswith("{{") and stripped.endswith("}}") and stripped.count("{{") == 1:
                # This was a pure template expression
                # Evaluate it to get the actual value
                expr = stripped[2:-2].strip()

                # Handle filters by extracting the base expression
                base_expr = expr.split("|")[0].strip()

                # Try to get the original value
                try:
                    result = cls._evaluate_expression(base_expr, context)

                    # If there are filters, infer the type from the rendered result
                    if "|" in expr:
                        return cls._infer_type(rendered)
                    return result
                except (KeyError, TypeError, AttributeError):
                    # If there are filters (like default), still try to infer type
                    if "|" in expr:
                        return cls._infer_type(rendered)
                    # Fall through to return rendered string

            return rendered

        except TemplateSyntaxError as e:
            raise ParameterResolutionError(
                f"Invalid template syntax: {e}",
                template=value,
            ) from e
        except UndefinedError as e:
            if strict:
                raise ParameterResolutionError(
                    f"Undefined variable in template: {e}",
                    template=value,
                ) from e
            # In non-strict mode, return empty string for undefined
            return ""
        except Exception as e:
            raise ParameterResolutionError(
                f"Template resolution failed: {e}",
                template=value,
            ) from e

    @classmethod
    def _evaluate_expression(cls, expr: str, context: dict[str, Any]) -> Any:
        """Evaluate a simple expression to get its value.

        Args:
            expr: Expression like "params.name" or "steps.step1.outputs.result"
            context: Context dict

        Returns:
            The value
        """
        parts = expr.replace("]", "").replace("[", ".").split(".")
        result = context

        for part in parts:
            if part.isdigit():
                result = result[int(part)]
            elif isinstance(result, dict):
                result = result[part]
            else:
                result = getattr(result, part)

        return result

    @classmethod
    def _infer_type(cls, rendered: str) -> Any:
        """Infer the type of a rendered string value.

        Tries to convert the string to int, float, bool, dict, list, or keeps as string.

        Args:
            rendered: Rendered string value

        Returns:
            Value with inferred type
        """
        import ast

        # Try integer
        try:
            return int(rendered)
        except ValueError:
            pass

        # Try float
        try:
            return float(rendered)
        except ValueError:
            pass

        # Try boolean
        if rendered.lower() in ("true", "false"):
            return rendered.lower() == "true"

        # Try parsing as Python literal (for {}, [], None, etc.)
        try:
            return ast.literal_eval(rendered)
        except (ValueError, SyntaxError):
            pass

        # Keep as string
        return rendered

    @classmethod
    def _coerce_type(cls, rendered: str, original: Any) -> Any:
        """Coerce rendered string to match original type if possible.

        Args:
            rendered: Rendered string value
            original: Original value for type hint

        Returns:
            Coerced value
        """
        if isinstance(original, bool):
            return rendered.lower() in ("true", "1", "yes")
        elif isinstance(original, int):
            try:
                return int(rendered)
            except ValueError:
                return rendered
        elif isinstance(original, float):
            try:
                return float(rendered)
            except ValueError:
                return rendered
        return rendered

    @classmethod
    def resolve_dict(
        cls,
        template: dict[str, Any],
        params: dict[str, Any],
        step_outputs: dict[str, dict[str, Any]],
        strict: bool = False,
    ) -> dict[str, Any]:
        """Resolve templates in all values of a dictionary.

        Args:
            template: Dictionary with template values
            params: Workflow parameters
            step_outputs: Step outputs
            strict: If True, raise on undefined

        Returns:
            New dictionary with resolved values
        """
        result = {}
        for key, value in template.items():
            result[key] = cls.resolve(value, params, step_outputs, strict)
        return result

    @classmethod
    def resolve_list(
        cls,
        template: list[Any],
        params: dict[str, Any],
        step_outputs: dict[str, dict[str, Any]],
        strict: bool = False,
    ) -> list[Any]:
        """Resolve templates in all elements of a list.

        Args:
            template: List with template values
            params: Workflow parameters
            step_outputs: Step outputs
            strict: If True, raise on undefined

        Returns:
            New list with resolved values
        """
        return [cls.resolve(item, params, step_outputs, strict) for item in template]

    @classmethod
    def has_templates(cls, value: Any) -> bool:
        """Check if a value contains any templates.

        Args:
            value: Value to check (string, dict, list, or primitive)

        Returns:
            True if value contains templates
        """
        if isinstance(value, str):
            return bool(cls._TEMPLATE_PATTERN.search(value))
        elif isinstance(value, dict):
            return any(cls.has_templates(v) for v in value.values())
        elif isinstance(value, list):
            return any(cls.has_templates(item) for item in value)
        return False

    @classmethod
    def extract_variables(cls, value: Any) -> set[str]:
        """Extract all variable references from templates.

        Args:
            value: Value containing templates

        Returns:
            Set of variable paths (e.g., "params.name", "steps.step1.outputs.x")
        """
        variables: set[str] = set()

        if isinstance(value, str):
            matches = cls._VARIABLE_PATTERN.findall(value)
            variables.update(matches)
        elif isinstance(value, dict):
            for v in value.values():
                variables.update(cls.extract_variables(v))
        elif isinstance(value, list):
            for item in value:
                variables.update(cls.extract_variables(item))

        return variables

    @classmethod
    def validate_references(
        cls,
        value: Any,
        available_params: set[str],
        available_steps: set[str],
    ) -> list[str]:
        """Validate that all references in templates exist.

        Args:
            value: Value containing templates
            available_params: Set of available parameter names
            available_steps: Set of available step IDs

        Returns:
            List of validation errors (empty if valid)
        """
        errors: list[str] = []
        variables = cls.extract_variables(value)

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
