"""Provides utility functions for managing the database connection.

Database module for budpipeline persistence (002-pipeline-event-persistence).
Uses budmicroframe patterns for consistent database configuration.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from pydantic import PostgresDsn
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from budpipeline.commons.config import app_settings, secrets_settings

# Constraint naming convention to fix alembic autogenerate command issues
# https://docs.sqlalchemy.org/en/20/core/constraints.html#constraint-naming-conventions
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata_obj = MetaData(naming_convention=convention)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    metadata = metadata_obj


def get_async_engine():
    """Create and return an async SQLAlchemy engine instance.

    Uses DATABASE_URL environment variable if available (docker-compose),
    otherwise constructs from individual configuration settings.
    """
    import os

    # Try DATABASE_URL first (docker-compose), then fall back to building from config
    postgres_url = os.environ.get("DATABASE_URL")
    if not postgres_url:
        # Build async PostgreSQL URL from config settings
        postgres_url = PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=secrets_settings.psql_user,
            password=secrets_settings.psql_password,
            host=app_settings.psql_host,
            port=app_settings.psql_port,
            path=app_settings.psql_dbname,
        ).__str__()

    return create_async_engine(
        postgres_url,
        pool_size=app_settings.psql_pool_size,
        max_overflow=app_settings.psql_max_overflow,
        pool_pre_ping=app_settings.psql_pool_pre_ping,
        pool_recycle=app_settings.psql_pool_recycle,
        pool_timeout=app_settings.psql_pool_timeout,
        connect_args={"timeout": app_settings.psql_connect_timeout},
        echo=app_settings.debug,
    )


# Create async engine
engine = get_async_engine()

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions.

    Yields:
        AsyncSession: An async SQLAlchemy session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables.

    Note: In production, use Alembic migrations instead.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for getting async database sessions.

    Use this for non-FastAPI contexts (e.g., event handlers, background tasks).
    For FastAPI endpoints, use get_db() dependency instead.

    Example:
        async with get_db_session() as session:
            result = await session.execute(query)
            await session.commit()

    Yields:
        AsyncSession: An async SQLAlchemy session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
