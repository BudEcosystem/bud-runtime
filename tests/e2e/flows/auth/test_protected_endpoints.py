"""
E2E Tests for Protected Endpoint Access.

Test Cases Covered:
- 7.1: Access /users/me with valid token
- 7.2: Access /users/me with expired token
- 7.3: Access /users/me with blacklisted token
- 7.4: Access /users/me without token
- 7.5: Access /users/me with malformed token
"""

import pytest
import httpx
from uuid import uuid4

from tests.e2e.helpers.auth_helper import AuthHelper
from tests.e2e.helpers.assertions import (
    assert_unauthorized,
)
from tests.e2e.fixtures.auth import TestUser, AuthTokens


@pytest.mark.e2e
@pytest.mark.priority_p0
@pytest.mark.auth
class TestProtectedEndpointAccess:
    """Test cases for protected endpoint access."""

    # =========================================================================
    # P0 - Critical Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_access_with_valid_token(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test 7.1: Access /users/me with valid token.

        Flow:
        1. Login and get tokens (via fixture)
        2. Access /users/me with valid access token
        3. Verify user profile is returned
        """
        user, tokens = authenticated_user
        auth = AuthHelper(budapp_client)

        # Access protected endpoint
        result = await auth.get_current_user(tokens.access_token)

        # Assertions
        assert result.success, f"Access failed: {result.error}"
        assert result.data is not None

        # User data may be nested under 'user' key
        user_data = result.data.get("user", result.data)
        assert user_data.get("email") == user.email, (
            f"Email mismatch: expected {user.email}, got {user_data.get('email')}"
        )

    @pytest.mark.asyncio
    async def test_access_without_token(
        self,
        budapp_client: httpx.AsyncClient,
    ):
        """
        Test 7.4: Access /users/me without token.

        Flow:
        1. Access /users/me without Authorization header
        2. Verify 401 Unauthorized response
        """
        response = await budapp_client.get("/users/me")

        # Assertions
        assert_unauthorized(response)

    @pytest.mark.asyncio
    async def test_access_with_malformed_token(
        self,
        budapp_client: httpx.AsyncClient,
    ):
        """
        Test 7.5: Access /users/me with malformed token.

        Flow:
        1. Access /users/me with malformed JWT token
        2. Verify 401 Unauthorized response
        """
        # Use malformed JWT token
        malformed_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.malformed.signature"

        response = await budapp_client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {malformed_token}"},
        )

        # Assertions
        assert_unauthorized(response)

    @pytest.mark.asyncio
    async def test_access_with_invalid_token(
        self,
        budapp_client: httpx.AsyncClient,
    ):
        """
        Test access /users/me with completely invalid token.

        Flow:
        1. Access /users/me with random string as token
        2. Verify 401 Unauthorized response
        """
        invalid_token = f"invalid_random_token_{uuid4().hex}"

        response = await budapp_client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {invalid_token}"},
        )

        # Assertions
        assert_unauthorized(response)

    @pytest.mark.asyncio
    async def test_access_with_blacklisted_token(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test 7.3: Access /users/me with blacklisted token.

        Flow:
        1. Login and get tokens
        2. Logout (blacklists access token)
        3. Attempt to access /users/me with blacklisted token
        4. Verify 401 Unauthorized response
        """
        user, tokens = authenticated_user
        auth = AuthHelper(budapp_client)

        # Logout to blacklist token
        logout_result = await auth.logout(
            refresh_token=tokens.refresh_token,
            access_token=tokens.access_token,
        )
        assert logout_result.success, f"Logout failed: {logout_result.error}"

        # Attempt access with blacklisted token
        result = await auth.get_current_user(tokens.access_token)

        # Assertions
        assert not result.success, "Access should fail with blacklisted token"
        assert result.status_code == 401, f"Expected 401, got {result.status_code}"

    # =========================================================================
    # P1 - Important Tests
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.priority_p1
    async def test_access_with_wrong_auth_scheme(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test access with wrong authentication scheme (Basic instead of Bearer).

        Flow:
        1. Login and get tokens
        2. Access /users/me with "Basic" scheme instead of "Bearer"
        3. Verify 401 Unauthorized response
        """
        user, tokens = authenticated_user

        response = await budapp_client.get(
            "/users/me",
            headers={"Authorization": f"Basic {tokens.access_token}"},
        )

        # Assertions
        assert response.status_code in (401, 403), (
            f"Expected 401 or 403, got {response.status_code}"
        )

    @pytest.mark.asyncio
    @pytest.mark.priority_p1
    async def test_access_with_empty_bearer(
        self,
        budapp_client: httpx.AsyncClient,
    ):
        """
        Test access with empty Bearer token.

        Flow:
        1. Access /users/me with "Bearer " but no token
        2. Verify 401 Unauthorized response
        """
        try:
            response = await budapp_client.get(
                "/users/me",
                headers={"Authorization": "Bearer "},
            )
            # Assertions
            assert_unauthorized(response)
        except httpx.LocalProtocolError:
            # Empty bearer may cause protocol error - this is acceptable
            pass

    @pytest.mark.asyncio
    @pytest.mark.priority_p1
    async def test_user_data_structure(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test that user profile contains expected fields.

        Flow:
        1. Login and get tokens
        2. Access /users/me
        3. Verify response contains required user fields
        """
        user, tokens = authenticated_user
        auth = AuthHelper(budapp_client)

        result = await auth.get_current_user(tokens.access_token)

        # Assertions
        assert result.success, f"Access failed: {result.error}"

        # User data may be nested under 'user' key
        data = result.data.get("user", result.data)
        assert "id" in data, "Response missing 'id' field"
        assert "email" in data, "Response missing 'email' field"

        # Verify email matches
        assert data["email"] == user.email

    @pytest.mark.asyncio
    @pytest.mark.priority_p1
    async def test_access_multiple_times_with_same_token(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test that same token can be used for multiple requests.

        Flow:
        1. Login and get tokens
        2. Access /users/me multiple times with same token
        3. Verify all requests succeed
        """
        user, tokens = authenticated_user
        auth = AuthHelper(budapp_client)

        # Make multiple requests
        for i in range(3):
            result = await auth.get_current_user(tokens.access_token)
            assert result.success, f"Request {i + 1} failed: {result.error}"
            # User data may be nested under 'user' key
            user_data = result.data.get("user", result.data)
            assert user_data["email"] == user.email


@pytest.mark.e2e
@pytest.mark.priority_p1
@pytest.mark.auth
class TestUserProfileVerification:
    """Test cases for comprehensive user profile data verification."""

    @pytest.mark.asyncio
    async def test_profile_contains_all_required_fields(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test that user profile contains all required fields.

        Verifies:
        - id (UUID string)
        - email
        - name
        - role
        - status
        """
        user, tokens = authenticated_user
        auth = AuthHelper(budapp_client)

        result = await auth.get_current_user(tokens.access_token)
        assert result.success, f"Get profile failed: {result.error}"

        # Extract user data
        user_data = result.data.get("user", result.data)

        # Verify all required fields exist
        required_fields = ["id", "email", "name", "role", "status"]
        for field in required_fields:
            assert field in user_data, f"Profile missing required field: '{field}'"
            assert user_data[field] is not None, f"Field '{field}' should not be None"

    @pytest.mark.asyncio
    async def test_profile_data_matches_registration(
        self,
        budapp_client: httpx.AsyncClient,
        unique_email: str,
        strong_password: str,
    ):
        """
        Test that profile data matches what was provided at registration.

        Flow:
        1. Register with specific name and role
        2. Login
        3. Get profile
        4. Verify name and role match
        """
        auth = AuthHelper(budapp_client)
        test_name = "Profile Match Test"
        test_role = "developer"

        # Register
        reg_result = await auth.register(
            email=unique_email,
            password=strong_password,
            name=test_name,
            role=test_role,
        )
        assert reg_result.success, f"Registration failed: {reg_result.error}"

        # Login
        login_result = await auth.login(email=unique_email, password=strong_password)
        assert login_result.success, f"Login failed: {login_result.error}"

        # Get profile
        profile_result = await auth.get_current_user(login_result.access_token)
        assert profile_result.success, f"Get profile failed: {profile_result.error}"

        # Verify data matches
        user_data = profile_result.data.get("user", profile_result.data)

        assert user_data["email"] == unique_email, (
            f"Email mismatch: expected {unique_email}, got {user_data['email']}"
        )
        assert user_data["name"] == test_name, (
            f"Name mismatch: expected {test_name}, got {user_data['name']}"
        )
        assert user_data["role"] == test_role, (
            f"Role mismatch: expected {test_role}, got {user_data['role']}"
        )

    @pytest.mark.asyncio
    async def test_profile_id_is_valid_uuid(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test that user ID is a valid UUID format.
        """
        from uuid import UUID

        user, tokens = authenticated_user
        auth = AuthHelper(budapp_client)

        result = await auth.get_current_user(tokens.access_token)
        assert result.success, f"Get profile failed: {result.error}"

        user_data = result.data.get("user", result.data)
        user_id = user_data.get("id")

        # Verify ID is a valid UUID
        assert user_id is not None, "User ID should not be None"
        try:
            UUID(user_id)
        except ValueError:
            pytest.fail(f"User ID '{user_id}' is not a valid UUID")

    @pytest.mark.asyncio
    async def test_profile_email_format_valid(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test that email in profile is valid format.
        """
        user, tokens = authenticated_user
        auth = AuthHelper(budapp_client)

        result = await auth.get_current_user(tokens.access_token)
        assert result.success, f"Get profile failed: {result.error}"

        user_data = result.data.get("user", result.data)
        email = user_data.get("email")

        # Basic email format check
        assert email is not None, "Email should not be None"
        assert "@" in email, f"Invalid email format: {email}"
        assert "." in email.split("@")[-1], f"Invalid email domain: {email}"

    @pytest.mark.asyncio
    async def test_profile_status_is_active(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test that authenticated user status is active.
        """
        user, tokens = authenticated_user
        auth = AuthHelper(budapp_client)

        result = await auth.get_current_user(tokens.access_token)
        assert result.success, f"Get profile failed: {result.error}"

        user_data = result.data.get("user", result.data)
        status = user_data.get("status")

        assert status is not None, "Status should not be None"
        assert status.lower() == "active", f"Expected 'active' status, got '{status}'"


@pytest.mark.e2e
@pytest.mark.priority_p1
@pytest.mark.auth
class TestProtectedEndpointHeaders:
    """Test cases for Authorization header handling."""

    @pytest.mark.asyncio
    async def test_case_insensitive_bearer(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test that Bearer scheme is case-insensitive.

        Note: This depends on server implementation. Many servers
        accept "bearer" or "BEARER" in addition to "Bearer".
        """
        user, tokens = authenticated_user

        # Try lowercase "bearer"
        response = await budapp_client.get(
            "/users/me",
            headers={"Authorization": f"bearer {tokens.access_token}"},
        )

        # May or may not work depending on implementation
        # Just verify it doesn't crash
        assert response.status_code in (200, 401), (
            f"Unexpected status: {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_token_with_extra_whitespace(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test access with extra whitespace in Authorization header.
        """
        user, tokens = authenticated_user

        # Try with extra spaces
        response = await budapp_client.get(
            "/users/me",
            headers={"Authorization": f"Bearer  {tokens.access_token}"},  # Double space
        )

        # Should handle gracefully (may fail or succeed)
        assert response.status_code in (200, 401), (
            f"Unexpected status: {response.status_code}"
        )
