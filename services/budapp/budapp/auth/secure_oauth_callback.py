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

"""Secure OAuth callback handler using exchange tokens."""

from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.auth.oauth_error_handler import OAuthError
from budapp.auth.oauth_schemas import OAuthCallbackRequest
from budapp.auth.oauth_services import OAuthService
from budapp.auth.token_exchange_service import TokenExchangeService
from budapp.auth.user_onboarding_service import UserOnboardingService
from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.dependencies import get_session
from budapp.commons.exceptions import ClientException
from budapp.user_ops.crud import UserDataManager
from budapp.user_ops.models import User
from budapp.user_ops.oauth_models import OAuthSession


logger = logging.get_logger(__name__)

secure_oauth_callback_router = APIRouter(tags=["oauth"])


@secure_oauth_callback_router.get(
    "/oauth/secure-callback",
    responses={
        status.HTTP_302_FOUND: {
            "description": "Redirect to frontend with exchange token",
        },
    },
    description="Secure OAuth callback that uses exchange tokens",
)
async def secure_oauth_callback(
    request: Request,
    code: Optional[str] = Query(None, description="Authorization code from provider"),
    state: str = Query(..., description="State parameter for validation"),
    error: Optional[str] = Query(None, description="Error from provider"),
    error_description: Optional[str] = Query(None, description="Error description"),
    session: Annotated[Session, Depends(get_session)] = None,
) -> RedirectResponse:
    """Secure OAuth callback that uses exchange tokens instead of URL parameters.

    This callback handler improves security by:
    1. Processing the OAuth callback normally
    2. Creating a short-lived exchange token instead of JWT tokens
    3. Redirecting to frontend with only the exchange token
    4. Frontend exchanges the token for JWT tokens via API call

    Benefits:
    - No sensitive tokens in URL/browser history
    - Tokens are generated fresh when requested
    - Exchange tokens are single-use and expire quickly
    - Prevents token leakage via referrer headers or logs

    Args:
        code: Authorization code from OAuth provider
        state: State parameter for CSRF protection
        error: Error code if authentication failed
        error_description: Detailed error description
        session: Database session

    Returns:
        RedirectResponse to frontend with exchange token or error
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
            }
            return RedirectResponse(
                url=f"{error_redirect}?{urlencode(error_params)}", status_code=status.HTTP_302_FOUND
            )

        # Validate that we have an authorization code
        if not code:
            error_params = {
                "error": "missing_code",
                "error_description": "Authorization code is missing",
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

        # If this is a new user, set up billing and default project
        if response.is_new_user:
            try:
                onboarding_service = UserOnboardingService(session)
                await onboarding_service.onboard_user_by_email(response.user_info.email)
            except Exception as e:
                logger.error(f"Failed to complete new user setup for {response.user_info.email}: {e}")
                # Don't fail the login if setup fails

        # Check if account linking is required
        if response.requires_linking:
            # For account linking, we still need to pass some info
            link_params = {
                "requires_linking": "true",
                "email": response.user_info.email if response.user_info else "",
                "provider": response.user_info.provider if response.user_info else "",
            }
            return RedirectResponse(
                url=f"{frontend_redirect}?{urlencode(link_params)}", status_code=status.HTTP_302_FOUND
            )

        # Create exchange token instead of passing JWT tokens
        exchange_service = TokenExchangeService(session)

        # We need to get the user ID from the response
        # The OAuth service should have created or found the user
        user_email = response.user_info.email if response.user_info else None
        if not user_email:
            raise ClientException("User email not found in OAuth response")

        # Get the user from database
        from budapp.user_ops.models import User

        user = await UserDataManager(session).retrieve_by_fields(User, {"email": user_email}, missing_ok=True)

        if not user:
            raise ClientException("User not found after OAuth authentication")

        # Create exchange token
        exchange_token = await exchange_service.create_exchange_token(
            user_id=user.id,
            email=user_email,
            is_new_user=response.is_new_user,
            provider=response.user_info.provider if response.user_info else None,
            ttl_seconds=60,  # 1 minute expiry
        )

        # Redirect with only the exchange token
        success_params = {
            "exchange_token": exchange_token,
            # Optionally include non-sensitive info
            "email": user_email,
            "is_new_user": str(response.is_new_user).lower(),
        }

        logger.info(f"OAuth authentication successful for user {user_email}, exchange token created")

        return RedirectResponse(
            url=f"{frontend_redirect}?{urlencode(success_params)}", status_code=status.HTTP_302_FOUND
        )

    except OAuthError as e:
        logger.error(f"OAuth callback failed with OAuthError: {e.code} - {e.message}")
        error_params = {
            "error": e.code.value if hasattr(e.code, "value") else str(e.code),
            "error_description": e.message,
        }
        redirect_url = error_redirect if "error_redirect" in locals() else default_error_url
        return RedirectResponse(url=f"{redirect_url}?{urlencode(error_params)}", status_code=status.HTTP_302_FOUND)

    except ClientException as e:
        logger.error(f"OAuth callback failed with ClientException: {e}")
        error_params = {
            "error": "authentication_failed",
            "error_description": str(e),
        }
        redirect_url = error_redirect if "error_redirect" in locals() else default_error_url
        return RedirectResponse(url=f"{redirect_url}?{urlencode(error_params)}", status_code=status.HTTP_302_FOUND)

    except Exception as e:
        logger.exception(f"Unexpected error in secure OAuth callback: {e}")
        error_params = {
            "error": "internal_error",
            "error_description": "An unexpected error occurred during authentication",
        }
        redirect_url = error_redirect if "error_redirect" in locals() else default_error_url
        return RedirectResponse(url=f"{redirect_url}?{urlencode(error_params)}", status_code=status.HTTP_302_FOUND)
