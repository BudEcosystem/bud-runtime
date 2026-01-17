"""CRUD operations for progress events.

This module provides database operations for ProgressEvent records
(002-pipeline-event-persistence - T014).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from budpipeline.progress.models import EventType, ProgressEvent


class ProgressEventCRUD:
    """CRUD operations for ProgressEvent."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._sequence_counter: dict[UUID, int] = {}

    async def _get_next_sequence_number(self, execution_id: UUID) -> int:
        """Get next sequence number for an execution.

        Args:
            execution_id: Execution UUID.

        Returns:
            Next sequence number.
        """
        # Get max sequence number from database
        stmt = select(func.coalesce(func.max(ProgressEvent.sequence_number), 0)).where(
            ProgressEvent.execution_id == execution_id
        )
        result = await self.session.execute(stmt)
        max_seq = result.scalar_one()

        # Use in-memory counter for faster increments within session
        if execution_id not in self._sequence_counter:
            self._sequence_counter[execution_id] = max_seq

        self._sequence_counter[execution_id] += 1
        return self._sequence_counter[execution_id]

    async def create(
        self,
        execution_id: UUID,
        event_type: EventType,
        progress_percentage: Decimal,
        eta_seconds: int | None = None,
        current_step_desc: str | None = None,
        event_details: dict[str, Any] | None = None,
    ) -> ProgressEvent:
        """Create a new progress event.

        Args:
            execution_id: Parent execution UUID.
            event_type: Type of progress event.
            progress_percentage: Progress at event time (0.00-100.00).
            eta_seconds: Estimated time to completion (optional).
            current_step_desc: Description of current step (optional).
            event_details: Additional event metadata (optional).

        Returns:
            Created ProgressEvent instance.
        """
        sequence_number = await self._get_next_sequence_number(execution_id)

        event = ProgressEvent(
            execution_id=execution_id,
            event_type=event_type,
            progress_percentage=progress_percentage,
            eta_seconds=eta_seconds,
            current_step_desc=current_step_desc,
            event_details=event_details,
            sequence_number=sequence_number,
            timestamp=datetime.utcnow(),
        )
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def get_by_id(self, event_id: UUID) -> ProgressEvent | None:
        """Get progress event by ID.

        Args:
            event_id: Event UUID.

        Returns:
            ProgressEvent instance or None if not found.
        """
        stmt = select(ProgressEvent).where(ProgressEvent.id == event_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_execution_id(
        self,
        execution_id: UUID,
        event_type: EventType | None = None,
        since: datetime | None = None,
        order_by_sequence: bool = True,
        limit: int | None = None,
    ) -> list[ProgressEvent]:
        """Get progress events for an execution.

        Args:
            execution_id: Parent execution UUID.
            event_type: Filter by event type (optional).
            since: Return events after this timestamp (optional).
            order_by_sequence: Order by sequence_number (default True).
            limit: Maximum number of events to return (optional).

        Returns:
            List of ProgressEvent instances.
        """
        stmt = select(ProgressEvent).where(ProgressEvent.execution_id == execution_id)

        if event_type is not None:
            stmt = stmt.where(ProgressEvent.event_type == event_type)

        if since is not None:
            stmt = stmt.where(ProgressEvent.timestamp > since)

        if order_by_sequence:
            stmt = stmt.order_by(ProgressEvent.sequence_number)
        else:
            stmt = stmt.order_by(ProgressEvent.timestamp.desc())

        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_events(
        self,
        execution_id: UUID,
        limit: int = 20,
    ) -> list[ProgressEvent]:
        """Get most recent progress events for an execution.

        Args:
            execution_id: Parent execution UUID.
            limit: Maximum number of events to return.

        Returns:
            List of most recent ProgressEvent instances (newest first).
        """
        stmt = (
            select(ProgressEvent)
            .where(ProgressEvent.execution_id == execution_id)
            .order_by(ProgressEvent.sequence_number.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        events = list(result.scalars().all())
        # Reverse to return in chronological order
        return events[::-1]

    async def get_latest_event(
        self,
        execution_id: UUID,
        event_type: EventType | None = None,
    ) -> ProgressEvent | None:
        """Get the latest progress event for an execution.

        Args:
            execution_id: Parent execution UUID.
            event_type: Filter by event type (optional).

        Returns:
            Latest ProgressEvent instance or None if none found.
        """
        stmt = (
            select(ProgressEvent)
            .where(ProgressEvent.execution_id == execution_id)
            .order_by(ProgressEvent.sequence_number.desc())
            .limit(1)
        )

        if event_type is not None:
            stmt = stmt.where(ProgressEvent.event_type == event_type)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_event_count(
        self,
        execution_id: UUID,
        event_type: EventType | None = None,
    ) -> int:
        """Get count of progress events for an execution.

        Args:
            execution_id: Parent execution UUID.
            event_type: Filter by event type (optional).

        Returns:
            Number of progress events.
        """
        stmt = (
            select(func.count())
            .select_from(ProgressEvent)
            .where(ProgressEvent.execution_id == execution_id)
        )

        if event_type is not None:
            stmt = stmt.where(ProgressEvent.event_type == event_type)

        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def create_workflow_progress_event(
        self,
        execution_id: UUID,
        progress_percentage: Decimal,
        eta_seconds: int | None = None,
        current_step_desc: str | None = None,
        additional_details: dict[str, Any] | None = None,
    ) -> ProgressEvent:
        """Create a workflow_progress event.

        Convenience method for creating progress update events.

        Args:
            execution_id: Parent execution UUID.
            progress_percentage: Overall progress (0.00-100.00).
            eta_seconds: Estimated time to completion.
            current_step_desc: Description of current step.
            additional_details: Additional metadata.

        Returns:
            Created ProgressEvent instance.
        """
        return await self.create(
            execution_id=execution_id,
            event_type=EventType.WORKFLOW_PROGRESS,
            progress_percentage=progress_percentage,
            eta_seconds=eta_seconds,
            current_step_desc=current_step_desc,
            event_details=additional_details,
        )

    async def create_step_completed_event(
        self,
        execution_id: UUID,
        progress_percentage: Decimal,
        step_id: str,
        step_name: str,
        duration_seconds: int | None = None,
    ) -> ProgressEvent:
        """Create a step_completed event.

        Args:
            execution_id: Parent execution UUID.
            progress_percentage: Progress after step completion.
            step_id: Completed step identifier.
            step_name: Completed step name.
            duration_seconds: Step execution duration.

        Returns:
            Created ProgressEvent instance.
        """
        return await self.create(
            execution_id=execution_id,
            event_type=EventType.STEP_COMPLETED,
            progress_percentage=progress_percentage,
            current_step_desc=f"Completed: {step_name}",
            event_details={
                "step_id": step_id,
                "step_name": step_name,
                "duration_seconds": duration_seconds,
            },
        )

    async def create_workflow_completed_event(
        self,
        execution_id: UUID,
        success: bool,
        final_message: str | None = None,
    ) -> ProgressEvent:
        """Create a workflow_completed event.

        Args:
            execution_id: Parent execution UUID.
            success: Whether workflow completed successfully.
            final_message: Optional completion message.

        Returns:
            Created ProgressEvent instance.
        """
        progress = Decimal("100.00") if success else Decimal("0.00")
        return await self.create(
            execution_id=execution_id,
            event_type=EventType.WORKFLOW_COMPLETED,
            progress_percentage=progress,
            eta_seconds=0,
            current_step_desc=final_message or ("Completed" if success else "Failed"),
            event_details={
                "success": success,
                "completed_at": datetime.utcnow().isoformat(),
            },
        )

    async def create_eta_update_event(
        self,
        execution_id: UUID,
        progress_percentage: Decimal,
        eta_seconds: int,
        reason: str | None = None,
    ) -> ProgressEvent:
        """Create an eta_update event.

        Args:
            execution_id: Parent execution UUID.
            progress_percentage: Current progress.
            eta_seconds: Updated ETA in seconds.
            reason: Reason for ETA update.

        Returns:
            Created ProgressEvent instance.
        """
        return await self.create(
            execution_id=execution_id,
            event_type=EventType.ETA_UPDATE,
            progress_percentage=progress_percentage,
            eta_seconds=eta_seconds,
            event_details={"reason": reason} if reason else None,
        )

    async def list_with_filters(
        self,
        execution_id: UUID,
        event_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ProgressEvent], int]:
        """List progress events with filters and pagination.

        Args:
            execution_id: Parent execution UUID.
            event_type: Filter by event type string (optional).
            start_time: Filter events with timestamp >= start_time.
            end_time: Filter events with timestamp <= end_time.
            limit: Maximum events to return.
            offset: Number of events to skip.

        Returns:
            Tuple of (list of events, total count).
        """
        # Build base query
        base_stmt = select(ProgressEvent).where(ProgressEvent.execution_id == execution_id)

        if event_type:
            base_stmt = base_stmt.where(ProgressEvent.event_type == EventType(event_type))

        if start_time:
            base_stmt = base_stmt.where(ProgressEvent.timestamp >= start_time)

        if end_time:
            base_stmt = base_stmt.where(ProgressEvent.timestamp <= end_time)

        # Get total count
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one()

        # Get paginated results (newest first)
        list_stmt = base_stmt.order_by(ProgressEvent.timestamp.desc()).offset(offset).limit(limit)
        list_result = await self.session.execute(list_stmt)
        events = list(list_result.scalars().all())

        return events, total
