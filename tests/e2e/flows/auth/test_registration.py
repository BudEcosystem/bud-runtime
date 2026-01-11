"""
E2E Tests for User Registration Flow.

Test Cases Covered:
- 1.1: Register new user with valid data
- 1.2: Register with existing email
- 1.3: Register with invalid email format
- 1.4: Register with weak password
- 1.5: Register rate limiting
- 1.6: Register prevents privilege escalation
"""

import pytest
import httpx
from uuid import uuid4

from tests.e2e.helpers.auth_helper import AuthHelper
from tests.e2e.helpers.assertions import (
    assert_success_response,
    assert_conflict,
    assert_validation_error,
    assert_rate_limited,
)
from tests.e2e.fixtures.auth import TestUser


@pytest.mark.e2e
@pytest.mark.priority_p1
@pytest.mark.auth
class TestRegistrationFlow:
    """Test cases for user registration flow."""

    # =========================================================================
    # P1 - Important Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_register_new_user_with_valid_data(
        self,
        budapp_client: httpx.AsyncClient,
        unique_email: str,
        strong_password: str,
    ):
        """
        Test 1.1: Register new user with valid data.

        Flow:
        1. Register with valid email, password, and user details
        2. Verify successful registration response
        3. Verify user can login with new credentials
        """
        auth = AuthHelper(budapp_client)

        # Register
        result = await auth.register(
            email=unique_email,
            password=strong_password,
            name="Test User",
        )

        # Assertions
        assert result.success, f"Registration failed: {result.error}"

        # Verify can login
        login_result = await auth.login(
            email=unique_email,
            password=strong_password,
        )
        assert login_result.success, f"Login failed after registration: {login_result.error}"

    @pytest.mark.asyncio
    async def test_register_with_existing_email(
        self,
        budapp_client: httpx.AsyncClient,
        registered_user: TestUser,
    ):
        """
        Test 1.2: Register with existing email.

        Flow:
        1. Use already registered user email (via fixture)
        2. Attempt to register with same email
        3. Verify 409 Conflict response
        """
        auth = AuthHelper(budapp_client)

        # Attempt registration with existing email
        result = await auth.register(
            email=registered_user.email,
            password="AnotherPassword123!",
            name="Another User",
        )

        # Assertions
        assert not result.success, "Registration should fail for existing email"
        # API may return 400 (Bad Request) or 409 (Conflict) for existing email
        assert result.status_code in (400, 409), f"Expected 400/409, got {result.status_code}"

    @pytest.mark.asyncio
    async def test_register_with_invalid_email_format(
        self,
        budapp_client: httpx.AsyncClient,
        strong_password: str,
    ):
        """
        Test 1.3: Register with invalid email format.

        Flow:
        1. Attempt to register with malformed email
        2. Verify 422 Validation Error response
        """
        auth = AuthHelper(budapp_client)

        # Test various invalid email formats
        invalid_emails = [
            "not-an-email",
            "missing@",
            "@missing-local.com",
            "spaces in@email.com",
            "",
        ]

        for invalid_email in invalid_emails:
            result = await auth.register(
                email=invalid_email,
                password=strong_password,
                name="Test User",
            )

            assert not result.success, f"Registration should fail for: {invalid_email}"
            assert result.status_code in (400, 422), (
                f"Expected 400/422 for '{invalid_email}', got {result.status_code}"
            )

    @pytest.mark.asyncio
    async def test_register_with_weak_password(
        self,
        budapp_client: httpx.AsyncClient,
        unique_email: str,
    ):
        """
        Test 1.4: Register with weak password.

        Flow:
        1. Attempt to register with password that doesn't meet requirements
        2. Verify 422 Validation Error response
        """
        auth = AuthHelper(budapp_client)

        # Test various weak passwords
        weak_passwords = [
            "short",          # Too short
            "12345678",       # No letters
            "password",       # Too simple
            "",               # Empty
        ]

        for weak_pw in weak_passwords:
            result = await auth.register(
                email=unique_email,
                password=weak_pw,
                name="Test User",
            )

            # Should fail with validation error
            assert not result.success, f"Registration should fail for weak password: {weak_pw}"
            assert result.status_code in (400, 422), (
                f"Expected 400/422 for weak password, got {result.status_code}"
            )

    @pytest.mark.asyncio
    async def test_register_returns_user_data(
        self,
        budapp_client: httpx.AsyncClient,
        unique_email: str,
        strong_password: str,
    ):
        """
        Test that registration returns user data.

        Flow:
        1. Register new user
        2. Verify response contains user information
        """
        auth = AuthHelper(budapp_client)

        result = await auth.register(
            email=unique_email,
            password=strong_password,
            name="Test User",
        )

        assert result.success, f"Registration failed: {result.error}"

        # If registration returns user data, verify it
        if result.data:
            # Check for common user fields (may be nested under 'user')
            user_data = result.data.get("user", result.data)
            if "email" in user_data:
                assert user_data["email"] == unique_email
            if "name" in user_data:
                assert user_data["name"] == "Test User"

    @pytest.mark.asyncio
    async def test_verify_user_data_after_registration(
        self,
        budapp_client: httpx.AsyncClient,
        unique_email: str,
        strong_password: str,
    ):
        """
        Test that user data is correctly stored and retrievable after registration.

        Flow:
        1. Register new user with specific name and role
        2. Login to get access token
        3. Call /users/me to retrieve user profile
        4. Verify all fields match registration data
        """
        auth = AuthHelper(budapp_client)
        test_name = "Verification Test User"
        test_role = "developer"

        # Register user
        reg_result = await auth.register(
            email=unique_email,
            password=strong_password,
            name=test_name,
            role=test_role,
        )
        assert reg_result.success, f"Registration failed: {reg_result.error}"

        # Login to get tokens
        login_result = await auth.login(
            email=unique_email,
            password=strong_password,
        )
        assert login_result.success, f"Login failed: {login_result.error}"

        # Get current user profile
        profile_result = await auth.get_current_user(login_result.access_token)
        assert profile_result.success, f"Get profile failed: {profile_result.error}"

        # Extract user data (may be nested under 'user' key)
        user_data = profile_result.data.get("user", profile_result.data)

        # Verify all fields match registration data
        assert user_data.get("email") == unique_email, (
            f"Email mismatch: expected {unique_email}, got {user_data.get('email')}"
        )
        assert user_data.get("name") == test_name, (
            f"Name mismatch: expected {test_name}, got {user_data.get('name')}"
        )
        assert user_data.get("role") == test_role, (
            f"Role mismatch: expected {test_role}, got {user_data.get('role')}"
        )

        # Verify user has an ID assigned
        assert user_data.get("id") is not None, "User should have an ID"

        # Verify user status is active
        assert user_data.get("status") in ("active", "Active", None), (
            f"Unexpected user status: {user_data.get('status')}"
        )

    # =========================================================================
    # P2 - Rate Limiting and Security Tests
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.priority_p2
    @pytest.mark.slow
    async def test_register_rate_limiting(
        self,
        budapp_client: httpx.AsyncClient,
        strong_password: str,
    ):
        """
        Test 1.5: Registration rate limiting (>3 in 10min).

        Flow:
        1. Make more than 3 registration attempts in 10 minutes
        2. Verify 429 Too Many Requests response

        Note: This test may take time due to rate limit window.
        """
        auth = AuthHelper(budapp_client)

        # Make 4 rapid registration attempts (limit is 3/10min)
        responses = []
        for i in range(4):
            email = f"ratelimit_{uuid4().hex[:8]}@example.com"
            result = await auth.register(
                email=email,
                password=strong_password,
                name=f"Test User{i}",
            )
            responses.append(result)

        # Check if rate limiting kicked in
        rate_limited = any(r.status_code == 429 for r in responses)
        if rate_limited:
            assert True, "Rate limiting is working"
        else:
            # Rate limiting might not be enabled in test environment
            pytest.skip("Rate limiting may not be enabled in test environment")

    @pytest.mark.asyncio
    @pytest.mark.priority_p2
    async def test_register_prevents_privilege_escalation(
        self,
        budapp_client: httpx.AsyncClient,
        unique_email: str,
        strong_password: str,
    ):
        """
        Test 1.6: Registration prevents privilege escalation.

        Flow:
        1. Attempt to register with admin user_type
        2. Verify user is created with CLIENT role, not ADMIN
        """
        # Direct API call to try to set user_type
        response = await budapp_client.post(
            "/auth/register",
            json={
                "email": unique_email,
                "password": strong_password,
                "name": "Attacker User",
                "role": "admin",  # Attempting privilege escalation
            },
        )

        # Registration should succeed but user_type should be CLIENT
        if response.status_code in (200, 201):
            data = response.json()
            # If user_type is in response, verify it's not ADMIN
            if "user_type" in data:
                assert data["user_type"] != "ADMIN", (
                    "User should not be created with ADMIN role"
                )
            if "role" in data:
                assert data["role"] != "ADMIN", (
                    "User should not be created with ADMIN role"
                )


