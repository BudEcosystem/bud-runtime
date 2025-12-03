from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from budmicroframe.shared.psql_service import PSQLBase, TimestampMixin
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

# from ..commons.database import Base
from .schemas import DeploymentStatusEnum, WorkerStatusEnum


if TYPE_CHECKING:
    from ..cluster_ops.models import Cluster


class WorkerInfo(PSQLBase, TimestampMixin):
    """Worker information model."""

    __tablename__ = "worker_info"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    cluster_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("cluster.id", ondelete="CASCADE"), nullable=False)
    deployment_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid, ForeignKey("deployment.id", ondelete="SET NULL"), nullable=True
    )
    deployment_name: Mapped[str] = mapped_column(String, nullable=False)
    namespace: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    node_ip: Mapped[str] = mapped_column(String, nullable=False)
    node_name: Mapped[str] = mapped_column(String, nullable=False)
    device_name: Mapped[str] = mapped_column(String, nullable=False)
    utilization: Mapped[str] = mapped_column(String, nullable=True)
    hardware: Mapped[str] = mapped_column(String, nullable=False)
    uptime: Mapped[str] = mapped_column(String, nullable=False)
    created_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_restart_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_updated_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            WorkerStatusEnum,
            name="worker_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String, nullable=True)
    cores: Mapped[int] = mapped_column(Integer, nullable=False)
    memory: Mapped[str] = mapped_column(String, nullable=False)
    deployment_status: Mapped[str] = mapped_column(
        Enum(
            DeploymentStatusEnum,
            name="deployment_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False)

    cluster: Mapped["Cluster"] = relationship("Cluster", back_populates="workers")  # noqa: F821
    deployment: Mapped[Optional["Deployment"]] = relationship("Deployment", back_populates="workers")


class Deployment(PSQLBase, TimestampMixin):
    """Deployment tracking model - single source of truth for deployment status."""

    __tablename__ = "deployment"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    cluster_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("cluster.id", ondelete="CASCADE"), nullable=False)

    # Deployment identification
    namespace: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    deployment_name: Mapped[str] = mapped_column(String, nullable=False)
    endpoint_name: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)

    # Configuration
    deployment_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    supported_endpoints: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False)
    number_of_replicas: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    deploy_config: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        Enum(
            DeploymentStatusEnum,
            name="deployment_status_enum",
            values_callable=lambda x: [e.value for e in x],
            create_type=False,  # Enum already exists from worker_info
        ),
        nullable=False,
    )

    # Tracking
    workflow_id: Mapped[Optional[UUID]] = mapped_column(Uuid, nullable=True)
    simulator_id: Mapped[Optional[UUID]] = mapped_column(Uuid, nullable=True)
    credential_id: Mapped[Optional[UUID]] = mapped_column(Uuid, nullable=True)
    last_status_check: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    cluster: Mapped["Cluster"] = relationship("Cluster", back_populates="deployments")  # noqa: F821
    workers: Mapped[list["WorkerInfo"]] = relationship("WorkerInfo", back_populates="deployment")
