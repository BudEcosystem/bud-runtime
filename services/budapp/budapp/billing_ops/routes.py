"""Billing API routes."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from budapp.billing_ops.schemas import (
    BillingAlertSchema,
    BillingPlanSchema,
    CreateBillingAlertRequest,
    CreateUserBillingRequest,
    CurrentUsageSchema,
    UpdateBillingPlanRequest,
    UpdateNotificationPreferencesRequest,
    UsageHistoryRequest,
    UserBillingSchema,
)
from budapp.billing_ops.services import BillingService
from budapp.commons.constants import UserTypeEnum
from budapp.commons.dependencies import get_current_active_user, get_session
from budapp.commons.logging import get_logger
from budapp.commons.schemas import SingleResponse
from budapp.user_ops.schemas import User


logger = get_logger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans", response_model=SingleResponse[List[BillingPlanSchema]])
async def get_billing_plans(
    db: Session = Depends(get_session),
) -> SingleResponse[List[BillingPlanSchema]]:
    """Get all available billing plans."""
    try:
        from budapp.billing_ops.models import BillingPlan

        plans = db.query(BillingPlan).filter_by(is_active=True).all()
        return SingleResponse(
            result=[BillingPlanSchema.from_orm(plan) for plan in plans],
            message="Billing plans retrieved successfully",
        )
    except Exception as e:
        logger.error(f"Error fetching billing plans: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch billing plans",
        )


@router.get("/current", response_model=SingleResponse[CurrentUsageSchema])
async def get_current_usage(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
) -> SingleResponse[CurrentUsageSchema]:
    """Get current billing period usage for the authenticated user."""
    try:
        service = BillingService(db)
        usage = await service.get_current_usage(current_user.id)

        # Now the service always returns valid billing data (Free plan as default)
        return SingleResponse(
            result=CurrentUsageSchema(**usage),
            message="Current usage retrieved successfully",
        )
    except Exception as e:
        logger.error(f"Error fetching current usage: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch current usage",
        )


@router.get("/user/{user_id}", response_model=SingleResponse[UserBillingSchema])
async def get_user_billing_info(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
) -> SingleResponse[UserBillingSchema]:
    """Get billing information for a specific user (admin only)."""
    try:
        # Check if user is admin
        if current_user.user_type != UserTypeEnum.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can view other users' billing information",
            )

        service = BillingService(db)
        user_billing = service.get_user_billing(user_id)

        if not user_billing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No billing information found for this user",
            )

        return SingleResponse(
            result=UserBillingSchema.from_orm(user_billing),
            message="User billing information retrieved successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user billing info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user billing information",
        )


@router.get("/user/{user_id}/usage", response_model=SingleResponse[CurrentUsageSchema])
async def get_user_current_usage(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
) -> SingleResponse[CurrentUsageSchema]:
    """Get current billing period usage for a specific user (admin only)."""
    try:
        # Check if user is admin
        if current_user.user_type != UserTypeEnum.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can view other users' usage",
            )

        service = BillingService(db)
        usage = await service.get_current_usage(user_id)

        # Now the service always returns valid billing data (Free plan as default)
        return SingleResponse(
            result=CurrentUsageSchema(**usage),
            message="User usage retrieved successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user usage: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user usage",
        )


@router.post("/history", response_model=SingleResponse)
async def get_usage_history(
    request: UsageHistoryRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
) -> SingleResponse:
    """Get historical usage data for the authenticated user."""
    try:
        service = BillingService(db)
        history = await service.get_usage_history(
            user_id=current_user.id,
            start_date=request.start_date,
            end_date=request.end_date,
            granularity=request.granularity,
            project_id=request.project_id,
        )
        return SingleResponse(
            result=history,
            message="Usage history retrieved successfully",
        )
    except Exception as e:
        logger.error(f"Error fetching usage history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch usage history",
        )


@router.get("/check-limits", response_model=SingleResponse)
async def check_usage_limits(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
) -> SingleResponse:
    """Check if user has exceeded usage limits."""
    try:
        service = BillingService(db)
        result = await service.check_usage_limits(current_user.id)
        return SingleResponse(
            result=result,
            message="Usage limits checked successfully",
        )
    except Exception as e:
        logger.error(f"Error checking usage limits: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check usage limits",
        )


@router.post("/setup", response_model=SingleResponse[UserBillingSchema])
async def setup_user_billing(
    request: CreateUserBillingRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
) -> SingleResponse[UserBillingSchema]:
    """Set up billing for a user (admin only)."""
    try:
        # Check if user is admin (using user_type)
        if current_user.user_type != UserTypeEnum.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can set up billing",
            )

        service = BillingService(db)

        # Verify the billing plan exists
        billing_plan = service.get_billing_plan(request.billing_plan_id)
        if not billing_plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Billing plan not found",
            )

        if not billing_plan.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot assign an inactive billing plan",
            )

        # Check if billing already exists
        existing = service.get_user_billing(request.user_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has billing configured",
            )

        user_billing = service.create_user_billing(
            user_id=request.user_id,
            billing_plan_id=request.billing_plan_id,
            custom_token_quota=request.custom_token_quota,
            custom_cost_quota=request.custom_cost_quota,
        )

        return SingleResponse(
            result=UserBillingSchema.from_orm(user_billing),
            message="User billing set up successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting up user billing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set up user billing",
        )


@router.put("/plan", response_model=SingleResponse[UserBillingSchema])
async def update_billing_plan(
    request: UpdateBillingPlanRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
) -> SingleResponse[UserBillingSchema]:
    """Update user's billing plan (admin only)."""
    try:
        # Check if user is admin
        if current_user.user_type != UserTypeEnum.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can update billing plans",
            )

        service = BillingService(db)

        # Verify the billing plan exists
        billing_plan = service.get_billing_plan(request.billing_plan_id)
        if not billing_plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Billing plan not found",
            )

        if not billing_plan.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot assign an inactive billing plan",
            )

        # Admin updates billing for the specified user
        user_billing = service.get_user_billing(request.user_id)
        if not user_billing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No billing information found for this user",
            )

        # Check if quotas or plan are being changed
        quota_changed = False
        if user_billing.billing_plan_id != request.billing_plan_id:
            quota_changed = True  # Plan change affects base quotas
        if request.custom_token_quota is not None and user_billing.custom_token_quota != request.custom_token_quota:
            quota_changed = True
        if request.custom_cost_quota is not None and user_billing.custom_cost_quota != request.custom_cost_quota:
            quota_changed = True

        # Update billing plan
        user_billing.billing_plan_id = request.billing_plan_id
        if request.custom_token_quota is not None:
            user_billing.custom_token_quota = request.custom_token_quota
        if request.custom_cost_quota is not None:
            user_billing.custom_cost_quota = request.custom_cost_quota

        db.commit()
        db.refresh(user_billing)

        # Reset alerts if quotas were changed
        if quota_changed:
            service.reset_user_alerts(user_billing.id)
            logger.info(f"Reset billing alerts for user {request.user_id} due to quota update")

        return SingleResponse(
            result=UserBillingSchema.from_orm(user_billing),
            message="Billing plan updated successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating billing plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update billing plan",
        )


