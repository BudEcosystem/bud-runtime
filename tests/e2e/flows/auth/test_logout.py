"""
E2E Tests for User Logout Flow.

Test Cases Covered:
- 4.1: Logout with valid tokens
- 4.2: Access token blacklisted after logout
- 4.3: Refresh token deleted from DB
- 4.4: Logout with already revoked token
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
class TestLogoutFlow:
    """Test cases for user logout flow."""

    # =========================================================================
    # P0 - Critical Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_logout_with_valid_tokens(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test 4.1: Logout with valid tokens.

        Flow:
        1. Login and get tokens (via fixture)
        2. Logout with refresh token and access token
        3. Verify successful logout response
        """
        user, tokens = authenticated_user
        auth = AuthHelper(budapp_client)

        # Logout
        result = await auth.logout(
            refresh_token=tokens.refresh_token,
            access_token=tokens.access_token,
        )

        # Assertions
        assert result.success, f"Logout failed: {result.error}"
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_access_token_blacklisted_after_logout(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test 4.2: Access token blacklisted after logout.

        Flow:
        1. Login and get tokens (via fixture)
        2. Verify access token works before logout
        3. Logout
        4. Attempt to use access token
        5. Verify 401 Unauthorized response
        """
        user, tokens = authenticated_user
        auth = AuthHelper(budapp_client)

        # Verify access token works before logout
        user_result = await auth.get_current_user(tokens.access_token)
        assert user_result.success, "Access token should work before logout"

        # Logout
        logout_result = await auth.logout(
            refresh_token=tokens.refresh_token,
            access_token=tokens.access_token,
        )
        assert logout_result.success, f"Logout failed: {logout_result.error}"

        # Attempt to use blacklisted access token
        blocked_result = await auth.get_current_user(tokens.access_token)

        # Assertions
        assert not blocked_result.success, (
            "Access token should be blacklisted after logout"
        )
        assert blocked_result.status_code == 401, (
            f"Expected 401, got {blocked_result.status_code}"
        )

    @pytest.mark.asyncio
    async def test_refresh_token_invalid_after_logout(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test 4.3: Refresh token deleted/invalid after logout.

        Flow:
        1. Login and get tokens (via fixture)
        2. Logout
        3. Attempt to use refresh token
        4. Verify 401 Unauthorized response
        """
        user, tokens = authenticated_user
        auth = AuthHelper(budapp_client)

        # Logout
        logout_result = await auth.logout(
            refresh_token=tokens.refresh_token,
            access_token=tokens.access_token,
        )
        assert logout_result.success, f"Logout failed: {logout_result.error}"

        # Attempt to use refresh token
        refresh_result = await auth.refresh_token(tokens.refresh_token)

        # Assertions
        assert not refresh_result.success, (
            "Refresh token should be invalid after logout"
        )
        assert refresh_result.status_code == 401, (
            f"Expected 401, got {refresh_result.status_code}"
        )

    # =========================================================================
    # P1 - Important Tests
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.priority_p1
    async def test_logout_with_already_revoked_token(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test 4.4: Logout with already revoked token.

        Flow:
        1. Login and get tokens
        2. Logout first time
        3. Attempt logout again with same token
        4. Verify graceful handling (200 OK or appropriate response)
        """
        user, tokens = authenticated_user
        auth = AuthHelper(budapp_client)

        # First logout
        first_logout = await auth.logout(
            refresh_token=tokens.refresh_token,
            access_token=tokens.access_token,
        )
        assert first_logout.success, f"First logout failed: {first_logout.error}"

        # Second logout with same token
        second_logout = await auth.logout(
            refresh_token=tokens.refresh_token,
        )

        # Should handle gracefully (might be 200 OK or 401)
        # The important thing is it doesn't crash
        assert second_logout.status_code in (200, 401, 404), (
            f"Unexpected status: {second_logout.status_code}"
        )

    @pytest.mark.asyncio
    @pytest.mark.priority_p1
    async def test_logout_without_access_token(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test logout with only refresh token (no access token in header).

        Flow:
        1. Login and get tokens
        2. Logout with only refresh token
        3. Verify successful logout
        4. Verify refresh token is invalidated
        """
        user, tokens = authenticated_user
        auth = AuthHelper(budapp_client)

        # Logout without access token
        logout_result = await auth.logout(
            refresh_token=tokens.refresh_token,
            # access_token not provided
        )
        assert logout_result.success, f"Logout failed: {logout_result.error}"

        # Verify refresh token is invalidated
        refresh_result = await auth.refresh_token(tokens.refresh_token)
        assert not refresh_result.success, (
            "Refresh token should be invalid after logout"
        )

    @pytest.mark.asyncio
    @pytest.mark.priority_p1
    async def test_can_login_again_after_logout(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test that user can login again after logout.

        Flow:
        1. Login and get tokens
        2. Logout
        3. Login again
        4. Verify new tokens are received
        """
        user, tokens = authenticated_user
        auth = AuthHelper(budapp_client)

        # Logout
        logout_result = await auth.logout(
            refresh_token=tokens.refresh_token,
            access_token=tokens.access_token,
        )
        assert logout_result.success, f"Logout failed: {logout_result.error}"

        # Login again
        login_result = await auth.login(
            email=user.email,
            password=user.password,
        )

        # Assertions
        assert login_result.success, f"Re-login failed: {login_result.error}"
        assert login_result.access_token, "Missing access_token after re-login"
        assert login_result.refresh_token, "Missing refresh_token after re-login"

        # New tokens should be different
        assert login_result.access_token != tokens.access_token
        assert login_result.refresh_token != tokens.refresh_token


@pytest.mark.e2e
@pytest.mark.priority_p0
@pytest.mark.auth
class TestLogoutValidation:
    """Test cases for logout input validation."""

    @pytest.mark.asyncio
    async def test_logout_without_refresh_token(
        self,
        budapp_client: httpx.AsyncClient,
    ):
        """Test logout without refresh token returns error."""
        response = await budapp_client.post(
            "/auth/logout",
            json={},
        )
        assert response.status_code in (400, 422), (
            f"Expected 400 or 422, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_logout_with_empty_refresh_token(
        self,
        budapp_client: httpx.AsyncClient,
    ):
        """Test logout with empty refresh token returns error."""
        response = await budapp_client.post(
            "/auth/logout",
            json={"refresh_token": ""},
        )
        assert response.status_code in (400, 401, 422), (
            f"Expected 400/401/422, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_logout_with_invalid_refresh_token(
        self,
        budapp_client: httpx.AsyncClient,
    ):
        """Test logout with invalid refresh token handles gracefully."""
        fake_token = f"invalid_token_{uuid4().hex}"

        response = await budapp_client.post(
            "/auth/logout",
            json={"refresh_token": fake_token},
        )

        # Should return error or success (graceful handling)
        assert response.status_code in (200, 400, 401, 404), (
            f"Unexpected status: {response.status_code}"
        )
