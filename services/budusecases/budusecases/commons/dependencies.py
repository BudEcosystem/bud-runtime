"""Dependency injection functions for BudUseCases."""

from collections.abc import AsyncGenerator
from uuid import UUID

from budmicroframe.shared.psql_service import Database
from fastapi import Header
from sqlalchemy.orm import Session

# Default user ID for unauthenticated requests (shows only public resources)
_DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000000")


async def get_session() -> AsyncGenerator[Session, None]:
    """Get database session."""
    db = Database()
    session = db.get_session()
    try:
        yield session
    finally:
        db.close_session(session)


def get_current_user_id(x_user_id: str = Header(default="")) -> UUID:
    """Extract user ID from x-user-id header, defaulting to nil UUID."""
    if x_user_id:
        return UUID(x_user_id)
    return _DEFAULT_USER_ID


def get_current_project_id(x_project_id: str = Header(default="")) -> UUID | None:
    """Extract project ID from x-project-id header."""
    if x_project_id:
        return UUID(x_project_id)
    return None
