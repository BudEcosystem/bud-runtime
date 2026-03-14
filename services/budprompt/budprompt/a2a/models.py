"""SQLAlchemy models for A2A protocol persistence."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, Integer, String, Text

from budprompt.commons import PSQLBase


class A2AContext(PSQLBase):
    """Stores multi-turn conversation context for A2A protocol sessions."""

    __tablename__ = "a2a_contexts"

    context_id = Column(String(255), primary_key=True)
    agent_id = Column(String(255), nullable=True)  # "prompt_id:vN"
    messages = Column(Text, nullable=False, default="[]")
    message_count = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    modified_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_a2a_contexts_agent_id", "agent_id"),
        Index("idx_a2a_contexts_modified_at", "modified_at"),
    )
