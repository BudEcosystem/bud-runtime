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

"""Integration tests for OAuth routes."""

import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from budapp.commons.constants import OAuthProviderEnum, UserRoleEnum
from budapp.user_ops.models import Tenant, User
from budapp.user_ops.oauth_models import TenantOAuthConfig


@pytest.fixture
async def test_tenant_with_oauth(async_session):
    """Create test tenant with OAuth configuration."""
    tenant = Tenant(
        id=uuid4(),
        name="Test OAuth Tenant",
        realm_name="test-oauth-realm",
        tenant_identifier="test-oauth-realm",
    )
    async_session.add(tenant)

    # Add OAuth configurations
    for provider in [OAuthProviderEnum.GOOGLE, OAuthProviderEnum.GITHUB]:
        config = TenantOAuthConfig(
            tenant_id=tenant.id,
            provider=provider.value,
            client_id=f"test-{provider.value}-client-id",
            client_secret_encrypted="encrypted-secret",
            enabled=True,
            allowed_domains=["example.com"] if provider == OAuthProviderEnum.GOOGLE else None,
            auto_create_users=True,
        )
        async_session.add(config)

    await async_session.commit()
    return tenant


@pytest.fixture
async def admin_user(async_session):
    """Create admin user for testing."""
    user = User(
        id=uuid4(),
        auth_id=uuid4(),
        name="Admin User",
        email="admin@example.com",
        role=UserRoleEnum.ADMIN,
    )
    async_session.add(user)
    await async_session.commit()
    return user


