"""
Authentication fixtures for E2E tests.

Provides fixtures for user registration, login, and token management.
"""

import os
from typing import Dict, Any, Optional
from uuid import uuid4
from dataclasses import dataclass

import pytest
import httpx


@dataclass
class AuthTokens:
    """Container for authentication tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"

    @property
    def auth_header(self) -> Dict[str, str]:
        """Get authorization header."""
        return {"Authorization": f"{self.token_type} {self.access_token}"}


@dataclass
class TestUser:
    """Container for test user data."""

    # Prevent pytest from treating this as a test class
    __test__ = False

    email: str
    password: str
    name: str = "Test User"
    role: str = "developer"

    @property
    def registration_data(self) -> Dict[str, str]:
        """Get data for user registration."""
        return {
            "email": self.email,
            "password": self.password,
            "name": self.name,
            "role": self.role,
        }

    @property
    def login_data(self) -> Dict[str, str]:
        """Get data for login."""
        return {
            "email": self.email,
            "password": self.password,
        }


@dataclass
class AdminUser:
    """Container for admin user data."""

    # Prevent pytest from treating this as a test class
    __test__ = False

    email: str
    password: str
    user_id: str = ""
    name: str = "Admin User"
    role: str = "admin"

    @property
    def registration_data(self) -> Dict[str, str]:
        """Get data for user registration."""
        return {
            "email": self.email,
            "password": self.password,
            "name": self.name,
            "role": self.role,
        }

    @property
    def login_data(self) -> Dict[str, str]:
        """Get data for login."""
        return {
            "email": self.email,
            "password": self.password,
        }


@pytest.fixture
def unique_email() -> str:
    """Generate a unique email address for testing."""
    return f"test_{uuid4().hex[:8]}@example.com"


@pytest.fixture
def strong_password() -> str:
    """Generate a strong password for testing."""
    return "TestP@ssw0rd123!"


@pytest.fixture
def weak_password() -> str:
    """Return a weak password for negative testing."""
    return "weak"


@pytest.fixture
def test_user_data(unique_email, strong_password) -> TestUser:
    """Create test user data with unique credentials."""
    return TestUser(
        email=unique_email,
        password=strong_password,
    )


@pytest.fixture
def admin_user_credentials() -> Dict[str, str]:
    """Get admin user credentials from environment."""
    return {
        "email": os.getenv("E2E_ADMIN_USER_EMAIL", "admin@example.com"),
        "password": os.getenv("E2E_ADMIN_USER_PASSWORD", "AdminPassword123!"),
    }


@pytest.fixture
async def registered_user(
    budapp_client: httpx.AsyncClient,
    test_user_data: TestUser,
) -> TestUser:
    """
    Register a new test user.

    Returns the test user data after successful registration.
    """
    response = await budapp_client.post(
        "/auth/register",
        json=test_user_data.registration_data,
    )

    if response.status_code not in (200, 201):
        # Check if user already exists (409 Conflict)
        if response.status_code == 409:
            # User already exists, return the data
            return test_user_data
        raise AssertionError(
            f"Failed to register user: {response.status_code} - {response.text}"
        )

    return test_user_data


@pytest.fixture
async def authenticated_user(
    budapp_client: httpx.AsyncClient,
    registered_user: TestUser,
) -> tuple[TestUser, AuthTokens]:
    """
    Get an authenticated test user with tokens.

    Returns tuple of (TestUser, AuthTokens).
    """
    response = await budapp_client.post(
        "/auth/login",
        json=registered_user.login_data,
    )

    if response.status_code != 200:
        raise AssertionError(
            f"Failed to login: {response.status_code} - {response.text}"
        )

    data = response.json()
    token_data = data.get("token", data)  # Handle nested token structure
    tokens = AuthTokens(
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
    )

    return registered_user, tokens


@pytest.fixture
async def auth_tokens(authenticated_user) -> AuthTokens:
    """Get authentication tokens for a test user."""
    _, tokens = authenticated_user
    return tokens


@pytest.fixture
async def auth_headers(auth_tokens: AuthTokens) -> Dict[str, str]:
    """Get authorization headers for authenticated requests."""
    return auth_tokens.auth_header


@pytest.fixture
async def authenticated_admin_user(
    budapp_client: httpx.AsyncClient,
    admin_user_credentials: Dict[str, str],
) -> tuple[AdminUser, AuthTokens]:
    """
    Get an authenticated admin user with tokens.

    Uses the super admin credentials from environment.
    Returns tuple of (AdminUser, AuthTokens).
    """
    response = await budapp_client.post(
        "/auth/login",
        json=admin_user_credentials,
    )

    if response.status_code != 200:
        raise AssertionError(
            f"Failed to login admin: {response.status_code} - {response.text}"
        )

    data = response.json()
    token_data = data.get("token", data)  # Handle nested token structure

    admin = AdminUser(
        email=admin_user_credentials["email"],
        password=admin_user_credentials["password"],
        user_id=data.get("user", {}).get("id", ""),
    )

    tokens = AuthTokens(
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
    )

    return admin, tokens
