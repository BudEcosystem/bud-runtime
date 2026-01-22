"""Tests for Condition Evaluator - TDD approach.

Tests conditional expression evaluation for workflow step execution.
Supports expressions like:
- {{ steps.step1.outputs.should_continue == true }}
- {{ params.env == 'production' }}
- {{ steps.step1.outputs.count > 10 }}
"""

import pytest

from budpipeline.commons.exceptions import ConditionEvaluationError
from budpipeline.engine.condition_evaluator import ConditionEvaluator


class TestBasicConditionEvaluation:
    """Test basic condition evaluation."""

    def test_evaluate_true_literal(self) -> None:
        """Should evaluate 'true' as True."""
        result = ConditionEvaluator.evaluate(
            condition="true",
            params={},
            step_outputs={},
        )
        assert result is True

    def test_evaluate_false_literal(self) -> None:
        """Should evaluate 'false' as False."""
        result = ConditionEvaluator.evaluate(
            condition="false",
            params={},
            step_outputs={},
        )
        assert result is False

    def test_evaluate_none_condition(self) -> None:
        """Should return True for None condition (always execute)."""
        result = ConditionEvaluator.evaluate(
            condition=None,
            params={},
            step_outputs={},
        )
        assert result is True

    def test_evaluate_empty_condition(self) -> None:
        """Should return True for empty condition (always execute)."""
        result = ConditionEvaluator.evaluate(
            condition="",
            params={},
            step_outputs={},
        )
        assert result is True

    def test_evaluate_whitespace_condition(self) -> None:
        """Should return True for whitespace-only condition."""
        result = ConditionEvaluator.evaluate(
            condition="   ",
            params={},
            step_outputs={},
        )
        assert result is True


class TestParameterConditions:
    """Test conditions using workflow parameters."""

    def test_param_equality_true(self) -> None:
        """Should evaluate param equality to True."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.env == 'production' }}",
            params={"env": "production"},
            step_outputs={},
        )
        assert result is True

    def test_param_equality_false(self) -> None:
        """Should evaluate param inequality to False."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.env == 'production' }}",
            params={"env": "staging"},
            step_outputs={},
        )
        assert result is False

    def test_param_not_equal(self) -> None:
        """Should evaluate not-equal condition."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.env != 'production' }}",
            params={"env": "staging"},
            step_outputs={},
        )
        assert result is True

    def test_param_boolean_value(self) -> None:
        """Should evaluate boolean parameter value."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.enabled }}",
            params={"enabled": True},
            step_outputs={},
        )
        assert result is True

    def test_param_boolean_false_value(self) -> None:
        """Should evaluate False boolean parameter."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.enabled }}",
            params={"enabled": False},
            step_outputs={},
        )
        assert result is False

    def test_param_truthy_string(self) -> None:
        """Should evaluate non-empty string as truthy."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.name }}",
            params={"name": "test"},
            step_outputs={},
        )
        assert result is True

    def test_param_falsy_empty_string(self) -> None:
        """Should evaluate empty string as falsy."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.name }}",
            params={"name": ""},
            step_outputs={},
        )
        assert result is False


class TestStepOutputConditions:
    """Test conditions using step outputs."""

    def test_step_output_equality(self) -> None:
        """Should evaluate step output equality."""
        result = ConditionEvaluator.evaluate(
            condition="{{ steps.step1.outputs.status == 'success' }}",
            params={},
            step_outputs={"step1": {"status": "success"}},
        )
        assert result is True

    def test_step_output_boolean(self) -> None:
        """Should evaluate step output boolean value."""
        result = ConditionEvaluator.evaluate(
            condition="{{ steps.step1.outputs.should_continue }}",
            params={},
            step_outputs={"step1": {"should_continue": True}},
        )
        assert result is True

    def test_step_output_boolean_comparison(self) -> None:
        """Should evaluate step output boolean comparison."""
        result = ConditionEvaluator.evaluate(
            condition="{{ steps.step1.outputs.should_continue == true }}",
            params={},
            step_outputs={"step1": {"should_continue": True}},
        )
        assert result is True

    def test_step_output_nested_value(self) -> None:
        """Should evaluate nested step output value."""
        result = ConditionEvaluator.evaluate(
            condition="{{ steps.step1.outputs.config.enabled }}",
            params={},
            step_outputs={"step1": {"config": {"enabled": True}}},
        )
        assert result is True


class TestNumericConditions:
    """Test numeric comparison conditions."""

    def test_greater_than_true(self) -> None:
        """Should evaluate greater than to True."""
        result = ConditionEvaluator.evaluate(
            condition="{{ steps.step1.outputs.count > 10 }}",
            params={},
            step_outputs={"step1": {"count": 15}},
        )
        assert result is True

    def test_greater_than_false(self) -> None:
        """Should evaluate greater than to False."""
        result = ConditionEvaluator.evaluate(
            condition="{{ steps.step1.outputs.count > 10 }}",
            params={},
            step_outputs={"step1": {"count": 5}},
        )
        assert result is False

    def test_less_than(self) -> None:
        """Should evaluate less than."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.replicas < 5 }}",
            params={"replicas": 3},
            step_outputs={},
        )
        assert result is True

    def test_greater_or_equal(self) -> None:
        """Should evaluate greater or equal."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.count >= 10 }}",
            params={"count": 10},
            step_outputs={},
        )
        assert result is True

    def test_less_or_equal(self) -> None:
        """Should evaluate less or equal."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.count <= 10 }}",
            params={"count": 5},
            step_outputs={},
        )
        assert result is True


