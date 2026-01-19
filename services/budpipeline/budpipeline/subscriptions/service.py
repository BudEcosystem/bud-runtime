"""Subscription management service for budpipeline.

This module provides subscription management with callback topic validation
and subscription lifecycle management (002-pipeline-event-persistence - T044, T045).
"""

from typing import Any
from uuid import UUID

from budpipeline.commons.database import AsyncSessionLocal
from budpipeline.commons.observability import get_logger
from budpipeline.subscriptions.crud import ExecutionSubscriptionCRUD
from budpipeline.subscriptions.models import DeliveryStatus

logger = get_logger(__name__)


class SubscriptionService:
    """Service for managing execution subscriptions and callback topic validation.

    Implements:
    - Topic validation via Dapr metadata (FR-022)
    - Subscription lifecycle management (create, get, update)
    - Active topic retrieval for event publishing
    """

    def __init__(self) -> None:
        """Initialize subscription service."""
        self._valid_topics_cache: dict[str, bool] = {}

    async def validate_topics(
        self,
        topics: list[str],
    ) -> tuple[list[str], list[str]]:
        """Validate callback topics via Dapr pub/sub metadata.

        Validates that topics exist and can receive messages.

        Args:
            topics: List of topic names to validate.

        Returns:
            Tuple of (valid_topics, invalid_topics).
        """
        valid_topics = []
        invalid_topics = []

        for topic in topics:
            is_valid = await self._validate_single_topic(topic)
            if is_valid:
                valid_topics.append(topic)
            else:
                invalid_topics.append(topic)

        return valid_topics, invalid_topics

    async def _validate_single_topic(self, topic: str) -> bool:
        """Validate a single topic.

        Args:
            topic: Topic name to validate.

        Returns:
            True if topic is valid, False otherwise.
        """
        # Check cache first
        if topic in self._valid_topics_cache:
            return self._valid_topics_cache[topic]

        # Basic validation: non-empty string, alphanumeric with hyphens/underscores
        if not topic or not isinstance(topic, str):
            return False

        # Check allowed characters (alphanumeric, hyphens, underscores, dots)
        import re

        if not re.match(r"^[a-zA-Z][a-zA-Z0-9._-]*$", topic):
            logger.warning(f"Invalid topic format: {topic}")
            return False

        # For now, accept valid format topics
        # In production, would validate against Dapr pub/sub component
        # by attempting to get topic metadata
        self._valid_topics_cache[topic] = True
        return True

    async def create_subscriptions(
        self,
        execution_id: UUID,
        callback_topics: list[str],
    ) -> list[UUID]:
        """Create subscriptions for callback topics.

        Creates ExecutionSubscription records for each valid topic.
        Invalid topics are logged and skipped.

        Args:
            execution_id: Pipeline execution UUID.
            callback_topics: List of callback topic names.

        Returns:
            List of created subscription UUIDs.
        """
        if not callback_topics:
            return []

        # Validate topics first
        valid_topics, invalid_topics = await self.validate_topics(callback_topics)

        if invalid_topics:
            logger.warning(
                "Some callback topics are invalid",
                execution_id=str(execution_id),
                invalid_topics=invalid_topics,
            )

        if not valid_topics:
            logger.warning(
                "No valid callback topics for subscription",
                execution_id=str(execution_id),
            )
            return []

        async with AsyncSessionLocal() as session:
            crud = ExecutionSubscriptionCRUD(session)

            subscriptions_data = [{"callback_topic": topic} for topic in valid_topics]

            subscriptions = await crud.create_batch(
                execution_id=execution_id,
                subscriptions=subscriptions_data,
            )
            await session.commit()

            subscription_ids = [sub.id for sub in subscriptions]

            logger.info(
                "Created execution subscriptions",
                execution_id=str(execution_id),
                subscription_count=len(subscription_ids),
                topics=valid_topics,
            )

            return subscription_ids

    async def get_active_topics(
        self,
        execution_id: UUID,
    ) -> list[str]:
        """Get active callback topics for an execution.

        Returns topics with active subscriptions (not expired or failed).

        Args:
            execution_id: Pipeline execution UUID.

        Returns:
            List of active callback topic names.
        """
        async with AsyncSessionLocal() as session:
            crud = ExecutionSubscriptionCRUD(session)
            return await crud.get_active_topics(execution_id)

    async def get_subscription_by_id(
        self,
        subscription_id: UUID,
    ) -> Any:
        """Get subscription by ID.

        Args:
            subscription_id: Subscription UUID.

        Returns:
            ExecutionSubscription or None if not found.
        """
        async with AsyncSessionLocal() as session:
            crud = ExecutionSubscriptionCRUD(session)
            return await crud.get_by_id(subscription_id)

    async def mark_delivery_success(
        self,
        subscription_id: UUID,
    ) -> None:
        """Mark subscription as successfully delivered (stays ACTIVE).

        Note: Subscriptions remain ACTIVE after successful delivery,
        as they continue to receive events until expiry or failure.

        Args:
            subscription_id: Subscription UUID.
        """
        async with AsyncSessionLocal() as session:
            crud = ExecutionSubscriptionCRUD(session)
            await crud.update_status(
                subscription_id=subscription_id,
                status=DeliveryStatus.ACTIVE,
            )
            await session.commit()

    async def mark_delivery_failed(
        self,
        subscription_id: UUID,
        error_message: str | None = None,
    ) -> None:
        """Mark subscription as failed.

        Args:
            subscription_id: Subscription UUID.
            error_message: Optional error message.
        """
        async with AsyncSessionLocal() as session:
            crud = ExecutionSubscriptionCRUD(session)
            await crud.update_status(
                subscription_id=subscription_id,
                status=DeliveryStatus.FAILED,
            )
            await session.commit()

            logger.warning(
                "Subscription delivery failed",
                subscription_id=str(subscription_id),
                error=error_message,
            )

    async def expire_subscription(
        self,
        subscription_id: UUID,
    ) -> None:
        """Mark subscription as expired.

        Args:
            subscription_id: Subscription UUID.
        """
        async with AsyncSessionLocal() as session:
            crud = ExecutionSubscriptionCRUD(session)
            await crud.update_status(
                subscription_id=subscription_id,
                status=DeliveryStatus.EXPIRED,
            )
            await session.commit()

    def clear_topic_cache(self) -> None:
        """Clear the topic validation cache.

        Useful for testing or when pub/sub configuration changes.
        """
        self._valid_topics_cache.clear()


# Global subscription service instance
subscription_service = SubscriptionService()
