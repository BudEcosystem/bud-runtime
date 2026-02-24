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

"""The endpoint ops package, containing essential business logic, services, and routing configurations for the endpoint ops."""

import json
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import DECIMAL, Boolean, DateTime, Enum, ForeignKey, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budapp.cluster_ops.models import Cluster
from budapp.commons.constants import AdapterStatusEnum, EndpointStatusEnum, ModelEndpointEnum
from budapp.commons.database import Base, TimestampMixin
from budapp.model_ops.models import Model
from budapp.project_ops.models import Project


class Endpoint(Base, TimestampMixin):
    """Endpoint model."""

    __tablename__ = "endpoint"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    model_id: Mapped[UUID] = mapped_column(ForeignKey("model.id", ondelete="CASCADE"), nullable=False)
    cache_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    cache_config: Mapped[str] = mapped_column(String, nullable=True)
    cluster_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("cluster.id", ondelete="CASCADE"), nullable=True)
    bud_cluster_id: Mapped[Optional[UUID]] = mapped_column(Uuid, nullable=True)
    url: Mapped[str] = mapped_column(String, nullable=False)
    namespace: Mapped[str] = mapped_column(String, nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("user.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            EndpointStatusEnum,
            name="endpoint_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    credential_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("proprietary_credential.id"), nullable=True)
    status_sync_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    model_configuration: Mapped[dict] = mapped_column(JSONB, nullable=True)
    active_replicas: Mapped[int] = mapped_column(Integer, nullable=False)
    total_replicas: Mapped[int] = mapped_column(Integer, nullable=False)
    number_of_nodes: Mapped[int] = mapped_column(Integer, nullable=False)
    deployment_config: Mapped[dict] = mapped_column(JSONB, nullable=True)
    deployment_settings: Mapped[dict] = mapped_column(JSONB, nullable=True)
    inference_cost: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    node_list: Mapped[list[str]] = mapped_column(JSONB, nullable=True)
    is_deprecated: Mapped[bool] = mapped_column(Boolean, default=False)
    supported_endpoints: Mapped[List[str]] = mapped_column(
        PG_ARRAY(
            PG_ENUM(
                ModelEndpointEnum,
                name="model_endpoint_enum",
                values_callable=lambda x: [e.value for e in x],
                create_type=False,
            ),
        ),
        nullable=False,
    )
    # Publication fields
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    published_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    published_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("user.id"), nullable=True)

    model: Mapped[Model] = relationship("Model", back_populates="endpoints", foreign_keys=[model_id])
    # worker: Mapped[Worker] = relationship(
    #     "Worker",
    #     back_populates="endpoint",
    #     cascade="all, delete",
    #     passive_deletes=True,
    # )
    project: Mapped[Project] = relationship("Project", back_populates="endpoints", foreign_keys=[project_id])

    cluster: Mapped[Optional[Cluster]] = relationship("Cluster", back_populates="endpoints", foreign_keys=[cluster_id])
    adapters: Mapped[list["Adapter"]] = relationship(back_populates="endpoint")
    created_user: Mapped["User"] = relationship(back_populates="created_endpoints", foreign_keys=[created_by])
    credential: Mapped[Optional["ProprietaryCredential"]] = relationship(
        "ProprietaryCredential", back_populates="endpoints"
    )
    routers: Mapped[list["RouterEndpoint"]] = relationship(
        "RouterEndpoint",
        back_populates="endpoint",
    )
    blocking_rules: Mapped[list["GatewayBlockingRule"]] = relationship(
        back_populates="endpoint", cascade="all, delete"
    )
    # Publication relationships
    published_user: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[published_by], back_populates="published_endpoints"
    )
    publication_history: Mapped[list["PublicationHistory"]] = relationship(
        "PublicationHistory", back_populates="endpoint", cascade="all, delete-orphan"
    )
    pricing_history: Mapped[list["DeploymentPricing"]] = relationship(
        "DeploymentPricing", back_populates="endpoint", cascade="all, delete-orphan"
    )

    @hybrid_property
    def cache_config_dict(self):
        if not self.cache_config:
            return {}
        return json.loads(self.cache_config)

    def to_dict(self):
        return {
            "id": str(self.id),
            "status": self.status,
            "project_id": str(self.project_id),
            "model_id": str(self.model_id),
            "cache_enabled": self.cache_enabled,
            "cache_config": self.cache_config_dict,
            "cluster_id": str(self.cluster_id) if self.cluster_id else None,
            "bud_cluster_id": str(self.bud_cluster_id) if self.bud_cluster_id else None,
            "url": self.url,
            "namespace": self.namespace,
            "replicas": self.replicas,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id=data.get("id"),
            status=data.get("status"),
            project_id=UUID(data.get("project_id")),
            model_id=UUID(data.get("model_id")),
            cache_enabled=data.get("cache_enabled"),
            cache_config=json.dumps(data.get("cache_config")),
            cluster_id=UUID(data.get("cluster_id")) if data.get("cluster_id") else None,
            bud_cluster_id=UUID(data.get("bud_cluster_id")) if data.get("bud_cluster_id") else None,
            url=data.get("url"),
            namespace=data.get("namespace"),
            replicas=data.get("replicas"),
            created_at=datetime.fromisoformat(data.get("created_at")),
            modified_at=datetime.fromisoformat(data.get("modified_at")),
        )


