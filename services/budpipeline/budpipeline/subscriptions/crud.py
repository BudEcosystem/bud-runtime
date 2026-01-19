"""CRUD operations for execution subscriptions.

This module provides database operations for ExecutionSubscription records
(002-pipeline-event-persistence - T015).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from budpipeline.subscriptions.models import DeliveryStatus, ExecutionSubscription


class ExecutionSubscriptionCRUD:
    """CRUD operations for ExecutionSubscription."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        execution_id: UUID,
        callback_topic: str,
        expiry_time: datetime | None = None,
    ) -> ExecutionSubscription:
        """Create a new execution subscription.

        Args:
            execution_id: Parent execution UUID.
            callback_topic: Dapr pub/sub topic name.
            expiry_time: When subscription expires (optional).

        Returns:
            Created ExecutionSubscription instance.
        """
        subscription = ExecutionSubscription(
            execution_id=execution_id,
            callback_topic=callback_topic,
            expiry_time=expiry_time,
            delivery_status=DeliveryStatus.ACTIVE,
        )
        self.session.add(subscription)
        await self.session.flush()
        await self.session.refresh(subscription)
        return subscription

    async def create_batch(
        self,
        execution_id: UUID,
        callback_topics: list[str],
        expiry_time: datetime | None = None,
    ) -> list[ExecutionSubscription]:
        """Create multiple subscriptions for an execution.

        Args:
            execution_id: Parent execution UUID.
            callback_topics: List of Dapr pub/sub topic names.
            expiry_time: When subscriptions expire (optional).

        Returns:
            List of created ExecutionSubscription instances.
        """
        subscriptions = []
        for topic in callback_topics:
            subscription = ExecutionSubscription(
                execution_id=execution_id,
                callback_topic=topic,
                expiry_time=expiry_time,
                delivery_status=DeliveryStatus.ACTIVE,
            )
            self.session.add(subscription)
            subscriptions.append(subscription)

        await self.session.flush()
        for subscription in subscriptions:
            await self.session.refresh(subscription)

        return subscriptions

    async def get_by_id(self, subscription_id: UUID) -> ExecutionSubscription | None:
        """Get subscription by ID.

        Args:
            subscription_id: Subscription UUID.

        Returns:
            ExecutionSubscription instance or None if not found.
        """
        stmt = select(ExecutionSubscription).where(ExecutionSubscription.id == subscription_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_execution_id(
        self,
        execution_id: UUID,
        active_only: bool = False,
    ) -> list[ExecutionSubscription]:
        """Get all subscriptions for an execution.

        Args:
            execution_id: Parent execution UUID.
            active_only: Only return active subscriptions.

        Returns:
            List of ExecutionSubscription instances.
        """
        stmt = select(ExecutionSubscription).where(
            ExecutionSubscription.execution_id == execution_id
        )

        if active_only:
            stmt = stmt.where(ExecutionSubscription.delivery_status == DeliveryStatus.ACTIVE)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_by_execution(
        self,
        execution_id: UUID,
    ) -> list[ExecutionSubscription]:
        """Get all active subscriptions for an execution.

        Convenience method for getting subscriptions ready for event publishing.

        Args:
            execution_id: Parent execution UUID.

        Returns:
            List of active ExecutionSubscription instances.
        """
        return await self.get_by_execution_id(execution_id, active_only=True)

    async def get_active_topics(self, execution_id: UUID) -> list[str]:
        """Get all active callback topics for an execution.

        Args:
            execution_id: Parent execution UUID.

        Returns:
            List of active callback topic names.
        """
        stmt = (
            select(ExecutionSubscription.callback_topic)
            .where(ExecutionSubscription.execution_id == execution_id)
            .where(ExecutionSubscription.delivery_status == DeliveryStatus.ACTIVE)
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.fetchall()]

    async def update_status(
        self,
        subscription_id: UUID,
        delivery_status: DeliveryStatus,
    ) -> ExecutionSubscription | None:
        """Update subscription delivery status.

        Args:
            subscription_id: Subscription UUID.
            delivery_status: New delivery status.

        Returns:
            Updated ExecutionSubscription instance or None if not found.
        """
        subscription = await self.get_by_id(subscription_id)
        if subscription is None:
            return None

        subscription.delivery_status = delivery_status
        await self.session.flush()
        await self.session.refresh(subscription)
        return subscription

    async def mark_failed(self, subscription_id: UUID) -> ExecutionSubscription | None:
        """Mark subscription as failed.

        Args:
            subscription_id: Subscription UUID.

        Returns:
            Updated ExecutionSubscription instance or None if not found.
        """
        return await self.update_status(subscription_id, DeliveryStatus.FAILED)

    async def mark_expired(self, subscription_id: UUID) -> ExecutionSubscription | None:
        """Mark subscription as expired.

        Args:
            subscription_id: Subscription UUID.

        Returns:
            Updated ExecutionSubscription instance or None if not found.
        """
        return await self.update_status(subscription_id, DeliveryStatus.EXPIRED)

    async def expire_subscriptions_batch(self) -> int:
        """Mark all expired subscriptions as expired.

        Checks expiry_time against current time and marks subscriptions
        that have passed their expiry as expired.

        Returns:
            Number of subscriptions marked as expired.
        """
        now = datetime.utcnow()
        stmt = (
            update(ExecutionSubscription)
            .where(ExecutionSubscription.delivery_status == DeliveryStatus.ACTIVE)
            .where(ExecutionSubscription.expiry_time.is_not(None))
            .where(ExecutionSubscription.expiry_time < now)
            .values(delivery_status=DeliveryStatus.EXPIRED)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def get_subscription_count(
        self,
        execution_id: UUID,
        status: DeliveryStatus | None = None,
    ) -> int:
        """Get count of subscriptions for an execution.

        Args:
            execution_id: Parent execution UUID.
            status: Filter by delivery status (optional).

        Returns:
            Number of subscriptions.
        """
        stmt = (
            select(func.count())
            .select_from(ExecutionSubscription)
            .where(ExecutionSubscription.execution_id == execution_id)
        )

        if status is not None:
            stmt = stmt.where(ExecutionSubscription.delivery_status == status)

        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_by_topic(
        self,
        execution_id: UUID,
        callback_topic: str,
    ) -> ExecutionSubscription | None:
        """Get subscription by execution and topic.

        Args:
            execution_id: Parent execution UUID.
            callback_topic: Callback topic name.

        Returns:
            ExecutionSubscription instance or None if not found.
        """
        stmt = select(ExecutionSubscription).where(
            ExecutionSubscription.execution_id == execution_id,
            ExecutionSubscription.callback_topic == callback_topic,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_by_execution(self, execution_id: UUID) -> int:
        """Delete all subscriptions for an execution.

        Note: Usually cascade delete handles this, but provided for explicit cleanup.

        Args:
            execution_id: Parent execution UUID.

        Returns:
            Number of subscriptions deleted.
        """
        subscriptions = await self.get_by_execution_id(execution_id)
        count = len(subscriptions)
        for subscription in subscriptions:
            await self.session.delete(subscription)
        await self.session.flush()
        return count
