"""Tests for billing service methods."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.orm import Session


class TestBillingService:
    """Test BillingService methods."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return MagicMock(spec=Session)

    @pytest.fixture
    def billing_service(self, mock_session):
        """Create a BillingService instance with mock session."""
        from budapp.billing_ops.services import BillingService
        return BillingService(mock_session)

    @pytest.mark.asyncio
    async def test_get_usage_from_clickhouse_success(self, billing_service):
        """Test successful usage retrieval from ClickHouse."""
        user_id = uuid.uuid4()
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
        end_date = datetime.now(timezone.utc)

        # Mock the HTTP response
        mock_response = {
            "param": {
                "total_tokens": 50000,
                "total_cost": 125.50,
                "request_count": 1500,
                "success_rate": 98.5,
            }
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_async_client = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_async_client

            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status.return_value = None
            mock_async_client.get.return_value = mock_response_obj

            result = await billing_service.get_usage_from_clickhouse(
                user_id, start_date, end_date
            )

            assert result["total_tokens"] == 50000
            assert result["total_cost"] == 125.50
            assert result["request_count"] == 1500
            assert result["success_rate"] == 98.5

    @pytest.mark.asyncio
    async def test_get_usage_from_clickhouse_with_project_filter(self, billing_service):
        """Test usage retrieval with project filter."""
        user_id = uuid.uuid4()
        project_id = uuid.uuid4()
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)

        mock_response = {
            "param": {
                "total_tokens": 10000,
                "total_cost": 25.00,
                "request_count": 300,
                "success_rate": 99.0,
            }
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_async_client = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_async_client

            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status.return_value = None
            mock_async_client.get.return_value = mock_response_obj

            await billing_service.get_usage_from_clickhouse(
                user_id, start_date, end_date, project_id
            )

            # Verify the correct parameters were passed
            mock_async_client.get.assert_called_once()
            call_args = mock_async_client.get.call_args
            assert call_args[1]["params"]["project_id"] == str(project_id)

    @pytest.mark.asyncio
    async def test_get_usage_from_clickhouse_error_handling(self, billing_service):
        """Test error handling in usage retrieval."""
        user_id = uuid.uuid4()
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
        end_date = datetime.now(timezone.utc)

        with patch('httpx.AsyncClient') as mock_client:
            mock_async_client = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_async_client
            mock_async_client.get.side_effect = httpx.HTTPError("Connection failed")

            result = await billing_service.get_usage_from_clickhouse(
                user_id, start_date, end_date
            )

            # Should return empty usage on error
            assert result["total_tokens"] == 0
            assert result["total_cost"] == 0.0
            assert result["request_count"] == 0
            assert result["success_rate"] == 0.0

    def test_get_user_billing(self, billing_service, mock_session):
        """Test retrieving user billing information."""
        from budapp.billing_ops.models import UserBilling
        user_id = uuid.uuid4()
        mock_user_billing = MagicMock(spec=UserBilling)

        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = mock_user_billing
        mock_session.execute.return_value = mock_execute

        result = billing_service.get_user_billing(user_id)

        assert result == mock_user_billing
        mock_session.execute.assert_called_once()

    def test_get_billing_plan(self, billing_service, mock_session):
        """Test retrieving billing plan."""
        from budapp.billing_ops.models import BillingPlan
        plan_id = uuid.uuid4()
        mock_plan = MagicMock(spec=BillingPlan)

        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = mock_plan
        mock_session.execute.return_value = mock_execute

        result = billing_service.get_billing_plan(plan_id)

        assert result == mock_plan

    def test_create_user_billing(self, billing_service, mock_session):
        """Test creating user billing."""
        from budapp.billing_ops.models import UserBilling
        user_id = uuid.uuid4()
        plan_id = uuid.uuid4()
        custom_token_quota = 75000
        custom_cost_quota = Decimal("150.00")

        # Mock the service methods that are called by create_user_billing
        with patch.object(billing_service, 'get_user_billing') as mock_get_user_billing, \
             patch.object(billing_service, 'get_user_billing_history') as mock_get_history, \
             patch('budapp.billing_ops.services.UserBilling') as MockUserBilling:

            # Mock no existing current billing
            mock_get_user_billing.return_value = None

            # Mock empty billing history (first billing record)
            mock_get_history.return_value = []

            # Mock the UserBilling constructor
            mock_user_billing = MagicMock(spec=UserBilling)
            mock_user_billing.user_id = user_id
            mock_user_billing.billing_plan_id = plan_id
            mock_user_billing.custom_token_quota = custom_token_quota
            mock_user_billing.custom_cost_quota = custom_cost_quota
            mock_user_billing.is_active = True
            mock_user_billing.is_suspended = False
            mock_user_billing.is_current = True
            mock_user_billing.cycle_number = 1
            MockUserBilling.return_value = mock_user_billing

            result = billing_service.create_user_billing(
                user_id=user_id,
                billing_plan_id=plan_id,
                custom_token_quota=custom_token_quota,
                custom_cost_quota=custom_cost_quota,
            )

            # Verify get_user_billing was called to check for existing billing
            mock_get_user_billing.assert_called_once_with(user_id)

            # Verify get_user_billing_history was called to determine cycle number
            mock_get_history.assert_called_once_with(user_id)

            # Verify UserBilling was created with correct parameters
            MockUserBilling.assert_called_once()
            call_args = MockUserBilling.call_args[1]
            assert call_args['user_id'] == user_id
            assert call_args['billing_plan_id'] == plan_id
            assert call_args['custom_token_quota'] == custom_token_quota
            assert call_args['custom_cost_quota'] == custom_cost_quota
            assert call_args['is_current'] is True
            assert call_args['cycle_number'] == 1

            # Verify returned object has expected attributes
            assert result.user_id == user_id
            assert result.billing_plan_id == plan_id
            assert result.custom_token_quota == custom_token_quota
            assert result.custom_cost_quota == custom_cost_quota
            assert result.is_active is True
            assert result.is_suspended is False
            assert result.is_current is True
            assert result.cycle_number == 1

            # Verify it was added to session
            mock_session.add.assert_called_once_with(mock_user_billing)
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once_with(mock_user_billing)

    def test_get_billing_alerts(self, billing_service, mock_session):
        """Test retrieving billing alerts for a user."""
        from budapp.billing_ops.models import BillingAlert, UserBilling
        user_id = uuid.uuid4()
        user_billing_id = uuid.uuid4()

        # Mock user billing
        mock_user_billing = MagicMock(spec=UserBilling)
        mock_user_billing.id = user_billing_id
        mock_user_billing.user_id = user_id

        # Mock alerts
        mock_alerts = [
            MagicMock(spec=BillingAlert, threshold_percent=50),
            MagicMock(spec=BillingAlert, threshold_percent=75),
        ]

        # Setup mock returns - get_billing_alerts only makes one execute call
        mock_execute = MagicMock()
        mock_execute.scalars.return_value.all.return_value = mock_alerts
        mock_session.execute.return_value = mock_execute

        result = billing_service.get_billing_alerts(user_id)

        assert len(result) == 2
        assert result == mock_alerts

    @pytest.mark.asyncio
    async def test_get_current_usage(self, billing_service, mock_session):
        """Test getting current billing period usage."""
        from budapp.billing_ops.models import BillingPlan, UserBilling
        user_id = uuid.uuid4()
        plan_id = uuid.uuid4()

        # Mock billing plan
        mock_plan = MagicMock(spec=BillingPlan)
        mock_plan.id = plan_id
        mock_plan.name = "Standard Plan"
        mock_plan.monthly_token_quota = 100000
        mock_plan.monthly_cost_quota = Decimal("200.00")
        mock_plan.base_monthly_price = Decimal("49.00")

        # Mock user billing
        mock_user_billing = MagicMock(spec=UserBilling)
        mock_user_billing.billing_plan_id = plan_id
        mock_user_billing.billing_plan = mock_plan
        mock_user_billing.custom_token_quota = None
        mock_user_billing.custom_cost_quota = None
        mock_user_billing.billing_period_start = datetime.now(timezone.utc).replace(day=1)
        mock_user_billing.billing_period_end = datetime.now(timezone.utc).replace(month=12)
        mock_user_billing.is_suspended = False

        # Setup mock returns
        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = mock_user_billing
        mock_session.execute.return_value = mock_execute

        # Mock the get_billing_plan method call
        with patch.object(billing_service, 'get_billing_plan') as mock_get_plan, \
             patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:

            mock_get_plan.return_value = mock_plan
            mock_get_usage.return_value = {
                "total_tokens": 25000,
                "total_cost": 50.00,
                "request_count": 500,
                "success_rate": 99.5,
            }

            result = await billing_service.get_current_usage(user_id)

            assert result["has_billing"] is True
            assert result["plan_name"] == "Standard Plan"
            assert result["base_monthly_price"] == 49.00
            assert result["usage"]["tokens_used"] == 25000
            assert result["usage"]["tokens_quota"] == 100000
            assert result["usage"]["tokens_usage_percent"] == 25.0
            assert result["usage"]["cost_used"] == 50.00
            assert result["usage"]["cost_quota"] == 200.00

    @pytest.mark.asyncio
    async def test_get_current_usage_no_billing(self, billing_service, mock_session):
        """Test getting usage when user has no billing setup."""
        user_id = uuid.uuid4()

        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_execute

        # Mock the methods called when no billing exists to avoid HTTP calls
        with patch.object(billing_service, 'get_free_billing_plan') as mock_get_free_plan, \
             patch.object(billing_service, '_get_default_free_plan') as mock_get_default_plan, \
             patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:

            # Return None for free plan from DB, but provide default free plan
            mock_get_free_plan.return_value = None
            mock_get_default_plan.return_value = {
                "name": "Free",
                "base_monthly_price": 0,
                "monthly_token_quota": 100000,
                "monthly_cost_quota": None,
                "max_projects": 2,
                "max_endpoints_per_project": 3,
            }
            mock_get_usage.return_value = {
                "total_tokens": 1000,
                "total_cost": 0.0,
                "request_count": 10,
                "success_rate": 100.0,
            }

            result = await billing_service.get_current_usage(user_id)

            # Users without billing setup should have has_billing False
            assert result["has_billing"] is False
            assert result["plan_name"] == "No Plan"
            assert result["base_monthly_price"] == 0.0
            assert result["usage"]["tokens_used"] == 0  # Service returns 0 for no billing
            assert result["usage"]["tokens_quota"] == 100000  # From free plan quota

    @pytest.mark.asyncio
    async def test_check_usage_limits_within_limits(self, billing_service, mock_session):
        """Test checking usage limits when within limits."""
        from budapp.billing_ops.models import BillingPlan, UserBilling
        user_id = uuid.uuid4()

        # Mock user billing and plan
        mock_plan = MagicMock(spec=BillingPlan)
        mock_plan.monthly_token_quota = 100000
        mock_plan.monthly_cost_quota = Decimal("200.00")

        mock_user_billing = MagicMock(spec=UserBilling)
        mock_user_billing.billing_plan = mock_plan
        mock_user_billing.custom_token_quota = None
        mock_user_billing.custom_cost_quota = None
        mock_user_billing.billing_period_start = datetime.now(timezone.utc).replace(day=1)
        mock_user_billing.billing_period_end = datetime.now(timezone.utc).replace(month=12)
        mock_user_billing.created_at = datetime.now(timezone.utc)
        mock_user_billing.is_suspended = False
        mock_user_billing.suspension_reason = None

        # Create a mock user with user_type attribute (required by check_usage_limits)
        from budapp.commons.constants import UserTypeEnum
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.user_type = UserTypeEnum.CLIENT

        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_execute

        # Mock the session.query() method that the service actually uses
        mock_query = MagicMock()
        mock_filter_by = MagicMock()
        mock_filter_by.first.return_value = mock_user
        mock_query.filter_by.return_value = mock_filter_by
        mock_session.query.return_value = mock_query

        # Mock ClickHouse usage (below limits)
        with patch.object(billing_service, 'get_user_billing') as mock_get_user_billing, \
             patch.object(billing_service, 'get_billing_plan') as mock_get_plan, \
             patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:

            mock_get_user_billing.return_value = mock_user_billing

            mock_get_plan.return_value = mock_plan
            mock_get_usage.return_value = {
                "total_tokens": 50000,
                "total_cost": 100.00,
                "request_count": 1000,
                "success_rate": 99.0,
            }

            result = await billing_service.check_usage_limits(user_id)

            assert result["allowed"] is True
            assert result["status"] == "allowed"

    @pytest.mark.asyncio
    async def test_check_usage_limits_exceeded(self, billing_service, mock_session):
        """Test checking usage limits when exceeded."""
        from budapp.billing_ops.models import BillingPlan, UserBilling
        user_id = uuid.uuid4()

        # Mock user billing and plan
        mock_plan = MagicMock(spec=BillingPlan)
        mock_plan.monthly_token_quota = 100000
        mock_plan.monthly_cost_quota = Decimal("200.00")

        mock_user_billing = MagicMock(spec=UserBilling)
        mock_user_billing.billing_plan = mock_plan
        mock_user_billing.custom_token_quota = None
        mock_user_billing.custom_cost_quota = None
        mock_user_billing.billing_period_start = datetime.now(timezone.utc).replace(day=1)
        mock_user_billing.billing_period_end = datetime.now(timezone.utc).replace(month=12)
        mock_user_billing.created_at = datetime.now(timezone.utc)
        mock_user_billing.is_suspended = False
        mock_user_billing.suspension_reason = None

        # Create a mock user with user_type attribute (required by check_usage_limits)
        from budapp.commons.constants import UserTypeEnum
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.user_type = UserTypeEnum.CLIENT

        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_execute

        # Mock the session.query() method that the service actually uses
        mock_query = MagicMock()
        mock_filter_by = MagicMock()
        mock_filter_by.first.return_value = mock_user
        mock_query.filter_by.return_value = mock_filter_by
        mock_session.query.return_value = mock_query

        # Mock ClickHouse usage (exceeds limits)
        with patch.object(billing_service, 'get_user_billing') as mock_get_user_billing, \
             patch.object(billing_service, 'get_billing_plan') as mock_get_plan, \
             patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:

            mock_get_user_billing.return_value = mock_user_billing

            mock_get_plan.return_value = mock_plan
            mock_get_usage.return_value = {
                "total_tokens": 150000,  # Exceeds 100000
                "total_cost": 250.00,  # Exceeds 200.00
                "request_count": 3000,
                "success_rate": 99.0,
            }

            result = await billing_service.check_usage_limits(user_id)

            assert result["allowed"] is False
            assert result["status"] == "token_limit_exceeded"
            assert result["tokens_used"] == 150000
            assert result["tokens_quota"] == 100000

    @pytest.mark.asyncio
    async def test_check_and_trigger_alerts(self, billing_service, mock_session):
        """Test checking and triggering billing alerts."""
        from budapp.billing_ops.models import BillingAlert, BillingPlan, UserBilling
        user_id = uuid.uuid4()
        user_billing_id = uuid.uuid4()

        # Mock billing plan
        mock_plan = MagicMock(spec=BillingPlan)
        mock_plan.monthly_token_quota = 100000
        mock_plan.monthly_cost_quota = Decimal("200.00")

        # Mock user billing
        mock_user_billing = MagicMock(spec=UserBilling)
        mock_user_billing.id = user_billing_id
        mock_user_billing.user_id = user_id
        mock_user_billing.billing_plan = mock_plan
        mock_user_billing.custom_token_quota = None
        mock_user_billing.custom_cost_quota = None
        mock_user_billing.billing_period_start = datetime.now(timezone.utc).replace(day=1)
        mock_user_billing.billing_period_end = datetime.now(timezone.utc).replace(month=12)
        mock_user_billing.created_at = datetime.now(timezone.utc)

        # Mock alerts
        mock_alert_50 = MagicMock(spec=BillingAlert)
        mock_alert_50.id = uuid.uuid4()
        mock_alert_50.alert_type = "token_usage"
        mock_alert_50.threshold_percent = 50
        mock_alert_50.is_active = True
        mock_alert_50.last_triggered_at = None
        mock_alert_50.last_triggered_value = None
        mock_alert_50.name = "50% Token Alert"

        mock_alert_75 = MagicMock(spec=BillingAlert)
        mock_alert_75.id = uuid.uuid4()
        mock_alert_75.alert_type = "cost_usage"
        mock_alert_75.threshold_percent = 75
        mock_alert_75.is_active = True
        mock_alert_75.last_triggered_at = None
        mock_alert_75.last_triggered_value = None
        mock_alert_75.name = "75% Cost Alert"

        # Mock a user object since the service queries for user details
        from budapp.user_ops.models import User
        mock_user = MagicMock(spec=User)
        mock_user.email = "test@example.com"
        mock_user.first_name = "Test"
        mock_user.last_name = "User"

        # Setup mock returns - use side_effect to return different objects for different queries
        def mock_execute_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            # Return user for User queries, user_billing for UserBilling queries
            mock_result.scalar_one_or_none.return_value = mock_user
            mock_result.scalars.return_value.all.return_value = [mock_alert_50, mock_alert_75]
            return mock_result

        mock_session.execute.side_effect = mock_execute_side_effect

        # Mock ClickHouse usage (triggers 50% token alert and 75% cost alert)
        with patch.object(billing_service, 'get_current_usage') as mock_get_current_usage, \
             patch.object(billing_service, 'get_user_billing') as mock_get_user_billing, \
             patch.object(billing_service, 'get_billing_alerts') as mock_get_alerts:
            # Mock the get_current_usage method response
            mock_get_current_usage.return_value = {
                "has_billing": True,
                "usage": {
                    "tokens_used": 60000,  # 60% of 100000
                    "tokens_quota": 100000,
                    "tokens_usage_percent": 60.0,
                    "cost_used": 160.00,  # 80% of 200.00
                    "cost_quota": 200.0,
                    "cost_usage_percent": 80.0,
                }
            }

            # Mock other service methods
            mock_get_user_billing.return_value = mock_user_billing
            mock_get_alerts.return_value = [mock_alert_50, mock_alert_75]

            # Mock notification service
            with patch('budapp.billing_ops.notification_service.BillingNotificationService') as MockNotificationService:
                mock_notification_service = MockNotificationService.return_value
                mock_notification_service.send_usage_alert = AsyncMock()

                result = await billing_service.check_and_trigger_alerts(user_id)

                # Should trigger both alerts
                assert len(result) == 2

                # Check alert details in the returned dictionaries
                alert_names = [alert["alert_name"] for alert in result]
                assert "50% Token Alert" in alert_names
                assert "75% Cost Alert" in alert_names

                # Check alert details
                token_alert = next(alert for alert in result if alert["alert_type"] == "token_usage")
                assert token_alert["current_percent"] == 60.0
                assert token_alert["current_value"] == 60000

                cost_alert = next(alert for alert in result if alert["alert_type"] == "cost_usage")
                assert cost_alert["current_percent"] == 80.0
                assert cost_alert["current_value"] == 160.0

    @pytest.mark.asyncio
    async def test_get_usage_history(self, billing_service, mock_session):
        """Test getting usage history."""
        user_id = uuid.uuid4()
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)

        # Mock ClickHouse response
        mock_response = {
            "param": [
                {
                    "date": "2024-01-01",
                    "tokens": 5000,
                    "cost": 12.50,
                    "request_count": 100,
                    "success_rate": 99.0,
                },
                {
                    "date": "2024-01-02",
                    "tokens": 7500,
                    "cost": 18.75,
                    "request_count": 150,
                    "success_rate": 98.5,
                },
            ]
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_async_client = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_async_client

            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status.return_value = None
            mock_async_client.get.return_value = mock_response_obj

            result = await billing_service.get_usage_history(
                user_id, start_date, end_date, granularity="daily"
            )

            assert len(result) == 2
            assert result[0]["tokens"] == 5000
            assert result[1]["tokens"] == 7500
