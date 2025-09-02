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

"""Internal OAuth proxy that handles provider authentication without exposing Keycloak."""

import secrets
from typing import Any, Dict, Optional
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.auth.oauth_error_handler import OAuthError, OAuthErrorCode
from budapp.auth.tenant_oauth_service import TenantOAuthService
from budapp.auth.token_exchange_service import TokenExchangeService
from budapp.commons import logging
from budapp.commons.api_utils import get_oauth_base_url
from budapp.commons.config import app_settings
from budapp.commons.dependencies import get_session
from budapp.commons.exceptions import ClientException
from budapp.user_ops.crud import UserDataManager
from budapp.user_ops.models import Tenant, User
from budapp.user_ops.oauth_models import OAuthSession, TenantOAuthConfig


logger = logging.get_logger(__name__)

# In-memory store for OAuth state (use Redis in production)
oauth_state_store: Dict[str, Dict[str, Any]] = {}


class InternalOAuthProxy:
    """Handles OAuth flow internally without exposing Keycloak to users."""

    def __init__(self, session: Session):
        self.session = session

    async def initiate_oauth(
        self,
        provider: str,
        tenant_id: Optional[UUID] = None,
        redirect_uri: Optional[str] = None,
        app_redirect_uri: Optional[str] = None,
    ) -> str:
        """Initiate OAuth flow by redirecting directly to provider.

        Args:
            provider: OAuth provider name (google, microsoft, github, linkedin)
            tenant_id: Tenant ID for multi-tenant support
            redirect_uri: Where to redirect after successful auth

        Returns:
            Authorization URL for the OAuth provider
        """
        # Get OAuth configuration for provider with decrypted secret
        oauth_config = await self._get_oauth_config(provider, tenant_id)
        if not oauth_config:
            raise ClientException(f"OAuth provider {provider} is not configured")

        # Get decrypted client secret using TenantOAuthService
        oauth_service = TenantOAuthService(self.session)
        decrypted_config = await oauth_service.get_decrypted_config(
            tenant_id=oauth_config.tenant_id, provider=provider
        )

        if not decrypted_config:
            raise ClientException(f"Failed to decrypt OAuth configuration for {provider}")

        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)

        # Store state with metadata including decrypted secret
        oauth_state_store[state] = {
            "provider": provider,
            "tenant_id": str(oauth_config.tenant_id) if oauth_config.tenant_id else None,
            "frontend_redirect_uri": redirect_uri,  # Where to redirect user after auth
            "oauth_callback_uri": app_redirect_uri,  # OAuth callback URL
            "client_id": decrypted_config["client_id"],
            "client_secret": decrypted_config["client_secret"],
        }

        # Build provider-specific authorization URL
        logger.info(f"Building auth URL for {provider} with callback URI: {app_redirect_uri}")
        auth_url = self._build_provider_auth_url(
            provider=provider,
            client_id=decrypted_config["client_id"],
            redirect_uri=app_redirect_uri,
            state=state,
            scope=self._get_provider_scope(provider),
        )

        logger.info(f"Generated auth URL for {provider}: {auth_url}")
        return auth_url

    async def handle_callback(
        self,
        code: str,
        state: str,
        error: Optional[str] = None,
        error_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle OAuth callback from provider.

        Args:
            code: Authorization code from provider
            state: State parameter for validation
            error: Error from provider
            error_description: Error details

        Returns:
            User tokens and information
        """
        # Validate state
        if state not in oauth_state_store:
            raise OAuthError(
                code=OAuthErrorCode.INVALID_STATE,
                message="Invalid or expired state parameter",
            )

        state_data = oauth_state_store.pop(state)  # Remove after use

        if error:
            raise OAuthError(
                code=OAuthErrorCode.PROVIDER_ERROR,
                message=error_description or "Authentication failed",
            )

        # Exchange code for tokens with provider
        provider = state_data["provider"]
        tokens = await self._exchange_code_with_provider(
            provider=provider,
            code=code,
            client_id=state_data["client_id"],
            client_secret=state_data["client_secret"],
            redirect_uri=state_data.get("oauth_callback_uri")
            or f"{app_settings.base_url}/api/v1/auth/oauth/internal/callback",
        )

        if not tokens:
            raise OAuthError(
                code=OAuthErrorCode.TOKEN_EXCHANGE_FAILED,
                message="Failed to exchange authorization code",
            )

        # Get user info from provider
        user_info = await self._get_user_info_from_provider(
            provider=provider,
            access_token=tokens.get("access_token"),
            id_token=tokens.get("id_token"),
        )

        # Create or update user in our system
        user = await self._process_user(
            provider=provider,
            user_info=user_info,
            tenant_id=state_data.get("tenant_id"),
        )

        # Create exchange token for secure token exchange
        exchange_service = TokenExchangeService(self.session)
        exchange_token = await exchange_service.create_exchange_token(
            user_id=user.id,
            email=user.email,
            is_new_user=user_info.get("is_new_user", False),
            provider=provider,
            ttl_seconds=60,
        )

        return {
            "exchange_token": exchange_token,
            "redirect_uri": state_data.get("frontend_redirect_uri"),
            "user": {
                "email": user.email,
                "name": user.name,
                "is_new_user": user_info.get("is_new_user", False),
            },
        }

    async def _get_oauth_config(
        self,
        provider: str,
        tenant_id: Optional[UUID] = None,
    ) -> Optional[TenantOAuthConfig]:
        """Get OAuth configuration for provider."""
        if not tenant_id:
            # Get default tenant
            tenant = await UserDataManager(self.session).retrieve_by_fields(
                Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
            )
            tenant_id = tenant.id if tenant else None

        if not tenant_id:
            return None

        # Convert provider string to enum if needed
        from budapp.commons.constants import OAuthProviderEnum

        # Ensure provider is a string value
        provider_str = provider.value if hasattr(provider, "value") else str(provider).lower()
        return await UserDataManager(self.session).retrieve_by_fields(
            TenantOAuthConfig,
            {"tenant_id": tenant_id, "provider": provider_str, "enabled": True},
            missing_ok=True,
        )

    def _build_provider_auth_url(
        self,
        provider: str,
        client_id: str,
        redirect_uri: str,
        state: str,
        scope: str,
    ) -> str:
        """Build authorization URL for specific provider."""
        # Provider-specific authorization endpoints
        auth_endpoints = {
            "google": "https://accounts.google.com/o/oauth2/v2/auth",
            "microsoft": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "github": "https://github.com/login/oauth/authorize",
            "linkedin": "https://www.linkedin.com/oauth/v2/authorization",
        }

        base_url = auth_endpoints.get(provider.lower())
        if not base_url:
            raise ClientException(f"Unknown provider: {provider}")

        # Build authorization parameters
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope,
            "state": state,
        }

        # Provider-specific parameters
        if provider.lower() == "google":
            params["access_type"] = "offline"  # For refresh token
            params["prompt"] = "consent"
        elif provider.lower() == "microsoft":
            params["response_mode"] = "query"

        return f"{base_url}?{urlencode(params)}"

    def _get_provider_scope(self, provider: str) -> str:
        """Get OAuth scope for provider."""
        scopes = {
            "google": "openid email profile",
            "microsoft": "openid email profile User.Read",
            "github": "user:email",
            "linkedin": "openid profile email",
        }
        return scopes.get(provider.lower(), "openid email profile")

    async def _exchange_code_with_provider(
        self,
        provider: str,
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> Optional[Dict[str, Any]]:
        """Exchange authorization code with OAuth provider."""
        # Provider-specific token endpoints
        token_endpoints = {
            "google": "https://oauth2.googleapis.com/token",
            "microsoft": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            "github": "https://github.com/login/oauth/access_token",
            "linkedin": "https://www.linkedin.com/oauth/v2/accessToken",
        }

        token_url = token_endpoints.get(provider.lower())
        if not token_url:
            return None

        try:
            logger.info(f"Exchanging code with {provider} - redirect_uri: {redirect_uri}")

            async with httpx.AsyncClient() as client:
                # Prepare token request
                data = {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": client_id,
                    "client_secret": client_secret,
                }

                logger.info(
                    f"Token exchange data for {provider}: client_id={client_id}, has_secret={bool(client_secret)}, redirect_uri={redirect_uri}"
                )

                # GitHub requires Accept header
                headers = {}
                if provider.lower() == "github":
                    headers["Accept"] = "application/json"

                response = await client.post(token_url, data=data, headers=headers)

                logger.info(f"Token exchange response from {provider}: status={response.status_code}")

                if response.status_code == 200:
                    tokens = response.json()
                    logger.info(
                        f"Successfully obtained tokens from {provider}: has_access_token={bool(tokens.get('access_token'))}, has_id_token={bool(tokens.get('id_token'))}"
                    )
                    return tokens
                else:
                    logger.error(f"Token exchange failed for {provider}: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Error exchanging code with {provider}: {e}")
            return None

    async def _get_user_info_from_provider(
        self,
        provider: str,
        access_token: str,
        id_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get user information from OAuth provider."""
        # Try to decode ID token first if available
        if id_token:
            try:
                import base64
                import json

                # Decode JWT payload
                parts = id_token.split(".")
                if len(parts) >= 2:
                    payload = parts[1]
                    payload += "=" * (4 - len(payload) % 4)
                    claims = json.loads(base64.urlsafe_b64decode(payload))

                    return {
                        "external_id": claims.get("sub") or claims.get("oid"),
                        "email": claims.get("email") or claims.get("preferred_username"),
                        "name": claims.get("name"),
                        "email_verified": claims.get("email_verified", True),
                        "is_new_user": False,  # Will be determined later
                    }
            except Exception as e:
                logger.warning(f"Failed to decode ID token: {e}")

        # Fetch from provider API
        user_info_endpoints = {
            "google": "https://www.googleapis.com/oauth2/v2/userinfo",
            "microsoft": "https://graph.microsoft.com/v1.0/me",
            "github": "https://api.github.com/user",
            "linkedin": "https://api.linkedin.com/v2/me",
        }

        endpoint = user_info_endpoints.get(provider.lower())
        if not endpoint:
            raise ClientException(f"Unknown provider: {provider}")

        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {access_token}"}
                logger.info(f"Fetching user info from {provider} at {endpoint}")
                response = await client.get(endpoint, headers=headers)

                logger.info(f"User info response from {provider}: status={response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"User info data from {provider}: {data}")

                    # Parse based on provider
                    if provider.lower() == "google":
                        return {
                            "external_id": data.get("id"),
                            "email": data.get("email"),
                            "name": data.get("name"),
                            "email_verified": data.get("verified_email", True),
                        }
                    elif provider.lower() == "microsoft":
                        return {
                            "external_id": data.get("id"),
                            "email": data.get("mail") or data.get("userPrincipalName"),
                            "name": data.get("displayName"),
                            "email_verified": True,
                        }
                    elif provider.lower() == "github":
                        # Get email separately if needed
                        email = data.get("email")
                        if not email:
                            email_response = await client.get("https://api.github.com/user/emails", headers=headers)
                            if email_response.status_code == 200:
                                emails = email_response.json()
                                for e in emails:
                                    if e.get("primary"):
                                        email = e.get("email")
                                        break

                        return {
                            "external_id": str(data.get("id")),
                            "email": email,
                            "name": data.get("name") or data.get("login"),
                            "email_verified": True,
                        }
                    elif provider.lower() == "linkedin":
                        # LinkedIn needs separate email call
                        return {
                            "external_id": data.get("id"),
                            "email": None,  # Need separate API call
                            "name": f"{data.get('localizedFirstName', '')} {data.get('localizedLastName', '')}".strip(),
                            "email_verified": True,
                        }
                    else:
                        # Generic fallback for any provider
                        return {
                            "external_id": str(data.get("id", "")),
                            "email": data.get("email", ""),
                            "name": data.get("name", ""),
                            "email_verified": True,
                        }
                else:
                    error_body = response.text
                    logger.error(
                        f"Failed to get user info from {provider}: HTTP {response.status_code}, Body: {error_body}"
                    )
                    raise ClientException(
                        f"Failed to get user information from {provider}: HTTP {response.status_code}"
                    )

        except ClientException:
            raise
        except Exception as e:
            logger.error(f"Error fetching user info from {provider}: {e}")
            raise ClientException(f"Failed to get user information from {provider}: {str(e)}")

    async def _process_user(
        self,
        provider: str,
        user_info: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> User:
        """Process user - create new or update existing."""
        from budapp.auth.oauth_schemas import OAuthUserInfo
        from budapp.auth.oauth_services import OAuthService

        # Validate user_info
        if not user_info:
            raise ClientException("No user information received from OAuth provider")

        # Ensure required fields are present
        if not user_info.get("external_id"):
            raise ClientException("No external ID received from OAuth provider")
        if not user_info.get("email"):
            raise ClientException("No email address received from OAuth provider")

        # Convert to OAuthUserInfo object
        oauth_user_info = OAuthUserInfo(
            provider=provider,
            external_id=user_info["external_id"],
            email=user_info["email"],
            name=user_info.get("name") or user_info["email"].split("@")[0],
            email_verified=user_info.get("email_verified", True),
            provider_data=user_info,
        )

        # Get tenant
        if tenant_id:
            from uuid import UUID

            tenant = await UserDataManager(self.session).retrieve_by_fields(
                Tenant, {"id": UUID(tenant_id)}, missing_ok=True
            )
        else:
            # Get default tenant
            tenant = await UserDataManager(self.session).retrieve_by_fields(
                Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
            )

        if not tenant:
            raise ClientException("No valid tenant found for user creation")

        # Use existing OAuth service logic for user processing
        oauth_service = OAuthService(self.session)

        # Check if user exists
        existing_user = await oauth_service._find_existing_user(oauth_user_info)

        if existing_user:
            # Update existing user
            await oauth_service._update_user_oauth_provider(existing_user, oauth_user_info)
            user_info["is_new_user"] = False
            return existing_user
        else:
            # Create new user
            user_info["is_new_user"] = True
            return await oauth_service._create_user_from_oauth(oauth_user_info, tenant)


# Router for internal OAuth proxy
internal_oauth_router = APIRouter(prefix="/oauth/internal", tags=["oauth-internal"])


@internal_oauth_router.get(
    "/authorize/{provider}",
    responses={
        status.HTTP_302_FOUND: {
            "description": "Redirect to OAuth provider",
        },
    },
    description="Initiate OAuth flow by redirecting to provider directly",
)
async def initiate_oauth(
    request: Request,
    provider: str,
    session: Annotated[Session, Depends(get_session)],
    redirect_uri: Optional[str] = Query(None, description="Where to redirect after auth"),
    tenant_id: Optional[UUID] = Query(None, description="Tenant ID"),
) -> RedirectResponse:
    """Initiate OAuth flow without exposing Keycloak.

    This endpoint redirects directly to the OAuth provider (Google, Microsoft, etc.)
    without going through Keycloak, keeping Keycloak completely internal.
    """
    try:
        logger.info(f"Initiating OAuth flow for provider: {provider} (type: {type(provider)})")
        proxy = InternalOAuthProxy(session)

        # Get authorization URL from provider
        auth_url = await proxy.initiate_oauth(
            provider=provider,
            tenant_id=tenant_id,
            redirect_uri=redirect_uri,
            app_redirect_uri=f"{get_oauth_base_url(request)}/oauth/internal/callback",
        )

        logger.info(f"Redirecting to {provider} for authentication")
        return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)

    except ClientException as ce:
        logger.error(f"Client error in OAuth: {ce}")
        error_params = urlencode({"error": "configuration_error", "error_description": str(ce)})
        error_url = f"{get_oauth_base_url(request)}/auth/error?{error_params}"
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)
    except Exception as e:
        logger.exception(f"Failed to initiate OAuth for provider {provider} with error: {e}")
        error_params = urlencode({"error": "initialization_failed", "error_description": str(e)})
        error_url = f"{get_oauth_base_url(request)}/auth/error?{error_params}"
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)


