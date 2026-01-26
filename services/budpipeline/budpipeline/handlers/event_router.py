"""Event Router - routes incoming events to the appropriate action executors.

This module provides event routing for the event-driven completion architecture.
When an event arrives, it extracts the workflow_id, finds the step waiting for it,
and routes the event to the action executor's on_event() method.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

# Use new action architecture
from budpipeline.actions.base import EventAction, EventContext, EventResult, action_registry
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

    # Get the action executor for this step
    action_type = step.handler_type
    if not action_type:
        error_msg = f"Step {step.id} has no handler_type/action_type set"
        logger.error(error_msg)
        return EventRouteResult(
            routed=False,
            step_execution_id=step.id,
            error=error_msg,
        )

    if not action_registry.has(action_type):
        error_msg = f"Action '{action_type}' not found in registry"
        logger.error(error_msg)
        return EventRouteResult(
            routed=False,
            step_execution_id=step.id,
            error=error_msg,
        )

    executor = action_registry.get_executor(action_type)

    # Create event context for the executor
    context = EventContext(
        step_execution_id=step.id,
        execution_id=step.execution_id,
        external_workflow_id=workflow_id,
        event_type=event_type,
        event_data=event_data,
        step_outputs=step.outputs or {},
    )

    # Call the executor's on_event method
    try:
        result: EventResult = await executor.on_event(context)
    except NotImplementedError:
        # Action doesn't support events - ignore
        logger.warning(f"Action {action_type} does not implement on_event(), ignoring event")
        return EventRouteResult(
            routed=True,
            step_execution_id=step.id,
            action_taken=EventAction.IGNORE,
            error=f"Action {action_type} does not support event handling",
        )
    except Exception as e:
        error_msg = f"Executor on_event() raised exception: {e}"
        logger.exception(error_msg)
        return EventRouteResult(
            routed=True,
            step_execution_id=step.id,
            action_taken=EventAction.IGNORE,
            error=error_msg,
        )

    logger.info(f"Action {action_type} returned action={result.action} for step {step.id}")

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
        logger.debug(f"Handler {action_type} ignored event for step {step.id}")
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
    for an event, OR when a wait_until step's scheduled wake time has arrived.

    For wait_until steps: This is a successful wake-up (COMPLETED status).
    For other steps: This is a timeout failure (TIMEOUT status).

    Args:
        session: Database session.
        step: The step execution that has timed out.

    Returns:
        EventRouteResult indicating the timeout was processed.
    """
    step_crud = StepExecutionCRUD(session)

    try:
        # Check if this is a wait_until step (scheduled wake-up, not a timeout)
        is_wait_until = step.handler_type == "wait_until"

        if is_wait_until:
            # Wait completed successfully - this is a wake-up, not a timeout
            final_status = StepStatus.COMPLETED
            step_outputs = step.outputs if step.outputs else {}
            outputs = {
                "waited": True,
                "scheduled_wake_time": step.timeout_at.isoformat() if step.timeout_at else None,
                "actual_wake_time": datetime.utcnow().isoformat(),
                "wait_duration_seconds": step_outputs.get("wait_duration_seconds"),
            }
            error_message = None

            logger.info(f"Wait-until step {step.id} woke up as scheduled")
        else:
            # Regular timeout (failure case)
            final_status = StepStatus.TIMEOUT
            outputs = {"timeout": True}
            error_message = (
                f"Step timed out waiting for event from workflow {step.external_workflow_id}"
            )

            logger.warning(
                f"Step {step.id} timed out waiting for event from workflow "
                f"{step.external_workflow_id}"
            )

        await step_crud.complete_step_from_event(
            step_uuid=step.id,
            expected_version=step.version,
            status=final_status,
            outputs=outputs,
            error_message=error_message,
        )

        return EventRouteResult(
            routed=True,
            step_execution_id=step.id,
            action_taken=EventAction.COMPLETE,
            step_completed=True,
            final_status=final_status,
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

        # Trigger execution of pending steps that have their dependencies met
        if pending_count > 0:
            logger.info(
                f"Execution {execution_id} has {pending_count} pending steps. "
                f"Checking if any can be started now."
            )
            await _continue_pipeline_execution(
                session=session,
                execution_id=execution_id,
                all_steps=all_steps,
            )
        else:
            logger.debug(
                f"Execution {execution_id} continuing: {pending_count} pending, "
                f"{running_count} running"
            )


async def _check_and_finalize_execution(
    session: AsyncSession,
    execution_id: UUID,
    all_steps: list[StepExecution],
) -> None:
    """Check if execution is complete and finalize if needed.

    Args:
        session: Database session.
        execution_id: The execution to check.
        all_steps: All step executions for this execution.
    """
    from decimal import Decimal

    from budpipeline.pipeline.crud import PipelineExecutionCRUD
    from budpipeline.pipeline.models import ExecutionStatus

    # Refresh step statuses from database
    step_crud = StepExecutionCRUD(session)
    fresh_steps = await step_crud.get_by_execution_id(execution_id)

    # Count step statuses
    completed_count = 0
    failed_count = 0
    pending_count = 0
    running_count = 0

    for s in fresh_steps:
        if s.status == StepStatus.COMPLETED:
            completed_count += 1
        elif s.status == StepStatus.FAILED or s.status == StepStatus.TIMEOUT:
            failed_count += 1
        elif s.status == StepStatus.PENDING:
            pending_count += 1
        elif s.status == StepStatus.RUNNING:
            running_count += 1

    total_steps = len(fresh_steps)
    all_done = pending_count == 0 and running_count == 0

    if not all_done:
        logger.debug(
            f"Execution {execution_id} not yet complete: "
            f"completed={completed_count}, failed={failed_count}, "
            f"pending={pending_count}, running={running_count}"
        )
        return

    # Execution is complete - finalize it
    execution_crud = PipelineExecutionCRUD(session)
    execution = await execution_crud.get_by_id(execution_id)

    if execution is None:
        logger.warning(f"Execution {execution_id} not found for finalization")
        return

    if execution.status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED):
        logger.debug(f"Execution {execution_id} already finalized with status {execution.status}")
        return

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
        logger.info(f"Execution {execution_id} COMPLETED: all {completed_count} steps completed")

        # Collect final outputs from all completed steps
        final_outputs = {}
        for s in fresh_steps:
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


