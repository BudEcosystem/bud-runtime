"""Tests for billing alert functionality."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from budapp.billing_ops.models import BillingAlert, BillingPlan, UserBilling
from budapp.billing_ops.services import BillingService


class TestBillingAlerts:
    """Test billing alert functionality."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return MagicMock(spec=Session)

    @pytest.fixture
    def billing_service(self, mock_session):
        """Create a BillingService instance."""
        return BillingService(mock_session)

    @pytest.fixture
    def billing_plan(self):
        """Create a test billing plan."""
        plan = MagicMock(spec=BillingPlan)
        plan.id = uuid.uuid4()
        plan.name = "Alert Test Plan"
        plan.monthly_token_quota = 100000
        plan.monthly_cost_quota = Decimal("200.00")
        return plan

    @pytest.fixture
    def user_billing(self, billing_plan):
        """Create test user billing."""
        user_billing = MagicMock(spec=UserBilling)
        user_billing.id = uuid.uuid4()
        user_billing.user_id = uuid.uuid4()
        user_billing.billing_plan = billing_plan
        user_billing.custom_token_quota = None
        user_billing.custom_cost_quota = None
        user_billing.billing_period_start = datetime.now(timezone.utc).replace(day=1)
        user_billing.billing_period_end = datetime.now(timezone.utc).replace(month=12)
        return user_billing

    def create_alert(
        self, user_id, name, alert_type, threshold_percent, last_triggered_at=None, last_triggered_value=None
    ):
        """Helper to create a billing alert."""
        alert = MagicMock(spec=BillingAlert)
        alert.id = uuid.uuid4()
        alert.user_id = user_id
        alert.name = name
        alert.alert_type = alert_type
        alert.threshold_percent = threshold_percent
        alert.is_active = True
        alert.last_triggered_at = last_triggered_at
        alert.last_triggered_value = last_triggered_value
        return alert

    def setup_database_mocks(self, mock_session, user_billing, alerts):
        """Helper to set up database mocks for check_and_trigger_alerts method."""
        # The check_and_trigger_alerts method makes several database calls:
        # 1. get_user_billing (returns user_billing)
        # 2. User query (for user email)
        # 3. get_billing_alerts (returns only active alerts)

        mock_user_billing_result = MagicMock()
        mock_user_billing_result.scalar_one_or_none.return_value = user_billing

        mock_user_result = MagicMock()
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user_result.scalar_one_or_none.return_value = mock_user

        # Filter alerts to only include active ones (mimics the database query behavior)
        active_alerts = [alert for alert in alerts if alert.is_active]
        mock_alerts_result = MagicMock()
        mock_alerts_result.scalars.return_value.all.return_value = active_alerts

        mock_session.execute.side_effect = [mock_user_billing_result, mock_user_result, mock_alerts_result]

    def create_usage_mock(self, tokens_percent, cost_percent, tokens_quota=100000, cost_quota=200.00):
        """Helper to create usage data mock for get_current_usage."""
        tokens_used = int(tokens_quota * tokens_percent / 100)
        cost_used = float(cost_quota * cost_percent / 100)

        return {
            "has_billing": True,
            "usage": {
                "tokens_used": tokens_used,
                "tokens_quota": tokens_quota,
                "tokens_usage_percent": tokens_percent,
                "cost_used": cost_used,
                "cost_quota": cost_quota,
                "cost_usage_percent": cost_percent,
                "request_count": 1000,
                "success_rate": 99.0,
            },
            "plan_name": "Test Plan"
        }

    @pytest.mark.asyncio
    async def test_check_alerts_no_triggers(self, billing_service, mock_session, user_billing):
        """Test checking alerts when none should trigger."""
        user_id = user_billing.user_id

        # Create alerts
        alerts = [
            self.create_alert(user_billing.user_id, "50% Token", "token_usage", 50),
            self.create_alert(user_billing.user_id, "75% Cost", "cost_usage", 75),
        ]

        # Set up database mocks
        self.setup_database_mocks(mock_session, user_billing, alerts)

        # Mock low usage (won't trigger alerts)
        with patch.object(billing_service, 'get_current_usage') as mock_get_current_usage:
            mock_get_current_usage.return_value = self.create_usage_mock(25, 20)  # 25% tokens, 20% cost

            with patch('budapp.billing_ops.notification_service.BillingNotificationService') as mock_notification_class:
                mock_notification_service = MagicMock()
                mock_notification_class.return_value = mock_notification_service

                result = await billing_service.check_and_trigger_alerts(user_id)

                assert len(result) == 0
                mock_notification_service.send_usage_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_alerts_single_trigger(self, billing_service, mock_session, user_billing):
        """Test single alert triggering."""
        user_id = user_billing.user_id

        # Create alerts
        alert_50 = self.create_alert(user_billing.user_id, "50% Token Alert", "token_usage", 50)
        alert_75 = self.create_alert(user_billing.user_id, "75% Token Alert", "token_usage", 75)

        # Set up database mocks
        self.setup_database_mocks(mock_session, user_billing, [alert_50, alert_75])

        # Mock usage that triggers 50% alert only
        with patch.object(billing_service, 'get_current_usage') as mock_get_current_usage:
            mock_get_current_usage.return_value = self.create_usage_mock(60, 25)  # 60% tokens, 25% cost

            with patch('budapp.billing_ops.notification_service.BillingNotificationService') as mock_notification_class:
                mock_notification_service = MagicMock()
                mock_notification_service.send_usage_alert.return_value = {"success": True}
                mock_notification_class.return_value = mock_notification_service

                result = await billing_service.check_and_trigger_alerts(user_id)

                assert len(result) == 1
                assert result[0]["alert_name"] == "50% Token Alert"
                assert result[0]["alert_type"] == "token_usage"
                assert result[0]["current_percent"] == 60
                assert alert_50.last_triggered_at is not None
                assert alert_75.last_triggered_at is None

    @pytest.mark.asyncio
    async def test_check_alerts_multiple_triggers(self, billing_service, mock_session, user_billing):
        """Test multiple alerts triggering."""
        user_id = user_billing.user_id

        # Create multiple alerts
        alerts = [
            self.create_alert(user_billing.user_id, "25% Token", "token_usage", 25),
            self.create_alert(user_billing.user_id, "50% Token", "token_usage", 50),
            self.create_alert(user_billing.user_id, "75% Token", "token_usage", 75),
            self.create_alert(user_billing.user_id, "50% Cost", "cost_usage", 50),
        ]

        # Set up database mocks
        self.setup_database_mocks(mock_session, user_billing, alerts)

        # Mock usage that triggers multiple alerts
        with patch.object(billing_service, 'get_current_usage') as mock_get_current_usage:
            mock_get_current_usage.return_value = self.create_usage_mock(80, 60)  # 80% tokens, 60% cost

            with patch('budapp.billing_ops.notification_service.BillingNotificationService') as mock_notification_class:
                mock_notification_service = MagicMock()
                mock_notification_service.send_usage_alert.return_value = {"success": True}
                mock_notification_class.return_value = mock_notification_service

                result = await billing_service.check_and_trigger_alerts(user_id)

                assert len(result) == 4
                assert all(alert.last_triggered_at is not None for alert in alerts)

    @pytest.mark.asyncio
    async def test_alert_cooldown_period(self, billing_service, mock_session, user_billing):
        """Test alert cooldown period to prevent spam."""
        user_id = user_billing.user_id

        # Create alert that was recently triggered at a higher usage level
        recent_trigger = datetime.now(timezone.utc) - timedelta(hours=1)
        alert = self.create_alert(
            user_billing.user_id,
            "50% Token Alert",
            "token_usage",
            50,
            last_triggered_at=recent_trigger,
            last_triggered_value=Decimal("60000")  # Previously triggered at 60K tokens, same as current usage
        )

        # Set up database mocks
        self.setup_database_mocks(mock_session, user_billing, [alert])

        # Mock usage that would trigger alert
        with patch.object(billing_service, 'get_current_usage') as mock_get_current_usage:
            mock_get_current_usage.return_value = self.create_usage_mock(60, 25)  # 60% tokens, 25% cost

            with patch('budapp.billing_ops.notification_service.BillingNotificationService') as mock_notification_class:
                mock_notification_service = MagicMock()
                mock_notification_class.return_value = mock_notification_service

                result = await billing_service.check_and_trigger_alerts(user_id)

                # Alert should not trigger again due to cooldown
                assert len(result) == 0
                mock_notification_service.send_usage_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_alert_100_percent_trigger(self, billing_service, mock_session, user_billing):
        """Test 100% usage alert."""
        user_id = user_billing.user_id

        alert_100 = self.create_alert(user_billing.user_id, "100% Token Alert", "token_usage", 100)

        # Set up database mocks
        self.setup_database_mocks(mock_session, user_billing, [alert_100])

        # Mock usage at exactly 100%
        with patch.object(billing_service, 'get_current_usage') as mock_get_current_usage:
            mock_get_current_usage.return_value = self.create_usage_mock(100, 75)  # 100% tokens, 75% cost

            with patch('budapp.billing_ops.notification_service.BillingNotificationService') as mock_notification_class:
                mock_notification_service = MagicMock()
                mock_notification_service.send_usage_alert.return_value = {"success": True}
                mock_notification_class.return_value = mock_notification_service

                result = await billing_service.check_and_trigger_alerts(user_id)

                assert len(result) == 1
                assert result[0]["alert_name"] == "100% Token Alert"
                assert result[0]["alert_type"] == "token_usage"
                assert result[0]["current_percent"] == 100

    @pytest.mark.asyncio
    async def test_alert_exceeded_threshold(self, billing_service, mock_session, user_billing):
        """Test alert when usage exceeds 100%."""
        user_id = user_billing.user_id

        # Create various threshold alerts
        alerts = [
            self.create_alert(user_billing.user_id, "90% Token", "token_usage", 90),
            self.create_alert(user_billing.user_id, "100% Token", "token_usage", 100),
            self.create_alert(user_billing.user_id, "90% Cost", "cost_usage", 90),
        ]

        # Set up database mocks
        self.setup_database_mocks(mock_session, user_billing, alerts)

        # Mock usage exceeding 100%
        with patch.object(billing_service, 'get_current_usage') as mock_get_current_usage:
            mock_get_current_usage.return_value = self.create_usage_mock(150, 125)  # 150% tokens, 125% cost

            with patch('budapp.billing_ops.notification_service.BillingNotificationService') as mock_notification_class:
                mock_notification_service = MagicMock()
                mock_notification_service.send_usage_alert.return_value = {"success": True}
                mock_notification_class.return_value = mock_notification_service

                result = await billing_service.check_and_trigger_alerts(user_id)

                # All alerts should trigger when exceeded
                assert len(result) == 3

    @pytest.mark.asyncio
    async def test_inactive_alerts_not_triggered(self, billing_service, mock_session, user_billing):
        """Test that inactive alerts are not triggered."""
        user_id = user_billing.user_id

        # Create mix of active and inactive alerts
        active_alert = self.create_alert(user_billing.user_id, "Active Alert", "token_usage", 50)
        inactive_alert = self.create_alert(user_billing.user_id, "Inactive Alert", "token_usage", 50)
        inactive_alert.is_active = False

        # Set up database mocks
        self.setup_database_mocks(mock_session, user_billing, [active_alert, inactive_alert])

        # Mock usage that would trigger both if active
        with patch.object(billing_service, 'get_current_usage') as mock_get_current_usage:
            mock_get_current_usage.return_value = self.create_usage_mock(60, 25)  # 60% tokens, 25% cost

            with patch('budapp.billing_ops.notification_service.BillingNotificationService') as mock_notification_class:
                mock_notification_service = MagicMock()
                mock_notification_service.send_usage_alert.return_value = {"success": True}
                mock_notification_class.return_value = mock_notification_service

                result = await billing_service.check_and_trigger_alerts(user_id)

                # Only active alert should trigger
                assert len(result) == 1
                assert result[0]["alert_name"] == "Active Alert"
                assert result[0]["alert_type"] == "token_usage"
                assert result[0]["current_percent"] == 60
                assert active_alert.last_triggered_at is not None
                assert inactive_alert.last_triggered_at is None

    @pytest.mark.asyncio
    async def test_alert_with_custom_quotas(self, billing_service, mock_session, user_billing):
        """Test alerts work correctly with custom quotas."""
        user_id = user_billing.user_id

        # Set custom quotas
        user_billing.custom_token_quota = 150000  # Higher than plan's 100000
        user_billing.custom_cost_quota = Decimal("300.00")  # Higher than plan's 200.00

        alert = self.create_alert(user_billing.user_id, "50% Custom Token", "token_usage", 50)

        # Set up database mocks
        self.setup_database_mocks(mock_session, user_billing, [alert])

        # Mock usage that's 50% of custom quota
        with patch.object(billing_service, 'get_current_usage') as mock_get_current_usage:
            mock_get_current_usage.return_value = self.create_usage_mock(50, 33, tokens_quota=150000, cost_quota=300.00)  # 50% of custom quotas

            with patch('budapp.billing_ops.notification_service.BillingNotificationService') as mock_notification_class:
                mock_notification_service = MagicMock()
                mock_notification_service.send_usage_alert.return_value = {"success": True}
                mock_notification_class.return_value = mock_notification_service

                result = await billing_service.check_and_trigger_alerts(user_id)

                assert len(result) == 1
                assert alert.last_triggered_value == Decimal("75000")

    @pytest.mark.asyncio
    async def test_alert_notification_error_handling(self, billing_service, mock_session, user_billing):
        """Test alert continues even if notification fails."""
        user_id = user_billing.user_id

        alert = self.create_alert(user_billing.user_id, "50% Alert", "token_usage", 50)

        # Set up database mocks
        self.setup_database_mocks(mock_session, user_billing, [alert])

        # Mock usage that triggers alert
        with patch.object(billing_service, 'get_current_usage') as mock_get_current_usage:
            mock_get_current_usage.return_value = self.create_usage_mock(60, 25)  # 60% tokens, 25% cost

            # Mock notification failure
            with patch('budapp.billing_ops.notification_service.BillingNotificationService') as mock_notification_class:
                mock_notification_service = MagicMock()
                mock_notification_service.send_usage_alert.side_effect = Exception("Notification service down")
                mock_notification_class.return_value = mock_notification_service

                # Should not raise exception
                result = await billing_service.check_and_trigger_alerts(user_id)

                # Alert should still be marked as triggered
                assert len(result) == 1
                assert alert.last_triggered_at is not None
