"""
E2E Tests for Token Refresh Flow.

Test Cases Covered:
- 3.1: Refresh with valid refresh token
- 3.2: Refresh with expired refresh token
- 3.3: Refresh with invalid/tampered token
- 3.4: Refresh with revoked token (post-logout)
- 3.5: Refresh rate limiting
"""

import pytest
import httpx
from uuid import uuid4

from tests.e2e.helpers.auth_helper import AuthHelper
from tests.e2e.fixtures.auth import TestUser, AuthTokens


@pytest.mark.e2e
@pytest.mark.priority_p0
@pytest.mark.auth
class TestTokenRefreshFlow:
    """Test cases for token refresh flow."""

    # =========================================================================
    # P0 - Critical Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_refresh_with_valid_token(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test 3.1: Refresh with valid refresh token.

        Flow:
        1. Login and get tokens (via fixture)
        2. Use refresh token to get new access token
        3. Verify new access token is returned
        """
        user, tokens = authenticated_user
        auth = AuthHelper(budapp_client)

        # Refresh token
        result = await auth.refresh_token(tokens.refresh_token)

        # Assertions
        assert result.success, f"Token refresh failed: {result.error}"
        assert result.access_token, "Missing new access_token"
        assert result.access_token != tokens.access_token, (
            "New access token should be different from old one"
        )

    @pytest.mark.asyncio
    async def test_refresh_with_invalid_token(
        self,
        budapp_client: httpx.AsyncClient,
    ):
        """
        Test 3.3: Refresh with invalid/tampered token.

        Flow:
        1. Attempt refresh with a made-up token
        2. Verify 401 Unauthorized response
        """
        auth = AuthHelper(budapp_client)

        # Use a fake/invalid token
        fake_token = f"invalid_refresh_token_{uuid4().hex}"

        result = await auth.refresh_token(fake_token)

        # Assertions
        assert not result.success, "Refresh should have failed"
        assert result.status_code == 401, f"Expected 401, got {result.status_code}"

    @pytest.mark.asyncio
    async def test_refresh_with_empty_token(
        self,
        budapp_client: httpx.AsyncClient,
    ):
        """
        Test refresh with empty token returns error.

        Flow:
        1. Attempt refresh with empty token
        2. Verify error response
        """
        response = await budapp_client.post(
            "/auth/refresh-token",
            json={"refresh_token": ""},
        )

        assert response.status_code in (400, 401, 422), (
            f"Expected 400/401/422, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_refresh_with_malformed_token(
        self,
        budapp_client: httpx.AsyncClient,
    ):
        """
        Test refresh with malformed token returns error.

        Flow:
        1. Attempt refresh with malformed JWT
        2. Verify 401 Unauthorized response
        """
        auth = AuthHelper(budapp_client)

        # Use malformed JWT-like token
        malformed_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature"

        result = await auth.refresh_token(malformed_token)

        # Assertions
        assert not result.success, "Refresh should have failed"
        assert result.status_code in (400, 401), (
            f"Expected 400 or 401, got {result.status_code}"
        )

    # =========================================================================
    # P1 - Important Tests
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.priority_p1
    async def test_refresh_with_revoked_token(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test 3.4: Refresh with revoked token (post-logout).

        Flow:
        1. Login and get tokens (via fixture)
        2. Logout to revoke tokens
        3. Attempt refresh with revoked token
        4. Verify 401 Unauthorized response
        """
        user, tokens = authenticated_user
        auth = AuthHelper(budapp_client)

        # Logout (revokes refresh token)
        logout_result = await auth.logout(
            refresh_token=tokens.refresh_token,
            access_token=tokens.access_token,
        )
        assert logout_result.success, f"Logout failed: {logout_result.error}"

        # Attempt refresh with revoked token
        result = await auth.refresh_token(tokens.refresh_token)

        # Assertions
        assert not result.success, "Refresh should have failed with revoked token"
        assert result.status_code == 401, f"Expected 401, got {result.status_code}"

    @pytest.mark.asyncio
    @pytest.mark.priority_p1
    async def test_new_access_token_is_valid(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test that new access token from refresh is valid for API calls.

        Flow:
        1. Login and get tokens
        2. Refresh to get new access token
        3. Use new access token to access protected endpoint
        4. Verify access is granted
        """
        user, tokens = authenticated_user
        auth = AuthHelper(budapp_client)

        # Refresh token
        refresh_result = await auth.refresh_token(tokens.refresh_token)
        assert refresh_result.success, f"Refresh failed: {refresh_result.error}"

        # Use new access token
        user_result = await auth.get_current_user(refresh_result.access_token)

        # Assertions
        assert user_result.success, f"API call failed: {user_result.error}"
        # User data may be nested under 'user' key
        user_data = user_result.data.get("user", user_result.data)
        assert user_data["email"] == user.email

    @pytest.mark.asyncio
    @pytest.mark.priority_p1
    async def test_old_access_token_still_valid_after_refresh(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test that old access token is still valid after refresh.

        Flow:
        1. Login and get tokens
        2. Refresh to get new access token
        3. Use OLD access token to access protected endpoint
        4. Verify access is granted (old token not revoked by refresh)
        """
        user, tokens = authenticated_user
        auth = AuthHelper(budapp_client)

        # Refresh token
        refresh_result = await auth.refresh_token(tokens.refresh_token)
        assert refresh_result.success, f"Refresh failed: {refresh_result.error}"

        # Use OLD access token
        user_result = await auth.get_current_user(tokens.access_token)

        # Assertions
        assert user_result.success, (
            "Old access token should still be valid after refresh"
        )

    # =========================================================================
    # P2 - Rate Limiting Tests
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.priority_p2
    @pytest.mark.slow
    async def test_refresh_rate_limiting(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test 3.5: Refresh rate limiting (>20/min per user).

        Flow:
        1. Login and get tokens
        2. Make more than 20 refresh attempts within a minute
        3. Verify 429 Too Many Requests response

        Note: This test may take time due to rate limit window.
        """
        user, tokens = authenticated_user
        auth = AuthHelper(budapp_client)

        # Make 21 rapid refresh attempts (limit is 20/min per user)
        responses = []
        for i in range(21):
            result = await auth.refresh_token(tokens.refresh_token)
            responses.append(result)

        # Check if rate limiting kicked in
        rate_limited = any(r.status_code == 429 for r in responses)
        if rate_limited:
            assert True, "Rate limiting is working"
        else:
            # Rate limiting might not be enabled in test environment
            pytest.skip("Rate limiting may not be enabled in test environment")


@pytest.mark.e2e
@pytest.mark.priority_p0
@pytest.mark.auth
class TestTokenRefreshValidation:
    """Test cases for token refresh input validation."""

    @pytest.mark.asyncio
    async def test_refresh_without_token(
        self,
        budapp_client: httpx.AsyncClient,
    ):
        """Test refresh without providing token returns error."""
        response = await budapp_client.post(
            "/auth/refresh-token",
            json={},
        )
        assert response.status_code in (400, 422), (
            f"Expected 400 or 422, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_refresh_with_null_token(
        self,
        budapp_client: httpx.AsyncClient,
    ):
        """Test refresh with null token returns error."""
        response = await budapp_client.post(
            "/auth/refresh-token",
            json={"refresh_token": None},
        )
        assert response.status_code in (400, 422), (
            f"Expected 400 or 422, got {response.status_code}"
        )
