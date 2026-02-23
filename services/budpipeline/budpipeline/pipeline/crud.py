"""CRUD operations for pipeline and step executions.

This module provides database operations for PipelineExecution and StepExecution
with optimistic locking for concurrent update handling
(002-pipeline-event-persistence - T012, T013).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from budpipeline.pipeline.models import (
    ExecutionStatus,
    PipelineDefinition,
    PipelineExecution,
    PipelineStatus,
    StepExecution,
    StepStatus,
)


class OptimisticLockError(Exception):
    """Raised when an optimistic lock conflict is detected."""

    def __init__(self, entity_type: str, entity_id: UUID, expected_version: int) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.expected_version = expected_version
        super().__init__(f"{entity_type} {entity_id} version conflict: expected {expected_version}")


class PipelineDefinitionCRUD:
    """CRUD operations for PipelineDefinition with optimistic locking."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        name: str,
        dag_definition: dict[str, Any],
        created_by: str,
        description: str | None = None,
        icon: str | None = None,
        status: PipelineStatus = PipelineStatus.DRAFT,
        user_id: UUID | None = None,
        system_owned: bool = False,
    ) -> PipelineDefinition:
        """Create a new pipeline definition.

        Args:
            name: Human-readable pipeline name.
            dag_definition: Complete pipeline DAG definition.
            created_by: User or service that created the pipeline.
            description: Optional pipeline description.
            icon: Optional icon/emoji for UI representation.
            status: Initial pipeline status (default: draft).
            user_id: UUID of the owning user (None for system/anonymous pipelines).
            system_owned: True if this is a system-owned pipeline visible to all users.

        Returns:
            Created PipelineDefinition instance.
        """
        # Calculate step count from DAG
        steps = dag_definition.get("steps", [])
        step_count = len(steps) if isinstance(steps, list) else 0

        definition = PipelineDefinition(
            name=name,
            description=description,
            icon=icon,
            dag_definition=dag_definition,
            status=status,
            step_count=step_count,
            created_by=created_by,
            user_id=user_id,
            system_owned=system_owned,
        )
        self.session.add(definition)
        await self.session.flush()
        await self.session.refresh(definition)
        return definition

    async def get_by_id(
        self,
        definition_id: UUID,
        include_executions: bool = False,
    ) -> PipelineDefinition | None:
        """Get pipeline definition by ID with optional relationships.

        Args:
            definition_id: Pipeline definition UUID.
            include_executions: Include related executions.

        Returns:
            PipelineDefinition instance or None if not found.
        """
        stmt = select(PipelineDefinition).where(PipelineDefinition.id == definition_id)

        if include_executions:
            stmt = stmt.options(selectinload(PipelineDefinition.executions))

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(
        self,
        status: PipelineStatus | None = None,
        created_by: str | None = None,
        user_id: UUID | None = None,
        include_system: bool = False,
    ) -> list[PipelineDefinition]:
        """List all pipeline definitions with optional filtering.

        Args:
            status: Filter by pipeline status.
            created_by: Filter by creator.
            user_id: Filter by user_id (returns only pipelines owned by this user).
            include_system: If True, also include system-owned pipelines when filtering by user_id.

        Returns:
            List of PipelineDefinition instances.
        """
        stmt = select(PipelineDefinition)

        if status is not None:
            stmt = stmt.where(PipelineDefinition.status == status)
        if created_by is not None:
            stmt = stmt.where(PipelineDefinition.created_by == created_by)

        # User isolation filter
        if user_id is not None:
            if include_system:
                # User's own pipelines OR system-owned pipelines
                from sqlalchemy import or_

                stmt = stmt.where(
                    or_(
                        PipelineDefinition.user_id == user_id,
                        PipelineDefinition.system_owned == True,  # noqa: E712
                    )
                )
            else:
                # Only user's own pipelines
                stmt = stmt.where(PipelineDefinition.user_id == user_id)

        stmt = stmt.order_by(PipelineDefinition.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id_for_user(
        self,
        definition_id: UUID,
        user_id: UUID | None,
        include_executions: bool = False,
    ) -> PipelineDefinition | None:
        """Get pipeline definition by ID with user permission check.

        Returns the pipeline if:
        - It belongs to the specified user, OR
        - It is a system-owned pipeline, OR
        - user_id is None (system/admin context)

        Args:
            definition_id: Pipeline definition UUID.
            user_id: User UUID to check ownership. None means system/admin access.
            include_executions: Include related executions.

        Returns:
            PipelineDefinition instance or None if not found or not authorized.
        """
        stmt = select(PipelineDefinition).where(PipelineDefinition.id == definition_id)

        if include_executions:
            stmt = stmt.options(selectinload(PipelineDefinition.executions))

        result = await self.session.execute(stmt)
        definition = result.scalar_one_or_none()

        if definition is None:
            return None

        # Check permission
        if user_id is None:
            # System/admin access - can see everything
            return definition

        if definition.system_owned:
            # System-owned pipelines are visible to everyone
            return definition

        if definition.user_id == user_id:
            # User owns this pipeline
            return definition

        # User doesn't have permission
        return None

    async def update_with_version(
        self,
        definition_id: UUID,
        expected_version: int,
        **updates: Any,
    ) -> PipelineDefinition:
        """Update pipeline definition with optimistic locking.

        Uses version column to detect concurrent modifications.
        If version mismatch occurs, raises OptimisticLockError.

        Args:
            definition_id: Pipeline definition UUID.
            expected_version: Expected version for optimistic lock.
            **updates: Fields to update.

        Returns:
            Updated PipelineDefinition instance.

        Raises:
            OptimisticLockError: If version mismatch detected.
            NoResultFound: If definition not found.
        """
        definition = await self.get_by_id(definition_id)
        if definition is None:
            raise NoResultFound(f"PipelineDefinition {definition_id} not found")

        if definition.version != expected_version:
            raise OptimisticLockError("PipelineDefinition", definition_id, expected_version)

        # If dag_definition is being updated, recalculate step_count
        if "dag_definition" in updates:
            dag = updates["dag_definition"]
            steps = dag.get("steps", [])
            updates["step_count"] = len(steps) if isinstance(steps, list) else 0

        for field, value in updates.items():
            if hasattr(definition, field):
                setattr(definition, field, value)

        # Increment version for optimistic locking
        definition.version = definition.version + 1
        definition.updated_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(definition)
        return definition

    async def delete(self, definition_id: UUID) -> bool:
        """Delete a pipeline definition.

        Args:
            definition_id: Pipeline definition UUID.

        Returns:
            True if deleted, False if not found.
        """
        definition = await self.get_by_id(definition_id)
        if definition is None:
            return False

        await self.session.delete(definition)
        await self.session.flush()
        return True

    async def get_execution_count(self, definition_id: UUID) -> int:
        """Get the count of executions for a pipeline definition.

        Args:
            definition_id: Pipeline definition UUID.

        Returns:
            Number of executions.
        """
        stmt = (
            select(func.count())
            .select_from(PipelineExecution)
            .where(PipelineExecution.pipeline_id == definition_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_execution_stats(self, definition_id: UUID) -> dict[str, Any]:
        """Get execution count and last execution time for a pipeline.

        Args:
            definition_id: Pipeline definition UUID.

        Returns:
            Dict with execution_count and last_execution_at.
        """
        stmt = select(
            func.count(PipelineExecution.id).label("execution_count"),
            func.max(PipelineExecution.created_at).label("last_execution_at"),
        ).where(PipelineExecution.pipeline_id == definition_id)
        result = await self.session.execute(stmt)
        row = result.one()
        return {
            "execution_count": row.execution_count,
            "last_execution_at": row.last_execution_at.isoformat()
            if row.last_execution_at
            else None,
        }

    async def exists_by_name_for_user(
        self,
        name: str,
        user_id: UUID | None,
        exclude_id: UUID | None = None,
    ) -> bool:
        """Check if a pipeline with the given name already exists for the user.

        Args:
            name: Pipeline name to check.
            user_id: User UUID to check within. If None, checks for system/anonymous pipelines.
            exclude_id: Optional pipeline ID to exclude from the check (for updates).

        Returns:
            True if a pipeline with the name exists, False otherwise.
        """
        from sqlalchemy import and_

        conditions = [PipelineDefinition.name == name]

        if user_id is not None:
            conditions.append(PipelineDefinition.user_id == user_id)
        else:
            conditions.append(PipelineDefinition.user_id.is_(None))

        if exclude_id is not None:
            conditions.append(PipelineDefinition.id != exclude_id)

        stmt = select(func.count()).select_from(PipelineDefinition).where(and_(*conditions))
        result = await self.session.execute(stmt)
        count = result.scalar_one()
        return count > 0


class PipelineExecutionCRUD:
    """CRUD operations for PipelineExecution with optimistic locking."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        pipeline_definition: dict[str, Any],
        initiator: str,
        pipeline_id: UUID | None = None,
        subscriber_ids: str | None = None,
        payload_type: str | None = None,
        notification_workflow_id: str | None = None,
    ) -> PipelineExecution:
        """Create a new pipeline execution.

        Args:
            pipeline_definition: Complete pipeline DAG definition (snapshot).
            initiator: User or service that initiated execution.
            pipeline_id: Optional reference to parent pipeline definition.
            subscriber_ids: Optional user ID(s) for Novu notification delivery.
            payload_type: Optional custom payload.type for event routing.
            notification_workflow_id: Optional override for payload.workflow_id in notifications.

        Returns:
            Created PipelineExecution instance.
        """
        execution = PipelineExecution(
            pipeline_id=pipeline_id,
            pipeline_definition=pipeline_definition,
            initiator=initiator,
            status=ExecutionStatus.PENDING,
            progress_percentage=Decimal("0.00"),
            subscriber_ids=subscriber_ids,
            payload_type=payload_type,
            notification_workflow_id=notification_workflow_id,
        )
        self.session.add(execution)
        await self.session.flush()
        await self.session.refresh(execution)
        return execution

    async def get_by_id(
        self,
        execution_id: UUID,
        include_steps: bool = False,
        include_events: bool = False,
        include_subscriptions: bool = False,
    ) -> PipelineExecution | None:
        """Get pipeline execution by ID with optional relationships.

        Args:
            execution_id: Execution UUID.
            include_steps: Include step executions.
            include_events: Include progress events.
            include_subscriptions: Include subscriptions.

        Returns:
            PipelineExecution instance or None if not found.
        """
        stmt = select(PipelineExecution).where(PipelineExecution.id == execution_id)

        if include_steps:
            stmt = stmt.options(selectinload(PipelineExecution.steps))
        if include_events:
            stmt = stmt.options(selectinload(PipelineExecution.progress_events))
        if include_subscriptions:
            stmt = stmt.options(selectinload(PipelineExecution.subscriptions))

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_with_version(
        self,
        execution_id: UUID,
        expected_version: int,
        **updates: Any,
    ) -> PipelineExecution:
        """Update pipeline execution with optimistic locking.

        Uses version column to detect concurrent modifications.
        If version mismatch occurs, raises OptimisticLockError.

        Args:
            execution_id: Execution UUID.
            expected_version: Expected version for optimistic lock.
            **updates: Fields to update.

        Returns:
            Updated PipelineExecution instance.

        Raises:
            OptimisticLockError: If version mismatch detected.
            NoResultFound: If execution not found.
        """
        # Get current execution
        execution = await self.get_by_id(execution_id)
        if execution is None:
            raise NoResultFound(f"PipelineExecution {execution_id} not found")

        # Check version
        if execution.version != expected_version:
            raise OptimisticLockError("PipelineExecution", execution_id, expected_version)

        # Apply updates
        for field, value in updates.items():
            if hasattr(execution, field):
                setattr(execution, field, value)

        # Increment version for optimistic locking
        execution.version = execution.version + 1
        execution.updated_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(execution)
        return execution

    async def update_status(
        self,
        execution_id: UUID,
        expected_version: int,
        status: ExecutionStatus,
        progress_percentage: Decimal | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        final_outputs: dict[str, Any] | None = None,
        error_info: dict[str, Any] | None = None,
    ) -> PipelineExecution:
        """Update execution status with optimistic locking.

        Convenience method for status transitions with optional related fields.

        Args:
            execution_id: Execution UUID.
            expected_version: Expected version for optimistic lock.
            status: New execution status.
            progress_percentage: Updated progress (optional).
            start_time: Execution start time (optional).
            end_time: Execution end time (optional).
            final_outputs: Final outputs if completed (optional).
            error_info: Error details if failed (optional).

        Returns:
            Updated PipelineExecution instance.
        """
        updates: dict[str, Any] = {"status": status}

        if progress_percentage is not None:
            updates["progress_percentage"] = progress_percentage
        if start_time is not None:
            updates["start_time"] = start_time
        if end_time is not None:
            updates["end_time"] = end_time
        if final_outputs is not None:
            updates["final_outputs"] = final_outputs
        if error_info is not None:
            updates["error_info"] = error_info

        return await self.update_with_version(execution_id, expected_version, **updates)

    async def list_paginated(
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
            page_size: Number of items per page.
            start_date: Filter by created_at >= start_date.
            end_date: Filter by created_at <= end_date.
            status: Filter by execution status.
            initiator: Filter by initiator.
            pipeline_id: Filter by pipeline definition ID.

        Returns:
            Tuple of (list of executions, total count).
        """
        # Base query
        stmt = select(PipelineExecution)
        count_stmt = select(func.count()).select_from(PipelineExecution)

        # Apply filters
        if start_date is not None:
            stmt = stmt.where(PipelineExecution.created_at >= start_date)
            count_stmt = count_stmt.where(PipelineExecution.created_at >= start_date)
        if end_date is not None:
            stmt = stmt.where(PipelineExecution.created_at <= end_date)
            count_stmt = count_stmt.where(PipelineExecution.created_at <= end_date)
        if status is not None:
            stmt = stmt.where(PipelineExecution.status == status)
            count_stmt = count_stmt.where(PipelineExecution.status == status)
        if initiator is not None:
            stmt = stmt.where(PipelineExecution.initiator == initiator)
            count_stmt = count_stmt.where(PipelineExecution.initiator == initiator)
        if pipeline_id is not None:
            stmt = stmt.where(PipelineExecution.pipeline_id == pipeline_id)
            count_stmt = count_stmt.where(PipelineExecution.pipeline_id == pipeline_id)

        # Get total count
        count_result = await self.session.execute(count_stmt)
        total_count = count_result.scalar_one()

        # Apply pagination and ordering
        offset = (page - 1) * page_size
        stmt = stmt.order_by(PipelineExecution.created_at.desc())
        stmt = stmt.offset(offset).limit(page_size)

        result = await self.session.execute(stmt)
        executions = list(result.scalars().all())

        return executions, total_count


class StepExecutionCRUD:
    """CRUD operations for StepExecution with optimistic locking."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_for_execution(
        self,
        execution_id: UUID,
        step_id: str,
        step_name: str,
        sequence_number: int,
    ) -> StepExecution:
        """Create a new step execution for a pipeline execution.

        Args:
            execution_id: Parent execution UUID.
            step_id: Step identifier from pipeline definition.
            step_name: Human-readable step name.
            sequence_number: Execution order within pipeline.

        Returns:
            Created StepExecution instance.
        """
        step = StepExecution(
            execution_id=execution_id,
            step_id=step_id,
            step_name=step_name,
            sequence_number=sequence_number,
            status=StepStatus.PENDING,
            progress_percentage=Decimal("0.00"),
            retry_count=0,
        )
        self.session.add(step)
        await self.session.flush()
        await self.session.refresh(step)
        return step

    async def create_batch_for_execution(
        self,
        execution_id: UUID,
        steps: list[dict[str, Any]],
    ) -> list[StepExecution]:
        """Create multiple step executions in batch.

        Args:
            execution_id: Parent execution UUID.
            steps: List of step definitions with step_id, step_name, sequence_number.

        Returns:
            List of created StepExecution instances.
        """
        step_executions = []
        for step_data in steps:
            step = StepExecution(
                execution_id=execution_id,
                step_id=step_data["step_id"],
                step_name=step_data["step_name"],
                sequence_number=step_data["sequence_number"],
                status=StepStatus.PENDING,
                progress_percentage=Decimal("0.00"),
                retry_count=0,
            )
            self.session.add(step)
            step_executions.append(step)

        await self.session.flush()
        for step in step_executions:
            await self.session.refresh(step)

        return step_executions

    async def get_by_id(self, step_id: UUID) -> StepExecution | None:
        """Get step execution by ID.

        Args:
            step_id: Step execution UUID.

        Returns:
            StepExecution instance or None if not found.
        """
        stmt = select(StepExecution).where(StepExecution.id == step_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_execution_id(
        self,
        execution_id: UUID,
        order_by_sequence: bool = True,
    ) -> list[StepExecution]:
        """Get all steps for an execution.

        Args:
            execution_id: Parent execution UUID.
            order_by_sequence: Order by sequence_number (default True).

        Returns:
            List of StepExecution instances.
        """
        stmt = select(StepExecution).where(StepExecution.execution_id == execution_id)

        if order_by_sequence:
            stmt = stmt.order_by(StepExecution.sequence_number)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_step_id_and_execution(
        self,
        execution_id: UUID,
        step_id: str,
    ) -> StepExecution | None:
        """Get step execution by step_id within an execution.

        Args:
            execution_id: Parent execution UUID.
            step_id: Step identifier from pipeline definition.

        Returns:
            StepExecution instance or None if not found.
        """
        stmt = select(StepExecution).where(
            StepExecution.execution_id == execution_id,
            StepExecution.step_id == step_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_with_version(
        self,
        step_uuid: UUID,
        expected_version: int,
        **updates: Any,
    ) -> StepExecution:
        """Update step execution with optimistic locking.

        Args:
            step_uuid: Step execution UUID.
            expected_version: Expected version for optimistic lock.
            **updates: Fields to update.

        Returns:
            Updated StepExecution instance.

        Raises:
            OptimisticLockError: If version mismatch detected.
            NoResultFound: If step execution not found.
        """
        step = await self.get_by_id(step_uuid)
        if step is None:
            raise NoResultFound(f"StepExecution {step_uuid} not found")

        if step.version != expected_version:
            raise OptimisticLockError("StepExecution", step_uuid, expected_version)

        for field, value in updates.items():
            if hasattr(step, field):
                setattr(step, field, value)

        # Increment version for optimistic locking
        step.version = step.version + 1
        step.updated_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(step)
        return step

    async def update_status(
        self,
        step_uuid: UUID,
        expected_version: int,
        status: StepStatus,
        progress_percentage: Decimal | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        outputs: dict[str, Any] | None = None,
        error_message: str | None = None,
        increment_retry: bool = False,
    ) -> StepExecution:
        """Update step status with optimistic locking.

        Args:
            step_uuid: Step execution UUID.
            expected_version: Expected version for optimistic lock.
            status: New step status.
            progress_percentage: Updated progress (optional).
            start_time: Step start time (optional).
            end_time: Step end time (optional).
            outputs: Step outputs if completed (optional).
            error_message: Error details if failed (optional).
            increment_retry: Increment retry_count (optional).

        Returns:
            Updated StepExecution instance.
        """
        updates: dict[str, Any] = {"status": status}

        if progress_percentage is not None:
            updates["progress_percentage"] = progress_percentage
        if start_time is not None:
            updates["start_time"] = start_time
        if end_time is not None:
            updates["end_time"] = end_time
        if outputs is not None:
            updates["outputs"] = outputs
        if error_message is not None:
            updates["error_message"] = error_message

        # Get current step for retry increment
        if increment_retry:
            step = await self.get_by_id(step_uuid)
            if step:
                updates["retry_count"] = step.retry_count + 1

        return await self.update_with_version(step_uuid, expected_version, **updates)

    async def get_running_steps(self, execution_id: UUID) -> list[StepExecution]:
        """Get all currently running steps for an execution.

        Args:
            execution_id: Parent execution UUID.

        Returns:
            List of running StepExecution instances.
        """
        stmt = select(StepExecution).where(
            StepExecution.execution_id == execution_id,
            StepExecution.status == StepStatus.RUNNING,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_completed_step_count(self, execution_id: UUID) -> int:
        """Get count of completed steps for an execution.

        Args:
            execution_id: Parent execution UUID.

        Returns:
            Number of completed steps.
        """
        stmt = (
            select(func.count())
            .select_from(StepExecution)
            .where(
                StepExecution.execution_id == execution_id,
                StepExecution.status == StepStatus.COMPLETED,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    # Event-driven completion tracking methods

    async def get_by_external_workflow_id(
        self,
        external_workflow_id: str,
    ) -> StepExecution | None:
        """Get step execution by external workflow ID for event routing.

        Used to find the step that is waiting for a completion event
        from an external workflow (e.g., budapp benchmark workflow).

        Args:
            external_workflow_id: External workflow ID (e.g., budapp workflow_id).

        Returns:
            StepExecution instance or None if not found.
        """
        stmt = select(StepExecution).where(
            StepExecution.external_workflow_id == external_workflow_id,
            StepExecution.awaiting_event == True,  # noqa: E712
            StepExecution.status == StepStatus.RUNNING,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_timed_out_steps(
        self,
        current_time: datetime | None = None,
    ) -> list[StepExecution]:
        """Get all steps that have timed out waiting for events.

        Used by the timeout scheduler to find and fail stale steps.

        Args:
            current_time: Current time for comparison (defaults to utcnow).

        Returns:
            List of timed out StepExecution instances.
        """
        if current_time is None:
            current_time = datetime.utcnow()

        stmt = select(StepExecution).where(
            StepExecution.awaiting_event == True,  # noqa: E712
            StepExecution.status == StepStatus.RUNNING,
            StepExecution.timeout_at.isnot(None),
            StepExecution.timeout_at < current_time,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_step_awaiting_event(
        self,
        step_uuid: UUID,
        expected_version: int,
        external_workflow_id: str,
        handler_type: str,
        timeout_at: datetime,
    ) -> StepExecution:
        """Mark a step as waiting for an external event.

        Called after handler.execute() returns when the handler needs
        to wait for an external completion event.

        Args:
            step_uuid: Step execution UUID.
            expected_version: Expected version for optimistic lock.
            external_workflow_id: External workflow ID for event correlation.
            handler_type: Handler type for event routing.
            timeout_at: When this step should timeout.

        Returns:
            Updated StepExecution instance.
        """
        return await self.update_with_version(
            step_uuid,
            expected_version,
            status=StepStatus.RUNNING,
            awaiting_event=True,
            external_workflow_id=external_workflow_id,
            handler_type=handler_type,
            timeout_at=timeout_at,
        )

    async def complete_step_from_event(
        self,
        step_uuid: UUID,
        expected_version: int,
        status: StepStatus,
        outputs: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> StepExecution:
        """Complete a step that was waiting for an event.

        Called by the event router when a completion event is received.

        Args:
            step_uuid: Step execution UUID.
            expected_version: Expected version for optimistic lock.
            status: Final step status (COMPLETED, FAILED, TIMEOUT).
            outputs: Step outputs if completed.
            error_message: Error message if failed/timed out.

        Returns:
            Updated StepExecution instance.
        """
        # For completed steps, set progress to 100%. For failed/timeout, set to 0.
        # We must provide a value since progress_percentage is NOT NULL.
        progress = Decimal("100.00") if status == StepStatus.COMPLETED else Decimal("0.00")

        return await self.update_with_version(
            step_uuid,
            expected_version,
            status=status,
            awaiting_event=False,
            end_time=datetime.utcnow(),
            progress_percentage=progress,
            outputs=outputs,
            error_message=error_message,
        )

    async def get_awaiting_steps_for_execution(
        self,
        execution_id: UUID,
    ) -> list[StepExecution]:
        """Get all steps awaiting events for an execution.

        Args:
            execution_id: Parent execution UUID.

        Returns:
            List of steps awaiting events.
        """
        stmt = select(StepExecution).where(
            StepExecution.execution_id == execution_id,
            StepExecution.awaiting_event == True,  # noqa: E712
            StepExecution.status == StepStatus.RUNNING,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
