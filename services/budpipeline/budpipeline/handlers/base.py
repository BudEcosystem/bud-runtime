"""Base Handler - abstract base class for all action handlers.

Defines the interface that all handlers must implement for executing
workflow actions.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


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
    """

    success: bool
    """Whether the execution was successful."""

    outputs: dict[str, Any] = field(default_factory=dict)
    """Output values from the execution."""

    error: str | None = None
    """Error message if execution failed."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional metadata about the execution."""


class BaseHandler(ABC):
    """Abstract base class for all action handlers.

    Subclasses must define:
    - action_type: Unique identifier for this action type
    - name: Human-readable name
    - description: Description of what this handler does
    - execute(): Async method that performs the action
    - validate_params(): Method to validate input parameters
    """

    action_type: str = ""
    """Unique identifier for this action type (e.g., 'internal.model.onboard')."""

    name: str = ""
    """Human-readable name for this handler."""

    description: str = ""
    """Description of what this handler does."""

    @abstractmethod
    async def execute(self, context: HandlerContext) -> HandlerResult:
        """Execute the action.

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
