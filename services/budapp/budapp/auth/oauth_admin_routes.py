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

"""Admin routes for managing OAuth configurations."""

from typing import List, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.commons import logging
from budapp.commons.constants import OAuthProviderEnum, UserRoleEnum
from budapp.commons.dependencies import get_current_user, get_session
from budapp.commons.exceptions import ClientException
from budapp.commons.schemas import CamelCaseModel, ErrorResponse, SingleResponse
from budapp.user_ops.models import User

from .tenant_oauth_service import TenantOAuthService


logger = logging.get_logger(__name__)

oauth_admin_router = APIRouter(prefix="/admin/oauth", tags=["oauth-admin"])


class ConfigureOAuthProviderRequest(CamelCaseModel):
    """Request model for configuring OAuth provider."""

    tenant_id: UUID = Field(..., description="Tenant ID")
    provider: OAuthProviderEnum = Field(..., description="OAuth provider")
    client_id: str = Field(..., description="OAuth client ID")
    client_secret: str = Field(..., description="OAuth client secret")
    enabled: bool = Field(True, description="Whether provider is enabled")
    allowed_domains: Optional[List[str]] = Field(None, description="Allowed email domains")
    auto_create_users: bool = Field(False, description="Auto-create users on first login")
    config_data: dict = Field(None, description="Additional provider-specific configuration")


class OAuthConfigurationResponse(CamelCaseModel):
    """Response model for OAuth configuration."""

    id: UUID
    tenant_id: UUID
    provider: str
    client_id: str
    enabled: bool
    allowed_domains: Optional[List[str]] = Field(default=[], description="Allowed email domains")
    auto_create_users: bool
    config_data: Optional[dict] = Field(default=None, description="Additional provider configuration")


def check_admin_permission(current_user: User) -> None:
    """Check if user has admin permissions."""
    if current_user.role not in [UserRoleEnum.ADMIN, UserRoleEnum.SUPER_ADMIN]:
        raise ClientException("Insufficient permissions to manage OAuth configurations")


@oauth_admin_router.post(
    "/configure",
    responses={
        status.HTTP_200_OK: {
            "model": SingleResponse[OAuthConfigurationResponse],
            "description": "OAuth provider configured successfully",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid configuration",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Insufficient permissions",
        },
    },
    description="Configure OAuth provider for a tenant (admin only)",
)
async def configure_oauth_provider(
    request: ConfigureOAuthProviderRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Union[SingleResponse[OAuthConfigurationResponse], ErrorResponse]:
    """Configure OAuth provider for a tenant."""
    try:
        # Check admin permissions
        check_admin_permission(current_user)

        service = TenantOAuthService(session)

        config = await service.configure_oauth_provider(
            tenant_id=request.tenant_id,
            provider=request.provider,
            client_id=request.client_id,
            client_secret=request.client_secret,
            enabled=request.enabled,
            allowed_domains=request.allowed_domains,
            auto_create_users=request.auto_create_users,
            config_data=request.config_data,
        )

        response = OAuthConfigurationResponse(
            id=config.id,
            tenant_id=config.tenant_id,
            provider=config.provider,
            client_id=config.client_id,
            enabled=config.enabled,
            allowed_domains=config.allowed_domains or [],
            auto_create_users=config.auto_create_users,
            config_data=config.config_data,
        )

        return SingleResponse[OAuthConfigurationResponse](
            success=True,
            message=f"OAuth provider {request.provider.value} configured successfully",
            result=response,
        )
    except ClientException as e:
        logger.error(f"Failed to configure OAuth provider: {e}")
        return ErrorResponse(
            code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Unexpected error configuring OAuth provider: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to configure OAuth provider",
        ).to_http_response()


@oauth_admin_router.get(
    "/configurations/{tenant_id}",
    responses={
        status.HTTP_200_OK: {
            "model": SingleResponse[List[OAuthConfigurationResponse]],
            "description": "OAuth configurations retrieved successfully",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Insufficient permissions",
        },
    },
    description="Get OAuth configurations for a tenant (admin only)",
)
async def get_oauth_configurations(
    tenant_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    enabled_only: bool = True,
) -> Union[SingleResponse[List[OAuthConfigurationResponse]], ErrorResponse]:
    """Get OAuth configurations for a tenant."""
    try:
        # Check admin permissions
        check_admin_permission(current_user)

        service = TenantOAuthService(session)

        configs = await service.get_oauth_configurations(tenant_id, enabled_only)

        response_data = [
            OAuthConfigurationResponse(
                id=config.id,
                tenant_id=config.tenant_id,
                provider=config.provider,
                client_id=config.client_id,
                enabled=config.enabled,
                allowed_domains=config.allowed_domains or [],
                auto_create_users=config.auto_create_users,
                config_data=config.config_data,
            )
            for config in configs
        ]

        return SingleResponse[List[OAuthConfigurationResponse]](
            success=True,
            message="OAuth configurations retrieved successfully",
            result=response_data,
        )
    except ClientException as e:
        logger.error(f"Failed to get OAuth configurations: {e}")
        return ErrorResponse(
            code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Unexpected error getting OAuth configurations: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve OAuth configurations",
        ).to_http_response()


@oauth_admin_router.put(
    "/disable/{tenant_id}/{provider}",
    responses={
        status.HTTP_200_OK: {
            "model": SingleResponse,
            "description": "OAuth provider disabled successfully",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Insufficient permissions",
        },
    },
    description="Disable OAuth provider for a tenant (admin only)",
)
async def disable_oauth_provider(
    tenant_id: UUID,
    provider: OAuthProviderEnum,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Union[SingleResponse, ErrorResponse]:
    """Disable OAuth provider for a tenant."""
    try:
        # Check admin permissions
        check_admin_permission(current_user)

        service = TenantOAuthService(session)

        await service.disable_oauth_provider(tenant_id, provider)

        return SingleResponse(
            success=True,
            message=f"OAuth provider {provider.value} disabled successfully",
            result=None,
        )
    except ClientException as e:
        logger.error(f"Failed to disable OAuth provider: {e}")
        return ErrorResponse(
            code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Unexpected error disabling OAuth provider: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to disable OAuth provider",
        ).to_http_response()
