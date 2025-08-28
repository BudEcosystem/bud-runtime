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

"""Unit tests for OAuth integration."""

import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from uuid import UUID, uuid4

UTC = timezone.utc  # For Python 3.8 compatibility

import pytest
from sqlalchemy.orm import Session

from budapp.auth.oauth_error_handler import OAuthError, OAuthErrorCode
from budapp.auth.oauth_schemas import (
    OAuthLoginRequest,
    OAuthCallbackRequest,
    OAuthUserInfo,
)
from budapp.auth.oauth_services import OAuthService
from budapp.commons.constants import OAuthProviderEnum, UserTypeEnum
from budapp.user_ops.models import Tenant, User
from budapp.user_ops.oauth_models import OAuthSession, TenantOAuthConfig


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = Mock(spec=Session)
    session.commit = Mock()
    session.add = Mock()
    session.query = Mock()
    session.flush = Mock()
    session.refresh = Mock()
    return session


@pytest.fixture
def oauth_service(mock_session):
    """Create OAuth service instance."""
    return OAuthService(mock_session)


@pytest.fixture
def test_tenant():
    """Create test tenant."""
    tenant = Tenant(
        id=uuid4(),
        name="Test Tenant",
        realm_name="test-realm",
        tenant_identifier="test-realm",
    )
    return tenant


@pytest.fixture
def test_oauth_config(test_tenant: Tenant):
    """Create test OAuth configuration."""
    config = TenantOAuthConfig(
        tenant_id=test_tenant.id,
        provider=OAuthProviderEnum.GOOGLE.value,
        client_id="test-client-id",
        client_secret_encrypted="encrypted-secret",
        enabled=True,
        allowed_domains=["example.com"],
        auto_create_users=True,
    )
    return config


class TestOAuthLoginInitiation:
    """Test OAuth login initiation."""

    @pytest.mark.asyncio
    async def test_initiate_oauth_login_success(
        self,
        oauth_service: OAuthService,
        test_tenant: Tenant,
        test_oauth_config: TenantOAuthConfig,
        mock_session,
    ):
        """Test successful OAuth login initiation."""
        request = OAuthLoginRequest(
            provider=OAuthProviderEnum.GOOGLE,
            tenant_id=test_tenant.id,
        )

        # Mock the necessary dependencies
        with patch.object(oauth_service, '_get_tenant_oauth_config') as mock_get_config:
            mock_get_config.return_value = test_oauth_config

            with patch.object(oauth_service, '_create_oauth_session') as mock_create_session:
                mock_oauth_session = OAuthSession(
                    id=uuid4(),
                    state=secrets.token_urlsafe(32),
                    provider=OAuthProviderEnum.GOOGLE.value,
                    tenant_id=test_tenant.id,
                    completed=False,
                    expires_at=datetime.now(UTC) + timedelta(minutes=10),
                )
                mock_create_session.return_value = mock_oauth_session

                with patch.object(oauth_service.keycloak_manager, 'get_broker_login_url') as mock_url:
                    mock_url.return_value = "https://keycloak.example.com/auth/broker/google/login?state=test"

                    response = await oauth_service.initiate_oauth_login(
                        request, "https://app.example.com"
                    )

        assert response.state
        assert response.auth_url
        assert response.expires_at > datetime.now(UTC)

    async def test_initiate_oauth_login_provider_not_configured(
        self,
        oauth_service: OAuthService,
        test_tenant: Tenant,
    ):
        """Test OAuth login with unconfigured provider."""
        request = OAuthLoginRequest(
            provider=OAuthProviderEnum.LINKEDIN,
            tenant_id=test_tenant.id,
        )

        with pytest.raises(OAuthError) as exc_info:
            await oauth_service.initiate_oauth_login(
                request, "https://app.example.com"
            )

        assert exc_info.value.code == OAuthErrorCode.PROVIDER_NOT_CONFIGURED

    async def test_initiate_oauth_login_provider_disabled(
        self,
        oauth_service: OAuthService,
        test_tenant: Tenant,
        test_oauth_config: TenantOAuthConfig,
    ):
        """Test OAuth login with disabled provider."""
        # Disable the provider
        test_oauth_config.enabled = False
        await oauth_service.session.commit()

        request = OAuthLoginRequest(
            provider=OAuthProviderEnum.GOOGLE,
            tenant_id=test_tenant.id,
        )

        with pytest.raises(OAuthError) as exc_info:
            await oauth_service.initiate_oauth_login(
                request, "https://app.example.com"
            )

        assert exc_info.value.code == OAuthErrorCode.PROVIDER_DISABLED


