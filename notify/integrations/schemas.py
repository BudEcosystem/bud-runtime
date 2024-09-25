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


"""Contains Pydantic schemas used for data validation and serialization within the integrations."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing_extensions import Self

from notify.commons import logging
from notify.commons.constants import (
    NOVU_CHANNEL_PROVIDER_MAPPING,
    NovuChannel,
    NovuEmailProviderId,
)
from notify.commons.schemas import (
    SuccessResponse,
)


logger = logging.get_logger(__name__)


class NovuIntegrationCredentials(BaseModel):
    """Represent Novu integration credentials schema."""

    api_key: Optional[str] = Field(None, alias="apiKey")
    user: Optional[str] = None
    secret_key: Optional[str] = Field(None, alias="secretKey")
    domain: Optional[str] = None
    password: Optional[str] = None
    host: Optional[str] = None
    port: Optional[str] = None
    secure: Optional[bool] = None
    region: Optional[str] = None
    account_sid: Optional[str] = Field(None, alias="accountSid")
    from_: Optional[str] = Field(None, alias="from")
    sender_name: Optional[str] = Field(None, alias="senderName")
    app_id: Optional[str] = Field(None, alias="appID")
    require_tls: Optional[bool] = Field(None, alias="requireTls")
    ignore_tls: Optional[bool] = Field(None, alias="ignoreTls")
    tls_options: Optional[dict] = Field(None, alias="tlsOptions")
    base_url: Optional[str] = Field(None, alias="baseUrl")
    webhook_url: Optional[str] = Field(None, alias="webhookUrl")
    ip_pool_name: Optional[str] = Field(None, alias="ipPoolName")

    class Config:
        """Pydantic config."""

        populate_by_name = True


class IntegrationRequest(BaseModel):
    """Represents an integration request."""

    provider_id: NovuEmailProviderId
    channel: NovuChannel
    active: bool = False
    credentials: Optional[NovuIntegrationCredentials] = Field(default_factory=dict)
    _name: str  # Keep it as private attribute. Might useful in future
    check: bool = False

    @field_validator("channel")
    def validate_channel(cls, v: NovuChannel) -> str:
        """Validate the communication channel.

        Args:
            v (NovuChannel): The channel to be validated.

        Returns:
            str: The validated channel value.

        Raises:
            ValueError: If the channel is not supported (i.e., not 'email').
        """
        if v != NovuChannel.EMAIL:
            raise ValueError(f"Channel {v.value} not supported")
        return v

    @model_validator(mode="after")
    def validate_provider_id(self) -> Self:
        """Validate the provider ID based on the channel.

        Returns:
            Self: The validated instance.

        Raises:
            ValueError: If the provider ID is not supported for the specified channel.
        """
        try:
            self._name = NOVU_CHANNEL_PROVIDER_MAPPING[self.channel.value][self.provider_id.value]
        except KeyError:
            raise ValueError(
                f"Integration {self.provider_id.value} not supported for {self.channel} channel"
            ) from None
        return self

    @model_validator(mode="after")
    def validate_credentials(self) -> Self:
        """Validate and serializes credentials.

        Returns:
            Self: The validated instance.
        """
        if self.credentials:
            self.credentials = self.credentials.model_dump(by_alias=True, exclude_none=True)
        return self


class IntegrationResponse(SuccessResponse):
    """Represents an integration response."""

    model_config = ConfigDict(extra="ignore")

    provider_id: str
    channel: str
    active: bool
    id: Optional[str] = Field(None, alias="_id")
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    deleted: Optional[bool] = None


class IntegrationBase(BaseModel):
    """Represents individual item in integration list response."""

    provider_id: str = Field(None, alias="providerId")
    channel: str
    active: bool
    credentials: Optional[dict] = None
    id: Optional[str] = Field(None, alias="_id")
    created_at: Optional[str] = Field(None, alias="createdAt")
    updated_at: Optional[str] = Field(None, alias="updatedAt")
    deleted: Optional[bool] = None
    primary: Optional[bool] = None


class IntegrationListResponse(SuccessResponse):
    """Represents an integration list response."""

    model_config = ConfigDict(extra="ignore")

    integrations: list[IntegrationBase]


class IntegrationCurlResponse(IntegrationResponse):
    """Represents an integration response received from the Novu API."""

    provider_id: str = Field(None, alias="providerId")
    id: Optional[str] = Field(None, alias="_id")
    created_at: Optional[str] = Field(None, alias="createdAt")
    updated_at: Optional[str] = Field(None, alias="updatedAt")