class TestLogicalOperators:
    """Test logical operators in conditions."""

    def test_and_operator_true(self) -> None:
        """Should evaluate AND to True when both are true."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.enabled and params.ready }}",
            params={"enabled": True, "ready": True},
            step_outputs={},
        )
        assert result is True

    def test_and_operator_false(self) -> None:
        """Should evaluate AND to False when one is false."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.enabled and params.ready }}",
            params={"enabled": True, "ready": False},
            step_outputs={},
        )
        assert result is False

    def test_or_operator_true(self) -> None:
        """Should evaluate OR to True when one is true."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.enabled or params.ready }}",
            params={"enabled": True, "ready": False},
            step_outputs={},
        )
        assert result is True

    def test_or_operator_false(self) -> None:
        """Should evaluate OR to False when both are false."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.enabled or params.ready }}",
            params={"enabled": False, "ready": False},
            step_outputs={},
        )
        assert result is False

    def test_not_operator(self) -> None:
        """Should evaluate NOT operator."""
        result = ConditionEvaluator.evaluate(
            condition="{{ not params.disabled }}",
            params={"disabled": False},
            step_outputs={},
        )
        assert result is True

    def test_complex_logical_expression(self) -> None:
        """Should evaluate complex logical expression."""
        result = ConditionEvaluator.evaluate(
            condition="{{ (params.env == 'prod' and params.enabled) or params.force }}",
            params={"env": "prod", "enabled": True, "force": False},
            step_outputs={},
        )
        assert result is True


class TestContainmentOperators:
    """Test 'in' and 'not in' operators."""

    def test_in_list(self) -> None:
        """Should evaluate 'in' for list membership."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.env in ['prod', 'production'] }}",
            params={"env": "prod"},
            step_outputs={},
        )
        assert result is True

    def test_not_in_list(self) -> None:
        """Should evaluate 'not in' for list non-membership."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.env not in ['prod', 'production'] }}",
            params={"env": "staging"},
            step_outputs={},
        )
        assert result is True

    def test_in_string(self) -> None:
        """Should evaluate 'in' for substring check."""
        result = ConditionEvaluator.evaluate(
            condition="{{ 'error' in params.message }}",
            params={"message": "An error occurred"},
            step_outputs={},
        )
        assert result is True


class TestSpecialCases:
    """Test special cases and edge conditions."""

    def test_none_value_comparison(self) -> None:
        """Should handle None value comparison."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.value is none }}",
            params={"value": None},
            step_outputs={},
        )
        assert result is True

    def test_defined_check(self) -> None:
        """Should check if variable is defined."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.value is defined }}",
            params={"value": "test"},
            step_outputs={},
        )
        assert result is True

    def test_undefined_check(self) -> None:
        """Should check if variable is undefined."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.missing is not defined }}",
            params={},
            step_outputs={},
        )
        assert result is True

    def test_empty_list_is_falsy(self) -> None:
        """Should evaluate empty list as falsy."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.items }}",
            params={"items": []},
            step_outputs={},
        )
        assert result is False

    def test_non_empty_list_is_truthy(self) -> None:
        """Should evaluate non-empty list as truthy."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.items }}",
            params={"items": [1, 2, 3]},
            step_outputs={},
        )
        assert result is True

    def test_zero_is_falsy(self) -> None:
        """Should evaluate zero as falsy."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.count }}",
            params={"count": 0},
            step_outputs={},
        )
        assert result is False

    def test_non_zero_is_truthy(self) -> None:
        """Should evaluate non-zero as truthy."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.count }}",
            params={"count": 5},
            step_outputs={},
        )
        assert result is True


class TestWithDefaultValues:
    """Test conditions with default filter."""

    def test_default_for_missing_param(self) -> None:
        """Should use default when param is missing."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.enabled | default(true) }}",
            params={},
            step_outputs={},
        )
        assert result is True

    def test_default_for_missing_step_output(self) -> None:
        """Should use default when step output is missing."""
        result = ConditionEvaluator.evaluate(
            condition="{{ steps.missing.outputs.value | default(false) }}",
            params={},
            step_outputs={},
        )
        assert result is False

    def test_default_in_comparison(self) -> None:
        """Should use default in comparison expression."""
        result = ConditionEvaluator.evaluate(
            condition="{{ (params.count | default(0)) > 5 }}",
            params={},
            step_outputs={},
        )
        assert result is False


