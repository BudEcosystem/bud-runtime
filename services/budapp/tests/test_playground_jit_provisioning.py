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

"""Unit tests for playground JIT user provisioning via access token flow."""

import contextlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from budapp.commons.constants import UserRoleEnum, UserStatusEnum, UserTypeEnum
from budapp.commons.exceptions import ClientException
from budapp.playground_ops.services import PlaygroundService
from budapp.user_ops.models import Tenant, TenantClient, User


UTC = timezone.utc


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = Mock(spec=Session)
    session.commit = Mock()
    session.add = Mock()
    session.flush = Mock()
    session.refresh = Mock()
    return session


@pytest.fixture
def playground_service(mock_session):
    """Create PlaygroundService instance."""
    return PlaygroundService(mock_session)


@pytest.fixture
def test_tenant():
    """Create a test tenant."""
    tenant = Mock(spec=Tenant)
    tenant.id = uuid4()
    tenant.realm_name = "bud-keycloak"
    tenant.is_active = True
    return tenant


@pytest.fixture
def test_tenant_client(test_tenant):
    """Create a test tenant client."""
    client = Mock(spec=TenantClient)
    client.id = uuid4()
    client.tenant_id = test_tenant.id
    client.client_id = "test-client-id"
    client.client_named_id = "bud-app"
    client.get_decrypted_client_secret = AsyncMock(return_value="test-secret")
    return client


@pytest.fixture
def test_user():
    """Create a complete test user with all required fields."""
    user = Mock(spec=User)
    user.id = uuid4()
    user.email = "testuser@bud.studio"
    user.name = "Test User"
    user.auth_id = "3dd53c4e-7b00-445b-8be1-c8ae3a8540de"
    user.user_type = UserTypeEnum.CLIENT.value
    user.role = UserRoleEnum.DEVELOPER.value
    user.status = UserStatusEnum.ACTIVE.value
    user.is_superuser = False
    user.first_login = True
    user.raw_token = None
    user.created_at = datetime.now(UTC)
    user.updated_at = datetime.now(UTC)
    return user


@pytest.fixture
def keycloak_user_dict():
    """Create a Keycloak user representation dict."""
    return {
        "id": "3dd53c4e-7b00-445b-8be1-c8ae3a8540de",
        "email": "testuser@bud.studio",
        "firstName": "Test",
        "lastName": "User",
        "enabled": True,
        "emailVerified": True,
    }


@pytest.fixture
def decoded_token():
    """Create a decoded JWT token payload."""
    return {
        "sub": "3dd53c4e-7b00-445b-8be1-c8ae3a8540de",
        "email_verified": True,
        "preferred_username": "testuser@bud.studio",
        "realm_access": {"roles": ["developer"]},
        "scope": "email profile",
        "iss": "https://keycloak.example.com/realms/bud-keycloak",
    }


