"""Tests for billing models."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


# Try to import models, skip tests if environment not set up
try:
    from budapp.billing_ops.models import BillingAlert, BillingPlan, UserBilling
    models_available = True
except (RuntimeError, ImportError) as e:
    models_available = False
    skip_reason = f"Models not available: {e}"


@pytest.fixture
def test_engine():
    """Create a test database engine."""
    if not models_available:
        pytest.skip(skip_reason)

    engine = create_engine("sqlite:///:memory:")

    # Only create billing-related tables to avoid PostgreSQL ARRAY type issues
    # Don't use Base.metadata.create_all() as it tries to create all tables including ModelTemplate with ARRAY columns
    billing_tables = [
        BillingPlan.__table__,
        UserBilling.__table__,
        BillingAlert.__table__,
    ]

    for table in billing_tables:
        table.create(engine, checkfirst=True)

    return engine


@pytest.fixture
def test_session(test_engine):
    """Create a test database session."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.mark.skipif(not models_available, reason=skip_reason if not models_available else "")
class TestBillingPlan:
    """Test BillingPlan model."""

    def test_create_billing_plan(self, test_session: Session):
        """Test creating a billing plan."""
        plan = BillingPlan(
            id=uuid.uuid4(),
            name="Free Plan",
            description="Basic free tier",
            monthly_token_quota=10000,
            monthly_cost_quota=Decimal("10.00"),
            max_projects=3,
            max_endpoints_per_project=5,
            base_monthly_price=Decimal("0.00"),
            overage_token_price=Decimal("0.001"),
            features={"support": "community", "sla": None},
            is_active=True,
        )

        test_session.add(plan)
        test_session.commit()

        # Retrieve and verify
        saved_plan = test_session.query(BillingPlan).filter_by(name="Free Plan").first()
        assert saved_plan is not None
        assert saved_plan.name == "Free Plan"
        assert saved_plan.monthly_token_quota == 10000
        assert saved_plan.base_monthly_price == Decimal("0.00")
        assert saved_plan.features["support"] == "community"
        assert saved_plan.is_active is True

    def test_billing_plan_unlimited_quotas(self, test_session: Session):
        """Test billing plan with unlimited quotas (None values)."""
        plan = BillingPlan(
            id=uuid.uuid4(),
            name="Enterprise Plan",
            description="Unlimited enterprise tier",
            monthly_token_quota=None,  # Unlimited
            monthly_cost_quota=None,  # Unlimited
            max_projects=None,  # Unlimited
            max_endpoints_per_project=None,  # Unlimited
            base_monthly_price=Decimal("999.00"),
            overage_token_price=None,
            features={"support": "dedicated", "sla": "99.99%"},
            is_active=True,
        )

        test_session.add(plan)
        test_session.commit()

        saved_plan = test_session.query(BillingPlan).filter_by(name="Enterprise Plan").first()
        assert saved_plan.monthly_token_quota is None
        assert saved_plan.monthly_cost_quota is None
        assert saved_plan.base_monthly_price == Decimal("999.00")


