"""Built-in handlers for common workflow actions."""

import asyncio
import logging
from typing import Any

from budpipeline.engine.condition_evaluator import ConditionEvaluator
from budpipeline.handlers.base import BaseHandler, HandlerContext, HandlerResult
from budpipeline.handlers.registry import register_handler

logger = logging.getLogger(__name__)


@register_handler("log")
class LogHandler(BaseHandler):
    """Handler that logs a message."""

    name = "Log Handler"
    description = "Logs a message at the specified level"

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters."""
        return []  # All params are optional

    async def execute(self, context: HandlerContext) -> HandlerResult:
        """Execute log action."""
        message = context.params.get("message", "No message provided")
        level = context.params.get("level", "info").lower()

        log_func = getattr(logger, level, logger.info)
        log_func(f"[{context.step_id}] {message}")

        return HandlerResult(
            success=True,
            outputs={"logged": True, "message": message},
        )


@register_handler("delay")
class DelayHandler(BaseHandler):
    """Handler that introduces a delay."""

    name = "Delay Handler"
    description = "Introduces a delay in seconds"

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters."""
        return []

    async def execute(self, context: HandlerContext) -> HandlerResult:
        """Execute delay action."""
        seconds = context.params.get("seconds", 1)

        logger.info(f"[{context.step_id}] Delaying for {seconds} seconds")
        await asyncio.sleep(seconds)

        return HandlerResult(
            success=True,
            outputs={"delayed": True, "seconds": seconds},
        )


@register_handler("transform")
class TransformHandler(BaseHandler):
    """Handler that transforms input data."""

    name = "Transform Handler"
    description = "Transforms input data using various operations"

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters."""
        return []

    async def execute(self, context: HandlerContext) -> HandlerResult:
        """Execute transform action."""
        input_data = context.params.get("input", {})
        operation = context.params.get("operation", "passthrough")

        try:
            if operation == "passthrough":
                result = input_data
            elif operation == "uppercase":
                if isinstance(input_data, str):
                    result = input_data.upper()
                elif isinstance(input_data, dict):
                    result = {
                        k: v.upper() if isinstance(v, str) else v for k, v in input_data.items()
                    }
                else:
                    result = input_data
            elif operation == "lowercase":
                if isinstance(input_data, str):
                    result = input_data.lower()
                elif isinstance(input_data, dict):
                    result = {
                        k: v.lower() if isinstance(v, str) else v for k, v in input_data.items()
                    }
                else:
                    result = input_data
            elif operation == "keys":
                result = list(input_data.keys()) if isinstance(input_data, dict) else []
            elif operation == "values":
                result = list(input_data.values()) if isinstance(input_data, dict) else []
            elif operation == "count":
                result = len(input_data) if hasattr(input_data, "__len__") else 0
            else:
                result = input_data

            return HandlerResult(
                success=True,
                outputs={"result": result, "operation": operation},
            )
        except Exception as e:
            return HandlerResult(
                success=False,
                error=f"Transform failed: {str(e)}",
            )


@register_handler("http_request")
class HttpRequestHandler(BaseHandler):
    """Handler that makes HTTP requests (mock for testing)."""

    name = "HTTP Request Handler"
    description = "Makes HTTP requests to external services"

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters."""
        return []

    async def execute(self, context: HandlerContext) -> HandlerResult:
        """Execute HTTP request action (mock)."""
        url = context.params.get("url", "")
        method = context.params.get("method", "GET").upper()
        context.params.get("headers", {})
        context.params.get("body", {})

        logger.info(f"[{context.step_id}] Mock HTTP {method} to {url}")

        # Mock response for testing
        return HandlerResult(
            success=True,
            outputs={
                "status_code": 200,
                "response": {"mock": True, "url": url, "method": method},
                "headers": {"content-type": "application/json"},
            },
        )


