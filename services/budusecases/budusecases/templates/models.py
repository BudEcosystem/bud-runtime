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

"""SQLAlchemy models for Template System."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from budmicroframe.shared.psql_service import PSQLBase
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Template(PSQLBase):
    """SQLAlchemy model for use case templates."""

    __tablename__ = "templates"
    __table_args__ = (
        UniqueConstraint("name", "user_id", name="uq_template_name_user_id"),
        Index(
            "ix_template_name_system_unique",
            "name",
            unique=True,
            postgresql_where=text("source = 'system'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    resources: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    deployment_order: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    access: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="system", index=True)
    user_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    components: Mapped[list["TemplateComponent"]] = relationship(
        "TemplateComponent",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="TemplateComponent.sort_order",
    )

    def __repr__(self) -> str:
        return f"<Template(name={self.name!r}, version={self.version!r})>"


class TemplateComponent(PSQLBase):
    """SQLAlchemy model for template component definitions."""

    __tablename__ = "template_components"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    template_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    component_type: Mapped[str] = mapped_column(String(50), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_component: Mapped[str | None] = mapped_column(String(255), nullable=True)
    compatible_components: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    chart: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    template: Mapped["Template"] = relationship("Template", back_populates="components")

    def __repr__(self) -> str:
        return f"<TemplateComponent(name={self.name!r}, type={self.component_type!r})>"
