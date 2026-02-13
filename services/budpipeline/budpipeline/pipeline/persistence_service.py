"""Pipeline persistence service for database operations.

This module provides the PersistenceService that replaces in-memory WorkflowStorage
with PostgreSQL database persistence (002-pipeline-event-persistence - T032).
"""

import time
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from budpipeline.commons.database import AsyncSessionLocal
from budpipeline.commons.observability import (
    get_logger,
    record_db_operation,
    record_execution_created,
)
from budpipeline.commons.resilience import (
    DatabaseRetryError,
    fallback_storage,
    with_db_retry,
)
from budpipeline.commons.sanitization import sanitize_outputs
from budpipeline.pipeline.crud import (
    OptimisticLockError,
    PipelineExecutionCRUD,
    StepExecutionCRUD,
)
from budpipeline.pipeline.models import (
    ExecutionStatus,
    PipelineExecution,
    StepExecution,
    StepStatus,
)
from budpipeline.progress.crud import ProgressEventCRUD
from budpipeline.progress.models import EventType
from budpipeline.progress.publisher import event_publisher
from budpipeline.subscriptions.crud import ExecutionSubscriptionCRUD

logger = get_logger(__name__)


class PersistenceService:
    """Service for persisting pipeline execution data to database.

    Provides resilient database operations with:
    - Circuit breaker pattern for failure detection
    - In-memory fallback when database unavailable
    - Retry with exponential backoff
    - Optimistic locking for concurrent updates
    """

    async def create_execution(
        self,
        pipeline_definition: dict[str, Any],
        initiator: str,
        callback_topics: list[str] | None = None,
        pipeline_id: UUID | None = None,
        subscriber_ids: str | None = None,
        payload_type: str | None = None,
        notification_workflow_id: str | None = None,
    ) -> tuple[UUID, int]:
        """Create a new pipeline execution in database.

        Args:
            pipeline_definition: Complete pipeline DAG definition.
            initiator: User or service that initiated execution.
            callback_topics: Optional list of callback topics for subscriptions.
            pipeline_id: Optional reference to parent pipeline definition.
            subscriber_ids: Optional user ID(s) for Novu notification delivery.
            payload_type: Optional custom payload.type for event routing.
            notification_workflow_id: Optional override for payload.workflow_id in notifications.

        Returns:
            Tuple of (execution_id, version).
        """
        start_time = time.time()

        try:
            async with AsyncSessionLocal() as session:
                # Create execution
                execution_crud = PipelineExecutionCRUD(session)
                execution = await with_db_retry(
                    execution_crud.create,
                    "create_execution",
                    pipeline_definition=pipeline_definition,
                    initiator=initiator,
                    pipeline_id=pipeline_id,
                    subscriber_ids=subscriber_ids,
                    payload_type=payload_type,
                    notification_workflow_id=notification_workflow_id,
                )

                # Create subscriptions if callback topics provided
                if callback_topics:
                    subscription_crud = ExecutionSubscriptionCRUD(session)
                    await subscription_crud.create_batch(
                        execution_id=execution.id,
                        callback_topics=callback_topics,
                    )

                await session.commit()

                record_execution_created(initiator)
                record_db_operation("create", "execution", time.time() - start_time)

                logger.info(
                    "Created pipeline execution",
                    execution_id=str(execution.id),
                    initiator=initiator,
                    callback_topics=callback_topics,
                )

                return execution.id, execution.version

        except DatabaseRetryError:
            # Fallback to in-memory storage
            import uuid

            exec_id = uuid.uuid4()
            fallback_data = {
                "id": str(exec_id),
                "pipeline_definition": pipeline_definition,
                "initiator": initiator,
                "status": ExecutionStatus.PENDING.value,
                "progress_percentage": "0.00",
                "version": 1,
                "created_at": datetime.utcnow().isoformat(),
            }
            fallback_storage.save_execution(exec_id, fallback_data)
            logger.warning(
                "Using fallback storage for execution",
                execution_id=str(exec_id),
            )
            return exec_id, 1

    async def create_steps_for_execution(
        self,
        execution_id: UUID,
        steps: list[dict[str, Any]],
    ) -> list[tuple[UUID, str, int]]:
        """Create step executions for a pipeline execution.

        Args:
            execution_id: Parent execution UUID.
            steps: List of step definitions with step_id, step_name, sequence_number.

        Returns:
            List of tuples (step_uuid, step_id, version).
        """
        start_time = time.time()

        try:
            async with AsyncSessionLocal() as session:
                step_crud = StepExecutionCRUD(session)
                created_steps = await with_db_retry(
                    step_crud.create_batch_for_execution,
                    "create_steps",
                    execution_id=execution_id,
                    steps=steps,
                )

                await session.commit()
                record_db_operation("create_batch", "step_execution", time.time() - start_time)

                return [(s.id, s.step_id, s.version) for s in created_steps]

        except DatabaseRetryError:
            # Fallback: store steps in memory
            import uuid

            result = []
            for step_data in steps:
                step_uuid = uuid.uuid4()
                fallback_data = {
                    "id": str(step_uuid),
                    "execution_id": str(execution_id),
                    "step_id": step_data["step_id"],
                    "step_name": step_data["step_name"],
                    "sequence_number": step_data["sequence_number"],
                    "status": StepStatus.PENDING.value,
                    "version": 1,
                }
                fallback_storage.save_step(execution_id, step_uuid, fallback_data)
                result.append((step_uuid, step_data["step_id"], 1))
            return result

    async def get_execution(
        self,
        execution_id: UUID,
        include_steps: bool = False,
        include_events: bool = False,
    ) -> PipelineExecution | None:
        """Get pipeline execution by ID.

        Args:
            execution_id: Execution UUID.
            include_steps: Include step executions.
            include_events: Include progress events.

        Returns:
            PipelineExecution instance or None.
        """
        start_time = time.time()

        # Check fallback first if active
        if fallback_storage.is_active():
            fallback_data = fallback_storage.get_execution(execution_id)
            if fallback_data:
                logger.debug("Serving execution from fallback", execution_id=str(execution_id))
                # Return a dict-like object for compatibility
                return self._dict_to_execution(fallback_data)

        try:
            async with AsyncSessionLocal() as session:
                crud = PipelineExecutionCRUD(session)
                execution = await with_db_retry(
                    crud.get_by_id,
                    "get_execution",
                    execution_id=execution_id,
                    include_steps=include_steps,
                    include_events=include_events,
                )

                record_db_operation("get", "execution", time.time() - start_time)
                return execution

        except DatabaseRetryError:
            # Try fallback
            fallback_data = fallback_storage.get_execution(execution_id)
            if fallback_data:
                return self._dict_to_execution(fallback_data)
            return None

    async def update_execution_status(
        self,
        execution_id: UUID,
        expected_version: int,
        status: ExecutionStatus,
        progress_percentage: Decimal | None = None,
        start_time_value: datetime | None = None,
        end_time_value: datetime | None = None,
        final_outputs: dict[str, Any] | None = None,
        error_info: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        subscriber_ids: str | None = None,
        payload_type: str | None = None,
        notification_workflow_id: str | None = None,
    ) -> tuple[bool, int]:
        """Update execution status with optimistic locking.

        Also publishes workflow events to callback topics (T048).

        Args:
            execution_id: Execution UUID.
            expected_version: Expected version for optimistic lock.
            status: New execution status.
            progress_percentage: Updated progress.
            start_time_value: Execution start time.
            end_time_value: Execution end time.
            final_outputs: Final outputs (will be sanitized).
            error_info: Error details.
            correlation_id: Optional correlation ID for event tracing.
            subscriber_ids: Optional user ID(s) for Novu notification delivery.
            payload_type: Optional custom payload.type for event routing.
            notification_workflow_id: Optional override for payload.workflow_id in notifications.

        Returns:
            Tuple of (success, new_version).
        """
        start_time = time.time()

        # Sanitize outputs before persisting
        sanitized_outputs = sanitize_outputs(final_outputs) if final_outputs else None

        try:
            async with AsyncSessionLocal() as session:
                crud = PipelineExecutionCRUD(session)

                try:
                    execution = await crud.update_status(
                        execution_id=execution_id,
                        expected_version=expected_version,
                        status=status,
                        progress_percentage=progress_percentage,
                        start_time=start_time_value,
                        end_time=end_time_value,
                        final_outputs=sanitized_outputs,
                        error_info=error_info,
                    )
                    await session.commit()

                    record_db_operation("update", "execution", time.time() - start_time)

                    logger.debug(
                        "Updated execution status",
                        execution_id=str(execution_id),
                        status=status.value,
                        new_version=execution.version,
                    )

                    # Publish events to callback topics (T048)
                    await self._publish_execution_event(
                        execution_id=execution_id,
                        status=status,
                        progress_percentage=progress_percentage,
                        final_outputs=final_outputs,
                        error_info=error_info,
                        correlation_id=correlation_id,
                        subscriber_ids=subscriber_ids,
                        payload_type=payload_type,
                        notification_workflow_id=notification_workflow_id,
                    )

                    return True, execution.version

                except OptimisticLockError:
                    logger.warning(
                        "Optimistic lock conflict on execution",
                        execution_id=str(execution_id),
                        expected_version=expected_version,
                    )
                    return False, expected_version

        except DatabaseRetryError:
            # Update fallback storage
            fallback_data = fallback_storage.get_execution(execution_id)
            if fallback_data:
                fallback_data["status"] = status.value
                if progress_percentage is not None:
                    fallback_data["progress_percentage"] = str(progress_percentage)
                fallback_storage.save_execution(execution_id, fallback_data)
                return True, expected_version + 1
            return False, expected_version

    async def _publish_execution_event(
        self,
        execution_id: UUID,
        status: ExecutionStatus,
        progress_percentage: Decimal | None = None,
        final_outputs: dict[str, Any] | None = None,
        error_info: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        subscriber_ids: str | None = None,
        payload_type: str | None = None,
        notification_workflow_id: str | None = None,
    ) -> None:
        """Publish execution status events to callback topics.

        Non-blocking - uses async fire-and-forget pattern.
        """
        try:
            if status == ExecutionStatus.COMPLETED:
                await event_publisher.publish_workflow_completed(
                    execution_id=execution_id,
                    success=True,
                    final_outputs=final_outputs,
                    correlation_id=correlation_id,
                    subscriber_ids=subscriber_ids,
                    payload_type=payload_type,
                    notification_workflow_id=notification_workflow_id,
                )
            elif status == ExecutionStatus.FAILED:
                message = error_info.get("message") if error_info else None
                await event_publisher.publish_workflow_completed(
                    execution_id=execution_id,
                    success=False,
                    final_message=message,
                    correlation_id=correlation_id,
                    subscriber_ids=subscriber_ids,
                    payload_type=payload_type,
                    notification_workflow_id=notification_workflow_id,
                )
            elif status == ExecutionStatus.RUNNING and progress_percentage is not None:
                await event_publisher.publish_workflow_progress(
                    execution_id=execution_id,
                    progress_percentage=progress_percentage,
                    correlation_id=correlation_id,
                    subscriber_ids=subscriber_ids,
                    payload_type=payload_type,
                    notification_workflow_id=notification_workflow_id,
                )
        except Exception as e:
            # Non-blocking - log and continue (FR-014)
            logger.warning(
                "Failed to publish execution event",
                execution_id=str(execution_id),
                status=status.value,
                error=str(e),
            )

    async def update_step_status(
        self,
        step_uuid: UUID,
        expected_version: int,
        status: StepStatus,
        progress_percentage: Decimal | None = None,
        start_time_value: datetime | None = None,
        end_time_value: datetime | None = None,
        outputs: dict[str, Any] | None = None,
        error_message: str | None = None,
        increment_retry: bool = False,
        execution_id: UUID | None = None,
        step_id: str | None = None,
        step_name: str | None = None,
        sequence_number: int | None = None,
        correlation_id: str | None = None,
        subscriber_ids: str | None = None,
        payload_type: str | None = None,
        notification_workflow_id: str | None = None,
    ) -> tuple[bool, int]:
        """Update step execution status with optimistic locking.

        Also publishes step events to callback topics (T048).

        Args:
            step_uuid: Step execution UUID.
            expected_version: Expected version for optimistic lock.
            status: New step status.
            progress_percentage: Updated progress.
            start_time_value: Step start time.
            end_time_value: Step end time.
            outputs: Step outputs (will be sanitized).
            error_message: Error description.
            increment_retry: Increment retry count.
            execution_id: Parent execution UUID for event publishing.
            step_id: Step identifier for event publishing.
            step_name: Step name for event publishing.
            sequence_number: Step sequence number for event publishing.
            correlation_id: Optional correlation ID for event tracing.
            subscriber_ids: Optional user ID(s) for Novu notification delivery.
            payload_type: Optional custom payload.type for event routing.
            notification_workflow_id: Optional override for payload.workflow_id in notifications.

        Returns:
            Tuple of (success, new_version).
        """
        start_time = time.time()

        # Sanitize outputs before persisting
        sanitized_outputs = sanitize_outputs(outputs) if outputs else None

        try:
            async with AsyncSessionLocal() as session:
                crud = StepExecutionCRUD(session)

                try:
                    step = await crud.update_status(
                        step_uuid=step_uuid,
                        expected_version=expected_version,
                        status=status,
                        progress_percentage=progress_percentage,
                        start_time=start_time_value,
                        end_time=end_time_value,
                        outputs=sanitized_outputs,
                        error_message=error_message,
                        increment_retry=increment_retry,
                    )
                    await session.commit()

                    record_db_operation("update", "step_execution", time.time() - start_time)

                    # Publish step events to callback topics (T048)
                    if execution_id and step_id and step_name:
                        await self._publish_step_event(
                            execution_id=execution_id,
                            step_id=step_id,
                            step_name=step_name,
                            status=status,
                            progress_percentage=progress_percentage or Decimal("0.00"),
                            sequence_number=sequence_number or 0,
                            error_message=error_message,
                            correlation_id=correlation_id,
                            subscriber_ids=subscriber_ids,
                            payload_type=payload_type,
                            notification_workflow_id=notification_workflow_id,
                        )

                    return True, step.version

                except OptimisticLockError:
                    logger.warning(
                        "Optimistic lock conflict on step",
                        step_uuid=str(step_uuid),
                        expected_version=expected_version,
                    )
                    return False, expected_version

        except DatabaseRetryError:
            # Fallback doesn't track step versions, just return success
            return True, expected_version + 1

    async def mark_step_awaiting_event(
        self,
        step_uuid: UUID,
        expected_version: int,
        external_workflow_id: str,
        handler_type: str,
        timeout_at: datetime,
        outputs: dict[str, Any] | None = None,
    ) -> tuple[bool, int]:
        """Mark a step as awaiting an external event for completion.

        This is used for event-driven step completion (event-driven-completion architecture).
        The step remains in RUNNING status but with awaiting_event=True.

        Args:
            step_uuid: Step execution UUID.
            expected_version: Expected version for optimistic lock.
            external_workflow_id: External workflow ID for event correlation.
            handler_type: Handler type for event routing (e.g., 'internal.model.add').
            timeout_at: When this step should timeout if event not received.
            outputs: Optional partial outputs from the handler.

        Returns:
            Tuple of (success, new_version).
        """
        start_time = time.time()

        # Sanitize outputs before persisting
        sanitized_outputs = sanitize_outputs(outputs) if outputs else None

        try:
            async with AsyncSessionLocal() as session:
                crud = StepExecutionCRUD(session)

                try:
                    step = await crud.mark_step_awaiting_event(
                        step_uuid=step_uuid,
                        expected_version=expected_version,
                        external_workflow_id=external_workflow_id,
                        handler_type=handler_type,
                        timeout_at=timeout_at,
                    )

                    # Also update outputs if provided
                    if sanitized_outputs:
                        step.outputs = sanitized_outputs

                    await session.commit()

                    record_db_operation("update", "step_awaiting_event", time.time() - start_time)

                    logger.info(
                        "Marked step as awaiting event",
                        step_uuid=str(step_uuid),
                        external_workflow_id=external_workflow_id,
                        handler_type=handler_type,
                        timeout_at=timeout_at.isoformat(),
                    )

                    return True, step.version

                except OptimisticLockError:
                    logger.warning(
                        "Optimistic lock conflict marking step awaiting event",
                        step_uuid=str(step_uuid),
                        expected_version=expected_version,
                    )
                    return False, expected_version

        except DatabaseRetryError:
            # Fallback storage doesn't support event-driven tracking
            logger.error(
                "Cannot mark step awaiting event in fallback storage",
                step_uuid=str(step_uuid),
            )
            return False, expected_version

    async def _publish_step_event(
        self,
        execution_id: UUID,
        step_id: str,
        step_name: str,
        status: StepStatus,
        progress_percentage: Decimal,
        sequence_number: int,
        error_message: str | None = None,
        correlation_id: str | None = None,
        subscriber_ids: str | None = None,
        payload_type: str | None = None,
        notification_workflow_id: str | None = None,
    ) -> None:
        """Publish step status events to callback topics.

        Non-blocking - uses async fire-and-forget pattern.
        """
        try:
            if status == StepStatus.RUNNING:
                await event_publisher.publish_step_started(
                    execution_id=execution_id,
                    step_id=step_id,
                    step_name=step_name,
                    sequence_number=sequence_number,
                    correlation_id=correlation_id,
                    subscriber_ids=subscriber_ids,
                    payload_type=payload_type,
                    notification_workflow_id=notification_workflow_id,
                )
            elif status == StepStatus.COMPLETED:
                await event_publisher.publish_step_completed(
                    execution_id=execution_id,
                    step_id=step_id,
                    step_name=step_name,
                    progress_percentage=progress_percentage,
                    correlation_id=correlation_id,
                    subscriber_ids=subscriber_ids,
                    payload_type=payload_type,
                    notification_workflow_id=notification_workflow_id,
                )
            elif status == StepStatus.FAILED:
                await event_publisher.publish_step_failed(
                    execution_id=execution_id,
                    step_id=step_id,
                    step_name=step_name,
                    error_message=error_message or "Step failed",
                    correlation_id=correlation_id,
                    subscriber_ids=subscriber_ids,
                    payload_type=payload_type,
                    notification_workflow_id=notification_workflow_id,
                )
        except Exception as e:
            # Non-blocking - log and continue (FR-014)
            logger.warning(
                "Failed to publish step event",
                execution_id=str(execution_id),
                step_id=step_id,
                status=status.value,
                error=str(e),
            )

    async def record_progress_event(
        self,
        execution_id: UUID,
        event_type: EventType,
        progress_percentage: Decimal,
        eta_seconds: int | None = None,
        current_step_desc: str | None = None,
        event_details: dict[str, Any] | None = None,
    ) -> UUID | None:
        """Record a progress event.

        Args:
            execution_id: Execution UUID.
            event_type: Type of progress event.
            progress_percentage: Current progress.
            eta_seconds: Estimated time remaining.
            current_step_desc: Description of current step.
            event_details: Additional event metadata.

        Returns:
            Event UUID or None if failed.
        """
        try:
            async with AsyncSessionLocal() as session:
                crud = ProgressEventCRUD(session)
                event = await crud.create(
                    execution_id=execution_id,
                    event_type=event_type,
                    progress_percentage=progress_percentage,
                    eta_seconds=eta_seconds,
                    current_step_desc=current_step_desc,
                    event_details=event_details,
                )
                await session.commit()
                return event.id

        except Exception as e:
            logger.warning(
                "Failed to record progress event",
                execution_id=str(execution_id),
                error=str(e),
            )
            # Store in fallback
            fallback_storage.save_event(
                execution_id,
                {
                    "event_type": event_type.value,
                    "progress_percentage": str(progress_percentage),
                    "eta_seconds": eta_seconds,
                    "current_step_desc": current_step_desc,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
            return None

    async def get_execution_steps(
        self,
        execution_id: UUID,
    ) -> list[StepExecution]:
        """Get all steps for an execution.

        Args:
            execution_id: Execution UUID.

        Returns:
            List of StepExecution instances.
        """
        try:
            async with AsyncSessionLocal() as session:
                crud = StepExecutionCRUD(session)
                return await crud.get_by_execution_id(execution_id)

        except DatabaseRetryError:
            # Return from fallback
            fallback_steps = fallback_storage.get_steps(execution_id)
            return [self._dict_to_step(s) for s in fallback_steps]

    async def list_executions(
        self,
        page: int = 1,
        page_size: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        status: ExecutionStatus | None = None,
        initiator: str | None = None,
        pipeline_id: UUID | None = None,
    ) -> tuple[list[PipelineExecution], int]:
        """List executions with filtering and pagination.

        Args:
            page: Page number (1-indexed).
            page_size: Items per page.
            start_date: Filter by created_at >= start_date.
            end_date: Filter by created_at <= end_date.
            status: Filter by status.
            initiator: Filter by initiator.
            pipeline_id: Filter by pipeline definition ID.

        Returns:
            Tuple of (list of executions, total count).
        """
        start_time = time.time()

        try:
            async with AsyncSessionLocal() as session:
                crud = PipelineExecutionCRUD(session)
                executions, total = await crud.list_paginated(
                    page=page,
                    page_size=page_size,
                    start_date=start_date,
                    end_date=end_date,
                    status=status,
                    initiator=initiator,
                    pipeline_id=pipeline_id,
                )

                record_db_operation("list", "execution", time.time() - start_time)
                return executions, total

        except DatabaseRetryError:
            # Return empty list from fallback (limited capability)
            return [], 0

    def _dict_to_execution(self, data: dict[str, Any]) -> PipelineExecution:
        """Convert dictionary to PipelineExecution-like object.

        Used for fallback storage compatibility.
        """
        # Create a minimal mock object for API compatibility
        from uuid import UUID as UUIDType

        exec_obj = PipelineExecution()
        exec_obj.id = UUIDType(data["id"]) if isinstance(data["id"], str) else data["id"]
        exec_obj.version = data.get("version", 1)
        exec_obj.pipeline_definition = data.get("pipeline_definition", {})
        exec_obj.initiator = data.get("initiator", "unknown")
        exec_obj.status = ExecutionStatus(data.get("status", "PENDING"))
        exec_obj.progress_percentage = Decimal(data.get("progress_percentage", "0.00"))
        exec_obj.created_at = datetime.fromisoformat(
            data.get("created_at", datetime.utcnow().isoformat())
        )
        exec_obj.updated_at = datetime.utcnow()
        return exec_obj

    def _dict_to_step(self, data: dict[str, Any]) -> StepExecution:
        """Convert dictionary to StepExecution-like object."""
        from uuid import UUID as UUIDType

        step_obj = StepExecution()
        step_obj.id = UUIDType(data["id"]) if isinstance(data["id"], str) else data["id"]
        step_obj.execution_id = (
            UUIDType(data["execution_id"])
            if isinstance(data["execution_id"], str)
            else data["execution_id"]
        )
        step_obj.version = data.get("version", 1)
        step_obj.step_id = data.get("step_id", "")
        step_obj.step_name = data.get("step_name", "")
        step_obj.status = StepStatus(data.get("status", "PENDING"))
        step_obj.sequence_number = data.get("sequence_number", 1)
        step_obj.progress_percentage = Decimal(data.get("progress_percentage", "0.00"))
        step_obj.retry_count = data.get("retry_count", 0)
        step_obj.created_at = datetime.utcnow()
        step_obj.updated_at = datetime.utcnow()
        return step_obj


# Global persistence service instance
persistence_service = PersistenceService()
