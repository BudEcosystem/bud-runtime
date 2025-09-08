"""Tests for billing notification integration."""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from budapp.billing_ops.models import BillingAlert, BillingPlan, UserBilling
from budapp.billing_ops.notification_service import BillingNotificationService
from budapp.billing_ops.services import BillingService
from budapp.user_ops.models import User


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = Mock(spec=User)
    user.id = uuid4()
    user.email = "test@example.com"
    user.user_type = "NORMAL"
    return user


@pytest.fixture
def mock_billing_plan():
    """Create a mock billing plan."""
    plan = Mock(spec=BillingPlan)
    plan.id = uuid4()
    plan.name = "Professional"
    plan.monthly_token_quota = 1000000
    plan.monthly_cost_quota = Decimal("100.00")
    plan.base_monthly_price = Decimal("50.00")
    plan.is_active = True
    return plan


@pytest.fixture
def mock_user_billing(mock_user, mock_billing_plan):
    """Create a mock user billing."""
    billing = Mock(spec=UserBilling)
    billing.id = uuid4()
    billing.user_id = mock_user.id
    billing.billing_plan_id = mock_billing_plan.id
    billing.billing_period_start = datetime.now(timezone.utc).replace(day=1)
    billing.billing_period_end = (billing.billing_period_start + timedelta(days=30))
    billing.custom_token_quota = None
    billing.custom_cost_quota = None
    billing.enable_email_notifications = True
    billing.enable_in_app_notifications = True
    billing.is_active = True
    billing.is_suspended = False
    billing.suspension_reason = None
    return billing


@pytest.fixture
def mock_billing_alert(mock_user):
    """Create a mock billing alert."""
    alert = Mock(spec=BillingAlert)
    alert.id = uuid4()
    alert.user_id = mock_user.id
    alert.name = "75% Token Usage Alert"
    alert.alert_type = "token_usage"
    alert.threshold_percent = 75
    alert.last_triggered_at = None
    alert.last_triggered_value = None
    alert.last_notification_sent_at = None
    alert.notification_failure_count = 0
    alert.last_notification_error = None
    alert.is_active = True
    return alert


class TestBillingNotificationService:
    """Test the BillingNotificationService class."""

    @pytest.mark.asyncio
    async def test_send_usage_alert_success(self):
        """Test successful usage alert notification."""
        service = BillingNotificationService()

        # Mock the internal notification methods
        with patch.object(service, '_send_in_app_notification', new_callable=AsyncMock) as mock_in_app, \
             patch.object(service, '_send_email_notification', new_callable=AsyncMock) as mock_email:

            # Add sample billing period dates
            period_start = datetime.now(timezone.utc).replace(day=1)
            period_end = (period_start.replace(month=period_start.month + 1)
                         if period_start.month < 12
                         else period_start.replace(year=period_start.year + 1, month=1))

            result = await service.send_usage_alert(
                user_id=uuid4(),
                user_email="test@example.com",
                alert_type="token_usage",
                threshold_percent=75,
                current_usage_percent=78.5,
                current_usage_value=785000,
                quota_value=1000000,
                plan_name="Professional",
                notification_preferences={
                    "enable_email_notifications": True,
                    "enable_in_app_notifications": True,
                },
                billing_period_start=period_start,
                billing_period_end=period_end,
            )

            assert result["success"] is True
            assert "in_app" in result["channels_sent"]
            assert "email" in result["channels_sent"]
            assert len(result["errors"]) == 0

            # Verify methods were called
            mock_in_app.assert_called_once()
            mock_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_usage_alert_with_email(self):
        """Test usage alert with email notification."""
        service = BillingNotificationService()

        with patch.object(service, '_send_email_notification', new_callable=AsyncMock) as mock_email:

            await service.send_usage_alert(
                user_id=uuid4(),
                user_email="user@example.com",
                alert_type="cost_usage",
                threshold_percent=90,
                current_usage_percent=92.0,
                current_usage_value=92.0,
                quota_value=100.0,
                plan_name="Professional",
                notification_preferences={
                    "enable_email_notifications": True,
                    "enable_in_app_notifications": False,
                },
            )

            # Verify user email was used
            mock_email.assert_called_once()
            call_args = mock_email.call_args[1]
            assert call_args["email"] == "user@example.com"

    @pytest.mark.asyncio
    async def test_send_usage_alert_partial_failure(self):
        """Test partial failure in notification sending."""
        service = BillingNotificationService()

        # Mock email to fail
        with patch.object(service, '_send_in_app_notification', new_callable=AsyncMock), \
             patch.object(service, '_send_email_notification', new_callable=AsyncMock) as mock_email:

            mock_email.side_effect = Exception("Email service unavailable")

            result = await service.send_usage_alert(
                user_id=uuid4(),
                user_email="test@example.com",
                alert_type="token_usage",
                threshold_percent=50,
                current_usage_percent=55.0,
                current_usage_value=550000,
                quota_value=1000000,
                plan_name="Professional",
                notification_preferences={
                    "enable_email_notifications": True,
                    "enable_in_app_notifications": True,
                },
            )

            assert result["success"] is True  # Still success because in-app worked
            assert "in_app" in result["channels_sent"]
            assert "email" not in result["channels_sent"]
            assert len(result["errors"]) == 1
            assert "email" in result["errors"][0]


