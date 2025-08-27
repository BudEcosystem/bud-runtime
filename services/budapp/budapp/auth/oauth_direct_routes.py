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

"""Direct OAuth routes that immediately redirect to provider."""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.auth.oauth_error_handler import OAuthError, OAuthErrorCode, get_user_friendly_message
from budapp.auth.oauth_proxy_services import ProxiedOAuthURLGenerator
from budapp.auth.oauth_services import OAuthService
from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.constants import OAuthProviderEnum
from budapp.commons.dependencies import get_session
from budapp.commons.exceptions import ClientException
from budapp.commons.keycloak import KeycloakManager
from budapp.commons.schemas import ErrorResponse
from budapp.user_ops.crud import UserDataManager
from budapp.user_ops.models import Tenant
from budapp.user_ops.oauth_models import OAuthSession, TenantOAuthConfig


logger = logging.get_logger(__name__)

oauth_direct_router = APIRouter(prefix="/auth/sso", tags=["sso"])


@oauth_direct_router.get(
    "/login/{provider}",
    responses={
        status.HTTP_302_FOUND: {
            "description": "Redirect to OAuth provider for authentication",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid provider or configuration error",
        },
    },
    description="Direct SSO login that immediately redirects to OAuth provider",
)
async def direct_sso_login(
    request: Request,
    provider: str,
    session: Annotated[Session, Depends(get_session)],
    tenant_id: Optional[UUID] = Query(None, description="Tenant ID (optional)"),
    redirect_uri: Optional[str] = Query(None, description="Frontend callback URL after authentication"),
    error_redirect: Optional[str] = Query(None, description="URL to redirect on error"),
) -> RedirectResponse:
    """Direct SSO login endpoint that immediately redirects to the OAuth provider.

    This combines the login initiation and redirect steps into one, simplifying
    the frontend implementation. The frontend just needs to redirect to this URL.

    Args:
        provider: OAuth provider name (github, google, azure, etc.)
        session: Database session
        tenant_id: Optional tenant ID
        redirect_uri: Optional frontend URL to return to after auth
        error_redirect: Optional URL to redirect to on error

    Returns:
        RedirectResponse to the OAuth provider login page
    """
    try:
        # Validate provider enum
        try:
            provider_enum = OAuthProviderEnum(provider.lower())
        except ValueError:
            error_msg = f"Invalid provider: {provider}"
            logger.error(error_msg)
            if error_redirect:
                return RedirectResponse(
                    url=f"{error_redirect}?error=invalid_provider&error_description={error_msg}",
                    status_code=status.HTTP_302_FOUND,
                )
            raise ClientException(error_msg)

        # Get tenant
        if tenant_id:
            tenant = await UserDataManager(session).retrieve_by_fields(Tenant, {"id": tenant_id}, missing_ok=True)
            if not tenant:
                error_msg = "Invalid tenant ID"
                if error_redirect:
                    return RedirectResponse(
                        url=f"{error_redirect}?error=invalid_tenant&error_description={error_msg}",
                        status_code=status.HTTP_302_FOUND,
                    )
                raise ClientException(error_msg)
        else:
            # Get default tenant
            tenant = await UserDataManager(session).retrieve_by_fields(
                Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
            )
            if not tenant:
                error_msg = "Default tenant not found"
                if error_redirect:
                    return RedirectResponse(
                        url=f"{error_redirect}?error=tenant_not_found&error_description={error_msg}",
                        status_code=status.HTTP_302_FOUND,
                    )
                raise ClientException(error_msg)

        # Check if provider is enabled for tenant
        oauth_config = await UserDataManager(session).retrieve_by_fields(
            TenantOAuthConfig, {"tenant_id": tenant.id, "provider": provider_enum.value}, missing_ok=True
        )

        if not oauth_config or not oauth_config.enabled:
            error_msg = f"OAuth provider '{provider}' is not configured for this tenant"
            if error_redirect:
                return RedirectResponse(
                    url=f"{error_redirect}?error=provider_not_configured&error_description={error_msg}",
                    status_code=status.HTTP_302_FOUND,
                )
            raise OAuthError(
                code=OAuthErrorCode.PROVIDER_NOT_CONFIGURED,
                message=get_user_friendly_message(OAuthErrorCode.PROVIDER_NOT_CONFIGURED, provider),
                provider=provider,
            )

        # Generate PKCE parameters (for additional security)
        code_verifier = secrets.token_urlsafe(32)
        state = secrets.token_urlsafe(32)

        # Determine callback URL - use secure callback for exchange tokens
        base_url = str(request.base_url).rstrip("/")
        # Use secure callback that returns exchange tokens instead of JWT in URL
        callback_url = f"{base_url}/oauth/secure-callback"

        # Store the frontend redirect URI in session for later use
        session_data = {
            "frontend_redirect": redirect_uri or f"{base_url}/auth/success",
            "error_redirect": error_redirect or f"{base_url}/auth/error",
        }

        # Create OAuth session in database
        oauth_session = OAuthSession(
            provider=provider_enum.value,
            state=state,
            code_verifier=code_verifier,
            redirect_uri=callback_url,
            tenant_id=tenant.id,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            completed=False,
            session_metadata=session_data,  # Store frontend URLs in session_metadata
        )

        UserDataManager(session).add_one(oauth_session)
        session.commit()

        # Get Keycloak manager
        keycloak_manager = KeycloakManager()

        # Determine if we should use proxy or direct Keycloak URL
        use_proxy = app_settings.oauth_use_proxy if hasattr(app_settings, "oauth_use_proxy") else True

        if use_proxy:
            # Use proxied URL
            auth_url = ProxiedOAuthURLGenerator.get_proxied_authorization_url(
                base_url=base_url,
                realm_name=tenant.realm_name,
                provider=provider_enum.value,
                redirect_uri=callback_url,
                state=state,
            )
        else:
            # Use direct Keycloak URL
            auth_url = keycloak_manager.get_broker_login_url(
                realm_name=tenant.realm_name,
                provider=provider_enum.value,
                redirect_uri=callback_url,
                state=state,
            )

        logger.info(f"Redirecting user to OAuth provider '{provider}' for tenant '{tenant.id}'")

        # Redirect directly to the OAuth provider
        return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)

    except OAuthError as e:
        logger.error(f"OAuth error during direct login: {e}")
        if error_redirect:
            return RedirectResponse(
                url=f"{error_redirect}?error={e.code.value}&error_description={e.message}",
                status_code=status.HTTP_302_FOUND,
            )
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during direct SSO login: {e}")
        if error_redirect:
            return RedirectResponse(
                url=f"{error_redirect}?error=internal_error&error_description=An unexpected error occurred",
                status_code=status.HTTP_302_FOUND,
            )
        raise ClientException("Failed to initiate SSO login")


