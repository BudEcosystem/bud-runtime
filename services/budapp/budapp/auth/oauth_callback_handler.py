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

"""Enhanced OAuth callback handler with frontend redirect support."""

from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.auth.oauth_error_handler import OAuthError
from budapp.auth.oauth_schemas import OAuthCallbackRequest
from budapp.auth.oauth_services import OAuthService
from budapp.commons import logging
from budapp.commons.dependencies import get_session
from budapp.commons.exceptions import ClientException
from budapp.user_ops.crud import UserDataManager
from budapp.user_ops.oauth_models import OAuthSession


logger = logging.get_logger(__name__)

oauth_callback_router = APIRouter(tags=["oauth"])


@oauth_callback_router.get(
    "/oauth/callback",
    responses={
        status.HTTP_302_FOUND: {
            "description": "Redirect to frontend with authentication result",
        },
    },
    description="Handle OAuth callback and redirect to frontend",
)
async def oauth_callback_with_redirect(
    request: Request,
    code: Optional[str] = Query(None, description="Authorization code from provider"),
    state: str = Query(..., description="State parameter for validation"),
    error: Optional[str] = Query(None, description="Error from provider"),
    error_description: Optional[str] = Query(None, description="Error description"),
    session: Annotated[Session, Depends(get_session)] = None,
) -> RedirectResponse:
    """Handle OAuth callback from provider and redirect to frontend.

    This enhanced callback handler:
    1. Validates the OAuth callback
    2. Exchanges code for tokens
    3. Creates or updates user
    4. Redirects to frontend with tokens or error

    Args:
        code: Authorization code from OAuth provider
        state: State parameter for CSRF protection
        error: Error code if authentication failed
        error_description: Detailed error description
        session: Database session

    Returns:
        RedirectResponse to frontend with tokens or error
    """
    # Default redirect URLs
    default_success_url = str(request.base_url).rstrip("/") + "/auth/success"
    default_error_url = str(request.base_url).rstrip("/") + "/auth/error"

    try:
        # Retrieve OAuth session to get redirect URLs
        oauth_session_record = await UserDataManager(session).retrieve_by_fields(
            OAuthSession, {"state": state}, missing_ok=True
        )

        # Get redirect URLs from session metadata or use defaults
        if oauth_session_record and oauth_session_record.session_metadata:
            frontend_redirect = oauth_session_record.session_metadata.get("frontend_redirect", default_success_url)
            error_redirect = oauth_session_record.session_metadata.get("error_redirect", default_error_url)
        else:
            frontend_redirect = default_success_url
            error_redirect = default_error_url

        # Handle provider errors
        if error:
            logger.error(f"OAuth provider returned error: {error} - {error_description}")
            error_params = {
                "error": error,
                "error_description": error_description or "Authentication failed",
                "state": state,
            }
            return RedirectResponse(
                url=f"{error_redirect}?{urlencode(error_params)}", status_code=status.HTTP_302_FOUND
            )

        # Validate that we have an authorization code
        if not code:
            error_params = {
                "error": "missing_code",
                "error_description": "Authorization code is missing",
                "state": state,
            }
            return RedirectResponse(
                url=f"{error_redirect}?{urlencode(error_params)}", status_code=status.HTTP_302_FOUND
            )

        # Process OAuth callback
        oauth_service = OAuthService(session)
        callback_request = OAuthCallbackRequest(
            code=code,
            state=state,
            error=error,
            error_description=error_description,
        )

        response = await oauth_service.handle_oauth_callback(callback_request)

        # Check if account linking is required
        if response.requires_linking:
            # Redirect to a linking page with user info
            link_params = {
                "requires_linking": "true",
                "email": response.user_info.email if response.user_info else "",
                "provider": response.user_info.provider if response.user_info else "",
                "state": state,
            }
            return RedirectResponse(
                url=f"{frontend_redirect}?{urlencode(link_params)}", status_code=status.HTTP_302_FOUND
            )

        # Successful authentication - redirect with tokens
        success_params = {
            "token": response.access_token,
            "refresh_token": response.refresh_token,
            "expires_in": str(response.expires_in),
            "state": state,
        }

        # Add user info if available
        if response.user_info:
            success_params["email"] = response.user_info.email
            success_params["name"] = response.user_info.name or ""
            success_params["is_new_user"] = str(response.is_new_user).lower()

        logger.info(
            f"OAuth authentication successful for user {response.user_info.email if response.user_info else 'unknown'}"
        )

        return RedirectResponse(
            url=f"{frontend_redirect}?{urlencode(success_params)}", status_code=status.HTTP_302_FOUND
        )

    except OAuthError as e:
        logger.error(f"OAuth callback failed with OAuthError: {e.code} - {e.message}")
        error_params = {
            "error": e.code.value if hasattr(e.code, "value") else str(e.code),
            "error_description": e.message,
            "provider": e.provider or "",
            "state": state,
        }
        # Use error_redirect if we have it, otherwise use default
        redirect_url = error_redirect if "error_redirect" in locals() else default_error_url
        return RedirectResponse(url=f"{redirect_url}?{urlencode(error_params)}", status_code=status.HTTP_302_FOUND)

    except ClientException as e:
        logger.error(f"OAuth callback failed with ClientException: {e}")
        error_params = {"error": "authentication_failed", "error_description": str(e), "state": state}
        redirect_url = error_redirect if "error_redirect" in locals() else default_error_url
        return RedirectResponse(url=f"{redirect_url}?{urlencode(error_params)}", status_code=status.HTTP_302_FOUND)

    except Exception as e:
        logger.exception(f"Unexpected error in OAuth callback: {e}")
        error_params = {
            "error": "internal_error",
            "error_description": "An unexpected error occurred during authentication",
            "state": state,
        }
        redirect_url = error_redirect if "error_redirect" in locals() else default_error_url
        return RedirectResponse(url=f"{redirect_url}?{urlencode(error_params)}", status_code=status.HTTP_302_FOUND)
