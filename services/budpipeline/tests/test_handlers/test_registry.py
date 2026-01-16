"""Tests for Handler Registry - TDD approach.

Tests handler registration, lookup, and execution dispatch.
"""

from typing import Any

import pytest

from budpipeline.commons.exceptions import ActionNotFoundError, ActionValidationError
from budpipeline.handlers.base import BaseHandler, HandlerContext, HandlerResult
from budpipeline.handlers.registry import HandlerRegistry


class MockHandler(BaseHandler):
    """Mock handler for testing."""

    action_type = "test.mock"
    name = "Mock Handler"
    description = "A mock handler for testing"

    async def execute(self, context: HandlerContext) -> HandlerResult:
        return HandlerResult(
            success=True,
            outputs={"result": "mock_output"},
        )

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        errors = []
        if "required_field" not in params:
            errors.append("Missing required field: required_field")
        return errors


class FailingHandler(BaseHandler):
    """Handler that always fails for testing."""

    action_type = "test.failing"
    name = "Failing Handler"
    description = "A handler that always fails"

    async def execute(self, context: HandlerContext) -> HandlerResult:
        return HandlerResult(
            success=False,
            error="Intentional failure",
        )

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        return []


class TestHandlerRegistry:
    """Test handler registry operations."""

    def test_register_handler(self) -> None:
        """Should register a handler class."""
        registry = HandlerRegistry()
        registry.register(MockHandler)

        assert "test.mock" in registry.list_handlers()

    def test_register_handler_duplicate(self) -> None:
        """Should allow re-registering same handler."""
        registry = HandlerRegistry()
        registry.register(MockHandler)
        registry.register(MockHandler)

        assert "test.mock" in registry.list_handlers()

    def test_get_handler(self) -> None:
        """Should get registered handler by action type."""
        registry = HandlerRegistry()
        registry.register(MockHandler)

        handler = registry.get("test.mock")
        assert handler is not None
        assert handler.action_type == "test.mock"

    def test_get_handler_not_found(self) -> None:
        """Should raise error for unregistered action type."""
        registry = HandlerRegistry()

        with pytest.raises(ActionNotFoundError) as exc_info:
            registry.get("nonexistent.action")

        assert "nonexistent.action" in str(exc_info.value)

    def test_list_handlers(self) -> None:
        """Should list all registered handlers."""
        registry = HandlerRegistry()
        registry.register(MockHandler)
        registry.register(FailingHandler)

        handlers = registry.list_handlers()
        assert "test.mock" in handlers
        assert "test.failing" in handlers
        assert len(handlers) == 2

    def test_has_handler(self) -> None:
        """Should check if handler exists."""
        registry = HandlerRegistry()
        registry.register(MockHandler)

        assert registry.has("test.mock") is True
        assert registry.has("nonexistent") is False

    def test_unregister_handler(self) -> None:
        """Should unregister a handler."""
        registry = HandlerRegistry()
        registry.register(MockHandler)
        registry.unregister("test.mock")

        assert registry.has("test.mock") is False

    def test_unregister_nonexistent(self) -> None:
        """Should handle unregistering nonexistent handler."""
        registry = HandlerRegistry()
        # Should not raise
        registry.unregister("nonexistent")

    def test_clear_registry(self) -> None:
        """Should clear all handlers."""
        registry = HandlerRegistry()
        registry.register(MockHandler)
        registry.register(FailingHandler)
        registry.clear()

        assert len(registry.list_handlers()) == 0

    def test_get_handler_info(self) -> None:
        """Should get handler metadata."""
        registry = HandlerRegistry()
        registry.register(MockHandler)

        info = registry.get_info("test.mock")
        assert info["name"] == "Mock Handler"
        assert info["description"] == "A mock handler for testing"
        assert info["action_type"] == "test.mock"


class TestHandlerValidation:
    """Test handler parameter validation."""

    def test_validate_params_success(self) -> None:
        """Should validate params successfully."""
        registry = HandlerRegistry()
        registry.register(MockHandler)

        errors = registry.validate_params(
            "test.mock",
            {"required_field": "value"},
        )
        assert errors == []

    def test_validate_params_failure(self) -> None:
        """Should return validation errors."""
        registry = HandlerRegistry()
        registry.register(MockHandler)

        errors = registry.validate_params("test.mock", {})
        assert len(errors) == 1
        assert "required_field" in errors[0]

    def test_validate_params_not_found(self) -> None:
        """Should raise error for nonexistent handler."""
        registry = HandlerRegistry()

        with pytest.raises(ActionNotFoundError):
            registry.validate_params("nonexistent", {})


