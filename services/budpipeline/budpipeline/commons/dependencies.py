"""FastAPI dependencies for budpipeline.

This module provides reusable dependencies for request handling,
including user context extraction from headers.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import Header, Request


@dataclass
class UserContext:
    """User context extracted from request headers or body.

    Attributes:
        user_id: The user's UUID, or None for unauthenticated/system requests.
        is_system: True if this is a system-level request (no user context).
    """

    user_id: UUID | None
    is_system: bool = False

    @property
    def user_id_str(self) -> str | None:
        """Get user_id as string, or None if not set."""
        return str(self.user_id) if self.user_id else None


async def get_user_context(
    x_user_id: str | None = Header(None, alias="X-User-ID"),
) -> UserContext:
    """Extract user context from request headers.

    This dependency resolves the user ID from the X-User-ID header,
    which is typically set by budapp after JWT validation.

    For direct service-to-service calls (via Dapr), the user_id may be
    passed in the request body instead - use resolve_user_id_from_body()
    for those cases.

    Args:
        x_user_id: User ID from X-User-ID header.

    Returns:
        UserContext with user_id if present, otherwise is_system=True.
    """
    if x_user_id:
        try:
            return UserContext(user_id=UUID(x_user_id))
        except ValueError:
            # Invalid UUID format - treat as no user context
            pass

    return UserContext(user_id=None, is_system=True)


def resolve_user_id_from_body(body: dict[str, Any]) -> UUID | None:
    """Extract user_id from request body for service-to-service calls.

    When budapp proxies requests to budpipeline via Dapr, the user_id
    may be included in the request body rather than headers.

    Args:
        body: The request body dict.

    Returns:
        UUID of the user if valid, None otherwise.
    """
    user_id = body.get("user_id")
    if user_id:
        try:
            return UUID(user_id)
        except (ValueError, TypeError):
            pass
    return None


async def get_user_context_with_body(
    request: Request,
    x_user_id: str | None = Header(None, alias="X-User-ID"),
) -> UserContext:
    """Extract user context from headers or request body.

    This dependency first checks the X-User-ID header, then falls back
    to looking for user_id in the request body (for service-to-service calls).

    Args:
        request: The FastAPI request object.
        x_user_id: User ID from X-User-ID header.

    Returns:
        UserContext with user_id if found, otherwise is_system=True.
    """
    # First try header
    if x_user_id:
        try:
            return UserContext(user_id=UUID(x_user_id))
        except ValueError:
            pass

    # Try to get from body for POST/PUT requests
    if request.method in ("POST", "PUT", "PATCH"):
        try:
            body = await request.json()
            user_id = resolve_user_id_from_body(body)
            if user_id:
                return UserContext(user_id=user_id)
        except Exception:
            # Body parsing failed - continue without user context
            pass

    return UserContext(user_id=None, is_system=True)
