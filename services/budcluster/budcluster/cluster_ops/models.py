import json
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

# from ..commons.database import Base
from budmicroframe.shared.dapr_service import DaprServiceCrypto
from budmicroframe.shared.psql_service import CRUDMixin, PSQLBase, TimestampMixin
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..commons.constants import ClusterNodeTypeEnum, ClusterPlatformEnum, ClusterStatusEnum


if TYPE_CHECKING:
    from ..benchmark_ops.models import BenchmarkSchema
    from ..deployment.models import WorkerInfo


class Cluster(PSQLBase, TimestampMixin):
    """Cluster model."""

    __tablename__ = "cluster"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    platform: Mapped[str] = mapped_column(
        Enum(
            ClusterPlatformEnum,
            name="cluster_platform_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    configuration: Mapped[str] = mapped_column(String, nullable=False)
    ingress_url: Mapped[str] = mapped_column(String, nullable=False)
    host: Mapped[str] = mapped_column(String, nullable=False)
    server_url: Mapped[str] = mapped_column(String, nullable=False)
    enable_master_node: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(
        Enum(
            ClusterStatusEnum,
            name="cluster_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String, nullable=True)

    # Metrics collection fields
    last_metrics_collection: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    metrics_collection_status: Mapped[str] = mapped_column(String(50), nullable=True)

    nodes: Mapped[list["ClusterNodeInfo"]] = relationship(back_populates="cluster", cascade="all, delete-orphan")
    workers: Mapped[list["WorkerInfo"]] = relationship(back_populates="cluster", cascade="all, delete-orphan")
    benchmarks: Mapped[list["BenchmarkSchema"]] = relationship(back_populates="cluster")

    @hybrid_property
    def config_file_dict(self):
        """Get configuration file as dict."""
        if not self.configuration:
            return {}
        with DaprServiceCrypto() as dapr_service:
            configuration_decrypted = dapr_service.decrypt_data(self.configuration)
        return json.loads(configuration_decrypted)


class ClusterNodeInfo(PSQLBase, TimestampMixin):
    """Cluster node info model."""

    __tablename__ = "cluster_node_info"
    __table_args__ = (UniqueConstraint("cluster_id", "name", name="uq_cluster_node_info_cluster_id_name"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    cluster_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("cluster.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    internal_ip: Mapped[str] = mapped_column(String, nullable=True)
    type: Mapped[str] = mapped_column(
        Enum(
            ClusterNodeTypeEnum,
            name="cluster_node_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    total_workers: Mapped[int] = mapped_column(Integer, default=0)
    available_workers: Mapped[int] = mapped_column(Integer, default=0)
    used_workers: Mapped[int] = mapped_column(Integer, default=0)
    threads_per_core: Mapped[int] = mapped_column(Integer, nullable=True)
    core_count: Mapped[int] = mapped_column(Integer, nullable=True)
    hardware_info: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    status: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status_sync_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # NFD schedulability fields
    schedulable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)
    unschedulable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    taints: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    conditions: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    pressure_conditions: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # NFD detection fields
    nfd_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    nfd_labels: Mapped[dict] = mapped_column(JSONB, nullable=True)
    detection_method: Mapped[str] = mapped_column(String, default="configmap", nullable=True)

    # Enhanced hardware support info
    kernel_info: Mapped[dict] = mapped_column(JSONB, nullable=True)
    driver_info: Mapped[dict] = mapped_column(JSONB, nullable=True)

    cluster: Mapped[Cluster] = relationship("Cluster", back_populates="nodes")

    @hybrid_property
    def hardware_info_dict(self):
        """Get hardware info as dict."""
        return json.loads(self.hardware_info) if self.hardware_info else {}


class ClusterNodeInfoCRUD(CRUDMixin[ClusterNodeInfo, None, None]):
    __model__ = ClusterNodeInfo

    def __init__(self):
        """Initialize cluster node info crud methods."""
        super().__init__(model=self.__model__)
