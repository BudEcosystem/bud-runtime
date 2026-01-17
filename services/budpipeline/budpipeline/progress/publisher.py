"""Event publisher for budpipeline progress events.

This module provides multi-topic event publishing with retry queue support
(002-pipeline-event-persistence - T047, T049, T050, T051).
"""

import asyncio
import contextlib
from collections import deque
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from budpipeline.commons.config import settings
from budpipeline.commons.observability import get_logger, record_event_published
from budpipeline.subscriptions.service import subscription_service

logger = get_logger(__name__)


class EventType:
    """Event types for pub/sub publishing."""

    WORKFLOW_PROGRESS = "workflow_progress"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    ETA_UPDATE = "eta_update"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"


class RetryableEvent:
    """Represents an event that can be retried."""

    def __init__(
        self,
        event_type: str,
        execution_id: UUID,
        topic: str,
        payload: dict[str, Any],
        retry_count: int = 0,
        max_retries: int = 3,
    ):
        self.event_type = event_type
        self.execution_id = execution_id
        self.topic = topic
        self.payload = payload
        self.retry_count = retry_count
        self.max_retries = max_retries
        self.created_at = datetime.now(timezone.utc)
        self.last_attempt = None

    def can_retry(self) -> bool:
        """Check if event can be retried."""
        return self.retry_count < self.max_retries


