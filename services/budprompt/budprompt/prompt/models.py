#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""Database models for prompt storage."""

from budmicroframe.shared.psql_service import PSQLBase, TimestampMixin
from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship


class Prompt(PSQLBase, TimestampMixin):
    """Prompt model for permanent storage."""

    __tablename__ = "prompt"

    id = Column(UUID(as_uuid=True), primary_key=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    default_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("prompt_version.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    # Relationships
    versions = relationship(
        "PromptVersion",
        back_populates="prompt",
        foreign_keys="PromptVersion.prompt_id",
        cascade="all, delete-orphan",
    )
    default_version = relationship("PromptVersion", foreign_keys=[default_version_id], post_update=True)

    def __repr__(self):
        """Return a string representation of the Prompt model."""
        return f"<Prompt(id={self.id}, name={self.name})>"


class PromptVersion(PSQLBase, TimestampMixin):
    """Prompt version model storing full configuration."""

    __tablename__ = "prompt_version"

    id = Column(UUID(as_uuid=True), primary_key=True)
    prompt_id = Column(UUID(as_uuid=True), ForeignKey("prompt.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)

    # Configuration fields (from PromptConfigurationData schema)
    deployment_name = Column(String(255), nullable=True)
    model_settings = Column(JSONB, nullable=True)
    stream = Column(Boolean, nullable=True)
    system_prompt = Column(Text, nullable=True)
    input_schema = Column(JSONB, nullable=True)
    input_validation = Column(JSONB, nullable=True)
    output_schema = Column(JSONB, nullable=True)
    output_validation = Column(JSONB, nullable=True)
    messages = Column(JSONB, nullable=False, default=list)
    llm_retry_limit = Column(Integer, nullable=True)
    enable_tools = Column(Boolean, nullable=True)
    allow_multiple_calls = Column(Boolean, nullable=True)
    system_prompt_role = Column(String(50), nullable=True)
    tools = Column(JSONB, nullable=False, default=list)

    # Relationships
    prompt = relationship("Prompt", back_populates="versions", foreign_keys=[prompt_id])

    # Table constraints and indexes
    __table_args__ = (
        UniqueConstraint("prompt_id", "version", name="uq_prompt_version"),
        Index("idx_prompt_version_lookup", "prompt_id", "version"),
    )

    def __repr__(self):
        """Return a string representation of the PromptVersion model."""
        return f"<PromptVersion(id={self.id}, prompt_id={self.prompt_id}, version={self.version})>"
