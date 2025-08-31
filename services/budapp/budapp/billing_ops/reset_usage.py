"""Manual usage reset functionality for billing cycle updates."""

import asyncio
import json
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from budapp.billing_ops.models import UserBilling
from budapp.commons.dependencies import get_session
from budapp.commons.logging import get_logger
from budapp.shared.redis_service import RedisService


logger = get_logger(__name__)


class UsageResetService:
    """Service for resetting usage when billing cycles change."""

    def __init__(self, session: Session):
        self.session = session

    async def reset_user_usage(self, user_id: UUID, reason: str = "Manual reset") -> bool:
        """Reset usage for a specific user.

        Args:
            user_id: The user ID to reset
            reason: Reason for the reset

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current billing information
            user_billing = self.session.query(UserBilling).filter_by(user_id=user_id).first()
            if not user_billing:
                logger.warning(f"No billing record found for user {user_id}")
                return False

            # Calculate new billing cycle
            from dateutil.relativedelta import relativedelta

            now = datetime.now(timezone.utc)

            # Start new cycle from now
            billing_cycle_start = now.isoformat()
            billing_cycle_end = (now + relativedelta(months=1)).isoformat()

            # Create reset usage data
            usage_limit_info = {
                "user_id": str(user_id),
                "allowed": True,
                "status": "allowed",
                "tokens_quota": user_billing.tokens_quota,
                "tokens_used": 0,  # Reset to 0
                "cost_quota": user_billing.cost_quota,
                "cost_used": 0.0,  # Reset to 0
                "prev_tokens_used": 0,
                "prev_cost_used": 0.0,
                "reason": None,
                "reset_at": billing_cycle_end,
                "last_updated": now.isoformat(),
                "billing_cycle_start": billing_cycle_start,
                "billing_cycle_end": billing_cycle_end,
            }

            # Publish to Redis
            redis_service = RedisService()
            key = f"usage_limit:{user_id}"
            await redis_service.set(key, json.dumps(usage_limit_info), ex=3600)  # 1 hour TTL for reset

            # Also clear any cached data in gateway by publishing a clear command
            clear_key = f"usage_limit_clear:{user_id}"
            await redis_service.set(clear_key, "1", ex=10)  # Signal to clear cache

            logger.info(f"Reset usage for user {user_id}: {reason}")
            return True

        except Exception as e:
            logger.error(f"Failed to reset usage for user {user_id}: {e}")
            return False

    async def reset_all_users(self, reason: str = "Billing cycle reset") -> int:
        """Reset usage for all users with active billing.

        Args:
            reason: Reason for the reset

        Returns:
            Number of users reset
        """
        try:
            # Get all active billing users
            active_billings = self.session.query(UserBilling).filter_by(is_suspended=False).all()

            reset_count = 0
            for billing in active_billings:
                if await self.reset_user_usage(billing.user_id, reason):
                    reset_count += 1
                    await asyncio.sleep(0.01)  # Small delay to avoid Redis overload

            logger.info(f"Reset usage for {reset_count} users: {reason}")
            return reset_count

        except Exception as e:
            logger.error(f"Failed to reset all users: {e}")
            return 0

    async def reset_expired_cycles(self) -> int:
        """Reset usage for users whose billing cycle has expired.

        Returns:
            Number of users reset
        """
        try:
            from dateutil.relativedelta import relativedelta

            now = datetime.now(timezone.utc)
            reset_count = 0

            # Get all active billing users
            active_billings = self.session.query(UserBilling).filter_by(is_suspended=False).all()

            for billing in active_billings:
                if billing.created_at:
                    # Calculate if cycle should be reset
                    months_since_start = (now.year - billing.created_at.year) * 12 + (
                        now.month - billing.created_at.month
                    )
                    cycle_start = billing.created_at + relativedelta(months=months_since_start)
                    cycle_end = cycle_start + relativedelta(months=1)

                    # Check if we need to reset (past cycle end)
                    if now >= cycle_end:
                        if await self.reset_user_usage(billing.user_id, "Automatic cycle reset"):
                            reset_count += 1
                            await asyncio.sleep(0.01)

            if reset_count > 0:
                logger.info(f"Automatically reset {reset_count} expired billing cycles")

            return reset_count

        except Exception as e:
            logger.error(f"Failed to reset expired cycles: {e}")
            return 0


async def manual_reset_user(user_id: UUID):
    """Manual function to reset a specific user's usage."""
    from budapp.commons.database import SessionLocal

    session = SessionLocal()
    try:
        service = UsageResetService(session)
        success = await service.reset_user_usage(user_id, "Manual admin reset")
        return success
    finally:
        session.close()


async def reset_all_users():
    """Reset all users' usage (use with caution)."""
    from budapp.commons.database import SessionLocal

    session = SessionLocal()
    try:
        service = UsageResetService(session)
        count = await service.reset_all_users("Full system reset")
        return count
    finally:
        session.close()


async def auto_reset_expired():
    """Automatically reset expired billing cycles."""
    from budapp.commons.database import SessionLocal

    session = SessionLocal()
    try:
        service = UsageResetService(session)
        count = await service.reset_expired_cycles()
        return count
    finally:
        session.close()


# Background task to periodically check for expired cycles
class BillingCycleResetTask:
    """Background task to automatically reset expired billing cycles."""

    def __init__(self, check_interval_seconds: int = 3600):  # Check every hour
        """Initialize the reset task.

        Args:
            check_interval_seconds: How often to check for expired cycles (default: 1 hour)
        """
        self.check_interval = check_interval_seconds
        self.running = False
        self.task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the background reset task."""
        if self.running:
            logger.warning("Billing cycle reset task is already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._reset_loop())
        logger.info(f"Started billing cycle reset task with {self.check_interval}s interval")

    async def stop(self):
        """Stop the background reset task."""
        import contextlib

        self.running = False
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
            self.task = None
        logger.info("Stopped billing cycle reset task")

    async def _reset_loop(self):
        """Main reset loop that runs periodically."""
        while self.running:
            try:
                await auto_reset_expired()
            except Exception as e:
                logger.error(f"Error in billing cycle reset task: {e}")

            # Wait for next check interval
            await asyncio.sleep(self.check_interval)


# Global instance of the reset task
billing_reset_task = BillingCycleResetTask()


async def start_billing_reset_task():
    """Start the billing cycle reset task."""
    await billing_reset_task.start()


async def stop_billing_reset_task():
    """Stop the billing cycle reset task."""
    await billing_reset_task.stop()
