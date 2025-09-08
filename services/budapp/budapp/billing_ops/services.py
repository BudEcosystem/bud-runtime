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
        """Get current user billing information."""
        stmt = select(UserBilling).where(UserBilling.user_id == user_id, UserBilling.is_current, UserBilling.is_active)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_user_billing_history(self, user_id: UUID) -> List[UserBilling]:
        """Get all billing history for a user, ordered by creation date."""
        stmt = (
            select(UserBilling)
            .where(UserBilling.user_id == user_id, UserBilling.is_active)
            .order_by(UserBilling.created_at.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_user_billing_for_period(self, user_id: UUID, date: datetime) -> Optional[UserBilling]:
        """Get user billing record that was active during a specific date."""
        stmt = select(UserBilling).where(
            UserBilling.user_id == user_id,
            UserBilling.billing_period_start <= date,
            UserBilling.billing_period_end > date,
            UserBilling.is_active,
        )
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

            user_billing = self.get_user_billing(user_id)
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

                # Also create new billing cycle if needed
                user_billing = self.get_user_billing(user_id)
                if user_billing and billing_cycle_start and billing_cycle_end:
                    try:
                        from datetime import datetime, timezone

                        cycle_start_dt = datetime.fromisoformat(billing_cycle_start.replace("Z", "+00:00"))
                        cycle_end_dt = datetime.fromisoformat(billing_cycle_end.replace("Z", "+00:00"))

                        # Ensure timezone aware
                        if cycle_start_dt.tzinfo is None:
                            cycle_start_dt = cycle_start_dt.replace(tzinfo=timezone.utc)
                        if cycle_end_dt.tzinfo is None:
                            cycle_end_dt = cycle_end_dt.replace(tzinfo=timezone.utc)

                        # Create new billing cycle if database is behind
                        if (
                            user_billing.billing_period_start != cycle_start_dt
                            or user_billing.billing_period_end != cycle_end_dt
                        ):
                            # Create new billing cycle entry (preserves history)
                            self.create_next_billing_cycle(user_id)
                            logger.info(f"Synchronized database billing period for user {user_id}")
                    except Exception as e:
                        logger.warning(f"Failed to update database billing period for user {user_id}: {e}")

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
        stmt = (
            select(BillingAlert)
            .where(
                BillingAlert.user_id == user_id,
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
        from dateutil.relativedelta import relativedelta

        # Calculate billing period (monthly) - start from current time
        now = datetime.now(timezone.utc)
        billing_period_start = now
        billing_period_end = now + relativedelta(months=1)

        # Check if there's an existing current billing record
        existing_current = self.get_user_billing(user_id)

        # Determine cycle number
        if existing_current:
            # This should not happen normally, but handle it
            cycle_number = existing_current.cycle_number + 1
            logger.warning(f"Creating new billing record for user {user_id} while current record exists")
        else:
            # Check for any historical records to get the next cycle number
            history = self.get_user_billing_history(user_id)
            cycle_number = (max(b.cycle_number for b in history) + 1) if history else 1

        user_billing = UserBilling(
            user_id=user_id,
            billing_plan_id=billing_plan_id,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
            custom_token_quota=custom_token_quota,
            custom_cost_quota=custom_cost_quota,
            is_current=True,
            cycle_number=cycle_number,
        )

        self.session.add(user_billing)
        self.session.commit()
        self.session.refresh(user_billing)

        logger.info(
            f"Created billing record for user {user_id}, cycle {cycle_number}: "
            f"{billing_period_start.isoformat()} to {billing_period_end.isoformat()}"
        )

        return user_billing

    def reset_user_alerts(self, user_id: UUID) -> None:
        """Reset all alerts for a user (used when billing cycle resets or quota changes)."""
        stmt = select(BillingAlert).where(BillingAlert.user_id == user_id, BillingAlert.is_active)
        alerts = self.session.execute(stmt).scalars().all()

        for alert in alerts:
            alert.last_triggered_at = None
            alert.last_triggered_value = None
            alert.last_notification_sent_at = None
            alert.notification_failure_count = 0
            alert.last_notification_error = None

        self.session.commit()
        logger.info(f"Reset {len(alerts)} alerts for user_id {user_id}")

    def create_billing_alert(self, user_id: UUID, name: str, alert_type: str, threshold_percent: int) -> BillingAlert:
        """Create a new billing alert with validation."""
        from fastapi import HTTPException, status

        # Check if alert with same name already exists for this user
        existing_alert_stmt = select(BillingAlert).where(BillingAlert.user_id == user_id, BillingAlert.name == name)
        existing_alert = self.session.execute(existing_alert_stmt).scalar_one_or_none()

        if existing_alert:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An alert with this name already exists")

        # Create the new alert
        alert = BillingAlert(
            user_id=user_id,
            name=name,
            alert_type=alert_type,
            threshold_percent=threshold_percent,
        )

        self.session.add(alert)
        self.session.commit()
        self.session.refresh(alert)

        return alert

    def create_next_billing_cycle(self, user_id: UUID) -> UserBilling:
        """Create a new billing cycle entry for a user, preserving the previous one as history."""
        from datetime import datetime, timezone

        from budapp.billing_ops.utils import calculate_billing_cycle

        # Get current billing record
        current_billing = self.get_user_billing(user_id)
        if not current_billing:
            raise ValueError(f"No current billing record found for user {user_id}")

        # Calculate the next billing cycle
        now = datetime.now(timezone.utc)
        cycle_start_str, cycle_end_str = calculate_billing_cycle(current_billing.created_at, reference_date=now)

        if not cycle_start_str or not cycle_end_str:
            raise ValueError(f"Failed to calculate next billing cycle for user {user_id}")

        # Parse cycle dates
        cycle_start = datetime.fromisoformat(cycle_start_str.replace("Z", "+00:00"))
        cycle_end = datetime.fromisoformat(cycle_end_str.replace("Z", "+00:00"))

        # Ensure timezone aware
        if cycle_start.tzinfo is None:
            cycle_start = cycle_start.replace(tzinfo=timezone.utc)
        if cycle_end.tzinfo is None:
            cycle_end = cycle_end.replace(tzinfo=timezone.utc)

        # Create new billing cycle entry
        new_billing = UserBilling(
            user_id=user_id,
            billing_plan_id=current_billing.billing_plan_id,
            billing_period_start=cycle_start,
            billing_period_end=cycle_end,
            custom_token_quota=current_billing.custom_token_quota,  # Inherit current settings
            custom_cost_quota=current_billing.custom_cost_quota,
            enable_email_notifications=current_billing.enable_email_notifications,
            enable_in_app_notifications=current_billing.enable_in_app_notifications,
            is_active=True,
            is_suspended=current_billing.is_suspended,
            suspension_reason=current_billing.suspension_reason,
            is_current=True,
            cycle_number=current_billing.cycle_number + 1,
        )

        # Mark the current billing as superseded
        superseded_at = datetime.now(timezone.utc)
        current_billing.is_current = False
        current_billing.superseded_at = superseded_at
        # We'll set superseded_by_id after we get the new record ID

        # Add new record to session
        self.session.add(new_billing)
        self.session.flush()  # Get the ID without committing

        # Now set the superseded_by reference
        current_billing.superseded_by_id = new_billing.id

        # Reset alerts for the new billing cycle
        self.reset_user_alerts(new_billing.id)

        # Commit all changes
        self.session.commit()
        self.session.refresh(new_billing)

        logger.info(
            f"Created new billing cycle for user {user_id}, cycle {new_billing.cycle_number}: "
            f"{cycle_start.isoformat()} to {cycle_end.isoformat()}"
        )
        logger.info(f"Superseded previous cycle {current_billing.cycle_number} at {superseded_at.isoformat()}")

        return new_billing

    def update_billing_period(self, user_billing: UserBilling) -> None:
        """Deprecated method - use create_next_billing_cycle instead."""
        logger.warning("update_billing_period is deprecated, use create_next_billing_cycle instead")
        self.create_next_billing_cycle(user_billing.user_id)
