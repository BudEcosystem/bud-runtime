"""Retention cleanup service for pipeline executions.

This module provides the retention cleanup workflow that removes
old pipeline execution records based on configurable retention period
(002-pipeline-event-persistence - T060, T061, T062).
"""

import time
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from budpipeline.commons.config import settings
from budpipeline.commons.database import AsyncSessionLocal
from budpipeline.commons.observability import get_logger
from budpipeline.pipeline.models import PipelineExecution, StepExecution
from budpipeline.progress.models import ProgressEvent
from budpipeline.subscriptions.models import ExecutionSubscription

logger = get_logger(__name__)

# Batch size for cleanup to manage memory
CLEANUP_BATCH_SIZE = 100


class RetentionCleanupService:
    """Service for cleaning up old pipeline execution records.

    Implements FR-048, FR-049, FR-050, FR-051, FR-052, FR-053.
    """

    def __init__(self, retention_days: int | None = None):
        """Initialize retention cleanup service.

        Args:
            retention_days: Number of days to retain records.
                           Defaults to settings.pipeline_retention_days.
        """
        self.retention_days = retention_days or settings.pipeline_retention_days

    def _get_cutoff_date(self) -> datetime:
        """Calculate the cutoff date for retention.

        Returns:
            Datetime representing the oldest date to keep.
        """
        return datetime.utcnow() - timedelta(days=self.retention_days)

    async def get_executions_to_cleanup(
        self,
        session: AsyncSession,
        limit: int = CLEANUP_BATCH_SIZE,
    ) -> list[UUID]:
        """Get execution IDs that are older than retention period.

        Args:
            session: Database session.
            limit: Maximum number of IDs to return.

        Returns:
            List of execution UUIDs to clean up.
        """
        cutoff_date = self._get_cutoff_date()

        stmt = (
            select(PipelineExecution.id)
            .where(PipelineExecution.created_at < cutoff_date)
            .order_by(PipelineExecution.created_at.asc())  # Oldest first
            .limit(limit)
        )

        result = await session.execute(stmt)
        return [row[0] for row in result.all()]

    async def delete_execution_cascade(
        self,
        session: AsyncSession,
        execution_id: UUID,
    ) -> dict[str, int]:
        """Delete an execution and all related records in dependency order.

        Deletes in order (FR-051):
        1. ProgressEvent records
        2. ExecutionSubscription records
        3. StepExecution records
        4. PipelineExecution record

        Args:
            session: Database session.
            execution_id: ID of execution to delete.

        Returns:
            Dictionary with counts of deleted records by type.
        """
        counts = {
            "progress_events": 0,
            "subscriptions": 0,
            "steps": 0,
            "executions": 0,
        }

        # 1. Delete ProgressEvent records
        progress_stmt = delete(ProgressEvent).where(ProgressEvent.execution_id == execution_id)
        progress_result = await session.execute(progress_stmt)
        counts["progress_events"] = progress_result.rowcount

        # 2. Delete ExecutionSubscription records
        subscription_stmt = delete(ExecutionSubscription).where(
            ExecutionSubscription.execution_id == execution_id
        )
        subscription_result = await session.execute(subscription_stmt)
        counts["subscriptions"] = subscription_result.rowcount

        # 3. Delete StepExecution records
        step_stmt = delete(StepExecution).where(StepExecution.execution_id == execution_id)
        step_result = await session.execute(step_stmt)
        counts["steps"] = step_result.rowcount

        # 4. Delete PipelineExecution record
        execution_stmt = delete(PipelineExecution).where(PipelineExecution.id == execution_id)
        execution_result = await session.execute(execution_stmt)
        counts["executions"] = execution_result.rowcount

        return counts

    async def run_cleanup(self) -> dict:
        """Run the retention cleanup job.

        Processes old executions in batches, deleting them
        in dependency order. Logs progress and errors (FR-052).
        Continues on individual failures (FR-053).

        Returns:
            Dictionary with cleanup results including counts and errors.
        """
        start_time = time.time()
        logger.info(
            "Retention cleanup started",
            retention_days=self.retention_days,
            cutoff_date=self._get_cutoff_date().isoformat(),
        )

        total_counts = {
            "progress_events": 0,
            "subscriptions": 0,
            "steps": 0,
            "executions": 0,
        }
        errors = []
        batch_count = 0

        try:
            while True:
                async with AsyncSessionLocal() as session:
                    # Get batch of executions to clean up
                    execution_ids = await self.get_executions_to_cleanup(
                        session, limit=CLEANUP_BATCH_SIZE
                    )

                    if not execution_ids:
                        logger.debug("No more executions to clean up")
                        break

                    batch_count += 1
                    batch_deleted = 0
                    batch_errors = 0

                    for execution_id in execution_ids:
                        try:
                            counts = await self.delete_execution_cascade(session, execution_id)

                            # Accumulate totals
                            for key, value in counts.items():
                                total_counts[key] += value

                            batch_deleted += 1

                            logger.debug(
                                "Deleted execution",
                                execution_id=str(execution_id),
                                progress_events=counts["progress_events"],
                                subscriptions=counts["subscriptions"],
                                steps=counts["steps"],
                            )

                        except Exception as e:
                            # Log error but continue (FR-053)
                            batch_errors += 1
                            error_msg = f"Failed to delete execution {execution_id}: {str(e)}"
                            errors.append(error_msg)
                            logger.error(
                                "Cleanup error for execution",
                                execution_id=str(execution_id),
                                error=str(e),
                            )
                            # Rollback this single deletion
                            await session.rollback()
                            continue

                    # Commit batch
                    await session.commit()

                    logger.info(
                        "Cleanup batch completed",
                        batch_number=batch_count,
                        deleted=batch_deleted,
                        errors=batch_errors,
                    )

        except Exception as e:
            logger.error(
                "Critical error during cleanup",
                error=str(e),
            )
            errors.append(f"Critical error: {str(e)}")

        elapsed_time = time.time() - start_time

        # Final logging (FR-052)
        logger.info(
            "Retention cleanup completed",
            duration_seconds=round(elapsed_time, 2),
            total_executions_deleted=total_counts["executions"],
            total_steps_deleted=total_counts["steps"],
            total_progress_events_deleted=total_counts["progress_events"],
            total_subscriptions_deleted=total_counts["subscriptions"],
            total_errors=len(errors),
            batches_processed=batch_count,
        )

        return {
            "status": "completed" if not errors else "completed_with_errors",
            "duration_seconds": round(elapsed_time, 2),
            "deleted": total_counts,
            "batches_processed": batch_count,
            "errors": errors,
        }

    async def get_cleanup_stats(self) -> dict:
        """Get statistics about executions pending cleanup.

        Returns:
            Dictionary with stats about old executions.
        """
        cutoff_date = self._get_cutoff_date()

        async with AsyncSessionLocal() as session:
            # Count old executions
            from sqlalchemy import func

            count_stmt = (
                select(func.count())
                .select_from(PipelineExecution)
                .where(PipelineExecution.created_at < cutoff_date)
            )
            count_result = await session.execute(count_stmt)
            pending_count = count_result.scalar_one()

            # Get oldest execution date
            oldest_stmt = select(func.min(PipelineExecution.created_at))
            oldest_result = await session.execute(oldest_stmt)
            oldest_date = oldest_result.scalar_one()

            return {
                "pending_cleanup_count": pending_count,
                "retention_days": self.retention_days,
                "cutoff_date": cutoff_date.isoformat(),
                "oldest_execution_date": oldest_date.isoformat() if oldest_date else None,
            }


# Global service instance
retention_service = RetentionCleanupService()


async def run_retention_cleanup() -> dict:
    """Run retention cleanup - entry point for scheduler.

    Returns:
        Cleanup results dictionary.
    """
    return await retention_service.run_cleanup()
