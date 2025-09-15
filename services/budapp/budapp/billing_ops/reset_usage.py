"""Manual usage reset functionality for billing cycle updates."""

import asyncio
import contextlib
import json
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from budapp.billing_ops.models import UserBilling
from budapp.billing_ops.services import BillingService
from budapp.commons.constants import UserTypeEnum
from budapp.commons.database import SessionLocal
from budapp.commons.dependencies import get_session
from budapp.commons.logging import get_logger
from budapp.shared.redis_service import RedisService
from budapp.user_ops.models import User as UserModel


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
            billing_service = BillingService(self.session)

            # Get user information to determine user type - use modern select
            stmt = select(UserModel).where(UserModel.id == user_id)
            user = self.session.execute(stmt).scalar_one_or_none()
            user_type = user.user_type if user else UserTypeEnum.CLIENT

            user_billing = billing_service.get_user_billing(user_id)
            if not user_billing:
                logger.warning(f"No current billing record found for user {user_id}")
                return False

            # Get current time
            now = datetime.now(timezone.utc)

            # Check if current billing cycle has expired - simple comparison
            if user_billing.billing_period_end <= now:
                # Create new billing cycle entry (preserves history)
                user_billing = billing_service.create_next_billing_cycle(user_id)
                logger.info(
                    f"Created new billing cycle for user {user_id}: "
                    f"{user_billing.billing_period_start.isoformat()} to {user_billing.billing_period_end.isoformat()}"
                )

            # Get effective quotas from current billing record
            billing_plan = billing_service.get_billing_plan(user_billing.billing_plan_id)

            tokens_quota = user_billing.custom_token_quota or (
                billing_plan.monthly_token_quota if billing_plan else None
            )
            cost_quota = user_billing.custom_cost_quota or (billing_plan.monthly_cost_quota if billing_plan else None)

            # Create reset usage data
            usage_limit_info = {
                "user_id": str(user_id),
                "user_type": user_type.value if user_type else "client",
                "allowed": True,
                "status": "admin_unlimited" if user_type == UserTypeEnum.ADMIN else "allowed",
                "tokens_quota": tokens_quota,
                "tokens_used": 0,  # Reset to 0
                "cost_quota": float(cost_quota) if cost_quota else None,
                "cost_used": 0.0,  # Reset to 0
                "prev_tokens_used": 0,
                "prev_cost_used": 0.0,
                "reason": reason if user_type != UserTypeEnum.ADMIN else "Admin user - unlimited access",
                "reset_at": user_billing.billing_period_end.isoformat(),
                "last_updated": now.isoformat(),
                "billing_cycle_start": user_billing.billing_period_start.isoformat(),
                "billing_cycle_end": user_billing.billing_period_end.isoformat(),
            }

            # Publish to Redis with single 90-minute TTL (consistent with hybrid sync)
            redis_service = RedisService()
            key = f"usage_limit:{user_id}"
            data = json.dumps(usage_limit_info)
            ttl_seconds = 90 * 60  # 90 minutes (consistent with main system)

            await redis_service.set(key, data, ex=ttl_seconds)

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
            # Get all current active billing users (not suspended)
            stmt = select(UserBilling).where(
                UserBilling.is_current, UserBilling.is_suspended.is_(False), UserBilling.is_active
            )
            active_billings = self.session.execute(stmt).scalars().all()

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
            now = datetime.now(timezone.utc)
            reset_count = 0

            # Directly query for expired billing cycles - much more efficient
            stmt = select(UserBilling).where(
                UserBilling.is_current,
                UserBilling.is_suspended.is_(False),
                UserBilling.is_active,
                UserBilling.billing_period_end <= now,
            )
            expired_billings = self.session.execute(stmt).scalars().all()

            for billing in expired_billings:
                logger.info(
                    f"Resetting expired cycle for user {billing.user_id}: "
                    f"cycle ended {billing.billing_period_end.isoformat()}, now={now.isoformat()}"
                )

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
    session = SessionLocal()
    try:
        service = UsageResetService(session)
        success = await service.reset_user_usage(user_id, "Manual admin reset")
        return success
    finally:
        session.close()


async def reset_all_users():
    """Reset all users' usage (use with caution)."""
    session = SessionLocal()
    try:
        service = UsageResetService(session)
        count = await service.reset_all_users("Full system reset")
        return count
    finally:
        session.close()


async def auto_reset_expired():
    """Automatically reset expired billing cycles."""
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
