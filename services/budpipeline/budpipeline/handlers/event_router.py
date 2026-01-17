"""Event Router - routes incoming events to the appropriate handlers.

This module provides event routing for the event-driven completion architecture.
When an event arrives, it extracts the workflow_id, finds the step waiting for it,
and routes the event to the handler's on_event() method.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from budpipeline.handlers.base import EventAction, EventContext, EventHandlerResult  # noqa: F401
from budpipeline.handlers.registry import global_registry
from budpipeline.pipeline.crud import StepExecutionCRUD
from budpipeline.pipeline.models import StepExecution, StepStatus

logger = logging.getLogger(__name__)


@dataclass
class EventRouteResult:
    """Result of routing an event to a handler."""

    routed: bool
    """Whether the event was routed to a handler."""

    step_execution_id: UUID | None = None
    """Step execution that received the event."""

    action_taken: EventAction | None = None
    """Action taken by the handler."""

    step_completed: bool = False
    """Whether the step was completed (COMPLETED, FAILED, or TIMEOUT)."""

    final_status: StepStatus | None = None
    """Final status if step was completed."""

    error: str | None = None
    """Error message if routing failed."""


def extract_workflow_id(event_data: dict[str, Any]) -> str | None:
    """Extract workflow_id from event data.

    Events can have workflow_id in various locations depending on the source:
    - workflow_completed events: event_data['workflow_id']
    - budcluster notifications: event_data['payload']['workflow_id']
    - Alternative: event_data['notification_metadata']['workflow_id']
    - Deep nested: event_data['payload']['content']['result']['workflow_id']

    Args:
        event_data: The incoming event data.

    Returns:
        Extracted workflow_id or None if not found.
    """
    # Direct workflow_id field (workflow_completed events)
    workflow_id = event_data.get("workflow_id")
    if workflow_id:
        return str(workflow_id)

    # payload.workflow_id (budcluster notification events - NotificationPayload.workflow_id)
    # Use 'or {}' to handle explicitly null values
    payload = event_data.get("payload") or {}
    workflow_id = payload.get("workflow_id")
    if workflow_id:
        return str(workflow_id)

    # notification_metadata.workflow_id (some budcluster events)
    notification_metadata = event_data.get("notification_metadata") or {}
    workflow_id = notification_metadata.get("workflow_id")
    if workflow_id:
        return str(workflow_id)

    # payload.content.result.workflow_id (deeply nested in some events)
    content = payload.get("content") or {}
    result = content.get("result") or {}
    workflow_id = result.get("workflow_id")
    if workflow_id:
        return str(workflow_id)

    return None


async def route_event(
    session: AsyncSession,
    event_data: dict[str, Any],
) -> EventRouteResult:
    """Route an incoming event to the appropriate handler.

    This is the main entry point for processing events. It:
    1. Extracts the workflow_id from the event
    2. Finds the step execution waiting for that workflow_id
    3. Gets the handler for that step
    4. Calls the handler's on_event() method
    5. Updates the step status based on the result

    Args:
        session: Database session for CRUD operations.
        event_data: The incoming event data.

    Returns:
        EventRouteResult with routing outcome.
    """
    # Extract workflow_id from event
    workflow_id = extract_workflow_id(event_data)

    if not workflow_id:
        logger.debug("Event has no workflow_id, cannot route")
        return EventRouteResult(routed=False, error="No workflow_id in event")

    event_type = event_data.get("type", "unknown")
    logger.info(f"Routing event: type={event_type}, workflow_id={workflow_id}")

    # Find the step execution waiting for this workflow_id
    step_crud = StepExecutionCRUD(session)
    step = await step_crud.get_by_external_workflow_id(workflow_id)

    if step is None:
        logger.debug(
            f"No step awaiting event for workflow_id={workflow_id}, "
            "event may have already been processed or step does not exist"
        )
        return EventRouteResult(
            routed=False,
            error=f"No step awaiting event for workflow_id={workflow_id}",
        )

    logger.info(
        f"Found step {step.id} (step_id={step.step_id}) awaiting event "
        f"for workflow_id={workflow_id}, handler_type={step.handler_type}"
    )

    # Get the handler for this step
    handler_type = step.handler_type
    if not handler_type:
        error_msg = f"Step {step.id} has no handler_type set"
        logger.error(error_msg)
        return EventRouteResult(
            routed=False,
            step_execution_id=step.id,
            error=error_msg,
        )

    if not global_registry.has(handler_type):
        error_msg = f"Handler '{handler_type}' not found in registry"
        logger.error(error_msg)
        return EventRouteResult(
            routed=False,
            step_execution_id=step.id,
            error=error_msg,
        )

    handler = global_registry.get(handler_type)

    # Create event context for the handler
    context = EventContext(
        step_execution_id=str(step.id),
        execution_id=str(step.execution_id),
        external_workflow_id=workflow_id,
        event_type=event_type,
        event_data=event_data,
        step_outputs=step.outputs or {},
    )

    # Call the handler's on_event method
    try:
        result = await handler.on_event(context)
    except Exception as e:
        error_msg = f"Handler on_event() raised exception: {e}"
        logger.exception(error_msg)
        return EventRouteResult(
            routed=True,
            step_execution_id=step.id,
            action_taken=EventAction.IGNORE,
            error=error_msg,
        )

    logger.info(f"Handler {handler_type} returned action={result.action} for step {step.id}")

    # Process the handler result
    if result.action == EventAction.COMPLETE:
        # Complete the step
        final_status = result.status or StepStatus.COMPLETED

        # Merge outputs from handler result with existing step outputs
        final_outputs = step.outputs.copy() if step.outputs else {}
        if result.outputs:
            final_outputs.update(result.outputs)

        await step_crud.complete_step_from_event(
            step_uuid=step.id,
            expected_version=step.version,
            status=final_status,
            outputs=final_outputs,
            error_message=result.error,
        )

        logger.info(
            f"Step {step.id} completed via event: status={final_status}, "
            f"outputs={list(final_outputs.keys())}"
        )

        return EventRouteResult(
            routed=True,
            step_execution_id=step.id,
            action_taken=EventAction.COMPLETE,
            step_completed=True,
            final_status=final_status,
        )

    elif result.action == EventAction.UPDATE_PROGRESS:
        # Update progress but keep waiting for more events
        if result.progress is not None:
            from decimal import Decimal

            await step_crud.update_with_version(
                step_uuid=step.id,
                expected_version=step.version,
                progress_percentage=Decimal(str(result.progress)),
            )
            logger.info(f"Step {step.id} progress updated to {result.progress}%")

        return EventRouteResult(
            routed=True,
            step_execution_id=step.id,
            action_taken=EventAction.UPDATE_PROGRESS,
            step_completed=False,
        )

    else:  # EventAction.IGNORE
        logger.debug(f"Handler {handler_type} ignored event for step {step.id}")
        return EventRouteResult(
            routed=True,
            step_execution_id=step.id,
            action_taken=EventAction.IGNORE,
            step_completed=False,
        )


async def process_timeout(
    session: AsyncSession,
    step: StepExecution,
) -> EventRouteResult:
    """Process a timed-out step.

    Called by the timeout scheduler when a step has been waiting too long
    for an event.

    Args:
        session: Database session.
        step: The step execution that has timed out.

    Returns:
        EventRouteResult indicating the timeout was processed.
    """
    step_crud = StepExecutionCRUD(session)

    try:
        await step_crud.complete_step_from_event(
            step_uuid=step.id,
            expected_version=step.version,
            status=StepStatus.TIMEOUT,
            outputs={"timeout": True},
            error_message=(
                f"Step timed out waiting for event from workflow {step.external_workflow_id}"
            ),
        )

        logger.warning(
            f"Step {step.id} timed out waiting for event from workflow {step.external_workflow_id}"
        )

        return EventRouteResult(
            routed=True,
            step_execution_id=step.id,
            action_taken=EventAction.COMPLETE,
            step_completed=True,
            final_status=StepStatus.TIMEOUT,
        )

    except Exception as e:
        error_msg = f"Failed to process timeout for step {step.id}: {e}"
        logger.exception(error_msg)
        return EventRouteResult(
            routed=False,
            step_execution_id=step.id,
            error=error_msg,
        )


async def get_steps_awaiting_events(
    session: AsyncSession,
    execution_id: UUID | None = None,
) -> list[StepExecution]:
    """Get all steps currently awaiting events.

    Useful for debugging and monitoring.

    Args:
        session: Database session.
        execution_id: Optional filter by execution ID.

    Returns:
        List of steps awaiting events.
    """
    step_crud = StepExecutionCRUD(session)

    if execution_id:
        return await step_crud.get_awaiting_steps_for_execution(execution_id)

    # Get all awaiting steps (query by status and awaiting_event flag)
    from sqlalchemy import select

    from budpipeline.pipeline.models import StepExecution

    stmt = select(StepExecution).where(
        StepExecution.awaiting_event == True,  # noqa: E712
        StepExecution.status == StepStatus.RUNNING,
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def trigger_pipeline_continuation(
    session: AsyncSession,
    step_execution_id: UUID | None,
) -> None:
    """Trigger continuation of a pipeline after a step completes via event.

    After an event-driven step completes (via on_event()), this function
    checks if there are more steps to execute and triggers the next ones.

    For MVP: This updates the execution status if all steps are complete.
    Full implementation would continue executing dependent steps.

    Args:
        session: Database session.
        step_execution_id: The step execution ID that just completed.
    """
    if step_execution_id is None:
        logger.warning("Cannot continue pipeline: no step_execution_id provided")
        return

    # Get the step to find its execution
    step_crud = StepExecutionCRUD(session)
    step = await step_crud.get_by_id(step_execution_id)

    if step is None:
        logger.warning(f"Step {step_execution_id} not found for continuation")
        return

    execution_id = step.execution_id

    # Get all steps for this execution
    all_steps = await step_crud.get_by_execution_id(execution_id)

    # Check completion status
    completed_count = 0
    failed_count = 0
    pending_count = 0
    running_count = 0

    for s in all_steps:
        if s.status == StepStatus.COMPLETED:
            completed_count += 1
        elif s.status == StepStatus.FAILED or s.status == StepStatus.TIMEOUT:
            failed_count += 1
        elif s.status == StepStatus.PENDING:
            pending_count += 1
        elif s.status == StepStatus.RUNNING:
            running_count += 1
        # SKIPPED steps don't count toward pending

    total_steps = len(all_steps)

    logger.info(
        f"Execution {execution_id} progress: "
        f"completed={completed_count}, failed={failed_count}, "
        f"pending={pending_count}, running={running_count}, total={total_steps}"
    )

    # Update execution status based on step completion
    from budpipeline.pipeline.crud import PipelineExecutionCRUD
    from budpipeline.pipeline.models import ExecutionStatus

    execution_crud = PipelineExecutionCRUD(session)
    execution = await execution_crud.get_by_id(execution_id)

    if execution is None:
        logger.warning(f"Execution {execution_id} not found for continuation")
        return

    # Check if execution is done
    all_done = pending_count == 0 and running_count == 0

    if all_done:
        from decimal import Decimal

        if failed_count > 0:
            # Execution failed
            final_status = ExecutionStatus.FAILED
            logger.info(
                f"Execution {execution_id} FAILED: {failed_count} steps failed out of {total_steps}"
            )
            await execution_crud.update_status(
                execution_id=execution_id,
                expected_version=execution.version,
                status=final_status,
                end_time=datetime.utcnow(),
                error_info={"failed_steps": failed_count, "total_steps": total_steps},
            )
        else:
            # Execution completed successfully
            final_status = ExecutionStatus.COMPLETED
            logger.info(
                f"Execution {execution_id} COMPLETED: all {completed_count} steps completed"
            )

            # Collect final outputs from all completed steps
            final_outputs = {}
            for s in all_steps:
                if s.status == StepStatus.COMPLETED and s.outputs:
                    final_outputs[s.step_id] = s.outputs

            await execution_crud.update_status(
                execution_id=execution_id,
                expected_version=execution.version,
                status=final_status,
                progress_percentage=Decimal("100.00"),
                end_time=datetime.utcnow(),
                final_outputs=final_outputs,
            )
    else:
        # Still running - update progress percentage
        from decimal import Decimal

        if total_steps > 0:
            progress = Decimal(str((completed_count / total_steps) * 100))
            await execution_crud.update_with_version(
                execution_id=execution_id,
                expected_version=execution.version,
                progress_percentage=progress.quantize(Decimal("0.01")),
            )

        # TODO: In full implementation, we would trigger execution
        # of the next pending steps that have their dependencies met.
        # For MVP, steps are executed sequentially, so event-driven
        # steps are the leaf nodes and just need status updates.
        logger.debug(
            f"Execution {execution_id} continuing: {pending_count} pending, {running_count} running"
        )
