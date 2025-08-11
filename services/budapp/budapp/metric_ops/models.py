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

"""Database models for metrics and gateway analytics."""

from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, Enum, ForeignKey, Index, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budapp.commons.database import Base, TimestampMixin

from ..commons.constants import BlockingRuleStatus, BlockingRuleType


class GatewayBlockingRule(Base, TimestampMixin):
    """Model for gateway blocking rules.

    This model stores various types of blocking rules that can be applied
    at the API gateway level to protect endpoints and manage access.
    """

    __tablename__ = "gateway_blocking_rule"

    # Primary key
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)

    # Rule identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=True)

    # Rule type and configuration
    rule_type: Mapped[str] = mapped_column(
        Enum(
            BlockingRuleType,
            name="blocking_rule_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )

    # Rule configuration (JSON field for flexibility)
    # For IP blocking: {"ip_addresses": ["192.168.1.1", "10.0.0.0/24"]}
    # For country blocking: {"countries": ["CN", "RU"]}
    # For user agent blocking: {"patterns": ["bot", "crawler"]}
    # For rate-based blocking: {"threshold": 100, "window_seconds": 60, "action": "block"}
    rule_config: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Rule status
    status: Mapped[str] = mapped_column(
        Enum(
            BlockingRuleStatus,
            name="blocking_rule_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=BlockingRuleStatus.ACTIVE,
    )

    # Blocking metadata
    reason: Mapped[str] = mapped_column(String(500), nullable=True)
    priority: Mapped[int] = mapped_column(default=0)  # Higher priority rules are evaluated first

    # Scope - rules are scoped to projects
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id"), nullable=False)

    # Optional endpoint-specific rule
    endpoint_id: Mapped[UUID] = mapped_column(ForeignKey("endpoint.id"), nullable=True)

    # User who created the rule
    created_by: Mapped[UUID] = mapped_column(ForeignKey("user.id"), nullable=False)

    # Statistics tracking
    match_count: Mapped[int] = mapped_column(default=0)
    last_matched_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="blocking_rules")
    endpoint: Mapped[Optional["Endpoint"]] = relationship(back_populates="blocking_rules")
    created_user: Mapped["User"] = relationship(foreign_keys=[created_by])

    # Indexes for performance
    __table_args__ = (
        Index("idx_blocking_rule_project_status", "project_id", "status"),
        Index("idx_blocking_rule_type_status", "rule_type", "status"),
        Index("idx_blocking_rule_endpoint", "endpoint_id"),
    )
