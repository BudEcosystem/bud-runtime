"""Integration tests for billing API endpoints."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from budapp.billing_ops.models import BillingAlert, BillingPlan, UserBilling
from budapp.commons.constants import UserTypeEnum
from budapp.user_ops.schemas import User


@pytest.fixture
def mock_current_user():
    """Create a mock current user."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.user_type = UserTypeEnum.CLIENT
    return user


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = "admin@example.com"
    user.user_type = UserTypeEnum.ADMIN
    return user


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return MagicMock(spec=Session)


class TestBillingPlanEndpoints:
    """Test billing plan endpoints."""

    @patch('budapp.billing_ops.routes.BillingPlanSchema.from_orm')
    def test_get_billing_plans_success(self, mock_from_orm, mock_db_session):
        """Test successful retrieval of billing plans."""

        from datetime import datetime, timezone

        # Use simple mock objects since we're mocking the schema serialization
        mock_plans = [
            MagicMock(spec=BillingPlan),
            MagicMock(spec=BillingPlan),
        ]

        # Mock the schema serialization to return expected data
        mock_from_orm.side_effect = [
            {
                "id": str(uuid.uuid4()),
                "name": "Free Plan",
                "description": "Basic free tier",
                "monthly_token_quota": 10000,
                "monthly_cost_quota": "10.00",
                "max_projects": 5,
                "max_endpoints_per_project": 10,
                "base_monthly_price": "0.00",
                "overage_token_price": "0.001",
                "features": {"api_rate_limit": 100, "support": "community"},
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "modified_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Pro Plan",
                "description": "Professional tier",
                "monthly_token_quota": 100000,
                "monthly_cost_quota": "200.00",
                "max_projects": 50,
                "max_endpoints_per_project": 100,
                "base_monthly_price": "99.00",
                "overage_token_price": "0.0008",
                "features": {"api_rate_limit": 1000, "support": "email", "custom_models": True},
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "modified_at": datetime.now(timezone.utc).isoformat(),
            }
        ]

        mock_query = MagicMock()
        mock_query.filter_by.return_value.all.return_value = mock_plans
        mock_db_session.query.return_value = mock_query

        # Import here to avoid circular imports
        from budapp.main import app
        from budapp.commons.dependencies import get_session

        # Override the dependency
        app.dependency_overrides[get_session] = lambda: mock_db_session

        # Verify the override is set
        assert get_session in app.dependency_overrides

        client = TestClient(app)

        try:
            response = client.get("/billing/plans")
        finally:
            # Clean up the override
            app.dependency_overrides.clear()

        # Debug: Always print response details for debugging
        print(f"\n=== DEBUG INFO ===")
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        try:
            response_body = response.text
            print(f"Response body: {response_body}")
        except Exception as e:
            print(f"Error reading response body: {e}")

        # Also print if mocks were called
        print(f"Mock query called: {mock_db_session.query.called}")
        print(f"Mock filter_by called: {mock_query.filter_by.called}")
        print(f"=== END DEBUG ===\n")

        # Verify the mock was called before checking status
        mock_db_session.query.assert_called_once()
        mock_query.filter_by.assert_called_once_with(is_active=True)
        mock_query.filter_by.return_value.all.assert_called_once()

        # Now check the response status with better error message
        if response.status_code != 200:
            try:
                error_detail = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
            except:
                error_detail = response.text
            assert False, f"Expected 200 OK but got {response.status_code}. Error: {error_detail}"

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "result" in data
        assert len(data["result"]) == 2

    def test_get_billing_plans_error(self, mock_db_session):
        """Test error handling in billing plans retrieval."""
        mock_db_session.query.side_effect = Exception("Database error")

        from budapp.main import app
        from budapp.commons.dependencies import get_session

        # Override the dependency
        app.dependency_overrides[get_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.get("/billing/plans")

        # Clean up the override
        app.dependency_overrides.clear()

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestCurrentUsageEndpoints:
    """Test current usage endpoints."""

    @pytest.mark.asyncio
    @patch('budapp.billing_ops.routes.BillingService')
    async def test_get_current_usage_success(
        self, mock_billing_service_class, mock_current_user, mock_db_session
    ):
        """Test successful retrieval of current usage."""

        # Mock billing service
        mock_service = MagicMock()
        mock_billing_service_class.return_value = mock_service

        mock_usage = {
            "has_billing": True,
            "billing_period_start": "2024-01-01T00:00:00Z",
            "billing_period_end": "2024-01-31T23:59:59Z",
            "plan_name": "Standard Plan",
            "billing_plan_id": str(uuid.uuid4()),  # Added missing field
            "base_monthly_price": 49.00,
            "usage": {
                "tokens_used": 25000,
                "tokens_quota": 100000,
                "tokens_usage_percent": 25.0,
                "cost_used": 50.00,
                "cost_quota": 200.00,
                "cost_usage_percent": 25.0,
                "request_count": 500,
                "success_rate": 99.5,
            },
            "is_suspended": False,
            "suspension_reason": None,
        }

        mock_service.get_current_usage = AsyncMock(return_value=mock_usage)

        from budapp.main import app
        from budapp.commons.dependencies import get_session, get_current_active_user

        # Override the dependencies
        app.dependency_overrides[get_session] = lambda: mock_db_session
        app.dependency_overrides[get_current_active_user] = lambda: mock_current_user

        client = TestClient(app)

        try:
            response = client.get("/billing/current")
        finally:
            # Clean up the overrides
            app.dependency_overrides.clear()

        # Debug: Print response details for troubleshooting
        print(f"\n=== CURRENT USAGE DEBUG ===")
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        try:
            response_body = response.text
            print(f"Response body: {response_body}")
        except Exception as e:
            print(f"Error reading response body: {e}")
        print(f"=== END DEBUG ===\n")

        if response.status_code != 200:
            try:
                error_detail = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
            except:
                error_detail = response.text
            assert False, f"Expected 200 OK but got {response.status_code}. Error: {error_detail}"

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["result"]["has_billing"] is True
        assert data["result"]["usage"]["tokens_used"] == 25000

    @pytest.mark.asyncio
    @patch('budapp.billing_ops.routes.BillingService')
    async def test_get_current_usage_no_billing(
        self, mock_billing_service_class, mock_current_user, mock_db_session
    ):
        """Test current usage when user has no billing."""

        mock_service = MagicMock()
        mock_billing_service_class.return_value = mock_service

        mock_usage = {
            "has_billing": False,
            "billing_period_start": None,
            "billing_period_end": None,
            "plan_name": None,
            "billing_plan_id": None,  # Added missing field
            "base_monthly_price": None,
            "usage": None,
            "is_suspended": None,
            "suspension_reason": None,
        }

        mock_service.get_current_usage = AsyncMock(return_value=mock_usage)

        from budapp.main import app
        from budapp.commons.dependencies import get_session, get_current_active_user

        # Override the dependencies
        app.dependency_overrides[get_session] = lambda: mock_db_session
        app.dependency_overrides[get_current_active_user] = lambda: mock_current_user

        client = TestClient(app)

        try:
            response = client.get("/billing/current")
        finally:
            # Clean up the overrides
            app.dependency_overrides.clear()

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["result"]["has_billing"] is False
        assert data["result"]["usage"] is None


class TestUserBillingEndpoints:
    """Test user billing management endpoints."""

    @patch('budapp.billing_ops.routes.BillingService')
    def test_get_user_billing_info_admin_success(
        self, mock_billing_service_class, mock_admin_user, mock_db_session
    ):
        """Test admin retrieving user billing info."""

        target_user_id = uuid.uuid4()

        mock_service = MagicMock()
        mock_billing_service_class.return_value = mock_service

        mock_user_billing = MagicMock(spec=UserBilling)
        mock_user_billing.id = uuid.uuid4()
        mock_user_billing.user_id = target_user_id
        mock_user_billing.billing_plan_id = uuid.uuid4()
        mock_user_billing.is_active = True
        mock_user_billing.is_suspended = False

        mock_service.get_user_billing.return_value = mock_user_billing

        from budapp.main import app
        from budapp.commons.dependencies import get_session, get_current_active_user

        # Override the dependencies
        app.dependency_overrides[get_session] = lambda: mock_db_session
        app.dependency_overrides[get_current_active_user] = lambda: mock_admin_user

        client = TestClient(app)
        
        try:
            response = client.get(f"/billing/user/{target_user_id}")
        finally:
            # Clean up the overrides
            app.dependency_overrides.clear()

        assert response.status_code == status.HTTP_200_OK

    def test_get_user_billing_info_non_admin_forbidden(
        self, mock_current_user, mock_db_session
    ):
        """Test non-admin cannot retrieve other user's billing info."""
        
        target_user_id = uuid.uuid4()

        from budapp.main import app
        from budapp.commons.dependencies import get_session, get_current_active_user

        # Override the dependencies
        app.dependency_overrides[get_session] = lambda: mock_db_session
        app.dependency_overrides[get_current_active_user] = lambda: mock_current_user

        client = TestClient(app)
        
        try:
            response = client.get(f"/billing/user/{target_user_id}")
        finally:
            # Clean up the overrides
            app.dependency_overrides.clear()

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch('budapp.billing_ops.routes.get_current_active_user')
    @patch('budapp.billing_ops.routes.get_session')
    @patch('budapp.billing_ops.routes.BillingService')
    def test_setup_user_billing_admin_success(
        self, mock_billing_service_class, mock_get_session, mock_get_user, mock_admin_user, mock_db_session
    ):
        """Test admin setting up user billing."""
        mock_get_user.return_value = mock_admin_user
        mock_get_session.return_value = mock_db_session

        mock_service = MagicMock()
        mock_billing_service_class.return_value = mock_service

        # Mock billing plan exists
        mock_plan = MagicMock(spec=BillingPlan)
        mock_plan.is_active = True
        mock_service.get_billing_plan.return_value = mock_plan

        # Mock no existing billing
        mock_service.get_user_billing.return_value = None

        # Mock create billing
        new_user_billing = MagicMock(spec=UserBilling)
        mock_service.create_user_billing.return_value = new_user_billing

        from budapp.main import app

        client = TestClient(app)

        request_data = {
            "user_id": str(uuid.uuid4()),
            "billing_plan_id": str(uuid.uuid4()),
            "custom_token_quota": 75000,
            "custom_cost_quota": 150.00,
        }

        response = client.post("/billing/setup", json=request_data)

        assert response.status_code == status.HTTP_200_OK

    @patch('budapp.billing_ops.routes.get_current_active_user')
    @patch('budapp.billing_ops.routes.get_session')
    @patch('budapp.billing_ops.routes.BillingService')
    def test_update_billing_plan_admin_success(
        self, mock_billing_service_class, mock_get_session, mock_get_user, mock_admin_user, mock_db_session
    ):
        """Test admin updating user's billing plan."""
        mock_get_user.return_value = mock_admin_user
        mock_get_session.return_value = mock_db_session

        mock_service = MagicMock()
        mock_billing_service_class.return_value = mock_service

        # Mock billing plan exists
        mock_plan = MagicMock(spec=BillingPlan)
        mock_plan.is_active = True
        mock_service.get_billing_plan.return_value = mock_plan

        # Mock existing user billing
        mock_user_billing = MagicMock(spec=UserBilling)
        mock_service.get_user_billing.return_value = mock_user_billing

        from budapp.main import app

        client = TestClient(app)

        request_data = {
            "user_id": str(uuid.uuid4()),
            "billing_plan_id": str(uuid.uuid4()),
            "custom_token_quota": 100000,
        }

        response = client.put("/billing/plan", json=request_data)

        assert response.status_code == status.HTTP_200_OK


class TestBillingAlertEndpoints:
    """Test billing alert endpoints."""

    @patch('budapp.billing_ops.routes.get_current_active_user')
    @patch('budapp.billing_ops.routes.get_session')
    @patch('budapp.billing_ops.routes.BillingService')
    def test_get_billing_alerts_success(
        self, mock_billing_service_class, mock_get_session, mock_get_user, mock_current_user, mock_db_session
    ):
        """Test retrieving billing alerts."""
        mock_get_user.return_value = mock_current_user
        mock_get_session.return_value = mock_db_session

        mock_service = MagicMock()
        mock_billing_service_class.return_value = mock_service

        mock_alerts = [
            MagicMock(spec=BillingAlert, name="50% Alert", threshold_percent=50),
            MagicMock(spec=BillingAlert, name="75% Alert", threshold_percent=75),
        ]

        mock_service.get_billing_alerts.return_value = mock_alerts

        from budapp.main import app

        client = TestClient(app)
        response = client.get("/billing/alerts")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["result"]) == 2

    @patch('budapp.billing_ops.routes.get_current_active_user')
    @patch('budapp.billing_ops.routes.get_session')
    @patch('budapp.billing_ops.routes.BillingService')
    def test_create_billing_alert_success(
        self, mock_billing_service_class, mock_get_session, mock_get_user, mock_current_user, mock_db_session
    ):
        """Test creating a billing alert."""
        mock_get_user.return_value = mock_current_user
        mock_get_session.return_value = mock_db_session

        mock_service = MagicMock()
        mock_billing_service_class.return_value = mock_service

        # Mock user billing exists
        mock_user_billing = MagicMock(spec=UserBilling)
        mock_user_billing.id = uuid.uuid4()
        mock_service.get_user_billing.return_value = mock_user_billing

        from budapp.main import app

        client = TestClient(app)

        request_data = {
            "name": "High Usage Alert",
            "alert_type": "token_usage",
            "threshold_percent": 80,
        }

        # Mock the database execute for existing alert check (should return None)
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None

        with patch('budapp.billing_ops.models.BillingAlert') as mock_alert_class:
            mock_alert = MagicMock()
            mock_alert_class.return_value = mock_alert

            response = client.post("/billing/alerts", json=request_data)

            assert response.status_code == status.HTTP_200_OK
            mock_db_session.add.assert_called_once_with(mock_alert)
            mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch('budapp.billing_ops.routes.get_current_active_user')
    @patch('budapp.billing_ops.routes.get_session')
    @patch('budapp.billing_ops.routes.BillingService')
    async def test_check_and_trigger_alerts_success(
        self, mock_billing_service_class, mock_get_session, mock_get_user, mock_current_user, mock_db_session
    ):
        """Test checking and triggering alerts."""
        mock_get_user.return_value = mock_current_user
        mock_get_session.return_value = mock_db_session

        mock_service = MagicMock()
        mock_billing_service_class.return_value = mock_service

        triggered_alerts = ["50% Token Alert", "75% Cost Alert"]
        mock_service.check_and_trigger_alerts = AsyncMock(return_value=triggered_alerts)

        from budapp.main import app

        client = TestClient(app)
        response = client.post("/billing/check-alerts")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["result"]["triggered_alerts"]) == 2


