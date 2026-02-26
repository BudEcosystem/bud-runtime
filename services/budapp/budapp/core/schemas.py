#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------


"""Contains core Pydantic schemas used for data validation and serialization within the core services."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Self, Union
from uuid import UUID

from pydantic import UUID4, BaseModel, ConfigDict, Field, field_validator, model_validator

from budapp.commons import logging
from budapp.commons.constants import (
    # ModelTemplateTypeEnum,
    NotificationCategory,
    NotificationType,
)
from budapp.commons.schemas import (
    CloudEventBase,
    PaginatedSuccessResponse,
    SuccessResponse,
)


logger = logging.get_logger(__name__)


# Schemas related to icons
class IconBase(BaseModel):
    """Base icon schema."""

    name: str
    file_path: str
    category: str


class IconCreate(IconBase):
    """Create icon schema."""

    pass


class IconUpdate(BaseModel):
    """Update icon schema."""

    category: str
    name: str


class IconResponse(IconBase):
    """Icon response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4


class IconFilter(BaseModel):
    """Icon filter schema."""

    name: str | None = None
    category: str | None = None


class IconListResponse(PaginatedSuccessResponse):
    """Icon list response schema."""

    icons: List[IconResponse]


# Schemas related to notifications


class NotificationContent(BaseModel):
    """Represents the content of a notification."""

    title: str | None = None
    message: str | None = None
    status: str | None = None
    result: Optional[Dict[str, Any]] = None
    primary_action: str | None = None
    secondary_action: str | None = None
    icon: str | None = None
    tag: str | None = None


class NotificationPayload(BaseModel):
    """Schema for notification payload."""

    category: NotificationCategory
    type: str | None = None
    event: str | None = None
    workflow_id: str | None = None
    source: str
    content: NotificationContent


class NotificationRequest(CloudEventBase):
    """Represents a notification request."""

    notification_type: NotificationType = NotificationType.EVENT
    name: str  # Workflow identifier
    subscriber_ids: Optional[Union[str, List[str]]] = None
    actor: Optional[str] = None
    topic_keys: Optional[Union[str, List[str]]] = None
    payload: NotificationPayload

    # Fields added by BudPipeline's EventPublisher for pipeline callback events.
    # CloudEventBase uses extra="forbid", so these must be declared explicitly.
    execution_id: Optional[str] = None
    pipeline_event_type: Optional[str] = None

    @model_validator(mode="before")
    def log_notification_hits(cls, data):
        """Log the notification hits for debugging purposes."""
        # TODO: remove this function after Debugging
        logger.info("================================================")
        logger.info("Received hit in notifications/:")
        logger.info(f"{data}")
        logger.info("================================================")
        return data

    @model_validator(mode="after")
    def validate_notification_rules(self) -> Self:
        """Check if required fields are present in the request.

        Raises:
            ValueError: If `subscriber_ids` is not present for event notifications.
            ValueError: If `topic_keys` is not present for topic notifications.

        Returns:
            Self: The instance of the class.
        """
        # NOTE: Commented out this condition for deployment, cluster status updates.
        # if self.notification_type == NotificationType.EVENT and not self.subscriber_ids:
        #     raise ValueError("subscriber_ids is required for event notifications")
        if self.notification_type == NotificationType.TOPIC and not self.topic_keys:
            raise ValueError("topic_keys is required for topic notifications")
        if self.notification_type == NotificationType.BROADCAST and (self.subscriber_ids or self.topic_keys):
            raise ValueError("subscriber_ids and topic_keys are not allowed for broadcast notifications")

        return self


class NotificationResponse(SuccessResponse):
    """Represents a notification response."""

    pass


# Schemas related to model templates


class ModelTemplateCreate(BaseModel):
    """Model template create schema."""

    name: str
    description: str
    icon: str
    template_type: str
    avg_sequence_length: Optional[int] = None
    avg_context_length: Optional[int] = None
    per_session_tokens_per_sec: Optional[list[int]] = None
    ttft: Optional[list[int]] = None
    e2e_latency: Optional[list[int]] = None

    @field_validator("per_session_tokens_per_sec", "ttft", "e2e_latency", mode="before")
    @classmethod
    def validate_int_range(cls, value):
        """Validate the int range of the list."""
        if value is not None and (
            not isinstance(value, list) or len(value) != 2 or not all(isinstance(x, int) for x in value)
        ):
            raise ValueError("Must be a list of two integers")
        return value


class ModelTemplateUpdate(ModelTemplateCreate):
    """Model template update schema."""

    pass


class ModelTemplateResponse(BaseModel):
    """Model template response schema."""

    id: UUID
    name: str
    description: str
    icon: str
    # template_type: ModelTemplateTypeEnum
    template_type: str
    avg_sequence_length: Optional[int] = None
    avg_context_length: Optional[int] = None
    per_session_tokens_per_sec: Optional[list[int]] = None
    ttft: Optional[list[int]] = None
    e2e_latency: Optional[list[int]] = None

    class Config:
        from_attributes = True


class ModelTemplateListResponse(PaginatedSuccessResponse):
    """Model template list response schema."""

    templates: List[ModelTemplateResponse]


class ModelTemplateFilter(BaseModel):
    """Model template filter schema."""

    # template_type: Optional[ModelTemplateTypeEnum] = None
    template_type: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None


class NotificationResult(BaseModel):
    """Notification result schema."""

    target_type: Literal["model", "cluster", "endpoint", "project", "guardrail", "workflow", "user"] | None = None
    target_id: UUID4 | None = None


class NotificationTrigger(BaseModel):
    """Represents a notification request."""

    notification_type: NotificationType = NotificationType.EVENT
    name: str  # Workflow identifier
    subscriber_ids: Optional[Union[str, List[str]]] = None
    payload: dict = Field(default_factory=dict)
    actor: Optional[str] = None
    topic_keys: Optional[Union[str, List[str]]] = Field(default_factory=list)
    time: str = datetime.now().isoformat()

    @model_validator(mode="after")
    def check_required_fields(self) -> Self:
        """Check if required fields are present in the request.

        Raises:
            ValueError: If `subscriber_ids` is not present for event notifications.
            ValueError: If `topic_keys` is not present for topic notifications.

        Returns:
            Self: The instance of the class.
        """
        if self.notification_type == NotificationType.EVENT and not self.subscriber_ids:
            raise ValueError("subscriber_ids is required for event notifications")
        if self.notification_type == NotificationType.TOPIC and not self.topic_keys:
            raise ValueError("topic_keys is required for topic notifications")
        return self


class SubscriberCreate(BaseModel):
    """Represents a subscriber request."""

    subscriber_id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    channels: Optional[list] = Field(default_factory=list)
    data: Optional[dict] = None


class SubscriberUpdate(BaseModel):
    """Represents a subscriber update request."""

    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    channels: Optional[list] = Field(default_factory=list)
    data: Optional[dict] = None


class AppNotificationResponse(BaseModel):
    """Represents a notification response."""

    acknowledged: bool
    status: str
    transaction_id: str
