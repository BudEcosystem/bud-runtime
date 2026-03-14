"""PostgreSQL conversation context store for A2A protocol.

The A2A SDK provides DatabaseTaskStore for task state but NO conversation context store.
This custom store persists multi-turn conversation history keyed by context_id.
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from .models import A2AContext


logger = logging.getLogger(__name__)


class PostgreSQLContextStore:
    """Async PostgreSQL-backed conversation context store.

    No hard message limit — the user controls context length via client-side configuration.
    """

    def __init__(self) -> None:
        """Initialize with no session maker — call initialize() before use."""
        self._session_maker: async_sessionmaker | None = None

    def initialize(self, engine: AsyncEngine) -> None:
        """Create session maker from shared async engine.

        Note: Table is managed by Alembic, not create_all().
        """
        self._session_maker = async_sessionmaker(engine, expire_on_commit=False)
        logger.info("PostgreSQLContextStore initialized")

    def _ensure_initialized(self) -> async_sessionmaker:
        if self._session_maker is None:
            raise RuntimeError("ContextStore not initialized — call initialize() first")
        return self._session_maker

    async def get_messages(self, context_id: str) -> list[dict]:
        """Load conversation history for a context. Returns empty list if not found."""
        session_maker = self._ensure_initialized()
        async with session_maker() as session:
            row = await session.get(A2AContext, context_id)
            if row is None:
                return []
            return json.loads(row.messages)

    async def save_messages(
        self,
        context_id: str,
        messages: list[dict],
        agent_id: str | None = None,
    ) -> None:
        """Upsert conversation history (insert or update)."""
        session_maker = self._ensure_initialized()
        async with session_maker() as session:
            row = await session.get(A2AContext, context_id)
            if row is None:
                row = A2AContext(
                    context_id=context_id,
                    agent_id=agent_id,
                    messages=json.dumps(messages, default=str),
                    message_count=len(messages),
                )
                session.add(row)
            else:
                row.messages = json.dumps(messages, default=str)
                row.message_count = len(messages)
                row.modified_at = datetime.now(timezone.utc)
                if agent_id:
                    row.agent_id = agent_id
            await session.commit()

    async def delete(self, context_id: str) -> bool:
        """Delete conversation history. Returns True if found."""
        session_maker = self._ensure_initialized()
        async with session_maker() as session:
            row = await session.get(A2AContext, context_id)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

    async def cleanup_stale(self, ttl_hours: int) -> int:
        """Delete contexts with modified_at older than TTL. Returns count deleted."""
        session_maker = self._ensure_initialized()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
        async with session_maker() as session:
            stmt = delete(A2AContext).where(A2AContext.modified_at < cutoff)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount
