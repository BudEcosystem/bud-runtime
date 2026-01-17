"""Tests for built-in control flow actions."""

from __future__ import annotations

import pytest

from budpipeline.actions.base import ActionContext
from budpipeline.actions.builtin import (
    AggregateExecutor,
    ConditionalExecutor,
    DelayExecutor,
    FailExecutor,
    LogExecutor,
    SetOutputExecutor,
    TransformExecutor,
)


def make_context(**params) -> ActionContext:
    """Create a test ActionContext."""
    return ActionContext(
        step_id="test_step",
        execution_id="test_execution",
        params=params,
        workflow_params={},
        step_outputs={},
    )


class TestLogExecutor:
    """Tests for LogExecutor."""

    @pytest.mark.asyncio
    async def test_log_default_message(self) -> None:
        """Test logging with default message."""
        executor = LogExecutor()
        context = make_context()
        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["logged"] is True
        assert result.outputs["message"] == "No message provided"
        assert result.outputs["level"] == "info"

    @pytest.mark.asyncio
    async def test_log_custom_message(self) -> None:
        """Test logging with custom message."""
        executor = LogExecutor()
        context = make_context(message="Hello, World!", level="warning")
        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["message"] == "Hello, World!"
        assert result.outputs["level"] == "warning"

    @pytest.mark.asyncio
    async def test_log_all_levels(self) -> None:
        """Test all log levels."""
        executor = LogExecutor()

        for level in ["debug", "info", "warning", "error"]:
            context = make_context(message=f"Test {level}", level=level)
            result = await executor.execute(context)
            assert result.success is True
            assert result.outputs["level"] == level


class TestDelayExecutor:
    """Tests for DelayExecutor."""

    @pytest.mark.asyncio
    async def test_delay_default(self) -> None:
        """Test delay with default duration."""
        executor = DelayExecutor()
        context = make_context()
        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["delayed"] is True
        assert result.outputs["duration_seconds"] == 1.0

    @pytest.mark.asyncio
    async def test_delay_custom_duration(self) -> None:
        """Test delay with custom duration."""
        executor = DelayExecutor()
        context = make_context(duration_seconds=0.1, reason="Testing")
        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["duration_seconds"] == 0.1
        assert result.outputs["reason"] == "Testing"

    @pytest.mark.asyncio
    async def test_delay_negative_duration(self) -> None:
        """Test delay fails with negative duration."""
        executor = DelayExecutor()
        context = make_context(duration_seconds=-1)
        result = await executor.execute(context)

        assert result.success is False
        assert "non-negative" in result.error

    def test_validate_params_invalid_duration(self) -> None:
        """Test validation catches invalid duration."""
        executor = DelayExecutor()
        errors = executor.validate_params({"duration_seconds": "not_a_number"})
        assert any("number" in e for e in errors)

    def test_validate_params_too_long(self) -> None:
        """Test validation catches duration over limit."""
        executor = DelayExecutor()
        errors = executor.validate_params({"duration_seconds": 5000})
        assert any("3600" in e for e in errors)


class TestConditionalExecutor:
    """Tests for ConditionalExecutor."""

    @pytest.mark.asyncio
    async def test_conditional_legacy_true(self) -> None:
        """Test legacy conditional mode with true condition."""
        executor = ConditionalExecutor()
        context = make_context(condition=True)
        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["branch"] == "true"

    @pytest.mark.asyncio
    async def test_conditional_legacy_false(self) -> None:
        """Test legacy conditional mode with false condition."""
        executor = ConditionalExecutor()
        context = make_context(condition=False)
        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["branch"] == "false"

    @pytest.mark.asyncio
    async def test_conditional_branches_first_match(self) -> None:
        """Test multi-branch mode with first branch matching."""
        executor = ConditionalExecutor()
        context = make_context(
            branches=[
                {
                    "id": "branch_a",
                    "label": "Branch A",
                    "condition": "true",
                    "target_step": "step_a",
                },
                {
                    "id": "branch_b",
                    "label": "Branch B",
                    "condition": "true",
                    "target_step": "step_b",
                },
            ]
        )
        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["matched_branch"] == "branch_a"
        assert result.outputs["target_step"] == "step_a"

    @pytest.mark.asyncio
    async def test_conditional_branches_no_match(self) -> None:
        """Test multi-branch mode with no branches matching."""
        executor = ConditionalExecutor()
        context = make_context(
            branches=[
                {
                    "id": "branch_a",
                    "label": "Branch A",
                    "condition": "false",
                    "target_step": "step_a",
                },
            ]
        )
        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["matched_branch"] is None
        assert result.outputs["target_step"] is None

    def test_validate_params_invalid_branch(self) -> None:
        """Test validation catches invalid branch structure."""
        executor = ConditionalExecutor()
        errors = executor.validate_params({"branches": [{"label": "No ID"}]})
        assert any("id" in e.lower() for e in errors)


class TestTransformExecutor:
    """Tests for TransformExecutor."""

    @pytest.mark.asyncio
    async def test_transform_passthrough(self) -> None:
        """Test passthrough operation."""
        executor = TransformExecutor()
        context = make_context(input={"key": "value"}, operation="passthrough")
        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["result"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_transform_uppercase(self) -> None:
        """Test uppercase operation."""
        executor = TransformExecutor()
        context = make_context(input="hello", operation="uppercase")
        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["result"] == "HELLO"

    @pytest.mark.asyncio
    async def test_transform_lowercase(self) -> None:
        """Test lowercase operation."""
        executor = TransformExecutor()
        context = make_context(input="HELLO", operation="lowercase")
        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["result"] == "hello"

    @pytest.mark.asyncio
    async def test_transform_keys(self) -> None:
        """Test keys operation."""
        executor = TransformExecutor()
        context = make_context(input={"a": 1, "b": 2}, operation="keys")
        result = await executor.execute(context)

        assert result.success is True
        assert sorted(result.outputs["result"]) == ["a", "b"]

    @pytest.mark.asyncio
    async def test_transform_values(self) -> None:
        """Test values operation."""
        executor = TransformExecutor()
        context = make_context(input={"a": 1, "b": 2}, operation="values")
        result = await executor.execute(context)

        assert result.success is True
        assert sorted(result.outputs["result"]) == [1, 2]

    @pytest.mark.asyncio
    async def test_transform_count(self) -> None:
        """Test count operation."""
        executor = TransformExecutor()
        context = make_context(input=[1, 2, 3, 4, 5], operation="count")
        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["result"] == 5


class TestAggregateExecutor:
    """Tests for AggregateExecutor."""

    @pytest.mark.asyncio
    async def test_aggregate_list(self) -> None:
        """Test list aggregation."""
        executor = AggregateExecutor()
        context = make_context(inputs=[1, 2, 3], operation="list")
        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["result"] == [1, 2, 3]
        assert result.outputs["count"] == 3

    @pytest.mark.asyncio
    async def test_aggregate_sum(self) -> None:
        """Test sum aggregation."""
        executor = AggregateExecutor()
        context = make_context(inputs=[1, 2, 3, 4, 5], operation="sum")
        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["result"] == 15

    @pytest.mark.asyncio
    async def test_aggregate_join(self) -> None:
        """Test join aggregation."""
        executor = AggregateExecutor()
        context = make_context(inputs=["hello", "world"], operation="join", separator=" ")
        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["result"] == "hello world"

    @pytest.mark.asyncio
    async def test_aggregate_merge(self) -> None:
        """Test merge aggregation."""
        executor = AggregateExecutor()
        context = make_context(inputs=[{"a": 1}, {"b": 2}], operation="merge")
        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["result"] == {"a": 1, "b": 2}

    @pytest.mark.asyncio
    async def test_aggregate_average(self) -> None:
        """Test average aggregation."""
        executor = AggregateExecutor()
        context = make_context(inputs=[10, 20, 30], operation="average")
        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["result"] == 20.0

    def test_validate_params_invalid_inputs(self) -> None:
        """Test validation catches non-list inputs."""
        executor = AggregateExecutor()
        errors = executor.validate_params({"inputs": "not a list"})
        assert any("list" in e for e in errors)


class TestSetOutputExecutor:
    """Tests for SetOutputExecutor."""

    @pytest.mark.asyncio
    async def test_set_output_dict(self) -> None:
        """Test setting outputs from dict."""
        executor = SetOutputExecutor()
        context = make_context(outputs={"key1": "value1", "key2": 42})
        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs["key1"] == "value1"
        assert result.outputs["key2"] == 42

    @pytest.mark.asyncio
    async def test_set_output_empty(self) -> None:
        """Test setting empty outputs."""
        executor = SetOutputExecutor()
        context = make_context(outputs={})
        result = await executor.execute(context)

        assert result.success is True
        assert result.outputs == {}

    @pytest.mark.asyncio
    async def test_set_output_invalid_type(self) -> None:
        """Test set_output fails with non-dict outputs."""
        executor = SetOutputExecutor()
        context = make_context(outputs="not a dict")
        result = await executor.execute(context)

        assert result.success is False
        assert "dictionary" in result.error


class TestFailExecutor:
    """Tests for FailExecutor."""

    @pytest.mark.asyncio
    async def test_fail_default_message(self) -> None:
        """Test fail with default message."""
        executor = FailExecutor()
        context = make_context()
        result = await executor.execute(context)

        assert result.success is False
        assert result.error == "Intentional failure"
        assert result.outputs["error_code"] == "INTENTIONAL_FAILURE"

    @pytest.mark.asyncio
    async def test_fail_custom_message(self) -> None:
        """Test fail with custom message."""
        executor = FailExecutor()
        context = make_context(message="Custom error", error_code="CUSTOM_ERROR")
        result = await executor.execute(context)

        assert result.success is False
        assert result.error == "Custom error"
        assert result.outputs["error_code"] == "CUSTOM_ERROR"
        assert result.outputs["message"] == "Custom error"
