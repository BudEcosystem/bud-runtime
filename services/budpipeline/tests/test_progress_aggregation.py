"""Unit tests for progress aggregation service.

Tests for T030 (002-pipeline-event-persistence):
- Weighted average progress calculation
- Monotonic progress enforcement (progress never decreases)
- ETA estimation
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from budpipeline.pipeline.models import StepExecution, StepStatus
from budpipeline.progress.service import ProgressAggregationService


@pytest.fixture
def progress_service():
    """Create a fresh progress aggregation service instance."""
    return ProgressAggregationService()


@pytest.fixture
def execution_id():
    """Generate a random execution ID."""
    return uuid4()


@pytest.fixture
def mock_step_execution():
    """Factory for creating mock step executions."""

    def _make_step(
        step_name: str,
        status: StepStatus,
        progress: Decimal = Decimal("0.00"),
        sequence: int = 1,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> MagicMock:
        step = MagicMock(spec=StepExecution)
        step.step_name = step_name
        step.status = status
        step.progress_percentage = progress
        step.sequence_number = sequence
        step.start_time = start_time
        step.end_time = end_time
        return step

    return _make_step


class TestWeightedAverageProgress:
    """Tests for weighted average progress calculation (FR-009)."""

    @pytest.mark.asyncio
    async def test_no_steps_returns_zero(self, progress_service, execution_id):
        """Test that execution with no steps returns 0% progress."""
        with patch("budpipeline.progress.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.get_by_execution_id = AsyncMock(return_value=[])

            with patch("budpipeline.progress.service.StepExecutionCRUD", return_value=mock_crud):
                result = await progress_service.calculate_aggregate_progress(execution_id)

        assert result["overall_progress"] == Decimal("0.00")
        assert result["completed_steps"] == 0
        assert result["total_steps"] == 0

    @pytest.mark.asyncio
    async def test_single_completed_step(self, progress_service, execution_id, mock_step_execution):
        """Test progress with single completed step."""
        step = mock_step_execution("Step 1", StepStatus.COMPLETED, Decimal("100.00"))

        with patch("budpipeline.progress.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.get_by_execution_id = AsyncMock(return_value=[step])

            with patch("budpipeline.progress.service.StepExecutionCRUD", return_value=mock_crud):
                result = await progress_service.calculate_aggregate_progress(execution_id)

        assert result["overall_progress"] == Decimal("100.00")
        assert result["completed_steps"] == 1
        assert result["total_steps"] == 1

    @pytest.mark.asyncio
    async def test_multiple_steps_weighted_average(
        self, progress_service, execution_id, mock_step_execution
    ):
        """Test weighted average across multiple steps.

        3 steps: 1 completed (100%), 1 running (50%), 1 pending (0%)
        Expected: (100 + 50 + 0) / 3 = 50%
        """
        steps = [
            mock_step_execution("Step 1", StepStatus.COMPLETED, Decimal("100.00"), 1),
            mock_step_execution("Step 2", StepStatus.RUNNING, Decimal("50.00"), 2),
            mock_step_execution("Step 3", StepStatus.PENDING, Decimal("0.00"), 3),
        ]

        with patch("budpipeline.progress.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.get_by_execution_id = AsyncMock(return_value=steps)

            with patch("budpipeline.progress.service.StepExecutionCRUD", return_value=mock_crud):
                result = await progress_service.calculate_aggregate_progress(execution_id)

        assert result["overall_progress"] == Decimal("50.00")
        assert result["completed_steps"] == 1
        assert result["total_steps"] == 3
        assert result["current_step"] == "Step 2"

    @pytest.mark.asyncio
    async def test_parallel_steps_weighted_average(
        self, progress_service, execution_id, mock_step_execution
    ):
        """Test weighted average with parallel steps.

        4 steps: step1 completed, step2a and step2b running in parallel, step3 pending
        step2a at 60%, step2b at 40%
        Expected: (100 + 60 + 40 + 0) / 4 = 50%
        """
        steps = [
            mock_step_execution("Step 1", StepStatus.COMPLETED, Decimal("100.00"), 1),
            mock_step_execution("Step 2A", StepStatus.RUNNING, Decimal("60.00"), 2),  # Running
            mock_step_execution(
                "Step 2B", StepStatus.RUNNING, Decimal("40.00"), 2
            ),  # Running parallel
            mock_step_execution("Step 3", StepStatus.PENDING, Decimal("0.00"), 3),
        ]

        with patch("budpipeline.progress.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.get_by_execution_id = AsyncMock(return_value=steps)

            with patch("budpipeline.progress.service.StepExecutionCRUD", return_value=mock_crud):
                result = await progress_service.calculate_aggregate_progress(execution_id)

        assert result["overall_progress"] == Decimal("50.00")
        assert result["completed_steps"] == 1
        assert result["total_steps"] == 4

    @pytest.mark.asyncio
    async def test_skipped_steps_count_as_complete(
        self, progress_service, execution_id, mock_step_execution
    ):
        """Test that skipped steps count as 100% for progress calculation."""
        steps = [
            mock_step_execution("Step 1", StepStatus.COMPLETED, Decimal("100.00"), 1),
            mock_step_execution("Step 2", StepStatus.SKIPPED, Decimal("0.00"), 2),  # Skipped
            mock_step_execution("Step 3", StepStatus.PENDING, Decimal("0.00"), 3),
        ]

        with patch("budpipeline.progress.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.get_by_execution_id = AsyncMock(return_value=steps)

            with patch("budpipeline.progress.service.StepExecutionCRUD", return_value=mock_crud):
                result = await progress_service.calculate_aggregate_progress(execution_id)

        # Skipped counts as 100%: (100 + 100 + 0) / 3 = 66.67
        assert result["overall_progress"] == Decimal("66.67")
        assert result["completed_steps"] == 2  # Skipped counts as completed
        assert result["total_steps"] == 3

    @pytest.mark.asyncio
    async def test_failed_step_contributes_partial_progress(
        self, progress_service, execution_id, mock_step_execution
    ):
        """Test that failed steps contribute their progress percentage."""
        steps = [
            mock_step_execution("Step 1", StepStatus.COMPLETED, Decimal("100.00"), 1),
            mock_step_execution("Step 2", StepStatus.FAILED, Decimal("30.00"), 2),  # Failed at 30%
        ]

        with patch("budpipeline.progress.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.get_by_execution_id = AsyncMock(return_value=steps)

            with patch("budpipeline.progress.service.StepExecutionCRUD", return_value=mock_crud):
                result = await progress_service.calculate_aggregate_progress(execution_id)

        # (100 + 30) / 2 = 65%
        assert result["overall_progress"] == Decimal("65.00")


class TestParallelStepAggregation:
    """Tests for parallel step progress aggregation (T065, FR-009)."""

    @pytest.fixture
    def progress_service(self):
        """Create a fresh progress aggregation service instance."""
        return ProgressAggregationService()

    @pytest.fixture
    def execution_id(self):
        """Generate a random execution ID."""
        return uuid4()

    @pytest.fixture
    def mock_step_execution(self):
        """Factory for creating mock step executions."""

        def _make_step(
            step_name: str,
            status: StepStatus,
            progress: Decimal = Decimal("0.00"),
            sequence: int = 1,
            start_time: datetime | None = None,
            end_time: datetime | None = None,
        ) -> MagicMock:
            step = MagicMock(spec=StepExecution)
            step.step_name = step_name
            step.status = status
            step.progress_percentage = progress
            step.sequence_number = sequence
            step.start_time = start_time
            step.end_time = end_time
            return step

        return _make_step

    @pytest.mark.asyncio
    async def test_multiple_parallel_steps_at_same_sequence(
        self, progress_service, execution_id, mock_step_execution
    ):
        """Test progress calculation with multiple parallel steps at same sequence.

        Scenario: 3 parallel steps (A, B, C) at sequence 2
        - Step A: 80% complete
        - Step B: 50% complete
        - Step C: 20% complete
        Each contributes equally to overall progress.
        """
        steps = [
            mock_step_execution("Step 1", StepStatus.COMPLETED, Decimal("100.00"), 1),
            mock_step_execution("Step 2A", StepStatus.RUNNING, Decimal("80.00"), 2),
            mock_step_execution("Step 2B", StepStatus.RUNNING, Decimal("50.00"), 2),
            mock_step_execution("Step 2C", StepStatus.RUNNING, Decimal("20.00"), 2),
            mock_step_execution("Step 3", StepStatus.PENDING, Decimal("0.00"), 3),
        ]

        with patch("budpipeline.progress.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.get_by_execution_id = AsyncMock(return_value=steps)

            with patch("budpipeline.progress.service.StepExecutionCRUD", return_value=mock_crud):
                result = await progress_service.calculate_aggregate_progress(execution_id)

        # (100 + 80 + 50 + 20 + 0) / 5 = 50%
        assert result["overall_progress"] == Decimal("50.00")
        assert result["total_steps"] == 5

    @pytest.mark.asyncio
    async def test_parallel_steps_some_completed(
        self, progress_service, execution_id, mock_step_execution
    ):
        """Test progress when some parallel steps complete before others."""
        steps = [
            mock_step_execution("Step 1", StepStatus.COMPLETED, Decimal("100.00"), 1),
            mock_step_execution("Step 2A", StepStatus.COMPLETED, Decimal("100.00"), 2),  # Done
            mock_step_execution("Step 2B", StepStatus.RUNNING, Decimal("60.00"), 2),  # In progress
            mock_step_execution("Step 3", StepStatus.PENDING, Decimal("0.00"), 3),
        ]

        with patch("budpipeline.progress.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.get_by_execution_id = AsyncMock(return_value=steps)

            with patch("budpipeline.progress.service.StepExecutionCRUD", return_value=mock_crud):
                result = await progress_service.calculate_aggregate_progress(execution_id)

        # (100 + 100 + 60 + 0) / 4 = 65%
        assert result["overall_progress"] == Decimal("65.00")
        assert result["completed_steps"] == 2

    @pytest.mark.asyncio
    async def test_parallel_step_with_one_failed(
        self, progress_service, execution_id, mock_step_execution
    ):
        """Test progress when one parallel step fails."""
        steps = [
            mock_step_execution("Step 1", StepStatus.COMPLETED, Decimal("100.00"), 1),
            mock_step_execution("Step 2A", StepStatus.FAILED, Decimal("40.00"), 2),  # Failed at 40%
            mock_step_execution(
                "Step 2B", StepStatus.RUNNING, Decimal("70.00"), 2
            ),  # Still running
            mock_step_execution("Step 3", StepStatus.PENDING, Decimal("0.00"), 3),
        ]

        with patch("budpipeline.progress.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.get_by_execution_id = AsyncMock(return_value=steps)

            with patch("budpipeline.progress.service.StepExecutionCRUD", return_value=mock_crud):
                result = await progress_service.calculate_aggregate_progress(execution_id)

        # (100 + 40 + 70 + 0) / 4 = 52.5%
        assert result["overall_progress"] == Decimal("52.50")

    @pytest.mark.asyncio
    async def test_large_parallel_fan_out(
        self, progress_service, execution_id, mock_step_execution
    ):
        """Test progress with large parallel fan-out (10 parallel steps)."""
        steps = [
            mock_step_execution("Step 1", StepStatus.COMPLETED, Decimal("100.00"), 1),
        ]
        # Add 10 parallel steps at sequence 2
        for i in range(10):
            progress = Decimal(str(i * 10))  # 0, 10, 20, ..., 90
            steps.append(mock_step_execution(f"Step 2-{i}", StepStatus.RUNNING, progress, 2))
        steps.append(mock_step_execution("Step 3", StepStatus.PENDING, Decimal("0.00"), 3))

        with patch("budpipeline.progress.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.get_by_execution_id = AsyncMock(return_value=steps)

            with patch("budpipeline.progress.service.StepExecutionCRUD", return_value=mock_crud):
                result = await progress_service.calculate_aggregate_progress(execution_id)

        # 1 completed + 10 running (avg 45%) + 1 pending = 12 steps
        # (100 + 0+10+20+30+40+50+60+70+80+90 + 0) / 12 = (100 + 450 + 0) / 12 = 45.83
        assert result["total_steps"] == 12
        assert result["overall_progress"] == Decimal("45.83")

    @pytest.mark.asyncio
    async def test_all_parallel_steps_completed(
        self, progress_service, execution_id, mock_step_execution
    ):
        """Test that all parallel steps must complete before next sequence starts."""
        steps = [
            mock_step_execution("Step 1", StepStatus.COMPLETED, Decimal("100.00"), 1),
            mock_step_execution("Step 2A", StepStatus.COMPLETED, Decimal("100.00"), 2),
            mock_step_execution("Step 2B", StepStatus.COMPLETED, Decimal("100.00"), 2),
            mock_step_execution("Step 3", StepStatus.RUNNING, Decimal("30.00"), 3),  # Started
        ]

        with patch("budpipeline.progress.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.get_by_execution_id = AsyncMock(return_value=steps)

            with patch("budpipeline.progress.service.StepExecutionCRUD", return_value=mock_crud):
                result = await progress_service.calculate_aggregate_progress(execution_id)

        # (100 + 100 + 100 + 30) / 4 = 82.5%
        assert result["overall_progress"] == Decimal("82.50")
        assert result["completed_steps"] == 3
        assert result["current_step"] == "Step 3"


class TestMonotonicProgress:
    """Tests for monotonic progress enforcement (FR-020)."""

    def test_progress_never_decreases(self, progress_service, execution_id):
        """Test that progress never decreases."""
        # First progress update at 50%
        result1 = progress_service._enforce_monotonic(execution_id, Decimal("50.00"))
        assert result1 == Decimal("50.00")

        # Second update at 75% - should increase
        result2 = progress_service._enforce_monotonic(execution_id, Decimal("75.00"))
        assert result2 == Decimal("75.00")

        # Third update at 60% - should stay at 75%
        result3 = progress_service._enforce_monotonic(execution_id, Decimal("60.00"))
        assert result3 == Decimal("75.00")

        # Fourth update at 80% - should increase
        result4 = progress_service._enforce_monotonic(execution_id, Decimal("80.00"))
        assert result4 == Decimal("80.00")

    def test_progress_starts_at_zero(self, progress_service, execution_id):
        """Test that new execution starts with 0% progress baseline."""
        # New execution, any positive progress should be accepted
        result = progress_service._enforce_monotonic(execution_id, Decimal("10.00"))
        assert result == Decimal("10.00")

    def test_progress_independent_per_execution(self, progress_service):
        """Test that progress tracking is independent per execution."""
        exec1 = uuid4()
        exec2 = uuid4()

        # Execution 1 at 50%
        progress_service._enforce_monotonic(exec1, Decimal("50.00"))

        # Execution 2 at 30% (independent)
        result2 = progress_service._enforce_monotonic(exec2, Decimal("30.00"))
        assert result2 == Decimal("30.00")

        # Execution 1 at 40% should stay at 50%
        result1 = progress_service._enforce_monotonic(exec1, Decimal("40.00"))
        assert result1 == Decimal("50.00")

        # Execution 2 at 60% should increase to 60%
        result2 = progress_service._enforce_monotonic(exec2, Decimal("60.00"))
        assert result2 == Decimal("60.00")

    def test_reset_tracking_clears_progress(self, progress_service, execution_id):
        """Test that reset_execution_tracking clears progress for execution."""
        # Set progress
        progress_service._enforce_monotonic(execution_id, Decimal("75.00"))

        # Reset tracking
        progress_service.reset_execution_tracking(execution_id)

        # New progress should start fresh
        result = progress_service._enforce_monotonic(execution_id, Decimal("25.00"))
        assert result == Decimal("25.00")


class TestETAEstimation:
    """Tests for ETA estimation (FR-018)."""

    @pytest.mark.asyncio
    async def test_eta_with_no_completed_steps(
        self, progress_service, execution_id, mock_step_execution
    ):
        """Test that ETA is None when no steps are completed."""
        steps = [
            mock_step_execution("Step 1", StepStatus.RUNNING, Decimal("50.00"), 1),
        ]

        with patch("budpipeline.progress.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.get_by_execution_id = AsyncMock(return_value=steps)

            with patch("budpipeline.progress.service.StepExecutionCRUD", return_value=mock_crud):
                result = await progress_service.calculate_aggregate_progress(execution_id)

        assert result["eta_seconds"] is None

    @pytest.mark.asyncio
    async def test_eta_with_all_steps_completed(
        self, progress_service, execution_id, mock_step_execution
    ):
        """Test that ETA is None when all steps are completed."""
        now = datetime.now(timezone.utc)
        steps = [
            mock_step_execution(
                "Step 1",
                StepStatus.COMPLETED,
                Decimal("100.00"),
                1,
                start_time=now - timedelta(seconds=60),
                end_time=now - timedelta(seconds=30),
            ),
            mock_step_execution(
                "Step 2",
                StepStatus.COMPLETED,
                Decimal("100.00"),
                2,
                start_time=now - timedelta(seconds=30),
                end_time=now,
            ),
        ]

        with patch("budpipeline.progress.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.get_by_execution_id = AsyncMock(return_value=steps)

            with patch("budpipeline.progress.service.StepExecutionCRUD", return_value=mock_crud):
                result = await progress_service.calculate_aggregate_progress(execution_id)

        assert result["eta_seconds"] is None

    @pytest.mark.asyncio
    async def test_eta_calculation_with_timing_data(
        self, progress_service, execution_id, mock_step_execution
    ):
        """Test ETA calculation based on completed step durations."""
        now = datetime.now(timezone.utc)

        # Step 1 completed in 30 seconds
        # Step 2 completed in 30 seconds
        # Step 3 running at 50%
        # Step 4 pending
        # Average duration = 30s, remaining = 1.5 steps worth = 45s
        steps = [
            mock_step_execution(
                "Step 1",
                StepStatus.COMPLETED,
                Decimal("100.00"),
                1,
                start_time=now - timedelta(seconds=90),
                end_time=now - timedelta(seconds=60),
            ),
            mock_step_execution(
                "Step 2",
                StepStatus.COMPLETED,
                Decimal("100.00"),
                2,
                start_time=now - timedelta(seconds=60),
                end_time=now - timedelta(seconds=30),
            ),
            mock_step_execution(
                "Step 3",
                StepStatus.RUNNING,
                Decimal("50.00"),  # 50% done
                3,
                start_time=now - timedelta(seconds=15),
                end_time=None,
            ),
            mock_step_execution(
                "Step 4",
                StepStatus.PENDING,
                Decimal("0.00"),
                4,
            ),
        ]

        with patch("budpipeline.progress.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.get_by_execution_id = AsyncMock(return_value=steps)

            with patch("budpipeline.progress.service.StepExecutionCRUD", return_value=mock_crud):
                result = await progress_service.calculate_aggregate_progress(execution_id)

        # Should have some ETA estimate
        assert result["eta_seconds"] is not None
        assert result["eta_seconds"] >= 0


class TestProgressEventRecording:
    """Tests for progress event recording methods."""

    @pytest.mark.asyncio
    async def test_record_step_start(self, progress_service, execution_id):
        """Test recording step start time for ETA calculation."""
        await progress_service.record_step_start(execution_id, "step1")

        assert execution_id in progress_service._step_start_times
        assert "step1" in progress_service._step_start_times[execution_id]
        assert isinstance(progress_service._step_start_times[execution_id]["step1"], datetime)

    @pytest.mark.asyncio
    async def test_record_step_completed(self, progress_service, execution_id):
        """Test recording step completion creates progress event."""
        # Record start first
        await progress_service.record_step_start(execution_id, "step1")

        with patch("budpipeline.progress.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.create_step_completed_event = AsyncMock()

            with patch("budpipeline.progress.service.ProgressEventCRUD", return_value=mock_crud):
                await progress_service.record_step_completed(
                    execution_id=execution_id,
                    step_id="step1",
                    step_name="First Step",
                    progress_percentage=Decimal("25.00"),
                )

            # Should have called create event
            mock_crud.create_step_completed_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_workflow_completed_cleans_up_tracking(
        self, progress_service, execution_id
    ):
        """Test that workflow completion cleans up tracking data."""
        # Set up some tracking data
        progress_service._enforce_monotonic(execution_id, Decimal("50.00"))
        await progress_service.record_step_start(execution_id, "step1")

        assert execution_id in progress_service._last_progress
        assert execution_id in progress_service._step_start_times

        with patch("budpipeline.progress.service.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_crud = MagicMock()
            mock_crud.create_workflow_completed_event = AsyncMock()

            with patch("budpipeline.progress.service.ProgressEventCRUD", return_value=mock_crud):
                await progress_service.record_workflow_completed(
                    execution_id=execution_id,
                    success=True,
                    final_message="Completed successfully",
                )

        # Tracking data should be cleaned up
        assert execution_id not in progress_service._last_progress
        assert execution_id not in progress_service._step_start_times
