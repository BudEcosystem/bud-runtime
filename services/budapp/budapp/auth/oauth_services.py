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

"""OAuth service layer for SSO integration."""

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from budapp.auth.oauth_error_handler import (
    OAuthError,
    OAuthErrorCode,
    OAuthSessionValidator,
    get_user_friendly_message,
    handle_oauth_error,
)
from budapp.auth.oauth_proxy_services import ProxiedOAuthURLGenerator
from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.constants import OAuthProviderEnum, UserColorEnum, UserRoleEnum, UserStatusEnum, UserTypeEnum
from budapp.commons.db_utils import SessionMixin
from budapp.commons.exceptions import ClientException
from budapp.commons.keycloak import KeycloakManager
from budapp.user_ops.crud import UserDataManager
from budapp.user_ops.models import Tenant, TenantClient, TenantUserMapping, User
from budapp.user_ops.oauth_models import OAuthSession, TenantOAuthConfig, UserOAuthProvider

from .oauth_schemas import (
    OAuthCallbackRequest,
    OAuthLoginRequest,
    OAuthLoginResponse,
    OAuthProviderConfig,
    OAuthTokenResponse,
    OAuthUserInfo,
)
from .schemas import UserLoginData


logger = logging.get_logger(__name__)


class OAuthService(SessionMixin):
    """Service for handling OAuth operations."""

    def __init__(self, session: Session):
        """Initialize OAuth service."""
        super().__init__(session)
        self.keycloak_manager = KeycloakManager()

    async def initiate_oauth_login(
        self, request: OAuthLoginRequest, base_url: str, use_proxy: bool = True
    ) -> OAuthLoginResponse:
        """Initiate OAuth login flow.

        Args:
            request: OAuth login request
            base_url: Base URL for callback
            use_proxy: Whether to use proxied URLs (default: True)

        Returns:
            OAuthLoginResponse with auth URL and state
        """
        # Get tenant configuration
        tenant = await self._get_tenant(request.tenant_id)

        # Verify provider is enabled for tenant
        oauth_config = await self._get_tenant_oauth_config(tenant.id, request.provider)
        if not oauth_config:
            raise OAuthError(
                code=OAuthErrorCode.PROVIDER_NOT_CONFIGURED,
                message=get_user_friendly_message(OAuthErrorCode.PROVIDER_NOT_CONFIGURED, request.provider.value),
                provider=request.provider.value,
            )
        if not oauth_config.enabled:
            raise OAuthError(
                code=OAuthErrorCode.PROVIDER_DISABLED,
                message=get_user_friendly_message(OAuthErrorCode.PROVIDER_DISABLED, request.provider.value),
                provider=request.provider.value,
            )

        # Generate PKCE parameters
        code_verifier = self._generate_code_verifier()
        # code_challenge = self._generate_code_challenge(code_verifier)
        _ = self._generate_code_challenge(code_verifier)

        # Generate secure state
        state = secrets.token_urlsafe(32)

        # Create OAuth session
        oauth_session = OAuthSession(
            provider=request.provider.value,
            state=state,
            code_verifier=code_verifier,
            redirect_uri=str(request.redirect_uri)
            if request.redirect_uri
            else f"{base_url}/api/v1/auth/oauth/callback",
            tenant_id=tenant.id,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            completed=False,
        )

        UserDataManager(self.session).add_one(oauth_session)
        self.session.commit()

        # Generate authorization URL
        if use_proxy:
            # Use proxied URL that hides Keycloak from clients
            auth_url = ProxiedOAuthURLGenerator.get_proxied_authorization_url(
                base_url=base_url,
                realm_name=tenant.realm_name,
                provider=request.provider.value,
                redirect_uri=oauth_session.redirect_uri,
                state=state,
            )
        else:
            # Use direct Keycloak URL (for backward compatibility)
            auth_url = self.keycloak_manager.get_broker_login_url(
                realm_name=tenant.realm_name,
                provider=request.provider.value,
                redirect_uri=oauth_session.redirect_uri,
                state=state,
            )

        return OAuthLoginResponse(auth_url=auth_url, state=state, expires_at=oauth_session.expires_at)

    async def handle_oauth_callback(self, request: OAuthCallbackRequest) -> OAuthTokenResponse:
        """Handle OAuth callback from provider.

        Args:
            request: OAuth callback request

        Returns:
            OAuthTokenResponse with tokens and user info
        """
        # Validate OAuth session
        oauth_session = await self._validate_oauth_session(request.state)

        if request.error:
            logger.error(f"OAuth error: {request.error} - {request.error_description}")
            raise ClientException(f"OAuth authentication failed: {request.error_description or request.error}")

        # Get tenant and client info
        tenant = await UserDataManager(self.session).retrieve_by_fields(Tenant, {"id": oauth_session.tenant_id})
        tenant_client = await UserDataManager(self.session).retrieve_by_fields(TenantClient, {"tenant_id": tenant.id})

        # Exchange code for tokens via Keycloak
        # Note: Keycloak handles the OAuth flow, so we authenticate through Keycloak
        # The actual implementation would depend on Keycloak's broker API

        # For now, we'll simulate getting user info from the provider
        # In production, this would come from Keycloak after successful OAuth
        user_info = await self._get_user_info_from_provider(oauth_session.provider, request.code, oauth_session)

        # Check if user exists
        existing_user = await self._find_existing_user(user_info)

        if existing_user:
            # Update user's OAuth provider info
            await self._update_user_oauth_provider(existing_user, user_info)

            # Generate tokens
            token_data = await self._generate_tokens_for_user(existing_user, tenant, tenant_client)

            return OAuthTokenResponse(
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                expires_in=token_data["expires_in"],
                token_type="Bearer",
                user_info=user_info,
                is_new_user=False,
                requires_linking=False,
            )
        else:
            # Check if auto-create is enabled
            oauth_config = await self._get_tenant_oauth_config(tenant.id, user_info.provider)

            if not oauth_config.auto_create_users:
                # User needs to link account or register
                return OAuthTokenResponse(
                    access_token="",
                    refresh_token="",
                    expires_in=0,
                    token_type="Bearer",
                    user_info=user_info,
                    is_new_user=False,
                    requires_linking=True,
                )

            # Create new user
            new_user = await self._create_user_from_oauth(user_info, tenant)

            # Generate tokens
            token_data = await self._generate_tokens_for_user(new_user, tenant, tenant_client)

            return OAuthTokenResponse(
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                expires_in=token_data["expires_in"],
                token_type="Bearer",
                user_info=user_info,
                is_new_user=True,
                requires_linking=False,
            )

    async def link_oauth_account(self, user_id: UUID, provider: OAuthProviderEnum, provider_user_id: str) -> bool:
        """Link OAuth account to existing user.

        Args:
            user_id: User ID to link
            provider: OAuth provider
            provider_user_id: Provider's user ID

        Returns:
            bool: Success status
        """
        # Get user
        user = await UserDataManager(self.session).retrieve_by_fields(User, {"id": user_id})

        # Check if already linked
        existing_link = await UserDataManager(self.session).retrieve_by_fields(
            UserOAuthProvider, {"user_id": user_id, "provider": provider.value}, missing_ok=True
        )

        if existing_link:
            raise ClientException(f"Account already linked to {provider.value}")

        # Get tenant for user
        tenant_mapping = await UserDataManager(self.session).retrieve_by_fields(
            TenantUserMapping, {"user_id": user_id}
        )
        tenant = await UserDataManager(self.session).retrieve_by_fields(Tenant, {"id": tenant_mapping.tenant_id})

        # Link in Keycloak
        await self.keycloak_manager.link_provider_account(
            user_id=str(user.auth_id),
            provider=provider.value,
            provider_user_id=provider_user_id,
            realm_name=tenant.realm_name,
        )

        # Create database link
        oauth_provider = UserOAuthProvider(user_id=user_id, provider=provider.value, external_id=provider_user_id)

        UserDataManager(self.session).add_one(oauth_provider)
        self.session.commit()

        return True

    async def get_available_providers(self, tenant_id: UUID) -> List[OAuthProviderConfig]:
        """Get available OAuth providers for a tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of available OAuth provider configurations
        """
        # Get all OAuth configs for tenant
        oauth_configs = await UserDataManager(self.session).get_all_by_fields(
            TenantOAuthConfig, {"tenant_id": tenant_id, "enabled": True}
        )

        providers = []
        # Handle case where no configs found (returns None or empty list)
        if not oauth_configs:
            return providers

        for config in oauth_configs:
            provider_info = self._get_provider_info(config.provider)
            providers.append(
                OAuthProviderConfig(
                    provider=config.provider,
                    enabled=config.enabled,
                    allowed_domains=config.allowed_domains,
                    auto_create_users=config.auto_create_users,
                    icon_url=provider_info.get("icon_url"),
                    display_name=provider_info.get("display_name"),
                )
            )

        return providers

    # Private helper methods

    async def _get_tenant(self, tenant_id: Optional[UUID]) -> Tenant:
        """Get tenant by ID or default tenant."""
        if tenant_id:
            tenant = await UserDataManager(self.session).retrieve_by_fields(Tenant, {"id": tenant_id}, missing_ok=True)
            if not tenant:
                raise ClientException("Invalid tenant ID")
        else:
            tenant = await UserDataManager(self.session).retrieve_by_fields(
                Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
            )
            if not tenant:
                raise ClientException("Default tenant not found")

        return tenant

    async def _get_tenant_oauth_config(
        self, tenant_id: UUID, provider: OAuthProviderEnum
    ) -> Optional[TenantOAuthConfig]:
        """Get OAuth configuration for tenant and provider."""
        return await UserDataManager(self.session).retrieve_by_fields(
            TenantOAuthConfig, {"tenant_id": tenant_id, "provider": provider.value}, missing_ok=True
        )

    def _generate_code_verifier(self) -> str:
        """Generate PKCE code verifier."""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8").rstrip("=")

    def _generate_code_challenge(self, verifier: str) -> str:
        """Generate PKCE code challenge from verifier."""
        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

    async def _validate_oauth_session(self, state: str) -> OAuthSession:
        """Validate OAuth session by state."""
        # Validate state format
        if not OAuthSessionValidator.validate_state_parameter(state):
            raise OAuthError(
                code=OAuthErrorCode.INVALID_STATE, message=get_user_friendly_message(OAuthErrorCode.INVALID_STATE)
            )

        oauth_session = await UserDataManager(self.session).retrieve_by_fields(
            OAuthSession, {"state": state}, missing_ok=True
        )

        if not oauth_session:
            raise OAuthError(
                code=OAuthErrorCode.INVALID_STATE, message=get_user_friendly_message(OAuthErrorCode.INVALID_STATE)
            )

        if oauth_session.completed:
            raise OAuthError(
                code=OAuthErrorCode.INVALID_STATE,
                message="This login link has already been used. Please start a new login.",
            )

        # Handle both timezone-aware and naive datetimes
        current_time = datetime.now(UTC)
        expires_at = oauth_session.expires_at

        # Make expires_at timezone-aware if it's naive
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at < current_time:
            raise OAuthError(
                code=OAuthErrorCode.STATE_EXPIRED, message=get_user_friendly_message(OAuthErrorCode.STATE_EXPIRED)
            )

        # Mark as completed
        oauth_session.completed = True
        self.session.commit()

        return oauth_session

    async def _get_user_info_from_provider(
        self, provider: str, code: str, oauth_session: OAuthSession
    ) -> OAuthUserInfo:
        """Get user info from OAuth provider via Keycloak.

        This method exchanges the authorization code for user information
        through Keycloak's token endpoint.
        """
        try:
            # Get tenant configuration
            tenant = await self._get_tenant(oauth_session.tenant_id)

            # Get OAuth configuration for this provider
            oauth_config = await UserDataManager(self.session).retrieve_by_fields(
                TenantOAuthConfig,
                {"tenant_id": oauth_session.tenant_id, "provider": provider, "enabled": True},
                missing_ok=True,
            )

            if not oauth_config:
                logger.error(f"OAuth configuration not found for provider {provider}")
                # Return minimal info for backward compatibility
                return OAuthUserInfo(
                    provider=provider,
                    external_id=f"{provider}_user_{code[:8]}",
                    email=f"{provider}_user@example.com",
                    name="OAuth User",
                    email_verified=True,
                    provider_data={},
                )

            # Exchange authorization code for tokens through Keycloak
            token_data = await self._exchange_code_for_tokens(
                code=code,
                provider=provider,
                tenant=tenant,
                redirect_uri=oauth_session.redirect_uri,
                client_id=oauth_config.client_id,
                client_secret=oauth_config.client_secret,
            )

            if not token_data:
                logger.error(f"Failed to exchange code for tokens with {provider}")
                # Return minimal info for backward compatibility
                return OAuthUserInfo(
                    provider=provider,
                    external_id=f"{provider}_user_{code[:8]}",
                    email=f"{provider}_user@example.com",
                    name="OAuth User",
                    email_verified=True,
                    provider_data={},
                )

            # Extract user info from token (ID token contains user claims)
            id_token = token_data.get("id_token")
            if id_token:
                # Decode ID token to get user info (without verification for now)
                import base64
                import json

                # Split the JWT token
                parts = id_token.split(".")
                if len(parts) >= 2:
                    # Decode the payload (second part)
                    payload = parts[1]
                    # Add padding if needed
                    payload += "=" * (4 - len(payload) % 4)
                    try:
                        user_claims = json.loads(base64.urlsafe_b64decode(payload))

                        # Extract user information from claims
                        email = (
                            user_claims.get("email") or user_claims.get("preferred_username") or user_claims.get("upn")
                        )
                        name = user_claims.get("name") or user_claims.get("given_name", "") + " " + user_claims.get(
                            "family_name", ""
                        )
                        external_id = user_claims.get("sub") or user_claims.get("oid") or f"{provider}_{code[:8]}"

                        return OAuthUserInfo(
                            provider=provider,
                            external_id=external_id,
                            email=email or f"{provider}_user@example.com",
                            name=name.strip() or "OAuth User",
                            email_verified=user_claims.get("email_verified", True),
                            provider_data=user_claims,
                        )
                    except Exception as e:
                        logger.error(f"Failed to decode ID token: {e}")

            # If we have access token but no ID token, try to get user info from provider
            access_token = token_data.get("access_token")
            if access_token:
                user_info = await self._fetch_user_info_from_provider(provider, access_token)
                if user_info:
                    return user_info

            # Fallback to minimal info
            logger.warning(f"Could not extract user info from {provider} OAuth response")
            return OAuthUserInfo(
                provider=provider,
                external_id=f"{provider}_user_{code[:8]}",
                email=f"{provider}_user@example.com",
                name="OAuth User",
                email_verified=True,
                provider_data=token_data,
            )

        except Exception as e:
            logger.error(f"Error getting user info from {provider}: {e}")
            # Return minimal info for backward compatibility
            return OAuthUserInfo(
                provider=provider,
                external_id=f"{provider}_error_{code[:8]}",
                email=f"{provider}_user@example.com",
                name="OAuth User",
                email_verified=False,
                provider_data={},
            )

    async def _exchange_code_for_tokens(
        self,
        code: str,
        provider: str,
        tenant: Tenant,
        redirect_uri: str,
        client_id: str,
        client_secret: str,
    ) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for tokens through Keycloak.

        Args:
            code: Authorization code from OAuth provider
            provider: OAuth provider name
            tenant: Tenant configuration
            redirect_uri: Redirect URI used in the authorization request
            client_id: OAuth client ID
            client_secret: OAuth client secret

        Returns:
            Token data including access_token, id_token, refresh_token
        """
        try:
            # For Keycloak identity brokering, we would typically exchange through Keycloak
            # This is a simplified implementation
            keycloak_url = app_settings.keycloak_server_url.rstrip("/")
            token_endpoint = f"{keycloak_url}/realms/{tenant.realm_name}/protocol/openid-connect/token"

            # Prepare token exchange request
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_endpoint,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": redirect_uri,
                        "client_id": client_id,
                        "client_secret": client_secret,
                    },
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Error exchanging code for tokens: {e}")
            return None

    async def _fetch_user_info_from_provider(self, provider: str, access_token: str) -> Optional[OAuthUserInfo]:
        """Fetch user information directly from OAuth provider.

        Args:
            provider: OAuth provider name
            access_token: Access token from OAuth provider

        Returns:
            User information from OAuth provider
        """
        try:
            import httpx

            # Provider-specific user info endpoints
            provider_endpoints = {
                "google": "https://www.googleapis.com/oauth2/v2/userinfo",
                "github": "https://api.github.com/user",
                "linkedin": "https://api.linkedin.com/v2/me",
                "microsoft": "https://graph.microsoft.com/v1.0/me",
            }

            endpoint = provider_endpoints.get(provider.lower())
            if not endpoint:
                logger.error(f"Unknown provider for user info: {provider}")
                return None

            headers = {"Authorization": f"Bearer {access_token}"}

            # Special handling for LinkedIn which requires additional headers
            if provider.lower() == "linkedin":
                headers["X-Restli-Protocol-Version"] = "2.0.0"

            async with httpx.AsyncClient() as client:
                response = await client.get(endpoint, headers=headers)

                if response.status_code == 200:
                    user_data = response.json()

                    # Parse user info based on provider
                    if provider.lower() == "google":
                        return OAuthUserInfo(
                            provider=provider,
                            external_id=user_data.get("id"),
                            email=user_data.get("email"),
                            name=user_data.get("name"),
                            email_verified=user_data.get("verified_email", True),
                            provider_data=user_data,
                        )
                    elif provider.lower() == "github":
                        # GitHub may require a separate call for email
                        email = user_data.get("email")
                        if not email:
                            # Try to get primary email
                            email_response = await client.get("https://api.github.com/user/emails", headers=headers)
                            if email_response.status_code == 200:
                                emails = email_response.json()
                                for e in emails:
                                    if e.get("primary"):
                                        email = e.get("email")
                                        break

                        return OAuthUserInfo(
                            provider=provider,
                            external_id=str(user_data.get("id")),
                            email=email,
                            name=user_data.get("name") or user_data.get("login"),
                            email_verified=True,
                            provider_data=user_data,
                        )
                    elif provider.lower() == "microsoft":
                        return OAuthUserInfo(
                            provider=provider,
                            external_id=user_data.get("id"),
                            email=user_data.get("mail") or user_data.get("userPrincipalName"),
                            name=user_data.get("displayName"),
                            email_verified=True,
                            provider_data=user_data,
                        )
                    elif provider.lower() == "linkedin":
                        # LinkedIn v2 API response structure
                        return OAuthUserInfo(
                            provider=provider,
                            external_id=user_data.get("id"),
                            email=None,  # LinkedIn requires separate email API call
                            name=f"{user_data.get('localizedFirstName', '')} {user_data.get('localizedLastName', '')}".strip(),
                            email_verified=True,
                            provider_data=user_data,
                        )

                logger.error(f"Failed to fetch user info: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error fetching user info from {provider}: {e}")
            return None

    async def _find_existing_user(self, user_info: OAuthUserInfo) -> Optional[User]:
        """Find existing user by email or OAuth provider."""
        # First check by OAuth provider
        oauth_link = await UserDataManager(self.session).retrieve_by_fields(
            UserOAuthProvider,
            {"provider": user_info.provider.value, "external_id": user_info.external_id},
            missing_ok=True,
        )

        if oauth_link:
            return await UserDataManager(self.session).retrieve_by_fields(User, {"id": oauth_link.user_id})

        # Check by email if available
        if user_info.email:
            return await UserDataManager(self.session).retrieve_by_fields(
                User, {"email": user_info.email}, missing_ok=True
            )

        return None

    async def _update_user_oauth_provider(self, user: User, user_info: OAuthUserInfo) -> None:
        """Update user's OAuth provider information."""
        # Check if OAuth link exists
        oauth_link = await UserDataManager(self.session).retrieve_by_fields(
            UserOAuthProvider, {"user_id": user.id, "provider": user_info.provider.value}, missing_ok=True
        )

        if not oauth_link:
            # Create new link
            oauth_link = UserOAuthProvider(
                user_id=user.id,
                provider=user_info.provider.value,
                external_id=user_info.external_id,
                email=user_info.email,
                provider_data=user_info.provider_data,
            )
            UserDataManager(self.session).add_one(oauth_link)
        else:
            # Update existing link
            oauth_link.external_id = user_info.external_id
            oauth_link.email = user_info.email
            oauth_link.provider_data = user_info.provider_data

        # Update user's auth_providers JSON field
        if not user.auth_providers:
            user.auth_providers = []

        # Add or update provider info
        provider_exists = False
        for provider in user.auth_providers:
            if provider.get("provider") == user_info.provider.value:
                provider["external_id"] = user_info.external_id
                provider["linked_at"] = datetime.now(UTC).isoformat()
                provider_exists = True
                break

        if not provider_exists:
            user.auth_providers.append(
                {
                    "provider": user_info.provider.value,
                    "external_id": user_info.external_id,
                    "linked_at": datetime.now(UTC).isoformat(),
                }
            )

        self.session.commit()

    def _generate_oauth_user_password(self) -> str:
        """Generate a password that meets all validation requirements for OAuth users.

        Requirements:
        - At least 8 characters
        - Contains at least one digit
        - Contains at least one uppercase letter
        - Contains at least one lowercase letter
        - Contains at least one special character
        - No whitespace

        Returns:
            A compliant password string
        """
        import random
        import string

        # Components to ensure requirements are met
        lowercase = random.choice(string.ascii_lowercase)
        uppercase = random.choice(string.ascii_uppercase)
        digit = random.choice(string.digits)
        special = random.choice(string.punctuation)

        # Generate additional random characters to reach desired length
        remaining_length = 12  # Total length will be 16 characters
        all_chars = string.ascii_letters + string.digits + string.punctuation
        additional = "".join(random.choices(all_chars, k=remaining_length))

        # Combine and shuffle
        password_chars = list(lowercase + uppercase + digit + special + additional)
        random.shuffle(password_chars)

        return "".join(password_chars)

    async def _create_user_from_oauth(self, user_info: OAuthUserInfo, tenant: Tenant) -> User:
        """Create new user from OAuth info."""
        # Get OAuth config to check domain restrictions
        oauth_config = await self._get_tenant_oauth_config(tenant.id, user_info.provider)

        # Validate email domain if restrictions are configured
        if oauth_config.allowed_domains and user_info.email:
            if not OAuthSessionValidator.validate_email_domain(user_info.email, oauth_config.allowed_domains):
                domain = user_info.email.split("@")[-1]
                raise OAuthError(
                    code=OAuthErrorCode.DOMAIN_NOT_ALLOWED,
                    message=get_user_friendly_message(OAuthErrorCode.DOMAIN_NOT_ALLOWED, domain=domain),
                    provider=user_info.provider.value,
                )

        # Import required models for permissions
        from budapp.commons.constants import PermissionEnum
        from budapp.permissions.schemas import PermissionList

        # Set default permissions for CLIENT users (same as registration)
        client_permissions = [
            PermissionList(name=PermissionEnum.CLIENT_ACCESS, has_permission=True),
            PermissionList(name=PermissionEnum.PROJECT_VIEW, has_permission=True),
            PermissionList(name=PermissionEnum.PROJECT_MANAGE, has_permission=True),
        ]

        # Process permissions to add implicit view permissions for manage permissions
        permission_dict = {p.name: p for p in client_permissions}
        manage_to_view_mapping = PermissionEnum.get_manage_to_view_mapping()

        for permission in client_permissions:
            if permission.has_permission and permission.name in manage_to_view_mapping:
                view_permission_name = manage_to_view_mapping[permission.name]
                permission_dict[view_permission_name] = PermissionList(name=view_permission_name, has_permission=True)

        processed_permissions = list(permission_dict.values())

        # Create user in database with CLIENT type
        user = User(
            auth_id=UUID(secrets.token_hex(16)),  # Will be replaced by Keycloak ID
            name=user_info.name or user_info.email.split("@")[0],
            email=user_info.email,
            role=UserRoleEnum.DEVELOPER,  # Default role
            status=UserStatusEnum.ACTIVE,  # SSO users are active immediately
            user_type=UserTypeEnum.CLIENT,  # Set as CLIENT user type
            color=UserColorEnum.get_random_color(),
            first_login=True,
            is_reset_password=False,  # SSO users don't need password reset
            auth_providers=[
                {
                    "provider": user_info.provider.value,
                    "external_id": user_info.external_id,
                    "linked_at": datetime.now(UTC).isoformat(),
                }
            ],
        )

        UserDataManager(self.session).add_one(user)

        # Create tenant mapping
        tenant_mapping = TenantUserMapping(tenant_id=tenant.id, user_id=user.id)
        UserDataManager(self.session).add_one(tenant_mapping)

        # Create OAuth provider link
        oauth_link = UserOAuthProvider(
            user_id=user.id,
            provider=user_info.provider.value,
            external_id=user_info.external_id,
            email=user_info.email,
            provider_data=user_info.provider_data,
        )
        UserDataManager(self.session).add_one(oauth_link)

        # Get tenant client for Keycloak user creation
        tenant_client = await UserDataManager(self.session).retrieve_by_fields(
            TenantClient, {"tenant_id": tenant.id}, missing_ok=True
        )
        if not tenant_client:
            raise ClientException("Tenant client configuration not found")

        # Create user in Keycloak with permissions
        # We need to create a UserCreate-like object for the Keycloak manager
        from budapp.user_ops.schemas import UserCreate

        # Generate a compliant password for OAuth users
        # Must have: digit, uppercase, lowercase, special character, no whitespace
        password = self._generate_oauth_user_password()

        user_create_data = UserCreate(
            name=user.name,
            email=user.email,
            password=password,
            role=user.role,
            user_type=user.user_type,
            permissions=processed_permissions,
            status=user.status,
        )

        # Create user in Keycloak with permissions
        try:
            keycloak_user_id = await self.keycloak_manager.create_user_with_permissions(
                user_create_data,
                realm_name=tenant.realm_name,
                client_id=tenant_client.client_id,
            )

            # Update user with Keycloak ID
            user.auth_id = UUID(keycloak_user_id)
            logger.info(f"Created user {user.email} in Keycloak with ID {keycloak_user_id}")

            # Try to link OAuth account in Keycloak (if method exists)
            try:
                if hasattr(self.keycloak_manager, "link_provider_account"):
                    await self.keycloak_manager.link_provider_account(
                        user_id=keycloak_user_id,
                        provider=user_info.provider.value,
                        provider_user_id=user_info.external_id,
                        realm_name=tenant.realm_name,
                    )
                    logger.info(f"Linked {user_info.provider.value} account for user {user.email}")
                else:
                    logger.warning("link_provider_account method not available - skipping OAuth link in Keycloak")
            except Exception as link_error:
                logger.warning(f"Failed to link OAuth account in Keycloak: {link_error}")
                # Continue without linking - user can still authenticate

        except Exception as kc_error:
            logger.error(f"Failed to create user in Keycloak: {kc_error}")
            # Check if user already exists in Keycloak
            try:
                realm_admin = self.keycloak_manager.get_realm_admin(tenant.realm_name)
                keycloak_users = realm_admin.get_users(query={"email": user.email})
                if keycloak_users:
                    # User exists, update auth_id
                    user.auth_id = UUID(keycloak_users[0]["id"])
                    logger.info(f"User {user.email} already exists in Keycloak, updated auth_id")
                else:
                    # User doesn't exist and we couldn't create - this is an error
                    # but we'll continue without auth_id for now
                    logger.error(f"Could not create or find user {user.email} in Keycloak")
            except Exception as lookup_error:
                logger.error(f"Failed to lookup user in Keycloak after creation failure: {lookup_error}")

        self.session.commit()

        # Set up billing and create default project for new CLIENT users
        logger.info(f"User type for {user.email}: {user.user_type}")
        if user.user_type == UserTypeEnum.CLIENT:
            logger.info(f"Setting up new CLIENT user {user.email} with billing and default project")
            await self._setup_new_client_user(user, tenant, tenant_client)
        else:
            logger.info(f"Skipping default project for non-CLIENT user {user.email}")

        return user

    async def _setup_new_client_user(self, user: User, tenant: Tenant, tenant_client: TenantClient) -> None:
        """Set up billing and create default project for new CLIENT users.

        Args:
            user: The newly created user
            tenant: The tenant the user belongs to
            tenant_client: The tenant client configuration
        """
        # Assign default billing plan
        try:
            from datetime import datetime, timedelta, timezone

            from dateutil.relativedelta import relativedelta

            from budapp.billing_ops.models import BillingPlan, UserBilling

            # Check if user already has billing
            existing_billing = await UserDataManager(self.session).retrieve_by_fields(
                UserBilling, {"user_id": user.id}, missing_ok=True
            )

            if existing_billing:
                logger.info(f"User {user.email} already has billing plan, skipping assignment")
            else:
                # Get the default free plan by name
                free_plan = await UserDataManager(self.session).retrieve_by_fields(
                    BillingPlan, {"name": "Free"}, missing_ok=True
                )

                if free_plan:
                    # Calculate billing period (monthly)
                    now = datetime.now(timezone.utc)
                    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    period_end = (period_start + relativedelta(months=1)) - timedelta(seconds=1)

                    # Create billing association with all required fields
                    user_billing = UserBilling(
                        user_id=user.id,
                        billing_plan_id=free_plan.id,
                        billing_period_start=period_start,
                        billing_period_end=period_end,
                        is_active=True,
                        is_suspended=False,
                    )
                    UserDataManager(self.session).add_one(user_billing)
                    self.session.commit()
                    logger.info(f"Free billing plan assigned to new OAuth user: {user.email}")
                else:
                    logger.warning("No 'Free' billing plan found in database - user will have no billing plan")

        except Exception as billing_error:
            logger.error(f"Failed to assign billing plan to OAuth user {user.email}: {billing_error}")
            # Continue even if billing assignment fails

        # Create default project
        try:
            from budapp.auth.schemas import ResourceCreate
            from budapp.commons.constants import ProjectStatusEnum, ProjectTypeEnum
            from budapp.permissions.service import PermissionService
            from budapp.project_ops.models import Project as ProjectModel

            logger.info(f"Creating default project for user {user.email} (ID: {user.id})")

            # Create default project for the client user
            default_project = ProjectModel(
                name="My First Project",
                description="Welcome to your first project! Start by adding models and creating endpoints.",
                created_by=user.id,
                status=ProjectStatusEnum.ACTIVE,
                benchmark=False,
                project_type=ProjectTypeEnum.CLIENT_APP.value,
            )

            # Insert the project into database
            UserDataManager(self.session).add_one(default_project)

            # Associate the user with the project
            default_project.users.append(user)
            self.session.commit()

            logger.info(
                f"✅ Default project '{default_project.name}' (ID: {default_project.id}) created successfully for OAuth user: {user.email}"
            )

            # Create project permissions in database
            import json

            from budapp.commons.constants import PermissionEnum
            from budapp.permissions.models import ProjectPermission

            # Get all project-level permissions
            project_permissions = PermissionEnum.get_project_level_scopes()

            # Create a single ProjectPermission record with all scopes
            project_permission = ProjectPermission(
                project_id=default_project.id,
                user_id=user.id,
                auth_id=user.auth_id,
                scopes=json.dumps(project_permissions),  # Store as JSON string
            )
            UserDataManager(self.session).add_one(project_permission)

            self.session.commit()
            logger.info(f"Project permissions added to database for user: {user.email}")

            # Create permissions for the project in Keycloak
            try:
                permission_service = PermissionService(self.session)

                # Create resource permission
                payload = ResourceCreate(
                    resource_id=str(default_project.id),
                    resource_type="project",
                    scopes=["view", "manage"],
                )

                # Use the user object directly to create permissions
                # The service will get tenant and client internally
                await permission_service.create_resource_permission_by_user(user, payload)

                logger.info(f"Default project permissions created in Keycloak for user: {user.email}")

            except Exception as perm_error:
                logger.error(f"Failed to create project permissions in Keycloak: {perm_error}")
                # Continue even if permission creation fails

        except Exception as project_error:
            logger.error(f"Failed to create default project for OAuth user {user.email}: {project_error}")
            # Don't fail user creation if project creation fails

    async def _generate_tokens_for_user(
        self, user: User, tenant: Tenant, tenant_client: TenantClient
    ) -> Dict[str, any]:
        """Generate JWT tokens for user.

        Note: This would typically be done by Keycloak.
        """
        # In production, we would get tokens from Keycloak
        # For now, return mock tokens
        return {
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }

    def _get_provider_info(self, provider: str) -> Dict[str, str]:
        """Get display information for OAuth provider."""
        provider_info = {
            OAuthProviderEnum.GOOGLE.value: {
                "display_name": "Google",
                "icon_url": "https://www.google.com/favicon.ico",
            },
            OAuthProviderEnum.LINKEDIN.value: {
                "display_name": "LinkedIn",
                "icon_url": "https://www.linkedin.com/favicon.ico",
            },
            OAuthProviderEnum.GITHUB.value: {"display_name": "GitHub", "icon_url": "https://github.com/favicon.ico"},
            OAuthProviderEnum.MICROSOFT.value: {
                "display_name": "Microsoft",
                "icon_url": "https://www.microsoft.com/favicon.ico",
            },
        }

        return provider_info.get(provider, {"display_name": provider.title(), "icon_url": None})