@register_handler("conditional")
class ConditionalHandler(BaseHandler):
    """Handler that routes to different steps based on multiple conditions.

    Supports multi-branch conditional routing where each branch has a
    Jinja2 condition expression and a target step. The first matching
    branch wins (evaluated in order).

    Parameters:
        branches: List of branch definitions, each containing:
            - id: Unique branch identifier
            - label: Display name for the branch
            - condition: Jinja2 condition expression
            - target_step: Step ID to route to when condition matches

    Legacy Parameters (backward compatibility):
        condition: Boolean or expression to evaluate
        true_result: Result when condition is true
        false_result: Result when condition is false

    Outputs:
        matched_branch: ID of the matched branch (or None)
        matched_label: Label of the matched branch (or "none")
        target_step: Step ID to execute next (or None)
        result: For legacy mode, the true/false result value
        branch: For legacy mode, "true" or "false"
    """

    action_type = "conditional"
    name = "Conditional Branch"
    description = "Route to different steps based on conditions"

    def get_required_params(self) -> list[str]:
        """Get list of required parameters."""
        return []  # branches or legacy params

    def get_optional_params(self) -> dict[str, Any]:
        """Get optional parameters with defaults."""
        return {
            "branches": [],
            "condition": True,
            "true_result": {"branch": "true"},
            "false_result": {"branch": "false"},
        }

    def get_output_names(self) -> list[str]:
        """Get list of output names."""
        return ["matched_branch", "matched_label", "target_step", "result", "branch"]

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters."""
        errors = []
        branches = params.get("branches", [])

        if branches:
            for i, branch in enumerate(branches):
                if not isinstance(branch, dict):
                    errors.append(f"Branch {i} must be a dictionary")
                    continue
                if not branch.get("id"):
                    errors.append(f"Branch {i} missing 'id' field")
                if not branch.get("condition"):
                    errors.append(f"Branch {i} missing 'condition' field")

        return errors

    async def execute(self, context: HandlerContext) -> HandlerResult:
        """Execute conditional action with multi-branch support."""
        branches = context.params.get("branches", [])

        # Multi-branch mode
        if branches:
            logger.info(f"[{context.step_id}] Evaluating {len(branches)} conditional branches")

            for branch in branches:
                branch_id = branch.get("id", "unknown")
                branch_label = branch.get("label", branch_id)
                condition = branch.get("condition", "true")
                target_step = branch.get("target_step")

                try:
                    # Evaluate condition using ConditionEvaluator
                    should_execute = ConditionEvaluator.evaluate(
                        condition,
                        context.workflow_params,
                        context.step_outputs,
                    )

                    logger.debug(
                        f"[{context.step_id}] Branch '{branch_label}' "
                        f"condition '{condition}' = {should_execute}"
                    )

                    if should_execute:
                        logger.info(
                            f"[{context.step_id}] Matched branch '{branch_label}' "
                            f"-> target: {target_step}"
                        )
                        return HandlerResult(
                            success=True,
                            outputs={
                                "matched_branch": branch_id,
                                "matched_label": branch_label,
                                "target_step": target_step,
                                # Legacy compatibility
                                "result": branch_label,
                                "branch": branch_id,
                            },
                        )

                except Exception as e:
                    logger.warning(
                        f"[{context.step_id}] Error evaluating branch '{branch_label}' "
                        f"condition: {e}"
                    )
                    continue

            # No branch matched
            logger.info(f"[{context.step_id}] No conditional branch matched")
            return HandlerResult(
                success=True,
                outputs={
                    "matched_branch": None,
                    "matched_label": "none",
                    "target_step": None,
                    "result": None,
                    "branch": "none",
                },
            )

        # Legacy mode (backward compatibility)
        condition_value = context.params.get("condition", True)
        true_result = context.params.get("true_result", {"branch": "true"})
        false_result = context.params.get("false_result", {"branch": "false"})

        if condition_value:
            result = true_result
            branch = "true"
        else:
            result = false_result
            branch = "false"

        return HandlerResult(
            success=True,
            outputs={
                "result": result,
                "branch": branch,
                # Multi-branch outputs for consistency
                "matched_branch": branch,
                "matched_label": branch,
                "target_step": None,
            },
        )


@register_handler("aggregate")
class AggregateHandler(BaseHandler):
    """Handler that aggregates multiple inputs."""

    name = "Aggregate Handler"
    description = "Aggregates multiple inputs using various operations"

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters."""
        return []

    async def execute(self, context: HandlerContext) -> HandlerResult:
        """Execute aggregate action."""
        inputs = context.params.get("inputs", [])
        operation = context.params.get("operation", "list")

        try:
            if operation == "list":
                result = list(inputs)
            elif operation == "sum":
                result = sum(inputs) if all(isinstance(i, int | float) for i in inputs) else 0
            elif operation == "join":
                separator = context.params.get("separator", ", ")
                result = separator.join(str(i) for i in inputs)
            elif operation == "merge":
                result = {}
                for item in inputs:
                    if isinstance(item, dict):
                        result.update(item)
            else:
                result = inputs

            return HandlerResult(
                success=True,
                outputs={"result": result, "count": len(inputs)},
            )
        except Exception as e:
            return HandlerResult(
                success=False,
                error=f"Aggregate failed: {str(e)}",
            )


@register_handler("set_output")
class SetOutputHandler(BaseHandler):
    """Handler that sets arbitrary outputs."""

    name = "Set Output Handler"
    description = "Sets arbitrary output values"

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters."""
        return []

    async def execute(self, context: HandlerContext) -> HandlerResult:
        """Execute set_output action."""
        outputs = context.params.get("outputs", {})

        return HandlerResult(
            success=True,
            outputs=outputs,
        )


@register_handler("fail")
class FailHandler(BaseHandler):
    """Handler that always fails (for testing error handling)."""

    name = "Fail Handler"
    description = "Always fails with the specified error message"

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters."""
        return []

    async def execute(self, context: HandlerContext) -> HandlerResult:
        """Execute fail action."""
        message = context.params.get("message", "Intentional failure")

        return HandlerResult(
            success=False,
            error=message,
        )


def register_builtin_handlers() -> None:
    """Register all built-in handlers.

    This is called automatically when the module is imported.
    The @register_handler decorator registers each handler.
    """
    logger.info("Built-in handlers registered")
