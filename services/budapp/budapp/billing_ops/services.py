"""Billing service for usage tracking and quota management."""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from budapp.billing_ops.models import BillingAlert, BillingPlan, UserBilling
from budapp.billing_ops.usage_cache import UsageCacheManager, UsageLimitStatus
from budapp.commons.config import app_settings
from budapp.commons.constants import UserTypeEnum
from budapp.commons.db_utils import DataManagerUtils
from budapp.commons.logging import get_logger
from budapp.user_ops.models import User


logger = get_logger(__name__)


class BillingService(DataManagerUtils):
    """Service for billing and usage tracking."""

    def __init__(self, db: Session):
        """Initialize billing service."""
        super().__init__(db)
        # Use Dapr invocation to communicate with budmetrics
        self.budmetrics_base_url = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_metrics_app_id}/method"
        self.usage_cache = UsageCacheManager()

    async def get_usage_from_clickhouse(
        self,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
        project_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Get usage data from ClickHouse via budmetrics API."""
        try:
            async with httpx.AsyncClient() as client:
                # Use the new usage/summary endpoint that queries ClickHouse directly
                params = {
                    "user_id": str(user_id),
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                }

                if project_id:
                    params["project_id"] = str(project_id)

                response = await client.get(
                    f"{self.budmetrics_base_url}/observability/usage/summary",
                    params=params,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()

                # Extract data from the response
                if result and "param" in result:
                    data = result["param"]
                    return {
                        "total_tokens": data.get("total_tokens", 0),
                        "total_cost": data.get("total_cost", 0.0),
                        "request_count": data.get("request_count", 0),
                        "success_rate": data.get("success_rate", 0.0),
                    }
                else:
                    # Return default values if no data
                    return {
                        "total_tokens": 0,
                        "total_cost": 0.0,
                        "request_count": 0,
                        "success_rate": 0.0,
                    }
        except Exception as e:
            logger.error(f"Error fetching usage from ClickHouse: {e}")
            # Return empty usage on error
            return {
                "total_tokens": 0,
                "total_cost": 0.0,
                "request_count": 0,
                "success_rate": 0.0,
            }

    def get_user_billing(self, user_id: UUID) -> Optional[UserBilling]:
        """Get user billing information."""
        stmt = select(UserBilling).where(UserBilling.user_id == user_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_billing_plan(self, plan_id: UUID) -> Optional[BillingPlan]:
        """Get billing plan details."""
        stmt = select(BillingPlan).where(BillingPlan.id == plan_id)
        return self.session.execute(stmt).scalar_one_or_none()

    async def get_current_usage(self, user_id: UUID) -> Dict[str, Any]:
        """Get current billing period usage for a user."""
        user_billing = self.get_user_billing(user_id)
        if not user_billing:
            return {
                "error": "No billing information found for user",
                "has_billing": False,
            }

        # Get usage from ClickHouse for current billing period
        usage_data = await self.get_usage_from_clickhouse(
            user_id=user_id,
            start_date=user_billing.billing_period_start,
            end_date=user_billing.billing_period_end,
        )

        # Get quotas (custom or plan defaults)
        billing_plan = self.get_billing_plan(user_billing.billing_plan_id)
        token_quota = user_billing.custom_token_quota or billing_plan.monthly_token_quota
        cost_quota = user_billing.custom_cost_quota or billing_plan.monthly_cost_quota

        # Calculate usage percentages
        token_usage_percent = (usage_data["total_tokens"] / token_quota * 100) if token_quota else 0
        cost_usage_percent = (Decimal(str(usage_data["total_cost"])) / cost_quota * 100) if cost_quota else 0

        return {
            "has_billing": True,
            "billing_period_start": user_billing.billing_period_start.isoformat(),
            "billing_period_end": user_billing.billing_period_end.isoformat(),
            "plan_name": billing_plan.name,
            "base_monthly_price": float(billing_plan.base_monthly_price),
            "usage": {
                "tokens_used": usage_data["total_tokens"],
                "tokens_quota": token_quota,
                "tokens_usage_percent": float(token_usage_percent),
                "cost_used": usage_data["total_cost"],
                "cost_quota": float(cost_quota) if cost_quota else None,
                "cost_usage_percent": float(cost_usage_percent),
                "request_count": usage_data["request_count"],
                "success_rate": usage_data["success_rate"],
            },
            "is_suspended": user_billing.is_suspended,
            "suspension_reason": user_billing.suspension_reason,
        }

    async def check_usage_limits(self, user_id: UUID, use_cache: bool = True) -> Dict[str, Any]:
        """Check if user has exceeded usage limits.

        Args:
            user_id: The user ID to check
            use_cache: Whether to use cached data (default: True)

        Returns:
            Dict with allowed status and related information
        """
        # First check if user is admin/superuser - they bypass all limits
        from budapp.user_ops.crud import UserDataManager
        from budapp.user_ops.models import User as UserModel

        user = await UserDataManager(self.session).retrieve_by_fields(UserModel, {"id": user_id}, missing_ok=True)

        # Admin users always bypass limits
        if user and user.user_type == UserTypeEnum.ADMIN:
            logger.info(f"Admin user {user_id} bypasses all usage limits")
            status = UsageLimitStatus.ALLOWED

            # Cache and publish the allowed status for admin
            await self.usage_cache.set_usage_limit_status(
                user_id=user_id,
                status=status,
                remaining_tokens=None,  # Unlimited for admin
                remaining_cost=None,  # Unlimited for admin
                reset_at=None,
                reason="Admin user - no limits",
            )

            await self.usage_cache.publish_usage_update(
                user_id=user_id,
                status=status,
                remaining_tokens=None,
                remaining_cost=None,
                reset_at=None,
                reason="Admin user - no limits",
            )

            return {
                "allowed": True,
                "reason": "Admin user - no limits",
                "remaining_tokens": None,
                "remaining_cost": None,
                "status": status.value,
            }

        # For non-admin users, check cache first
        if use_cache:
            cached_status = await self.usage_cache.get_usage_limit_status(user_id)
            if cached_status:
                logger.debug(f"Using cached usage limit status for user {user_id}")
                return cached_status

        # Get fresh usage data for non-admin users
        usage = await self.get_current_usage(user_id)

        # Determine status and cache it
        status = UsageLimitStatus.ALLOWED
        reason = None
        remaining_tokens = None
        remaining_cost = None

        if not usage.get("has_billing"):
            status = UsageLimitStatus.NO_BILLING_PLAN
            reason = "No billing plan configured"
        elif usage.get("is_suspended"):
            status = UsageLimitStatus.ACCOUNT_SUSPENDED
            reason = usage.get("suspension_reason", "Account suspended")
        elif (
            usage["usage"]["tokens_quota"] is not None
            and usage["usage"]["tokens_used"] >= usage["usage"]["tokens_quota"]
        ):
            status = UsageLimitStatus.TOKEN_LIMIT_EXCEEDED
            reason = "Monthly token quota exceeded"
        elif usage["usage"]["cost_quota"] is not None and usage["usage"]["cost_used"] >= usage["usage"]["cost_quota"]:
            status = UsageLimitStatus.COST_LIMIT_EXCEEDED
            reason = "Monthly cost quota exceeded"
        else:
            # Calculate remaining quotas
            if usage["usage"]["tokens_quota"] is not None:
                remaining_tokens = usage["usage"]["tokens_quota"] - usage["usage"]["tokens_used"]
            if usage["usage"]["cost_quota"] is not None:
                remaining_cost = usage["usage"]["cost_quota"] - usage["usage"]["cost_used"]

        # Get billing period end for reset time
        reset_at = None
        if usage.get("billing_period_end"):
            reset_at = datetime.fromisoformat(usage["billing_period_end"])

        # Cache the status
        await self.usage_cache.set_usage_limit_status(
            user_id=user_id,
            status=status,
            remaining_tokens=remaining_tokens,
            remaining_cost=remaining_cost,
            reset_at=reset_at,
            reason=reason,
        )

        # Always publish update to keep gateway cache synchronized
        await self.usage_cache.publish_usage_update(
            user_id=user_id,
            status=status,
            remaining_tokens=remaining_tokens,
            remaining_cost=remaining_cost,
            reset_at=reset_at,
            reason=reason,
        )

        return {
            "allowed": status == UsageLimitStatus.ALLOWED,
            "reason": reason,
            "remaining_tokens": remaining_tokens,
            "remaining_cost": remaining_cost,
            "status": status.value,
        }

    async def get_usage_history(
        self,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "daily",
    ) -> Dict[str, Any]:
        """Get historical usage data with specified granularity."""
        try:
            async with httpx.AsyncClient() as client:
                # Use the new usage/history endpoint that queries ClickHouse directly
                params = {
                    "user_id": str(user_id),
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "granularity": granularity,
                }

                response = await client.get(
                    f"{self.budmetrics_base_url}/observability/usage/history",
                    params=params,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()

                # Extract data from the response
                if result and "param" in result:
                    return result["param"]  # Already contains {"data": [...]}
                else:
                    return {"data": []}
        except Exception as e:
            logger.error(f"Error fetching usage history: {e}")
            return {"error": str(e), "data": []}

    def get_billing_alerts(self, user_id: UUID) -> List[BillingAlert]:
        """Get all billing alerts for a user."""
        user_billing = self.get_user_billing(user_id)
        if not user_billing:
            return []

        stmt = select(BillingAlert).where(
            BillingAlert.user_billing_id == user_billing.id,
            BillingAlert.is_active,
        )
        return list(self.session.execute(stmt).scalars().all())

    async def check_and_trigger_alerts(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Check usage against alert thresholds and return triggered alerts."""
        usage = await self.get_current_usage(user_id)
        if not usage.get("has_billing"):
            return []

        alerts = self.get_billing_alerts(user_id)
        triggered_alerts = []

        for alert in alerts:
            should_trigger = False
            current_value = None

            if alert.alert_type == "token_usage":
                current_percent = usage["usage"]["tokens_usage_percent"]
                current_value = usage["usage"]["tokens_used"]
                should_trigger = current_percent >= alert.threshold_percent
            elif alert.alert_type == "cost_usage":
                current_percent = usage["usage"]["cost_usage_percent"]
                current_value = usage["usage"]["cost_used"]
                should_trigger = current_percent >= alert.threshold_percent

            # Check if we should trigger (and haven't already for this value)
            if should_trigger:
                if (
                    not alert.last_triggered_at
                    or alert.last_triggered_value != current_value
                    or (datetime.now(timezone.utc) - alert.last_triggered_at).days >= 1
                ):
                    # Update alert
                    alert.last_triggered_at = datetime.now(timezone.utc)
                    alert.last_triggered_value = Decimal(str(current_value))
                    self.session.commit()

                    triggered_alerts.append(
                        {
                            "alert_name": alert.name,
                            "alert_type": alert.alert_type,
                            "threshold_percent": alert.threshold_percent,
                            "current_value": current_value,
                            "current_percent": current_percent,
                        }
                    )

        return triggered_alerts

    def create_user_billing(
        self,
        user_id: UUID,
        billing_plan_id: UUID,
        custom_token_quota: Optional[int] = None,
        custom_cost_quota: Optional[Decimal] = None,
    ) -> UserBilling:
        """Create billing configuration for a user."""
        # Calculate billing period (monthly)
        now = datetime.now(timezone.utc)
        billing_period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Get next month
        if billing_period_start.month == 12:
            billing_period_end = billing_period_start.replace(year=billing_period_start.year + 1, month=1)
        else:
            billing_period_end = billing_period_start.replace(month=billing_period_start.month + 1)

        user_billing = UserBilling(
            user_id=user_id,
            billing_plan_id=billing_plan_id,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
            custom_token_quota=custom_token_quota,
            custom_cost_quota=custom_cost_quota,
        )

        self.session.add(user_billing)
        self.session.commit()
        self.session.refresh(user_billing)

        return user_billing

    def update_billing_period(self, user_billing: UserBilling) -> None:
        """Update billing period to next month."""
        user_billing.billing_period_start = user_billing.billing_period_end

        # Calculate next period end
        if user_billing.billing_period_end.month == 12:
            user_billing.billing_period_end = user_billing.billing_period_end.replace(
                year=user_billing.billing_period_end.year + 1, month=1
            )
        else:
            user_billing.billing_period_end = user_billing.billing_period_end.replace(
                month=user_billing.billing_period_end.month + 1
            )

        self.session.commit()

    async def handle_usage_update(
        self, user_id: UUID, tokens_used: int, cost_incurred: float, endpoint_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle real-time usage update from budmetrics.

        Args:
            user_id: The user ID
            tokens_used: Number of tokens used in the request
            cost_incurred: Cost incurred in the request
            endpoint_id: Optional endpoint/model ID that was used

        Returns:
            Dict with updated usage status
        """
        # Check if user is admin first - they always get allowed status
        from budapp.user_ops.crud import UserDataManager
        from budapp.user_ops.models import User as UserModel

        user = await UserDataManager(self.session).retrieve_by_fields(UserModel, {"id": user_id}, missing_ok=True)

        if user and user.user_type == UserTypeEnum.ADMIN:
            logger.debug(f"Admin user {user_id} in usage update - always allowed")
            status = UsageLimitStatus.ALLOWED

            # Still track usage for admin users (for analytics)
            counters = await self.usage_cache.increment_usage_counter(user_id, tokens_used, cost_incurred)

            # Publish allowed status for admin
            await self.usage_cache.publish_usage_update(
                user_id=user_id,
                status=status,
                remaining_tokens=None,
                remaining_cost=None,
                reset_at=None,
                reason="Admin user - no limits",
                metadata={
                    "endpoint_id": endpoint_id,
                    "tokens_used": tokens_used,
                    "cost_incurred": cost_incurred,
                },
            )

            return {
                "status": status.value,
                "allowed": True,
                "reason": "Admin user - no limits",
                "remaining_tokens": None,
                "remaining_cost": None,
                "usage_today": {
                    "tokens": counters["tokens_today"],
                    "cost": counters["cost_today_cents"] / 100.0,
                },
            }

        # For non-admin users, proceed with normal usage tracking
        counters = await self.usage_cache.increment_usage_counter(user_id, tokens_used, cost_incurred)

        # Get current billing info (from cache if available)
        cached_billing = await self.usage_cache.get_cached_billing_info(user_id)

        if not cached_billing:
            # Fetch and cache billing info
            user_billing = self.get_user_billing(user_id)
            if user_billing:
                billing_plan = self.get_billing_plan(user_billing.billing_plan_id)
                token_quota = user_billing.custom_token_quota or billing_plan.monthly_token_quota
                cost_quota = user_billing.custom_cost_quota or billing_plan.monthly_cost_quota

                await self.usage_cache.cache_user_billing_info(
                    user_id=user_id,
                    billing_plan_id=user_billing.billing_plan_id,
                    token_quota=token_quota,
                    cost_quota=cost_quota,
                    billing_period_end=user_billing.billing_period_end,
                    is_suspended=user_billing.is_suspended,
                )

                cached_billing = {
                    "token_quota": token_quota,
                    "cost_quota": float(cost_quota) if cost_quota else None,
                    "billing_period_end": user_billing.billing_period_end.isoformat(),
                    "is_suspended": user_billing.is_suspended,
                }

        # Check if limits are exceeded
        status = UsageLimitStatus.ALLOWED
        reason = None

        if cached_billing:
            if cached_billing.get("is_suspended"):
                status = UsageLimitStatus.ACCOUNT_SUSPENDED
                reason = "Account suspended"
            elif (
                cached_billing.get("token_quota") is not None
                and counters["tokens_today"] >= cached_billing["token_quota"]
            ):
                status = UsageLimitStatus.TOKEN_LIMIT_EXCEEDED
                reason = "Daily token quota exceeded"
            elif cached_billing.get("cost_quota") is not None:
                cost_today = counters["cost_today_cents"] / 100.0
                if cost_today >= cached_billing["cost_quota"]:
                    status = UsageLimitStatus.COST_LIMIT_EXCEEDED
                    reason = "Daily cost quota exceeded"

        # Update cache with new status
        remaining_tokens = None
        remaining_cost = None

        if cached_billing and status == UsageLimitStatus.ALLOWED:
            if cached_billing.get("token_quota") is not None:
                remaining_tokens = cached_billing["token_quota"] - counters["tokens_today"]
            if cached_billing.get("cost_quota") is not None:
                remaining_cost = cached_billing["cost_quota"] - (counters["cost_today_cents"] / 100.0)

        reset_at = datetime.fromisoformat(cached_billing["billing_period_end"]) if cached_billing else None

        await self.usage_cache.set_usage_limit_status(
            user_id=user_id,
            status=status,
            remaining_tokens=remaining_tokens,
            remaining_cost=remaining_cost,
            reset_at=reset_at,
            reason=reason,
        )

        # Always publish update to keep gateway cache synchronized
        await self.usage_cache.publish_usage_update(
            user_id=user_id,
            status=status,
            remaining_tokens=remaining_tokens,
            remaining_cost=remaining_cost,
            reset_at=reset_at,
            reason=reason,
            metadata={
                "endpoint_id": endpoint_id,
                "tokens_used": tokens_used,
                "cost_incurred": cost_incurred,
            },
        )

        return {
            "status": status.value,
            "allowed": status == UsageLimitStatus.ALLOWED,
            "reason": reason,
            "remaining_tokens": remaining_tokens,
            "remaining_cost": remaining_cost,
            "usage_today": {
                "tokens": counters["tokens_today"],
                "cost": counters["cost_today_cents"] / 100.0,
            },
        }

    async def refresh_user_cache(self, user_id: UUID) -> bool:
        """Refresh all cached data for a user.

        Args:
            user_id: The user ID

        Returns:
            True if successful, False otherwise
        """
        try:
            # Invalidate existing cache
            await self.usage_cache.invalidate_user_cache(user_id)

            # Re-check usage limits to populate cache
            await self.check_usage_limits(user_id, use_cache=False)

            # Cache billing info
            user_billing = self.get_user_billing(user_id)
            if user_billing:
                billing_plan = self.get_billing_plan(user_billing.billing_plan_id)
                token_quota = user_billing.custom_token_quota or billing_plan.monthly_token_quota
                cost_quota = user_billing.custom_cost_quota or billing_plan.monthly_cost_quota

                await self.usage_cache.cache_user_billing_info(
                    user_id=user_id,
                    billing_plan_id=user_billing.billing_plan_id,
                    token_quota=token_quota,
                    cost_quota=cost_quota,
                    billing_period_end=user_billing.billing_period_end,
                    is_suspended=user_billing.is_suspended,
                )

                # The check_usage_limits call above already publishes the update
                # No need for separate billing update since we removed that channel

            return True
        except Exception as e:
            logger.error(f"Failed to refresh user cache: {e}")
            return False