class TestHandlerExecution:
    """Test handler execution via registry."""

    @pytest.mark.asyncio
    async def test_execute_handler(self) -> None:
        """Should execute handler and return result."""
        registry = HandlerRegistry()
        registry.register(MockHandler)

        context = HandlerContext(
            step_id="step1",
            execution_id="exec-123",
            params={"required_field": "value"},
            workflow_params={},
            step_outputs={},
        )

        result = await registry.execute("test.mock", context)

        assert result.success is True
        assert result.outputs == {"result": "mock_output"}

    @pytest.mark.asyncio
    async def test_execute_failing_handler(self) -> None:
        """Should return failure result from handler."""
        registry = HandlerRegistry()
        registry.register(FailingHandler)

        context = HandlerContext(
            step_id="step1",
            execution_id="exec-123",
            params={},
            workflow_params={},
            step_outputs={},
        )

        result = await registry.execute("test.failing", context)

        assert result.success is False
        assert result.error == "Intentional failure"

    @pytest.mark.asyncio
    async def test_execute_not_found(self) -> None:
        """Should raise error for nonexistent handler."""
        registry = HandlerRegistry()

        context = HandlerContext(
            step_id="step1",
            execution_id="exec-123",
            params={},
            workflow_params={},
            step_outputs={},
        )

        with pytest.raises(ActionNotFoundError):
            await registry.execute("nonexistent", context)

    @pytest.mark.asyncio
    async def test_execute_with_validation(self) -> None:
        """Should validate params before execution."""
        registry = HandlerRegistry()
        registry.register(MockHandler)

        context = HandlerContext(
            step_id="step1",
            execution_id="exec-123",
            params={},  # Missing required_field
            workflow_params={},
            step_outputs={},
        )

        with pytest.raises(ActionValidationError) as exc_info:
            await registry.execute("test.mock", context, validate=True)

        assert "required_field" in str(exc_info.value)


class TestGlobalRegistry:
    """Test global registry instance."""

    def test_global_registry_exists(self) -> None:
        """Should have a global registry instance."""
        from budpipeline.handlers.registry import global_registry

        assert global_registry is not None
        assert isinstance(global_registry, HandlerRegistry)

    def test_register_decorator(self) -> None:
        """Should register handler using decorator."""
        from budpipeline.handlers.registry import register_handler

        @register_handler
        class DecoratedHandler(BaseHandler):
            action_type = "test.decorated"
            name = "Decorated Handler"
            description = "Handler registered via decorator"

            async def execute(self, context: HandlerContext) -> HandlerResult:
                return HandlerResult(success=True)

            def validate_params(self, params: dict[str, Any]) -> list[str]:
                return []

        from budpipeline.handlers.registry import global_registry

        assert global_registry.has("test.decorated")

        # Cleanup
        global_registry.unregister("test.decorated")


class TestHandlerContext:
    """Test HandlerContext dataclass."""

    def test_create_context(self) -> None:
        """Should create context with all fields."""
        context = HandlerContext(
            step_id="step1",
            execution_id="exec-123",
            params={"key": "value"},
            workflow_params={"wf_key": "wf_value"},
            step_outputs={"prev_step": {"output": "data"}},
        )

        assert context.step_id == "step1"
        assert context.execution_id == "exec-123"
        assert context.params == {"key": "value"}
        assert context.workflow_params == {"wf_key": "wf_value"}
        assert context.step_outputs == {"prev_step": {"output": "data"}}

    def test_context_optional_fields(self) -> None:
        """Should create context with default optional fields."""
        context = HandlerContext(
            step_id="step1",
            execution_id="exec-123",
            params={},
            workflow_params={},
            step_outputs={},
        )

        assert context.timeout_seconds is None
        assert context.retry_count == 0


class TestHandlerResult:
    """Test HandlerResult dataclass."""

    def test_create_success_result(self) -> None:
        """Should create success result."""
        result = HandlerResult(
            success=True,
            outputs={"result": "value"},
        )

        assert result.success is True
        assert result.outputs == {"result": "value"}
        assert result.error is None

    def test_create_failure_result(self) -> None:
        """Should create failure result."""
        result = HandlerResult(
            success=False,
            error="Something went wrong",
        )

        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.outputs == {}

    def test_result_with_metadata(self) -> None:
        """Should include metadata in result."""
        result = HandlerResult(
            success=True,
            outputs={"result": "value"},
            metadata={"duration_ms": 150},
        )

        assert result.metadata == {"duration_ms": 150}
