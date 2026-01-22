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

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budapp.commons.constants import (
    GuardrailDeploymentStatusEnum,
    GuardrailProviderTypeEnum,
    GuardrailRuleDeploymentStatusEnum,
    GuardrailStatusEnum,
    ProbeTypeEnum,
    ScannerTypeEnum,
)
from budapp.commons.database import Base, TimestampMixin
from budapp.endpoint_ops.models import Endpoint
from budapp.model_ops.models import Provider
from budapp.project_ops.models import Project
from budapp.user_ops.models import User


class GuardrailProbe(Base, TimestampMixin):
    """Guardrail probe model - represents a type of vulnerability or threat detection."""

    __tablename__ = "guardrail_probe"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    uri: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    examples: Mapped[Optional[List[str]]] = mapped_column(PG_ARRAY(String), nullable=True)
    tags: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(
            GuardrailStatusEnum,
            name="guardrail_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=GuardrailStatusEnum.ACTIVE,
    )

    # Foreign keys
    provider_id: Mapped[UUID] = mapped_column(ForeignKey("provider.id"), nullable=False)
    created_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("user.id"), nullable=True)

    provider_type: Mapped[str] = mapped_column(
        Enum(
            GuardrailProviderTypeEnum,
            name="guardrail_provider_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    probe_type: Mapped[str] = mapped_column(
        Enum(
            ProbeTypeEnum,
            name="probe_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ProbeTypeEnum.PROVIDER,
    )

    # Relationships
    provider: Mapped["Provider"] = relationship("Provider")
    rules: Mapped[List["GuardrailRule"]] = relationship("GuardrailRule", back_populates="probe")
    probe_profiles: Mapped[List["GuardrailProfileProbe"]] = relationship(
        "GuardrailProfileProbe", back_populates="probe"
    )

    @hybrid_property
    def guard_types(self) -> List[str]:
        """Python-side implementation: Aggregates unique guard_types from all rules."""
        if not self.rules:
            return []
        # Use a set to efficiently find unique types
        all_types = set()
        for rule in self.rules:
            if rule.guard_types:
                all_types.update(rule.guard_types)
        return sorted(all_types)  # sorted for consistent output

    @guard_types.expression
    def guard_types(cls):
        """SQL-side implementation: Generates a subquery to aggregate types."""
        # This subquery unnests all arrays, finds distinct values, and re-aggregates them.
        subquery = (
            select(func.array_agg(func.distinct(func.unnest(GuardrailRule.guard_types))))
            .where(GuardrailRule.probe_id == cls.id)
            .label("aggregated_guard_types")
        )
        return subquery.as_scalar()

    # You can apply the exact same pattern for scanner_types and modality_types
    @hybrid_property
    def scanner_types(self) -> List[str]:
        if not self.rules:
            return []
        all_types = set()
        for rule in self.rules:
            if rule.scanner_types:
                all_types.update(rule.scanner_types)
        return sorted(all_types)

    @scanner_types.expression
    def scanner_types(cls):
        subquery = (
            select(func.array_agg(func.distinct(func.unnest(GuardrailRule.scanner_types))))
            .where(GuardrailRule.probe_id == cls.id)
            .label("aggregated_scanner_types")
        )
        return subquery.as_scalar()

    @hybrid_property
    def modality_types(self) -> List[str]:
        if not self.rules:
            return []
        all_types = set()
        for rule in self.rules:
            if rule.modality_types:
                all_types.update(rule.modality_types)
        return sorted(all_types)

    @modality_types.expression
    def modality_types(cls):
        subquery = (
            select(func.array_agg(func.distinct(func.unnest(GuardrailRule.modality_types))))
            .where(GuardrailRule.probe_id == cls.id)
            .label("aggregated_modality_types")
        )
        return subquery.as_scalar()

    @hybrid_property
    def examples(self) -> List[str]:
        """Python-side implementation for examples.
        Aggregates all unique examples from rules and returns up to 10.
        """
        if not self.rules:
            return []
        all_examples = set()
        for rule in self.rules:
            if rule.examples:
                all_examples.update(rule.examples)
        # Sort for consistent output and then slice the top 10
        return sorted(all_examples)[:10]

    @examples.expression
    def examples(cls):
        """SQL expression that aggregates up to 10 unique examples into a single array."""
        # Step 1: Create a subquery to get the first 10 distinct, unnested examples for a probe.
        # We must do the LIMIT here, before the final aggregation.
        limited_examples_subquery = (
            select(func.unnest(GuardrailRule.examples).label("example"))
            .where(GuardrailRule.probe_id == cls.id)
            .distinct()
            .limit(10)
            .subquery("limited_examples")
        )

        # Step 2: Aggregate the results of the subquery back into an array.
        final_query = select(func.array_agg(limited_examples_subquery.c.example))

        return final_query.label("aggregated_examples").as_scalar()


class GuardrailRule(Base, TimestampMixin):
    """Specific rules within each probe."""

    __tablename__ = "guardrail_rule"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    probe_id: Mapped[UUID] = mapped_column(
        ForeignKey("guardrail_probe.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    uri: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    examples: Mapped[Optional[List[str]]] = mapped_column(PG_ARRAY(String), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(
            GuardrailStatusEnum,
            name="guardrail_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=GuardrailStatusEnum.ACTIVE,
    )
    guard_types: Mapped[Optional[List[str]]] = mapped_column(PG_ARRAY(String), nullable=True)
    scanner_types: Mapped[Optional[List[str]]] = mapped_column(PG_ARRAY(String), nullable=True)
    modality_types: Mapped[Optional[List[str]]] = mapped_column(PG_ARRAY(String), nullable=True)

    # Model-based rule fields
    scanner_type: Mapped[Optional[str]] = mapped_column(
        Enum(
            ScannerTypeEnum,
            name="scanner_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    model_uri: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model_provider_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_gated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    model_config_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    model_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("model.id", ondelete="SET NULL"), nullable=True)

    created_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("user.id"), nullable=True)

    # Relationships
    probe: Mapped["GuardrailProbe"] = relationship("GuardrailProbe", back_populates="rules")
    rule_profiles: Mapped[List["GuardrailProfileRule"]] = relationship("GuardrailProfileRule", back_populates="rule")
    model: Mapped[Optional["Model"]] = relationship("Model")


class GuardrailProfile(Base, TimestampMixin):
    __tablename__ = "guardrail_profile"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tags: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    severity_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    guard_types: Mapped[Optional[List[str]]] = mapped_column(PG_ARRAY(String), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(
            GuardrailStatusEnum,
            name="guardrail_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=GuardrailStatusEnum.ACTIVE,
    )
    created_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("user.id"), nullable=True)
    project_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=True)

    created_user: Mapped["User"] = relationship(foreign_keys=[created_by])  # back_populates="created_guardrails"
    project: Mapped[Optional["Project"]] = relationship("Project")
    probe_profiles: Mapped[List["GuardrailProfileProbe"]] = relationship(
        "GuardrailProfileProbe", back_populates="profile"
    )
    deployments: Mapped[List["GuardrailDeployment"]] = relationship("GuardrailDeployment", back_populates="profile")


class GuardrailProfileProbe(Base, TimestampMixin):
    __tablename__ = "guardrail_profile_probe"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(ForeignKey("guardrail_profile.id", ondelete="CASCADE"), nullable=False)
    probe_id: Mapped[UUID] = mapped_column(
        ForeignKey("guardrail_probe.id", ondelete="CASCADE"), index=True, nullable=False
    )
    severity_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    guard_types: Mapped[Optional[List[str]]] = mapped_column(PG_ARRAY(String), nullable=True)
    created_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("user.id"), nullable=False)

    profile: Mapped["GuardrailProfile"] = relationship("GuardrailProfile", back_populates="probe_profiles")
    probe: Mapped["GuardrailProbe"] = relationship("GuardrailProbe", back_populates="probe_profiles")
    rule_profiles: Mapped[List["GuardrailProfileRule"]] = relationship(
        "GuardrailProfileRule", back_populates="probe_profile"
    )


class GuardrailProfileRule(Base, TimestampMixin):
    __tablename__ = "guardrail_profile_rule"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    profile_probe_id: Mapped[UUID] = mapped_column(
        ForeignKey("guardrail_profile_probe.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[UUID] = mapped_column(
        ForeignKey("guardrail_rule.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        Enum(
            GuardrailStatusEnum,
            name="guardrail_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=GuardrailStatusEnum.ACTIVE,
    )
    severity_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    guard_types: Mapped[Optional[List[str]]] = mapped_column(PG_ARRAY(String), nullable=True)
    created_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("user.id"), nullable=False)

    rule: Mapped["GuardrailRule"] = relationship("GuardrailRule", back_populates="rule_profiles")
    probe_profile: Mapped["GuardrailProfileProbe"] = relationship(
        "GuardrailProfileProbe", back_populates="rule_profiles"
    )


class GuardrailDeployment(Base, TimestampMixin):
    """Tracks guardrail deployment configurations."""

    __tablename__ = "guardrail_deployment"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(ForeignKey("guardrail_profile.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(
            GuardrailDeploymentStatusEnum,
            name="guardrail_deployment_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=GuardrailDeploymentStatusEnum.RUNNING,
    )

    created_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("user.id"), nullable=False)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    endpoint_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("endpoint.id", ondelete="CASCADE"), nullable=True)
    credential_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("proprietary_credential.id"), nullable=True)

    # Override fields from profile
    severity_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    guard_types: Mapped[Optional[List[str]]] = mapped_column(PG_ARRAY(String), nullable=True)

    # Relationships
    endpoint: Mapped[Optional["Endpoint"]] = relationship("Endpoint")
    user: Mapped["User"] = relationship("User")
    project: Mapped["Project"] = relationship("Project")
    credential: Mapped[Optional["ProprietaryCredential"]] = relationship("ProprietaryCredential")
    profile: Mapped["GuardrailProfile"] = relationship("GuardrailProfile", back_populates="deployments")
    rule_deployments: Mapped[List["GuardrailRuleDeployment"]] = relationship(
        "GuardrailRuleDeployment", back_populates="guardrail_deployment"
    )


class GuardrailRuleDeployment(Base, TimestampMixin):
    """Tracks model deployments for guardrail rules."""

    __tablename__ = "guardrail_rule_deployment"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    guardrail_deployment_id: Mapped[UUID] = mapped_column(
        ForeignKey("guardrail_deployment.id", ondelete="CASCADE"), index=True, nullable=False
    )
    rule_id: Mapped[UUID] = mapped_column(
        ForeignKey("guardrail_rule.id", ondelete="CASCADE"), index=True, nullable=False
    )
    model_id: Mapped[UUID] = mapped_column(ForeignKey("model.id", ondelete="CASCADE"), nullable=False)
    endpoint_id: Mapped[UUID] = mapped_column(
        ForeignKey("endpoint.id", ondelete="CASCADE"), index=True, nullable=False
    )
    cluster_id: Mapped[UUID] = mapped_column(ForeignKey("cluster.id", ondelete="CASCADE"), nullable=False)
    config_override_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(
            GuardrailRuleDeploymentStatusEnum,
            name="guardrail_rule_deployment_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=GuardrailRuleDeploymentStatusEnum.PENDING,
    )
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    guardrail_deployment: Mapped["GuardrailDeployment"] = relationship(
        "GuardrailDeployment", back_populates="rule_deployments"
    )
    rule: Mapped["GuardrailRule"] = relationship("GuardrailRule")
    model: Mapped["Model"] = relationship("Model")
    endpoint: Mapped["Endpoint"] = relationship("Endpoint")
    cluster: Mapped["Cluster"] = relationship("Cluster")