class TestErrorHandling:
    """Test error handling for invalid conditions."""

    def test_invalid_syntax_raises(self) -> None:
        """Should raise error for invalid syntax."""
        with pytest.raises(ConditionEvaluationError):
            ConditionEvaluator.evaluate(
                condition="{{ invalid {{ syntax }}",
                params={},
                step_outputs={},
            )

    def test_undefined_variable_in_strict_mode(self) -> None:
        """Should raise error for undefined variable in strict mode."""
        with pytest.raises(ConditionEvaluationError):
            ConditionEvaluator.evaluate(
                condition="{{ params.missing }}",
                params={},
                step_outputs={},
                strict=True,
            )

    def test_undefined_in_non_strict_returns_false(self) -> None:
        """Should return False for undefined in non-strict mode."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.missing }}",
            params={},
            step_outputs={},
            strict=False,
        )
        assert result is False


class TestMixedConditions:
    """Test conditions mixing params and step outputs."""

    def test_param_and_step_output(self, workflow_params: dict, step_outputs: dict) -> None:
        """Should evaluate condition with both params and step outputs."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.replicas > 1 and steps.onboard.outputs.model_id }}",
            params=workflow_params,
            step_outputs=step_outputs,
        )
        assert result is True

    def test_complex_mixed_condition(self, workflow_params: dict, step_outputs: dict) -> None:
        """Should evaluate complex mixed condition."""
        result = ConditionEvaluator.evaluate(
            condition=(
                "{{ steps.onboard.outputs.model_id and params.cluster_id == 'cluster-123' }}"
            ),
            params=workflow_params,
            step_outputs=step_outputs,
        )
        assert result is True


class TestFilterInConditions:
    """Test filters used in conditions."""

    def test_length_filter(self) -> None:
        """Should use length filter in condition."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.items | length > 2 }}",
            params={"items": [1, 2, 3, 4]},
            step_outputs={},
        )
        assert result is True

    def test_lower_filter(self) -> None:
        """Should use lower filter in condition."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.env | lower == 'production' }}",
            params={"env": "PRODUCTION"},
            step_outputs={},
        )
        assert result is True

    def test_upper_filter(self) -> None:
        """Should use upper filter in condition."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.env | upper == 'STAGING' }}",
            params={"env": "staging"},
            step_outputs={},
        )
        assert result is True

    def test_first_filter(self) -> None:
        """Should use first filter in condition."""
        result = ConditionEvaluator.evaluate(
            condition="{{ params.items | first == 'a' }}",
            params={"items": ["a", "b", "c"]},
            step_outputs={},
        )
        assert result is True


class TestValidateCondition:
    """Test condition validation."""

    def test_validate_valid_condition(self) -> None:
        """Should validate valid condition without errors."""
        errors = ConditionEvaluator.validate(
            condition="{{ params.enabled }}",
            available_params={"enabled"},
            available_steps=set(),
        )
        assert errors == []

    def test_validate_missing_param(self) -> None:
        """Should report missing parameter."""
        errors = ConditionEvaluator.validate(
            condition="{{ params.missing }}",
            available_params=set(),
            available_steps=set(),
        )
        assert len(errors) == 1
        assert "missing" in errors[0].lower()

    def test_validate_missing_step(self) -> None:
        """Should report missing step."""
        errors = ConditionEvaluator.validate(
            condition="{{ steps.unknown.outputs.value }}",
            available_params=set(),
            available_steps={"step1", "step2"},
        )
        assert len(errors) == 1
        assert "unknown" in errors[0].lower()

    def test_validate_complex_condition(self) -> None:
        """Should validate complex condition with multiple references."""
        errors = ConditionEvaluator.validate(
            condition="{{ params.enabled and steps.step1.outputs.ready }}",
            available_params={"enabled"},
            available_steps={"step1"},
        )
        assert errors == []