class TestBillingServiceNotifications:
    """Test billing service notification integration."""

    @pytest.mark.asyncio
    async def test_check_and_trigger_alerts_with_notifications(self, mock_db, mock_user, mock_user_billing, mock_billing_plan, mock_billing_alert):
        """Test that alerts trigger notifications when thresholds are exceeded."""
        service = BillingService(mock_db)

        # Setup mocks
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            mock_user_billing,  # get_user_billing (first call in check_and_trigger_alerts)
            mock_user,  # get user for email
            mock_user_billing,  # get_user_billing (second call in get_billing_alerts)
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_billing_alert]

        # Mock the get_current_usage to return high usage
        # Note: BillingNotificationService is in notification_service module, not services module
        # Note: BillingNotificationService is in notification_service module, not services module
        with patch.object(service, 'get_current_usage', new_callable=AsyncMock) as mock_get_usage, \
             patch.object(service, 'get_billing_plan') as mock_get_plan, \
             patch('budapp.billing_ops.notification_service.BillingNotificationService') as MockNotificationService:

            mock_get_usage.return_value = {
                "has_billing": True,
                "plan_name": "Professional",
                "usage": {
                    "tokens_used": 800000,
                    "tokens_quota": 1000000,
                    "tokens_usage_percent": 80.0,
                    "cost_used": 80.0,
                    "cost_quota": 100.0,
                    "cost_usage_percent": 80.0,
                },
            }
            mock_get_plan.return_value = mock_billing_plan

            # Setup notification service mock
            mock_notification_instance = MockNotificationService.return_value
            mock_notification_instance.send_usage_alert = AsyncMock(return_value={
                "success": True,
                "channels_sent": ["in_app", "email"],
                "errors": [],
            })

            # Execute
            triggered_alerts = await service.check_and_trigger_alerts(mock_user.id)

            # Verify
            assert len(triggered_alerts) == 1
            assert triggered_alerts[0]["alert_name"] == "75% Token Usage Alert"
            assert triggered_alerts[0]["threshold_percent"] == 75
            assert triggered_alerts[0]["current_percent"] == 80.0

            # Verify notification was sent
            mock_notification_instance.send_usage_alert.assert_called_once()

            # Verify alert was updated
            assert mock_billing_alert.last_triggered_at is not None
            assert mock_billing_alert.last_triggered_value == Decimal("800000")
            assert mock_billing_alert.last_notification_sent_at is not None
            assert mock_billing_alert.notification_failure_count == 0

    @pytest.mark.asyncio
    async def test_check_and_trigger_alerts_notification_failure(self, mock_db, mock_user, mock_user_billing, mock_billing_plan, mock_billing_alert):
        """Test alert notification failure handling."""
        service = BillingService(mock_db)

        # Setup mocks
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            mock_user_billing,  # get_user_billing (first call in check_and_trigger_alerts)
            mock_user,  # get user for email
            mock_user_billing,  # get_user_billing (second call in get_billing_alerts)
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_billing_alert]

        # Note: BillingNotificationService is in notification_service module, not services module
        with patch.object(service, 'get_current_usage', new_callable=AsyncMock) as mock_get_usage, \
             patch.object(service, 'get_billing_plan') as mock_get_plan, \
             patch('budapp.billing_ops.notification_service.BillingNotificationService') as MockNotificationService:

            mock_get_usage.return_value = {
                "has_billing": True,
                "plan_name": "Professional",
                "usage": {
                    "tokens_used": 800000,
                    "tokens_quota": 1000000,
                    "tokens_usage_percent": 80.0,
                    "cost_used": 80.0,
                    "cost_quota": 100.0,
                    "cost_usage_percent": 80.0,
                },
            }
            mock_get_plan.return_value = mock_billing_plan

            # Setup notification service to fail
            mock_notification_instance = MockNotificationService.return_value
            mock_notification_instance.send_usage_alert = AsyncMock(side_effect=Exception("Notification service error"))

            # Execute
            triggered_alerts = await service.check_and_trigger_alerts(mock_user.id)

            # Verify alert was still triggered
            assert len(triggered_alerts) == 1

            # Verify failure was tracked
            assert mock_billing_alert.notification_failure_count == 1
            assert "Notification service error" in mock_billing_alert.last_notification_error

    @pytest.mark.asyncio
    async def test_alert_threshold_value_check(self, mock_db, mock_user, mock_user_billing, mock_billing_plan, mock_billing_alert):
        """Test that alerts don't re-trigger if last_triggered_value is already above threshold."""
        service = BillingService(mock_db)

        # Set last triggered value to 800000 (80% of 1000000)
        mock_billing_alert.last_triggered_at = datetime.now(timezone.utc) - timedelta(hours=12)
        mock_billing_alert.last_triggered_value = Decimal("800000")

        # Setup mocks
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            mock_user_billing,  # get_user_billing (first call in check_and_trigger_alerts)
            mock_user,  # get user for email
            mock_user_billing,  # get_user_billing (second call in get_billing_alerts)
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_billing_alert]

        with patch.object(service, 'get_current_usage', new_callable=AsyncMock) as mock_get_usage:

            # Current usage is 82% - higher than 75% threshold but alert was already triggered at 80%
            mock_get_usage.return_value = {
                "has_billing": True,
                "plan_name": "Professional",
                "usage": {
                    "tokens_used": 820000,  # 82% - slightly higher than before
                    "tokens_quota": 1000000,
                    "tokens_usage_percent": 82.0,
                    "cost_used": 82.0,
                    "cost_quota": 100.0,
                    "cost_usage_percent": 82.0,
                },
            }

            # Execute
            triggered_alerts = await service.check_and_trigger_alerts(mock_user.id)

            # Verify no alerts were triggered (already triggered for a value above threshold)
            assert len(triggered_alerts) == 0

    @pytest.mark.asyncio
    async def test_alert_triggers_when_crossing_new_threshold(self, mock_db, mock_user, mock_user_billing, mock_billing_plan):
        """Test that alert triggers when usage crosses a new threshold."""
        service = BillingService(mock_db)

        # Create two alerts at different thresholds
        mock_alert_75 = Mock(spec=BillingAlert)
        mock_alert_75.id = uuid4()
        mock_alert_75.user_id = mock_user.id
        mock_alert_75.name = "75% Token Usage Alert"
        mock_alert_75.alert_type = "token_usage"
        mock_alert_75.threshold_percent = 75
        mock_alert_75.last_triggered_at = datetime.now(timezone.utc) - timedelta(days=1)
        mock_alert_75.last_triggered_value = Decimal("760000")  # Already triggered at 76%
        mock_alert_75.last_notification_sent_at = None
        mock_alert_75.notification_failure_count = 0
        mock_alert_75.last_notification_error = None
        mock_alert_75.is_active = True

        mock_alert_90 = Mock(spec=BillingAlert)
        mock_alert_90.id = uuid4()
        mock_alert_90.user_id = mock_user.id
        mock_alert_90.name = "90% Token Usage Alert"
        mock_alert_90.alert_type = "token_usage"
        mock_alert_90.threshold_percent = 90
        mock_alert_90.last_triggered_at = None  # Never triggered
        mock_alert_90.last_triggered_value = None
        mock_alert_90.last_notification_sent_at = None
        mock_alert_90.notification_failure_count = 0
        mock_alert_90.last_notification_error = None
        mock_alert_90.is_active = True

        # Setup mocks
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            mock_user_billing,  # get_user_billing (first call in check_and_trigger_alerts)
            mock_user,  # get user for email
            mock_user_billing,  # get_user_billing (second call in get_billing_alerts)
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_alert_75, mock_alert_90]

        with patch.object(service, 'get_current_usage', new_callable=AsyncMock) as mock_get_usage, \
             patch.object(service, 'get_billing_plan') as mock_get_plan, \
             patch('budapp.billing_ops.notification_service.BillingNotificationService') as MockNotificationService:

            # Current usage is 92%
            mock_get_usage.return_value = {
                "has_billing": True,
                "plan_name": "Professional",
                "usage": {
                    "tokens_used": 920000,  # 92%
                    "tokens_quota": 1000000,
                    "tokens_usage_percent": 92.0,
                    "cost_used": 92.0,
                    "cost_quota": 100.0,
                    "cost_usage_percent": 92.0,
                },
            }
            mock_get_plan.return_value = mock_billing_plan

            # Setup notification service mock
            mock_notification_instance = MockNotificationService.return_value
            mock_notification_instance.send_usage_alert = AsyncMock(return_value={
                "success": True,
                "channels_sent": ["in_app", "email"],
                "errors": [],
            })

            # Execute
            triggered_alerts = await service.check_and_trigger_alerts(mock_user.id)

            # Verify only the 90% alert was triggered (75% already triggered at 76%)
            assert len(triggered_alerts) == 1
            assert triggered_alerts[0]["alert_name"] == "90% Token Usage Alert"
            assert triggered_alerts[0]["threshold_percent"] == 90


    @pytest.mark.asyncio
    async def test_reset_user_alerts(self, mock_db, mock_user, mock_user_billing):
        """Test that reset_user_alerts clears all alert tracking fields."""
        service = BillingService(mock_db)

        # Create alerts with tracking data
        mock_alert_1 = Mock(spec=BillingAlert)
        mock_alert_1.id = uuid4()
        mock_alert_1.user_id = mock_user.id
        mock_alert_1.last_triggered_at = datetime.now(timezone.utc)
        mock_alert_1.last_triggered_value = Decimal("750000")
        mock_alert_1.last_notification_sent_at = datetime.now(timezone.utc)
        mock_alert_1.notification_failure_count = 2
        mock_alert_1.last_notification_error = "Previous error"

        mock_alert_2 = Mock(spec=BillingAlert)
        mock_alert_2.id = uuid4()
        mock_alert_2.user_id = mock_user.id
        mock_alert_2.last_triggered_at = datetime.now(timezone.utc)
        mock_alert_2.last_triggered_value = Decimal("900000")
        mock_alert_2.last_notification_sent_at = datetime.now(timezone.utc)
        mock_alert_2.notification_failure_count = 1
        mock_alert_2.last_notification_error = "Some error"

        # Setup mocks
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_user_billing
        mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_alert_1, mock_alert_2]

        # Execute
        service.reset_user_alerts(mock_user.id)

        # Verify all tracking fields were reset
        assert mock_alert_1.last_triggered_at is None
        assert mock_alert_1.last_triggered_value is None
        assert mock_alert_1.last_notification_sent_at is None
        assert mock_alert_1.notification_failure_count == 0
        assert mock_alert_1.last_notification_error is None

        assert mock_alert_2.last_triggered_at is None
        assert mock_alert_2.last_triggered_value is None
        assert mock_alert_2.last_notification_sent_at is None
        assert mock_alert_2.notification_failure_count == 0
        assert mock_alert_2.last_notification_error is None

        # Verify commit was called
        mock_db.commit.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
