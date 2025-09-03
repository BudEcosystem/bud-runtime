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
from budapp.commons.config import app_settings
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

    def get_free_billing_plan(self) -> Optional[Dict[str, Any]]:
        """Get the Free billing plan from database."""
        stmt = select(BillingPlan).where(BillingPlan.name.ilike("%free%"), BillingPlan.is_active)
        free_plan = self.session.execute(stmt).scalar_one_or_none()
        if free_plan:
            return {
                "name": free_plan.name,
                "base_monthly_price": free_plan.base_monthly_price,
                "monthly_token_quota": free_plan.monthly_token_quota,
                "monthly_cost_quota": free_plan.monthly_cost_quota,
                "max_projects": free_plan.max_projects,
                "max_endpoints_per_project": free_plan.max_endpoints_per_project,
            }
        return None

    def _get_default_free_plan(self) -> Dict[str, Any]:
        """Get default Free plan configuration when not in database."""
        return {
            "name": "Free",
            "base_monthly_price": 0,
            "monthly_token_quota": 100000,  # 100K tokens
            "monthly_cost_quota": None,  # No cost limit for free tier
            "max_projects": 2,
            "max_endpoints_per_project": 3,
        }

    async def get_current_usage(self, user_id: UUID) -> Dict[str, Any]:
        """Get current billing period usage for a user."""
        user_billing = self.get_user_billing(user_id)
        if not user_billing:
            # Try to get the Free plan as default
            free_plan = self.get_free_billing_plan()
            if not free_plan:
                # Create a virtual Free plan if it doesn't exist in DB
                free_plan = self._get_default_free_plan()

            # For Free plan users, we still need dates for ClickHouse query but return None in response
            now = datetime.now(timezone.utc)
            billing_period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Calculate end of month for internal use
            if billing_period_start.month == 12:
                billing_period_end = billing_period_start.replace(
                    year=billing_period_start.year + 1, month=1
                ) - timedelta(seconds=1)
            else:
                billing_period_end = billing_period_start.replace(month=billing_period_start.month + 1) - timedelta(
                    seconds=1
                )

            # Get actual usage from ClickHouse even for Free plan users
            usage_data = await self.get_usage_from_clickhouse(
                user_id=user_id,
                start_date=billing_period_start,
                end_date=billing_period_end,
            )

            # Get Free plan quotas
            token_quota = free_plan.get("monthly_token_quota", 100000)  # Default 100K tokens for free
            cost_quota = free_plan.get("monthly_cost_quota", None)  # No cost limit for free tier

            # Calculate usage percentages
            token_usage_percent = (usage_data["total_tokens"] / token_quota * 100) if token_quota else 0
            cost_usage_percent = (Decimal(str(usage_data["total_cost"])) / cost_quota * 100) if cost_quota else 0

            return {
                "has_billing": True,  # We're treating free plan as having billing
                "billing_period_start": None,  # Return None for Free plan users
                "billing_period_end": None,  # Return None for Free plan users
                "plan_name": free_plan.get("name", "Free"),
                "billing_plan_id": None,  # Return None for Free plan users
                "base_monthly_price": float(free_plan.get("base_monthly_price", 0)),
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
                "is_suspended": False,
                "suspension_reason": None,
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
            "billing_plan_id": user_billing.billing_plan_id,
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

    async def check_usage_limits(self, user_id: UUID) -> Dict[str, Any]:
        """Check if user has exceeded usage limits and publish to Redis."""
        import json
        from datetime import datetime, timezone

        from budapp.shared.redis_service import RedisService

        """Check if user has exceeded usage limits."""
        usage = await self.get_current_usage(user_id)

        # Now all users have billing (at least Free plan)
        if usage.get("is_suspended"):
            return {"allowed": False, "reason": usage.get("suspension_reason", "Account suspended")}

        # Check token limit
        if usage["usage"]["tokens_quota"] and usage["usage"]["tokens_used"] >= usage["usage"]["tokens_quota"]:
            plan_name = usage.get("plan_name", "your plan")
            return {"allowed": False, "reason": f"Monthly token quota exceeded for {plan_name}"}

        # Check cost limit (Free plan has no cost limit)
        if usage["usage"]["cost_quota"] and usage["usage"]["cost_used"] >= usage["usage"]["cost_quota"]:
            return {"allowed": False, "reason": "Monthly cost quota exceeded"}

        # Get current usage values
        tokens_used = usage["usage"]["tokens_used"] if usage.get("usage") else 0
        cost_used = usage["usage"]["cost_used"] if usage.get("usage") else 0.0
        tokens_quota = usage["usage"]["tokens_quota"] if usage.get("usage") else None
        cost_quota = usage["usage"]["cost_quota"] if usage.get("usage") else None

        # Get previous values from Redis (for delta calculation)
        existing_data = None
        prev_tokens_used = tokens_used  # Default to current values
        prev_cost_used = cost_used
        try:
            logger.info(f"usage sync for user {user_id}")
            redis_service = RedisService()
            key = f"usage_limit:{user_id}"
            existing_data = await redis_service.get(key)
            if existing_data:
                existing = json.loads(existing_data)
                # Use the previous values stored in Redis for delta calculation
                # These represent the last known state from the previous sync
                prev_tokens_used = existing.get("tokens_used", tokens_used)
                prev_cost_used = existing.get("cost_used", cost_used)
        except Exception as e:
            logger.warning(f"Failed to get previous usage from Redis: {e}")
            # Keep the defaults (current values) if Redis fails

        # Get billing cycle information
        billing_cycle_start = None
        billing_cycle_end = None
        if usage.get("has_billing"):
            # Get billing cycle from user billing record
            from budapp.billing_ops.models import UserBilling
            from budapp.billing_ops.utils import calculate_billing_cycle

            user_billing = self.session.query(UserBilling).filter_by(user_id=user_id).first()
            if user_billing and user_billing.created_at:
                billing_cycle_start, billing_cycle_end = calculate_billing_cycle(user_billing.created_at)

        # Check if this is a new billing cycle
        if existing_data and billing_cycle_start:
            existing = json.loads(existing_data)
            old_cycle_start = existing.get("billing_cycle_start")
            if old_cycle_start != billing_cycle_start:
                # New billing cycle detected - reset current usage but keep previous values
                # The prev_* values should be the last known values from the previous cycle
                # This allows the gateway to calculate proper deltas
                tokens_used = 0
                cost_used = 0.0
                # prev_tokens_used and prev_cost_used already set from existing data above
                logger.info(f"Billing cycle reset for user {user_id}: new cycle starts {billing_cycle_start}")

        # Determine usage limit status with new format
        usage_limit_info = {
            "user_id": str(user_id),
            "allowed": True,
            "status": "allowed",
            "tokens_quota": tokens_quota,
            "tokens_used": tokens_used,
            "cost_quota": cost_quota,
            "cost_used": cost_used,
            "prev_tokens_used": prev_tokens_used,
            "prev_cost_used": prev_cost_used,
            "reason": None,
            "reset_at": billing_cycle_end,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "billing_cycle_start": billing_cycle_start,
            "billing_cycle_end": billing_cycle_end,
            "plan_name": usage.get("plan_name", "Free"),
        }

        if not usage.get("has_billing"):
            # No billing plan means freemium user - allow with no limits
            usage_limit_info.update(
                {
                    "allowed": True,
                    "status": "no_billing_plan",
                    "reason": "No billing plan - freemium user",
                }
            )
        elif usage.get("is_suspended"):
            usage_limit_info.update(
                {
                    "allowed": False,
                    "status": "suspended",
                    "reason": usage.get("suspension_reason", "Account suspended"),
                }
            )
        elif tokens_quota and tokens_used >= tokens_quota:
            usage_limit_info.update(
                {
                    "allowed": False,
                    "status": "token_limit_exceeded",
                    "reason": "Monthly token quota exceeded",
                }
            )
        elif cost_quota and cost_used >= cost_quota:
            usage_limit_info.update(
                {
                    "allowed": False,
                    "status": "cost_limit_exceeded",
                    "reason": "Monthly cost quota exceeded",
                }
            )
        else:
            # User is within limits
            usage_limit_info.update(
                {
                    "allowed": True,
                    "status": "allowed",
                }
            )

        # Publish to Redis for gateway consumption
        try:
            redis_service = RedisService()
            key = f"usage_limit:{user_id}"
            # Store with 60 second TTL - ensures data availability between sync intervals (30s)
            await redis_service.set(key, json.dumps(usage_limit_info), ex=60)
        except Exception as e:
            logger.warning(f"Failed to publish usage limit to Redis: {e}")

        return usage_limit_info

    async def get_usage_history(
        self,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "daily",
        project_id: Optional[UUID] = None,
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

                if project_id:
                    params["project_id"] = str(project_id)

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
        """Get all billing alerts for a user, ordered by threshold percent."""
        user_billing = self.get_user_billing(user_id)
        if not user_billing:
            return []

        stmt = (
            select(BillingAlert)
            .where(
                BillingAlert.user_billing_id == user_billing.id,
                BillingAlert.is_active,
            )
            .order_by(BillingAlert.threshold_percent)
        )
        return list(self.session.execute(stmt).scalars().all())

    async def check_and_trigger_alerts(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Check usage against alert thresholds and return triggered alerts."""
        from budapp.billing_ops.notification_service import BillingNotificationService

        usage = await self.get_current_usage(user_id)
        if not usage.get("has_billing"):
            return []

        # Get user information for notifications
        user_billing = self.get_user_billing(user_id)
        if not user_billing:
            return []

        # Get user details for email
        stmt = select(User).where(User.id == user_id)
        user = self.session.execute(stmt).scalar_one_or_none()
        if not user:
            return []

        alerts = self.get_billing_alerts(user_id)
        triggered_alerts = []
        notification_service = BillingNotificationService()

        for alert in alerts:
            should_trigger = False
            current_value = None
            quota_value = None

            if alert.alert_type == "token_usage":
                current_percent = usage["usage"]["tokens_usage_percent"]
                current_value = usage["usage"]["tokens_used"]
                quota_value = usage["usage"]["tokens_quota"]
            elif alert.alert_type == "cost_usage":
                current_percent = usage["usage"]["cost_usage_percent"]
                current_value = usage["usage"]["cost_used"]
                quota_value = usage["usage"]["cost_quota"]
            else:
                continue  # Skip unknown alert types

            # Check if threshold is crossed
            if current_percent >= alert.threshold_percent:
                # Calculate the threshold value
                if quota_value:
                    threshold_value = Decimal(str(quota_value * alert.threshold_percent / 100))

                    # Only trigger if we haven't already triggered for a value >= threshold
                    # This prevents re-triggering when usage continues to increase
                    if not alert.last_triggered_value or alert.last_triggered_value < threshold_value:
                        should_trigger = True

            if should_trigger:
                # Update alert
                alert.last_triggered_at = datetime.now(timezone.utc)
                alert.last_triggered_value = Decimal(str(current_value))

                # Send notification
                try:
                    notification_preferences = {
                        "enable_email_notifications": user_billing.enable_email_notifications,
                        "enable_in_app_notifications": user_billing.enable_in_app_notifications,
                    }

                    notification_result = await notification_service.send_usage_alert(
                        user_id=user_id,
                        user_email=user.email,
                        alert_type=alert.alert_type,
                        threshold_percent=alert.threshold_percent,
                        current_usage_percent=current_percent,
                        current_usage_value=current_value,
                        quota_value=quota_value,
                        plan_name=usage.get("plan_name", "Unknown"),
                        notification_preferences=notification_preferences,
                        billing_period_start=user_billing.billing_period_start,
                        billing_period_end=user_billing.billing_period_end,
                    )

                    # Update notification tracking
                    if notification_result["success"]:
                        alert.last_notification_sent_at = datetime.now(timezone.utc)
                        alert.notification_failure_count = 0
                        alert.last_notification_error = None
                    else:
                        alert.notification_failure_count += 1
                        alert.last_notification_error = "; ".join(
                            notification_result.get("errors", ["Unknown error"])
                        )[:500]

                    logger.info(f"Notification sent for alert {alert.name}: {notification_result}")

                except Exception as e:
                    logger.error(f"Failed to send notification for alert {alert.name}: {e}")
                    alert.notification_failure_count += 1
                    alert.last_notification_error = str(e)[:500]

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

    def reset_user_alerts(self, user_billing_id: UUID) -> None:
        """Reset all alerts for a user billing (used when billing cycle resets or quota changes)."""
        stmt = select(BillingAlert).where(BillingAlert.user_billing_id == user_billing_id, BillingAlert.is_active)
        alerts = self.session.execute(stmt).scalars().all()

        for alert in alerts:
            alert.last_triggered_at = None
            alert.last_triggered_value = None
            alert.last_notification_sent_at = None
            alert.notification_failure_count = 0
            alert.last_notification_error = None

        self.session.commit()
        logger.info(f"Reset {len(alerts)} alerts for user_billing_id {user_billing_id}")

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

        # Reset alerts when billing period updates
        self.reset_user_alerts(user_billing.id)

        self.session.commit()
