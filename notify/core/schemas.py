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

from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self

from notify.commons.constants import NotificationType
from notify.commons.schemas import (
    CloudEventBase,
    PaginatedSuccessResponse,
    SuccessResponse,
)


# Schemas related to notifications


class NotificationRequest(CloudEventBase):
    """Represents a notification request."""

    notification_type: NotificationType = NotificationType.EVENT
    name: str  # Workflow identifier
    subscriber_ids: Optional[Union[str, List[str]]] = None
    payload: dict = Field(default_factory=dict)
    actor: Optional[str] = None
    topic_keys: Optional[Union[str, List[str]]] = None

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
        if self.notification_type == NotificationType.BROADCAST and (self.subscriber_ids or self.topic_keys):
            raise ValueError("subscriber_ids and topic_keys are not allowed for broadcast notifications")
        return self


class NotificationResponse(SuccessResponse):
    """Represents a notification response."""

    acknowledged: bool
    status: str
    transaction_id: str


# Schemas related to subscribers


class SubscriberRequest(BaseModel):
    """Represents a subscriber request."""

    subscriber_id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    channels: Optional[list] = Field(default_factory=list)
    data: Optional[dict] = None


class SubscriberUpdateRequest(BaseModel):
    """Represents a subscriber update request."""

    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    channels: Optional[list] = Field(default_factory=list)
    data: Optional[dict] = None


class SubscriberBulkCreateResponse(SuccessResponse):
    """Represents a subscriber bulk response."""

    model_config = ConfigDict(extra="ignore")

    created: list = Field(default_factory=list)
    updated: list = Field(default_factory=list)
    failed: list = Field(default_factory=list)


class SubscriberBase(BaseModel):
    """Represents a subscriber list response."""

    subscriber_id: str = Field(None, alias="subscriberId")
    email: Optional[str] = None
    first_name: Optional[str] = Field(None, alias="firstName")
    last_name: Optional[str] = Field(None, alias="lastName")
    phone: Optional[str] = None
    avatar: Optional[str] = None
    locale: Optional[str] = None
    id: Optional[str] = Field(None, alias="_id")
    channels: Optional[list] = None
    created_at: Optional[str] = Field(None, alias="createdAt")
    updated_at: Optional[str] = Field(None, alias="updatedAt")
    is_online: Optional[bool] = Field(None, alias="isOnline")
    last_online_at: Optional[str] = Field(None, alias="lastOnlineAt")
    data: Optional[dict] = None


class PaginatedSubscriberResponse(PaginatedSuccessResponse):
    """Represents a subscriber paginated response."""

    model_config = ConfigDict(extra="ignore")

    subscribers: list[SubscriberBase]


class SubscriberResponse(SuccessResponse):
    """Represents a subscriber list response."""

    model_config = ConfigDict(extra="ignore")

    subscriber_id: str = Field(None, alias="subscriberId")
    email: Optional[str] = None
    first_name: Optional[str] = Field(None, alias="firstName")
    last_name: Optional[str] = Field(None, alias="lastName")
    phone: Optional[str] = None
    avatar: Optional[str] = None
    locale: Optional[str] = None
    id: Optional[str] = Field(None, alias="_id")
    channels: Optional[list] = None
    created_at: Optional[str] = Field(None, alias="createdAt")
    updated_at: Optional[str] = Field(None, alias="updatedAt")
    is_online: Optional[bool] = Field(None, alias="isOnline")
    last_online_at: Optional[str] = Field(None, alias="lastOnlineAt")
    data: Optional[dict] = None


# Schemas related to topics


class TopicRequest(BaseModel):
    """Represents a topic request."""

    topic_name: str
    topic_key: str


class TopicUpdateRequest(BaseModel):
    """Represents a topic update request."""

    topic_name: str


class TopicSubscriberRequest(BaseModel):
    """Represents a topic update request."""

    subscribers: Union[list[str], str]


class TopicBase(BaseModel):
    """Represents a topic base response."""

    key: str
    name: Optional[str] = None
    id: Optional[str] = Field(None, alias="_id")
    subscribers: Optional[List[str]] = None


class PaginatedTopicResponse(PaginatedSuccessResponse):
    """Represents a topic paginated response."""

    model_config = ConfigDict(extra="ignore")

    topics: list[TopicBase]


class TopicResponse(SuccessResponse):
    """Represents a topic list response."""

    model_config = ConfigDict(extra="ignore")

    key: str
    name: Optional[str] = None
    id: Optional[str] = Field(None, alias="_id")
    subscribers: Optional[List[str]] = None


class TopicCheckSubscriberResponse(SuccessResponse):
    """Represents a topic check subscriber response."""

    model_config = ConfigDict(extra="ignore")

    is_subscribed: bool


class TopicAddSubscriberResponse(SuccessResponse):
    """Represents a topic add subscriber response."""

    model_config = ConfigDict(extra="ignore")

    success: list = Field(default_factory=list)
    failed: list = Field(default_factory=list)
