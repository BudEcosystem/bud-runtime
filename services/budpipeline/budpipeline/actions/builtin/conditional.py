"""Conditional action - routes execution based on evaluated conditions.

Supports multi-branch conditional routing where each branch has a
Jinja2 condition expression and a target step. The first matching
branch wins (evaluated in order).
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
from budpipeline.engine.condition_evaluator import ConditionEvaluator

logger = structlog.get_logger()


class ConditionalExecutor(BaseActionExecutor):
    """Executor that evaluates conditions and determines branch routing."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute the conditional action with multi-branch support."""
        branches = context.params.get("branches", [])

        # Multi-branch mode
        if branches:
            logger.info(
                "conditional_evaluating_branches",
                step_id=context.step_id,
                execution_id=context.execution_id,
                branch_count=len(branches),
            )

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
                        "conditional_branch_evaluated",
                        step_id=context.step_id,
                        branch_id=branch_id,
                        branch_label=branch_label,
                        condition=condition,
                        result=should_execute,
                    )

                    if should_execute:
                        logger.info(
                            "conditional_branch_matched",
                            step_id=context.step_id,
                            branch_id=branch_id,
                            branch_label=branch_label,
                            target_step=target_step,
                        )
                        return ActionResult(
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
                        "conditional_branch_error",
                        step_id=context.step_id,
                        branch_id=branch_id,
                        condition=condition,
                        error=str(e),
                    )
                    continue

            # No branch matched
            logger.info(
                "conditional_no_match",
                step_id=context.step_id,
                execution_id=context.execution_id,
            )
            return ActionResult(
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
        return self._execute_legacy_mode(context)

    def _execute_legacy_mode(self, context: ActionContext) -> ActionResult:
        """Execute legacy conditional mode."""
        condition_value = context.params.get("condition", True)
        true_result = context.params.get("true_result", {"branch": "true"})
        false_result = context.params.get("false_result", {"branch": "false"})

        if condition_value:
            result = true_result
            branch = "true"
        else:
            result = false_result
            branch = "false"

        logger.info(
            "conditional_legacy_evaluated",
            step_id=context.step_id,
            condition=condition_value,
            branch=branch,
        )

        return ActionResult(
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

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate conditional parameters."""
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


META = ActionMeta(
    type="conditional",
    name="Conditional Branch",
    category="Control Flow",
    description="Routes execution to different steps based on evaluated conditions. Supports multiple branches with Jinja2 expressions.",
    icon="git-branch",
    color="#8b5cf6",
    params=[
        ParamDefinition(
            name="branches",
            label="Branches",
            type=ParamType.BRANCHES,
            required=False,
            default=[],
            description="List of branches with conditions. First matching branch wins.",
        ),
        # Legacy params for backward compatibility
        ParamDefinition(
            name="condition",
            label="Condition (Legacy)",
            type=ParamType.BOOLEAN,
            required=False,
            default=True,
            description="Boolean condition for legacy two-branch mode.",
            group="Legacy",
        ),
        ParamDefinition(
            name="true_result",
            label="True Result (Legacy)",
            type=ParamType.JSON,
            required=False,
            default={"branch": "true"},
            description="Result when condition is true (legacy mode).",
            group="Legacy",
        ),
        ParamDefinition(
            name="false_result",
            label="False Result (Legacy)",
            type=ParamType.JSON,
            required=False,
            default={"branch": "false"},
            description="Result when condition is false (legacy mode).",
            group="Legacy",
        ),
    ],
    outputs=[
        OutputDefinition(
            name="matched_branch",
            type="string",
            description="ID of the matched branch, or null if none matched",
        ),
        OutputDefinition(
            name="matched_label",
            type="string",
            description="Label of the matched branch",
        ),
        OutputDefinition(
            name="target_step",
            type="string",
            description="Step ID to execute next, or null",
        ),
        OutputDefinition(
            name="result",
            type="object",
            description="Result value (legacy compatibility)",
        ),
        OutputDefinition(
            name="branch",
            type="string",
            description="Branch identifier (legacy compatibility)",
        ),
    ],
    execution_mode=ExecutionMode.SYNC,
    idempotent=True,
    examples=[
        ActionExample(
            title="Multi-branch routing",
            params={
                "branches": [
                    {
                        "id": "high_priority",
                        "label": "High Priority",
                        "condition": "{{ params.priority > 5 }}",
                        "target_step": "urgent_processing",
                    },
                    {
                        "id": "normal",
                        "label": "Normal Priority",
                        "condition": "true",
                        "target_step": "standard_processing",
                    },
                ]
            },
            description="Routes to different steps based on priority level",
        ),
    ],
)


@register_action(META)
class ConditionalAction:
    """Conditional action class for entry point registration."""

    meta = META
    executor_class = ConditionalExecutor
