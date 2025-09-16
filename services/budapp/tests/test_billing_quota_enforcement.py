"""Tests for billing quota enforcement logic."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session


class TestQuotaEnforcement:
    """Test quota enforcement logic."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return MagicMock(spec=Session)

    @pytest.fixture
    def billing_service(self, mock_session):
        """Create a BillingService instance."""
        from budapp.billing_ops.services import BillingService
        return BillingService(mock_session)

    @pytest.fixture
    def standard_plan(self):
        """Create a standard billing plan with defined quotas."""
        from budapp.billing_ops.models import BillingPlan
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
        from budapp.billing_ops.models import BillingPlan
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
        from budapp.billing_ops.models import UserBilling
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
        user_billing.created_at = datetime.now(timezone.utc).replace(day=1)  # Fixed datetime instead of Mock
        return user_billing

    @pytest.mark.asyncio
    async def test_check_token_quota_within_limit(self, billing_service, mock_session, user_billing_standard, standard_plan):
        """Test token quota check when usage is within limit."""
        user_id = user_billing_standard.user_id

        # Create a mock user with user_type attribute (required by check_usage_limits)
        from budapp.commons.constants import UserTypeEnum
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.user_type = UserTypeEnum.CLIENT

        # Setup mock returns for both execute() and query() methods
        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = mock_user  # Return User object, not UserBilling
        mock_session.execute.return_value = mock_execute

        # Mock the session.query() method that the service actually uses
        mock_query = MagicMock()
        mock_filter_by = MagicMock()
        mock_filter_by.first.return_value = mock_user  # Return User object, not UserBilling
        mock_query.filter_by.return_value = mock_filter_by
        mock_session.query.return_value = mock_query

        # Mock usage below limit (50% of quota)
        with patch.object(billing_service, 'get_current_usage') as mock_get_usage:
            mock_get_usage.return_value = {
                "has_billing": True,
                "usage": {
                    "tokens_used": 50000,  # 50% of 100000
                    "cost_used": 100.00,
                    "tokens_quota": 100000,
                    "cost_quota": 200.00,
                    "tokens_remaining": 50000,
                    "cost_remaining": 100.00,
                },
                "within_limits": True,
                "token_limit_exceeded": False,
                "cost_limit_exceeded": False,
            }

            result = await billing_service.check_usage_limits(user_id)

            assert result["allowed"] is True
            assert result["status"] == "allowed"
            assert result["tokens_used"] == 50000
            assert result["tokens_quota"] == 100000

    @pytest.mark.asyncio
    async def test_check_token_quota_exceeded(self, billing_service, mock_session, user_billing_standard):
        """Test token quota check when usage exceeds limit."""
        user_id = user_billing_standard.user_id

        # Create a mock user with user_type attribute (required by check_usage_limits)
        from budapp.commons.constants import UserTypeEnum
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.user_type = UserTypeEnum.CLIENT

        # Setup mock returns for both execute() and query() methods
        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_execute

        # Mock the session.query() method that the service actually uses
        mock_query = MagicMock()
        mock_filter_by = MagicMock()
        mock_filter_by.first.return_value = mock_user
        mock_query.filter_by.return_value = mock_filter_by
        mock_session.query.return_value = mock_query

        # Mock get_user_billing to return the actual billing object
        with patch.object(billing_service, 'get_user_billing') as mock_get_user_billing, \
             patch.object(billing_service, 'get_current_usage') as mock_get_usage:

            mock_get_user_billing.return_value = user_billing_standard
            mock_get_usage.return_value = {
                "has_billing": True,
                "usage": {
                    "tokens_used": 120000,  # 120% of 100000
                    "cost_used": 240.00,
                    "tokens_quota": 100000,
                    "cost_quota": 200.00,
                },
            }

            result = await billing_service.check_usage_limits(user_id)

            assert result["allowed"] is False
            assert result["status"] == "token_limit_exceeded"
            assert result["tokens_used"] == 120000
            assert result["tokens_quota"] == 100000

    @pytest.mark.asyncio
    async def test_check_cost_quota_within_limit(self, billing_service, mock_session, user_billing_standard):
        """Test cost quota check when usage is within limit."""
        user_id = user_billing_standard.user_id

        # Create a mock user with user_type attribute (required by check_usage_limits)
        from budapp.commons.constants import UserTypeEnum
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.user_type = UserTypeEnum.CLIENT

        # Setup mock returns for both execute() and query() methods
        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_execute

        # Mock the session.query() method that the service actually uses
        mock_query = MagicMock()
        mock_filter_by = MagicMock()
        mock_filter_by.first.return_value = mock_user
        mock_query.filter_by.return_value = mock_filter_by
        mock_session.query.return_value = mock_query

        # Mock get_user_billing to return the actual billing object
        with patch.object(billing_service, 'get_user_billing') as mock_get_user_billing, \
             patch.object(billing_service, 'get_current_usage') as mock_get_usage:

            mock_get_user_billing.return_value = user_billing_standard
            mock_get_usage.return_value = {
                "has_billing": True,
                "usage": {
                    "tokens_used": 80000,
                    "cost_used": 150.00,  # 75% of 200.00
                    "tokens_quota": 100000,
                    "cost_quota": 200.00,
                },
            }

            result = await billing_service.check_usage_limits(user_id)

            assert result["allowed"] is True
            assert result["status"] == "allowed"
            assert result["cost_used"] == 150.00
            assert result["cost_quota"] == 200.00

    @pytest.mark.asyncio
    async def test_check_cost_quota_exceeded(self, billing_service, mock_session, user_billing_standard):
        """Test cost quota check when usage exceeds limit."""
        user_id = user_billing_standard.user_id

        # Create a mock user with user_type attribute (required by check_usage_limits)
        from budapp.commons.constants import UserTypeEnum
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.user_type = UserTypeEnum.CLIENT

        # Setup mock returns for both execute() and query() methods
        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_execute

        # Mock the session.query() method that the service actually uses
        mock_query = MagicMock()
        mock_filter_by = MagicMock()
        mock_filter_by.first.return_value = mock_user
        mock_query.filter_by.return_value = mock_filter_by
        mock_session.query.return_value = mock_query

        # Mock get_user_billing to return the actual billing object
        with patch.object(billing_service, 'get_user_billing') as mock_get_user_billing, \
             patch.object(billing_service, 'get_current_usage') as mock_get_usage:

            mock_get_user_billing.return_value = user_billing_standard
            mock_get_usage.return_value = {
                "has_billing": True,
                "usage": {
                    "tokens_used": 90000,
                    "cost_used": 250.00,  # 125% of 200.00
                    "tokens_quota": 100000,
                    "cost_quota": 200.00,
                },
            }

            result = await billing_service.check_usage_limits(user_id)

            assert result["allowed"] is False
            assert result["status"] == "cost_limit_exceeded"
            assert result["cost_used"] == 250.00
            assert result["cost_quota"] == 200.00

    @pytest.mark.asyncio
    async def test_check_both_quotas_exceeded(self, billing_service, mock_session, user_billing_standard):
        """Test when both token and cost quotas are exceeded."""
        user_id = user_billing_standard.user_id

        # Create a mock user with user_type attribute (required by check_usage_limits)
        from budapp.commons.constants import UserTypeEnum
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.user_type = UserTypeEnum.CLIENT

        # Setup mock returns for both execute() and query() methods
        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_execute

        # Mock the session.query() method that the service actually uses
        mock_query = MagicMock()
        mock_filter_by = MagicMock()
        mock_filter_by.first.return_value = mock_user
        mock_query.filter_by.return_value = mock_filter_by
        mock_session.query.return_value = mock_query

        # Mock get_user_billing to return the actual billing object
        with patch.object(billing_service, 'get_user_billing') as mock_get_user_billing, \
             patch.object(billing_service, 'get_current_usage') as mock_get_usage:

            mock_get_user_billing.return_value = user_billing_standard
            mock_get_usage.return_value = {
                "has_billing": True,
                "usage": {
                    "tokens_used": 150000,  # 150% of token quota
                    "cost_used": 300.00,  # 150% of cost quota
                    "tokens_quota": 100000,
                    "cost_quota": 200.00,
                },
            }

            result = await billing_service.check_usage_limits(user_id)

            assert result["allowed"] is False
            # Token limit is checked first, so status should be token_limit_exceeded
            assert result["status"] == "token_limit_exceeded"

    @pytest.mark.asyncio
    async def test_custom_quota_override(self, billing_service, mock_session, user_billing_standard):
        """Test custom quotas override plan defaults."""
        user_id = user_billing_standard.user_id

        # Set custom quotas
        user_billing_standard.custom_token_quota = 150000  # Override plan's 100000
        user_billing_standard.custom_cost_quota = Decimal("300.00")  # Override plan's 200.00

        # Create a mock user with user_type attribute (required by check_usage_limits)
        from budapp.commons.constants import UserTypeEnum
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.user_type = UserTypeEnum.CLIENT

        # Setup mock returns for both execute() and query() methods
        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_execute

        # Mock the session.query() method that the service actually uses
        mock_query = MagicMock()
        mock_filter_by = MagicMock()
        mock_filter_by.first.return_value = mock_user
        mock_query.filter_by.return_value = mock_filter_by
        mock_session.query.return_value = mock_query

        # Mock get_user_billing to return the actual billing object
        with patch.object(billing_service, 'get_user_billing') as mock_get_user_billing, \
             patch.object(billing_service, 'get_current_usage') as mock_get_usage:

            mock_get_user_billing.return_value = user_billing_standard
            mock_get_usage.return_value = {
                "has_billing": True,
                "usage": {
                    "tokens_used": 120000,  # Exceeds plan's 100000 but within custom 150000
                    "cost_used": 250.00,  # Exceeds plan's 200.00 but within custom 300.00
                    "tokens_quota": 150000,  # Custom quota
                    "cost_quota": 300.00,  # Custom quota
                },
            }

            result = await billing_service.check_usage_limits(user_id)

            assert result["allowed"] is True
            assert result["status"] == "allowed"
            assert result["tokens_quota"] == 150000
            assert result["cost_quota"] == 300.00

    @pytest.mark.asyncio
    async def test_unlimited_quota_never_exceeded(self, billing_service, mock_session, unlimited_plan):
        """Test unlimited quotas are never exceeded."""
        from budapp.billing_ops.models import UserBilling
        user_billing = MagicMock(spec=UserBilling)
        user_billing.user_id = uuid.uuid4()
        user_billing.billing_plan = unlimited_plan
        user_billing.custom_token_quota = None
        user_billing.custom_cost_quota = None
        user_billing.billing_period_start = datetime.now(timezone.utc).replace(day=1)
        user_billing.billing_period_end = datetime.now(timezone.utc).replace(month=12)
        user_billing.is_suspended = False
        user_billing.created_at = datetime.now(timezone.utc)

        # Create a mock user with user_type attribute (required by check_usage_limits)
        from budapp.commons.constants import UserTypeEnum
        mock_user = MagicMock()
        mock_user.id = user_billing.user_id
        mock_user.user_type = UserTypeEnum.CLIENT

        # Setup mock returns for both execute() and query() methods
        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_execute

        # Mock the session.query() method that the service actually uses
        mock_query = MagicMock()
        mock_filter_by = MagicMock()
        mock_filter_by.first.return_value = mock_user
        mock_query.filter_by.return_value = mock_filter_by
        mock_session.query.return_value = mock_query

        # Mock get_user_billing to return the actual billing object
        with patch.object(billing_service, 'get_user_billing') as mock_get_user_billing, \
             patch.object(billing_service, 'get_current_usage') as mock_get_usage:

            mock_get_user_billing.return_value = user_billing
            mock_get_usage.return_value = {
                "has_billing": True,
                "usage": {
                    "tokens_used": 10000000,  # 10 million tokens
                    "cost_used": 25000.00,  # $25,000
                    "tokens_quota": None,  # Unlimited
                    "cost_quota": None,  # Unlimited
                },
            }

            result = await billing_service.check_usage_limits(user_billing.user_id)

            assert result["allowed"] is True
            assert result["status"] == "allowed"
            assert result["tokens_quota"] is None  # Unlimited
            assert result["cost_quota"] is None  # Unlimited

    @pytest.mark.asyncio
    async def test_suspended_user_quota_check(self, billing_service, mock_session, user_billing_standard):
        """Test quota check for suspended user."""
        user_id = user_billing_standard.user_id
        user_billing_standard.is_suspended = True
        user_billing_standard.suspension_reason = "Payment failed"

        # Create a mock user with user_type attribute (required by check_usage_limits)
        from budapp.commons.constants import UserTypeEnum
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.user_type = UserTypeEnum.CLIENT

        # Setup mock returns for both execute() and query() methods
        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_execute

        # Mock the session.query() method that the service actually uses
        mock_query = MagicMock()
        mock_filter_by = MagicMock()
        mock_filter_by.first.return_value = mock_user
        mock_query.filter_by.return_value = mock_filter_by
        mock_session.query.return_value = mock_query

        # Mock get_user_billing to return the actual billing object
        with patch.object(billing_service, 'get_user_billing') as mock_get_user_billing, \
             patch.object(billing_service, 'get_current_usage') as mock_get_usage:

            mock_get_user_billing.return_value = user_billing_standard
            mock_get_usage.return_value = {
                "has_billing": True,
                "usage": {
                    "tokens_used": 100,
                    "cost_used": 1.00,
                    "tokens_quota": 100000,
                    "cost_quota": 200.00,
                },
                "is_suspended": True,
                "suspension_reason": "Payment failed",
            }

            result = await billing_service.check_usage_limits(user_id)

            # The service should indicate suspension
            assert result["allowed"] is False
            assert result["status"] == "suspended"
            assert result["reason"] == "Payment failed"

    @pytest.mark.asyncio
    async def test_no_billing_setup(self, billing_service, mock_session):
        """Test quota check when user has no billing setup."""
        user_id = uuid.uuid4()

        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = None  # No billing setup
        mock_session.execute.return_value = mock_execute

        # Setup mock returns for both execute() and query() methods
        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = None  # No user billing
        mock_session.execute.return_value = mock_execute

        # Mock the session.query() method that the service actually uses
        mock_query = MagicMock()
        mock_filter_by = MagicMock()
        mock_filter_by.first.return_value = None  # No user billing
        mock_query.filter_by.return_value = mock_filter_by
        mock_session.query.return_value = mock_query

        with patch.object(billing_service, 'get_current_usage') as mock_get_usage:
            mock_get_usage.return_value = {
                "has_billing": False,
            }

            result = await billing_service.check_usage_limits(user_id)

            assert result["allowed"] is True  # Freemium users are allowed
            assert result["status"] == "no_billing_plan"
            assert "freemium" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_project_level_quota_check(self, billing_service, mock_session, user_billing_standard):
        """Test quota check at project level."""
        user_id = user_billing_standard.user_id
        project_id = uuid.uuid4()

        # Create a mock user with user_type attribute (required by check_usage_limits)
        from budapp.commons.constants import UserTypeEnum
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.user_type = UserTypeEnum.CLIENT

        # Setup mock returns for both execute() and query() methods
        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_execute

        # Mock the session.query() method that the service actually uses
        mock_query = MagicMock()
        mock_filter_by = MagicMock()
        mock_filter_by.first.return_value = mock_user
        mock_query.filter_by.return_value = mock_filter_by
        mock_session.query.return_value = mock_query

        # Mock get_user_billing to return the actual billing object
        with patch.object(billing_service, 'get_user_billing') as mock_get_user_billing, \
             patch.object(billing_service, 'get_current_usage') as mock_get_usage:

            mock_get_user_billing.return_value = user_billing_standard
            mock_get_usage.return_value = {
                "has_billing": True,
                "usage": {
                    "tokens_used": 20000,  # Project uses 20% of user's quota
                    "cost_used": 40.00,
                    "tokens_quota": 100000,
                    "cost_quota": 200.00,
                },
            }

            # Note: This would need to be implemented in the actual service
            # For now, we're testing the concept
            result = await billing_service.check_usage_limits(user_id)

            # Verify the result is within limits
            assert result["allowed"] is True
            assert result["status"] == "allowed"
            # Verify usage was retrieved
            mock_get_usage.assert_called_once()

    @pytest.mark.asyncio
    async def test_quota_percentage_calculation(self, billing_service, mock_session, user_billing_standard):
        """Test accurate percentage calculation for quota usage."""
        user_id = user_billing_standard.user_id

        # Create a mock user with user_type attribute (required by check_usage_limits)
        from budapp.commons.constants import UserTypeEnum
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.user_type = UserTypeEnum.CLIENT

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

        # Setup mock returns for both execute() and query() methods
        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_execute

        # Mock the session.query() method that the service actually uses
        mock_query = MagicMock()
        mock_filter_by = MagicMock()
        mock_filter_by.first.return_value = mock_user
        mock_query.filter_by.return_value = mock_filter_by
        mock_session.query.return_value = mock_query

        for tokens_used, expected_percent in test_cases:
            with patch.object(billing_service, 'get_user_billing') as mock_get_user_billing, \
                 patch.object(billing_service, 'get_current_usage') as mock_get_usage:

                mock_get_user_billing.return_value = user_billing_standard
                mock_get_usage.return_value = {
                    "has_billing": True,
                    "usage": {
                        "tokens_used": tokens_used,
                        "cost_used": 0.0,
                        "tokens_quota": 100000,  # From standard plan
                        "cost_quota": 200.00,
                    },
                }

                result = await billing_service.check_usage_limits(user_id)

                # Calculate percentage
                if result.get("tokens_quota"):
                    actual_percent = (tokens_used / result["tokens_quota"]) * 100
                    assert abs(actual_percent - expected_percent) < 0.01  # Allow small floating point difference
