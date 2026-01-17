"""Base Handler - abstract base class for all action handlers.

Defines the interface that all handlers must implement for executing
workflow actions. Supports both synchronous and event-driven async handlers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from budpipeline.pipeline.models import StepStatus


class EventAction(str, Enum):
    """Actions that can be taken in response to an event."""

    COMPLETE = "complete"  # Complete the step (COMPLETED or FAILED)
    UPDATE_PROGRESS = "update_progress"  # Update progress, keep waiting
    IGNORE = "ignore"  # Event not relevant, ignore it


@dataclass
class HandlerContext:
    """Context passed to handlers during execution.

    Contains all information needed for a handler to execute its action.
    """

    step_id: str
    """The ID of the step being executed."""

    execution_id: str
    """The workflow execution ID."""

    params: dict[str, Any]
    """Resolved parameters for this step."""

    workflow_params: dict[str, Any]
    """Original workflow-level parameters."""

    step_outputs: dict[str, dict[str, Any]]
    """Outputs from previously executed steps."""

    timeout_seconds: int | None = None
    """Optional timeout for this step execution."""

    retry_count: int = 0
    """Current retry attempt (0 for first attempt)."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional metadata for handler use."""


@dataclass
class HandlerResult:
    """Result returned by a handler after execution.

    Contains success/failure status, outputs, and any error information.
    For async handlers, also contains event-driven tracking information.
    """

    success: bool
    """Whether the execution was successful (or successfully started for async)."""

    outputs: dict[str, Any] = field(default_factory=dict)
    """Output values from the execution."""

    error: str | None = None
    """Error message if execution failed."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional metadata about the execution."""

    # Event-driven completion tracking fields
    awaiting_event: bool = False
    """True if handler is waiting for external event to complete."""

    external_workflow_id: str | None = None
    """External workflow ID for event correlation (e.g., budapp workflow_id)."""

    timeout_seconds: int | None = None
    """Timeout in seconds for waiting on external event."""


@dataclass
class EventContext:
    """Context passed to handlers when processing an incoming event.

    Contains the event data and information about the step waiting for it.
    """

    step_execution_id: str
    """The step execution UUID waiting for this event."""

    execution_id: str
    """The pipeline execution UUID."""

    external_workflow_id: str
    """The external workflow ID that generated this event."""

    event_type: str
    """The type of event received (e.g., 'performance_benchmark')."""

    event_data: dict[str, Any]
    """The full event payload."""

    step_outputs: dict[str, Any] = field(default_factory=dict)
    """Previous outputs from the execute() call."""


@dataclass
class EventHandlerResult:
    """Result returned by a handler after processing an event.

    Tells the event router what action to take based on the event.
    """

    action: EventAction
    """Action to take: complete the step, update progress, or ignore."""

    status: StepStatus | None = None
    """Final step status if action is COMPLETE (COMPLETED, FAILED)."""

    outputs: dict[str, Any] = field(default_factory=dict)
    """Output values to store if completing."""

    error: str | None = None
    """Error message if status is FAILED."""

    progress: float | None = None
    """Progress percentage if action is UPDATE_PROGRESS (0.0-100.0)."""


class BaseHandler(ABC):
    """Abstract base class for all action handlers.

    Subclasses must define:
    - action_type: Unique identifier for this action type
    - name: Human-readable name
    - description: Description of what this handler does
    - execute(): Async method that performs the action
    - validate_params(): Method to validate input parameters

    For event-driven handlers (requires_events=True), also implement:
    - on_event(): Async method that processes incoming events
    """

    action_type: str = ""
    """Unique identifier for this action type (e.g., 'internal.model.onboard')."""

    name: str = ""
    """Human-readable name for this handler."""

    description: str = ""
    """Description of what this handler does."""

    requires_events: bool = False
    """True if this handler uses event-driven completion.

    When True, execute() should return with awaiting_event=True and an
    external_workflow_id, and on_event() will be called when events arrive.
    """

    @abstractmethod
    async def execute(self, context: HandlerContext) -> HandlerResult:
        """Execute the action.

        For synchronous handlers: Execute and return final result.
        For async handlers: Start the operation and return with
        awaiting_event=True, external_workflow_id set.

        Args:
            context: Execution context with parameters and step info

        Returns:
            HandlerResult with success status and outputs
        """
        pass

    @abstractmethod
    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate the input parameters for this handler.

        Args:
            params: Parameters to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        pass

    async def on_event(self, context: EventContext) -> EventHandlerResult:
        """Process an incoming event for this handler.

        Called when an event arrives that matches this handler's
        external_workflow_id. The handler should examine the event
        and decide whether to complete the step.

        Override in handlers that use event-driven completion
        (requires_events=True).

        Args:
            context: Event context with event data and step info

        Returns:
            EventHandlerResult telling router what action to take
        """
        # Default implementation ignores all events
        # Subclasses should override this for event-driven completion
        return EventHandlerResult(action=EventAction.IGNORE)

    def get_required_params(self) -> list[str]:
        """Get list of required parameter names.

        Override in subclass to specify required parameters.

        Returns:
            List of required parameter names
        """
        return []

    def get_optional_params(self) -> dict[str, Any]:
        """Get optional parameters with their defaults.

        Override in subclass to specify optional parameters.

        Returns:
            Dict mapping parameter names to default values
        """
        return {}

    def get_output_names(self) -> list[str]:
        """Get list of output names this handler produces.

        Override in subclass to specify outputs.

        Returns:
            List of output names
        """
        return []

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(action_type='{self.action_type}')"