class TestOAuthCallback:
    """Test OAuth callback handling."""

    async def test_handle_oauth_callback_new_user(
        self,
        oauth_service: OAuthService,
        test_tenant: Tenant,
        test_oauth_config: TenantOAuthConfig,
        async_session: AsyncSession,
    ):
        """Test OAuth callback for new user."""
        # Create OAuth session
        state = secrets.token_urlsafe(32)
        oauth_session = OAuthSession(
            provider=OAuthProviderEnum.GOOGLE.value,
            state=state,
            tenant_id=test_tenant.id,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            completed=False,
        )
        async_session.add(oauth_session)
        await async_session.commit()

        # Mock user info from provider
        mock_user_info = OAuthUserInfo(
            provider=OAuthProviderEnum.GOOGLE,
            external_id="google-123",
            email="newuser@example.com",
            name="New User",
            email_verified=True,
        )

        with patch.object(oauth_service, '_get_user_info_from_provider', return_value=mock_user_info), \
             patch.object(oauth_service, '_generate_tokens_for_user', return_value={
                 "access_token": "test-token",
                 "refresh_token": "test-refresh",
                 "expires_in": 3600,
             }), \
             patch.object(oauth_service.keycloak_manager, 'create_user', return_value=str(uuid4())), \
             patch.object(oauth_service.keycloak_manager, 'link_provider_account', return_value=True):

            request = OAuthCallbackRequest(
                code="test-code",
                state=state,
            )

            response = await oauth_service.handle_oauth_callback(request)

        assert response.access_token == "test-token"
        assert response.is_new_user is True
        assert response.requires_linking is False
        assert response.user_info.email == "newuser@example.com"

        # Verify user was created
        user = await oauth_service.session.get(
            User, {"email": "newuser@example.com"}
        )
        assert user is not None
        assert user.user_type == UserTypeEnum.CLIENT

    async def test_handle_oauth_callback_existing_user(
        self,
        oauth_service: OAuthService,
        test_tenant: Tenant,
        test_oauth_config: TenantOAuthConfig,
        async_session: AsyncSession,
    ):
        """Test OAuth callback for existing user."""
        # Create existing user
        existing_user = User(
            auth_id=uuid4(),
            name="Existing User",
            email="existing@example.com",
            user_type=UserTypeEnum.CLIENT,
        )
        async_session.add(existing_user)

        # Create OAuth session
        state = secrets.token_urlsafe(32)
        oauth_session = OAuthSession(
            provider=OAuthProviderEnum.GOOGLE.value,
            state=state,
            tenant_id=test_tenant.id,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            completed=False,
        )
        async_session.add(oauth_session)
        await async_session.commit()

        # Mock user info from provider
        mock_user_info = OAuthUserInfo(
            provider=OAuthProviderEnum.GOOGLE,
            external_id="google-123",
            email="existing@example.com",
            name="Existing User",
            email_verified=True,
        )

        with patch.object(oauth_service, '_get_user_info_from_provider', return_value=mock_user_info), \
             patch.object(oauth_service, '_generate_tokens_for_user', return_value={
                 "access_token": "test-token",
                 "refresh_token": "test-refresh",
                 "expires_in": 3600,
             }):

            request = OAuthCallbackRequest(
                code="test-code",
                state=state,
            )

            response = await oauth_service.handle_oauth_callback(request)

        assert response.access_token == "test-token"
        assert response.is_new_user is False
        assert response.requires_linking is False

    async def test_handle_oauth_callback_invalid_state(
        self,
        oauth_service: OAuthService,
    ):
        """Test OAuth callback with invalid state."""
        request = OAuthCallbackRequest(
            code="test-code",
            state="invalid-state",
        )

        with pytest.raises(OAuthError) as exc_info:
            await oauth_service.handle_oauth_callback(request)

        assert exc_info.value.code == OAuthErrorCode.INVALID_STATE

    async def test_handle_oauth_callback_expired_session(
        self,
        oauth_service: OAuthService,
        test_tenant: Tenant,
        async_session: AsyncSession,
    ):
        """Test OAuth callback with expired session."""
        # Create expired OAuth session
        state = secrets.token_urlsafe(32)
        oauth_session = OAuthSession(
            provider=OAuthProviderEnum.GOOGLE.value,
            state=state,
            tenant_id=test_tenant.id,
            expires_at=datetime.now(UTC) - timedelta(minutes=1),  # Expired
            completed=False,
        )
        async_session.add(oauth_session)
        await async_session.commit()

        request = OAuthCallbackRequest(
            code="test-code",
            state=state,
        )

        with pytest.raises(OAuthError) as exc_info:
            await oauth_service.handle_oauth_callback(request)

        assert exc_info.value.code == OAuthErrorCode.STATE_EXPIRED

    async def test_handle_oauth_callback_domain_not_allowed(
        self,
        oauth_service: OAuthService,
        test_tenant: Tenant,
        test_oauth_config: TenantOAuthConfig,
        async_session: AsyncSession,
    ):
        """Test OAuth callback with disallowed email domain."""
        # Create OAuth session
        state = secrets.token_urlsafe(32)
        oauth_session = OAuthSession(
            provider=OAuthProviderEnum.GOOGLE.value,
            state=state,
            tenant_id=test_tenant.id,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            completed=False,
        )
        async_session.add(oauth_session)
        await async_session.commit()

        # Mock user info with disallowed domain
        mock_user_info = OAuthUserInfo(
            provider=OAuthProviderEnum.GOOGLE,
            external_id="google-123",
            email="user@notallowed.com",  # Not in allowed_domains
            name="New User",
            email_verified=True,
        )

        with patch.object(oauth_service, '_get_user_info_from_provider', return_value=mock_user_info):
            request = OAuthCallbackRequest(
                code="test-code",
                state=state,
            )

            with pytest.raises(OAuthError) as exc_info:
                await oauth_service.handle_oauth_callback(request)

            assert exc_info.value.code == OAuthErrorCode.DOMAIN_NOT_ALLOWED


