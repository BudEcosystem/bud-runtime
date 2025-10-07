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

"""The cluster ops package, containing essential business logic, services, and routing configurations for the cluster ops."""

import json
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budapp.commons.constants import ClusterStatusEnum
from budapp.commons.database import Base, TimestampMixin


class Cluster(Base, TimestampMixin):
    """Cluster model."""

    __tablename__ = "cluster"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    ingress_url: Mapped[str] = mapped_column(
        String, nullable=True
    )  # as cloud cluster doesnt have ingress url by default
    cluster_type: Mapped[str] = mapped_column(
        String, nullable=False, default="ON_PERM"
    )  # New Addition ->  ON_PERM || CLOUD
    status: Mapped[str] = mapped_column(
        Enum(
            ClusterStatusEnum,
            name="cluster_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    icon: Mapped[str] = mapped_column(String, nullable=False)
    cpu_count: Mapped[int] = mapped_column(Integer, default=0)
    gpu_count: Mapped[int] = mapped_column(Integer, default=0)
    hpu_count: Mapped[int] = mapped_column(Integer, default=0)
    cpu_total_workers: Mapped[int] = mapped_column(Integer, default=0)
    cpu_available_workers: Mapped[int] = mapped_column(Integer, default=0)
    gpu_total_workers: Mapped[int] = mapped_column(Integer, default=0)
    gpu_available_workers: Mapped[int] = mapped_column(Integer, default=0)
    hpu_total_workers: Mapped[int] = mapped_column(Integer, default=0)
    hpu_available_workers: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str] = mapped_column(String, nullable=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("user.id"), nullable=False)
    cluster_id: Mapped[UUID] = mapped_column(Uuid, nullable=True)
    status_sync_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    total_nodes: Mapped[int] = mapped_column(Integer, default=0)
    available_nodes: Mapped[int] = mapped_column(Integer, default=0)

    # Relation For Cloud Provider & Credential ID
    cloud_provider_id: Mapped[UUID] = mapped_column(Uuid, nullable=True)
    credential_id: Mapped[UUID] = mapped_column(Uuid, nullable=True)
    region: Mapped[str] = mapped_column(String, nullable=True)

    # cloud_credential: Mapped["CloudCredentials"] = relationship("CloudCredentials",foreign_keys=[credential_id])
    # cloud_provider: Mapped["CloudProviders"] = relationship("CloudProviders",foreign_keys=[cloud_provider_id])

    endpoints: Mapped[list["Endpoint"]] = relationship(
        "Endpoint",
        back_populates="cluster",
    )
    benchmarks: Mapped[list["BenchmarkSchema"]] = relationship(
        back_populates="cluster",
    )
    created_user: Mapped["User"] = relationship(back_populates="created_clusters", foreign_keys=[created_by])
    model_cluster_recommended: Mapped[list["ModelClusterRecommended"]] = relationship(
        "ModelClusterRecommended",
        back_populates="cluster",
    )
    cluster_settings: Mapped["ClusterSettings"] = relationship(
        "ClusterSettings", back_populates="cluster", uselist=False
    )

    @hybrid_property
    def kubernetes_info_dict(self):
        if not self.kubernetes_metadata:
            return {}
        return json.loads(self.kubernetes_metadata)


class ClusterSettings(Base, TimestampMixin):
    """Cluster settings model."""

    __tablename__ = "cluster_settings"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    cluster_id: Mapped[UUID] = mapped_column(ForeignKey("cluster.id", ondelete="CASCADE"), nullable=False)
    default_storage_class: Mapped[str] = mapped_column(String, nullable=True)
    default_access_mode: Mapped[str] = mapped_column(String, nullable=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("user.id"), nullable=False)

    cluster: Mapped["Cluster"] = relationship("Cluster", back_populates="cluster_settings")
    created_user: Mapped["User"] = relationship("User", foreign_keys=[created_by])


class ModelClusterRecommended(Base):
    """Model cluster recommended model."""

    __tablename__ = "model_cluster_recommended"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    model_id: Mapped[UUID] = mapped_column(ForeignKey("model.id"), nullable=False)
    cluster_id: Mapped[UUID] = mapped_column(ForeignKey("cluster.id"), nullable=False)
    hardware_type: Mapped[list[str]] = mapped_column(PG_ARRAY(String), nullable=False)
    cost_per_million_tokens: Mapped[float] = mapped_column(Float, nullable=False)

    model: Mapped["Model"] = relationship("Model", back_populates="model_cluster_recommended")
    cluster: Mapped["Cluster"] = relationship("Cluster", back_populates="model_cluster_recommended")
