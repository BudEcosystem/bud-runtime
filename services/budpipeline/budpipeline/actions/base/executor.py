"""Base action executor definition.

This module defines the abstract base class that all action executors
must inherit from.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .context import ActionContext, EventContext
from .result import ActionResult, EventResult


class BaseActionExecutor(ABC):
    """Base class for action execution logic.

    All action executors must inherit from this class and implement
    the execute() method. Event-driven actions should also implement
    on_event().

    Example:
        class MyExecutor(BaseActionExecutor):
            async def execute(self, context: ActionContext) -> ActionResult:
                # Do work
                return ActionResult(success=True, outputs={"result": "done"})
    """

    @abstractmethod
    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute the action.

        For SYNC actions:
            Complete the work and return ActionResult with success=True/False.

        For EVENT_DRIVEN actions:
            Initiate the operation and return ActionResult with:
            - success=True
            - awaiting_event=True
            - external_workflow_id=<correlation_id>

        Args:
            context: Execution context with params and workflow state

        Returns:
            ActionResult indicating success/failure or awaiting event
        """
        pass

    async def on_event(self, context: EventContext) -> EventResult:
        """Handle incoming event for event-driven actions.

        Called when an external event matches this action's
        external_workflow_id. Override this method for EVENT_DRIVEN actions.

        Args:
            context: Event context with event data and step state

        Returns:
            EventResult indicating what action to take

        Raises:
            NotImplementedError: If not overridden for event-driven action
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement on_event(). "
            "Event-driven actions must override this method."
        )

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters beyond schema validation.

        Override this method to add custom validation logic that
        cannot be expressed in the ParamDefinition schema.

        Args:
            params: The resolved parameters to validate

        Returns:
            List of validation error messages. Empty if valid.
        """
        return []

    async def cleanup(self, context: ActionContext) -> None:  # noqa: B027
        """Cleanup resources on failure or cancellation.

        Override this method to release resources if the action
        is interrupted or fails. Called after execute() fails
        or when the execution is cancelled.

        Args:
            context: The execution context

        Note:
            This method is intentionally not abstract - most actions
            don't need cleanup. Subclasses can override when needed.
        """
