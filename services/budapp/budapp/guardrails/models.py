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

from budapp.auth.models import User
from budapp.commons.constants import GuardrailDeploymentStatusEnum, GuardrailDeploymentTypeEnum, GuardrailProviderEnum
from budapp.commons.database import Base, TimestampMixin
from budapp.endpoint_ops.models import Endpoint
from budapp.project_ops.models import Project


class GuardrailProvider(Base, TimestampMixin):
    """Guardrail provider model - represents different guardrail service providers."""

    __tablename__ = "guardrail_providers"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_type: Mapped[str] = mapped_column(
        Enum(
            GuardrailProviderEnum,
            name="guardrail_provider_type",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    configuration_schema: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Foreign keys
    created_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=True)
    project_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=True)

    # Relationships
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    owner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
    project: Mapped[Optional["Project"]] = relationship("Project")
    probes: Mapped[List["GuardrailProbe"]] = relationship("GuardrailProbe", back_populates="provider")


class GuardrailProbe(Base, TimestampMixin):
    """Guardrail probe model - represents a type of vulnerability or threat detection."""

    __tablename__ = "guardrail_probes"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tags: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)

    # Foreign keys
    provider_id: Mapped[UUID] = mapped_column(
        ForeignKey("guardrail_providers.id", ondelete="RESTRICT"), nullable=False
    )
    created_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=True)
    project_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=True)

    # Relationships
    provider: Mapped["GuardrailProvider"] = relationship("GuardrailProvider", back_populates="probes")
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    owner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
    project: Mapped[Optional["Project"]] = relationship("Project")
    rules: Mapped[List["GuardrailRule"]] = relationship(
        "GuardrailRule", back_populates="probe", cascade="all, delete-orphan"
    )
    deployment_associations: Mapped[List["GuardrailDeploymentProbe"]] = relationship(
        "GuardrailDeploymentProbe", back_populates="probe"
    )

    @hybrid_property
    def is_custom(self) -> bool:
        """Check if this probe is custom based on provider type."""
        return self.provider and self.provider.provider_type == GuardrailProviderEnum.CUSTOM


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
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    probe: Mapped["GuardrailProbe"] = relationship("GuardrailProbe", back_populates="rules")
    deployment_configs: Mapped[List["GuardrailDeploymentRuleConfig"]] = relationship(
        "GuardrailDeploymentRuleConfig", back_populates="rule"
    )
    scanner_associations: Mapped[List["GuardrailRuleScanner"]] = relationship(
        "GuardrailRuleScanner", back_populates="rule", cascade="all, delete-orphan"
    )
    modality_associations: Mapped[List["GuardrailRuleModality"]] = relationship(
        "GuardrailRuleModality", back_populates="rule", cascade="all, delete-orphan"
    )
    guard_type_associations: Mapped[List["GuardrailRuleGuardType"]] = relationship(
        "GuardrailRuleGuardType", back_populates="rule", cascade="all, delete-orphan"
    )


class GuardrailScannerType(Base, TimestampMixin):
    """Reference table for available scanner types."""

    __tablename__ = "guardrail_scanner_types"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    supported_modalities: Mapped[List[str]] = mapped_column(PG_ARRAY(String), nullable=False)
    configuration_schema: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    rule_associations: Mapped[List["GuardrailRuleScanner"]] = relationship(
        "GuardrailRuleScanner", back_populates="scanner_type"
    )


class GuardrailModalityType(Base, TimestampMixin):
    """Reference table for available modality types."""

    __tablename__ = "guardrail_modality_types"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    rule_associations: Mapped[List["GuardrailRuleModality"]] = relationship(
        "GuardrailRuleModality", back_populates="modality_type"
    )


class GuardrailGuardType(Base, TimestampMixin):
    """Reference table for available guard types."""

    __tablename__ = "guardrail_guard_types"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    rule_associations: Mapped[List["GuardrailRuleGuardType"]] = relationship(
        "GuardrailRuleGuardType", back_populates="guard_type"
    )


class GuardrailRuleScanner(Base, TimestampMixin):
    """Junction table linking rules to scanner types."""

    __tablename__ = "guardrail_rule_scanners"
    __table_args__ = (UniqueConstraint("rule_id", "scanner_type_id", name="uq_rule_scanner"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    rule_id: Mapped[UUID] = mapped_column(ForeignKey("guardrail_rules.id", ondelete="CASCADE"), nullable=False)
    scanner_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("guardrail_scanner_types.id", ondelete="RESTRICT"), nullable=False
    )

    # Relationships
    rule: Mapped["GuardrailRule"] = relationship("GuardrailRule", back_populates="scanner_associations")
    scanner_type: Mapped["GuardrailScannerType"] = relationship(
        "GuardrailScannerType", back_populates="rule_associations"
    )


class GuardrailRuleModality(Base, TimestampMixin):
    """Junction table linking rules to modality types."""

    __tablename__ = "guardrail_rule_modalities"
    __table_args__ = (UniqueConstraint("rule_id", "modality_type_id", name="uq_rule_modality"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    rule_id: Mapped[UUID] = mapped_column(ForeignKey("guardrail_rules.id", ondelete="CASCADE"), nullable=False)
    modality_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("guardrail_modality_types.id", ondelete="RESTRICT"), nullable=False
    )

    # Relationships
    rule: Mapped["GuardrailRule"] = relationship("GuardrailRule", back_populates="modality_associations")
    modality_type: Mapped["GuardrailModalityType"] = relationship(
        "GuardrailModalityType", back_populates="rule_associations"
    )


class GuardrailRuleGuardType(Base, TimestampMixin):
    """Junction table linking rules to guard types."""

    __tablename__ = "guardrail_rule_guard_types"
    __table_args__ = (UniqueConstraint("rule_id", "guard_type_id", name="uq_rule_guard_type"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    rule_id: Mapped[UUID] = mapped_column(ForeignKey("guardrail_rules.id", ondelete="CASCADE"), nullable=False)
    guard_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("guardrail_guard_types.id", ondelete="RESTRICT"), nullable=False
    )

    # Relationships
    rule: Mapped["GuardrailRule"] = relationship("GuardrailRule", back_populates="guard_type_associations")
    guard_type: Mapped["GuardrailGuardType"] = relationship("GuardrailGuardType", back_populates="rule_associations")


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
    deployment_endpoint_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(
            GuardrailDeploymentStatusEnum,
            name="guardrail_deployment_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=GuardrailDeploymentStatusEnum.INACTIVE.value,
    )
    configuration: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    default_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
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
    execution_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    configuration: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    threshold_override: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    deployment: Mapped["GuardrailDeployment"] = relationship(
        "GuardrailDeployment", back_populates="probe_associations"
    )
    probe: Mapped["GuardrailProbe"] = relationship("GuardrailProbe", back_populates="deployment_associations")
    rule_configs: Mapped[List["GuardrailDeploymentRuleConfig"]] = relationship(
        "GuardrailDeploymentRuleConfig", back_populates="deployment_probe", cascade="all, delete-orphan"
    )


class GuardrailDeploymentRuleConfig(Base, TimestampMixin):
    """Per-deployment rule configurations allowing granular control."""

    __tablename__ = "guardrail_deployment_rule_configs"
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
        "GuardrailDeploymentProbe", back_populates="rule_configs"
    )
    rule: Mapped["GuardrailRule"] = relationship("GuardrailRule", back_populates="deployment_configs")
