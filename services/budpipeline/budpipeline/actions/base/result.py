"""Action execution result definitions.

This module defines the result objects returned by action executors
after execution and event handling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventAction(str, Enum):
    """Actions that can be taken when handling an event."""

    COMPLETE = "complete"  # Complete the step (success or failure)
    UPDATE_PROGRESS = "update_progress"  # Update progress, keep waiting
    IGNORE = "ignore"  # Ignore this event, keep waiting


class StepStatus(str, Enum):
    """Status values for step execution.

    Note: Uses UPPERCASE values to match database model.
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    TIMEOUT = "TIMEOUT"
    RETRYING = "RETRYING"


@dataclass
class ActionResult:
    """Result returned from action execute() method.

    For SYNC actions:
        - success=True: Step completed successfully
        - success=False: Step failed

    For EVENT_DRIVEN actions:
        - success=True, awaiting_event=True: Step initiated, waiting for event
        - success=False: Step failed during initiation
    """

    success: bool
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    # Event-driven execution fields
    awaiting_event: bool = False
    external_workflow_id: str | None = None
    timeout_seconds: int | None = None

    def __post_init__(self) -> None:
        """Validate result state."""
        if self.awaiting_event and not self.success:
            raise ValueError("awaiting_event=True requires success=True")
        if self.awaiting_event and not self.external_workflow_id:
            raise ValueError("awaiting_event=True requires external_workflow_id")


@dataclass
class EventResult:
    """Result returned from action on_event() method.

    Determines what happens after processing an event:
        - COMPLETE: Finish the step with given status
        - UPDATE_PROGRESS: Update progress percentage, keep waiting
        - IGNORE: Ignore this event, continue waiting
    """

    action: EventAction
    status: StepStatus | None = None
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    progress: float | None = None  # 0.0 to 100.0
    eta_minutes: int | None = None  # Estimated time remaining in minutes

    def __post_init__(self) -> None:
        """Validate result state."""
        if self.action == EventAction.COMPLETE and self.status is None:
            raise ValueError("COMPLETE action requires status")
        if (
            self.action == EventAction.UPDATE_PROGRESS
            and self.progress is None
            and self.eta_minutes is None
        ):
            raise ValueError("UPDATE_PROGRESS action requires progress or eta_minutes")

    @staticmethod
    def eta_from_content(content: dict[str, Any]) -> EventResult | None:
        """Parse ETA from upstream service event content and build an UPDATE_PROGRESS result.

        Upstream services (budsim, budmodel, budcluster) publish ETA events with
        the estimated time in *minutes* as a string in content["message"].
        Returns None if the content doesn't contain a valid ETA.
        """
        eta_minutes_str = content.get("message", "")
        try:
            eta_minutes = max(0, int(eta_minutes_str))
        except (ValueError, TypeError):
            return None
        return EventResult(
            action=EventAction.UPDATE_PROGRESS,
            eta_minutes=eta_minutes,
        )
