"""Handler Registry - manages registration and lookup of action handlers.

Provides:
- Handler registration by action type
- Handler lookup and instantiation
- Parameter validation
- Execution dispatch
"""

from collections.abc import Callable
from typing import Any

from budpipeline.commons.exceptions import ActionNotFoundError, ActionValidationError
from budpipeline.handlers.base import BaseHandler, HandlerContext, HandlerResult


class HandlerRegistry:
    """Registry for action handlers.

    Manages the mapping from action types to handler classes and provides
    methods for validation and execution.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._handlers: dict[str, type[BaseHandler]] = {}
        self._instances: dict[str, BaseHandler] = {}

    def register(self, handler_class: type[BaseHandler]) -> None:
        """Register a handler class.

        Args:
            handler_class: The handler class to register
        """
        action_type = handler_class.action_type
        self._handlers[action_type] = handler_class
        # Clear cached instance if re-registering
        self._instances.pop(action_type, None)

    def unregister(self, action_type: str) -> None:
        """Unregister a handler by action type.

        Args:
            action_type: The action type to unregister
        """
        self._handlers.pop(action_type, None)
        self._instances.pop(action_type, None)

    def get(self, action_type: str) -> BaseHandler:
        """Get a handler instance by action type.

        Args:
            action_type: The action type to look up

        Returns:
            Handler instance

        Raises:
            ActionNotFoundError: If action type is not registered
        """
        if action_type not in self._handlers:
            raise ActionNotFoundError(action_type)

        # Use cached instance or create new one
        if action_type not in self._instances:
            self._instances[action_type] = self._handlers[action_type]()

        return self._instances[action_type]

    def has(self, action_type: str) -> bool:
        """Check if a handler is registered.

        Args:
            action_type: The action type to check

        Returns:
            True if handler is registered
        """
        return action_type in self._handlers

    def list_handlers(self) -> list[str]:
        """List all registered action types.

        Returns:
            List of registered action types
        """
        return list(self._handlers.keys())

    def clear(self) -> None:
        """Clear all registered handlers."""
        self._handlers.clear()
        self._instances.clear()

    def get_info(self, action_type: str) -> dict[str, Any]:
        """Get metadata about a handler.

        Args:
            action_type: The action type to look up

        Returns:
            Dict with handler metadata

        Raises:
            ActionNotFoundError: If action type is not registered
        """
        handler = self.get(action_type)
        return {
            "action_type": handler.action_type,
            "name": handler.name,
            "description": handler.description,
            "required_params": handler.get_required_params(),
            "optional_params": handler.get_optional_params(),
            "outputs": handler.get_output_names(),
        }

    def validate_params(self, action_type: str, params: dict[str, Any]) -> list[str]:
        """Validate parameters for a handler.

        Args:
            action_type: The action type
            params: Parameters to validate

        Returns:
            List of validation errors (empty if valid)

        Raises:
            ActionNotFoundError: If action type is not registered
        """
        handler = self.get(action_type)
        return handler.validate_params(params)

    async def execute(
        self,
        action_type: str,
        context: HandlerContext,
        validate: bool = False,
    ) -> HandlerResult:
        """Execute a handler.

        Args:
            action_type: The action type to execute
            context: Execution context
            validate: If True, validate params before execution

        Returns:
            Handler execution result

        Raises:
            ActionNotFoundError: If action type is not registered
            ActionValidationError: If validation fails (when validate=True)
        """
        handler = self.get(action_type)

        if validate:
            errors = handler.validate_params(context.params)
            if errors:
                raise ActionValidationError(action_type, errors)

        return await handler.execute(context)


# Global registry instance
global_registry = HandlerRegistry()


def register_handler(
    cls_or_action: type[BaseHandler] | str | None = None,
) -> type[BaseHandler] | Callable[[type[BaseHandler]], type[BaseHandler]]:
    """Decorator to register a handler with the global registry.

    Usage:
        # With action type as argument
        @register_handler("my.action")
        class MyHandler(BaseHandler):
            ...

        # Without argument (uses class's action_type attribute)
        @register_handler
        class MyHandler(BaseHandler):
            action_type = "my.action"
            ...

    Args:
        cls_or_action: Either the handler class or the action type string

    Returns:
        The decorated class or a decorator function
    """
    if cls_or_action is None:
        # Called as @register_handler()
        def decorator(cls: type[BaseHandler]) -> type[BaseHandler]:
            global_registry.register(cls)
            return cls

        return decorator

    if isinstance(cls_or_action, str):
        # Called as @register_handler("action_type")
        action_type = cls_or_action

        def decorator(cls: type[BaseHandler]) -> type[BaseHandler]:
            # Set the action_type on the class
            cls.action_type = action_type
            global_registry.register(cls)
            return cls

        return decorator

    # Called as @register_handler (without parentheses)
    cls = cls_or_action
    global_registry.register(cls)
    return cls
