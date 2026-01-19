"""Schedule Polling Service - polls for due schedules and triggers executions.

Called by Dapr cron binding every minute to check for schedules that need
to run and trigger their associated workflows.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from budpipeline.commons.config import settings
from budpipeline.commons.constants import ScheduleType
from budpipeline.commons.database import get_db_session
from budpipeline.commons.exceptions import CronParseError
from budpipeline.pipeline.service import workflow_service
from budpipeline.scheduler.cron_parser import CronParser
from budpipeline.scheduler.schemas import ScheduleState
from budpipeline.scheduler.services import ScheduleService
from budpipeline.scheduler.storage import ScheduleStorage, schedule_storage

logger = logging.getLogger(__name__)


class SchedulePollingService:
    """Polls for due schedules and triggers workflow executions.

    Called by the Dapr cron binding at regular intervals (default: every minute).
    """

    def __init__(
        self,
        storage: ScheduleStorage | None = None,
    ):
        self.storage = storage or schedule_storage
        self._lock = asyncio.Lock()
        self._max_concurrent = settings.scheduler_max_concurrent_jobs

    async def poll_and_execute(self) -> dict[str, Any]:
        """Main polling method called by Dapr cron binding.

        1. Get all due schedules (next_run_at <= now)
        2. For each due schedule:
           - Check if enabled and not expired
           - Trigger workflow execution
           - Calculate next_run_at
           - Update schedule state
        3. Return summary of triggered schedules

        Returns:
            Dictionary with polling results
        """
        async with self._lock:  # Prevent concurrent poll runs
            now = datetime.now(timezone.utc)
            logger.debug(f"Polling for due schedules at {now.isoformat()}")

            try:
                due_schedules = await self.storage.get_due_schedules(now)
            except Exception as e:
                logger.error(f"Failed to get due schedules: {e}")
                return {
                    "polled_at": now.isoformat(),
                    "due_count": 0,
                    "triggered_count": 0,
                    "error_count": 1,
                    "errors": [{"error": str(e)}],
                }

            if not due_schedules:
                logger.debug("No due schedules found")
                return {
                    "polled_at": now.isoformat(),
                    "due_count": 0,
                    "triggered_count": 0,
                    "error_count": 0,
                }

            logger.info(f"Found {len(due_schedules)} due schedules")

            triggered: list[dict[str, Any]] = []
            errors: list[dict[str, Any]] = []

            # Process schedules (could be parallelized with semaphore)
            for schedule in due_schedules[: self._max_concurrent]:
                try:
                    result = await self._execute_schedule(schedule, now)
                    if result.get("skipped"):
                        logger.debug(f"Skipped schedule {schedule.id}: {result.get('skipped')}")
                    else:
                        triggered.append(result)
                except Exception as e:
                    logger.error(f"Failed to execute schedule {schedule.id}: {e}")
                    errors.append(
                        {
                            "schedule_id": schedule.id,
                            "schedule_name": schedule.name,
                            "error": str(e),
                        }
                    )

            summary = {
                "polled_at": now.isoformat(),
                "due_count": len(due_schedules),
                "triggered_count": len(triggered),
                "error_count": len(errors),
            }

            if triggered:
                summary["triggered"] = triggered
            if errors:
                summary["errors"] = errors

            logger.info(
                f"Schedule poll completed: triggered {len(triggered)} "
                f"of {len(due_schedules)} due schedules, {len(errors)} errors"
            )

            return summary

    async def _execute_schedule(
        self,
        schedule: ScheduleState,
        now: datetime,
    ) -> dict[str, Any]:
        """Execute a single schedule.

        Args:
            schedule: The schedule to execute
            now: Current time

        Returns:
            Execution result dictionary
        """
        # Check if enabled
        if not schedule.enabled:
            return {"schedule_id": schedule.id, "skipped": "disabled"}

        # Check if expired
        if schedule.expires_at and now > schedule.expires_at:
            await self._mark_expired(schedule)
            return {"schedule_id": schedule.id, "skipped": "expired"}

        # Check max runs
        if schedule.max_runs and schedule.run_count >= schedule.max_runs:
            await self._mark_completed(schedule)
            return {"schedule_id": schedule.id, "skipped": "max_runs_reached"}

        # Build trigger info
        trigger_info = {
            "type": "scheduled",
            "schedule_id": schedule.id,
            "schedule_name": schedule.name,
            "scheduled_at": (schedule.next_run_at.isoformat() if schedule.next_run_at else None),
            "triggered_at": now.isoformat(),
        }

        # Execute workflow
        logger.info(f"Triggering workflow {schedule.workflow_id} from schedule {schedule.id}")

        async with get_db_session() as session:
            result = await workflow_service.execute_pipeline_async(
                session=session,
                pipeline_id=schedule.workflow_id,
                params={
                    **schedule.params,
                    "_trigger": trigger_info,
                },
            )

        execution_id = result.get("execution_id", "")
        execution_status = result.get("status", "pending")

        # Calculate next run time
        next_run_at = self._calculate_next_run(schedule, now)

        # Update schedule state
        await self.storage.update_schedule_after_run(
            schedule_id=schedule.id,
            execution_id=execution_id,
            execution_status=execution_status,
            next_run_at=next_run_at,
        )

        return {
            "schedule_id": schedule.id,
            "schedule_name": schedule.name,
            "workflow_id": schedule.workflow_id,
            "execution_id": execution_id,
            "next_run_at": next_run_at.isoformat() if next_run_at else None,
        }

    def _calculate_next_run(
        self,
        schedule: ScheduleState,
        from_time: datetime,
    ) -> datetime | None:
        """Calculate next run time based on schedule type.

        Args:
            schedule: The schedule
            from_time: Base time for calculation

        Returns:
            Next run time, or None for completed schedules
        """
        if schedule.schedule_type == ScheduleType.ONE_TIME:
            # One-time schedules don't repeat
            return None

        if schedule.schedule_type == ScheduleType.CRON:
            if not schedule.expression:
                return None
            try:
                expr = CronParser.parse(schedule.expression, schedule.timezone)
                return CronParser.get_next(expr, from_time)
            except CronParseError:
                logger.error(
                    f"Invalid cron expression for schedule {schedule.id}: {schedule.expression}"
                )
                return None

        if schedule.schedule_type == ScheduleType.INTERVAL:
            if not schedule.expression:
                return None
            try:
                interval_seconds = ScheduleService._parse_interval(schedule.expression)
                return from_time + timedelta(seconds=interval_seconds)
            except ValueError:
                logger.error(
                    f"Invalid interval expression for schedule {schedule.id}: {schedule.expression}"
                )
                return None

        return None

    async def _mark_expired(self, schedule: ScheduleState) -> None:
        """Mark schedule as expired."""
        schedule.status = "expired"
        schedule.enabled = False
        schedule.next_run_at = None
        schedule.updated_at = datetime.now(timezone.utc)
        await self.storage.save_schedule(schedule)
        logger.info(f"Marked schedule {schedule.id} as expired")

    async def _mark_completed(self, schedule: ScheduleState) -> None:
        """Mark schedule as completed (max runs reached)."""
        schedule.status = "completed"
        schedule.enabled = False
        schedule.next_run_at = None
        schedule.updated_at = datetime.now(timezone.utc)
        await self.storage.save_schedule(schedule)
        logger.info(f"Marked schedule {schedule.id} as completed (max runs reached)")


# Global instance
polling_service = SchedulePollingService()
