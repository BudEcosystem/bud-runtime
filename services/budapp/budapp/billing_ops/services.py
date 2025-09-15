"""Billing service for usage tracking and quota management."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from dateutil.relativedelta import relativedelta
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from budapp.billing_ops.models import BillingAlert, BillingPlan, UserBilling
from budapp.billing_ops.notification_service import BillingNotificationService
from budapp.commons.config import app_settings
from budapp.commons.constants import UserTypeEnum
from budapp.commons.db_utils import DataManagerUtils
from budapp.commons.logging import get_logger
from budapp.shared.redis_service import RedisService
from budapp.user_ops.models import User
from budapp.user_ops.models import User as UserModel


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

    async def get_bulk_usage_from_clickhouse(
        self,
        user_ids: List[UUID],
        start_date: datetime,
        end_date: datetime,
        project_id: Optional[UUID] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Get usage data for multiple users from ClickHouse via budmetrics bulk API.

        This method is significantly more efficient than calling get_usage_from_clickhouse
        for each user individually. It makes a single API call to fetch usage data for
        all requested users.

        Args:
            user_ids: List of user UUIDs to get usage for
            start_date: Start of the usage period
            end_date: End of the usage period
            project_id: Optional project filter

        Returns:
            Dict mapping user_id strings to usage data dicts
        """
        try:
            # Limit batch size for safety
            if len(user_ids) > 1000:
                logger.warning(f"Bulk usage request for {len(user_ids)} users exceeds recommended limit of 1000")

            # Use Dapr invoke pattern for service-to-service communication
            dapr_url = f"{app_settings.dapr_base_url}/v1.0/invoke/budmetrics/method/observability/usage/summary/bulk"

            payload = {
                "user_ids": [str(uid) for uid in user_ids],
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            }

            if project_id:
                payload["project_id"] = str(project_id)

            async with httpx.AsyncClient(timeout=60.0) as client:  # Longer timeout for bulk requests
                response = await client.post(dapr_url, json=payload)
                response.raise_for_status()
                result = response.json()

                # Process the bulk response
                if result and "param" in result and "users" in result["param"]:
                    users_data = result["param"]["users"]

                    # Create lookup dict by user_id
                    usage_lookup = {}
                    for user_data in users_data:
                        user_id = user_data["user_id"]
                        usage_lookup[user_id] = {
                            "total_tokens": user_data.get("total_tokens", 0),
                            "total_cost": user_data.get("total_cost", 0.0),
                            "request_count": user_data.get("request_count", 0),
                            "success_rate": user_data.get("success_rate", 0.0),
                        }

                    # Ensure we have entries for all requested users (even if they have no usage)
                    for user_id in user_ids:
                        user_id_str = str(user_id)
                        if user_id_str not in usage_lookup:
                            usage_lookup[user_id_str] = {
                                "total_tokens": 0,
                                "total_cost": 0.0,
                                "request_count": 0,
                                "success_rate": 0.0,
                            }

                    return usage_lookup
                else:
                    # Return empty usage for all users if no data
                    return {
                        str(user_id): {
                            "total_tokens": 0,
                            "total_cost": 0.0,
                            "request_count": 0,
                            "success_rate": 0.0,
                        }
                        for user_id in user_ids
                    }

        except Exception as e:
            logger.error(f"Error fetching bulk usage from ClickHouse: {e}")
            # Return empty usage for all users on error
            return {
                str(user_id): {
                    "total_tokens": 0,
                    "total_cost": 0.0,
                    "request_count": 0,
                    "success_rate": 0.0,
                }
                for user_id in user_ids
            }

    async def check_bulk_usage_limits(self, user_ids: List[UUID]) -> Dict[str, Dict[str, Any]]:
        """Check usage limits for multiple users efficiently using bulk API.

        This method is significantly more efficient than calling check_usage_limits
        for each user individually. It makes a single bulk API call and processes
        the results for all users at once.

        Args:
            user_ids: List of user UUIDs to check limits for

        Returns:
            Dict mapping user_id strings to usage limit results
        """
        if not user_ids:
            return {}

        result_dict = {}

        # Get current time for timestamps
        now = datetime.now(timezone.utc)

        try:
            # Get user information for all users at once
            users_stmt = select(UserModel).where(UserModel.id.in_(user_ids))
            users = self.session.execute(users_stmt).scalars().all()
            user_lookup = {user.id: user for user in users}

            # Get billing information for all users
            billing_stmt = select(UserBilling).where(
                UserBilling.user_id.in_(user_ids), UserBilling.is_current, UserBilling.is_active
            )
            billings = self.session.execute(billing_stmt).scalars().all()
            billing_lookup = {billing.user_id: billing for billing in billings}

            # Get billing plans for all users
            plan_ids = [b.billing_plan_id for b in billings if b.billing_plan_id]
            if plan_ids:
                plans_stmt = select(BillingPlan).where(BillingPlan.id.in_(plan_ids))
                plans = self.session.execute(plans_stmt).scalars().all()
                plan_lookup = {plan.id: plan for plan in plans}
            else:
                plan_lookup = {}

            # Separate users into those with and without billing
            users_with_billing = []
            users_without_billing = []

            for user_id in user_ids:
                if user_id in billing_lookup:
                    users_with_billing.append(user_id)
                else:
                    users_without_billing.append(user_id)

            # Get bulk usage data for users with billing
            if users_with_billing:
                # Group users by their billing cycle dates to minimize API calls
                cycle_groups = {}
                for user_id in users_with_billing:
                    billing = billing_lookup[user_id]
                    cycle_key = (billing.billing_period_start, billing.billing_period_end)
                    if cycle_key not in cycle_groups:
                        cycle_groups[cycle_key] = []
                    cycle_groups[cycle_key].append(user_id)

                # Get bulk usage data for each unique billing cycle
                bulk_usage_data = {}
                for (cycle_start, cycle_end), user_group in cycle_groups.items():
                    group_usage_data = await self.get_bulk_usage_from_clickhouse(user_group, cycle_start, cycle_end)
                    bulk_usage_data.update(group_usage_data)

                # Process each user with billing
                for user_id in users_with_billing:
                    user_id_str = str(user_id)
                    user = user_lookup.get(user_id)
                    billing = billing_lookup[user_id]
                    plan = plan_lookup.get(billing.billing_plan_id) if billing.billing_plan_id else None
                    usage_data = bulk_usage_data.get(
                        user_id_str, {"total_tokens": 0, "total_cost": 0.0, "request_count": 0, "success_rate": 0.0}
                    )

                    # Check if admin user (unlimited access)
                    user_type = user.user_type if user else UserTypeEnum.CLIENT
                    if user_type == UserTypeEnum.ADMIN:
                        usage_limit_info = {
                            "user_id": user_id_str,
                            "user_type": user_type.value,
                            "allowed": True,
                            "status": "admin_unlimited",
                            "tokens_quota": None,
                            "tokens_used": usage_data["total_tokens"],
                            "cost_quota": None,
                            "cost_used": usage_data["total_cost"],
                            "prev_tokens_used": 0,
                            "prev_cost_used": 0.0,
                            "reason": "Admin user - unlimited access",
                            "reset_at": billing.billing_period_end.isoformat() if billing else None,
                            "last_updated": now.isoformat(),
                            "billing_cycle_start": billing.billing_period_start.isoformat() if billing else None,
                            "billing_cycle_end": billing.billing_period_end.isoformat() if billing else None,
                        }
                        result_dict[user_id_str] = usage_limit_info
                        continue

                    # Regular user processing
                    tokens_used = usage_data["total_tokens"]
                    cost_used = usage_data["total_cost"]

                    # Get quotas
                    tokens_quota = billing.custom_token_quota or (plan.monthly_token_quota if plan else None)
                    cost_quota = billing.custom_cost_quota or (plan.monthly_cost_quota if plan else None)

                    # Check limits
                    allowed = True
                    status = "allowed"
                    reason = None

                    # Check suspension
                    if billing.is_suspended:
                        allowed = False
                        status = "suspended"
                        reason = billing.suspension_reason or "Account suspended"
                    # Check token limits
                    elif tokens_quota and tokens_used >= tokens_quota:
                        allowed = False
                        status = "token_limit_exceeded"
                        reason = f"Token limit exceeded: {tokens_used}/{tokens_quota}"
                    # Check cost limits
                    elif cost_quota and cost_used >= cost_quota:
                        allowed = False
                        status = "cost_limit_exceeded"
                        reason = f"Cost limit exceeded: ${cost_used:.2f}/${cost_quota:.2f}"

                    usage_limit_info = {
                        "user_id": user_id_str,
                        "user_type": user_type.value,
                        "allowed": allowed,
                        "status": status,
                        "tokens_quota": tokens_quota,
                        "tokens_used": tokens_used,
                        "cost_quota": float(cost_quota) if cost_quota else None,
                        "cost_used": cost_used,
                        "prev_tokens_used": 0,
                        "prev_cost_used": 0.0,
                        "reason": reason,
                        "reset_at": billing.billing_period_end.isoformat() if billing.billing_period_end else None,
                        "last_updated": now.isoformat(),
                        "billing_cycle_start": billing.billing_period_start.isoformat()
                        if billing.billing_period_start
                        else None,
                        "billing_cycle_end": billing.billing_period_end.isoformat()
                        if billing.billing_period_end
                        else None,
                    }

                    result_dict[user_id_str] = usage_limit_info

            # Process users without billing (freemium)
            if users_without_billing:
                # For freemium users, get usage data separately
                now = datetime.now(timezone.utc)
                billing_period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                if billing_period_start.month == 12:
                    billing_period_end = billing_period_start.replace(
                        year=billing_period_start.year + 1, month=1
                    ) - timedelta(seconds=1)
                else:
                    billing_period_end = billing_period_start.replace(
                        month=billing_period_start.month + 1
                    ) - timedelta(seconds=1)

                freemium_usage_data = await self.get_bulk_usage_from_clickhouse(
                    users_without_billing, billing_period_start, billing_period_end
                )

                free_plan = self._get_default_free_plan()
                token_quota = free_plan.get("monthly_token_quota", 100000)

                for user_id in users_without_billing:
                    user_id_str = str(user_id)
                    user = user_lookup.get(user_id)
                    user_type = user.user_type if user else UserTypeEnum.CLIENT
                    usage_data = freemium_usage_data.get(
                        user_id_str, {"total_tokens": 0, "total_cost": 0.0, "request_count": 0, "success_rate": 0.0}
                    )

                    # Check if admin user (unlimited access)
                    if user_type == UserTypeEnum.ADMIN:
                        usage_limit_info = {
                            "user_id": user_id_str,
                            "user_type": user_type.value,
                            "allowed": True,
                            "status": "admin_unlimited",
                            "tokens_quota": None,
                            "tokens_used": usage_data["total_tokens"],
                            "cost_quota": None,
                            "cost_used": usage_data["total_cost"],
                            "prev_tokens_used": 0,
                            "prev_cost_used": 0.0,
                            "reason": "Admin user - unlimited access",
                            "reset_at": None,
                            "last_updated": now.isoformat(),
                            "billing_cycle_start": None,
                            "billing_cycle_end": None,
                        }
                        result_dict[user_id_str] = usage_limit_info
                        continue

                    usage_limit_info = {
                        "user_id": user_id_str,
                        "user_type": user_type.value,
                        "allowed": True,
                        "status": "no_billing_plan",
                        "tokens_quota": token_quota,
                        "tokens_used": usage_data["total_tokens"],
                        "cost_quota": None,
                        "cost_used": usage_data["total_cost"],
                        "prev_tokens_used": 0,
                        "prev_cost_used": 0.0,
                        "reason": "No billing plan - freemium user",
                        "reset_at": None,
                        "last_updated": now.isoformat(),
                        "billing_cycle_start": None,
                        "billing_cycle_end": None,
                    }

                    result_dict[user_id_str] = usage_limit_info

            # Publish to Redis with single 90-minute TTL
            redis_service = RedisService()
            ttl_seconds = 90 * 60  # 90 minutes

            # Count admin users for logging
            admin_count = sum(1 for info in result_dict.values() if info.get("status") == "admin_unlimited")

            for user_id_str, usage_limit_info in result_dict.items():
                key = f"usage_limit:{user_id_str}"
                data = json.dumps(usage_limit_info)
                await redis_service.set(key, data, ex=ttl_seconds)

            logger.info(
                f"Bulk checked usage limits for {len(result_dict)} users (including {admin_count} admin users)"
            )
            return result_dict

        except Exception as e:
            logger.error(f"Error in bulk usage limits check: {e}")
            # Return empty results for all users on error
            return {str(user_id): {} for user_id in user_ids}

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
            # All users should have billing records - this case should not occur
            logger.warning(f"No billing record found for user {user_id} - this should not happen")
            # Try to get the Free plan as default
            free_plan = self.get_free_billing_plan()
            if not free_plan:
                # Create a virtual Free plan if it doesn't exist in DB
                free_plan = self._get_default_free_plan()

            # Return minimal response indicating no billing setup
            return {
                "has_billing": False,
                "billing_period_start": None,
                "billing_period_end": None,
                "plan_name": "No Plan",
                "billing_plan_id": None,
                "base_monthly_price": 0.0,
                "usage": {
                    "tokens_used": 0,
                    "tokens_quota": free_plan.get("monthly_token_quota", 100000),
                    "tokens_usage_percent": 0.0,
                    "cost_used": 0.0,
                    "cost_quota": free_plan.get("monthly_cost_quota", None),
                    "cost_usage_percent": 0.0,
                    "request_count": 0,
                    "success_rate": 0.0,
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
        # Get user information to determine user type
        stmt = select(UserModel).where(UserModel.id == user_id)
        user = self.session.execute(stmt).scalar_one_or_none()
        user_type = user.user_type if user else UserTypeEnum.CLIENT
        is_admin_user = user_type == UserTypeEnum.ADMIN

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
            user_billing = self.get_user_billing(user_id)
            if user_billing:
                # Use the actual stored billing cycle dates (no need to recalculate)
                billing_cycle_start = user_billing.billing_period_start.isoformat()
                billing_cycle_end = user_billing.billing_period_end.isoformat()

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
            "user_type": user_type.value if user_type else "client",
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

        if is_admin_user:
            # Admin users always have unlimited access regardless of billing status
            usage_limit_info.update(
                {
                    "allowed": True,
                    "status": "admin_unlimited",
                    "reason": "Admin user - unlimited access",
                }
            )
        elif not usage.get("has_billing"):
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

        # Publish to Redis for gateway consumption with single 90-minute TTL
        try:
            redis_service = RedisService()
            key = f"usage_limit:{user_id}"
            data = json.dumps(usage_limit_info)
            ttl_seconds = 90 * 60  # 90 minutes

            await redis_service.set(key, data, ex=ttl_seconds)

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
        # Get current billing record
        current_billing = self.get_user_billing(user_id)
        if not current_billing:
            raise ValueError(f"No current billing record found for user {user_id}")

        # Create a new billing cycle using smart date logic and plan-based cycle period
        now = datetime.now(timezone.utc)

        # Get the billing plan to determine cycle length
        billing_plan = self.get_billing_plan(current_billing.billing_plan_id)
        cycle_months = billing_plan.billing_cycle_months if billing_plan else 1

        # Smart cycle start logic:
        # 1. Use previous cycle end date if it's in the past or now
        # 2. Use current time if previous cycle end is in the future (early reset)
        previous_end = current_billing.billing_period_end
        if previous_end.tzinfo is None:
            previous_end = previous_end.replace(tzinfo=timezone.utc)

        # Smart cycle start logic: use previous end if past/current, otherwise use now (early reset)
        cycle_start = previous_end if previous_end <= now else now

        # Calculate cycle end based on plan's cycle period
        cycle_end = cycle_start + relativedelta(months=cycle_months)

        try:
            # Start a nested transaction to handle constraint issues
            with self.session.begin_nested():
                # First, mark the current billing as superseded (this removes any unique constraint conflicts)
                superseded_at = datetime.now(timezone.utc)
                current_billing.is_current = False
                current_billing.superseded_at = superseded_at

                # Flush to ensure the update is committed before creating new record
                self.session.flush()

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

                # Add new record to session
                self.session.add(new_billing)
                self.session.flush()  # Get the ID without committing

                # Now set the superseded_by reference
                current_billing.superseded_by_id = new_billing.id

                # Reset alerts for the new billing cycle
                self.reset_user_alerts(new_billing.id)

        except Exception as e:
            logger.error(f"Failed to create billing cycle for user {user_id}: {e}")
            raise

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

    def get_all_users_with_active_billing(self) -> List[UUID]:
        """Get all user IDs that have active billing records.

        This method returns a list of user IDs who have active and current billing records.
        Used for full sync operations to ensure all users with billing are included in
        usage limit synchronization, even if they have no recent activity.

        Returns:
            List[UUID]: List of user IDs with active billing records
        """
        try:
            stmt = select(UserBilling.user_id).where(UserBilling.is_current, UserBilling.is_active).distinct()

            result = self.session.execute(stmt).scalars().all()
            user_ids = list(result)

            logger.info(f"Found {len(user_ids)} users with active billing records")
            return user_ids

        except Exception as e:
            logger.error(f"Error getting users with active billing: {e}")
            return []