@router.get("/alerts", response_model=SingleResponse[List[BillingAlertSchema]])
async def get_billing_alerts(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
) -> SingleResponse[List[BillingAlertSchema]]:
    """Get all billing alerts for the authenticated user."""
    try:
        service = BillingService(db)
        alerts = service.get_billing_alerts(current_user.id)
        return SingleResponse(
            result=[BillingAlertSchema.from_orm(alert) for alert in alerts],
            message="Billing alerts retrieved successfully",
        )
    except Exception as e:
        logger.error(f"Error fetching billing alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch billing alerts",
        )


@router.post("/alerts", response_model=SingleResponse[BillingAlertSchema])
async def create_billing_alert(
    request: CreateBillingAlertRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
) -> SingleResponse[BillingAlertSchema]:
    """Create a new billing alert for the authenticated user."""
    try:
        service = BillingService(db)

        user_billing = service.get_user_billing(current_user.id)
        if not user_billing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No billing information found",
            )

        from budapp.billing_ops.models import BillingAlert

        alert = BillingAlert(
            user_billing_id=user_billing.id,
            name=request.name,
            alert_type=request.alert_type,
            threshold_percent=request.threshold_percent,
        )

        db.add(alert)
        db.commit()
        db.refresh(alert)

        return SingleResponse(
            result=BillingAlertSchema.from_orm(alert),
            message="Billing alert created successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating billing alert: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create billing alert",
        )


