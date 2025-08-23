"""Usage cache manager for real-time billing limit enforcement."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from budapp.commons.logging import get_logger
from budapp.shared.redis_service import RedisService


logger = get_logger(__name__)


class UsageLimitStatus(Enum):
    """Usage limit status enum."""

    ALLOWED = "allowed"
    TOKEN_LIMIT_EXCEEDED = "token_limit_exceeded"
    COST_LIMIT_EXCEEDED = "cost_limit_exceeded"
    ACCOUNT_SUSPENDED = "account_suspended"
    NO_BILLING_PLAN = "no_billing_plan"


class UsageCacheManager:
    """Manages usage cache for real-time limit enforcement."""

    # Cache key patterns
    USAGE_LIMIT_KEY = "usage_limits:{user_id}"
    USAGE_COUNTER_KEY = "usage_counter:{user_id}:{date}"
    USER_BILLING_KEY = "user_billing:{user_id}"
    API_KEY_USER_MAP = "api_key_user:{api_key}"

    # Cache TTLs (in seconds)
    LIMIT_CACHE_TTL = 300  # 5 minutes
    COUNTER_CACHE_TTL = 86400  # 24 hours
    BILLING_CACHE_TTL = 600  # 10 minutes
    API_KEY_MAP_TTL = 3600  # 1 hour

    # Pub/Sub channels
    USAGE_UPDATE_CHANNEL = "usage_limit_updates"

    def __init__(self):
        """Initialize the usage cache manager."""
        self.redis_service = RedisService()

    async def get_usage_limit_status(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Get cached usage limit status for a user.

        Args:
            user_id: The user ID

        Returns:
            Dict with usage limit status or None if not cached
        """
        try:
            key = self.USAGE_LIMIT_KEY.format(user_id=str(user_id))
            cached_data = await self.redis_service.get(key)

            if cached_data:
                return json.loads(cached_data)
            return None

        except Exception as e:
            logger.warning(f"Failed to get usage limit status from cache: {e}")
            return None

    async def set_usage_limit_status(
        self,
        user_id: UUID,
        status: UsageLimitStatus,
        remaining_tokens: Optional[int] = None,
        remaining_cost: Optional[float] = None,
        reset_at: Optional[datetime] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Cache usage limit status for a user.

        Args:
            user_id: The user ID
            status: The usage limit status
            remaining_tokens: Remaining token quota
            remaining_cost: Remaining cost quota
            reset_at: When the limits reset
            reason: Reason for the status

        Returns:
            True if successfully cached, False otherwise
        """
        try:
            key = self.USAGE_LIMIT_KEY.format(user_id=str(user_id))
            cache_data = {
                "status": status.value,
                "allowed": status == UsageLimitStatus.ALLOWED,
                "remaining_tokens": remaining_tokens,
                "remaining_cost": remaining_cost,
                "reset_at": reset_at.isoformat() if reset_at else None,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            await self.redis_service.set(key, json.dumps(cache_data), ex=self.LIMIT_CACHE_TTL)
            return True

        except Exception as e:
            logger.error(f"Failed to set usage limit status in cache: {e}")
            return False

    async def increment_usage_counter(self, user_id: UUID, tokens_used: int, cost_incurred: float) -> Dict[str, int]:
        """Increment usage counters for a user.

        Args:
            user_id: The user ID
            tokens_used: Number of tokens used
            cost_incurred: Cost incurred in this request

        Returns:
            Dict with updated counter values
        """
        try:
            date_str = datetime.now(timezone.utc).date().isoformat()

            # Token counter key
            token_key = f"{self.USAGE_COUNTER_KEY.format(user_id=str(user_id), date=date_str)}:tokens"
            # Cost counter key (stored as cents to avoid float precision issues)
            cost_key = f"{self.USAGE_COUNTER_KEY.format(user_id=str(user_id), date=date_str)}:cost"

            # Increment counters atomically
            new_token_count = await self.redis_service.incr(token_key)

            # Convert cost to cents for storage
            cost_cents = int(cost_incurred * 100)
            if cost_cents > 0:
                new_cost_cents = await self.redis_service.incr(cost_key)
            else:
                # Get current value without incrementing if cost is 0
                current_cost = await self.redis_service.get(cost_key)
                new_cost_cents = int(current_cost) if current_cost else 0

            # Set TTL on first increment
            await self.redis_service.ttl(token_key)
            if await self.redis_service.ttl(token_key) == -1:
                await self.redis_service.set(token_key, str(new_token_count), ex=self.COUNTER_CACHE_TTL, xx=True)

            if cost_cents > 0 and await self.redis_service.ttl(cost_key) == -1:
                await self.redis_service.set(cost_key, str(new_cost_cents), ex=self.COUNTER_CACHE_TTL, xx=True)

            return {
                "tokens_today": new_token_count,
                "cost_today_cents": new_cost_cents,
            }

        except Exception as e:
            logger.error(f"Failed to increment usage counter: {e}")
            return {"tokens_today": 0, "cost_today_cents": 0}

    async def get_usage_counters(self, user_id: UUID) -> Dict[str, Any]:
        """Get current usage counters for a user.

        Args:
            user_id: The user ID

        Returns:
            Dict with current usage counter values
        """
        try:
            date_str = datetime.now(timezone.utc).date().isoformat()
            token_key = f"{self.USAGE_COUNTER_KEY.format(user_id=str(user_id), date=date_str)}:tokens"
            cost_key = f"{self.USAGE_COUNTER_KEY.format(user_id=str(user_id), date=date_str)}:cost"

            token_count = await self.redis_service.get(token_key)
            cost_cents = await self.redis_service.get(cost_key)

            return {
                "tokens_today": int(token_count) if token_count else 0,
                "cost_today": (int(cost_cents) / 100.0) if cost_cents else 0.0,
                "date": date_str,
            }

        except Exception as e:
            logger.warning(f"Failed to get usage counters: {e}")
            return {"tokens_today": 0, "cost_today": 0.0, "date": datetime.now(timezone.utc).date().isoformat()}

    async def cache_user_billing_info(
        self,
        user_id: UUID,
        billing_plan_id: UUID,
        token_quota: Optional[int],
        cost_quota: Optional[Decimal],
        billing_period_end: datetime,
        is_suspended: bool = False,
    ) -> bool:
        """Cache user billing information for quick access.

        Args:
            user_id: The user ID
            billing_plan_id: The billing plan ID
            token_quota: Monthly token quota
            cost_quota: Monthly cost quota
            billing_period_end: End of current billing period
            is_suspended: Whether account is suspended

        Returns:
            True if successfully cached, False otherwise
        """
        try:
            key = self.USER_BILLING_KEY.format(user_id=str(user_id))
            billing_data = {
                "billing_plan_id": str(billing_plan_id),
                "token_quota": token_quota,
                "cost_quota": float(cost_quota) if cost_quota else None,
                "billing_period_end": billing_period_end.isoformat(),
                "is_suspended": is_suspended,
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }

            await self.redis_service.set(key, json.dumps(billing_data), ex=self.BILLING_CACHE_TTL)
            return True

        except Exception as e:
            logger.error(f"Failed to cache user billing info: {e}")
            return False

    async def get_cached_billing_info(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Get cached billing information for a user.

        Args:
            user_id: The user ID

        Returns:
            Dict with billing info or None if not cached
        """
        try:
            key = self.USER_BILLING_KEY.format(user_id=str(user_id))
            cached_data = await self.redis_service.get(key)

            if cached_data:
                return json.loads(cached_data)
            return None

        except Exception as e:
            logger.warning(f"Failed to get billing info from cache: {e}")
            return None

    async def map_api_key_to_user(self, api_key: str, user_id: UUID) -> bool:
        """Map an API key to a user ID for quick lookup.

        Args:
            api_key: The API key
            user_id: The user ID

        Returns:
            True if successfully mapped, False otherwise
        """
        try:
            key = self.API_KEY_USER_MAP.format(api_key=api_key)
            await self.redis_service.set(key, str(user_id), ex=self.API_KEY_MAP_TTL)
            return True

        except Exception as e:
            logger.error(f"Failed to map API key to user: {e}")
            return False

    async def get_user_id_from_api_key(self, api_key: str) -> Optional[UUID]:
        """Get user ID from API key mapping.

        Args:
            api_key: The API key

        Returns:
            User ID or None if not found
        """
        try:
            key = self.API_KEY_USER_MAP.format(api_key=api_key)
            user_id_str = await self.redis_service.get(key)

            if user_id_str:
                return UUID(user_id_str)
            return None

        except Exception as e:
            logger.warning(f"Failed to get user ID from API key: {e}")
            return None

    async def publish_usage_update(
        self,
        user_id: UUID,
        status: UsageLimitStatus,
        remaining_tokens: Optional[int] = None,
        remaining_cost: Optional[float] = None,
        reset_at: Optional[datetime] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Publish usage limit update to Redis pub/sub.

        Args:
            user_id: The user ID
            status: The new usage limit status
            remaining_tokens: Remaining token quota
            remaining_cost: Remaining cost quota
            reset_at: When the limits reset
            reason: Reason for the status
            metadata: Additional metadata to include

        Returns:
            True if successfully published, False otherwise
        """
        try:
            # Build update message with all fields expected by gateway
            update_message = {
                "user_id": str(user_id),
                "status": status.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Add metadata fields that gateway expects
            if metadata:
                update_message["metadata"] = metadata
            else:
                update_message["metadata"] = {}

            # Ensure gateway-expected fields are in metadata
            if remaining_tokens is not None:
                update_message["metadata"]["remaining_tokens"] = remaining_tokens
            if remaining_cost is not None:
                update_message["metadata"]["remaining_cost"] = remaining_cost
            if reason is not None:
                update_message["metadata"]["reason"] = reason
            if reset_at is not None:
                update_message["metadata"]["reset_at"] = reset_at.isoformat()

            # Use Redis pub/sub to notify gateway
            async with self.redis_service.redis_singleton as redis:
                await redis.publish(self.USAGE_UPDATE_CHANNEL, json.dumps(update_message))

            logger.debug(f"Published usage update for user {user_id}: {status.value}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish usage update: {e}")
            return False

    async def invalidate_user_cache(self, user_id: UUID) -> bool:
        """Invalidate all cached data for a user.

        Args:
            user_id: The user ID

        Returns:
            True if successfully invalidated, False otherwise
        """
        try:
            keys_to_delete = [
                self.USAGE_LIMIT_KEY.format(user_id=str(user_id)),
                self.USER_BILLING_KEY.format(user_id=str(user_id)),
            ]

            # Also delete today's counters
            date_str = datetime.now(timezone.utc).date().isoformat()
            keys_to_delete.extend(
                [
                    f"{self.USAGE_COUNTER_KEY.format(user_id=str(user_id), date=date_str)}:tokens",
                    f"{self.USAGE_COUNTER_KEY.format(user_id=str(user_id), date=date_str)}:cost",
                ]
            )

            await self.redis_service.delete(*keys_to_delete)
            logger.info(f"Invalidated cache for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to invalidate user cache: {e}")
            return False

    async def reset_daily_counters(self, user_id: UUID) -> bool:
        """Reset daily usage counters for a user.

        Args:
            user_id: The user ID

        Returns:
            True if successfully reset, False otherwise
        """
        try:
            date_str = datetime.now(timezone.utc).date().isoformat()
            keys_to_delete = [
                f"{self.USAGE_COUNTER_KEY.format(user_id=str(user_id), date=date_str)}:tokens",
                f"{self.USAGE_COUNTER_KEY.format(user_id=str(user_id), date=date_str)}:cost",
            ]

            await self.redis_service.delete(*keys_to_delete)
            logger.info(f"Reset daily counters for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to reset daily counters: {e}")
            return False
