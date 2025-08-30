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

"""OAuth routes for SSO integration."""

from typing import Union
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.auth.oauth_error_handler import OAuthError
from budapp.commons import logging
from budapp.commons.api_utils import get_oauth_base_url
from budapp.commons.dependencies import get_current_user, get_session
from budapp.commons.exceptions import ClientException
from budapp.commons.rate_limiter import rate_limit
from budapp.commons.schemas import ErrorResponse, SingleResponse
from budapp.user_ops.models import User

from .oauth_schemas import (
    OAuthCallbackRequest,
    OAuthErrorResponse,
    OAuthLinkRequest,
    OAuthLoginRequest,
    OAuthLoginResponse,
    OAuthProvidersResponse,
    OAuthTokenResponse,
)
from .oauth_services import OAuthService


logger = logging.get_logger(__name__)

oauth_router = APIRouter(prefix="/oauth", tags=["oauth"])


@oauth_router.post(
    "/login",
    responses={
        status.HTTP_200_OK: {
            "model": SingleResponse[OAuthLoginResponse],
            "description": "OAuth login URL generated successfully",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request or provider not enabled",
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "model": ErrorResponse,
            "description": "Too many login attempts",
        },
    },
    description="Initiate OAuth login flow for a specific provider",
)
@rate_limit(max_requests=10, window_seconds=60)  # 10 requests per minute
async def initiate_oauth_login(
    request: Request,
    login_request: OAuthLoginRequest,
    session: Annotated[Session, Depends(get_session)],
) -> Union[SingleResponse[OAuthLoginResponse], ErrorResponse]:
    """Initiate OAuth login flow."""
    try:
        oauth_service = OAuthService(session)

        # Get base URL from request
        base_url = get_oauth_base_url(request)

        # Use proxy by default to hide Keycloak URL
        response = await oauth_service.initiate_oauth_login(login_request, base_url, use_proxy=True)

        return SingleResponse[OAuthLoginResponse](
            success=True,
            message="OAuth login initiated successfully",
            result=response,
        )
    except OAuthError as e:
        logger.error(f"OAuth login initiation failed: {e.code} - {e.message}")
        return ErrorResponse(
            code=status.HTTP_400_BAD_REQUEST,
            message=e.message,
        ).to_http_response()
    except ClientException as e:
        logger.error(f"OAuth login initiation failed: {e}")
        return ErrorResponse(
            code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Unexpected error in OAuth login: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to initiate OAuth login",
        ).to_http_response()


# DEPRECATED: Callback handled by oauth_internal_proxy.py
# @oauth_router.get(
#     "/callback",
#     responses={
#         status.HTTP_200_OK: {
#             "model": SingleResponse[OAuthTokenResponse],
#             "description": "OAuth authentication successful",
#         },
#         status.HTTP_400_BAD_REQUEST: {
#             "model": OAuthErrorResponse,
#             "description": "OAuth authentication failed",
#         },
#     },
#     description="Handle OAuth callback from provider",
# )
# async def oauth_callback(
#     code: str = Query(..., description="Authorization code from provider"),
#     state: str = Query(..., description="State parameter for validation"),
#     error: str = Query(None, description="Error from provider"),
#     error_description: str = Query(None, description="Error description"),
#     session: Session = Depends(get_session),
# ) -> Union[SingleResponse[OAuthTokenResponse], OAuthErrorResponse]:
#     """Handle OAuth callback from provider."""
#     try:
#         oauth_service = OAuthService(session)

#         callback_request = OAuthCallbackRequest(
#             code=code,
#             state=state,
#             error=error,
#             error_description=error_description,
#         )

#         response = await oauth_service.handle_oauth_callback(callback_request)

#         # Check if account linking is required
#         if response.requires_linking:
#             return SingleResponse[OAuthTokenResponse](
#                 success=True,
#                 message="Account linking required",
#                 result=response,
#             )

#         return SingleResponse[OAuthTokenResponse](
#             success=True,
#             message="OAuth authentication successful",
#             result=response,
#         )
#     except OAuthError as e:
#         logger.error(f"OAuth callback failed: {e.code} - {e.message}")
#         return OAuthErrorResponse(
#             error=e.code,
#             error_description=e.message,
#             provider=e.provider,
#         )
#     except ClientException as e:
#         logger.error(f"OAuth callback failed: {e}")
#         return OAuthErrorResponse(
#             error="authentication_failed",
#             error_description=str(e),
#         )
#     except Exception as e:
#         logger.exception(f"Unexpected error in OAuth callback: {e}")
#         return OAuthErrorResponse(
#             error="internal_error",
#             error_description="An unexpected error occurred",
#         )


@oauth_router.post(
    "/link",
    responses={
        status.HTTP_200_OK: {
            "model": SingleResponse,
            "description": "OAuth account linked successfully",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Account linking failed",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Authentication required",
        },
    },
    description="Link OAuth account to existing user",
)
async def link_oauth_account(
    link_request: OAuthLinkRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Union[SingleResponse, ErrorResponse]:
    """Link OAuth account to existing user."""
    try:
        # TODO: This would need to initiate a new OAuth flow to get the provider user ID.
        # oauth_service = OAuthService(session)
        # For now, we'll return a placeholder response

        return SingleResponse(
            success=True,
            message=f"Please complete OAuth flow to link your {link_request.provider.value} account",
            result=None,
        )
    except ClientException as e:
        logger.error(f"OAuth account linking failed: {e}")
        return ErrorResponse(
            code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Unexpected error in OAuth account linking: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to link OAuth account",
        ).to_http_response()


@oauth_router.get(
    "/providers",
    responses={
        status.HTTP_200_OK: {
            "model": SingleResponse[OAuthProvidersResponse],
            "description": "Available OAuth providers retrieved successfully",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request",
        },
    },
    description="Get available OAuth providers for a tenant",
)
async def get_oauth_providers(
    tenant_id: UUID = Query(None, description="Tenant ID (uses default if not provided)"),
    session: Session = Depends(get_session),
) -> Union[SingleResponse[OAuthProvidersResponse], ErrorResponse]:
    """Get available OAuth providers for a tenant."""
    try:
        oauth_service = OAuthService(session)

        # If no tenant_id provided, get default tenant
        if not tenant_id:
            from budapp.commons.config import app_settings

            tenant = await oauth_service._get_tenant(None)
            tenant_id = tenant.id

        providers = await oauth_service.get_available_providers(tenant_id)

        response = OAuthProvidersResponse(
            providers=providers,
            tenant_id=tenant_id,
        )

        return SingleResponse[OAuthProvidersResponse](
            success=True,
            message="OAuth providers retrieved successfully",
            result=response,
        )
    except ClientException as e:
        logger.error(f"Failed to get OAuth providers: {e}")
        return ErrorResponse(
            code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Unexpected error getting OAuth providers: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve OAuth providers",
        ).to_http_response()
