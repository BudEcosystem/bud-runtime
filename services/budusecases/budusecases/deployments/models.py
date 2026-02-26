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

"""SQLAlchemy models for Deployment module."""

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from budmicroframe.shared.psql_service import PSQLBase
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .enums import ComponentDeploymentStatus, DeploymentStatus


class UseCaseDeployment(PSQLBase):
    """SQLAlchemy model for use case deployments."""

    __tablename__ = "usecase_deployments"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    template_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cluster_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    project_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    status: Mapped[DeploymentStatus] = mapped_column(
        String(50), nullable=False, default=DeploymentStatus.PENDING.value, index=True
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    pipeline_execution_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    access_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    gateway_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __init__(self, **kwargs: Any) -> None:
        """Initialize with Python defaults for status."""
        if "status" not in kwargs:
            kwargs["status"] = DeploymentStatus.PENDING
        if "parameters" not in kwargs:
            kwargs["parameters"] = {}
        if "metadata_" not in kwargs:
            kwargs["metadata_"] = {}
        super().__init__(**kwargs)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    template: Mapped[Optional["Template"]] = relationship(  # noqa: F821
        "Template", foreign_keys=[template_id]
    )
    component_deployments: Mapped[list["ComponentDeployment"]] = relationship(
        "ComponentDeployment",
        back_populates="usecase_deployment",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<UseCaseDeployment(name={self.name!r}, status={self.status!r})>"


class ComponentDeployment(PSQLBase):
    """SQLAlchemy model for individual component deployments."""

    __tablename__ = "component_deployments"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    usecase_deployment_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("usecase_deployments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    component_name: Mapped[str] = mapped_column(String(255), nullable=False)
    component_type: Mapped[str] = mapped_column(String(50), nullable=False)
    selected_component: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    status: Mapped[ComponentDeploymentStatus] = mapped_column(
        String(50), nullable=False, default=ComponentDeploymentStatus.PENDING
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    endpoint_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    usecase_deployment: Mapped["UseCaseDeployment"] = relationship(
        "UseCaseDeployment", back_populates="component_deployments"
    )

    def __repr__(self) -> str:
        return f"<ComponentDeployment(name={self.component_name!r}, status={self.status!r})>"
