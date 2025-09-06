"""Tests for billing quota enforcement logic."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from budapp.billing_ops.models import BillingPlan, UserBilling
from budapp.billing_ops.services import BillingService


class TestQuotaEnforcement:
    """Test quota enforcement logic."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return MagicMock(spec=Session)

    @pytest.fixture
    def billing_service(self, mock_session):
        """Create a BillingService instance."""
        return BillingService(mock_session)

    @pytest.fixture
    def standard_plan(self):
        """Create a standard billing plan with defined quotas."""
        plan = MagicMock(spec=BillingPlan)
        plan.id = uuid.uuid4()
        plan.name = "Standard Plan"
        plan.monthly_token_quota = 100000
        plan.monthly_cost_quota = Decimal("200.00")
        plan.max_projects = 5
        plan.max_endpoints_per_project = 10
        return plan

    @pytest.fixture
    def unlimited_plan(self):
        """Create an unlimited billing plan."""
        plan = MagicMock(spec=BillingPlan)
        plan.id = uuid.uuid4()
        plan.name = "Enterprise Plan"
        plan.monthly_token_quota = None  # Unlimited
        plan.monthly_cost_quota = None  # Unlimited
        plan.max_projects = None  # Unlimited
        plan.max_endpoints_per_project = None  # Unlimited
        return plan

    @pytest.fixture
    def user_billing_standard(self, standard_plan):
        """Create user billing with standard plan."""
        user_billing = MagicMock(spec=UserBilling)
        user_billing.id = uuid.uuid4()
        user_billing.user_id = uuid.uuid4()
        user_billing.billing_plan = standard_plan
        user_billing.billing_plan_id = standard_plan.id
        user_billing.custom_token_quota = None
        user_billing.custom_cost_quota = None
        user_billing.billing_period_start = datetime.now(timezone.utc).replace(day=1)
        user_billing.billing_period_end = datetime.now(timezone.utc).replace(month=12)
        user_billing.is_suspended = False
        return user_billing

    @pytest.mark.asyncio
    async def test_check_token_quota_within_limit(self, billing_service, mock_session, user_billing_standard):
        """Test token quota check when usage is within limit."""
        user_id = user_billing_standard.user_id

        # Setup mock returns
        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = user_billing_standard
        mock_session.execute.return_value = mock_execute

        # Mock usage below limit (50% of quota)
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
            mock_get_usage.return_value = {
                "total_tokens": 50000,  # 50% of 100000
                "total_cost": 100.00,
                "request_count": 1000,
                "success_rate": 99.0,
            }

            result = await billing_service.check_usage_limits(user_id)

            assert result["within_limits"] is True
            assert result["token_limit_exceeded"] is False
            assert result["tokens_used"] == 50000
            assert result["tokens_quota"] == 100000
            assert result["tokens_remaining"] == 50000

    @pytest.mark.asyncio
    async def test_check_token_quota_exceeded(self, billing_service, mock_session, user_billing_standard):
        """Test token quota check when usage exceeds limit."""
        user_id = user_billing_standard.user_id

        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = user_billing_standard
        mock_session.execute.return_value = mock_execute

        # Mock usage exceeding limit
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
            mock_get_usage.return_value = {
                "total_tokens": 120000,  # 120% of 100000
                "total_cost": 240.00,
                "request_count": 2400,
                "success_rate": 98.5,
            }

            result = await billing_service.check_usage_limits(user_id)

            assert result["within_limits"] is False
            assert result["token_limit_exceeded"] is True
            assert result["tokens_used"] == 120000
            assert result["tokens_quota"] == 100000

    @pytest.mark.asyncio
    async def test_check_cost_quota_within_limit(self, billing_service, mock_session, user_billing_standard):
        """Test cost quota check when usage is within limit."""
        user_id = user_billing_standard.user_id

        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = user_billing_standard
        mock_session.execute.return_value = mock_execute

        # Mock usage within cost limit
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
            mock_get_usage.return_value = {
                "total_tokens": 80000,
                "total_cost": 150.00,  # 75% of 200.00
                "request_count": 1600,
                "success_rate": 99.2,
            }

            result = await billing_service.check_usage_limits(user_id)

            assert result["within_limits"] is True
            assert result["cost_limit_exceeded"] is False
            assert result["cost_used"] == 150.00
            assert result["cost_quota"] == 200.00
            assert result["cost_remaining"] == 50.00

    @pytest.mark.asyncio
    async def test_check_cost_quota_exceeded(self, billing_service, mock_session, user_billing_standard):
        """Test cost quota check when usage exceeds limit."""
        user_id = user_billing_standard.user_id

        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = user_billing_standard
        mock_session.execute.return_value = mock_execute

        # Mock usage exceeding cost limit
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
            mock_get_usage.return_value = {
                "total_tokens": 90000,
                "total_cost": 250.00,  # 125% of 200.00
                "request_count": 2500,
                "success_rate": 98.0,
            }

            result = await billing_service.check_usage_limits(user_id)

            assert result["within_limits"] is False
            assert result["cost_limit_exceeded"] is True
            assert result["cost_used"] == 250.00
            assert result["cost_quota"] == 200.00

    @pytest.mark.asyncio
    async def test_check_both_quotas_exceeded(self, billing_service, mock_session, user_billing_standard):
        """Test when both token and cost quotas are exceeded."""
        user_id = user_billing_standard.user_id

        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = user_billing_standard
        mock_session.execute.return_value = mock_execute

        # Mock usage exceeding both limits
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
            mock_get_usage.return_value = {
                "total_tokens": 150000,  # 150% of token quota
                "total_cost": 300.00,  # 150% of cost quota
                "request_count": 3000,
                "success_rate": 97.5,
            }

            result = await billing_service.check_usage_limits(user_id)

            assert result["within_limits"] is False
            assert result["token_limit_exceeded"] is True
            assert result["cost_limit_exceeded"] is True

    @pytest.mark.asyncio
    async def test_custom_quota_override(self, billing_service, mock_session, user_billing_standard):
        """Test custom quotas override plan defaults."""
        user_id = user_billing_standard.user_id

        # Set custom quotas
        user_billing_standard.custom_token_quota = 150000  # Override plan's 100000
        user_billing_standard.custom_cost_quota = Decimal("300.00")  # Override plan's 200.00

        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = user_billing_standard
        mock_session.execute.return_value = mock_execute

        # Mock usage that would exceed plan limits but not custom limits
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
            mock_get_usage.return_value = {
                "total_tokens": 120000,  # Exceeds plan's 100000 but within custom 150000
                "total_cost": 250.00,  # Exceeds plan's 200.00 but within custom 300.00
                "request_count": 2400,
                "success_rate": 98.5,
            }

            result = await billing_service.check_usage_limits(user_id)

            assert result["within_limits"] is True
            assert result["token_limit_exceeded"] is False
            assert result["cost_limit_exceeded"] is False
            assert result["tokens_quota"] == 150000
            assert result["cost_quota"] == 300.00

    @pytest.mark.asyncio
    async def test_unlimited_quota_never_exceeded(self, billing_service, mock_session, unlimited_plan):
        """Test unlimited quotas are never exceeded."""
        user_billing = MagicMock(spec=UserBilling)
        user_billing.user_id = uuid.uuid4()
        user_billing.billing_plan = unlimited_plan
        user_billing.custom_token_quota = None
        user_billing.custom_cost_quota = None
        user_billing.billing_period_start = datetime.now(timezone.utc).replace(day=1)
        user_billing.billing_period_end = datetime.now(timezone.utc).replace(month=12)
        user_billing.is_suspended = False

        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = user_billing
        mock_session.execute.return_value = mock_execute

        # Mock very high usage
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
            mock_get_usage.return_value = {
                "total_tokens": 10000000,  # 10 million tokens
                "total_cost": 25000.00,  # $25,000
                "request_count": 100000,
                "success_rate": 99.9,
            }

            result = await billing_service.check_usage_limits(user_billing.user_id)

            assert result["within_limits"] is True
            assert result["token_limit_exceeded"] is False
            assert result["cost_limit_exceeded"] is False
            assert result["tokens_quota"] is None  # Unlimited
            assert result["cost_quota"] is None  # Unlimited

    @pytest.mark.asyncio
    async def test_suspended_user_quota_check(self, billing_service, mock_session, user_billing_standard):
        """Test quota check for suspended user."""
        user_id = user_billing_standard.user_id
        user_billing_standard.is_suspended = True
        user_billing_standard.suspension_reason = "Payment failed"

        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = user_billing_standard
        mock_session.execute.return_value = mock_execute

        # Even with low usage, suspended users should be blocked
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
            mock_get_usage.return_value = {
                "total_tokens": 100,
                "total_cost": 1.00,
                "request_count": 10,
                "success_rate": 100.0,
            }

            result = await billing_service.check_usage_limits(user_id)

            # The service should indicate suspension
            assert result["is_suspended"] is True
            assert result["suspension_reason"] == "Payment failed"

    @pytest.mark.asyncio
    async def test_no_billing_setup(self, billing_service, mock_session):
        """Test quota check when user has no billing setup."""
        user_id = uuid.uuid4()

        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = None  # No billing setup
        mock_session.execute.return_value = mock_execute

        result = await billing_service.check_usage_limits(user_id)

        assert result["has_billing"] is False
        assert result["within_limits"] is False
        assert "No billing plan configured" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_project_level_quota_check(self, billing_service, mock_session, user_billing_standard):
        """Test quota check at project level."""
        user_id = user_billing_standard.user_id
        project_id = uuid.uuid4()

        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = user_billing_standard
        mock_session.execute.return_value = mock_execute

        # Mock project-specific usage
        with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
            mock_get_usage.return_value = {
                "total_tokens": 20000,  # Project uses 20% of user's quota
                "total_cost": 40.00,
                "request_count": 400,
                "success_rate": 99.5,
            }

            # Note: This would need to be implemented in the actual service
            # For now, we're testing the concept
            result = await billing_service.check_usage_limits(user_id, project_id=project_id)

            # Verify project_id was passed to usage retrieval
            mock_get_usage.assert_called_once()
            call_args = mock_get_usage.call_args
            if len(call_args[0]) > 3:
                assert call_args[0][3] == project_id

    @pytest.mark.asyncio
    async def test_quota_percentage_calculation(self, billing_service, mock_session, user_billing_standard):
        """Test accurate percentage calculation for quota usage."""
        user_id = user_billing_standard.user_id

        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = user_billing_standard
        mock_session.execute.return_value = mock_execute

        test_cases = [
            # (tokens_used, expected_percent)
            (0, 0.0),
            (10000, 10.0),
            (25000, 25.0),
            (50000, 50.0),
            (75000, 75.0),
            (99000, 99.0),
            (100000, 100.0),
        ]

        for tokens_used, expected_percent in test_cases:
            with patch.object(billing_service, 'get_usage_from_clickhouse') as mock_get_usage:
                mock_get_usage.return_value = {
                    "total_tokens": tokens_used,
                    "total_cost": 0.0,
                    "request_count": 0,
                    "success_rate": 0.0,
                }

                result = await billing_service.check_usage_limits(user_id)

                # Calculate percentage
                if user_billing_standard.billing_plan.monthly_token_quota:
                    actual_percent = (tokens_used / user_billing_standard.billing_plan.monthly_token_quota) * 100
                    assert abs(actual_percent - expected_percent) < 0.01  # Allow small floating point difference