@internal_oauth_router.get(
    "/callback",
    responses={
        status.HTTP_302_FOUND: {
            "description": "Redirect to frontend with exchange token",
        },
    },
    description="Handle OAuth callback from provider",
)
async def handle_oauth_callback(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    code: Optional[str] = Query(None, description="Authorization code"),
    state: str = Query(..., description="State parameter"),
    error: Optional[str] = Query(None, description="Error from provider"),
    error_description: Optional[str] = Query(None, description="Error details"),
) -> RedirectResponse:
    """Handle OAuth callback from provider.

    This endpoint receives the OAuth callback directly from the provider,
    processes it internally with Keycloak if needed, and returns tokens.
    """
    try:
        proxy = InternalOAuthProxy(session)

        # Process callback
        result = await proxy.handle_callback(
            code=code,
            state=state,
            error=error,
            error_description=error_description,
        )

        # Build redirect URL with exchange token
        redirect_uri = result.get("redirect_uri") or f"{get_oauth_base_url(request)}/auth/success"

        params = {
            "exchange_token": result["exchange_token"],
            "email": result["user"]["email"],
            "is_new_user": str(result["user"]["is_new_user"]).lower(),
        }

        redirect_url = f"{redirect_uri}?{urlencode(params)}"
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)

    except OAuthError as e:
        logger.error(f"OAuth error: {e.code} - {e.message}")
        error_params = {
            "error": e.code.value if hasattr(e.code, "value") else str(e.code),
            "error_description": e.message,
        }
        error_url = f"{str(request.base_url).rstrip('/')}/auth/error?{urlencode(error_params)}"
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)

    except Exception as e:
        logger.exception(f"Unexpected error in OAuth callback: {e}")
        error_params = {
            "error": "internal_error",
            "error_description": "An unexpected error occurred",
        }
        error_url = f"{str(request.base_url).rstrip('/')}/auth/error?{urlencode(error_params)}"
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)
