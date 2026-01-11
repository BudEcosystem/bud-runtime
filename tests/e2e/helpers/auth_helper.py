"""
Authentication helper for E2E tests.

Provides utility functions for auth-related operations.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass

import httpx


@dataclass
class AuthResponse:
    """Container for authentication response data."""

    status_code: int
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def access_token(self) -> Optional[str]:
        if not self.data:
            return None
        # Handle nested token structure (data.token.access_token)
        token_data = self.data.get("token", self.data)
        return token_data.get("access_token")

    @property
    def refresh_token(self) -> Optional[str]:
        if not self.data:
            return None
        # Handle nested token structure (data.token.refresh_token)
        token_data = self.data.get("token", self.data)
        return token_data.get("refresh_token")


class AuthHelper:
    """Helper class for authentication operations."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def register(
        self,
        email: str,
        password: str,
        name: str = "Test User",
        role: str = "developer",
    ) -> AuthResponse:
        """
        Register a new user.

        Args:
            email: User email address
            password: User password
            name: User full name
            role: User role (developer, admin, devops, tester)

        Returns:
            AuthResponse with registration result
        """
        payload = {
            "email": email,
            "password": password,
            "name": name,
            "role": role,
        }

        response = await self.client.post("/auth/register", json=payload)

        if response.status_code in (200, 201):
            return AuthResponse(
                status_code=response.status_code,
                data=response.json(),
            )
        return AuthResponse(
            status_code=response.status_code,
            error=response.text,
        )

    async def login(
        self,
        email: str,
        password: str,
        remember_me: bool = False,
    ) -> AuthResponse:
        """
        Login a user.

        Args:
            email: User email address
            password: User password
            remember_me: Whether to extend session duration

        Returns:
            AuthResponse with login result
        """
        payload = {
            "email": email,
            "password": password,
        }
        if remember_me:
            payload["remember_me"] = True

        response = await self.client.post("/auth/login", json=payload)

        if response.status_code == 200:
            return AuthResponse(
                status_code=response.status_code,
                data=response.json(),
            )
        return AuthResponse(
            status_code=response.status_code,
            error=response.text,
        )

    async def logout(
        self,
        refresh_token: str,
        access_token: Optional[str] = None,
    ) -> AuthResponse:
        """
        Logout a user.

        Args:
            refresh_token: User refresh token
            access_token: Optional access token for blacklisting

        Returns:
            AuthResponse with logout result
        """
        headers = {}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        response = await self.client.post(
            "/auth/logout",
            json={"refresh_token": refresh_token},
            headers=headers,
        )

        if response.status_code == 200:
            return AuthResponse(
                status_code=response.status_code,
                data=response.json() if response.text else {},
            )
        return AuthResponse(
            status_code=response.status_code,
            error=response.text,
        )

    async def refresh_token(self, refresh_token: str) -> AuthResponse:
        """
        Refresh an access token.

        Args:
            refresh_token: User refresh token

        Returns:
            AuthResponse with new access token
        """
        response = await self.client.post(
            "/auth/refresh-token",
            json={"refresh_token": refresh_token},
        )

        if response.status_code == 200:
            return AuthResponse(
                status_code=response.status_code,
                data=response.json(),
            )
        return AuthResponse(
            status_code=response.status_code,
            error=response.text,
        )

    async def get_current_user(self, access_token: str) -> AuthResponse:
        """
        Get current user profile.

        Args:
            access_token: User access token

        Returns:
            AuthResponse with user data
        """
        response = await self.client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if response.status_code == 200:
            return AuthResponse(
                status_code=response.status_code,
                data=response.json(),
            )
        return AuthResponse(
            status_code=response.status_code,
            error=response.text,
        )

    async def request_password_reset(self, email: str) -> AuthResponse:
        """
        Request password reset.

        Args:
            email: User email address

        Returns:
            AuthResponse with reset request result
        """
        response = await self.client.post(
            "/users/reset-password",
            json={"email": email},
        )

        if response.status_code == 200:
            return AuthResponse(
                status_code=response.status_code,
                data=response.json(),
            )
        return AuthResponse(
            status_code=response.status_code,
            error=response.text,
        )

    async def validate_reset_token(self, token: str) -> AuthResponse:
        """
        Validate password reset token.

        Args:
            token: Password reset token

        Returns:
            AuthResponse with validation result
        """
        response = await self.client.post(
            "/users/validate-reset-token",
            json={"token": token},
        )

        if response.status_code == 200:
            return AuthResponse(
                status_code=response.status_code,
                data=response.json(),
            )
        return AuthResponse(
            status_code=response.status_code,
            error=response.text,
        )

    async def reset_password_with_token(
        self,
        token: str,
        new_password: str,
        confirm_password: str = None,
    ) -> AuthResponse:
        """
        Reset password using token.

        Args:
            token: Password reset token
            new_password: New password
            confirm_password: Password confirmation (defaults to new_password)

        Returns:
            AuthResponse with reset result
        """
        response = await self.client.post(
            "/users/reset-password-with-token",
            json={
                "token": token,
                "new_password": new_password,
                "confirm_password": confirm_password or new_password,
            },
        )

        if response.status_code == 200:
            return AuthResponse(
                status_code=response.status_code,
                data=response.json() if response.text else {},
            )
        return AuthResponse(
            status_code=response.status_code,
            error=response.text,
        )
