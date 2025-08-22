"""Unit tests for logout functionality with token blacklisting."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from budapp.auth.schemas import LogoutRequest
from budapp.auth.services import AuthService
from budapp.commons.dependencies import get_current_user
from budapp.user_ops.models import Tenant, TenantClient, User


@pytest.mark.asyncio
async def test_logout_blacklists_access_token():
    """Test that logout properly blacklists the access token."""
    # Setup
    mock_session = MagicMock(spec=Session)
    auth_service = AuthService(mock_session)

    # Mock logout request with refresh token
    logout_request = LogoutRequest(refresh_token="test_refresh_token")
    access_token = "test_access_token"

    # Mock the database queries
    with patch("budapp.auth.services.UserDataManager") as mock_user_manager:
        with patch("budapp.auth.services.KeycloakManager") as mock_keycloak:
            with patch("budapp.auth.services.RedisService") as mock_redis_class:
                # Setup mocks
                mock_redis = AsyncMock()
                mock_redis_class.return_value = mock_redis

                mock_data_manager = AsyncMock()
                mock_user_manager.return_value = mock_data_manager

                # Mock tenant retrieval
                mock_tenant = MagicMock(spec=Tenant)
                mock_tenant.id = "5f59dc5e-7cdb-4c92-8cee-eab63492e82e"  # Valid UUID v4
                mock_tenant.realm_name = "test-realm"
                mock_data_manager.retrieve_by_fields.return_value = mock_tenant

                # Mock tenant client
                mock_tenant_client = MagicMock(spec=TenantClient)
                mock_tenant_client.id = "8be3c315-1964-4db9-9957-8c62d4ce4559"  # Valid UUID v4
                mock_tenant_client.client_id = "test-client"
                mock_tenant_client.client_named_id = "test-client-named"
                mock_tenant_client.client_secret = "secret"

                # Configure retrieve_by_fields to return different values based on the model
                async def retrieve_by_fields_side_effect(model, *args, **kwargs):
                    if model == Tenant:
                        return mock_tenant
                    elif model == TenantClient:
                        return mock_tenant_client
                    return None

                mock_data_manager.retrieve_by_fields.side_effect = retrieve_by_fields_side_effect

                # Mock Keycloak token validation
                mock_keycloak_instance = AsyncMock()
                mock_keycloak.return_value = mock_keycloak_instance
                mock_keycloak_instance.validate_token.return_value = {
                    "exp": int(time.time()) + 3600,  # Token expires in 1 hour
                    "sub": "user-id",
                }
                mock_keycloak_instance.logout_user.return_value = True

                # Execute logout with access token
                await auth_service.logout_user(logout_request, access_token)

                # Verify Redis blacklist was called
                mock_redis.set.assert_called_once()
                call_args = mock_redis.set.call_args

                # Check the blacklist key format
                assert call_args[0][0] == "token_blacklist:test_access_token"
                assert call_args[0][1] == "1"
                # Check TTL is set (should be around 3600 seconds)
                assert call_args[1]["ex"] > 0
                assert call_args[1]["ex"] <= 3600


@pytest.mark.asyncio
async def test_logout_without_access_token():
    """Test that logout works even without access token (backward compatibility)."""
    mock_session = MagicMock(spec=Session)
    auth_service = AuthService(mock_session)

    # Mock logout request without access token
    logout_request = LogoutRequest(refresh_token="test_refresh_token")

    with patch("budapp.auth.services.UserDataManager") as mock_user_manager:
        with patch("budapp.auth.services.KeycloakManager") as mock_keycloak:
            with patch("budapp.auth.services.RedisService") as mock_redis_class:
                # Setup mocks
                mock_redis = AsyncMock()
                mock_redis_class.return_value = mock_redis

                mock_data_manager = AsyncMock()
                mock_user_manager.return_value = mock_data_manager

                # Mock tenant retrieval
                mock_tenant = MagicMock(spec=Tenant)
                mock_tenant.id = "9c69891e-8f91-4583-8cdb-6cc05cbf18c1"  # Valid UUID v4
                mock_tenant.realm_name = "test-realm"

                # Mock tenant client
                mock_tenant_client = MagicMock(spec=TenantClient)
                mock_tenant_client.id = "6f959769-f619-427d-b7d8-c2fe78ba9fad"  # Valid UUID v4
                mock_tenant_client.client_id = "test-client"
                mock_tenant_client.client_named_id = "test-client-named"
                mock_tenant_client.client_secret = "secret"

                # Configure retrieve_by_fields to return different values based on the model
                async def retrieve_by_fields_side_effect(model, *args, **kwargs):
                    if model == Tenant:
                        return mock_tenant
                    elif model == TenantClient:
                        return mock_tenant_client
                    return None

                mock_data_manager.retrieve_by_fields.side_effect = retrieve_by_fields_side_effect

                # Mock Keycloak logout
                mock_keycloak_instance = AsyncMock()
                mock_keycloak.return_value = mock_keycloak_instance
                mock_keycloak_instance.logout_user.return_value = True

                # Execute logout without access token
                await auth_service.logout_user(logout_request, None)

                # Verify Redis blacklist was NOT called (no access token)
                mock_redis.set.assert_not_called()


@pytest.mark.asyncio
async def test_get_current_user_checks_blacklist():
    """Test that get_current_user checks the token blacklist."""
    # Mock dependencies
    mock_token = MagicMock()
    mock_token.credentials = "test_access_token"

    mock_session = MagicMock(spec=Session)

    with patch("budapp.commons.dependencies.RedisService") as mock_redis_class:
        with patch("budapp.commons.dependencies.UserDataManager") as mock_user_manager:
            with patch("budapp.commons.dependencies.KeycloakManager") as mock_keycloak:
                # Setup Redis mock
                mock_redis = AsyncMock()
                mock_redis_class.return_value = mock_redis

                # Test case 1: Token is blacklisted
                mock_redis.get.return_value = "1"  # Token is in blacklist

                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(mock_token, mock_session)

                assert exc_info.value.status_code == 401
                assert exc_info.value.detail == "Invalid authentication credentials"

                # Verify Redis was checked
                mock_redis.get.assert_called_with("token_blacklist:test_access_token")

                # Test case 2: Token is not blacklisted
                mock_redis.get.return_value = None  # Token not in blacklist

                # Setup other mocks for successful validation
                mock_data_manager = AsyncMock()
                mock_user_manager.return_value = mock_data_manager

                mock_tenant = MagicMock(spec=Tenant)
                mock_tenant.id = "63b8cb28-1002-4651-9f6d-11478a9334bb"  # Valid UUID v4
                mock_tenant.realm_name = "test-realm"

                mock_tenant_client = MagicMock(spec=TenantClient)
                mock_tenant_client.id = "326a0d45-8cc0-49aa-9613-636026e04697"  # Valid UUID v4
                mock_tenant_client.client_id = "test-client"
                mock_tenant_client.client_named_id = "test-client-named"
                mock_tenant_client.client_secret = "secret"

                mock_user = MagicMock(spec=User)
                mock_user.auth_id = "user-auth-id"  # This is not a UUID, just an auth ID

                # Configure retrieve_by_fields
                async def retrieve_by_fields_side_effect(model, *args, **kwargs):
                    if model == Tenant:
                        return mock_tenant
                    elif model == TenantClient:
                        return mock_tenant_client
                    elif model == User:
                        return mock_user
                    return None

                mock_data_manager.retrieve_by_fields.side_effect = retrieve_by_fields_side_effect

                # Mock Keycloak validation
                mock_keycloak_instance = AsyncMock()
                mock_keycloak.return_value = mock_keycloak_instance
                mock_keycloak_instance.validate_token.return_value = {
                    "sub": "user-auth-id",
                    "exp": int(time.time()) + 3600,
                }

                # Should succeed when token is not blacklisted
                result = await get_current_user(mock_token, mock_session)
                assert result == mock_user
                assert result.raw_token == "test_access_token"


@pytest.mark.asyncio
async def test_logout_continues_on_blacklist_failure():
    """Test that logout continues even if blacklisting fails."""
    mock_session = MagicMock(spec=Session)
    auth_service = AuthService(mock_session)

    logout_request = LogoutRequest(refresh_token="test_refresh_token")
    access_token = "test_access_token"

    with patch("budapp.auth.services.UserDataManager") as mock_user_manager:
        with patch("budapp.auth.services.KeycloakManager") as mock_keycloak:
            with patch("budapp.auth.services.RedisService") as mock_redis_class:
                # Setup Redis to fail
                mock_redis = AsyncMock()
                mock_redis.set.side_effect = Exception("Redis connection failed")
                mock_redis_class.return_value = mock_redis

                # Setup other mocks
                mock_data_manager = AsyncMock()
                mock_user_manager.return_value = mock_data_manager

                mock_tenant = MagicMock(spec=Tenant)
                mock_tenant.id = "fa1d8a4e-aa70-4b04-af0a-e2865f8b186e"  # Valid UUID v4
                mock_tenant.realm_name = "test-realm"

                # Mock tenant client
                mock_tenant_client = MagicMock(spec=TenantClient)
                mock_tenant_client.id = "31a52d0d-c623-49c7-a9b4-03d5ef939f8d"  # Valid UUID v4
                mock_tenant_client.client_id = "test-client"
                mock_tenant_client.client_named_id = "test-client-named"
                mock_tenant_client.client_secret = "secret"

                # Configure retrieve_by_fields to return different values based on the model
                async def retrieve_by_fields_side_effect(model, *args, **kwargs):
                    if model == Tenant:
                        return mock_tenant
                    elif model == TenantClient:
                        return mock_tenant_client
                    return None

                mock_data_manager.retrieve_by_fields.side_effect = retrieve_by_fields_side_effect

                mock_keycloak_instance = AsyncMock()
                mock_keycloak.return_value = mock_keycloak_instance
                mock_keycloak_instance.logout_user.return_value = True

                # Logout should not raise exception even if Redis fails
                await auth_service.logout_user(logout_request, access_token)

                # Verify Keycloak logout was still called
                mock_keycloak_instance.logout_user.assert_called_once()