class TestUsageLimitEndpoints:
    """Test usage limit checking endpoints."""

    @pytest.mark.asyncio
    @patch('budapp.billing_ops.routes.get_current_active_user')
    @patch('budapp.billing_ops.routes.get_session')
    @patch('budapp.billing_ops.routes.BillingService')
    async def test_check_usage_limits_within_limits(
        self, mock_billing_service_class, mock_get_session, mock_get_user, mock_current_user, mock_db_session
    ):
        """Test checking usage limits when within limits."""
        mock_get_user.return_value = mock_current_user
        mock_get_session.return_value = mock_db_session

        mock_service = MagicMock()
        mock_billing_service_class.return_value = mock_service

        mock_result = {
            "within_limits": True,
            "token_limit_exceeded": False,
            "cost_limit_exceeded": False,
            "tokens_used": 50000,
            "tokens_quota": 100000,
            "cost_used": 100.00,
            "cost_quota": 200.00,
        }

        mock_service.check_usage_limits = AsyncMock(return_value=mock_result)

        from budapp.main import app

        client = TestClient(app)
        response = client.get("/billing/check-limits")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["result"]["within_limits"] is True

    @pytest.mark.asyncio
    @patch('budapp.billing_ops.routes.get_current_active_user')
    @patch('budapp.billing_ops.routes.get_session')
    @patch('budapp.billing_ops.routes.BillingService')
    async def test_check_usage_limits_exceeded(
        self, mock_billing_service_class, mock_get_session, mock_get_user, mock_current_user, mock_db_session
    ):
        """Test checking usage limits when exceeded."""
        mock_get_user.return_value = mock_current_user
        mock_get_session.return_value = mock_db_session

        mock_service = MagicMock()
        mock_billing_service_class.return_value = mock_service

        mock_result = {
            "within_limits": False,
            "token_limit_exceeded": True,
            "cost_limit_exceeded": False,
            "tokens_used": 150000,
            "tokens_quota": 100000,
            "cost_used": 150.00,
            "cost_quota": 200.00,
        }

        mock_service.check_usage_limits = AsyncMock(return_value=mock_result)

        from budapp.main import app

        client = TestClient(app)
        response = client.get("/billing/check-limits")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["result"]["within_limits"] is False
        assert data["result"]["token_limit_exceeded"] is True


class TestUsageHistoryEndpoints:
    """Test usage history endpoints."""

    @pytest.mark.asyncio
    @patch('budapp.billing_ops.routes.get_current_active_user')
    @patch('budapp.billing_ops.routes.get_session')
    @patch('budapp.billing_ops.routes.BillingService')
    async def test_get_usage_history_success(
        self, mock_billing_service_class, mock_get_session, mock_get_user, mock_current_user, mock_db_session
    ):
        """Test retrieving usage history."""
        mock_get_user.return_value = mock_current_user
        mock_get_session.return_value = mock_db_session

        mock_service = MagicMock()
        mock_billing_service_class.return_value = mock_service

        mock_history = [
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

        mock_service.get_usage_history = AsyncMock(return_value=mock_history)

        from budapp.main import app

        client = TestClient(app)

        request_data = {
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-01-31T23:59:59Z",
            "granularity": "daily",
        }

        response = client.post("/billing/history", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["result"]) == 2
        assert data["result"][0]["tokens"] == 5000
