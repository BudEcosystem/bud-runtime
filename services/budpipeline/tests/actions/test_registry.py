"""Tests for action registry."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from budpipeline.actions.base.context import ActionContext
from budpipeline.actions.base.executor import BaseActionExecutor
from budpipeline.actions.base.meta import (
    ActionMeta,
)
from budpipeline.actions.base.registry import (
    ActionRegistry,
    action_registry,
    register_action,
)
from budpipeline.actions.base.result import ActionResult


class MockExecutor(BaseActionExecutor):
    """Mock executor for testing."""

    async def execute(self, context: ActionContext) -> ActionResult:
        return ActionResult(success=True, outputs={"result": "executed"})


class TestActionRegistry:
    """Tests for ActionRegistry class."""

    @pytest.fixture(autouse=True)
    def reset_registry(self) -> None:
        """Reset registry before each test."""
        # Reset the singleton for testing
        ActionRegistry._instance = None
        yield
        ActionRegistry._instance = None

    def test_singleton_pattern(self) -> None:
        """Registry should be a singleton."""
        reg1 = ActionRegistry()
        reg2 = ActionRegistry()
        assert reg1 is reg2

    def test_register_action_class(self) -> None:
        """Test manual action registration."""
        registry = ActionRegistry()

        action_meta = ActionMeta(
            type="test_action",
            name="Test Action",
            category="Testing",
            description="A test action",
        )

        # Use type() to create class dynamically to avoid scoping issues
        TestAction = type(
            "TestAction",
            (),
            {"meta": action_meta, "executor_class": MockExecutor},
        )

        registry._register_action_class("test_action", TestAction)

        assert registry.has("test_action")
        assert registry.get_meta("test_action") is action_meta

    def test_register_action_missing_meta(self) -> None:
        """Test registration fails without meta attribute."""
        registry = ActionRegistry()

        class BadAction:
            executor_class = MockExecutor

        with pytest.raises(ValueError, match="missing 'meta'"):
            registry._register_action_class("bad_action", BadAction)

    def test_register_action_missing_executor_class(self) -> None:
        """Test registration fails without executor_class attribute."""
        registry = ActionRegistry()

        action_meta = ActionMeta(
            type="bad_action",
            name="Bad Action",
            category="Testing",
            description="Missing executor",
        )

        BadAction = type("BadAction", (), {"meta": action_meta})

        with pytest.raises(ValueError, match="missing 'executor_class'"):
            registry._register_action_class("bad_action", BadAction)

    def test_register_action_invalid_executor_class(self) -> None:
        """Test registration fails with invalid executor class."""
        registry = ActionRegistry()

        action_meta = ActionMeta(
            type="bad_action",
            name="Bad Action",
            category="Testing",
            description="Invalid executor",
        )

        class NotAnExecutor:
            pass

        BadAction = type(
            "BadAction",
            (),
            {"meta": action_meta, "executor_class": NotAnExecutor},
        )

        with pytest.raises(ValueError, match="must inherit from BaseActionExecutor"):
            registry._register_action_class("bad_action", BadAction)

    def test_register_action_invalid_metadata(self) -> None:
        """Test registration fails with invalid metadata."""
        registry = ActionRegistry()

        action_meta = ActionMeta(
            type="",  # Invalid: empty type
            name="Bad Action",
            category="Testing",
            description="Invalid metadata",
        )

        BadAction = type(
            "BadAction",
            (),
            {"meta": action_meta, "executor_class": MockExecutor},
        )

        with pytest.raises(ValueError, match="Invalid action metadata"):
            registry._register_action_class("bad_action", BadAction)

    def test_register_decorator(self) -> None:
        """Test the register decorator method."""
        registry = ActionRegistry()

        action_meta = ActionMeta(
            type="decorated_action",
            name="Decorated Action",
            category="Testing",
            description="Registered via decorator",
        )

        # Create class with the meta before decorating
        DecoratedAction = type(
            "DecoratedAction",
            (),
            {"meta": action_meta, "executor_class": MockExecutor},
        )
        DecoratedAction = registry.register(DecoratedAction)

        assert registry.has("decorated_action")
        assert registry.get_meta("decorated_action") is action_meta

    def test_get_meta_returns_none_for_unknown(self) -> None:
        """get_meta should return None for unknown action types."""
        registry = ActionRegistry()
        assert registry.get_meta("nonexistent") is None

    def test_get_executor_raises_for_unknown(self) -> None:
        """get_executor should raise KeyError for unknown action types."""
        registry = ActionRegistry()
        with pytest.raises(KeyError, match="Unknown action type"):
            registry.get_executor("nonexistent")

    def test_get_executor_lazy_instantiation(self) -> None:
        """Executor should be lazily instantiated."""
        registry = ActionRegistry()

        action_meta = ActionMeta(
            type="lazy_action",
            name="Lazy Action",
            category="Testing",
            description="Tests lazy instantiation",
        )

        LazyAction = type(
            "LazyAction",
            (),
            {"meta": action_meta, "executor_class": MockExecutor},
        )

        registry._register_action_class("lazy_action", LazyAction)

        # Executor should not be created yet
        action_data = registry._actions["lazy_action"]
        assert action_data["executor_instance"] is None

        # Get executor - should create instance
        executor = registry.get_executor("lazy_action")
        assert isinstance(executor, MockExecutor)

        # Should return same instance
        executor2 = registry.get_executor("lazy_action")
        assert executor is executor2

    def test_has_method(self) -> None:
        """Test the has() method."""
        registry = ActionRegistry()

        action_meta = ActionMeta(
            type="exists",
            name="Exists",
            category="Testing",
            description="Test",
        )

        ExistsAction = type(
            "ExistsAction",
            (),
            {"meta": action_meta, "executor_class": MockExecutor},
        )

        registry._register_action_class("exists", ExistsAction)

        assert registry.has("exists") is True
        assert registry.has("does_not_exist") is False

    def test_list_actions(self) -> None:
        """Test listing all registered actions."""
        registry = ActionRegistry()

        # Register multiple actions
        for i in range(3):
            meta = ActionMeta(
                type=f"action_{i}",
                name=f"Action {i}",
                category="Testing",
                description="Test",
            )

            action_class = type(
                f"Action{i}",
                (),
                {"meta": meta, "executor_class": MockExecutor},
            )
            registry._register_action_class(f"action_{i}", action_class)

        actions = registry.list_actions()
        assert len(actions) == 3
        assert "action_0" in actions
        assert "action_1" in actions
        assert "action_2" in actions

    def test_get_all_meta(self) -> None:
        """Test getting metadata for all actions."""
        registry = ActionRegistry()

        # Register multiple actions
        for i in range(2):
            meta = ActionMeta(
                type=f"meta_action_{i}",
                name=f"Meta Action {i}",
                category="Testing",
                description="Test",
            )

            action_class = type(
                f"MetaAction{i}",
                (),
                {"meta": meta, "executor_class": MockExecutor},
            )
            registry._register_action_class(f"meta_action_{i}", action_class)

        all_meta = registry.get_all_meta()
        assert len(all_meta) == 2
        assert all(isinstance(m, ActionMeta) for m in all_meta)

    def test_get_by_category(self) -> None:
        """Test grouping actions by category."""
        registry = ActionRegistry()

        # Register actions in different categories
        categories = ["Model", "Model", "Cluster", "Testing"]
        for i, category in enumerate(categories):
            meta = ActionMeta(
                type=f"cat_action_{i}",
                name=f"Cat Action {i}",
                category=category,
                description="Test",
            )

            action_class = type(
                f"CatAction{i}",
                (),
                {"meta": meta, "executor_class": MockExecutor},
            )
            registry._register_action_class(f"cat_action_{i}", action_class)

        by_category = registry.get_by_category()
        assert len(by_category) == 3
        assert len(by_category["Model"]) == 2
        assert len(by_category["Cluster"]) == 1
        assert len(by_category["Testing"]) == 1

    def test_reset(self) -> None:
        """Test registry reset."""
        registry = ActionRegistry()

        action_meta = ActionMeta(
            type="reset_action",
            name="Reset Action",
            category="Testing",
            description="Test",
        )

        ResetAction = type(
            "ResetAction",
            (),
            {"meta": action_meta, "executor_class": MockExecutor},
        )

        registry._register_action_class("reset_action", ResetAction)
        assert registry.has("reset_action")

        registry.reset()
        assert not registry.has("reset_action")
        assert registry.list_actions() == []

    @patch("budpipeline.actions.base.registry.importlib.metadata.entry_points")
    def test_discover_actions(self, mock_entry_points: MagicMock) -> None:
        """Test action discovery from entry points."""
        registry = ActionRegistry()

        action_meta = ActionMeta(
            type="discovered_action",
            name="Discovered Action",
            category="Testing",
            description="Test",
        )

        DiscoveredAction = type(
            "DiscoveredAction",
            (),
            {"meta": action_meta, "executor_class": MockExecutor},
        )

        # Mock entry point
        mock_ep = MagicMock()
        mock_ep.name = "discovered_action"
        mock_ep.load.return_value = DiscoveredAction

        mock_entry_points.return_value = [mock_ep]

        registry.discover_actions()

        assert registry.has("discovered_action")
        mock_ep.load.assert_called_once()

    @patch("budpipeline.actions.base.registry.importlib.metadata.entry_points")
    def test_discover_actions_handles_errors(self, mock_entry_points: MagicMock) -> None:
        """Test that discovery continues on individual action errors."""
        registry = ActionRegistry()

        # First entry point fails
        bad_ep = MagicMock()
        bad_ep.name = "bad_action"
        bad_ep.load.side_effect = Exception("Load failed")

        # Second entry point succeeds
        good_meta = ActionMeta(
            type="good_action",
            name="Good Action",
            category="Testing",
            description="Test",
        )

        class GoodAction:
            meta = good_meta
            executor_class = MockExecutor

        good_ep = MagicMock()
        good_ep.name = "good_action"
        good_ep.load.return_value = GoodAction

        mock_entry_points.return_value = [bad_ep, good_ep]

        registry.discover_actions()

        # Good action should still be registered
        assert registry.has("good_action")
        assert not registry.has("bad_action")

    @patch("budpipeline.actions.base.registry.importlib.metadata.entry_points")
    def test_discover_actions_idempotent(self, mock_entry_points: MagicMock) -> None:
        """Test that discover_actions only runs once."""
        registry = ActionRegistry()

        mock_ep = MagicMock()
        mock_ep.name = "once_action"
        mock_ep.load.return_value = type(
            "OnceAction",
            (),
            {
                "meta": ActionMeta(
                    type="once_action",
                    name="Once",
                    category="Testing",
                    description="Test",
                ),
                "executor_class": MockExecutor,
            },
        )
        mock_entry_points.return_value = [mock_ep]

        registry.discover_actions()
        registry.discover_actions()  # Second call should be no-op

        mock_entry_points.assert_called_once()


class TestRegisterActionDecorator:
    """Tests for register_action decorator function."""

    @pytest.fixture(autouse=True)
    def reset_registry(self) -> None:
        """Reset registry before each test."""
        ActionRegistry._instance = None
        yield
        ActionRegistry._instance = None

    def test_register_action_decorator(self) -> None:
        """Test the register_action decorator."""
        meta = ActionMeta(
            type="decorated",
            name="Decorated",
            category="Testing",
            description="Test",
        )

        @register_action(meta)
        class DecoratedAction:
            executor_class = MockExecutor

        # Decorator should set meta attribute
        assert hasattr(DecoratedAction, "meta")
        assert DecoratedAction.meta is meta


class TestGlobalRegistry:
    """Tests for global registry instance."""

    def test_global_registry_exists(self) -> None:
        """Test that global action_registry is importable."""
        assert action_registry is not None
        assert isinstance(action_registry, ActionRegistry)


class TestThreadSafety:
    """Tests for thread safety of ActionRegistry."""

    @pytest.fixture(autouse=True)
    def reset_registry(self) -> None:
        """Reset registry before each test."""
        ActionRegistry._instance = None
        yield
        ActionRegistry._instance = None

    def test_singleton_has_locks(self) -> None:
        """Test that registry has thread safety primitives."""
        registry = ActionRegistry()
        assert hasattr(registry, "_executor_lock")
        assert hasattr(ActionRegistry, "_lock")
