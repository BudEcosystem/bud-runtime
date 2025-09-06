"""Test fixtures and factory methods for billing tests."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from budapp.billing_ops.models import BillingAlert, BillingPlan, UserBilling
from budapp.commons.constants import UserTypeEnum
from budapp.commons.database import Base
from budapp.user_ops.models import User


class BillingPlanFactory:
    """Factory for creating billing plans."""

    @staticmethod
    def create_free_plan() -> BillingPlan:
        """Create a free billing plan."""
        return BillingPlan(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),  # Well-known free plan ID
            name="Free Plan",
            description="Basic free tier for individual developers",
            monthly_token_quota=10000,
            monthly_cost_quota=Decimal("10.00"),
            max_projects=1,
            max_endpoints_per_project=3,
            base_monthly_price=Decimal("0.00"),
            overage_token_price=None,  # No overages allowed
            features={
                "support": "community",
                "sla": None,
                "priority": "low",
                "api_rate_limit": 100,
            },
            is_active=True,
        )

    @staticmethod
    def create_starter_plan() -> BillingPlan:
        """Create a starter billing plan."""
        return BillingPlan(
            id=uuid.uuid4(),
            name="Starter Plan",
            description="For small teams and projects",
            monthly_token_quota=50000,
            monthly_cost_quota=Decimal("50.00"),
            max_projects=3,
            max_endpoints_per_project=5,
            base_monthly_price=Decimal("29.00"),
            overage_token_price=Decimal("0.001"),  # $0.001 per token over quota
            features={
                "support": "email",
                "sla": "99%",
                "priority": "normal",
                "api_rate_limit": 500,
            },
            is_active=True,
        )

    @staticmethod
    def create_professional_plan() -> BillingPlan:
        """Create a professional billing plan."""
        return BillingPlan(
            id=uuid.uuid4(),
            name="Professional Plan",
            description="For growing businesses",
            monthly_token_quota=200000,
            monthly_cost_quota=Decimal("200.00"),
            max_projects=10,
            max_endpoints_per_project=20,
            base_monthly_price=Decimal("99.00"),
            overage_token_price=Decimal("0.0008"),
            features={
                "support": "priority",
                "sla": "99.5%",
                "priority": "high",
                "api_rate_limit": 2000,
                "custom_models": True,
            },
            is_active=True,
        )

    @staticmethod
    def create_enterprise_plan() -> BillingPlan:
        """Create an enterprise billing plan."""
        return BillingPlan(
            id=uuid.uuid4(),
            name="Enterprise Plan",
            description="Unlimited usage for large organizations",
            monthly_token_quota=None,  # Unlimited
            monthly_cost_quota=None,  # Unlimited
            max_projects=None,  # Unlimited
            max_endpoints_per_project=None,  # Unlimited
            base_monthly_price=Decimal("999.00"),
            overage_token_price=None,
            features={
                "support": "dedicated",
                "sla": "99.99%",
                "priority": "critical",
                "api_rate_limit": None,  # Unlimited
                "custom_models": True,
                "white_label": True,
                "dedicated_infrastructure": True,
            },
            is_active=True,
        )

    @staticmethod
    def create_custom_plan(
        name: str,
        token_quota: Optional[int] = None,
        cost_quota: Optional[Decimal] = None,
        base_price: Decimal = Decimal("0.00"),
        **kwargs
    ) -> BillingPlan:
        """Create a custom billing plan."""
        return BillingPlan(
            id=uuid.uuid4(),
            name=name,
            description=kwargs.get("description", f"Custom plan: {name}"),
            monthly_token_quota=token_quota,
            monthly_cost_quota=cost_quota,
            max_projects=kwargs.get("max_projects"),
            max_endpoints_per_project=kwargs.get("max_endpoints_per_project"),
            base_monthly_price=base_price,
            overage_token_price=kwargs.get("overage_token_price"),
            features=kwargs.get("features", {}),
            is_active=kwargs.get("is_active", True),
        )


class UserBillingFactory:
    """Factory for creating user billing records."""

    @staticmethod
    def create_user_billing(
        user_id: uuid.UUID,
        billing_plan: BillingPlan,
        custom_token_quota: Optional[int] = None,
        custom_cost_quota: Optional[Decimal] = None,
        billing_period_days: int = 30,
    ) -> UserBilling:
        """Create a user billing record."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = period_start + timedelta(days=billing_period_days)

        return UserBilling(
            id=uuid.uuid4(),
            user_id=user_id,
            billing_plan_id=billing_plan.id,
            billing_period_start=period_start,
            billing_period_end=period_end,
            custom_token_quota=custom_token_quota,
            custom_cost_quota=custom_cost_quota,
            is_active=True,
            is_suspended=False,
        )

    @staticmethod
    def create_suspended_billing(
        user_id: uuid.UUID,
        billing_plan: BillingPlan,
        suspension_reason: str = "Payment failed",
    ) -> UserBilling:
        """Create a suspended user billing record."""
        billing = UserBillingFactory.create_user_billing(user_id, billing_plan)
        billing.is_suspended = True
        billing.suspension_reason = suspension_reason
        billing.is_active = False
        return billing


