"""FastAPI dependency for API key authentication.

Provides a reusable dependency that validates an API key (Bearer token)
and returns project context. Used by SDK-facing endpoints that authenticate
via API key rather than JWT.
"""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from budapp.commons import logging
from budapp.commons.dependencies import get_session
from budapp.credential_ops.services import CredentialService


logger = logging.get_logger(__name__)

api_key_security = HTTPBearer()


@dataclass
class APIKeyContext:
    """Context extracted from a validated API key."""

    project_id: str
    api_key_id: str
    user_id: str | None


async def get_api_key_context(
    token: Annotated[HTTPAuthorizationCredentials, Depends(api_key_security)],
    session: Session = Depends(get_session),
) -> APIKeyContext:
    """Validate an API key and return project context.

    Mirrors the ``get_current_user`` pattern from ``dependencies.py`` but
    authenticates via API key instead of JWT.

    Args:
        token: Bearer token from the Authorization header.
        session: Database session.

    Returns:
        APIKeyContext with project_id, api_key_id, user_id.

    Raises:
        HTTPException: 401 if the API key is invalid.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "Bearer"},
    )

    context = await CredentialService(session).validate_api_key_and_get_context(token.credentials)
    if context is None:
        raise credentials_exception

    return APIKeyContext(
        project_id=context["api_key_project_id"],
        api_key_id=context.get("api_key_id", ""),
        user_id=context.get("user_id"),
    )
