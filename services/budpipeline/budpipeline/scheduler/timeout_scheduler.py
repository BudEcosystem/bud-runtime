"""Timeout Scheduler - checks for and handles timed-out event-driven steps.

This module provides a scheduler that periodically checks for steps that have
been waiting for external events past their timeout_at deadline and marks them
as TIMEOUT status.
"""

import logging
from datetime import datetime, timezone

from budpipeline.commons.config import settings
from budpipeline.commons.database import AsyncSessionLocal
from budpipeline.handlers.event_router import process_timeout, trigger_pipeline_continuation
from budpipeline.pipeline.crud import StepExecutionCRUD

logger = logging.getLogger(__name__)


async def check_and_process_timeouts() -> dict:
    """Check for timed-out steps and process them.

    This function is called by the Dapr cron binding to periodically
    check for steps that have exceeded their timeout_at deadline.

    Returns:
        Dict with processing results.
    """
    try:
        async with AsyncSessionLocal() as session:
            step_crud = StepExecutionCRUD(session)

            # Get all steps that have timed out
            current_time = datetime.now(timezone.utc)
            timed_out_steps = await step_crud.get_timed_out_steps(current_time)

            if not timed_out_steps:
                logger.debug("No timed-out steps found")
                return {
                    "status": "ok",
                    "checked_at": current_time.isoformat(),
                    "timed_out_count": 0,
                    "processed_count": 0,
                }

            logger.info(f"Found {len(timed_out_steps)} timed-out steps to process")

            processed_count = 0
            errors = []

            for step in timed_out_steps:
                try:
                    logger.info(
                        f"Processing timeout for step {step.id} "
                        f"(external_workflow_id={step.external_workflow_id}, "
                        f"timeout_at={step.timeout_at})"
                    )

                    # Process the timeout
                    result = await process_timeout(session, step)

                    if result.step_completed:
                        processed_count += 1

                        # Trigger pipeline continuation to update execution status
                        try:
                            await trigger_pipeline_continuation(session, step.id)
                        except Exception as cont_err:
                            logger.error(
                                f"Failed to trigger continuation for step {step.id}: {cont_err}"
                            )
                    else:
                        errors.append(f"Step {step.id}: {result.error or 'Unknown error'}")

                except Exception as e:
                    error_msg = f"Step {step.id}: {str(e)}"
                    logger.exception(f"Error processing timeout: {error_msg}")
                    errors.append(error_msg)

            await session.commit()

            logger.info(
                f"Timeout check completed: processed {processed_count} of "
                f"{len(timed_out_steps)} timed-out steps"
            )

            return {
                "status": "ok" if not errors else "partial",
                "checked_at": current_time.isoformat(),
                "timed_out_count": len(timed_out_steps),
                "processed_count": processed_count,
                "errors": errors if errors else None,
            }

    except Exception as e:
        logger.exception(f"Error in timeout check: {e}")
        return {
            "status": "error",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
        }


async def get_timeout_stats() -> dict:
    """Get statistics about steps awaiting events and timeouts.

    Returns:
        Dict with timeout statistics.
    """
    try:
        async with AsyncSessionLocal() as session:
            StepExecutionCRUD(session)

            # Get steps currently awaiting events
            from sqlalchemy import func, select

            from budpipeline.pipeline.models import StepExecution, StepStatus

            # Count awaiting steps
            awaiting_stmt = (
                select(func.count())
                .select_from(StepExecution)
                .where(
                    StepExecution.awaiting_event == True,  # noqa: E712
                    StepExecution.status == StepStatus.RUNNING,
                )
            )
            awaiting_result = await session.execute(awaiting_stmt)
            awaiting_count = awaiting_result.scalar() or 0

            # Count steps that are past timeout but not yet processed
            current_time = datetime.now(timezone.utc)
            overdue_stmt = (
                select(func.count())
                .select_from(StepExecution)
                .where(
                    StepExecution.awaiting_event == True,  # noqa: E712
                    StepExecution.status == StepStatus.RUNNING,
                    StepExecution.timeout_at < current_time,
                )
            )
            overdue_result = await session.execute(overdue_stmt)
            overdue_count = overdue_result.scalar() or 0

            # Get earliest timeout deadline
            earliest_stmt = select(func.min(StepExecution.timeout_at)).where(
                StepExecution.awaiting_event == True,  # noqa: E712
                StepExecution.status == StepStatus.RUNNING,
            )
            earliest_result = await session.execute(earliest_stmt)
            earliest_timeout = earliest_result.scalar()

            return {
                "awaiting_events_count": awaiting_count,
                "overdue_timeout_count": overdue_count,
                "earliest_timeout": earliest_timeout.isoformat() if earliest_timeout else None,
                "current_time": current_time.isoformat(),
                "check_interval_seconds": settings.step_timeout_check_interval,
            }

    except Exception as e:
        logger.exception(f"Error getting timeout stats: {e}")
        return {
            "error": str(e),
        }


# Module-level scheduler instance (for Dapr binding)
timeout_scheduler = type(
    "TimeoutScheduler",
    (),
    {
        "check_and_process_timeouts": staticmethod(check_and_process_timeouts),
        "get_timeout_stats": staticmethod(get_timeout_stats),
    },
)()
