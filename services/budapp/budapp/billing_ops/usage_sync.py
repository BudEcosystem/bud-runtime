"""Background task to periodically sync usage limits to Redis for gateway consumption."""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from budapp.billing_ops.services import BillingService
from budapp.commons.dependencies import get_session
from budapp.commons.logging import get_logger


logger = get_logger(__name__)


class UsageLimitSyncTask:
    """Periodically syncs usage limits to Redis for gateway to consume."""

    def __init__(self, sync_interval_seconds: int = 30):
        """Initialize the sync task.

        Args:
            sync_interval_seconds: How often to sync usage limits (default: 30 seconds)

        Note: Redis TTL for usage limits is set to 60 seconds in BillingService.check_usage_limits()
        to ensure data availability between sync intervals.
        """
        self.sync_interval = sync_interval_seconds
        self.running = False
        self.task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the background sync task."""
        if self.running:
            logger.warning("Usage limit sync task is already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._sync_loop())
        logger.info(f"Started usage limit sync task with {self.sync_interval}s interval")

    async def stop(self):
        """Stop the background sync task."""
        import contextlib

        self.running = False
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
            self.task = None
        logger.info("Stopped usage limit sync task")

    async def _sync_loop(self):
        """Main sync loop that runs periodically."""
        while self.running:
            try:
                await self._sync_active_users()
            except Exception as e:
                logger.error(f"Error in usage limit sync: {e}")

            # Wait for next sync interval
            await asyncio.sleep(self.sync_interval)

    async def _sync_active_users(self):
        """Sync usage limits for all active users."""
        from budapp.commons.database import SessionLocal

        session = None
        try:
            # Create a database session directly
            session = SessionLocal()
            service = BillingService(session)

            # Get all users with active billing plans
            from budapp.billing_ops.models import UserBilling
            from budapp.commons.constants import UserTypeEnum
            from budapp.user_ops.models import User as UserModel

            # Query active users with billing plans
            active_users = (
                session.query(UserModel)
                .join(UserBilling, UserModel.id == UserBilling.user_id)
                .filter(~UserBilling.is_suspended)
                .all()
            )

            # Also get admin users (they always have unlimited access)
            admin_users = session.query(UserModel).filter(UserModel.user_type == UserTypeEnum.ADMIN).all()

            # Combine and deduplicate
            all_users = list({user.id: user for user in active_users + admin_users}.values())

            logger.debug(f"Syncing usage limits for {len(all_users)} users")

            # Sync each user's usage limits
            for user in all_users:
                try:
                    # Check and publish usage limits
                    # This will update Redis with the latest usage status
                    await service.check_usage_limits(user.id)
                except Exception as e:
                    logger.warning(f"Failed to sync usage limits for user {user.id}: {e}")

        except Exception as e:
            logger.error(f"Failed to sync active users: {e}")
        finally:
            if session:
                session.close()


# Global instance of the sync task
usage_sync_task = UsageLimitSyncTask()


async def start_usage_sync():
    """Start the usage limit sync task."""
    await usage_sync_task.start()


async def stop_usage_sync():
    """Stop the usage limit sync task."""
    await usage_sync_task.stop()
