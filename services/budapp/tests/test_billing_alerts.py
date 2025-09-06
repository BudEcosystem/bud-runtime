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
        self, user_billing_id, name, alert_type, threshold_percent, last_triggered_at=None
    ):
        """Helper to create a billing alert."""
        alert = MagicMock(spec=BillingAlert)
        alert.id = uuid.uuid4()
        alert.user_billing_id = user_billing_id
        alert.name = name
        alert.alert_type = alert_type
        alert.threshold_percent = threshold_percent
        alert.is_active = True
        alert.last_triggered_at = last_triggered_at
        alert.last_triggered_value = None
        return alert

    @pytest.mark.asyncio
    async def test_check_alerts_no_triggers(self, billing_service, mock_session, user_billing):
        """Test checking alerts when none should trigger."""
        user_id = user_billing.user_id

        # Create alerts
        alerts = [
            self.create_alert(user_billing.id, "50% Token", "token_usage", 50),
            self.create_alert(user_billing.id, "75% Cost", "cost_usage", 75),
        ]

        # Mock database queries
        mock_execute1 = MagicMock()
        mock_execute1.scalar_one_or_none.return_value = user_billing

        mock_execute2 = MagicMock()
        mock_execute2.scalars.return_value.all.return_value = alerts

        mock_session.execute.side_effect = [mock_execute1, mock_execute2]

        # Mock low usage (won't trigger alerts)
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
            mock_get_usage.return_value = {
                "total_tokens": 25000,  # 25% of quota
                "total_cost": 40.00,  # 20% of quota
                "request_count": 500,
                "success_rate": 99.5,
            }

            with patch('budapp.billing_ops.services.BillingNotificationService') as mock_notification_class:
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
        alert_50 = self.create_alert(user_billing.id, "50% Token Alert", "token_usage", 50)
        alert_75 = self.create_alert(user_billing.id, "75% Token Alert", "token_usage", 75)

        # Mock database queries
        mock_execute1 = MagicMock()
        mock_execute1.scalar_one_or_none.return_value = user_billing

        mock_execute2 = MagicMock()
        mock_execute2.scalars.return_value.all.return_value = [alert_50, alert_75]

        mock_session.execute.side_effect = [mock_execute1, mock_execute2]

        # Mock usage that triggers 50% alert only
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
            mock_get_usage.return_value = {
                "total_tokens": 60000,  # 60% of quota (triggers 50% alert)
                "total_cost": 50.00,
                "request_count": 1200,
                "success_rate": 99.0,
            }

            with patch('budapp.billing_ops.services.BillingNotificationService') as mock_notification_class:
                mock_notification_service = MagicMock()
                mock_notification_service.send_usage_alert.return_value = {"success": True}
                mock_notification_class.return_value = mock_notification_service

                result = await billing_service.check_and_trigger_alerts(user_id)

                assert len(result) == 1
                assert "50% Token Alert" in result
                assert alert_50.last_triggered_at is not None
                assert alert_75.last_triggered_at is None

    @pytest.mark.asyncio
    async def test_check_alerts_multiple_triggers(self, billing_service, mock_session, user_billing):
        """Test multiple alerts triggering."""
        user_id = user_billing.user_id

        # Create multiple alerts
        alerts = [
            self.create_alert(user_billing.id, "25% Token", "token_usage", 25),
            self.create_alert(user_billing.id, "50% Token", "token_usage", 50),
            self.create_alert(user_billing.id, "75% Token", "token_usage", 75),
            self.create_alert(user_billing.id, "50% Cost", "cost_usage", 50),
        ]

        # Mock database queries
        mock_execute1 = MagicMock()
        mock_execute1.scalar_one_or_none.return_value = user_billing

        mock_execute2 = MagicMock()
        mock_execute2.scalars.return_value.all.return_value = alerts

        mock_session.execute.side_effect = [mock_execute1, mock_execute2]

        # Mock usage that triggers multiple alerts
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
            mock_get_usage.return_value = {
                "total_tokens": 80000,  # 80% (triggers 25%, 50%, 75%)
                "total_cost": 120.00,  # 60% (triggers 50% cost)
                "request_count": 1600,
                "success_rate": 98.5,
            }

            with patch('budapp.billing_ops.services.BillingNotificationService') as mock_notification_class:
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

        # Create alert that was recently triggered
        recent_trigger = datetime.now(timezone.utc) - timedelta(hours=1)
        alert = self.create_alert(
            user_billing.id,
            "50% Token Alert",
            "token_usage",
            50,
            last_triggered_at=recent_trigger
        )

        # Mock database queries
        mock_execute1 = MagicMock()
        mock_execute1.scalar_one_or_none.return_value = user_billing

        mock_execute2 = MagicMock()
        mock_execute2.scalars.return_value.all.return_value = [alert]

        mock_session.execute.side_effect = [mock_execute1, mock_execute2]

        # Mock usage that would trigger alert
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
            mock_get_usage.return_value = {
                "total_tokens": 60000,  # Still above 50%
                "total_cost": 50.00,
                "request_count": 1200,
                "success_rate": 99.0,
            }

            with patch('budapp.billing_ops.services.BillingNotificationService') as mock_notification_class:
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

        alert_100 = self.create_alert(user_billing.id, "100% Token Alert", "token_usage", 100)

        # Mock database queries
        mock_execute1 = MagicMock()
        mock_execute1.scalar_one_or_none.return_value = user_billing

        mock_execute2 = MagicMock()
        mock_execute2.scalars.return_value.all.return_value = [alert_100]

        mock_session.execute.side_effect = [mock_execute1, mock_execute2]

        # Mock usage at exactly 100%
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
            mock_get_usage.return_value = {
                "total_tokens": 100000,  # Exactly 100%
                "total_cost": 150.00,
                "request_count": 2000,
                "success_rate": 99.0,
            }

            with patch('budapp.billing_ops.services.BillingNotificationService') as mock_notification_class:
                mock_notification_service = MagicMock()
                mock_notification_service.send_usage_alert.return_value = {"success": True}
                mock_notification_class.return_value = mock_notification_service

                result = await billing_service.check_and_trigger_alerts(user_id)

                assert len(result) == 1
                assert "100% Token Alert" in result

    @pytest.mark.asyncio
    async def test_alert_exceeded_threshold(self, billing_service, mock_session, user_billing):
        """Test alert when usage exceeds 100%."""
        user_id = user_billing.user_id

        # Create various threshold alerts
        alerts = [
            self.create_alert(user_billing.id, "90% Token", "token_usage", 90),
            self.create_alert(user_billing.id, "100% Token", "token_usage", 100),
            self.create_alert(user_billing.id, "90% Cost", "cost_usage", 90),
        ]

        # Mock database queries
        mock_execute1 = MagicMock()
        mock_execute1.scalar_one_or_none.return_value = user_billing

        mock_execute2 = MagicMock()
        mock_execute2.scalars.return_value.all.return_value = alerts

        mock_session.execute.side_effect = [mock_execute1, mock_execute2]

        # Mock usage exceeding 100%
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
            mock_get_usage.return_value = {
                "total_tokens": 150000,  # 150% of quota
                "total_cost": 250.00,  # 125% of quota
                "request_count": 3000,
                "success_rate": 98.0,
            }

            with patch('budapp.billing_ops.services.BillingNotificationService') as mock_notification_class:
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
        active_alert = self.create_alert(user_billing.id, "Active Alert", "token_usage", 50)
        inactive_alert = self.create_alert(user_billing.id, "Inactive Alert", "token_usage", 50)
        inactive_alert.is_active = False

        # Mock database queries
        mock_execute1 = MagicMock()
        mock_execute1.scalar_one_or_none.return_value = user_billing

        mock_execute2 = MagicMock()
        mock_execute2.scalars.return_value.all.return_value = [active_alert, inactive_alert]

        mock_session.execute.side_effect = [mock_execute1, mock_execute2]

        # Mock usage that would trigger both if active
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
            mock_get_usage.return_value = {
                "total_tokens": 60000,  # 60% of quota
                "total_cost": 50.00,
                "request_count": 1200,
                "success_rate": 99.0,
            }

            with patch('budapp.billing_ops.services.BillingNotificationService') as mock_notification_class:
                mock_notification_service = MagicMock()
                mock_notification_service.send_usage_alert.return_value = {"success": True}
                mock_notification_class.return_value = mock_notification_service

                result = await billing_service.check_and_trigger_alerts(user_id)

                # Only active alert should trigger
                assert len(result) == 1
                assert "Active Alert" in result
                assert active_alert.last_triggered_at is not None
                assert inactive_alert.last_triggered_at is None

    @pytest.mark.asyncio
    async def test_alert_with_custom_quotas(self, billing_service, mock_session, user_billing):
        """Test alerts work correctly with custom quotas."""
        user_id = user_billing.user_id

        # Set custom quotas
        user_billing.custom_token_quota = 150000  # Higher than plan's 100000
        user_billing.custom_cost_quota = Decimal("300.00")  # Higher than plan's 200.00

        alert = self.create_alert(user_billing.id, "50% Custom Token", "token_usage", 50)

        # Mock database queries
        mock_execute1 = MagicMock()
        mock_execute1.scalar_one_or_none.return_value = user_billing

        mock_execute2 = MagicMock()
        mock_execute2.scalars.return_value.all.return_value = [alert]

        mock_session.execute.side_effect = [mock_execute1, mock_execute2]

        # Mock usage that's 50% of custom quota
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
            mock_get_usage.return_value = {
                "total_tokens": 75000,  # 50% of custom 150000
                "total_cost": 100.00,
                "request_count": 1500,
                "success_rate": 99.0,
            }

            with patch('budapp.billing_ops.services.BillingNotificationService') as mock_notification_class:
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

        alert = self.create_alert(user_billing.id, "50% Alert", "token_usage", 50)

        # Mock database queries
        mock_execute1 = MagicMock()
        mock_execute1.scalar_one_or_none.return_value = user_billing

        mock_execute2 = MagicMock()
        mock_execute2.scalars.return_value.all.return_value = [alert]

        mock_session.execute.side_effect = [mock_execute1, mock_execute2]

        # Mock usage that triggers alert
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
            mock_get_usage.return_value = {
                "total_tokens": 60000,
                "total_cost": 50.00,
                "request_count": 1200,
                "success_rate": 99.0,
            }

            # Mock notification failure
            with patch('budapp.billing_ops.services.BillingNotificationService') as mock_notification_class:
                mock_notification_service = MagicMock()
                mock_notification_service.send_usage_alert.side_effect = Exception("Notification service down")
                mock_notification_class.return_value = mock_notification_service

                # Should not raise exception
                result = await billing_service.check_and_trigger_alerts(user_id)

                # Alert should still be marked as triggered
                assert len(result) == 1
                assert alert.last_triggered_at is not None
