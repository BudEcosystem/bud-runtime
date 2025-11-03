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

"""Database models for the prompt ops module."""

from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budapp.commons.constants import (
    PromptStatusEnum,
    PromptTypeEnum,
    PromptVersionStatusEnum,
    RateLimitTypeEnum,
)
from budapp.commons.database import Base, TimestampMixin


class Prompt(Base, TimestampMixin):
    """Prompt model for managing AI prompt configurations."""

    __tablename__ = "prompt"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    tags: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("user.id"), nullable=False)

    prompt_type: Mapped[str] = mapped_column(
        Enum(
            PromptTypeEnum,
            name="prompt_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=PromptTypeEnum.SIMPLE_PROMPT,
    )
    auto_scale: Mapped[bool] = mapped_column(Boolean, default=False)
    caching: Mapped[bool] = mapped_column(Boolean, default=False)
    concurrency: Mapped[list[int]] = mapped_column(PG_ARRAY(Integer), nullable=True)
    rate_limit: Mapped[bool] = mapped_column(Boolean, default=False)
    rate_limit_value: Mapped[int] = mapped_column(Integer, nullable=True)
    default_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("prompt_version.id", ondelete="SET NULL", use_alter=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        Enum(
            PromptStatusEnum,
            name="prompt_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=PromptStatusEnum.ACTIVE,
    )

    versions: Mapped[list["PromptVersion"]] = relationship(
        "PromptVersion",
        back_populates="prompt",
        cascade="all, delete-orphan",
        foreign_keys="PromptVersion.prompt_id",
    )
    default_version: Mapped["PromptVersion"] = relationship(
        "PromptVersion",
        foreign_keys=[default_version_id],
        post_update=True,
    )
    project: Mapped["Project"] = relationship("Project", foreign_keys=[project_id])
    created_user: Mapped["User"] = relationship("User", foreign_keys=[created_by])


class PromptVersion(Base, TimestampMixin):
    """Prompt version model for managing different versions of prompts."""

    __tablename__ = "prompt_version"
    __table_args__ = (UniqueConstraint("prompt_id", "version", name="uq_prompt_version_prompt_id_version"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    prompt_id: Mapped[UUID] = mapped_column(ForeignKey("prompt.id", ondelete="CASCADE"), nullable=False)
    endpoint_id: Mapped[UUID] = mapped_column(ForeignKey("endpoint.id", ondelete="CASCADE"), nullable=False)
    model_id: Mapped[UUID] = mapped_column(ForeignKey("model.id", ondelete="CASCADE"), nullable=False)
    cluster_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("cluster.id", ondelete="CASCADE"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            PromptVersionStatusEnum,
            name="prompt_version_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=PromptVersionStatusEnum.ACTIVE,
    )
    created_by: Mapped[UUID] = mapped_column(ForeignKey("user.id"), nullable=False)
    version_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    prompt: Mapped["Prompt"] = relationship("Prompt", back_populates="versions", foreign_keys=[prompt_id])
    endpoint: Mapped["Endpoint"] = relationship("Endpoint", foreign_keys=[endpoint_id])
    model: Mapped["Model"] = relationship("Model", foreign_keys=[model_id])
    cluster: Mapped["Cluster"] = relationship("Cluster", foreign_keys=[cluster_id])
    created_user: Mapped["User"] = relationship("User", foreign_keys=[created_by])