class TestPlaygroundJITProvisioning:
    """Tests for JIT user provisioning in initialize_session_with_access_token."""

    @pytest.mark.asyncio
    async def test_existing_user_skips_jit(self, playground_service, test_user, test_tenant, test_tenant_client):
        """When user exists in DB, JIT provisioning should NOT be triggered."""
        with (
            patch.object(playground_service, "session"),
            patch("budapp.playground_ops.services.UserDataManager") as MockUDM,
            patch("budapp.playground_ops.services.KeycloakManager") as MockKM,
            patch("budapp.playground_ops.services.app_settings") as mock_settings,
        ):
            mock_settings.default_realm_name = "bud-keycloak"

            # UserDataManager returns tenant, tenant_client, then user (exists in DB)
            udm_instance = MockUDM.return_value
            udm_instance.retrieve_by_fields = AsyncMock(side_effect=[test_tenant, test_tenant_client, test_user])

            km_instance = MockKM.return_value
            km_instance.validate_token = AsyncMock(return_value={"sub": test_user.auth_id})

            # get_keycloak_user_by_id should NOT be called
            km_instance.get_keycloak_user_by_id = Mock()

            with contextlib.suppress(Exception):
                await playground_service.initialize_session_with_access_token(access_token="valid-access-token")

            # Verify get_keycloak_user_by_id was NOT called (no JIT needed)
            km_instance.get_keycloak_user_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_jit_provisions_user_when_not_in_db(
        self, playground_service, test_user, test_tenant, test_tenant_client, keycloak_user_dict
    ):
        """When user NOT in DB but exists in Keycloak, JIT provisioning should create user."""
        with (
            patch("budapp.playground_ops.services.UserDataManager") as MockUDM,
            patch("budapp.playground_ops.services.KeycloakManager") as MockKM,
            patch("budapp.playground_ops.services.AuthService") as MockAuthService,
            patch("budapp.playground_ops.services.app_settings") as mock_settings,
        ):
            mock_settings.default_realm_name = "bud-keycloak"

            udm_instance = MockUDM.return_value
            # Returns: tenant, tenant_client, None (user not found)
            udm_instance.retrieve_by_fields = AsyncMock(side_effect=[test_tenant, test_tenant_client, None])

            km_instance = MockKM.return_value
            km_instance.validate_token = AsyncMock(return_value={"sub": "3dd53c4e-7b00-445b-8be1-c8ae3a8540de"})
            km_instance.get_keycloak_user_by_id = Mock(return_value=keycloak_user_dict)

            auth_instance = MockAuthService.return_value
            auth_instance._create_user_from_keycloak = AsyncMock(return_value=test_user)

            with contextlib.suppress(Exception):
                await playground_service.initialize_session_with_access_token(access_token="valid-access-token")

            # Verify JIT provisioning was triggered
            km_instance.get_keycloak_user_by_id.assert_called_once_with(
                "3dd53c4e-7b00-445b-8be1-c8ae3a8540de", "bud-keycloak"
            )
            auth_instance._create_user_from_keycloak.assert_called_once_with(
                keycloak_user=keycloak_user_dict,
                tenant_client=test_tenant_client,
                tenant=test_tenant,
                realm_name="bud-keycloak",
            )

    @pytest.mark.asyncio
    async def test_jit_returns_404_when_user_not_in_keycloak(
        self, playground_service, test_tenant, test_tenant_client
    ):
        """When user NOT in DB and NOT in Keycloak, should return 404."""
        with (
            patch("budapp.playground_ops.services.UserDataManager") as MockUDM,
            patch("budapp.playground_ops.services.KeycloakManager") as MockKM,
            patch("budapp.playground_ops.services.app_settings") as mock_settings,
        ):
            mock_settings.default_realm_name = "bud-keycloak"

            udm_instance = MockUDM.return_value
            udm_instance.retrieve_by_fields = AsyncMock(side_effect=[test_tenant, test_tenant_client, None])

            km_instance = MockKM.return_value
            km_instance.validate_token = AsyncMock(return_value={"sub": "nonexistent-user-id"})
            km_instance.get_keycloak_user_by_id = Mock(return_value=None)

            with pytest.raises(ClientException) as exc_info:
                await playground_service.initialize_session_with_access_token(access_token="valid-access-token")

            assert exc_info.value.status_code == 404
            assert "identity provider" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_jit_race_condition_recovery(
        self, playground_service, test_user, test_tenant, test_tenant_client, keycloak_user_dict
    ):
        """When JIT provisioning fails due to race condition, should recover by re-querying DB."""
        with (
            patch("budapp.playground_ops.services.UserDataManager") as MockUDM,
            patch("budapp.playground_ops.services.KeycloakManager") as MockKM,
            patch("budapp.playground_ops.services.AuthService") as MockAuthService,
            patch("budapp.playground_ops.services.app_settings") as mock_settings,
        ):
            mock_settings.default_realm_name = "bud-keycloak"

            udm_instance = MockUDM.return_value
            # First 3 calls: tenant, tenant_client, None (user not found)
            # 4th call (re-check after race): returns user
            udm_instance.retrieve_by_fields = AsyncMock(side_effect=[test_tenant, test_tenant_client, None, test_user])

            km_instance = MockKM.return_value
            km_instance.validate_token = AsyncMock(return_value={"sub": "3dd53c4e-7b00-445b-8be1-c8ae3a8540de"})
            km_instance.get_keycloak_user_by_id = Mock(return_value=keycloak_user_dict)

            # Simulate race condition — IntegrityError from concurrent insert
            auth_instance = MockAuthService.return_value
            auth_instance._create_user_from_keycloak = AsyncMock(
                side_effect=IntegrityError("duplicate key value violates unique constraint", "params", "orig")
            )

            with contextlib.suppress(Exception):
                await playground_service.initialize_session_with_access_token(access_token="valid-access-token")

            # Verify the re-check was attempted (4th call to retrieve_by_fields)
            assert udm_instance.retrieve_by_fields.call_count == 4

    @pytest.mark.asyncio
    async def test_jit_non_race_error_returns_500(
        self, playground_service, test_tenant, test_tenant_client, keycloak_user_dict
    ):
        """When JIT fails with a non-IntegrityError, should return 500 immediately without re-querying DB."""
        with (
            patch("budapp.playground_ops.services.UserDataManager") as MockUDM,
            patch("budapp.playground_ops.services.KeycloakManager") as MockKM,
            patch("budapp.playground_ops.services.AuthService") as MockAuthService,
            patch("budapp.playground_ops.services.app_settings") as mock_settings,
        ):
            mock_settings.default_realm_name = "bud-keycloak"

            udm_instance = MockUDM.return_value
            # Only 3 calls: tenant, tenant_client, None (user not found)
            # No 4th call — non-race errors don't trigger DB re-query
            udm_instance.retrieve_by_fields = AsyncMock(side_effect=[test_tenant, test_tenant_client, None])

            km_instance = MockKM.return_value
            km_instance.validate_token = AsyncMock(return_value={"sub": "3dd53c4e-7b00-445b-8be1-c8ae3a8540de"})
            km_instance.get_keycloak_user_by_id = Mock(return_value=keycloak_user_dict)

            auth_instance = MockAuthService.return_value
            auth_instance._create_user_from_keycloak = AsyncMock(side_effect=Exception("database connection lost"))

            with pytest.raises(ClientException) as exc_info:
                await playground_service.initialize_session_with_access_token(access_token="valid-access-token")

            assert exc_info.value.status_code == 500
            assert "Failed to provision" in exc_info.value.message
            # Verify no re-query was attempted (only 3 calls, not 4)
            assert udm_instance.retrieve_by_fields.call_count == 3

    @pytest.mark.asyncio
    async def test_jit_race_condition_requery_fails_returns_500(
        self, playground_service, test_tenant, test_tenant_client, keycloak_user_dict
    ):
        """When IntegrityError race condition occurs but re-query also finds no user, should return 500."""
        with (
            patch("budapp.playground_ops.services.UserDataManager") as MockUDM,
            patch("budapp.playground_ops.services.KeycloakManager") as MockKM,
            patch("budapp.playground_ops.services.AuthService") as MockAuthService,
            patch("budapp.playground_ops.services.app_settings") as mock_settings,
        ):
            mock_settings.default_realm_name = "bud-keycloak"

            udm_instance = MockUDM.return_value
            # 4 calls: tenant, tenant_client, None (not found), None (re-query also fails)
            udm_instance.retrieve_by_fields = AsyncMock(side_effect=[test_tenant, test_tenant_client, None, None])

            km_instance = MockKM.return_value
            km_instance.validate_token = AsyncMock(return_value={"sub": "3dd53c4e-7b00-445b-8be1-c8ae3a8540de"})
            km_instance.get_keycloak_user_by_id = Mock(return_value=keycloak_user_dict)

            auth_instance = MockAuthService.return_value
            auth_instance._create_user_from_keycloak = AsyncMock(
                side_effect=IntegrityError("duplicate key", "params", "orig")
            )

            with pytest.raises(ClientException) as exc_info:
                await playground_service.initialize_session_with_access_token(access_token="valid-access-token")

            assert exc_info.value.status_code == 500
            assert "Failed to provision" in exc_info.value.message


