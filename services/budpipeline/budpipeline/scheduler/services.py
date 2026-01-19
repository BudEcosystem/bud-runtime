"""Schedule Services - business logic for schedule management.

Provides services for creating, updating, and managing schedules,
webhooks, and event triggers.
"""

import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from budpipeline.commons.constants import ScheduleType
from budpipeline.commons.exceptions import CronParseError
from budpipeline.scheduler.cron_parser import CronParser
from budpipeline.scheduler.schemas import (
    EventTriggerCreate,
    EventTriggerResponse,
    EventTriggerState,
    EventTriggerUpdate,
    NextRunsPreview,
    ScheduleCreate,
    ScheduleResponse,
    ScheduleState,
    ScheduleUpdate,
    WebhookCreate,
    WebhookResponse,
    WebhookState,
    WebhookUpdate,
)
from budpipeline.scheduler.storage import ScheduleStorage, schedule_storage

logger = logging.getLogger(__name__)


# Regex for parsing @every interval expressions
INTERVAL_PATTERN = re.compile(
    r"^@every\s+(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$",
    re.IGNORECASE,
)


class ScheduleServiceError(Exception):
    """Exception raised by schedule services."""

    pass


class ScheduleService:
    """Service for managing schedules."""

    def __init__(self, storage: ScheduleStorage | None = None):
        self.storage = storage or schedule_storage

    async def create_schedule(
        self,
        request: ScheduleCreate,
        created_by: str | None = None,
    ) -> ScheduleResponse:
        """Create a new schedule.

        Args:
            request: Schedule creation request
            created_by: User ID who created the schedule

        Returns:
            Created schedule response

        Raises:
            ScheduleServiceError: If schedule creation fails
        """
        now = datetime.now(timezone.utc)

        # Validate and calculate next_run_at
        try:
            next_run_at = self._calculate_next_run(
                request.schedule.type,
                request.schedule.expression,
                request.schedule.timezone,
                request.schedule.run_at,
                now,
            )
        except (CronParseError, ValueError) as e:
            raise ScheduleServiceError(f"Invalid schedule: {str(e)}") from e

        # Create schedule state
        schedule = ScheduleState(
            id=str(uuid4()),
            workflow_id=request.workflow_id,
            name=request.name,
            description=request.description,
            schedule_type=request.schedule.type,
            expression=request.schedule.expression,
            timezone=request.schedule.timezone,
            run_at=request.schedule.run_at,
            params=request.params,
            enabled=request.enabled,
            created_at=now,
            updated_at=now,
            next_run_at=next_run_at,
            max_runs=request.max_runs,
            expires_at=request.expires_at,
            status="active" if request.enabled else "paused",
            created_by=created_by,
        )

        await self.storage.save_schedule(schedule)

        logger.info(
            f"Created schedule {schedule.id} for workflow {request.workflow_id}, "
            f"next_run_at={next_run_at}"
        )

        return schedule.to_response()

    async def get_schedule(self, schedule_id: str) -> ScheduleResponse | None:
        """Get a schedule by ID."""
        schedule = await self.storage.get_schedule(schedule_id)
        if schedule:
            return schedule.to_response()
        return None

    async def list_schedules(
        self,
        workflow_id: str | None = None,
        enabled: bool | None = None,
        status: str | None = None,
    ) -> list[ScheduleResponse]:
        """List schedules with optional filters."""
        schedules = await self.storage.list_schedules(
            workflow_id=workflow_id,
            enabled=enabled,
            status=status,
        )
        return [s.to_response() for s in schedules]

    async def update_schedule(
        self,
        schedule_id: str,
        request: ScheduleUpdate,
    ) -> ScheduleResponse | None:
        """Update a schedule."""
        schedule = await self.storage.get_schedule(schedule_id)
        if not schedule:
            return None

        now = datetime.now(timezone.utc)
        schedule.updated_at = now

        # Update fields
        if request.name is not None:
            schedule.name = request.name
        if request.description is not None:
            schedule.description = request.description
        if request.params is not None:
            schedule.params = request.params
        if request.enabled is not None:
            schedule.enabled = request.enabled
            if request.enabled and schedule.status == "paused":
                schedule.status = "active"
            elif not request.enabled:
                schedule.status = "paused"
        if request.max_runs is not None:
            schedule.max_runs = request.max_runs
        if request.expires_at is not None:
            schedule.expires_at = request.expires_at

        # Update schedule config and recalculate next_run_at
        if request.schedule:
            schedule.schedule_type = request.schedule.type
            schedule.expression = request.schedule.expression
            schedule.timezone = request.schedule.timezone
            schedule.run_at = request.schedule.run_at

            try:
                schedule.next_run_at = self._calculate_next_run(
                    schedule.schedule_type,
                    schedule.expression,
                    schedule.timezone,
                    schedule.run_at,
                    now,
                )
            except (CronParseError, ValueError) as e:
                raise ScheduleServiceError(f"Invalid schedule: {str(e)}") from e

        await self.storage.save_schedule(schedule)
        return schedule.to_response()

    async def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule."""
        return await self.storage.delete_schedule(schedule_id)

    async def pause_schedule(self, schedule_id: str) -> ScheduleResponse | None:
        """Pause a schedule."""
        schedule = await self.storage.get_schedule(schedule_id)
        if not schedule:
            return None

        schedule.enabled = False
        schedule.status = "paused"
        schedule.updated_at = datetime.now(timezone.utc)

        await self.storage.save_schedule(schedule)
        return schedule.to_response()

    async def resume_schedule(self, schedule_id: str) -> ScheduleResponse | None:
        """Resume a paused schedule."""
        schedule = await self.storage.get_schedule(schedule_id)
        if not schedule:
            return None

        if schedule.status in ("expired", "completed"):
            raise ScheduleServiceError(f"Cannot resume {schedule.status} schedule")

        now = datetime.now(timezone.utc)

        # Recalculate next_run_at
        schedule.next_run_at = self._calculate_next_run(
            schedule.schedule_type,
            schedule.expression,
            schedule.timezone,
            schedule.run_at,
            now,
        )

        schedule.enabled = True
        schedule.status = "active"
        schedule.updated_at = now

        await self.storage.save_schedule(schedule)
        return schedule.to_response()

    async def get_next_runs(
        self,
        schedule_id: str,
        count: int = 10,
    ) -> NextRunsPreview | None:
        """Get preview of next N runs for a schedule."""
        schedule = await self.storage.get_schedule(schedule_id)
        if not schedule:
            return None

        if schedule.schedule_type == ScheduleType.ONE_TIME:
            runs = [schedule.run_at] if schedule.run_at else []
        elif schedule.schedule_type == ScheduleType.CRON:
            try:
                expr = CronParser.parse(schedule.expression, schedule.timezone)
                runs = CronParser.get_next_n(expr, count=count)
            except CronParseError:
                runs = []
        elif schedule.schedule_type == ScheduleType.INTERVAL:
            runs = self._get_next_interval_runs(schedule.expression, count)
        else:
            runs = []

        return NextRunsPreview(schedule_id=schedule_id, next_runs=runs)

    def _calculate_next_run(
        self,
        schedule_type: ScheduleType,
        expression: str | None,
        tz: str,
        run_at: datetime | None,
        now: datetime,
    ) -> datetime | None:
        """Calculate the next run time for a schedule."""
        if schedule_type == ScheduleType.MANUAL:
            return None

        if schedule_type == ScheduleType.ONE_TIME:
            if run_at and run_at > now:
                return run_at
            return None

        if schedule_type == ScheduleType.CRON:
            if not expression:
                raise ValueError("Cron expression required")
            expr = CronParser.parse(expression, tz)
            return CronParser.get_next(expr, now)

        if schedule_type == ScheduleType.INTERVAL:
            if not expression:
                raise ValueError("Interval expression required")
            interval_seconds = self._parse_interval(expression)
            return now + timedelta(seconds=interval_seconds)

        return None

    @staticmethod
    def _parse_interval(expression: str) -> int:
        """Parse @every interval expression to seconds.

        Supports: @every 5m, @every 1h, @every 30s, @every 1h30m
        """
        match = INTERVAL_PATTERN.match(expression.strip())
        if not match:
            raise ValueError(
                f"Invalid interval expression: {expression}. "
                f"Use format: @every 1h30m, @every 5m, @every 30s"
            )

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)

        total = hours * 3600 + minutes * 60 + seconds
        if total == 0:
            raise ValueError("Interval must be greater than 0")

        return total

    def _get_next_interval_runs(
        self,
        expression: str,
        count: int,
    ) -> list[datetime]:
        """Get next N run times for interval schedule."""
        try:
            interval_seconds = self._parse_interval(expression)
            now = datetime.now(timezone.utc)
            return [now + timedelta(seconds=interval_seconds * (i + 1)) for i in range(count)]
        except ValueError:
            return []


class WebhookService:
    """Service for managing webhooks."""

    def __init__(self, storage: ScheduleStorage | None = None):
        self.storage = storage or schedule_storage

    async def create_webhook(
        self,
        request: WebhookCreate,
    ) -> tuple[WebhookResponse, str | None]:
        """Create a webhook.

        Returns:
            Tuple of (response, secret) where secret is only returned once
        """
        now = datetime.now(timezone.utc)
        webhook_id = str(uuid4())

        # Generate secret if required
        secret: str | None = None
        secret_hash: str | None = None

        if request.config.require_secret:
            secret = self._generate_secret()
            secret_hash = self._hash_secret(secret)

        webhook = WebhookState(
            id=webhook_id,
            workflow_id=request.workflow_id,
            name=request.name,
            secret_hash=secret_hash,
            allowed_ips=request.config.allowed_ips,
            headers_to_include=request.config.headers_to_include,
            params=request.params,
            enabled=request.enabled,
            created_at=now,
            updated_at=now,
        )

        await self.storage.save_webhook(webhook)

        response = webhook.to_response()
        response.secret = secret  # Only returned on create

        logger.info(f"Created webhook {webhook_id} for workflow {request.workflow_id}")

        return response, secret

    async def get_webhook(
        self,
        webhook_id: str,
        base_url: str = "",
    ) -> WebhookResponse | None:
        """Get a webhook by ID."""
        webhook = await self.storage.get_webhook(webhook_id)
        if webhook:
            return webhook.to_response(base_url)
        return None

    async def list_webhooks(
        self,
        workflow_id: str | None = None,
        enabled: bool | None = None,
        base_url: str = "",
    ) -> list[WebhookResponse]:
        """List webhooks with optional filters."""
        webhooks = await self.storage.list_webhooks(
            workflow_id=workflow_id,
            enabled=enabled,
        )
        return [w.to_response(base_url) for w in webhooks]

    async def update_webhook(
        self,
        webhook_id: str,
        request: WebhookUpdate,
        base_url: str = "",
    ) -> WebhookResponse | None:
        """Update a webhook."""
        webhook = await self.storage.get_webhook(webhook_id)
        if not webhook:
            return None

        now = datetime.now(timezone.utc)
        webhook.updated_at = now

        if request.name is not None:
            webhook.name = request.name
        if request.params is not None:
            webhook.params = request.params
        if request.enabled is not None:
            webhook.enabled = request.enabled
        if request.config:
            webhook.allowed_ips = request.config.allowed_ips
            webhook.headers_to_include = request.config.headers_to_include

        await self.storage.save_webhook(webhook)
        return webhook.to_response(base_url)

    async def delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook."""
        return await self.storage.delete_webhook(webhook_id)

    async def rotate_secret(
        self,
        webhook_id: str,
        base_url: str = "",
    ) -> tuple[WebhookResponse | None, str | None]:
        """Rotate webhook secret.

        Returns:
            Tuple of (response, new_secret)
        """
        webhook = await self.storage.get_webhook(webhook_id)
        if not webhook:
            return None, None

        secret = self._generate_secret()
        webhook.secret_hash = self._hash_secret(secret)
        webhook.updated_at = datetime.now(timezone.utc)

        await self.storage.save_webhook(webhook)

        response = webhook.to_response(base_url)
        response.secret = secret

        return response, secret

    def validate_secret(self, webhook: WebhookState, provided_secret: str) -> bool:
        """Validate provided secret against stored hash."""
        if not webhook.secret_hash:
            return True  # No secret required

        provided_hash = self._hash_secret(provided_secret)
        return secrets.compare_digest(webhook.secret_hash, provided_hash)

    def validate_ip(self, webhook: WebhookState, client_ip: str) -> bool:
        """Validate client IP against allowed list."""
        if not webhook.allowed_ips:
            return True  # No IP restriction

        # Simple exact match for now
        # Could be extended to support CIDR ranges
        return client_ip in webhook.allowed_ips

    @staticmethod
    def _generate_secret(length: int = 32) -> str:
        """Generate a cryptographically secure secret."""
        return secrets.token_urlsafe(length)

    @staticmethod
    def _hash_secret(secret: str) -> str:
        """Hash secret for storage."""
        return hashlib.sha256(secret.encode()).hexdigest()