class EventPublisher:
    """Multi-topic event publisher with non-blocking async publishing.

    Implements:
    - Multi-topic publishing (FR-013)
    - Correlation IDs in all events (FR-015)
    - Non-blocking publishing (FR-014)
    - Retry queue for failed publishes (FR-046)
    """

    def __init__(
        self,
        pubsub_name: str = "pubsub",
        max_queue_size: int = 1000,
        retry_interval_seconds: int = 5,
    ):
        """Initialize event publisher.

        Args:
            pubsub_name: Dapr pub/sub component name.
            max_queue_size: Maximum retry queue size.
            retry_interval_seconds: Interval between retry attempts.
        """
        self.pubsub_name = pubsub_name
        self.max_queue_size = max_queue_size
        self.retry_interval_seconds = retry_interval_seconds
        self._retry_queue: deque[RetryableEvent] = deque(maxlen=max_queue_size)
        self._retry_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the retry processor."""
        if self._running:
            return

        self._running = True
        self._retry_task = asyncio.create_task(self._process_retry_queue())
        logger.info("Event publisher retry processor started")

    async def stop(self) -> None:
        """Stop the retry processor."""
        self._running = False
        if self._retry_task:
            self._retry_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._retry_task
        logger.info("Event publisher retry processor stopped")

    async def publish_to_topics(
        self,
        execution_id: UUID,
        event_type: str,
        data: dict[str, Any],
        correlation_id: str | None = None,
        step_id: str | None = None,
    ) -> list[str]:
        """Publish event to all active callback topics for an execution.

        Non-blocking - fires and forgets. Failed publishes go to retry queue.

        Args:
            execution_id: Pipeline execution UUID.
            event_type: Type of event (workflow_progress, step_completed, etc.).
            data: Event payload data.
            correlation_id: Optional correlation ID for tracing.
            step_id: Optional step ID for step-level events.

        Returns:
            List of topics event was queued for publishing.
        """
        # Get active topics for this execution
        topics = await subscription_service.get_active_topics(execution_id)

        if not topics:
            logger.debug(
                "No active topics for execution",
                execution_id=str(execution_id),
                event_type=event_type,
            )
            return []

        # Build event payload with correlation IDs (FR-015)
        payload = self._build_event_payload(
            event_type=event_type,
            execution_id=execution_id,
            data=data,
            correlation_id=correlation_id,
            step_id=step_id,
        )

        # Publish to each topic non-blocking (FR-014)
        for topic in topics:
            # Fire and forget - don't block execution on publish
            asyncio.create_task(
                self._publish_single_topic(
                    topic=topic,
                    execution_id=execution_id,
                    event_type=event_type,
                    payload=payload,
                )
            )

        logger.debug(
            "Queued event for publishing",
            execution_id=str(execution_id),
            event_type=event_type,
            topics=topics,
        )

        return topics

    def _build_event_payload(
        self,
        event_type: str,
        execution_id: UUID,
        data: dict[str, Any],
        correlation_id: str | None = None,
        step_id: str | None = None,
    ) -> dict[str, Any]:
        """Build event payload with correlation IDs.

        Args:
            event_type: Type of event.
            execution_id: Execution UUID.
            data: Event data.
            correlation_id: Optional correlation ID.
            step_id: Optional step ID.

        Returns:
            Complete event payload.
        """
        payload = {
            "type": event_type,
            "execution_id": str(execution_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

        if correlation_id:
            payload["correlation_id"] = correlation_id

        if step_id:
            payload["step_id"] = step_id

        return payload

    async def _publish_single_topic(
        self,
        topic: str,
        execution_id: UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> bool:
        """Publish event to a single topic.

        Args:
            topic: Target topic.
            execution_id: Execution UUID.
            event_type: Event type.
            payload: Event payload.

        Returns:
            True if successful, False otherwise.
        """
        try:
            # Import Dapr client here to avoid circular imports
            from dapr.aio.clients import DaprClient

            async with DaprClient() as client:
                await client.publish_event(
                    pubsub_name=self.pubsub_name,
                    topic_name=topic,
                    data=payload,
                    data_content_type="application/json",
                )

            record_event_published(event_type, topic)

            logger.debug(
                "Published event to topic",
                topic=topic,
                execution_id=str(execution_id),
                event_type=event_type,
            )
            return True

        except Exception as e:
            logger.warning(
                "Failed to publish event, queueing for retry",
                topic=topic,
                execution_id=str(execution_id),
                event_type=event_type,
                error=str(e),
            )

            # Queue for retry (FR-046)
            self._queue_for_retry(
                event_type=event_type,
                execution_id=execution_id,
                topic=topic,
                payload=payload,
            )
            return False

    def _queue_for_retry(
        self,
        event_type: str,
        execution_id: UUID,
        topic: str,
        payload: dict[str, Any],
    ) -> None:
        """Queue failed event for retry.

        Args:
            event_type: Event type.
            execution_id: Execution UUID.
            topic: Target topic.
            payload: Event payload.
        """
        event = RetryableEvent(
            event_type=event_type,
            execution_id=execution_id,
            topic=topic,
            payload=payload,
        )

        if len(self._retry_queue) >= self.max_queue_size:
            logger.warning(
                "Retry queue full, dropping oldest event",
                queue_size=len(self._retry_queue),
            )
            self._retry_queue.popleft()

        self._retry_queue.append(event)

    async def _process_retry_queue(self) -> None:
        """Background task to process retry queue."""
        while self._running:
            try:
                await asyncio.sleep(self.retry_interval_seconds)

                if not self._retry_queue:
                    continue

                # Process up to 10 events per cycle
                events_to_retry = []
                for _ in range(min(10, len(self._retry_queue))):
                    if self._retry_queue:
                        events_to_retry.append(self._retry_queue.popleft())

                for event in events_to_retry:
                    if not event.can_retry():
                        logger.error(
                            "Event exceeded max retries, dropping",
                            execution_id=str(event.execution_id),
                            topic=event.topic,
                            event_type=event.event_type,
                            retry_count=event.retry_count,
                        )
                        continue

                    event.retry_count += 1
                    event.last_attempt = datetime.now(timezone.utc)

                    success = await self._publish_single_topic(
                        topic=event.topic,
                        execution_id=event.execution_id,
                        event_type=event.event_type,
                        payload=event.payload,
                    )

                    if not success and event.can_retry():
                        # Re-queue if still retriable
                        self._retry_queue.append(event)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in retry queue processor: {e}")

    # Convenience methods for specific event types

    async def publish_workflow_progress(
        self,
        execution_id: UUID,
        progress_percentage: Decimal,
        eta_seconds: int | None = None,
        current_step: str | None = None,
        correlation_id: str | None = None,
    ) -> list[str]:
        """Publish workflow progress event.

        Args:
            execution_id: Execution UUID.
            progress_percentage: Current progress (0-100).
            eta_seconds: Estimated time to completion.
            current_step: Description of current step.
            correlation_id: Optional correlation ID.

        Returns:
            List of topics published to.
        """
        data = {
            "progress_percentage": float(progress_percentage),
            "eta_seconds": eta_seconds,
            "current_step": current_step,
        }

        return await self.publish_to_topics(
            execution_id=execution_id,
            event_type=EventType.WORKFLOW_PROGRESS,
            data=data,
            correlation_id=correlation_id,
        )

    async def publish_step_started(
        self,
        execution_id: UUID,
        step_id: str,
        step_name: str,
        sequence_number: int,
        correlation_id: str | None = None,
    ) -> list[str]:
        """Publish step started event.

        Args:
            execution_id: Execution UUID.
            step_id: Step identifier.
            step_name: Step name.
            sequence_number: Step sequence number.
            correlation_id: Optional correlation ID.

        Returns:
            List of topics published to.
        """
        data = {
            "step_id": step_id,
            "step_name": step_name,
            "sequence_number": sequence_number,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        return await self.publish_to_topics(
            execution_id=execution_id,
            event_type=EventType.STEP_STARTED,
            data=data,
            correlation_id=correlation_id,
            step_id=step_id,
        )

    async def publish_step_completed(
        self,
        execution_id: UUID,
        step_id: str,
        step_name: str,
        progress_percentage: Decimal,
        duration_seconds: int | None = None,
        correlation_id: str | None = None,
    ) -> list[str]:
        """Publish step completed event.

        Args:
            execution_id: Execution UUID.
            step_id: Step identifier.
            step_name: Step name.
            progress_percentage: Overall progress after step.
            duration_seconds: Step duration.
            correlation_id: Optional correlation ID.

        Returns:
            List of topics published to.
        """
        data = {
            "step_id": step_id,
            "step_name": step_name,
            "progress_percentage": float(progress_percentage),
            "duration_seconds": duration_seconds,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

        return await self.publish_to_topics(
            execution_id=execution_id,
            event_type=EventType.STEP_COMPLETED,
            data=data,
            correlation_id=correlation_id,
            step_id=step_id,
        )

    async def publish_step_failed(
        self,
        execution_id: UUID,
        step_id: str,
        step_name: str,
        error_message: str,
        correlation_id: str | None = None,
    ) -> list[str]:
        """Publish step failed event.

        Args:
            execution_id: Execution UUID.
            step_id: Step identifier.
            step_name: Step name.
            error_message: Error message.
            correlation_id: Optional correlation ID.

        Returns:
            List of topics published to.
        """
        data = {
            "step_id": step_id,
            "step_name": step_name,
            "error_message": error_message,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }

        return await self.publish_to_topics(
            execution_id=execution_id,
            event_type=EventType.STEP_FAILED,
            data=data,
            correlation_id=correlation_id,
            step_id=step_id,
        )

    async def publish_workflow_completed(
        self,
        execution_id: UUID,
        success: bool,
        final_outputs: dict[str, Any] | None = None,
        final_message: str | None = None,
        correlation_id: str | None = None,
    ) -> list[str]:
        """Publish workflow completed event.

        Args:
            execution_id: Execution UUID.
            success: Whether workflow completed successfully.
            final_outputs: Final workflow outputs.
            final_message: Optional completion message.
            correlation_id: Optional correlation ID.

        Returns:
            List of topics published to.
        """
        event_type = EventType.WORKFLOW_COMPLETED if success else EventType.WORKFLOW_FAILED

        data = {
            "success": success,
            "outputs": final_outputs,
            "message": final_message,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

        return await self.publish_to_topics(
            execution_id=execution_id,
            event_type=event_type,
            data=data,
            correlation_id=correlation_id,
        )

    async def publish_eta_update(
        self,
        execution_id: UUID,
        eta_seconds: int,
        progress_percentage: Decimal,
        correlation_id: str | None = None,
    ) -> list[str]:
        """Publish ETA update event.

        Args:
            execution_id: Execution UUID.
            eta_seconds: Updated estimated time.
            progress_percentage: Current progress.
            correlation_id: Optional correlation ID.

        Returns:
            List of topics published to.
        """
        data = {
            "eta_seconds": eta_seconds,
            "progress_percentage": float(progress_percentage),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        return await self.publish_to_topics(
            execution_id=execution_id,
            event_type=EventType.ETA_UPDATE,
            data=data,
            correlation_id=correlation_id,
        )

    @property
    def retry_queue_size(self) -> int:
        """Get current retry queue size."""
        return len(self._retry_queue)


# Global event publisher instance
event_publisher = EventPublisher(
    pubsub_name=settings.dapr_pubsub_name if hasattr(settings, "dapr_pubsub_name") else "pubsub",
)
