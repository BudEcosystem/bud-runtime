"""Billing schemas for API validation."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class BillingPlanSchema(BaseModel):
    """Billing plan schema."""

    id: UUID
    name: str
    description: Optional[str]
    monthly_token_quota: Optional[int]
    monthly_cost_quota: Optional[Decimal]
    max_projects: Optional[int]
    max_endpoints_per_project: Optional[int]
    base_monthly_price: Decimal
    overage_token_price: Optional[Decimal]
    features: Dict[str, Any]
    is_active: bool
    created_at: datetime
    modified_at: datetime

    class Config:
        from_attributes = True


class UserBillingSchema(BaseModel):
    """User billing schema."""

    id: UUID
    user_id: UUID
    billing_plan_id: UUID
    billing_period_start: datetime
    billing_period_end: datetime
    custom_token_quota: Optional[int]
    custom_cost_quota: Optional[Decimal]
    enable_email_notifications: bool = True
    enable_in_app_notifications: bool = True
    is_active: bool
    is_suspended: bool
    suspension_reason: Optional[str]

    # Historical tracking fields
    is_current: bool
    cycle_number: int
    superseded_at: Optional[datetime] = None
    superseded_by_id: Optional[UUID] = None

    created_at: datetime
    modified_at: datetime

    class Config:
        from_attributes = True


class BillingAlertSchema(BaseModel):
    """Billing alert schema."""

    id: UUID
    user_id: UUID
    name: str
    alert_type: str
    threshold_percent: int
    last_triggered_at: Optional[datetime]
    last_triggered_value: Optional[Decimal]
    last_notification_sent_at: Optional[datetime] = None
    notification_failure_count: int = 0
    last_notification_error: Optional[str] = None
    is_active: bool
    created_at: datetime
    modified_at: datetime

    class Config:
        from_attributes = True


class UsageSummarySchema(BaseModel):
    """Usage summary schema."""

    tokens_used: int
    tokens_quota: Optional[int]
    tokens_usage_percent: float
    cost_used: float
    cost_quota: Optional[float]
    cost_usage_percent: float
    request_count: int
    success_rate: float


class CurrentUsageSchema(BaseModel):
    """Current usage response schema."""

    has_billing: bool
    billing_period_start: Optional[str]
    billing_period_end: Optional[str]
    plan_name: Optional[str]
    billing_plan_id: Optional[UUID]
    base_monthly_price: Optional[float]
    usage: Optional[UsageSummarySchema]
    is_suspended: Optional[bool]
    suspension_reason: Optional[str]


class UsageHistorySchema(BaseModel):
    """Usage history schema."""

    date: str
    tokens: int
    cost: float
    request_count: int
    success_rate: float


class CreateUserBillingRequest(BaseModel):
    """Request to create user billing."""

    user_id: UUID
    billing_plan_id: UUID
    custom_token_quota: Optional[int] = None
    custom_cost_quota: Optional[Decimal] = None


class CreateBillingAlertRequest(BaseModel):
    """Request to create billing alert."""

    name: str
    alert_type: str = Field(..., pattern="^(token_usage|cost_usage)$")
    threshold_percent: int = Field(..., ge=1, le=100)


class UpdateBillingPlanRequest(BaseModel):
    """Request to update user's billing plan."""

    user_id: UUID  # User whose billing to update
    billing_plan_id: UUID
    custom_token_quota: Optional[int] = None
    custom_cost_quota: Optional[Decimal] = None


class UsageHistoryRequest(BaseModel):
    """Request for usage history."""

    start_date: datetime
    end_date: datetime
    granularity: str = Field(default="daily", pattern="^(hourly|daily|weekly|monthly)$")
    project_id: Optional[UUID] = None


class UpdateNotificationPreferencesRequest(BaseModel):
    """Request to update notification preferences."""

    enable_email_notifications: Optional[bool] = None
    enable_in_app_notifications: Optional[bool] = None


class UpdateBillingAlertStatusRequest(BaseModel):
    """Request to update billing alert status (enable/disable)."""

    is_active: bool
