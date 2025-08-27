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

"""OAuth proxy routes to hide Keycloak URL from end users."""

from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.dependencies import get_session
from budapp.commons.exceptions import ClientException
from budapp.commons.schemas import ErrorResponse


logger = logging.get_logger(__name__)

oauth_proxy_router = APIRouter(prefix="/oauth/proxy", tags=["oauth-proxy"])


def get_internal_keycloak_url() -> str:
    """Get internal Keycloak URL for server-to-server communication."""
    # Use internal Docker network URL if available, otherwise use configured URL
    if "host.docker.internal" in app_settings.keycloak_server_url:
        # Keep using host.docker.internal for internal communication
        return app_settings.keycloak_server_url
    return app_settings.keycloak_server_url


def get_public_proxy_url(request: Request) -> str:
    """Get public proxy URL for client-facing redirects."""
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}/api/v1/auth/oauth/proxy"


@oauth_proxy_router.get(
    "/authorize",
    responses={
        status.HTTP_302_FOUND: {
            "description": "Redirect to Keycloak authorization endpoint",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request parameters",
        },
    },
    description="Proxy authorization requests to Keycloak",
)
async def proxy_authorize(
    request: Request,
    client_id: str = Query(..., description="OAuth client ID"),
    redirect_uri: str = Query(..., description="Redirect URI after authentication"),
    response_type: str = Query("code", description="OAuth response type"),
    scope: str = Query("openid email profile", description="OAuth scopes"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    kc_idp_hint: Optional[str] = Query(None, description="Identity provider hint"),
    realm_name: str = Query("bud-v3-realm", description="Keycloak realm"),
) -> RedirectResponse:
    """Proxy OAuth authorization requests to Keycloak.

    This endpoint acts as a proxy to hide the actual Keycloak URL from clients.
    It forwards the authorization request to Keycloak and handles the response.
    """
    try:
        internal_keycloak_url = get_internal_keycloak_url().rstrip("/")

        # Build Keycloak authorization URL
        auth_params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": response_type,
            "scope": scope,
            "state": state,
        }

        # Add identity provider hint if provided (for social login)
        if kc_idp_hint:
            auth_params["kc_idp_hint"] = kc_idp_hint

        # Construct the authorization URL
        from urllib.parse import urlencode

        keycloak_auth_url = (
            f"{internal_keycloak_url}/realms/{realm_name}/protocol/openid-connect/auth?{urlencode(auth_params)}"
        )

        # Replace host.docker.internal with 127.0.0.1 for browser access (matches GitHub OAuth)
        if "host.docker.internal" in keycloak_auth_url:
            # Using 127.0.0.1 to match GitHub OAuth configuration
            keycloak_auth_url = keycloak_auth_url.replace("host.docker.internal", "127.0.0.1")

        logger.debug(f"Proxying authorization to Keycloak: {keycloak_auth_url}")

        # Return redirect response to Keycloak
        # The URL is now browser-accessible (localhost instead of host.docker.internal)
        return RedirectResponse(url=keycloak_auth_url, status_code=status.HTTP_302_FOUND)

    except Exception as e:
        logger.exception(f"Error proxying authorization request: {e}")
        raise ClientException("Failed to process authorization request")


@oauth_proxy_router.post(
    "/token",
    responses={
        status.HTTP_200_OK: {
            "description": "Token exchange successful",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request or authentication failed",
        },
    },
    description="Proxy token exchange requests to Keycloak",
)
async def proxy_token_exchange(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> Dict[str, Any]:
    """Proxy OAuth token exchange requests to Keycloak.

    This endpoint handles the token exchange after successful authorization,
    hiding the actual Keycloak URL from clients.
    """
    try:
        # Get form data from request
        form_data = await request.form()

        internal_keycloak_url = get_internal_keycloak_url().rstrip("/")

        # Get realm from form data or use default
        realm_name = form_data.get("realm", "bud-v3-realm")

        # Prepare token exchange request
        token_url = f"{internal_keycloak_url}/realms/{realm_name}/protocol/openid-connect/token"

        # Forward the token exchange request to Keycloak
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data=dict(form_data),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )

            if response.status_code != 200:
                logger.error(f"Token exchange failed: {response.text}")
                raise ClientException("Authentication failed")

            return response.json()

    except ClientException:
        raise
    except Exception as e:
        logger.exception(f"Error proxying token exchange: {e}")
        raise ClientException("Failed to exchange token")


@oauth_proxy_router.get(
    "/userinfo",
    responses={
        status.HTTP_200_OK: {
            "description": "User information retrieved successfully",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Invalid or expired token",
        },
    },
    description="Proxy userinfo requests to Keycloak",
)
async def proxy_userinfo(
    request: Request,
    authorization: str = Depends(lambda r: r.headers.get("Authorization")),
) -> Dict[str, Any]:
    """Proxy userinfo requests to Keycloak.

    This endpoint retrieves user information from Keycloak using the access token,
    hiding the actual Keycloak URL from clients.
    """
    try:
        if not authorization:
            raise ClientException("Authorization header required")

        internal_keycloak_url = get_internal_keycloak_url().rstrip("/")

        # Default realm - could be extracted from token if needed
        realm_name = "bud-v3-realm"

        # Forward the userinfo request to Keycloak
        userinfo_url = f"{internal_keycloak_url}/realms/{realm_name}/protocol/openid-connect/userinfo"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                userinfo_url,
                headers={
                    "Authorization": authorization,
                },
            )

            if response.status_code != 200:
                logger.error(f"Userinfo request failed: {response.text}")
                raise ClientException("Failed to retrieve user information")

            return response.json()

    except ClientException:
        raise
    except Exception as e:
        logger.exception(f"Error proxying userinfo request: {e}")
        raise ClientException("Failed to retrieve user information")


@oauth_proxy_router.post(
    "/logout",
    responses={
        status.HTTP_200_OK: {
            "description": "Logout successful",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Logout failed",
        },
    },
    description="Proxy logout requests to Keycloak",
)
async def proxy_logout(
    request: Request,
    refresh_token: str = Query(..., description="Refresh token to revoke"),
    realm_name: str = Query("bud-v3-realm", description="Keycloak realm"),
) -> Dict[str, str]:
    """Proxy logout requests to Keycloak.

    This endpoint handles logout by revoking the refresh token,
    hiding the actual Keycloak URL from clients.
    """
    try:
        internal_keycloak_url = get_internal_keycloak_url().rstrip("/")

        # Get client credentials from environment or database
        # This should ideally come from the tenant configuration
        client_id = "default-internal-client"
        client_secret = app_settings.keycloak_client_secret  # Add this to settings if needed

        # Prepare logout request
        logout_url = f"{internal_keycloak_url}/realms/{realm_name}/protocol/openid-connect/logout"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                logout_url,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )

            if response.status_code not in [200, 204]:
                logger.error(f"Logout failed: {response.text}")
                raise ClientException("Logout failed")

            return {"message": "Logout successful"}

    except ClientException:
        raise
    except Exception as e:
        logger.exception(f"Error proxying logout request: {e}")
        raise ClientException("Failed to process logout")
