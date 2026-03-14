"""Reusable FastAPI dependencies for A2A routes."""

from typing import Optional

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


_bearer_scheme = HTTPBearer(auto_error=False)


async def get_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),  # noqa: B008
    api_key_header: Optional[str] = Header(None, alias="api-key"),  # noqa: B008
) -> Optional[str]:
    """Extract API key from Bearer token or api-key header.

    Checked in order: Authorization: Bearer <token>, then api-key header.
    Returns None if neither is present (A2A auth is passthrough/optional).
    """
    if credentials and credentials.credentials:
        return credentials.credentials
    return api_key_header
