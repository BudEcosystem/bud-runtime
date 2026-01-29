"""Wait Until action - durable wait that survives service restarts.

This action pauses pipeline execution until a specified time. Unlike the
in-memory delay action, wait_until uses database-persisted state and
the timeout scheduler to wake up, making it durable across service restarts.

Two modes are supported:
1. Duration-based: Wait for N hours (e.g., wait 2 hours)
2. Absolute time: Wait until a specific time (e.g., wait until 9:00 AM)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import structlog

from budpipeline.actions.base import (
    ActionContext,
    ActionMeta,
    ActionResult,
    BaseActionExecutor,
    EventAction,
    EventContext,
    EventResult,
    ExecutionMode,
    OutputDefinition,
    ParamDefinition,
    ParamType,
    StepStatus,
    ValidationRules,
    register_action,
)

logger = structlog.get_logger()

# Maximum wait duration: 1 week (168 hours)
MAX_WAIT_HOURS = 168
# Minimum wait duration: 1 minute (0.0167 hours)
MIN_WAIT_HOURS = 0.0167


def _parse_until_time(until_time: str, tz: ZoneInfo) -> datetime:
    """Parse until_time string into a datetime.

    Supports:
    - ISO 8601 format: '2024-01-27T09:00:00'
    - Time-only format: '09:00' (uses next occurrence in specified timezone)

    Args:
        until_time: Time string to parse.
        tz: Timezone for interpretation.

    Returns:
        Datetime in UTC.

    Raises:
        ValueError: If format is unrecognized.
    """
    # Try ISO 8601 format first
    try:
        # If it has a T, try ISO format
        if "T" in until_time:
            # Parse as naive datetime first
            dt = datetime.fromisoformat(until_time.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                # If no timezone info, apply the specified timezone
                dt = dt.replace(tzinfo=tz)
            return dt.astimezone(timezone.utc)
    except ValueError:
        pass

    # Try time-only format (HH:MM or HH:MM:SS)
    try:
        parts = until_time.split(":")
        if len(parts) >= 2:
            hour = int(parts[0])
            minute = int(parts[1])
            second = int(parts[2]) if len(parts) > 2 else 0

            # Get current time in the specified timezone
            now = datetime.now(tz)

            # Create target time for today
            target = now.replace(hour=hour, minute=minute, second=second, microsecond=0)

            # If target is in the past, use tomorrow
            if target <= now:
                target += timedelta(days=1)

            return target.astimezone(timezone.utc)
    except (ValueError, IndexError):
        pass

    raise ValueError(
        f"Unrecognized time format: '{until_time}'. "
        "Use ISO 8601 (e.g., '2024-01-27T09:00:00') or time-only (e.g., '09:00')"
    )


class WaitUntilExecutor(BaseActionExecutor):
    """Executor that waits until a specified time using the timeout scheduler."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Calculate wake time and return awaiting_event=True.

        The step will stay in RUNNING status until the timeout scheduler
        wakes it up by calling process_timeout().
        """
        duration_hours = context.params.get("duration_hours")
        until_time = context.params.get("until_time")
        tz_name = context.params.get("timezone", "UTC")

        # Resolve timezone
        try:
            tz = ZoneInfo(tz_name)
        except KeyError:
            return ActionResult(
                success=False,
                error=f"Invalid timezone: '{tz_name}'",
            )

        now = datetime.now(timezone.utc)

        # Calculate wake_time based on mode
        if duration_hours is not None:
            # Duration mode: wait for N hours
            try:
                hours = float(duration_hours)
            except (TypeError, ValueError):
                return ActionResult(
                    success=False,
                    error=f"Invalid duration_hours value: {duration_hours}",
                )

            if hours < MIN_WAIT_HOURS:
                return ActionResult(
                    success=False,
                    error=f"duration_hours must be at least {MIN_WAIT_HOURS} (1 minute)",
                )

            if hours > MAX_WAIT_HOURS:
                return ActionResult(
                    success=False,
                    error=f"duration_hours cannot exceed {MAX_WAIT_HOURS} (1 week)",
                )

            wake_time = now + timedelta(hours=hours)
            wait_description = f"{hours} hours"

        elif until_time is not None:
            # Absolute time mode: wait until specific time
            try:
                wake_time = _parse_until_time(until_time, tz)
            except ValueError as e:
                return ActionResult(
                    success=False,
                    error=str(e),
                )

            # Validate wake_time is in the future
            if wake_time <= now:
                return ActionResult(
                    success=False,
                    error=f"until_time must be in the future. Got: {until_time} ({tz_name})",
                )

            # Validate it's not too far in the future
            max_wake_time = now + timedelta(hours=MAX_WAIT_HOURS)
            if wake_time > max_wake_time:
                return ActionResult(
                    success=False,
                    error=f"until_time cannot be more than {MAX_WAIT_HOURS} hours in the future",
                )

            wait_description = f"until {wake_time.isoformat()}"

        else:
            return ActionResult(
                success=False,
                error="Either duration_hours or until_time must be specified",
            )

        # Calculate timeout in seconds for the scheduler
        timeout_seconds = int((wake_time - now).total_seconds())

        # Generate a unique workflow ID for this wait
        workflow_id = f"wait_until:{uuid.uuid4()}"

        logger.info(
            "wait_until_scheduled",
            step_id=context.step_id,
            execution_id=context.execution_id,
            wake_time=wake_time.isoformat(),
            timeout_seconds=timeout_seconds,
            wait_description=wait_description,
        )

        # Return immediately with awaiting_event=True
        # The timeout scheduler will wake us up at the specified time
        return ActionResult(
            success=True,
            outputs={
                "waited": False,  # Will be set to True when woken up
                "scheduled_wake_time": wake_time.isoformat(),
                "actual_wake_time": None,  # Will be set when woken up
                "wait_duration_seconds": timeout_seconds,
            },
            awaiting_event=True,
            external_workflow_id=workflow_id,
            timeout_seconds=timeout_seconds,
        )

    async def on_event(self, context: EventContext) -> EventResult:
        """Process wake-up event from timeout scheduler.

        This method is called when the timeout_at deadline is reached.
        For wait_until actions, this is the expected completion, not a timeout.
        """
        logger.info(
            "wait_until_woken_up",
            step_execution_id=context.step_execution_id,
            external_workflow_id=context.external_workflow_id,
        )

        return EventResult(
            action=EventAction.COMPLETE,
            status=StepStatus.COMPLETED,
            outputs={
                "waited": True,
                "scheduled_wake_time": context.step_outputs.get("scheduled_wake_time"),
                "actual_wake_time": datetime.now(timezone.utc).isoformat(),
                "wait_duration_seconds": context.step_outputs.get("wait_duration_seconds"),
            },
        )

    def validate_params(self, params: dict) -> list[str]:
        """Validate wait_until parameters."""
        errors = []

        duration_hours = params.get("duration_hours")
        until_time = params.get("until_time")
        tz_name = params.get("timezone", "UTC")

        # Must have one of duration_hours or until_time
        if duration_hours is None and until_time is None:
            errors.append("Either duration_hours or until_time must be specified")
            return errors

        # Cannot have both
        if duration_hours is not None and until_time is not None:
            errors.append("Specify either duration_hours or until_time, not both")
            return errors

        # Validate duration_hours
        if duration_hours is not None:
            try:
                hours = float(duration_hours)
                if hours < MIN_WAIT_HOURS:
                    errors.append(f"duration_hours must be at least {MIN_WAIT_HOURS} (1 minute)")
                if hours > MAX_WAIT_HOURS:
                    errors.append(f"duration_hours cannot exceed {MAX_WAIT_HOURS} (1 week)")
            except (TypeError, ValueError):
                errors.append(
                    f"duration_hours must be a number, got: {type(duration_hours).__name__}"
                )

        # Validate until_time
        if until_time is not None:
            if not isinstance(until_time, str):
                errors.append(f"until_time must be a string, got: {type(until_time).__name__}")
            else:
                # Try to parse to validate format
                try:
                    tz = ZoneInfo(tz_name)
                    _parse_until_time(until_time, tz)
                except KeyError:
                    errors.append(f"Invalid timezone: '{tz_name}'")
                except ValueError as e:
                    errors.append(str(e))

        # Validate timezone
        try:
            ZoneInfo(tz_name)
        except KeyError:
            errors.append(f"Invalid timezone: '{tz_name}'")

        return errors


META = ActionMeta(
    type="wait_until",
    version="1.0.0",
    name="Wait Until",
    category="Control Flow",
    description=(
        "Pause pipeline execution for a specified duration or until a specific time. "
        "This is a durable wait that survives service restarts (up to 1 week)."
    ),
    icon="clock",
    color="#6366f1",  # Indigo
    params=[
        ParamDefinition(
            name="duration_hours",
            label="Duration (hours)",
            type=ParamType.NUMBER,
            required=False,
            description="Hours to wait (min: 0.0167 = 1 minute, max: 168 = 1 week)",
            placeholder="2.5",
            validation=ValidationRules(min=MIN_WAIT_HOURS, max=MAX_WAIT_HOURS),
        ),
        ParamDefinition(
            name="until_time",
            label="Until Time",
            type=ParamType.STRING,
            required=False,
            description="Absolute time to wait until (ISO 8601: '2024-01-27T09:00:00' or time-only: '09:00')",
            placeholder="09:00 or 2024-01-27T09:00:00",
        ),
        ParamDefinition(
            name="timezone",
            label="Timezone",
            type=ParamType.STRING,
            required=False,
            default="UTC",
            description="Timezone for until_time (IANA format, e.g., 'America/New_York', 'Europe/London')",
            placeholder="UTC",
        ),
    ],
    outputs=[
        OutputDefinition(
            name="waited",
            type="boolean",
            description="True when the wait has completed",
        ),
        OutputDefinition(
            name="scheduled_wake_time",
            type="string",
            description="ISO timestamp of when the step was scheduled to wake up",
        ),
        OutputDefinition(
            name="actual_wake_time",
            type="string",
            description="ISO timestamp of when the step actually woke up",
        ),
        OutputDefinition(
            name="wait_duration_seconds",
            type="number",
            description="Total wait duration in seconds",
        ),
    ],
    execution_mode=ExecutionMode.EVENT_DRIVEN,
    timeout_seconds=int(MAX_WAIT_HOURS * 3600) + 60,  # Max wait + buffer
    idempotent=True,
)


@register_action(META)
class WaitUntilAction:
    """Wait Until action class for entry point registration."""

    meta = META
    executor_class = WaitUntilExecutor