async def _continue_pipeline_execution(
    session: AsyncSession,
    execution_id: UUID,
    all_steps: list[StepExecution],
) -> None:
    """Continue executing pending steps after an event-driven step completes.

    This function finds pending steps whose dependencies are all satisfied
    (completed or skipped) and executes them.

    Args:
        session: Database session.
        execution_id: The execution to continue.
        all_steps: All step executions for this execution.
    """
    from budpipeline.actions.base import ActionContext, action_registry
    from budpipeline.commons.config import settings
    from budpipeline.pipeline.crud import PipelineExecutionCRUD

    # Build set of completed step IDs and collect their outputs
    completed_step_ids: set[str] = set()
    step_outputs: dict[str, dict[str, Any]] = {}

    for s in all_steps:
        if s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED):
            completed_step_ids.add(s.step_id)
            if s.outputs:
                step_outputs[s.step_id] = s.outputs

    # Get execution to retrieve DAG and params
    execution_crud = PipelineExecutionCRUD(session)
    execution = await execution_crud.get_by_id(execution_id)
    if not execution:
        logger.warning(f"Execution {execution_id} not found for continuation")
        return

    # Get DAG from pipeline_definition (which contains the 'dag' field with steps)
    pipeline_def = execution.pipeline_definition or {}
    dag_dict = pipeline_def.get("dag", {})
    dag_steps = dag_dict.get("steps", [])
    workflow_params = pipeline_def.get("params", {}) or {}

    # Build dependency map from DAG definition
    step_deps: dict[str, list[str]] = {}
    for dag_step in dag_steps:
        step_id = dag_step.get("id", "")
        depends_on = dag_step.get("depends_on", [])
        step_deps[step_id] = depends_on

    # Find pending steps whose dependencies are all completed
    ready_steps: list[StepExecution] = []
    for s in all_steps:
        if s.status != StepStatus.PENDING:
            continue

        deps = step_deps.get(s.step_id, [])
        deps_satisfied = all(dep_id in completed_step_ids for dep_id in deps)

        if deps_satisfied:
            ready_steps.append(s)

    if not ready_steps:
        logger.debug(f"No pending steps ready to execute for execution {execution_id}")
        # Check if execution should be finalized
        await _check_and_finalize_execution(session, execution_id, all_steps)
        return

    logger.info(
        f"Found {len(ready_steps)} pending steps ready to execute: "
        f"{[s.step_id for s in ready_steps]}"
    )

    step_crud = StepExecutionCRUD(session)

    # Execute each ready step
    for step_exec in ready_steps:
        step_id = step_exec.step_id

        # Refresh step from database to get latest version and status
        fresh_step = await step_crud.get_by_id(step_exec.id)
        if fresh_step is None:
            logger.warning(f"Step {step_id} no longer exists in database")
            continue

        # Check if step is still pending (may have been started by concurrent process)
        if fresh_step.status != StepStatus.PENDING:
            logger.debug(
                f"Step {step_id} is no longer pending (status={fresh_step.status}), skipping"
            )
            continue

        # Find the step definition in DAG
        dag_step = next((ds for ds in dag_steps if ds.get("id") == step_id), None)
        if not dag_step:
            logger.warning(f"Step {step_id} not found in DAG definition")
            continue

        action_type = dag_step.get("action", "")
        step_params = dag_step.get("params", {})

        if not action_registry.has(action_type):
            logger.warning(f"Action {action_type} not registered, skipping step {step_id}")
            continue

        # Mark step as RUNNING using the fresh version
        step_started_at = datetime.utcnow()
        try:
            updated_step = await step_crud.update_with_version(
                step_uuid=fresh_step.id,
                expected_version=fresh_step.version,
                status=StepStatus.RUNNING,
                start_time=step_started_at,
            )
            # Use the version from the updated step for subsequent operations
            current_version = updated_step.version
        except Exception as e:
            logger.warning(f"Failed to mark step {step_id} as RUNNING: {e}")
            continue

        # Resolve parameters
        from budpipeline.engine.param_resolver import ParamResolver

        try:
            resolved_params = ParamResolver.resolve_dict(step_params, workflow_params, step_outputs)
        except Exception as e:
            logger.warning(f"Failed to resolve params for step {step_id}: {e}")
            resolved_params = step_params

        # Get action metadata for timeout
        action_meta = action_registry.get_meta(action_type)
        timeout_seconds = action_meta.timeout_seconds if action_meta else None

        # Create ActionContext
        action_context = ActionContext(
            step_id=step_id,
            execution_id=str(execution_id),
            params=resolved_params,
            workflow_params=workflow_params,
            step_outputs=step_outputs,
            timeout_seconds=timeout_seconds,
            retry_count=0,
        )

        # Execute the action
        executor = action_registry.get_executor(action_type)
        try:
            result = await executor.execute(action_context)
        except Exception as e:
            # Step failed with exception
            logger.exception(f"Step {step_id} execution raised exception: {e}")
            await step_crud.complete_step_from_event(
                step_uuid=fresh_step.id,
                expected_version=current_version,
                status=StepStatus.FAILED,
                outputs={},
                error_message=str(e),
            )
            continue

        if result.success:
            if result.awaiting_event and result.external_workflow_id:
                # Step is awaiting an event - persist and wait
                from datetime import timedelta

                timeout_secs = result.timeout_seconds or settings.default_async_step_timeout
                timeout_at = datetime.utcnow() + timedelta(seconds=timeout_secs)

                from budpipeline.pipeline.persistence_service import persistence_service

                await persistence_service.mark_step_awaiting_event(
                    step_uuid=fresh_step.id,
                    expected_version=current_version,
                    external_workflow_id=result.external_workflow_id,
                    handler_type=action_type,
                    timeout_at=timeout_at,
                    outputs=result.outputs,
                )
                logger.info(f"Step {step_id} now awaiting event from {result.external_workflow_id}")
                # Don't continue to dependent steps - wait for event
            else:
                # Step completed synchronously
                await step_crud.complete_step_from_event(
                    step_uuid=fresh_step.id,
                    expected_version=current_version,
                    status=StepStatus.COMPLETED,
                    outputs=result.outputs,
                    error_message=None,
                )
                logger.info(f"Step {step_id} completed synchronously")

                # Commit the completion before continuing
                await session.commit()

                # Add to completed set and continue checking for more ready steps
                completed_step_ids.add(step_id)
                if result.outputs:
                    step_outputs[step_id] = result.outputs

                # Recursively continue execution for any newly ready steps
                updated_steps = await step_crud.get_by_execution_id(execution_id)
                await _continue_pipeline_execution(session, execution_id, updated_steps)
        else:
            # Step failed
            await step_crud.complete_step_from_event(
                step_uuid=fresh_step.id,
                expected_version=current_version,
                status=StepStatus.FAILED,
                outputs=result.outputs or {},
                error_message=result.error,
            )
            logger.warning(f"Step {step_id} failed: {result.error}")
