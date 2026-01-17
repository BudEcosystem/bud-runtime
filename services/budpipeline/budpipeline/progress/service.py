"""Progress aggregation service for budpipeline.

This module provides progress aggregation with weighted averaging,
monotonic progress enforcement, and ETA estimation
(002-pipeline-event-persistence - T033).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from budpipeline.commons.database import AsyncSessionLocal
from budpipeline.commons.observability import get_logger
from budpipeline.pipeline.crud import StepExecutionCRUD
from budpipeline.pipeline.models import StepStatus
from budpipeline.progress.crud import ProgressEventCRUD
from budpipeline.progress.models import ProgressEvent

logger = get_logger(__name__)


class ProgressAggregationService:
    """Service for aggregating pipeline progress from step executions.

    Implements:
    - Weighted average progress across concurrent steps (FR-009)
    - Monotonic progress (never decreases) (FR-020)
    - ETA estimation based on step completion rates (FR-018)
    """

    def __init__(self) -> None:
        """Initialize progress aggregation service."""
        self._last_progress: dict[UUID, Decimal] = {}  # Monotonic tracking
        self._step_start_times: dict[UUID, dict[str, datetime]] = {}  # For ETA

    async def calculate_aggregate_progress(
        self,
        execution_id: UUID,
    ) -> dict[str, Any]:
        """Calculate aggregated progress for an execution.

        Uses weighted averaging where each step contributes equally to overall progress.
        For concurrent steps, progress is averaged.

        Args:
            execution_id: Execution UUID.

        Returns:
            Dictionary with aggregated progress information:
            - overall_progress: Weighted average (0.00-100.00)
            - eta_seconds: Estimated time to completion
            - completed_steps: Number of completed steps
            - total_steps: Total number of steps
            - current_step: Name of currently running step
        """
        async with AsyncSessionLocal() as session:
            step_crud = StepExecutionCRUD(session)
            steps = await step_crud.get_by_execution_id(execution_id)

            if not steps:
                return {
                    "overall_progress": Decimal("0.00"),
                    "eta_seconds": None,
                    "completed_steps": 0,
                    "total_steps": 0,
                    "current_step": None,
                }

            total_steps = len(steps)
            completed_steps = 0
            running_steps = []
            total_progress = Decimal("0.00")
            current_step_name = None

            for step in steps:
                if step.status == StepStatus.COMPLETED:
                    completed_steps += 1
                    total_progress += Decimal("100.00")
                elif step.status == StepStatus.SKIPPED:
                    completed_steps += 1
                    total_progress += Decimal("100.00")  # Skipped counts as complete
                elif step.status == StepStatus.RUNNING:
                    running_steps.append(step)
                    total_progress += step.progress_percentage
                    current_step_name = step.step_name
                elif step.status == StepStatus.FAILED:
                    total_progress += step.progress_percentage
                # PENDING and RETRYING contribute 0

            # Calculate weighted average
            if total_steps > 0:
                overall_progress = total_progress / Decimal(total_steps)
            else:
                overall_progress = Decimal("0.00")

            # Enforce monotonic progress (FR-020)
            overall_progress = self._enforce_monotonic(execution_id, overall_progress)

            # Calculate ETA (FR-018)
            eta_seconds = await self._estimate_eta(
                execution_id,
                completed_steps,
                total_steps,
                running_steps,
            )

            return {
                "overall_progress": overall_progress.quantize(Decimal("0.01")),
                "eta_seconds": eta_seconds,
                "completed_steps": completed_steps,
                "total_steps": total_steps,
                "current_step": current_step_name,
            }

    def _enforce_monotonic(
        self,
        execution_id: UUID,
        new_progress: Decimal,
    ) -> Decimal:
        """Enforce monotonic progress (never decreases).

        Args:
            execution_id: Execution UUID.
            new_progress: Newly calculated progress.

        Returns:
            Progress value that is >= last recorded progress.
        """
        last_progress = self._last_progress.get(execution_id, Decimal("0.00"))

        if new_progress < last_progress:
            logger.debug(
                "Enforcing monotonic progress",
                execution_id=str(execution_id),
                calculated=str(new_progress),
                enforced=str(last_progress),
            )
            return last_progress

        self._last_progress[execution_id] = new_progress
        return new_progress

    async def _estimate_eta(
        self,
        execution_id: UUID,
        completed_steps: int,
        total_steps: int,
        running_steps: list,
    ) -> int | None:
        """Estimate time to completion based on step completion rates.

        Uses simple averaging: (time_elapsed / completed_steps) * remaining_steps

        Args:
            execution_id: Execution UUID.
            completed_steps: Number of completed steps.
            total_steps: Total number of steps.
            running_steps: Currently running steps.

        Returns:
            Estimated seconds to completion, or None if can't estimate.
        """
        if completed_steps == 0 or total_steps == completed_steps:
            return None

        # Get step timing data
        self._step_start_times.get(execution_id, {})

        # Calculate average step duration from completed steps
        total_duration = 0.0
        counted = 0

        async with AsyncSessionLocal() as session:
            step_crud = StepExecutionCRUD(session)
            steps = await step_crud.get_by_execution_id(execution_id)

            for step in steps:
                if step.status in (StepStatus.COMPLETED, StepStatus.SKIPPED):
                    if step.start_time and step.end_time:
                        duration = (step.end_time - step.start_time).total_seconds()
                        total_duration += duration
                        counted += 1

        if counted == 0:
            return None

        avg_step_duration = total_duration / counted
        remaining_steps = total_steps - completed_steps

        # Account for progress in running steps
        running_remaining = 0.0
        for step in running_steps:
            progress_ratio = float(step.progress_percentage) / 100.0
            running_remaining += (1.0 - progress_ratio) * avg_step_duration

        eta_seconds = int(
            running_remaining + (remaining_steps - len(running_steps)) * avg_step_duration
        )

        return max(0, eta_seconds)

    async def get_recent_events(
        self,
        execution_id: UUID,
        limit: int = 20,
    ) -> list[ProgressEvent]:
        """Get recent progress events for an execution.

        Args:
            execution_id: Execution UUID.
            limit: Maximum number of events.

        Returns:
            List of recent ProgressEvent instances.
        """
        async with AsyncSessionLocal() as session:
            crud = ProgressEventCRUD(session)
            return await crud.get_recent_events(execution_id, limit)

    async def record_step_start(
        self,
        execution_id: UUID,
        step_id: str,
    ) -> None:
        """Record step start time for ETA calculation.

        Args:
            execution_id: Execution UUID.
            step_id: Step identifier.
        """
        if execution_id not in self._step_start_times:
            self._step_start_times[execution_id] = {}
        self._step_start_times[execution_id][step_id] = datetime.utcnow()

    async def record_step_completed(
        self,
        execution_id: UUID,
        step_id: str,
        step_name: str,
        progress_percentage: Decimal,
    ) -> None:
        """Record step completion and create progress event.

        Args:
            execution_id: Execution UUID.
            step_id: Step identifier.
            step_name: Step name.
            progress_percentage: Current overall progress.
        """
        duration = None
        if execution_id in self._step_start_times:
            start_time = self._step_start_times[execution_id].get(step_id)
            if start_time:
                duration = int((datetime.utcnow() - start_time).total_seconds())

        async with AsyncSessionLocal() as session:
            crud = ProgressEventCRUD(session)
            await crud.create_step_completed_event(
                execution_id=execution_id,
                progress_percentage=progress_percentage,
                step_id=step_id,
                step_name=step_name,
                duration_seconds=duration,
            )
            await session.commit()

    async def record_workflow_progress(
        self,
        execution_id: UUID,
        progress_percentage: Decimal,
        eta_seconds: int | None = None,
        current_step: str | None = None,
    ) -> None:
        """Record overall workflow progress event.

        Args:
            execution_id: Execution UUID.
            progress_percentage: Current progress.
            eta_seconds: Estimated time remaining.
            current_step: Currently executing step description.
        """
        async with AsyncSessionLocal() as session:
            crud = ProgressEventCRUD(session)
            await crud.create_workflow_progress_event(
                execution_id=execution_id,
                progress_percentage=progress_percentage,
                eta_seconds=eta_seconds,
                current_step_desc=current_step,
            )
            await session.commit()

    async def record_workflow_completed(
        self,
        execution_id: UUID,
        success: bool,
        final_message: str | None = None,
    ) -> None:
        """Record workflow completion event.

        Args:
            execution_id: Execution UUID.
            success: Whether workflow completed successfully.
            final_message: Optional completion message.
        """
        async with AsyncSessionLocal() as session:
            crud = ProgressEventCRUD(session)
            await crud.create_workflow_completed_event(
                execution_id=execution_id,
                success=success,
                final_message=final_message,
            )
            await session.commit()

        # Clean up tracking data
        self._last_progress.pop(execution_id, None)
        self._step_start_times.pop(execution_id, None)

    def reset_execution_tracking(self, execution_id: UUID) -> None:
        """Reset progress tracking for an execution.

        Call when execution is completed or cancelled.

        Args:
            execution_id: Execution UUID.
        """
        self._last_progress.pop(execution_id, None)
        self._step_start_times.pop(execution_id, None)


# Global progress aggregation service instance
progress_service = ProgressAggregationService()
