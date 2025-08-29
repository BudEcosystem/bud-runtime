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

            # Mock UserDataManager for session creation
            with patch('budapp.user_ops.crud.UserDataManager') as MockDataManager:
                mock_dm = Mock()
                mock_dm.add_one = Mock()
                MockDataManager.return_value = mock_dm

                with patch.object(oauth_service.keycloak_manager, 'get_broker_login_url') as mock_url:
                    mock_url.return_value = "https://keycloak.example.com/auth/broker/google/login?state=test"

                    response = await oauth_service.initiate_oauth_login(
                        request, "https://app.example.com"
                    )

        assert response.state
        assert response.auth_url
        assert response.expires_at > datetime.now(UTC)

    @pytest.mark.asyncio
    async def test_initiate_oauth_login_provider_not_configured(
        self,
        oauth_service: OAuthService,
        test_tenant: Tenant,
        mock_session,
    ):
        """Test OAuth login with unconfigured provider."""
        request = OAuthLoginRequest(
            provider=OAuthProviderEnum.LINKEDIN,
            tenant_id=test_tenant.id,
        )

        with patch.object(oauth_service, '_get_tenant_oauth_config') as mock_get_config:
            mock_get_config.return_value = None

            with pytest.raises(OAuthError) as exc_info:
                await oauth_service.initiate_oauth_login(
                    request, "https://app.example.com"
                )

        assert exc_info.value.code == OAuthErrorCode.PROVIDER_NOT_CONFIGURED

    @pytest.mark.asyncio
    async def test_initiate_oauth_login_provider_disabled(
        self,
        oauth_service: OAuthService,
        test_tenant: Tenant,
        test_oauth_config: TenantOAuthConfig,
        mock_session,
    ):
        """Test OAuth login with disabled provider."""
        # Disable the provider
        test_oauth_config.enabled = False

        request = OAuthLoginRequest(
            provider=OAuthProviderEnum.GOOGLE,
            tenant_id=test_tenant.id,
        )

        with patch.object(oauth_service, '_get_tenant_oauth_config') as mock_get_config:
            mock_get_config.return_value = test_oauth_config

            with pytest.raises(OAuthError) as exc_info:
                await oauth_service.initiate_oauth_login(
                    request, "https://app.example.com"
                )

        assert exc_info.value.code == OAuthErrorCode.PROVIDER_DISABLED