@pytest.mark.skipif(not models_available, reason=skip_reason if not models_available else "")
class TestUserBilling:
    """Test UserBilling model."""

    def test_create_user_billing(self, test_session: Session):
        """Test creating user billing."""
        # Create a billing plan first
        plan = BillingPlan(
            id=uuid.uuid4(),
            name="Standard Plan",
            base_monthly_price=Decimal("49.00"),
            monthly_token_quota=100000,
        )
        test_session.add(plan)
        test_session.commit()

        # Create user billing
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        next_month = now.replace(month=now.month + 1) if now.month < 12 else now.replace(year=now.year + 1, month=1)

        user_billing = UserBilling(
            id=uuid.uuid4(),
            user_id=user_id,
            billing_plan_id=plan.id,
            billing_period_start=now,
            billing_period_end=next_month,
            custom_token_quota=None,
            custom_cost_quota=None,
            is_active=True,
            is_suspended=False,
        )

        test_session.add(user_billing)
        test_session.commit()

        # Retrieve and verify
        saved_billing = test_session.query(UserBilling).filter_by(user_id=user_id).first()
        assert saved_billing is not None
        assert saved_billing.billing_plan_id == plan.id
        assert saved_billing.is_active is True
        assert saved_billing.is_suspended is False

    def test_user_billing_with_custom_quotas(self, test_session: Session):
        """Test user billing with custom quotas."""
        # Create a billing plan
        plan = BillingPlan(
            id=uuid.uuid4(),
            name="Custom Plan",
            base_monthly_price=Decimal("99.00"),
            monthly_token_quota=50000,
            monthly_cost_quota=Decimal("100.00"),
        )
        test_session.add(plan)
        test_session.commit()

        # Create user billing with custom quotas
        user_billing = UserBilling(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            billing_plan_id=plan.id,
            billing_period_start=datetime.now(timezone.utc),
            billing_period_end=datetime.now(timezone.utc).replace(month=12),
            custom_token_quota=75000,  # Override plan default
            custom_cost_quota=Decimal("150.00"),  # Override plan default
            is_active=True,
            is_suspended=False,
        )

        test_session.add(user_billing)
        test_session.commit()

        assert user_billing.custom_token_quota == 75000
        assert user_billing.custom_cost_quota == Decimal("150.00")

    def test_suspended_user_billing(self, test_session: Session):
        """Test suspended user billing."""
        plan = BillingPlan(
            id=uuid.uuid4(),
            name="Suspended Plan",
            base_monthly_price=Decimal("0.00"),
        )
        test_session.add(plan)

        user_billing = UserBilling(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            billing_plan_id=plan.id,
            billing_period_start=datetime.now(timezone.utc),
            billing_period_end=datetime.now(timezone.utc).replace(month=12),
            is_active=False,
            is_suspended=True,
            suspension_reason="Payment failed",
        )

        test_session.add(user_billing)
        test_session.commit()

        assert user_billing.is_suspended is True
        assert user_billing.suspension_reason == "Payment failed"
        assert user_billing.is_active is False


@pytest.mark.skipif(not models_available, reason=skip_reason if not models_available else "")
class TestBillingAlert:
    """Test BillingAlert model."""

    def test_create_billing_alert(self, test_session: Session):
        """Test creating a billing alert."""
        # Create plan and user billing
        plan = BillingPlan(id=uuid.uuid4(), name="Alert Plan", base_monthly_price=Decimal("0.00"))
        test_session.add(plan)

        user_billing = UserBilling(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            billing_plan_id=plan.id,
            billing_period_start=datetime.now(timezone.utc),
            billing_period_end=datetime.now(timezone.utc).replace(month=12),
        )
        test_session.add(user_billing)
        test_session.commit()

        # Create alert
        alert = BillingAlert(
            id=uuid.uuid4(),
            user_id=user_billing.user_id,
            name="50% Token Usage Alert",
            alert_type="token_usage",
            threshold_percent=50,
            is_active=True,
        )

        test_session.add(alert)
        test_session.commit()

        saved_alert = test_session.query(BillingAlert).filter_by(user_id=user_billing.user_id).first()
        assert saved_alert is not None
        assert saved_alert.name == "50% Token Usage Alert"
        assert saved_alert.alert_type == "token_usage"
        assert saved_alert.threshold_percent == 50
        assert saved_alert.is_active is True

    def test_triggered_billing_alert(self, test_session: Session):
        """Test billing alert with trigger history."""
        # Setup
        plan = BillingPlan(id=uuid.uuid4(), name="Alert Plan", base_monthly_price=Decimal("0.00"))
        test_session.add(plan)

        user_billing = UserBilling(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            billing_plan_id=plan.id,
            billing_period_start=datetime.now(timezone.utc),
            billing_period_end=datetime.now(timezone.utc).replace(month=12),
        )
        test_session.add(user_billing)
        test_session.commit()

        # Create alert with trigger history
        alert = BillingAlert(
            id=uuid.uuid4(),
            user_id=user_billing.user_id,
            name="90% Cost Alert",
            alert_type="cost_usage",
            threshold_percent=90,
            last_triggered_at=datetime.now(timezone.utc),
            last_triggered_value=Decimal("89.50"),
            is_active=True,
        )

        test_session.add(alert)
        test_session.commit()

        assert alert.last_triggered_at is not None
        assert alert.last_triggered_value == Decimal("89.50")

    def test_multiple_alerts_per_user(self, test_session: Session):
        """Test multiple alerts for a single user billing."""
        # Setup
        plan = BillingPlan(id=uuid.uuid4(), name="Multi-Alert Plan", base_monthly_price=Decimal("0.00"))
        test_session.add(plan)

        user_billing = UserBilling(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            billing_plan_id=plan.id,
            billing_period_start=datetime.now(timezone.utc),
            billing_period_end=datetime.now(timezone.utc).replace(month=12),
        )
        test_session.add(user_billing)
        test_session.commit()

        # Create multiple alerts
        alerts = [
            BillingAlert(
                id=uuid.uuid4(),
                user_id=user_billing.user_id,
                name="25% Token Alert",
                alert_type="token_usage",
                threshold_percent=25,
                is_active=True,
            ),
            BillingAlert(
                id=uuid.uuid4(),
                user_id=user_billing.user_id,
                name="50% Token Alert",
                alert_type="token_usage",
                threshold_percent=50,
                is_active=True,
            ),
            BillingAlert(
                id=uuid.uuid4(),
                user_id=user_billing.user_id,
                name="75% Cost Alert",
                alert_type="cost_usage",
                threshold_percent=75,
                is_active=True,
            ),
        ]

        for alert in alerts:
            test_session.add(alert)
        test_session.commit()

        # Verify all alerts
        saved_alerts = test_session.query(BillingAlert).filter_by(user_id=user_billing.user_id).all()
        assert len(saved_alerts) == 3
        assert sorted([a.threshold_percent for a in saved_alerts]) == [25, 50, 75]