@oauth_direct_router.get(
    "/providers",
    responses={
        status.HTTP_200_OK: {
            "description": "List of available SSO providers with direct login URLs",
        },
    },
    description="Get available SSO providers with direct login URLs",
)
async def get_sso_providers(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    tenant_id: Optional[UUID] = Query(None, description="Tenant ID (optional)"),
):
    """Get available SSO providers with direct login URLs.

    This endpoint returns all configured OAuth providers for the tenant
    along with ready-to-use login URLs that the frontend can use for
    direct redirects or login buttons.

    Returns:
        List of providers with their configuration and login URLs
    """
    try:
        # Get tenant
        if tenant_id:
            tenant = await UserDataManager(session).retrieve_by_fields(Tenant, {"id": tenant_id}, missing_ok=True)
            if not tenant:
                raise ClientException("Invalid tenant ID")
        else:
            tenant = await UserDataManager(session).retrieve_by_fields(
                Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
            )
            if not tenant:
                raise ClientException("Default tenant not found")

        # Get all OAuth configs for tenant
        oauth_configs = await UserDataManager(session).get_all_by_fields(
            TenantOAuthConfig, {"tenant_id": tenant.id, "enabled": True}
        )

        base_url = str(request.base_url).rstrip("/")
        providers = []

        for config in oauth_configs:
            # Get provider display information
            provider_info = {
                "github": {
                    "displayName": "GitHub",
                    "iconUrl": "https://github.githubassets.com/favicons/favicon.svg",
                    "buttonClass": "github",
                },
                "google": {
                    "displayName": "Google",
                    "iconUrl": "https://www.google.com/favicon.ico",
                    "buttonClass": "google",
                },
                "azure": {
                    "displayName": "Microsoft",
                    "iconUrl": "https://www.microsoft.com/favicon.ico",
                    "buttonClass": "microsoft",
                },
                "gitlab": {
                    "displayName": "GitLab",
                    "iconUrl": "https://gitlab.com/assets/favicon-7901bd695fb93edb07975966062049829afb56cf11511236e61bcf425070e36e.png",
                    "buttonClass": "gitlab",
                },
            }.get(config.provider, {"displayName": config.provider.title(), "iconUrl": None, "buttonClass": "default"})

            # Build direct login URL
            login_url = f"{base_url}/auth/sso/login/{config.provider}"
            if tenant_id:
                login_url += f"?tenant_id={tenant_id}"

            providers.append(
                {
                    "provider": config.provider,
                    "enabled": config.enabled,
                    "displayName": provider_info["displayName"],
                    "iconUrl": provider_info["iconUrl"],
                    "buttonClass": provider_info["buttonClass"],
                    "loginUrl": login_url,  # Direct login URL
                    "allowedDomains": config.allowed_domains,
                    "autoCreateUsers": config.auto_create_users,
                }
            )

        return {"success": True, "result": providers, "message": "SSO providers retrieved successfully"}

    except Exception as e:
        logger.exception(f"Error fetching SSO providers: {e}")
        raise ClientException("Failed to fetch SSO providers")