class TestKeycloakGetUserById:
    """Tests for KeycloakManager.get_keycloak_user_by_id."""

    def test_returns_user_dict_when_found(self):
        """Should return user dict when user exists in Keycloak."""
        from budapp.commons.keycloak import KeycloakManager

        with patch.object(KeycloakManager, "get_realm_admin") as mock_get_admin:
            mock_admin = Mock()
            mock_admin.get_user.return_value = {
                "id": "test-uuid",
                "email": "test@bud.studio",
            }
            mock_get_admin.return_value = mock_admin

            km = KeycloakManager.__new__(KeycloakManager)
            result = km.get_keycloak_user_by_id("test-uuid", "bud-keycloak")

            assert result is not None
            assert result["id"] == "test-uuid"
            assert result["email"] == "test@bud.studio"
            mock_admin.get_user.assert_called_once_with("test-uuid")

    def test_returns_none_when_user_not_found(self):
        """Should return None when KeycloakGetError is raised."""
        from keycloak.exceptions import KeycloakGetError

        from budapp.commons.keycloak import KeycloakManager

        with patch.object(KeycloakManager, "get_realm_admin") as mock_get_admin:
            mock_admin = Mock()
            mock_admin.get_user.side_effect = KeycloakGetError(error_message="User not found", response_code=404)
            mock_get_admin.return_value = mock_admin

            km = KeycloakManager.__new__(KeycloakManager)
            result = km.get_keycloak_user_by_id("nonexistent-uuid", "bud-keycloak")

            assert result is None

    def test_raises_on_non_404_keycloak_error(self):
        """Should re-raise KeycloakGetError for non-404 errors (5xx, 403, etc.)."""
        from keycloak.exceptions import KeycloakGetError

        from budapp.commons.keycloak import KeycloakManager

        with patch.object(KeycloakManager, "get_realm_admin") as mock_get_admin:
            mock_admin = Mock()
            mock_admin.get_user.side_effect = KeycloakGetError(error_message="Forbidden", response_code=403)
            mock_get_admin.return_value = mock_admin

            km = KeycloakManager.__new__(KeycloakManager)
            with pytest.raises(KeycloakGetError):
                km.get_keycloak_user_by_id("test-uuid", "bud-keycloak")

    def test_raises_on_generic_exception(self):
        """Should re-raise unexpected exceptions."""
        from budapp.commons.keycloak import KeycloakManager

        with patch.object(KeycloakManager, "get_realm_admin") as mock_get_admin:
            mock_admin = Mock()
            mock_admin.get_user.side_effect = ConnectionError("Network error")
            mock_get_admin.return_value = mock_admin

            km = KeycloakManager.__new__(KeycloakManager)
            with pytest.raises(ConnectionError):
                km.get_keycloak_user_by_id("test-uuid", "bud-keycloak")