class TestOAuthProviderConfiguration:
    """Test OAuth provider configuration."""

    async def test_get_available_providers(
        self,
        oauth_service: OAuthService,
        test_tenant: Tenant,
        test_oauth_config: TenantOAuthConfig,
    ):
        """Test getting available OAuth providers."""
        providers = await oauth_service.get_available_providers(test_tenant.id)

        assert len(providers) == 1
        assert providers[0].provider == OAuthProviderEnum.GOOGLE.value
        assert providers[0].enabled is True
        assert providers[0].allowed_domains == ["example.com"]
        assert providers[0].auto_create_users is True

    async def test_get_available_providers_empty(
        self,
        oauth_service: OAuthService,
        test_tenant: Tenant,
    ):
        """Test getting available providers when none configured."""
        providers = await oauth_service.get_available_providers(test_tenant.id)

        assert len(providers) == 0


class TestOAuthErrorHandling:
    """Test OAuth error handling."""

    def test_validate_state_parameter(self):
        """Test state parameter validation."""
        from budapp.auth.oauth_error_handler import OAuthSessionValidator

        # Valid state
        valid_state = secrets.token_urlsafe(32)
        assert OAuthSessionValidator.validate_state_parameter(valid_state) is True

        # Invalid states
        assert OAuthSessionValidator.validate_state_parameter("") is False
        assert OAuthSessionValidator.validate_state_parameter("short") is False
        assert OAuthSessionValidator.validate_state_parameter("invalid@state") is False

    def test_validate_email_domain(self):
        """Test email domain validation."""
        from budapp.auth.oauth_error_handler import OAuthSessionValidator

        allowed_domains = ["example.com", "company.org"]

        # Valid domains
        assert OAuthSessionValidator.validate_email_domain(
            "user@example.com", allowed_domains
        ) is True
        assert OAuthSessionValidator.validate_email_domain(
            "user@company.org", allowed_domains
        ) is True

        # Invalid domain
        assert OAuthSessionValidator.validate_email_domain(
            "user@other.com", allowed_domains
        ) is False

        # No restrictions
        assert OAuthSessionValidator.validate_email_domain(
            "user@any.com", None
        ) is True