class Adapter(Base, TimestampMixin):
    """Adapter model."""

    __tablename__ = "adapter"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    deployment_name: Mapped[str] = mapped_column(String, nullable=False)
    endpoint_id: Mapped[UUID] = mapped_column(ForeignKey("endpoint.id", ondelete="CASCADE"), nullable=False)
    model_id: Mapped[UUID] = mapped_column(ForeignKey("model.id", ondelete="CASCADE"), nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("user.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(AdapterStatusEnum, name="adapter_status_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    status_sync_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    endpoint: Mapped[Endpoint] = relationship("Endpoint", back_populates="adapters", foreign_keys=[endpoint_id])
    model: Mapped[Model] = relationship("Model", back_populates="adapters", foreign_keys=[model_id])

    def to_dict(self):
        """Convert the Adapter instance to a dictionary.

        Returns:
            dict: A dictionary representation of the Adapter instance.
        """
        return {
            "id": str(self.id),
            "name": self.name,
            "endpoint_id": str(self.endpoint_id),
            "model_id": str(self.model_id),
            "status": self.status,
            "status_sync_at": self.status_sync_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Create an Adapter instance from a dictionary.

        Args:
            data (dict): A dictionary containing the Adapter data.

        Returns:
            Adapter: An instance of the Adapter class.
        """
        return cls(
            id=data.get("id"),
            name=data.get("name"),
            endpoint_id=UUID(data.get("endpoint_id")),
            model_id=UUID(data.get("model_id")),
            created_by=UUID(data.get("created_by")),
            status=data.get("status"),
            status_sync_at=datetime.fromisoformat(data.get("status_sync_at")),
            created_at=datetime.fromisoformat(data.get("created_at")),
            modified_at=datetime.fromisoformat(data.get("modified_at")),
        )


class DeploymentPricing(Base, TimestampMixin):
    """Deployment pricing model for tracking endpoint pricing history."""

    __tablename__ = "deployment_pricing"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    endpoint_id: Mapped[UUID] = mapped_column(ForeignKey("endpoint.id", ondelete="CASCADE"), nullable=False)
    input_cost: Mapped[float] = mapped_column(DECIMAL(10, 6), nullable=False)
    output_cost: Mapped[float] = mapped_column(DECIMAL(10, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    per_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("user.id"), nullable=False)

    # Relationships
    endpoint: Mapped[Endpoint] = relationship("Endpoint", back_populates="pricing_history")
    created_user: Mapped["User"] = relationship("User", foreign_keys=[created_by])

    def to_dict(self):
        """Convert the DeploymentPricing instance to a dictionary.

        Returns:
            dict: A dictionary representation of the DeploymentPricing instance.
        """
        return {
            "id": str(self.id),
            "endpoint_id": str(self.endpoint_id),
            "input_cost": float(self.input_cost),
            "output_cost": float(self.output_cost),
            "currency": self.currency,
            "per_tokens": self.per_tokens,
            "is_current": self.is_current,
            "created_by": str(self.created_by),
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }


class PublicationHistory(Base, TimestampMixin):
    """Publication history model for tracking publish/unpublish actions on endpoints."""

    __tablename__ = "publication_history"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    deployment_id: Mapped[UUID] = mapped_column(ForeignKey("endpoint.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # "publish" or "unpublish"
    performed_by: Mapped[UUID] = mapped_column(ForeignKey("user.id"), nullable=False)
    performed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    action_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    previous_state: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    new_state: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    endpoint: Mapped[Endpoint] = relationship(
        "Endpoint", back_populates="publication_history", foreign_keys=[deployment_id]
    )
    performed_by_user: Mapped["User"] = relationship("User", foreign_keys=[performed_by])

    def to_dict(self):
        """Convert the PublicationHistory instance to a dictionary.

        Returns:
            dict: A dictionary representation of the PublicationHistory instance.
        """
        return {
            "id": str(self.id),
            "deployment_id": str(self.deployment_id),
            "action": self.action,
            "performed_by": str(self.performed_by),
            "performed_at": self.performed_at.isoformat(),
            "action_metadata": self.action_metadata,
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }
