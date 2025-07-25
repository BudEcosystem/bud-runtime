from datetime import datetime
from uuid import UUID, uuid4

from budmicroframe.shared.psql_service import PSQLBase, TimestampMixin
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

# from ..commons.database import Base
from .schemas import DeploymentStatusEnum, WorkerStatusEnum


class WorkerInfo(PSQLBase, TimestampMixin):
    """Worker information model."""

    __tablename__ = "worker_info"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    cluster_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("cluster.id", ondelete="CASCADE"), nullable=False)
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