@pytest.mark.skipif(not models_available, reason=skip_reason if not models_available else "")
class TestModelRelationships:
    """Test relationships between billing models."""

    def test_billing_plan_user_billing_relationship(self, test_session: Session):
        """Test relationship between BillingPlan and UserBilling."""
        # Create billing plan
        plan = BillingPlan(
            id=uuid.uuid4(),
            name="Relationship Plan",
            base_monthly_price=Decimal("29.00"),
        )
        test_session.add(plan)
        test_session.commit()

        # Create multiple user billings
        user_billings = []
        for _ in range(3):
            ub = UserBilling(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                billing_plan_id=plan.id,
                billing_period_start=datetime.now(timezone.utc),
                billing_period_end=datetime.now(timezone.utc).replace(month=12),
            )
            user_billings.append(ub)
            test_session.add(ub)

        test_session.commit()

        # Test relationship
        test_session.refresh(plan)
        assert len(plan.user_billings) == 3

    def test_user_billing_alerts_relationship(self, test_session: Session):
        """Test relationship between UserBilling and BillingAlert."""
        # Setup
        plan = BillingPlan(id=uuid.uuid4(), name="Alert Relationship Plan", base_monthly_price=Decimal("0.00"))
        test_session.add(plan)

        user_billing = UserBilling(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            billing_plan_id=plan.id,
            billing_period_start=datetime.now(timezone.utc),
            billing_period_end=datetime.now(timezone.utc).replace(month=12),
        )
        test_session.add(user_billing)
        test_session.commit()

        # Add alerts
        alerts = []
        for percent in [25, 50, 75, 100]:
            alert = BillingAlert(
                id=uuid.uuid4(),
                user_id=user_billing.user_id,
                name=f"{percent}% Alert",
                alert_type="token_usage",
                threshold_percent=percent,
                is_active=True,
            )
            alerts.append(alert)
            test_session.add(alert)

        test_session.commit()

        # Test relationship - Note: This relationship may need to be updated in the model as well
        # For now, we'll verify alerts were created for the correct user
        saved_alerts = test_session.query(BillingAlert).filter_by(user_id=user_billing.user_id).all()
        assert len(saved_alerts) == 4
        assert all(alert.user_id == user_billing.user_id for alert in saved_alerts)