class TestOAuthCallback:
    """Test OAuth callback handling."""

    @pytest.mark.asyncio
    async def test_handle_oauth_callback_new_user(
        self,
        oauth_service: OAuthService,
        test_tenant: Tenant,
        test_oauth_config: TenantOAuthConfig,
        mock_session,
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
        mock_session.add(oauth_session)
        mock_session.commit()

        # Mock user info from provider
        mock_user_info = OAuthUserInfo(
            provider=OAuthProviderEnum.GOOGLE,
            external_id="google-123",
            email="newuser@example.com",
            name="New User",
            email_verified=True,
        )

        with patch.object(oauth_service, '_validate_oauth_session', return_value=oauth_session), \
             patch('budapp.user_ops.crud.UserDataManager') as mock_user_manager, \
             patch.object(oauth_service, '_get_user_info_from_provider', return_value=mock_user_info), \
             patch.object(oauth_service, '_find_existing_user', return_value=None), \
             patch.object(oauth_service, '_get_tenant_oauth_config', return_value=test_oauth_config), \
             patch.object(oauth_service, '_create_user_from_oauth') as mock_create_user, \
             patch.object(oauth_service, '_generate_tokens_for_user', return_value={
                 "access_token": "test-token",
                 "refresh_token": "test-refresh",
                 "expires_in": 3600,
             }):

            # Mock UserDataManager for tenant and tenant_client retrieval
            mock_user_manager_instance = AsyncMock()
            mock_user_manager.return_value = mock_user_manager_instance
            mock_tenant_client = Mock(client_id="test-client-id")
            mock_user_manager_instance.retrieve_by_fields = AsyncMock(side_effect=[
                test_tenant,  # First call: retrieve Tenant
                mock_tenant_client,  # Second call: retrieve TenantClient
            ])

            # Mock user creation
            new_user = Mock()
            new_user.id = uuid4()
            new_user.email = "newuser@example.com"
            mock_create_user.return_value = new_user

            request = OAuthCallbackRequest(
                code="test-code",
                state=state,
            )

            response = await oauth_service.handle_oauth_callback(request)

        assert response.access_token == "test-token"
        assert response.is_new_user is True
        assert response.requires_linking is False
        assert response.user_info.email == "newuser@example.com"

    @pytest.mark.asyncio
    async def test_handle_oauth_callback_existing_user(
        self,
        oauth_service: OAuthService,
        test_tenant: Tenant,
        test_oauth_config: TenantOAuthConfig,
        mock_session,
    ):
        """Test OAuth callback for existing user."""
        # Create existing user
        existing_user = User(
            auth_id=uuid4(),
            name="Existing User",
            email="existing@example.com",
            user_type=UserTypeEnum.CLIENT,
        )
        mock_session.add(existing_user)

        # Create OAuth session
        state = secrets.token_urlsafe(32)
        oauth_session = OAuthSession(
            provider=OAuthProviderEnum.GOOGLE.value,
            state=state,
            tenant_id=test_tenant.id,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            completed=False,
        )
        mock_session.add(oauth_session)
        mock_session.commit()

        # Mock user info from provider
        mock_user_info = OAuthUserInfo(
            provider=OAuthProviderEnum.GOOGLE,
            external_id="google-123",
            email="existing@example.com",
            name="Existing User",
            email_verified=True,
        )

        with patch.object(oauth_service, '_validate_oauth_session', return_value=oauth_session), \
             patch('budapp.user_ops.crud.UserDataManager') as mock_user_manager, \
             patch.object(oauth_service, '_get_user_info_from_provider', return_value=mock_user_info), \
             patch.object(oauth_service, '_find_existing_user', return_value=existing_user), \
             patch.object(oauth_service, '_update_user_oauth_provider') as mock_update, \
             patch.object(oauth_service, '_generate_tokens_for_user', return_value={
                 "access_token": "test-token",
                 "refresh_token": "test-refresh",
                 "expires_in": 3600,
             }):

            # Mock UserDataManager for tenant and tenant_client retrieval
            mock_user_manager_instance = AsyncMock()
            mock_user_manager.return_value = mock_user_manager_instance
            mock_tenant_client = Mock(client_id="test-client-id")
            mock_user_manager_instance.retrieve_by_fields = AsyncMock(side_effect=[
                test_tenant,  # First call: retrieve Tenant
                mock_tenant_client,  # Second call: retrieve TenantClient
            ])

            request = OAuthCallbackRequest(
                code="test-code",
                state=state,
            )

            response = await oauth_service.handle_oauth_callback(request)

        assert response.access_token == "test-token"
        assert response.is_new_user is False
        assert response.requires_linking is False

    @pytest.mark.asyncio
    async def test_handle_oauth_callback_invalid_state(
        self,
        oauth_service: OAuthService,
        mock_session,
    ):
        """Test OAuth callback with invalid state."""
        with patch('budapp.user_ops.crud.UserDataManager') as mock_user_manager:
            # Mock UserDataManager to return None for invalid state
            mock_user_manager_instance = AsyncMock()
            mock_user_manager.return_value = mock_user_manager_instance
            mock_user_manager_instance.retrieve_by_fields = AsyncMock(return_value=None)

            request = OAuthCallbackRequest(
                code="test-code",
                state="invalid-state",
            )

            with pytest.raises(OAuthError) as exc_info:
                await oauth_service.handle_oauth_callback(request)

            assert exc_info.value.code == OAuthErrorCode.INVALID_STATE

    @pytest.mark.asyncio
    async def test_handle_oauth_callback_expired_session(
        self,
        oauth_service: OAuthService,
        test_tenant: Tenant,
        mock_session,
    ):
        """Test OAuth callback with expired session."""
        # Create expired OAuth session
        state = secrets.token_urlsafe(32)
        expired_time = datetime.now(UTC) - timedelta(minutes=1)
        oauth_session = OAuthSession(
            provider=OAuthProviderEnum.GOOGLE.value,
            state=state,
            tenant_id=test_tenant.id,
            expires_at=expired_time,  # Expired
            completed=False,  # Explicitly not completed
        )
        mock_session.add(oauth_session)
        mock_session.commit()

        with patch('budapp.user_ops.crud.UserDataManager') as mock_user_manager:
            # Mock UserDataManager to return the expired session
            mock_user_manager_instance = AsyncMock()
            mock_user_manager.return_value = mock_user_manager_instance

            # Create a fresh copy of the session for each call to avoid state mutation
            def return_expired_session(*args, **kwargs):
                # Return the expired session only for OAuthSession queries
                if args and args[0] == OAuthSession:
                    # Create a fresh session object to avoid state mutation
                    fresh_session = OAuthSession(
                        provider=OAuthProviderEnum.GOOGLE.value,
                        state=state,
                        tenant_id=test_tenant.id,
                        expires_at=expired_time,
                        completed=False,
                    )
                    return fresh_session
                return None

            mock_user_manager_instance.retrieve_by_fields = AsyncMock(side_effect=return_expired_session)

            request = OAuthCallbackRequest(
                code="test-code",
                state=state,
            )

            with pytest.raises(OAuthError) as exc_info:
                await oauth_service.handle_oauth_callback(request)

            assert exc_info.value.code == OAuthErrorCode.STATE_EXPIRED

    @pytest.mark.asyncio
    async def test_handle_oauth_callback_domain_not_allowed(
        self,
        oauth_service: OAuthService,
        test_tenant: Tenant,
        test_oauth_config: TenantOAuthConfig,
        mock_session,
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
        mock_session.add(oauth_session)
        mock_session.commit()

        # Mock user info with disallowed domain
        mock_user_info = OAuthUserInfo(
            provider=OAuthProviderEnum.GOOGLE,
            external_id="google-123",
            email="user@notallowed.com",  # Not in allowed_domains
            name="New User",
            email_verified=True,
        )

        with patch.object(oauth_service, '_validate_oauth_session', return_value=oauth_session), \
             patch('budapp.user_ops.crud.UserDataManager') as mock_user_manager, \
             patch.object(oauth_service, '_get_user_info_from_provider', return_value=mock_user_info), \
             patch.object(oauth_service, '_find_existing_user', return_value=None), \
             patch.object(oauth_service, '_get_tenant_oauth_config', return_value=test_oauth_config):

            # Mock UserDataManager for tenant and tenant_client retrieval
            mock_user_manager_instance = AsyncMock()
            mock_user_manager.return_value = mock_user_manager_instance
            mock_tenant_client = Mock(client_id="test-client-id")
            mock_user_manager_instance.retrieve_by_fields = AsyncMock(side_effect=[
                test_tenant,  # First call: retrieve Tenant
                mock_tenant_client,  # Second call: retrieve TenantClient
            ])

            request = OAuthCallbackRequest(
                code="test-code",
                state=state,
            )

            with pytest.raises(OAuthError) as exc_info:
                await oauth_service.handle_oauth_callback(request)

            assert exc_info.value.code == OAuthErrorCode.DOMAIN_NOT_ALLOWED


class TestOAuthProviderConfiguration:
    """Test OAuth provider configuration."""

    @pytest.mark.asyncio
    async def test_get_available_providers(
        self,
        oauth_service: OAuthService,
        test_tenant: Tenant,
        test_oauth_config: TenantOAuthConfig,
        mock_session,
    ):
        """Test getting available OAuth providers."""
        providers = await oauth_service.get_available_providers(test_tenant.id)

        assert len(providers) == 1
        assert providers[0].provider == OAuthProviderEnum.GOOGLE.value
        assert providers[0].enabled is True
        assert providers[0].allowed_domains == ["example.com"]
        assert providers[0].auto_create_users is True

    @pytest.mark.asyncio
    async def test_get_available_providers_empty(
        self,
        oauth_service: OAuthService,
        test_tenant: Tenant,
        mock_session,
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