class BillingAlertFactory:
    """Factory for creating billing alerts."""

    @staticmethod
    def create_token_alert(
        user_billing_id: uuid.UUID,
        threshold_percent: int,
        name: Optional[str] = None,
    ) -> BillingAlert:
        """Create a token usage alert."""
        return BillingAlert(
            id=uuid.uuid4(),
            user_billing_id=user_billing_id,
            name=name or f"{threshold_percent}% Token Usage Alert",
            alert_type="token_usage",
            threshold_percent=threshold_percent,
            is_active=True,
        )

    @staticmethod
    def create_cost_alert(
        user_billing_id: uuid.UUID,
        threshold_percent: int,
        name: Optional[str] = None,
    ) -> BillingAlert:
        """Create a cost usage alert."""
        return BillingAlert(
            id=uuid.uuid4(),
            user_billing_id=user_billing_id,
            name=name or f"{threshold_percent}% Cost Usage Alert",
            alert_type="cost_usage",
            threshold_percent=threshold_percent,
            is_active=True,
        )

    @staticmethod
    def create_standard_alerts(user_billing_id: uuid.UUID) -> List[BillingAlert]:
        """Create a standard set of alerts (50%, 75%, 90%, 100%)."""
        thresholds = [50, 75, 90, 100]
        alerts = []

        for threshold in thresholds:
            alerts.append(
                BillingAlertFactory.create_token_alert(user_billing_id, threshold)
            )
            alerts.append(
                BillingAlertFactory.create_cost_alert(user_billing_id, threshold)
            )

        return alerts


class UsageDataFactory:
    """Factory for creating mock usage data."""

    @staticmethod
    def create_usage_data(
        tokens: int = 0,
        cost: float = 0.0,
        request_count: int = 0,
        success_rate: float = 100.0,
    ) -> Dict[str, Any]:
        """Create mock usage data from ClickHouse."""
        return {
            "total_tokens": tokens,
            "total_cost": cost,
            "request_count": request_count,
            "success_rate": success_rate,
        }

    @staticmethod
    def create_daily_usage_history(
        days: int = 7,
        base_tokens: int = 1000,
        base_cost: float = 2.50,
    ) -> List[Dict[str, Any]]:
        """Create mock daily usage history."""
        history = []
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        for i in range(days):
            date = start_date + timedelta(days=i)
            # Add some variation to the data
            variation = 1 + (i % 3) * 0.2

            history.append({
                "date": date.strftime("%Y-%m-%d"),
                "tokens": int(base_tokens * variation),
                "cost": base_cost * variation,
                "request_count": int(100 * variation),
                "success_rate": 99.0 - (i % 5) * 0.5,
            })

        return history