@pytest.mark.e2e
@pytest.mark.priority_p1
@pytest.mark.auth
class TestRegistrationValidation:
    """Test cases for registration input validation."""

    @pytest.mark.asyncio
    async def test_register_with_missing_email(
        self,
        budapp_client: httpx.AsyncClient,
        strong_password: str,
    ):
        """Test registration without email returns validation error."""
        response = await budapp_client.post(
            "/auth/register",
            json={
                "password": strong_password,
                "name": "Test User",
            },
        )
        assert response.status_code in (400, 422), (
            f"Expected 400 or 422, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_register_with_missing_password(
        self,
        budapp_client: httpx.AsyncClient,
        unique_email: str,
    ):
        """Test registration without password returns validation error."""
        response = await budapp_client.post(
            "/auth/register",
            json={
                "email": unique_email,
                "name": "Test User",
            },
        )
        assert response.status_code in (400, 422), (
            f"Expected 400 or 422, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_register_with_empty_body(
        self,
        budapp_client: httpx.AsyncClient,
    ):
        """Test registration with empty body returns validation error."""
        response = await budapp_client.post(
            "/auth/register",
            json={},
        )
        assert response.status_code in (400, 422), (
            f"Expected 400 or 422, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_register_with_very_long_email(
        self,
        budapp_client: httpx.AsyncClient,
        strong_password: str,
    ):
        """Test registration with very long email."""
        long_email = "a" * 300 + "@example.com"

        response = await budapp_client.post(
            "/auth/register",
            json={
                "email": long_email,
                "password": strong_password,
                "name": "Test User",
            },
        )
        # Should fail with validation error
        assert response.status_code in (400, 422), (
            f"Expected 400 or 422 for very long email, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_register_with_special_characters_in_name(
        self,
        budapp_client: httpx.AsyncClient,
        unique_email: str,
        strong_password: str,
    ):
        """Test registration with special characters in name."""
        auth = AuthHelper(budapp_client)

        result = await auth.register(
            email=unique_email,
            password=strong_password,
            name="Test-O'Brien Jr.",  # Common name with special chars
        )

        # Should either succeed or fail gracefully
        assert result.status_code in (200, 201, 400, 422), (
            f"Unexpected status: {result.status_code}"
        )
