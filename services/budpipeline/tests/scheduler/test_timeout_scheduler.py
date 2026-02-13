"""Tests for timeout scheduler handling of wait_until steps."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from budpipeline.actions.base import EventAction, StepStatus
from budpipeline.handlers.event_router import process_timeout
from budpipeline.pipeline.models import StepExecution


def make_step_execution(
    handler_type: str = "test_action",
    external_workflow_id: str | None = None,
    outputs: dict | None = None,
    timeout_at: datetime | None = None,
) -> MagicMock:
    """Create a mock StepExecution."""
    step = MagicMock(spec=StepExecution)
    step.id = uuid4()
    step.step_id = "test_step"
    step.execution_id = uuid4()
    step.handler_type = handler_type
    step.external_workflow_id = external_workflow_id or f"{handler_type}:{uuid4()}"
    step.outputs = outputs or {}
    step.version = 1
    step.status = StepStatus.RUNNING
    step.awaiting_event = True
    step.timeout_at = timeout_at or datetime.now(timezone.utc)
    return step


class TestProcessTimeoutWaitUntil:
    """Tests for process_timeout handling of wait_until steps."""

    @pytest.mark.asyncio
    async def test_wait_until_completes_with_success(self) -> None:
        """Test that wait_until steps complete with COMPLETED status, not TIMEOUT."""
        session = AsyncMock()
        step = make_step_execution(
            handler_type="wait_until",
            external_workflow_id=f"wait_until:{uuid4()}",
            outputs={"wait_duration_seconds": 3600},
            timeout_at=datetime.now(timezone.utc),
        )

        mock_step_crud = AsyncMock()
        mock_step_crud.complete_step_from_event = AsyncMock()

        mock_exec_crud = AsyncMock()
        mock_exec_crud.get_by_id = AsyncMock(
            return_value=MagicMock(
                subscriber_ids=None,
                payload_type=None,
                notification_workflow_id=None,
            )
        )

        with (
            patch(
                "budpipeline.handlers.event_router.StepExecutionCRUD",
                return_value=mock_step_crud,
            ),
            patch(
                "budpipeline.handlers.event_router.PipelineExecutionCRUD",
                return_value=mock_exec_crud,
            ),
        ):
            result = await process_timeout(session, step)

        # Verify step completed with SUCCESS, not TIMEOUT
        assert result.routed is True
        assert result.step_completed is True
        assert result.final_status == StepStatus.COMPLETED
        assert result.action_taken == EventAction.COMPLETE

        # Verify the CRUD was called with correct status
        mock_step_crud.complete_step_from_event.assert_called_once()
        call_kwargs = mock_step_crud.complete_step_from_event.call_args[1]
        assert call_kwargs["status"] == StepStatus.COMPLETED
        assert call_kwargs["error_message"] is None
        assert call_kwargs["outputs"]["waited"] is True
        assert call_kwargs["outputs"]["actual_wake_time"] is not None

    @pytest.mark.asyncio
    async def test_regular_step_times_out(self) -> None:
        """Test that non-wait_until steps still timeout with TIMEOUT status."""
        session = AsyncMock()
        step = make_step_execution(
            handler_type="model_add",
            external_workflow_id=f"model_add:{uuid4()}",
        )

        mock_step_crud = AsyncMock()
        mock_step_crud.complete_step_from_event = AsyncMock()

        mock_exec_crud = AsyncMock()
        mock_exec_crud.get_by_id = AsyncMock(
            return_value=MagicMock(
                subscriber_ids=None,
                payload_type=None,
                notification_workflow_id=None,
            )
        )

        with (
            patch(
                "budpipeline.handlers.event_router.StepExecutionCRUD",
                return_value=mock_step_crud,
            ),
            patch(
                "budpipeline.handlers.event_router.PipelineExecutionCRUD",
                return_value=mock_exec_crud,
            ),
        ):
            result = await process_timeout(session, step)

        # Verify step completed with TIMEOUT
        assert result.routed is True
        assert result.step_completed is True
        assert result.final_status == StepStatus.TIMEOUT
        assert result.action_taken == EventAction.COMPLETE

        # Verify the CRUD was called with TIMEOUT status
        mock_step_crud.complete_step_from_event.assert_called_once()
        call_kwargs = mock_step_crud.complete_step_from_event.call_args[1]
        assert call_kwargs["status"] == StepStatus.TIMEOUT
        assert call_kwargs["error_message"] is not None
        assert "timed out" in call_kwargs["error_message"]
        assert call_kwargs["outputs"]["timeout"] is True

    @pytest.mark.asyncio
    async def test_wait_until_preserves_scheduled_wake_time(self) -> None:
        """Test that wait_until preserves the scheduled wake time in outputs."""
        session = AsyncMock()
        scheduled_time = datetime(2024, 1, 27, 9, 0, 0, tzinfo=timezone.utc)
        step = make_step_execution(
            handler_type="wait_until",
            external_workflow_id=f"wait_until:{uuid4()}",
            outputs={
                "wait_duration_seconds": 3600,
                "scheduled_wake_time": scheduled_time.isoformat(),
            },
            timeout_at=scheduled_time,
        )

        mock_step_crud = AsyncMock()
        mock_step_crud.complete_step_from_event = AsyncMock()

        mock_exec_crud = AsyncMock()
        mock_exec_crud.get_by_id = AsyncMock(
            return_value=MagicMock(
                subscriber_ids=None,
                payload_type=None,
                notification_workflow_id=None,
            )
        )

        with (
            patch(
                "budpipeline.handlers.event_router.StepExecutionCRUD",
                return_value=mock_step_crud,
            ),
            patch(
                "budpipeline.handlers.event_router.PipelineExecutionCRUD",
                return_value=mock_exec_crud,
            ),
        ):
            await process_timeout(session, step)

        # Verify outputs contain both scheduled and actual wake times
        call_kwargs = mock_step_crud.complete_step_from_event.call_args[1]
        outputs = call_kwargs["outputs"]
        assert outputs["scheduled_wake_time"] == scheduled_time.isoformat()
        assert outputs["actual_wake_time"] is not None
        assert outputs["wait_duration_seconds"] == 3600

    @pytest.mark.asyncio
    async def test_process_timeout_handles_exception(self) -> None:
        """Test that process_timeout handles exceptions gracefully."""
        session = AsyncMock()
        step = make_step_execution(handler_type="wait_until")

        mock_step_crud = AsyncMock()
        mock_step_crud.complete_step_from_event = AsyncMock(side_effect=Exception("Database error"))

        with patch(
            "budpipeline.handlers.event_router.StepExecutionCRUD",
            return_value=mock_step_crud,
        ):
            result = await process_timeout(session, step)

        assert result.routed is False
        assert result.error is not None
        assert "Database error" in result.error
