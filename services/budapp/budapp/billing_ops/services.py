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
        """Check if user has exceeded usage limits and publish to Redis."""
        import json
        from datetime import datetime, timezone

        from budapp.shared.redis_service import RedisService

        usage = await self.get_current_usage(user_id)

        # Get current usage values
        tokens_used = usage["usage"]["tokens_used"] if usage.get("usage") else 0
        cost_used = usage["usage"]["cost_used"] if usage.get("usage") else 0.0
        tokens_quota = usage["usage"]["tokens_quota"] if usage.get("usage") else None
        cost_quota = usage["usage"]["cost_quota"] if usage.get("usage") else None

        # Get previous values from Redis (for delta calculation)
        existing_data = None
        try:
            redis_service = RedisService()
            key = f"usage_limit:{user_id}"
            existing_data = await redis_service.get(key)
            if existing_data:
                existing = json.loads(existing_data)
                prev_tokens_used = existing.get("tokens_used", 0)
                prev_cost_used = existing.get("cost_used", 0.0)
            else:
                prev_tokens_used = 0
                prev_cost_used = 0.0
        except Exception:
            prev_tokens_used = 0
            prev_cost_used = 0.0

        # Get billing cycle information
        billing_cycle_start = None
        billing_cycle_end = None
        if usage.get("has_billing"):
            # Get billing cycle from user billing record
            from budapp.billing_ops.models import UserBilling

            user_billing = self.session.query(UserBilling).filter_by(user_id=user_id).first()
            if user_billing:
                # Calculate current billing cycle
                from dateutil.relativedelta import relativedelta

                now = datetime.now(timezone.utc)

                # Assuming monthly billing cycle
                if user_billing.created_at:
                    # Find the start of current billing cycle
                    months_since_start = (now.year - user_billing.created_at.year) * 12 + (
                        now.month - user_billing.created_at.month
                    )
                    cycle_start = user_billing.created_at + relativedelta(months=months_since_start)
                    cycle_end = cycle_start + relativedelta(months=1)

                    # If we've passed the cycle end, move to next cycle
                    if now >= cycle_end:
                        cycle_start = cycle_end
                        cycle_end = cycle_start + relativedelta(months=1)

                    billing_cycle_start = cycle_start.isoformat()
                    billing_cycle_end = cycle_end.isoformat()

        # Check if this is a new billing cycle
        if existing_data and billing_cycle_start:
            existing = json.loads(existing_data)
            old_cycle_start = existing.get("billing_cycle_start")
            if old_cycle_start != billing_cycle_start:
                # New billing cycle detected - reset usage
                tokens_used = 0
                cost_used = 0.0
                prev_tokens_used = 0
                prev_cost_used = 0.0
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
            # Store with 10 second TTL - will be refreshed by sync task
            await redis_service.set(key, json.dumps(usage_limit_info), ex=10)
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