class TestOAuthLoginRoute:
    """Test OAuth login initiation route."""

    def test_initiate_oauth_login_success(
        self,
        client: TestClient,
        test_tenant_with_oauth: Tenant,
    ):
        """Test successful OAuth login initiation."""
        with patch('budapp.auth.oauth_services.KeycloakManager') as mock_keycloak:
            mock_keycloak.return_value.get_broker_login_url.return_value = (
                "https://keycloak.example.com/auth/broker/google/login"
            )

            response = client.post(
                "/oauth/login",
                json={
                    "provider": "google",
                    "tenantId": str(test_tenant_with_oauth.id),
                },
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert "authUrl" in data
        assert "state" in data
        assert "expiresAt" in data

    def test_initiate_oauth_login_provider_not_configured(
        self,
        client: TestClient,
        test_tenant_with_oauth: Tenant,
    ):
        """Test OAuth login with unconfigured provider."""
        response = client.post(
            "/oauth/login",
            json={
                "provider": "linkedin",  # Not configured
                "tenantId": str(test_tenant_with_oauth.id),
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not configured" in response.json()["message"].lower()

    def test_initiate_oauth_login_rate_limit(
        self,
        client: TestClient,
        test_tenant_with_oauth: Tenant,
    ):
        """Test OAuth login rate limiting."""
        # Make multiple requests to trigger rate limit
        for i in range(11):  # Rate limit is 10 per minute
            response = client.post(
                "/oauth/login",
                json={
                    "provider": "google",
                    "tenantId": str(test_tenant_with_oauth.id),
                },
            )

        # Last request should be rate limited
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


class TestOAuthSecureCallbackRoute:
    """Test OAuth secure callback route."""

    def test_oauth_secure_callback_success(self, client: TestClient):
        """Test successful OAuth secure callback."""
        with patch('budapp.auth.oauth_services.OAuthService') as mock_service, \
             patch('budapp.auth.token_exchange_service.TokenExchangeService') as mock_exchange, \
             patch('budapp.user_ops.crud.UserDataManager') as mock_user_manager:

            # Mock OAuth service
            mock_oauth_instance = AsyncMock()
            mock_service.return_value = mock_oauth_instance

            # Mock handle_oauth_callback to return a token response
            mock_oauth_instance.handle_oauth_callback.return_value = AsyncMock(
                access_token="test-token",
                refresh_token="test-refresh",
                expires_in=3600,
                token_type="Bearer",
                user_info=AsyncMock(
                    provider="google",
                    email="user@example.com",
                    external_id="google-123",
                    name="Test User",
                ),
                is_new_user=True,
                requires_linking=False,
            )

            # Mock UserDataManager to return a user when looking up by email
            mock_user = AsyncMock()
            mock_user.id = uuid4()
            mock_user.email = "user@example.com"
            mock_user_manager_instance = AsyncMock()
            mock_user_manager.return_value = mock_user_manager_instance
            mock_user_manager_instance.retrieve_by_fields.return_value = mock_user

            # Mock token exchange service
            mock_exchange_instance = AsyncMock()
            mock_exchange.return_value = mock_exchange_instance
            mock_exchange_instance.create_exchange_token.return_value = "exchange-token-123"

            # Test the secure callback route
            response = client.get(
                "/oauth/secure-callback",
                params={
                    "code": "test-code",
                    "state": "test-state",
                },
            )

        # Secure callback returns a redirect with exchange token
        assert response.status_code == status.HTTP_302_FOUND
        # Check redirect location contains exchange token
        location = response.headers.get("location")
        assert "exchange_token=exchange-token-123" in location

    def test_oauth_secure_callback_error_from_provider(self, client: TestClient):
        """Test OAuth secure callback with error from provider."""
        response = client.get(
            "/oauth/secure-callback",
            params={
                "state": "test-state",
                "error": "access_denied",
                "error_description": "User denied access",
            },
        )

        # Secure callback returns a redirect to error page
        assert response.status_code == status.HTTP_302_FOUND
        location = response.headers.get("location")
        assert "error=" in location


class TestOAuthProvidersRoute:
    """Test OAuth providers listing route."""

    def test_get_oauth_providers_success(
        self,
        client: TestClient,
        test_tenant_with_oauth: Tenant,
    ):
        """Test getting available OAuth providers."""
        response = client.get(
            "/oauth/providers",
            params={"tenant_id": str(test_tenant_with_oauth.id)},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert len(data["providers"]) == 2

        provider_names = [p["provider"] for p in data["providers"]]
        assert "google" in provider_names
        assert "github" in provider_names

    def test_get_oauth_providers_default_tenant(self, client: TestClient):
        """Test getting OAuth providers for default tenant."""
        with patch('budapp.auth.oauth_services.OAuthService') as mock_service:
            mock_instance = AsyncMock()
            mock_service.return_value = mock_instance

            mock_instance._get_tenant.return_value = AsyncMock(id=uuid4())
            mock_instance.get_available_providers.return_value = []

            response = client.get("/oauth/providers")

        assert response.status_code == status.HTTP_200_OK


class TestOAuthAdminRoutes:
    """Test OAuth admin routes."""

    def test_configure_oauth_provider_success(
        self,
        client: TestClient,
        test_tenant_with_oauth: Tenant,
        admin_user: User,
    ):
        """Test configuring OAuth provider as admin."""
        with patch('budapp.commons.dependencies.get_current_user') as mock_user:
            mock_user.return_value = admin_user

            with patch('budapp.auth.tenant_oauth_service.TenantOAuthService') as mock_service:
                mock_instance = AsyncMock()
                mock_service.return_value = mock_instance

                mock_instance.configure_oauth_provider.return_value = AsyncMock(
                    id=uuid4(),
                    tenant_id=test_tenant_with_oauth.id,
                    provider="microsoft",
                    client_id="test-client",
                    enabled=True,
                )

                response = client.post(
                    "/admin/oauth/configure",
                    json={
                        "tenantId": str(test_tenant_with_oauth.id),
                        "provider": "microsoft",
                        "clientId": "test-client",
                        "clientSecret": "test-secret",
                        "enabled": True,
                        "allowedDomains": ["company.com"],
                        "autoCreateUsers": False,
                    },
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["provider"] == "microsoft"

    def test_configure_oauth_provider_forbidden(
        self,
        client: TestClient,
        test_tenant_with_oauth: Tenant,
    ):
        """Test configuring OAuth provider without admin permissions."""
        # Create non-admin user
        with patch('budapp.commons.dependencies.get_current_user') as mock_user:
            non_admin = User(
                id=uuid4(),
                auth_id=uuid4(),
                name="Regular User",
                email="user@example.com",
                role=UserRoleEnum.DEVELOPER,
            )
            mock_user.return_value = non_admin

            response = client.post(
                "/admin/oauth/configure",
                json={
                    "tenantId": str(test_tenant_with_oauth.id),
                    "provider": "microsoft",
                    "clientId": "test-client",
                    "clientSecret": "test-secret",
                },
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "permissions" in response.json()["message"].lower()

    def test_disable_oauth_provider_success(
        self,
        client: TestClient,
        test_tenant_with_oauth: Tenant,
        admin_user: User,
    ):
        """Test disabling OAuth provider as admin."""
        with patch('budapp.commons.dependencies.get_current_user') as mock_user:
            mock_user.return_value = admin_user

            with patch('budapp.auth.tenant_oauth_service.TenantOAuthService') as mock_service:
                mock_instance = AsyncMock()
                mock_service.return_value = mock_instance
                mock_instance.disable_oauth_provider.return_value = True

                response = client.put(
                    f"/admin/oauth/disable/{test_tenant_with_oauth.id}/google"
                )

        assert response.status_code == status.HTTP_200_OK
        assert "disabled successfully" in response.json()["message"]
