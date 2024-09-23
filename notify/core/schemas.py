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

from typing import List, Optional

from pydantic import BaseModel, Field

from notify.commons.schemas import CloudEventBase, SuccessResponse


class NotificationRequest(CloudEventBase):
    """Represents a notification request."""

    subscriber_id: str

    title: str
    message: str

    redirect_url: Optional[str] = None
    primary_action: Optional[str] = None
    secondary_action: Optional[str] = None


class NotificationResponse(SuccessResponse):
    """Represents a notification response."""

    notification_id: str


class SubscriberRequest(CloudEventBase):
    """Represents a subscriber request."""

    subscriber_id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    channels: Optional[list] = Field(default_factory=list)
    data: Optional[dict] = None


class SubscriberUpdateRequest(CloudEventBase):
    """Represents a subscriber update request."""

    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    channels: Optional[list] = Field(default_factory=list)
    data: Optional[dict] = None


class SubscriberSdk(BaseModel):
    """Represents a subscriber response."""

    subscriber_id: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    locale: Optional[str] = None
    id: Optional[str] = Field(None, alias="_id")
    channels: Optional[list] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    is_online: Optional[bool] = None
    last_online_at: Optional[str] = None
    data: Optional[dict] = None


class SubscriberItem(BaseModel):
    """Represents a subscriber list item."""

    subscriber_id: str = Field(None, alias="subscriberId")
    email: Optional[str] = None
    first_name: Optional[str] = Field(None, alias="firstName")
    last_name: Optional[str] = Field(None, alias="lastName")
    phone: Optional[str] = None
    avatar: Optional[str] = None
    locale: Optional[str] = None
    id: Optional[str] = None
    channels: Optional[list] = None
    created_at: Optional[str] = Field(None, alias="createdAt")
    updated_at: Optional[str] = Field(None, alias="updatedAt")
    is_online: Optional[bool] = Field(None, alias="isOnline")
    last_online_at: Optional[str] = Field(None, alias="lastOnlineAt")
    data: Optional[dict] = None


class SubscriberBulkResponse(SuccessResponse):
    """Represents a subscriber bulk response."""

    created: list
    updated: list
    failed: list


class SubscriberResponse(SuccessResponse):
    """Represents a subscriber list response."""

    subscriber_id: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    locale: Optional[str] = None
    id: Optional[str] = None
    channels: Optional[list] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    is_online: Optional[bool] = None
    last_online_at: Optional[str] = None
    data: Optional[dict] = None


class SubscriberListResponse(SuccessResponse):
    """Represents a subscriber list response."""

    subscribers: List[SubscriberItem]
