"""Action registry for plugin discovery and management.

This module provides the central registry for all pipeline actions.
Actions are discovered via Python entry points at startup, enabling
plugin-style extensibility without modifying core code.
"""

from __future__ import annotations

import importlib.metadata
import threading
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import structlog

from .executor import BaseActionExecutor
from .meta import ActionMeta

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()


@runtime_checkable
class ActionClassProtocol(Protocol):
    """Protocol for action classes with meta and executor_class attributes."""

    meta: ActionMeta
    executor_class: type[BaseActionExecutor]


class ActionRegistry:
    """Central registry for all pipeline actions.

    Actions are discovered via Python entry points at startup.
    This enables plugin-style extensibility without modifying core code.

    Usage:
        from budpipeline.actions import action_registry

        # Discover all actions at startup
        action_registry.discover_actions()

        # Get action metadata
        meta = action_registry.get_meta("model_add")

        # Get action executor
        executor = action_registry.get_executor("model_add")

        # Check if action exists
        if action_registry.has("model_add"):
            ...
    """

    _instance: ActionRegistry | None = None
    _lock: threading.Lock = threading.Lock()

    # Instance attributes - declared here for mypy
    _actions: dict[str, dict[str, Any]]
    _loaded: bool
    _executor_lock: threading.Lock

    def __new__(cls) -> ActionRegistry:
        """Thread-safe singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._actions = {}
                    cls._instance._loaded = False
                    cls._instance._executor_lock = threading.Lock()
        return cls._instance

    def discover_actions(self) -> None:
        """Discover and load all actions from entry points.

        Scans the "budpipeline.actions" entry point group and loads
        all registered action classes.
        """
        if self._loaded:
            return

        try:
            entry_points = importlib.metadata.entry_points(group="budpipeline.actions")
        except TypeError:
            # Python < 3.10 compatibility
            all_eps = importlib.metadata.entry_points()
            entry_points: Iterable[Any] = all_eps.get("budpipeline.actions", [])

        for ep in entry_points:
            try:
                action_class = ep.load()
                self._register_action_class(ep.name, action_class)
                logger.info("action_registered", action_type=ep.name)
            except Exception as e:
                logger.error(
                    "action_registration_failed",
                    action_type=ep.name,
                    error=str(e),
                )

        self._loaded = True
        logger.info("action_discovery_complete", count=len(self._actions))

    def _register_action_class(
        self, action_type: str, action_class: type[ActionClassProtocol] | Any
    ) -> None:
        """Register an action class.

        Args:
            action_type: The action type identifier
            action_class: The action class with meta and executor_class attributes

        Raises:
            ValueError: If action class is invalid or has invalid metadata
        """
        if not hasattr(action_class, "meta"):
            raise ValueError(f"Action {action_type} missing 'meta' attribute")
        if not hasattr(action_class, "executor_class"):
            raise ValueError(f"Action {action_type} missing 'executor_class' attribute")

        meta: ActionMeta = action_class.meta  # type: ignore[union-attr]

        # Validate metadata
        errors = self._validate_meta(meta)
        if errors:
            raise ValueError(f"Invalid action metadata for {action_type}: {errors}")

        # Verify executor class
        executor_class: type[BaseActionExecutor] = action_class.executor_class  # type: ignore[union-attr]
        if not issubclass(executor_class, BaseActionExecutor):
            raise ValueError(
                f"executor_class for {action_type} must inherit from BaseActionExecutor"
            )

        self._actions[action_type] = {
            "meta": meta,
            "executor_class": executor_class,
            "executor_instance": None,  # Lazy instantiation
        }

    def register(self, action_class: type[ActionClassProtocol] | Any) -> type:
        """Decorator for manual action registration.

        Usage:
            @action_registry.register
            class MyAction:
                meta = ActionMeta(...)
                executor_class = MyExecutor

        Args:
            action_class: The action class to register

        Returns:
            The same action class (for decorator chaining)
        """
        meta: ActionMeta = action_class.meta  # type: ignore[union-attr]
        self._register_action_class(meta.type, action_class)
        return action_class

    def get_meta(self, action_type: str) -> ActionMeta | None:
        """Get action metadata by type.

        Args:
            action_type: The action type identifier

        Returns:
            ActionMeta if found, None otherwise
        """
        action = self._actions.get(action_type)
        return action["meta"] if action else None

    def get_executor(self, action_type: str) -> BaseActionExecutor:
        """Get action executor instance (lazy singleton, thread-safe).

        Args:
            action_type: The action type identifier

        Returns:
            The executor instance

        Raises:
            KeyError: If action type not found
        """
        action = self._actions.get(action_type)
        if not action:
            raise KeyError(f"Unknown action type: {action_type}")

        # Thread-safe lazy instantiation
        if action["executor_instance"] is None:
            with self._executor_lock:
                # Double-check after acquiring lock
                if action["executor_instance"] is None:
                    action["executor_instance"] = action["executor_class"]()

        return action["executor_instance"]

    def has(self, action_type: str) -> bool:
        """Check if action type is registered.

        Args:
            action_type: The action type identifier

        Returns:
            True if registered, False otherwise
        """
        return action_type in self._actions

    def list_actions(self) -> list[str]:
        """List all registered action types.

        Returns:
            List of action type identifiers
        """
        return list(self._actions.keys())

    def get_all_meta(self) -> list[ActionMeta]:
        """Get metadata for all registered actions.

        Returns:
            List of ActionMeta objects
        """
        return [a["meta"] for a in self._actions.values()]

    def get_by_category(self) -> dict[str, list[ActionMeta]]:
        """Get actions grouped by category.

        Returns:
            Dictionary mapping category names to lists of ActionMeta
        """
        by_category: dict[str, list[ActionMeta]] = {}
        for action in self._actions.values():
            meta = action["meta"]
            if meta.category not in by_category:
                by_category[meta.category] = []
            by_category[meta.category].append(meta)
        return by_category

    def _validate_meta(self, meta: ActionMeta) -> list[str]:
        """Validate action metadata.

        Args:
            meta: The ActionMeta to validate

        Returns:
            List of validation error messages
        """
        return meta.validate()

    def reset(self) -> None:
        """Reset the registry (for testing).

        Clears all registered actions and resets the loaded flag.
        Thread-safe.
        """
        with self._executor_lock:
            self._actions.clear()
            self._loaded = False


# Global registry instance
action_registry = ActionRegistry()


def register_action(meta: ActionMeta) -> Callable[[type], type]:
    """Decorator to register an action class with metadata.

    Usage:
        @register_action(ActionMeta(type="my_action", ...))
        class MyAction:
            executor_class = MyExecutor

    Args:
        meta: The action metadata

    Returns:
        Decorator function
    """

    def decorator(cls: type) -> type:
        cls.meta = meta  # type: ignore[attr-defined]
        # Registration happens when entry point is loaded
        return cls

    return decorator
