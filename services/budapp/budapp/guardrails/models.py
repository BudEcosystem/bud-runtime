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

"""Guardrail database models."""

from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budapp.commons.constants import (
    GuardrailDeploymentStatusEnum,
    GuardrailDeploymentTypeEnum,
    GuardrailProviderTypeEnum,
)
from budapp.commons.database import Base, TimestampMixin
from budapp.endpoint_ops.models import Endpoint
from budapp.model_ops.models import Provider
from budapp.project_ops.models import Project
from budapp.user_ops.models import User


class GuardrailProbe(Base, TimestampMixin):
    """Guardrail probe model - represents a type of vulnerability or threat detection."""

    __tablename__ = "guardrail_probes"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tags: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    sentinel_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Foreign keys
    provider_id: Mapped[UUID] = mapped_column(ForeignKey("provider.id", ondelete="RESTRICT"), nullable=False)
    created_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=True)
    project_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=True)

    provider_type: Mapped[str] = mapped_column(
        Enum(
            GuardrailProviderTypeEnum,
            name="guardrail_provider_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    is_custom: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    provider: Mapped["Provider"] = relationship("Provider")
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    owner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
    project: Mapped[Optional["Project"]] = relationship("Project")
    rules: Mapped[List["GuardrailRule"]] = relationship(
        "GuardrailRule", back_populates="probe", cascade="all, delete-orphan"
    )
    deployment_associations: Mapped[List["GuardrailDeploymentProbe"]] = relationship(
        "GuardrailDeploymentProbe", back_populates="probe"
    )


class GuardrailRule(Base, TimestampMixin):
    """Specific rules within each probe."""

    __tablename__ = "guardrail_rules"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    probe_id: Mapped[UUID] = mapped_column(ForeignKey("guardrail_probes.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    examples: Mapped[Optional[List[str]]] = mapped_column(PG_ARRAY(String), nullable=True)
    configuration: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    guard_types: Mapped[Optional[List[str]]] = mapped_column(PG_ARRAY(String), nullable=True)
    sentinel_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    scanner_types: Mapped[Optional[List[str]]] = mapped_column(PG_ARRAY(String), nullable=True)
    modality_types: Mapped[Optional[List[str]]] = mapped_column(PG_ARRAY(String), nullable=True)

    # Relationships
    probe: Mapped["GuardrailProbe"] = relationship("GuardrailProbe", back_populates="rules")
    deployment_rules: Mapped[List["GuardrailDeploymentRule"]] = relationship(
        "GuardrailDeploymentRule", back_populates="rule"
    )


class GuardrailDeployment(Base, TimestampMixin):
    """Tracks guardrail deployment configurations."""

    __tablename__ = "guardrail_deployments"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    deployment_type: Mapped[str] = mapped_column(
        Enum(
            GuardrailDeploymentTypeEnum,
            name="guardrail_deployment_type",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    endpoint_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("endpoint.id", ondelete="CASCADE"), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(
            GuardrailDeploymentStatusEnum,
            name="guardrail_deployment_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=GuardrailDeploymentStatusEnum.RUNNING.value,
    )
    configuration: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    default_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    guardrail_types: Mapped[Optional[List[str]]] = mapped_column(PG_ARRAY(String), nullable=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    endpoint: Mapped[Optional["Endpoint"]] = relationship("Endpoint")
    user: Mapped["User"] = relationship("User")
    project: Mapped["Project"] = relationship("Project")
    probe_associations: Mapped[List["GuardrailDeploymentProbe"]] = relationship(
        "GuardrailDeploymentProbe", back_populates="deployment", cascade="all, delete-orphan"
    )


class GuardrailDeploymentProbe(Base, TimestampMixin):
    """Junction table linking deployments to probes (many-to-many)."""

    __tablename__ = "guardrail_deployment_probes"
    __table_args__ = (UniqueConstraint("deployment_id", "probe_id", name="uq_deployment_probe"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    deployment_id: Mapped[UUID] = mapped_column(
        ForeignKey("guardrail_deployments.id", ondelete="CASCADE"), nullable=False
    )
    probe_id: Mapped[UUID] = mapped_column(ForeignKey("guardrail_probes.id", ondelete="CASCADE"), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    configuration: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    threshold_override: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    deployment: Mapped["GuardrailDeployment"] = relationship(
        "GuardrailDeployment", back_populates="probe_associations"
    )
    probe: Mapped["GuardrailProbe"] = relationship("GuardrailProbe", back_populates="deployment_associations")
    rule: Mapped[List["GuardrailDeploymentRule"]] = relationship(
        "GuardrailDeploymentRule", back_populates="deployment_probe", cascade="all, delete-orphan"
    )


class GuardrailDeploymentRule(Base, TimestampMixin):
    """Per-deployment rule configurations allowing granular control."""

    __tablename__ = "guardrail_deployment_rule"
    __table_args__ = (UniqueConstraint("deployment_probe_id", "rule_id", name="uq_deployment_probe_rule"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    deployment_probe_id: Mapped[UUID] = mapped_column(
        ForeignKey("guardrail_deployment_probes.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[UUID] = mapped_column(ForeignKey("guardrail_rules.id", ondelete="CASCADE"), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    configuration: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    threshold_override: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    deployment_probe: Mapped["GuardrailDeploymentProbe"] = relationship(
        "GuardrailDeploymentProbe", back_populates="rule"
    )
    rule: Mapped["GuardrailRule"] = relationship("GuardrailRule", back_populates="deployment_rules")
