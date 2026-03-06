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

"""Job SQLAlchemy model for unified job tracking in BudCluster.

This module defines the Job model which serves as a single tracking point
for all workloads running on clusters managed by BudCluster.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from budmicroframe.shared.psql_service import CRUDMixin, PSQLBase, TimestampMixin
from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .enums import JobPriority, JobSource, JobStatus, JobType


if TYPE_CHECKING:
    from ..cluster_ops.models import Cluster


class Job(PSQLBase, TimestampMixin):
    """Unified job tracking model for BudCluster.

    This model tracks all workloads running on managed clusters, regardless
    of their source (BudUseCases, BudPipeline, BudApp, or manual creation).

    Attributes:
        id: Unique identifier for the job (UUID).
        name: Human-readable name for the job.
        job_type: Type of job (MODEL_DEPLOYMENT, FINE_TUNING, etc.).
        status: Current status of the job (PENDING, RUNNING, etc.).
        source: Service that created this job (BUDUSECASES, BUDPIPELINE, etc.).
        source_id: ID of the entity in the source service (e.g., deployment_id).
        cluster_id: ID of the cluster where the job runs.
        namespace: Kubernetes namespace for the job.
        endpoint_id: Optional link to an endpoint (for deployment jobs).
        priority: Job scheduling priority.
        config: Job configuration as JSON.
        metadata_: Additional metadata as JSON.
        error_message: Error details if job failed.
        retry_count: Number of retry attempts made.
        timeout_seconds: Maximum execution time for the job.
        started_at: Timestamp when job started executing.
        completed_at: Timestamp when job finished (success or failure).
    """

    __tablename__ = "job"

    # Primary key
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)

    # Core fields
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_type: Mapped[str] = mapped_column(
        Enum(
            JobType,
            name="job_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum(
            JobStatus,
            name="job_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        Enum(
            JobSource,
            name="job_source_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )

    # Source tracking
    source_id: Mapped[Optional[UUID]] = mapped_column(Uuid, nullable=True)

    # Cluster relationship
    cluster_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("cluster.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Kubernetes namespace
    namespace: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Optional endpoint link (for deployment jobs)
    endpoint_id: Mapped[Optional[UUID]] = mapped_column(Uuid, nullable=True)

    # Priority (using integer to allow flexible priority values)
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=JobPriority.NORMAL.value,
    )

    # Configuration and metadata (JSONB for flexible storage)
    config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Timeout configuration
    timeout_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Execution timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    cluster: Mapped["Cluster"] = relationship("Cluster", backref="jobs")

    # Table indexes for common query patterns
    __table_args__ = (
        Index("ix_job_status", "status"),
        Index("ix_job_cluster_id", "cluster_id"),
        Index("ix_job_source", "source"),
        Index("ix_job_job_type", "job_type"),
        Index("ix_job_created_at", "created_at"),
        Index("ix_job_source_source_id", "source", "source_id"),
    )


class JobCRUD(CRUDMixin[Job, None, None]):
    """CRUD operations for Job model."""

    __model__ = Job

    def __init__(self):
        """Initialize job CRUD methods."""
        super().__init__(model=self.__model__)