class TestUserFactory:
    """Factory for creating test users."""

    @staticmethod
    def create_client_user(email: Optional[str] = None) -> User:
        """Create a client user."""
        user = User()
        user.id = uuid.uuid4()
        user.email = email or f"client_{uuid.uuid4().hex[:8]}@example.com"
        user.user_type = UserTypeEnum.CLIENT
        user.is_active = True
        return user

    @staticmethod
    def create_admin_user(email: Optional[str] = None) -> User:
        """Create an admin user."""
        user = User()
        user.id = uuid.uuid4()
        user.email = email or f"admin_{uuid.uuid4().hex[:8]}@example.com"
        user.user_type = UserTypeEnum.ADMIN
        user.is_active = True
        return user


# Pytest Fixtures

@pytest.fixture
def test_db_engine():
    """Create a test database engine."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def test_db_session(test_db_engine):
    """Create a test database session."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    session = SessionLocal()

    yield session

    session.close()


@pytest.fixture
def free_plan(test_db_session):
    """Create and persist a free billing plan."""
    plan = BillingPlanFactory.create_free_plan()
    test_db_session.add(plan)
    test_db_session.commit()
    return plan


@pytest.fixture
def starter_plan(test_db_session):
    """Create and persist a starter billing plan."""
    plan = BillingPlanFactory.create_starter_plan()
    test_db_session.add(plan)
    test_db_session.commit()
    return plan


@pytest.fixture
def professional_plan(test_db_session):
    """Create and persist a professional billing plan."""
    plan = BillingPlanFactory.create_professional_plan()
    test_db_session.add(plan)
    test_db_session.commit()
    return plan


@pytest.fixture
def enterprise_plan(test_db_session):
    """Create and persist an enterprise billing plan."""
    plan = BillingPlanFactory.create_enterprise_plan()
    test_db_session.add(plan)
    test_db_session.commit()
    return plan


@pytest.fixture
def client_user():
    """Create a client user."""
    return TestUserFactory.create_client_user()


@pytest.fixture
def admin_user():
    """Create an admin user."""
    return TestUserFactory.create_admin_user()


@pytest.fixture
def user_with_free_billing(test_db_session, client_user, free_plan):
    """Create a user with free billing plan."""
    user_billing = UserBillingFactory.create_user_billing(client_user.id, free_plan)
    test_db_session.add(user_billing)
    test_db_session.commit()
    return client_user, user_billing


@pytest.fixture
def user_with_professional_billing(test_db_session, client_user, professional_plan):
    """Create a user with professional billing plan."""
    user_billing = UserBillingFactory.create_user_billing(client_user.id, professional_plan)
    test_db_session.add(user_billing)
    test_db_session.commit()
    return client_user, user_billing


@pytest.fixture
def user_with_alerts(test_db_session, user_with_professional_billing):
    """Create a user with standard billing alerts."""
    user, user_billing = user_with_professional_billing
    alerts = BillingAlertFactory.create_standard_alerts(user_billing.id)

    for alert in alerts:
        test_db_session.add(alert)
    test_db_session.commit()

    return user, user_billing, alerts


@pytest.fixture
def mock_low_usage():
    """Mock low usage data (25% of typical quota)."""
    return UsageDataFactory.create_usage_data(
        tokens=25000,
        cost=50.00,
        request_count=500,
        success_rate=99.5,
    )


@pytest.fixture
def mock_medium_usage():
    """Mock medium usage data (60% of typical quota)."""
    return UsageDataFactory.create_usage_data(
        tokens=60000,
        cost=120.00,
        request_count=1200,
        success_rate=99.0,
    )


@pytest.fixture
def mock_high_usage():
    """Mock high usage data (90% of typical quota)."""
    return UsageDataFactory.create_usage_data(
        tokens=90000,
        cost=180.00,
        request_count=1800,
        success_rate=98.5,
    )


@pytest.fixture
def mock_exceeded_usage():
    """Mock usage data that exceeds typical quotas."""
    return UsageDataFactory.create_usage_data(
        tokens=150000,
        cost=300.00,
        request_count=3000,
        success_rate=97.5,
    )


@pytest.fixture
def mock_usage_history():
    """Mock 7-day usage history."""
    return UsageDataFactory.create_daily_usage_history(days=7)