@router.post("/check-alerts", response_model=SingleResponse)
async def check_and_trigger_alerts(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
) -> SingleResponse:
    """Check and trigger billing alerts for the authenticated user."""
    try:
        service = BillingService(db)
        triggered_alerts = await service.check_and_trigger_alerts(current_user.id)

        return SingleResponse(
            result={"triggered_alerts": triggered_alerts},
            message=f"{len(triggered_alerts)} alerts triggered" if triggered_alerts else "No alerts triggered",
        )
    except Exception as e:
        logger.error(f"Error checking alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check alerts",
        )


@router.put("/notification-preferences", response_model=SingleResponse[UserBillingSchema])
async def update_notification_preferences(
    request: UpdateNotificationPreferencesRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
) -> SingleResponse[UserBillingSchema]:
    """Update notification preferences for the authenticated user."""
    try:
        service = BillingService(db)
        user_billing = service.get_user_billing(current_user.id)

        if not user_billing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No billing information found for this user",
            )

        # Update notification preferences
        if request.enable_email_notifications is not None:
            user_billing.enable_email_notifications = request.enable_email_notifications
        if request.enable_in_app_notifications is not None:
            user_billing.enable_in_app_notifications = request.enable_in_app_notifications

        db.commit()
        db.refresh(user_billing)

        return SingleResponse(
            result=UserBillingSchema.from_orm(user_billing),
            message="Notification preferences updated successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating notification preferences: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification preferences",
        )


@router.post("/reset/{user_id}", response_model=SingleResponse)
async def reset_user_usage(
    user_id: UUID,
    reason: str = "Manual reset",
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
) -> SingleResponse:
    """Reset a user's usage (admin only)."""
    try:
        # Check if current user is admin
        if current_user.user_type != UserTypeEnum.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can reset user usage",
            )

        from budapp.billing_ops.reset_usage import UsageResetService

        service = UsageResetService(db)
        success = await service.reset_user_usage(user_id, reason)

        if success:
            return SingleResponse(
                result={"user_id": str(user_id), "reset": True},
                message=f"Successfully reset usage for user {user_id}",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found or has no billing plan",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting user usage: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset user usage",
        )


@router.post("/reset-all", response_model=SingleResponse)
async def reset_all_users_usage(
    reason: str = "System reset",
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
) -> SingleResponse:
    """Reset all users' usage (admin only)."""
    try:
        # Check if current user is admin
        if current_user.user_type != UserTypeEnum.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can reset all users' usage",
            )

        from budapp.billing_ops.reset_usage import UsageResetService

        service = UsageResetService(db)
        count = await service.reset_all_users(reason)

        return SingleResponse(
            result={"users_reset": count},
            message=f"Successfully reset usage for {count} users",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting all users' usage: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset all users' usage",
        )


@router.post("/reset-expired", response_model=SingleResponse)
async def reset_expired_cycles(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
) -> SingleResponse:
    """Reset expired billing cycles (admin only)."""
    try:
        # Check if current user is admin
        if current_user.user_type != UserTypeEnum.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can reset expired cycles",
            )

        from budapp.billing_ops.reset_usage import UsageResetService

        service = UsageResetService(db)
        count = await service.reset_expired_cycles()

        return SingleResponse(
            result={"cycles_reset": count},
            message=f"Successfully reset {count} expired billing cycles",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting expired cycles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset expired cycles",
        )
