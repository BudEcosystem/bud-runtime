"""Subscription schemas for budpipeline.

This module contains Pydantic schemas for execution subscriptions API
(002-pipeline-event-persistence - T019).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from budpipeline.subscriptions.models import DeliveryStatus


class ExecutionSubscriptionCreate(BaseModel):
    """Request to create a new execution subscription (T019)."""

    execution_id: UUID = Field(..., description="Parent execution reference")
    callback_topic: str = Field(..., max_length=255, description="Dapr pub/sub topic name")
    expiry_time: datetime | None = Field(
        None, description="When subscription expires (NULL = no expiry)"
    )


class ExecutionSubscriptionResponse(BaseModel):
    """Execution subscription response schema (T019)."""

    model_config = {"from_attributes": True}

    id: UUID = Field(..., description="Unique subscription identifier")
    execution_id: UUID = Field(..., description="Parent execution reference")
    callback_topic: str = Field(..., description="Dapr pub/sub topic name")
    subscription_time: datetime = Field(..., description="When subscription created")
    expiry_time: datetime | None = Field(None, description="When subscription expires")
    delivery_status: DeliveryStatus = Field(..., description="Current subscription status")
    created_at: datetime = Field(..., description="Record creation time")


class SubscriptionStatusUpdate(BaseModel):
    """Request to update subscription delivery status."""

    delivery_status: DeliveryStatus = Field(..., description="New delivery status")


class SubscriptionBatchCreate(BaseModel):
    """Request to create multiple subscriptions at once."""

    callback_topics: list[str] = Field(
        ..., min_length=1, description="List of callback topic names"
    )
    expiry_time: datetime | None = Field(None, description="When subscriptions expire")


class SubscriptionListResponse(BaseModel):
    """Response for listing subscriptions."""

    subscriptions: list[ExecutionSubscriptionResponse] = Field(
        ..., description="List of subscriptions"
    )
    total_count: int = Field(..., description="Total number of subscriptions")
    active_count: int = Field(..., description="Number of active subscriptions")
