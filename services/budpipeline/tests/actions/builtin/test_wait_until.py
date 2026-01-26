"""Tests for wait_until action."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from budpipeline.actions.base import ActionContext, EventAction, EventContext, StepStatus
from budpipeline.actions.builtin.wait_until import (
    MAX_WAIT_HOURS,
    MIN_WAIT_HOURS,
    WaitUntilExecutor,
    _parse_until_time,
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


def make_event_context(
    step_outputs: dict | None = None,
    event_data: dict | None = None,
) -> EventContext:
    """Create a test EventContext."""
    return EventContext(
        step_execution_id=uuid4(),
        execution_id=uuid4(),
        external_workflow_id=f"wait_until:{uuid4()}",
        event_type="timeout",
        event_data=event_data or {},
        step_outputs=step_outputs or {},
    )


class TestWaitUntilExecutor:
    """Tests for WaitUntilExecutor."""

    @pytest.mark.asyncio
    async def test_execute_with_duration_hours(self) -> None:
        """Test execution with duration_hours parameter."""
        executor = WaitUntilExecutor()
        context = make_context(duration_hours=2.5)

        result = await executor.execute(context)

        assert result.success is True
        assert result.awaiting_event is True
        assert result.external_workflow_id is not None
        assert result.external_workflow_id.startswith("wait_until:")
        assert result.timeout_seconds is not None
        # 2.5 hours = 9000 seconds
        assert result.timeout_seconds == pytest.approx(2.5 * 3600, abs=2)
        assert result.outputs["waited"] is False
        assert result.outputs["scheduled_wake_time"] is not None
        assert result.outputs["actual_wake_time"] is None

    @pytest.mark.asyncio
    async def test_execute_with_until_time_iso(self) -> None:
        """Test execution with ISO format until_time."""
        executor = WaitUntilExecutor()
        # Use a time 1 hour in the future
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        context = make_context(until_time=future_time.isoformat())

        result = await executor.execute(context)

        assert result.success is True
        assert result.awaiting_event is True
        assert result.timeout_seconds is not None
        # Should be approximately 1 hour
        assert result.timeout_seconds == pytest.approx(3600, abs=10)

    @pytest.mark.asyncio
    async def test_execute_with_until_time_hhmm(self) -> None:
        """Test execution with HH:MM format until_time."""
        executor = WaitUntilExecutor()
        # Calculate a time that's definitely in the future
        now = datetime.now(timezone.utc)
        future_hour = (now.hour + 2) % 24
        context = make_context(until_time=f"{future_hour:02d}:30", timezone="UTC")

        result = await executor.execute(context)

        assert result.success is True
        assert result.awaiting_event is True
        assert result.external_workflow_id is not None

    @pytest.mark.asyncio
    async def test_execute_with_timezone(self) -> None:
        """Test execution with explicit timezone."""
        executor = WaitUntilExecutor()
        # Use a time 1 hour in the future
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        context = make_context(
            until_time=future_time.strftime("%Y-%m-%dT%H:%M:%S"),
            timezone="America/New_York",
        )

        result = await executor.execute(context)

        assert result.success is True
        assert result.awaiting_event is True

    @pytest.mark.asyncio
    async def test_execute_minimum_duration(self) -> None:
        """Test execution with minimum allowed duration (1 minute)."""
        executor = WaitUntilExecutor()
        context = make_context(duration_hours=MIN_WAIT_HOURS)

        result = await executor.execute(context)

        assert result.success is True
        assert result.awaiting_event is True
        assert result.timeout_seconds == pytest.approx(60, abs=2)  # ~1 minute

    @pytest.mark.asyncio
    async def test_execute_fails_duration_too_short(self) -> None:
        """Test execution fails when duration is too short."""
        executor = WaitUntilExecutor()
        context = make_context(duration_hours=0.001)  # ~3.6 seconds

        result = await executor.execute(context)

        assert result.success is False
        assert "at least" in result.error

    @pytest.mark.asyncio
    async def test_execute_fails_duration_too_long(self) -> None:
        """Test execution fails when duration exceeds 1 week."""
        executor = WaitUntilExecutor()
        context = make_context(duration_hours=200)  # > 168 hours

        result = await executor.execute(context)

        assert result.success is False
        assert str(MAX_WAIT_HOURS) in result.error

    @pytest.mark.asyncio
    async def test_execute_fails_past_time(self) -> None:
        """Test execution fails when until_time is in the past."""
        executor = WaitUntilExecutor()
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        context = make_context(until_time=past_time.isoformat())

        result = await executor.execute(context)

        assert result.success is False
        assert "future" in result.error

    @pytest.mark.asyncio
    async def test_execute_fails_missing_params(self) -> None:
        """Test execution fails when neither duration nor until_time specified."""
        executor = WaitUntilExecutor()
        context = make_context()

        result = await executor.execute(context)

        assert result.success is False
        assert "duration_hours" in result.error or "until_time" in result.error

    @pytest.mark.asyncio
    async def test_execute_fails_invalid_timezone(self) -> None:
        """Test execution fails with invalid timezone."""
        executor = WaitUntilExecutor()
        context = make_context(duration_hours=1, timezone="Invalid/Timezone")

        result = await executor.execute(context)

        assert result.success is False
        assert "timezone" in result.error.lower()

    @pytest.mark.asyncio
    async def test_on_event_completes_with_success(self) -> None:
        """Test on_event completes the step successfully."""
        executor = WaitUntilExecutor()
        context = make_event_context(
            step_outputs={
                "scheduled_wake_time": "2024-01-27T09:00:00+00:00",
                "wait_duration_seconds": 3600,
            }
        )

        result = await executor.on_event(context)

        assert result.action == EventAction.COMPLETE
        assert result.status == StepStatus.COMPLETED
        assert result.outputs["waited"] is True
        assert result.outputs["scheduled_wake_time"] == "2024-01-27T09:00:00+00:00"
        assert result.outputs["actual_wake_time"] is not None
        assert result.outputs["wait_duration_seconds"] == 3600


class TestWaitUntilValidation:
    """Tests for wait_until parameter validation."""

    def test_validate_params_missing_both(self) -> None:
        """Test validation fails when both params missing."""
        executor = WaitUntilExecutor()
        errors = executor.validate_params({})

        assert len(errors) > 0
        assert any("duration_hours" in e or "until_time" in e for e in errors)

    def test_validate_params_both_specified(self) -> None:
        """Test validation fails when both params specified."""
        executor = WaitUntilExecutor()
        errors = executor.validate_params({"duration_hours": 1, "until_time": "09:00"})

        assert len(errors) > 0
        assert any("not both" in e for e in errors)

    def test_validate_params_duration_too_long(self) -> None:
        """Test validation catches duration over limit."""
        executor = WaitUntilExecutor()
        errors = executor.validate_params({"duration_hours": 200})

        assert any(str(MAX_WAIT_HOURS) in e for e in errors)

    def test_validate_params_duration_too_short(self) -> None:
        """Test validation catches duration under limit."""
        executor = WaitUntilExecutor()
        errors = executor.validate_params({"duration_hours": 0.0001})

        assert any(str(MIN_WAIT_HOURS) in e for e in errors)

    def test_validate_params_invalid_duration_type(self) -> None:
        """Test validation catches non-numeric duration."""
        executor = WaitUntilExecutor()
        errors = executor.validate_params({"duration_hours": "not_a_number"})

        assert any("number" in e for e in errors)

    def test_validate_params_invalid_until_time_format(self) -> None:
        """Test validation catches invalid time format."""
        executor = WaitUntilExecutor()
        errors = executor.validate_params({"until_time": "invalid"})

        assert len(errors) > 0

    def test_validate_params_invalid_timezone(self) -> None:
        """Test validation catches invalid timezone."""
        executor = WaitUntilExecutor()
        errors = executor.validate_params({"duration_hours": 1, "timezone": "Invalid/TZ"})

        assert any("timezone" in e.lower() for e in errors)

    def test_validate_params_valid_duration(self) -> None:
        """Test validation passes for valid duration."""
        executor = WaitUntilExecutor()
        errors = executor.validate_params({"duration_hours": 2})

        assert len(errors) == 0

    def test_validate_params_valid_until_time(self) -> None:
        """Test validation passes for valid until_time."""
        executor = WaitUntilExecutor()
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        errors = executor.validate_params({"until_time": future_time.isoformat()})

        assert len(errors) == 0


class TestParseUntilTime:
    """Tests for _parse_until_time helper function."""

    def test_parse_iso_format(self) -> None:
        """Test parsing ISO 8601 format."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("UTC")
        result = _parse_until_time("2024-01-27T09:00:00", tz)

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 27
        assert result.hour == 9
        assert result.minute == 0
        assert result.tzinfo == timezone.utc

    def test_parse_iso_format_with_timezone(self) -> None:
        """Test parsing ISO 8601 format with timezone."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("UTC")
        result = _parse_until_time("2024-01-27T09:00:00-05:00", tz)

        # 9:00 EST = 14:00 UTC
        assert result.hour == 14
        assert result.tzinfo == timezone.utc

    def test_parse_time_only_hhmm(self) -> None:
        """Test parsing HH:MM format."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("UTC")
        result = _parse_until_time("09:00", tz)

        assert result.hour == 9
        assert result.minute == 0
        assert result.tzinfo == timezone.utc

    def test_parse_time_only_hhmmss(self) -> None:
        """Test parsing HH:MM:SS format."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("UTC")
        result = _parse_until_time("09:30:45", tz)

        assert result.hour == 9
        assert result.minute == 30
        assert result.second == 45

    def test_parse_time_only_uses_next_occurrence(self) -> None:
        """Test that time-only format uses next occurrence if time has passed."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("UTC")
        now = datetime.now(tz)

        # Use a time 1 hour in the past
        past_hour = (now.hour - 1) % 24
        result = _parse_until_time(f"{past_hour:02d}:00", tz)

        # Should be tomorrow
        assert result > now

    def test_parse_invalid_format_raises(self) -> None:
        """Test that invalid format raises ValueError."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("UTC")

        with pytest.raises(ValueError) as exc_info:
            _parse_until_time("invalid", tz)

        assert "Unrecognized time format" in str(exc_info.value)
