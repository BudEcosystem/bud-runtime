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


"""Contains Pydantic schemas used for data validation and serialization within the auth services."""

from typing import Any, List

from pydantic import UUID4, BaseModel, ConfigDict, EmailStr, Field, field_validator

from budapp.commons.constants import TokenTypeEnum, UserRoleEnum, UserTypeEnum
from budapp.commons.helpers import validate_password_string
from budapp.commons.schemas import SuccessResponse
from budapp.permissions.schemas import PermissionList


class AuthToken(BaseModel):
    """Token schema."""

    access_token: str
    refresh_token: str
    token_type: str  # Bearer


class AccessTokenData(BaseModel):
    """Access token data schema."""

    sub: str
    type: str = TokenTypeEnum.ACCESS.value


class RefreshTokenData(BaseModel):
    """Refresh token data schema."""

    sub: str
    type: str = TokenTypeEnum.REFRESH.value
    secret_key: str


class TokenCreate(BaseModel):
    """Token create schema."""

    auth_id: UUID4
    secret_key: str | None = None
    token_hash: str
    type: TokenTypeEnum


class UserLogin(BaseModel):
    """User login schema."""

    email: EmailStr = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=100)
    tenant_id: UUID4 | None = Field(
        None,
        description="The ID of the tenant. If not provided, the user will be logged in to the first tenant they belong to.",
    )
    user_type: UserTypeEnum = Field(
        UserTypeEnum.CLIENT,
        description="Type of user (admin or client). Defaults to client.",
    )
    remember_me: bool = Field(
        False,
        description="If true, returns offline tokens for extended 30-day sessions.",
    )


class UserLoginData(BaseModel):
    """User login data schema."""

    token: Any
    first_login: bool
    is_reset_password: bool


class UserLoginResponse(SuccessResponse):
    """User login response schema."""

    model_config = ConfigDict(extra="ignore")
    token: Any
    first_login: bool
    is_reset_password: bool


class LogoutRequest(BaseModel):
    """Schema for logout request."""

    tenant_id: UUID4 | None = Field(
        None,
        description="The ID of the tenant. If not provided, the user will be logged in to the first tenant they belong to.",
    )
    refresh_token: str = Field(min_length=1)

    class Config:
        """Pydantic config."""

        from_attributes = True


class LogoutResponse(SuccessResponse):
    """Schema for logout response."""

    message: str

    class Config:
        """Pydantic config."""

        from_attributes = True


class UserBase(BaseModel):
    """Base user schema."""

    name: str = Field(min_length=1, max_length=100)
    email: EmailStr = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Validate that name contains only letters, spaces, hyphens, and apostrophes."""
        import re

        stripped_value = value.strip()
        if not re.match(r"^[a-zA-Z\s\-']+$", stripped_value):
            raise ValueError("Name can only contain letters, spaces, hyphens, and apostrophes")
        return stripped_value


class UserCreate(UserBase):
    """Create user schema."""

    password: str = Field(min_length=8, max_length=100)
    permissions: List[PermissionList] | None = None
    role: UserRoleEnum
    company: str | None = Field(None, max_length=255, description="Company name")
    purpose: str | None = Field(None, max_length=255, description="Purpose of using the platform")
    user_type: UserTypeEnum = Field(UserTypeEnum.CLIENT, description="Type of user (admin or client)")

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        is_valid, message = validate_password_string(value)
        if not is_valid:
            raise ValueError(message)
        return value

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: UserRoleEnum) -> UserRoleEnum:
        if value == UserRoleEnum.SUPER_ADMIN:
            raise ValueError("The SUPER_ADMIN role is not permitted.")
        return value


class UserRegisterResponse(SuccessResponse):
    """User register response schema."""

    message: str

    class Config:
        """Pydantic config."""

        from_attributes = True


class ResourceCreate(BaseModel):
    """Resource create schema."""

    resource_type: str
    resource_id: str
    scopes: List[str]  # view , manage


class DeletePermissionRequest(BaseModel):
    """Delete permission request schema."""

    resource_type: str
    resource_id: str
    delete_resource: bool = False


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""

    refresh_token: str = Field(min_length=1)


class RefreshTokenResponse(SuccessResponse):
    """Refresh token response schema."""

    model_config = ConfigDict(extra="ignore")
    token: Any
