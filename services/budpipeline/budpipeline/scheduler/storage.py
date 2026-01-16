"""Schedule Storage Service using Dapr State Store.

Provides persistence for schedules, webhooks, and event triggers.
Uses key prefixes and an index for efficient listing and querying.
"""

import logging
from datetime import datetime, timezone

from budpipeline.scheduler.schemas import (
    EventTriggerState,
    ScheduleState,
    WebhookState,
)
from budpipeline.shared.dapr_state import DaprStateStore, DaprStateStoreError

logger = logging.getLogger(__name__)


# Key prefixes for different entity types
SCHEDULE_PREFIX = "budpipeline:schedule:"
SCHEDULE_INDEX_KEY = "budpipeline:schedule:index"

WEBHOOK_PREFIX = "budpipeline:webhook:"
WEBHOOK_INDEX_KEY = "budpipeline:webhook:index"

EVENT_TRIGGER_PREFIX = "budpipeline:event_trigger:"
EVENT_TRIGGER_INDEX_KEY = "budpipeline:event_trigger:index"


class ScheduleStorageError(Exception):
    """Exception raised when storage operations fail."""

    pass


class ScheduleStorage:
    """Manages schedule persistence using Dapr state store."""

    def __init__(self, state_store: DaprStateStore | None = None):
        """Initialize storage with optional custom state store."""
        self.state_store = state_store or DaprStateStore()

    # ========================================================================
    # Schedule Operations
    # ========================================================================

    async def save_schedule(self, schedule: ScheduleState) -> None:
        """Save a schedule to the state store.

        Args:
            schedule: The schedule to save

        Raises:
            ScheduleStorageError: If the save operation fails
        """
        key = f"{SCHEDULE_PREFIX}{schedule.id}"

        try:
            # Save the schedule
            await self.state_store.save(key, schedule.model_dump(mode="json"))

            # Update the index
            await self._add_to_index(SCHEDULE_INDEX_KEY, schedule.id)

            logger.info(f"Saved schedule: {schedule.id}")

        except DaprStateStoreError as e:
            raise ScheduleStorageError(f"Failed to save schedule: {e.message}") from e

    async def get_schedule(self, schedule_id: str) -> ScheduleState | None:
        """Get a schedule by ID.

        Args:
            schedule_id: The schedule ID

        Returns:
            The schedule, or None if not found
        """
        key = f"{SCHEDULE_PREFIX}{schedule_id}"

        try:
            data = await self.state_store.get(key)
            if data is None:
                return None
            return ScheduleState.model_validate(data)

        except DaprStateStoreError as e:
            logger.error(f"Failed to get schedule {schedule_id}: {e.message}")
            raise ScheduleStorageError(f"Failed to get schedule: {e.message}") from e

    async def list_schedules(
        self,
        workflow_id: str | None = None,
        enabled: bool | None = None,
        status: str | None = None,
    ) -> list[ScheduleState]:
        """List schedules with optional filters.

        Args:
            workflow_id: Filter by workflow ID
            enabled: Filter by enabled status
            status: Filter by schedule status

        Returns:
            List of matching schedules
        """
        try:
            # Get all schedule IDs from index
            schedule_ids = await self._get_index(SCHEDULE_INDEX_KEY)

            if not schedule_ids:
                return []

            # Get all schedules in bulk
            keys = [f"{SCHEDULE_PREFIX}{sid}" for sid in schedule_ids]
            results = await self.state_store.bulk_get(keys)

            schedules: list[ScheduleState] = []
            for key, data in results.items():
                if data:
                    try:
                        schedule = ScheduleState.model_validate(data)

                        # Apply filters
                        if workflow_id and schedule.workflow_id != workflow_id:
                            continue
                        if enabled is not None and schedule.enabled != enabled:
                            continue
                        if status and schedule.status != status:
                            continue

                        schedules.append(schedule)
                    except Exception as e:
                        logger.warning(f"Failed to parse schedule from {key}: {e}")

            return schedules

        except DaprStateStoreError as e:
            logger.error(f"Failed to list schedules: {e.message}")
            raise ScheduleStorageError(f"Failed to list schedules: {e.message}") from e

    async def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule.

        Args:
            schedule_id: The schedule ID

        Returns:
            True if deleted, False if not found
        """
        key = f"{SCHEDULE_PREFIX}{schedule_id}"

        try:
            deleted = await self.state_store.delete(key)

            if deleted:
                # Remove from index
                await self._remove_from_index(SCHEDULE_INDEX_KEY, schedule_id)
                logger.info(f"Deleted schedule: {schedule_id}")

            return deleted

        except DaprStateStoreError as e:
            raise ScheduleStorageError(f"Failed to delete schedule: {e.message}") from e

    async def get_due_schedules(self, now: datetime) -> list[ScheduleState]:
        """Get all schedules that are due to run.

        Args:
            now: Current time

        Returns:
            List of schedules where next_run_at <= now and enabled
        """
        try:
            schedules = await self.list_schedules(enabled=True, status="active")

            due = []
            for schedule in schedules:
                if schedule.next_run_at and schedule.next_run_at <= now:
                    due.append(schedule)

            logger.debug(f"Found {len(due)} due schedules")
            return due

        except ScheduleStorageError:
            raise

    async def update_schedule_after_run(
        self,
        schedule_id: str,
        execution_id: str,
        execution_status: str,
        next_run_at: datetime | None,
    ) -> None:
        """Update schedule state after a run completes.

        Args:
            schedule_id: The schedule ID
            execution_id: ID of the execution
            execution_status: Status of the execution
            next_run_at: Next scheduled run time (None for one-time schedules)
        """
        schedule = await self.get_schedule(schedule_id)
        if not schedule:
            logger.warning(f"Schedule {schedule_id} not found for update")
            return

        now = datetime.now(timezone.utc)

        # Update fields
        schedule.last_run_at = now
        schedule.last_execution_id = execution_id
        schedule.last_execution_status = execution_status
        schedule.run_count += 1
        schedule.updated_at = now

        # Update next_run_at (None for completed one-time schedules)
        schedule.next_run_at = next_run_at

        # Check if schedule should be marked completed
        if schedule.max_runs and schedule.run_count >= schedule.max_runs:
            schedule.status = "completed"
            schedule.next_run_at = None
        elif schedule.expires_at and now >= schedule.expires_at:
            schedule.status = "expired"
            schedule.next_run_at = None
        elif next_run_at is None:
            schedule.status = "completed"

        await self.save_schedule(schedule)

    # ========================================================================
    # Webhook Operations
    # ========================================================================

    async def save_webhook(self, webhook: WebhookState) -> None:
        """Save a webhook to the state store."""
        key = f"{WEBHOOK_PREFIX}{webhook.id}"

        try:
            await self.state_store.save(key, webhook.model_dump(mode="json"))
            await self._add_to_index(WEBHOOK_INDEX_KEY, webhook.id)
            logger.info(f"Saved webhook: {webhook.id}")

        except DaprStateStoreError as e:
            raise ScheduleStorageError(f"Failed to save webhook: {e.message}") from e

    async def get_webhook(self, webhook_id: str) -> WebhookState | None:
        """Get a webhook by ID."""
        key = f"{WEBHOOK_PREFIX}{webhook_id}"

        try:
            data = await self.state_store.get(key)
            if data is None:
                return None
            return WebhookState.model_validate(data)

        except DaprStateStoreError as e:
            raise ScheduleStorageError(f"Failed to get webhook: {e.message}") from e

    async def list_webhooks(
        self,
        workflow_id: str | None = None,
        enabled: bool | None = None,
    ) -> list[WebhookState]:
        """List webhooks with optional filters."""
        try:
            webhook_ids = await self._get_index(WEBHOOK_INDEX_KEY)

            if not webhook_ids:
                return []

            keys = [f"{WEBHOOK_PREFIX}{wid}" for wid in webhook_ids]
            results = await self.state_store.bulk_get(keys)

            webhooks: list[WebhookState] = []
            for key, data in results.items():
                if data:
                    try:
                        webhook = WebhookState.model_validate(data)

                        if workflow_id and webhook.workflow_id != workflow_id:
                            continue
                        if enabled is not None and webhook.enabled != enabled:
                            continue

                        webhooks.append(webhook)
                    except Exception as e:
                        logger.warning(f"Failed to parse webhook from {key}: {e}")

            return webhooks

        except DaprStateStoreError as e:
            raise ScheduleStorageError(f"Failed to list webhooks: {e.message}") from e

    async def delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook."""
        key = f"{WEBHOOK_PREFIX}{webhook_id}"

        try:
            deleted = await self.state_store.delete(key)

            if deleted:
                await self._remove_from_index(WEBHOOK_INDEX_KEY, webhook_id)
                logger.info(f"Deleted webhook: {webhook_id}")

            return deleted

        except DaprStateStoreError as e:
            raise ScheduleStorageError(f"Failed to delete webhook: {e.message}") from e

    async def update_webhook_triggered(self, webhook_id: str) -> None:
        """Update webhook after it's triggered."""
        webhook = await self.get_webhook(webhook_id)
        if not webhook:
            return

        webhook.last_triggered_at = datetime.now(timezone.utc)
        webhook.trigger_count += 1
        webhook.updated_at = datetime.now(timezone.utc)

        await self.save_webhook(webhook)

    # ========================================================================
    # Event Trigger Operations
    # ========================================================================

    async def save_event_trigger(self, trigger: EventTriggerState) -> None:
        """Save an event trigger to the state store."""
        key = f"{EVENT_TRIGGER_PREFIX}{trigger.id}"

        try:
            await self.state_store.save(key, trigger.model_dump(mode="json"))
            await self._add_to_index(EVENT_TRIGGER_INDEX_KEY, trigger.id)
            logger.info(f"Saved event trigger: {trigger.id}")

        except DaprStateStoreError as e:
            raise ScheduleStorageError(f"Failed to save event trigger: {e.message}") from e

    async def get_event_trigger(self, trigger_id: str) -> EventTriggerState | None:
        """Get an event trigger by ID."""
        key = f"{EVENT_TRIGGER_PREFIX}{trigger_id}"

        try:
            data = await self.state_store.get(key)
            if data is None:
                return None
            return EventTriggerState.model_validate(data)

        except DaprStateStoreError as e:
            raise ScheduleStorageError(f"Failed to get event trigger: {e.message}") from e

    async def list_event_triggers(
        self,
        event_type: str | None = None,
        workflow_id: str | None = None,
        enabled: bool | None = None,
    ) -> list[EventTriggerState]:
        """List event triggers with optional filters."""
        try:
            trigger_ids = await self._get_index(EVENT_TRIGGER_INDEX_KEY)

            if not trigger_ids:
                return []

            keys = [f"{EVENT_TRIGGER_PREFIX}{tid}" for tid in trigger_ids]
            results = await self.state_store.bulk_get(keys)

            triggers: list[EventTriggerState] = []
            for key, data in results.items():
                if data:
                    try:
                        trigger = EventTriggerState.model_validate(data)

                        if event_type and trigger.event_type != event_type:
                            continue
                        if workflow_id and trigger.workflow_id != workflow_id:
                            continue
                        if enabled is not None and trigger.enabled != enabled:
                            continue

                        triggers.append(trigger)
                    except Exception as e:
                        logger.warning(f"Failed to parse event trigger from {key}: {e}")

            return triggers

        except DaprStateStoreError as e:
            raise ScheduleStorageError(f"Failed to list event triggers: {e.message}") from e

    async def delete_event_trigger(self, trigger_id: str) -> bool:
        """Delete an event trigger."""
        key = f"{EVENT_TRIGGER_PREFIX}{trigger_id}"

        try:
            deleted = await self.state_store.delete(key)

            if deleted:
                await self._remove_from_index(EVENT_TRIGGER_INDEX_KEY, trigger_id)
                logger.info(f"Deleted event trigger: {trigger_id}")

            return deleted

        except DaprStateStoreError as e:
            raise ScheduleStorageError(f"Failed to delete event trigger: {e.message}") from e

    async def update_event_trigger_triggered(self, trigger_id: str) -> None:
        """Update event trigger after it's triggered."""
        trigger = await self.get_event_trigger(trigger_id)
        if not trigger:
            return

        trigger.last_triggered_at = datetime.now(timezone.utc)
        trigger.trigger_count += 1
        trigger.updated_at = datetime.now(timezone.utc)

        await self.save_event_trigger(trigger)

    # ========================================================================
    # Index Management
    # ========================================================================

    async def _get_index(self, index_key: str) -> list[str]:
        """Get list of IDs from an index."""
        try:
            data = await self.state_store.get(index_key)
            if data is None:
                return []
            return data.get("ids", [])
        except DaprStateStoreError:
            return []

    async def _add_to_index(self, index_key: str, item_id: str) -> None:
        """Add an ID to an index."""
        ids = await self._get_index(index_key)
        if item_id not in ids:
            ids.append(item_id)
            await self.state_store.save(index_key, {"ids": ids})

    async def _remove_from_index(self, index_key: str, item_id: str) -> None:
        """Remove an ID from an index."""
        ids = await self._get_index(index_key)
        if item_id in ids:
            ids.remove(item_id)
            await self.state_store.save(index_key, {"ids": ids})


# Global instance
schedule_storage = ScheduleStorage()
