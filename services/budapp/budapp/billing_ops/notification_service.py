"""Billing notification service for sending usage alerts."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from budapp.commons.dapr import dapr_invoker
from budapp.shared.notification_service import NotificationService


logger = logging.getLogger(__name__)


class BillingNotificationService:
    """Service for handling billing alert notifications."""

    def __init__(self):
        """Initialize the billing notification service."""
        self.notification_service = NotificationService()

    async def send_usage_alert(
        self,
        user_id: UUID,
        user_email: str,
        alert_type: str,
        threshold_percent: int,
        current_usage_percent: float,
        current_usage_value: float,
        quota_value: Optional[float],
        plan_name: str,
        notification_preferences: Dict[str, Any],
        billing_period_start: Optional[datetime] = None,
        billing_period_end: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Send usage alert notification to user.

        Args:
            user_id: User's UUID
            user_email: User's email address
            alert_type: Type of alert (token_usage or cost_usage)
            threshold_percent: Configured threshold percentage
            current_usage_percent: Current usage percentage
            current_usage_value: Current usage value
            quota_value: Quota limit value
            plan_name: Billing plan name
            notification_preferences: User's notification preferences
            billing_period_start: Start of billing period
            billing_period_end: End of billing period

        Returns:
            Dict with notification send results
        """
        try:
            # Prepare notification content
            alert_title = self._get_alert_title(alert_type, threshold_percent)
            alert_message = self._get_alert_message(
                alert_type=alert_type,
                threshold_percent=threshold_percent,
                current_usage_percent=current_usage_percent,
                current_usage_value=current_usage_value,
                quota_value=quota_value,
                plan_name=plan_name,
                billing_period_start=billing_period_start,
                billing_period_end=billing_period_end,
            )

            results = {
                "success": False,
                "channels_sent": [],
                "errors": [],
            }

            # Send in-app notification if enabled
            if notification_preferences.get("enable_in_app_notifications", True):
                try:
                    await self._send_in_app_notification(
                        user_id=user_id,
                        title=alert_title,
                        message=alert_message,
                        alert_type=alert_type,
                        threshold_percent=threshold_percent,
                    )
                    results["channels_sent"].append("in_app")
                except Exception as e:
                    logger.error(f"Failed to send in-app notification: {e}")
                    results["errors"].append(f"in_app: {str(e)}")

            # Send email notification if enabled
            if notification_preferences.get("enable_email_notifications", True):
                try:
                    await self._send_email_notification(
                        email=user_email,
                        title=alert_title,
                        message=alert_message,
                        alert_type=alert_type,
                    )
                    results["channels_sent"].append("email")
                except Exception as e:
                    logger.error(f"Failed to send email notification: {e}")
                    results["errors"].append(f"email: {str(e)}")

            results["success"] = len(results["channels_sent"]) > 0
            return results

        except Exception as e:
            logger.error(f"Error sending usage alert notification: {e}")
            return {
                "success": False,
                "channels_sent": [],
                "errors": [str(e)],
            }

    def _get_alert_title(self, alert_type: str, threshold_percent: int) -> str:
        """Get alert title based on type and threshold."""
        if alert_type == "token_usage":
            return f"Token Usage Alert: {threshold_percent}% Threshold Reached"
        elif alert_type == "cost_usage":
            return f"Cost Usage Alert: {threshold_percent}% Threshold Reached"
        else:
            return f"Usage Alert: {threshold_percent}% Threshold Reached"

    def _get_alert_message(
        self,
        alert_type: str,
        threshold_percent: int,
        current_usage_percent: float,
        current_usage_value: float,
        quota_value: Optional[float],
        plan_name: str,
        billing_period_start: Optional[datetime] = None,
        billing_period_end: Optional[datetime] = None,
    ) -> str:
        """Get detailed alert message."""
        # Determine period description
        period_desc = "billing period"
        if billing_period_start and billing_period_end:
            delta_days = (billing_period_end - billing_period_start).days
            if 28 <= delta_days <= 31:
                period_desc = "monthly"
            elif 89 <= delta_days <= 92:
                period_desc = "quarterly"
            elif 365 <= delta_days <= 366:
                period_desc = "annual"
            elif delta_days == 7:
                period_desc = "weekly"
            elif delta_days == 14:
                period_desc = "bi-weekly"
            else:
                period_desc = f"{delta_days}-day"

        if alert_type == "token_usage":
            usage_type = "token"
            unit = "tokens"
            value_str = f"{int(current_usage_value):,}"
            quota_str = f"{int(quota_value):,}" if quota_value else "unlimited"
        else:  # cost_usage
            usage_type = "cost"
            unit = "USD"
            value_str = f"${current_usage_value:,.2f}"
            quota_str = f"${quota_value:,.2f}" if quota_value else "unlimited"

        message = f"""Your {usage_type} usage has reached {current_usage_percent:.1f}% of your {period_desc} quota.

Current Usage: {value_str} {unit}
{period_desc.capitalize()} Quota: {quota_str} {unit}
Billing Plan: {plan_name}

You have reached the {threshold_percent}% threshold you configured for {usage_type} usage alerts."""

        # Add period dates if available
        if billing_period_start and billing_period_end:
            message += f"\nBilling Period: {billing_period_start.strftime('%Y-%m-%d')} to {billing_period_end.strftime('%Y-%m-%d')}"

        # Add recommendations based on threshold
        if threshold_percent >= 90:
            message += f"\n\n⚠️ Warning: You are approaching your {period_desc} {usage_type} limit. Consider upgrading your plan to avoid service interruptions."
        elif threshold_percent >= 75:
            message += f"\n\nℹ️ Tip: Monitor your {usage_type} usage closely to stay within your {period_desc} quota."

        return message

    async def _send_in_app_notification(
        self,
        user_id: UUID,
        title: str,
        message: str,
        alert_type: str,
        threshold_percent: int,
    ) -> None:
        """Send in-app notification via budnotify service."""
        try:
            # Prepare notification payload for budnotify
            notification_data = {
                "user_id": str(user_id),
                "notification_type": "billing_alert",
                "title": title,
                "message": message,
                "metadata": {
                    "alert_type": alert_type,
                    "threshold_percent": threshold_percent,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                "priority": "high" if threshold_percent >= 90 else "medium",
            }

            # Send via Dapr service invocation to budnotify
            response = await dapr_invoker.invoke_service(
                app_id="budnotify",
                method_name="notifications/in-app",
                data=notification_data,
                http_verb="POST",
            )

            if response.status_code != 200:
                raise Exception(f"Failed to send in-app notification: {response.text}")

            logger.info(f"In-app notification sent successfully for user {user_id}")

        except Exception as e:
            logger.error(f"Error sending in-app notification: {e}")
            raise

    async def _send_email_notification(
        self,
        email: str,
        title: str,
        message: str,
        alert_type: str,
    ) -> None:
        """Send email notification via budnotify service."""
        try:
            # Prepare email notification payload
            email_data = {
                "to": email,
                "subject": title,
                "body": message,
                "template": "billing_alert",
                "template_data": {
                    "alert_type": alert_type,
                    "message": message,
                },
                "priority": "high",
            }

            # Send via Dapr service invocation to budnotify
            response = await dapr_invoker.invoke_service(
                app_id="budnotify",
                method_name="notifications/email",
                data=email_data,
                http_verb="POST",
            )

            if response.status_code != 200:
                raise Exception(f"Failed to send email notification: {response.text}")

            logger.info(f"Email notification sent successfully to {email}")

        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            raise
