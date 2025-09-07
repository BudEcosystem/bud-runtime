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
        user_id = uuid.uuid4()
        plan_id = uuid.uuid4()
        custom_token_quota = 75000
        custom_cost_quota = Decimal("150.00")

        result = billing_service.create_user_billing(
            user_id=user_id,
            billing_plan_id=plan_id,
            custom_token_quota=custom_token_quota,
            custom_cost_quota=custom_cost_quota,
        )

        # Verify UserBilling was created
        assert result.user_id == user_id
        assert result.billing_plan_id == plan_id
        assert result.custom_token_quota == custom_token_quota
        assert result.custom_cost_quota == custom_cost_quota
        assert result.is_active is True
        assert result.is_suspended is False

        # Verify it was added to session
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

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

        # Setup mock returns
        mock_execute1 = MagicMock()
        mock_execute1.scalar_one_or_none.return_value = mock_user_billing

        mock_execute2 = MagicMock()
        mock_execute2.scalars.return_value.all.return_value = mock_alerts

        mock_session.execute.side_effect = [mock_execute1, mock_execute2]

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

        # Mock ClickHouse usage
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
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

        result = await billing_service.get_current_usage(user_id)

        assert result["has_billing"] is False
        assert result["usage"] is None
        assert result["plan_name"] is None

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

        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = mock_user_billing
        mock_session.execute.return_value = mock_execute

        # Mock the session.query() method that the service actually uses
        mock_query = MagicMock()
        mock_filter_by = MagicMock()
        mock_filter_by.first.return_value = mock_user_billing
        mock_query.filter_by.return_value = mock_filter_by
        mock_session.query.return_value = mock_query

        # Mock ClickHouse usage (below limits)
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
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

        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = mock_user_billing
        mock_session.execute.return_value = mock_execute

        # Mock the session.query() method that the service actually uses
        mock_query = MagicMock()
        mock_filter_by = MagicMock()
        mock_filter_by.first.return_value = mock_user_billing
        mock_query.filter_by.return_value = mock_filter_by
        mock_session.query.return_value = mock_query

        # Mock ClickHouse usage (exceeds limits)
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
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
        mock_alert_50.name = "50% Token Alert"

        mock_alert_75 = MagicMock(spec=BillingAlert)
        mock_alert_75.id = uuid.uuid4()
        mock_alert_75.alert_type = "cost_usage"
        mock_alert_75.threshold_percent = 75
        mock_alert_75.is_active = True
        mock_alert_75.last_triggered_at = None
        mock_alert_75.name = "75% Cost Alert"

        # Setup mock returns
        mock_execute1 = MagicMock()
        mock_execute1.scalar_one_or_none.return_value = mock_user_billing

        mock_execute2 = MagicMock()
        mock_execute2.scalars.return_value.all.return_value = [mock_alert_50, mock_alert_75]

        mock_session.execute.side_effect = [mock_execute1, mock_execute2]

        # Mock ClickHouse usage (triggers 50% token alert and 75% cost alert)
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
            mock_get_usage.return_value = {
                "total_tokens": 60000,  # 60% of 100000
                "total_cost": 160.00,  # 80% of 200.00
                "request_count": 1500,
                "success_rate": 99.0,
            }

            # Mock notification service
            with patch.object(billing_service, '_send_alert_notification') as mock_send:
                mock_send.return_value = None

                result = await billing_service.check_and_trigger_alerts(user_id)

                # Should trigger both alerts
                assert len(result) == 2
                assert "50% Token Alert" in result
                assert "75% Cost Alert" in result

                # Verify alerts were updated
                assert mock_alert_50.last_triggered_at is not None
                assert mock_alert_75.last_triggered_at is not None

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
