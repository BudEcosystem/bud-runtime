"""Billing models for PostgreSQL."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budapp.commons.database import Base, TimestampMixin


class BillingPlan(Base, TimestampMixin):
    """Billing plan configuration."""

    __tablename__ = "billing_plans"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(500))

    # Quotas
    monthly_token_quota: Mapped[Optional[int]] = mapped_column(nullable=True)  # None = unlimited
    monthly_cost_quota: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)  # None = unlimited
    max_projects: Mapped[Optional[int]] = mapped_column(nullable=True)  # None = unlimited
    max_endpoints_per_project: Mapped[Optional[int]] = mapped_column(nullable=True)  # None = unlimited

    # Pricing
    base_monthly_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    overage_token_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 6), nullable=True
    )  # Price per 1K tokens

    # Features
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    user_billings: Mapped[list["UserBilling"]] = relationship(back_populates="billing_plan")


class UserBilling(Base, TimestampMixin):
    """User billing configuration and status."""

    __tablename__ = "user_billing"
    __table_args__ = (
        # Index for finding current billing record for a user
        Index("ix_user_billing_user_current", "user_id", "is_current"),
        # Index for finding active billing records
        Index("ix_user_billing_active", "user_id", "is_active"),
        # Index for billing period queries
        Index("ix_user_billing_period", "user_id", "billing_period_start", "billing_period_end"),
        # Index for historical queries
        Index("ix_user_billing_created_current", "created_at", "is_current"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )  # Removed unique constraint
    billing_plan_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("billing_plans.id"), nullable=False)

    # Current period
    billing_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    billing_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Custom quotas (override plan defaults)
    custom_token_quota: Mapped[Optional[int]] = mapped_column(nullable=True)
    custom_cost_quota: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)

    # Notification preferences
    enable_email_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_in_app_notifications: Mapped[bool] = mapped_column(Boolean, default=True)

    # Status flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    suspension_reason: Mapped[Optional[str]] = mapped_column(String(500))

    # Historical tracking - NEW FIELDS
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cycle_number: Mapped[int] = mapped_column(nullable=False, default=1)  # Track which billing cycle this is
    superseded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # When this cycle was replaced
    superseded_by_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("user_billing.id"))

    # Relationships
    billing_plan: Mapped["BillingPlan"] = relationship(back_populates="user_billings")
    alerts: Mapped[list["BillingAlert"]] = relationship(back_populates="user_billing")


class BillingAlert(Base, TimestampMixin):
    """Billing alerts configuration."""

    __tablename__ = "billing_alerts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_billing_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("user_billing.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'token_usage', 'cost_usage'
    threshold_percent: Mapped[int] = mapped_column(nullable=False)  # 50, 75, 90, 100

    # Last notification tracking
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_triggered_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))

    # Notification tracking
    last_notification_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    notification_failure_count: Mapped[int] = mapped_column(default=0)
    last_notification_error: Mapped[Optional[str]] = mapped_column(String(500))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    user_billing: Mapped["UserBilling"] = relationship(back_populates="alerts")
