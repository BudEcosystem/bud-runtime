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

"""OAuth-related schemas for SSO integration."""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from budapp.commons.constants import OAuthProviderEnum
from budapp.commons.schemas import CamelCaseModel


class OAuthLoginRequest(CamelCaseModel):
    """Request model for initiating OAuth login."""

    provider: OAuthProviderEnum = Field(..., description="OAuth provider to use")
    tenant_id: Optional[UUID] = Field(None, description="Tenant ID for multi-tenant support")
    redirect_uri: Optional[HttpUrl] = Field(None, description="Custom redirect URI after OAuth")


class OAuthLoginResponse(CamelCaseModel):
    """Response model for OAuth login initiation."""

    auth_url: HttpUrl = Field(..., description="OAuth authorization URL")
    state: str = Field(..., description="State parameter for CSRF protection")
    expires_at: datetime = Field(..., description="When the OAuth session expires")


class OAuthCallbackRequest(BaseModel):
    """Request model for OAuth callback."""

    code: str = Field(..., description="Authorization code from provider")
    state: str = Field(..., description="State parameter for validation")
    provider: Optional[str] = Field(None, description="Provider name from callback")
    error: Optional[str] = Field(None, description="Error from provider if any")
    error_description: Optional[str] = Field(None, description="Error description if any")


class OAuthLinkRequest(CamelCaseModel):
    """Request model for linking OAuth account."""

    provider: OAuthProviderEnum = Field(..., description="OAuth provider to link")


class OAuthUserInfo(CamelCaseModel):
    """OAuth user information from provider."""

    provider: OAuthProviderEnum
    external_id: str = Field(..., description="User ID from provider")
    email: Optional[str] = None
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    picture: Optional[str] = None
    locale: Optional[str] = None
    email_verified: Optional[bool] = None
    provider_data: Optional[Dict] = Field(default_factory=dict, description="Raw provider data")


class OAuthTokenResponse(CamelCaseModel):
    """OAuth token response after successful authentication."""

    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"
    user_info: OAuthUserInfo
    is_new_user: bool = Field(False, description="Whether a new user was created")
    requires_linking: bool = Field(False, description="Whether account linking is required")


class OAuthProviderConfig(CamelCaseModel):
    """OAuth provider configuration."""

    provider: OAuthProviderEnum
    enabled: bool = True
    client_id: Optional[str] = Field(None, description="OAuth client ID")
    allowed_domains: Optional[List[str]] = Field(None, description="Allowed email domains")
    auto_create_users: bool = Field(False, description="Auto-create users on first login")
    icon_url: Optional[str] = None
    display_name: Optional[str] = None


class OAuthProvidersResponse(CamelCaseModel):
    """Response model for available OAuth providers."""

    providers: List[OAuthProviderConfig]
    tenant_id: UUID


class OAuthSessionInfo(CamelCaseModel):
    """OAuth session information."""

    id: UUID
    provider: OAuthProviderEnum
    state: str
    redirect_uri: Optional[str] = None
    expires_at: datetime
    completed: bool = False


class OAuthErrorResponse(CamelCaseModel):
    """OAuth error response."""

    error: str
    error_description: Optional[str] = None
    provider: Optional[OAuthProviderEnum] = None