class EventTriggerService:
    """Service for managing event triggers."""

    # Supported event types from the platform
    SUPPORTED_EVENTS = {
        "model.onboarded": {
            "source": "budapp",
            "description": "Model successfully onboarded",
        },
        "model.deleted": {
            "source": "budapp",
            "description": "Model deleted",
        },
        "benchmark.completed": {
            "source": "budapp",
            "description": "Benchmark run completed",
        },
        "benchmark.failed": {
            "source": "budapp",
            "description": "Benchmark run failed",
        },
        "cluster.healthy": {
            "source": "budcluster",
            "description": "Cluster health check passed",
        },
        "cluster.unhealthy": {
            "source": "budcluster",
            "description": "Cluster health check failed",
        },
        "deployment.created": {
            "source": "budcluster",
            "description": "New deployment created",
        },
        "deployment.failed": {
            "source": "budcluster",
            "description": "Deployment failed",
        },
    }

    def __init__(self, storage: ScheduleStorage | None = None):
        self.storage = storage or schedule_storage

    async def create_event_trigger(
        self,
        request: EventTriggerCreate,
    ) -> EventTriggerResponse:
        """Create an event trigger."""
        # Validate event type
        if request.config.event_type not in self.SUPPORTED_EVENTS:
            raise ScheduleServiceError(
                f"Unsupported event type: {request.config.event_type}. "
                f"Supported: {list(self.SUPPORTED_EVENTS.keys())}"
            )

        now = datetime.now(timezone.utc)

        trigger = EventTriggerState(
            id=str(uuid4()),
            workflow_id=request.workflow_id,
            name=request.name,
            event_type=request.config.event_type,
            filters=request.config.filters,
            params=request.params,
            enabled=request.enabled,
            created_at=now,
            updated_at=now,
        )

        await self.storage.save_event_trigger(trigger)

        logger.info(f"Created event trigger {trigger.id} for event {request.config.event_type}")

        return trigger.to_response()

    async def get_event_trigger(self, trigger_id: str) -> EventTriggerResponse | None:
        """Get an event trigger by ID."""
        trigger = await self.storage.get_event_trigger(trigger_id)
        if trigger:
            return trigger.to_response()
        return None

    async def list_event_triggers(
        self,
        event_type: str | None = None,
        workflow_id: str | None = None,
        enabled: bool | None = None,
    ) -> list[EventTriggerResponse]:
        """List event triggers with optional filters."""
        triggers = await self.storage.list_event_triggers(
            event_type=event_type,
            workflow_id=workflow_id,
            enabled=enabled,
        )
        return [t.to_response() for t in triggers]

    async def update_event_trigger(
        self,
        trigger_id: str,
        request: EventTriggerUpdate,
    ) -> EventTriggerResponse | None:
        """Update an event trigger."""
        trigger = await self.storage.get_event_trigger(trigger_id)
        if not trigger:
            return None

        now = datetime.now(timezone.utc)
        trigger.updated_at = now

        if request.name is not None:
            trigger.name = request.name
        if request.params is not None:
            trigger.params = request.params
        if request.enabled is not None:
            trigger.enabled = request.enabled
        if request.config:
            if request.config.event_type not in self.SUPPORTED_EVENTS:
                raise ScheduleServiceError(f"Unsupported event type: {request.config.event_type}")
            trigger.event_type = request.config.event_type
            trigger.filters = request.config.filters

        await self.storage.save_event_trigger(trigger)
        return trigger.to_response()

    async def delete_event_trigger(self, trigger_id: str) -> bool:
        """Delete an event trigger."""
        return await self.storage.delete_event_trigger(trigger_id)

    def get_supported_events(self) -> list[dict[str, str]]:
        """Get list of supported event types."""
        return [
            {
                "type": event_type,
                "source": info["source"],
                "description": info["description"],
            }
            for event_type, info in self.SUPPORTED_EVENTS.items()
        ]

    def matches_filters(self, event_data: dict[str, Any], filters: dict[str, Any]) -> bool:
        """Check if event data matches filter conditions.

        Supports dot notation for nested keys (e.g., "result.status").
        """
        for key, expected_value in filters.items():
            actual_value = self._get_nested_value(event_data, key)
            if actual_value != expected_value:
                return False
        return True

    @staticmethod
    def _get_nested_value(data: dict[str, Any], key: str) -> Any:
        """Get nested value using dot notation."""
        parts = key.split(".")
        value: Any = data
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value


# Global service instances
schedule_service = ScheduleService()
webhook_service = WebhookService()
event_trigger_service = EventTriggerService()
