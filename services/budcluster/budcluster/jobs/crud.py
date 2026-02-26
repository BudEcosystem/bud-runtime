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

"""CRUD operations for Job model in BudCluster.

This module provides the JobDataManager class for database operations
on the unified job tracking table.
"""

from datetime import datetime, timezone
from typing import Dict, Optional, Sequence, Tuple
from uuid import UUID

from budmicroframe.commons.logging import get_logger
from fastapi import status
from fastapi.exceptions import HTTPException
from sqlalchemy import and_, func, select

from ..commons.base_crud import BaseDataManager
from .enums import ACTIVE_JOB_STATUSES, PENDING_JOB_STATUSES, TERMINAL_JOB_STATUSES, JobSource, JobStatus
from .models import Job
from .schemas import JobCreate, JobUpdate


logger = get_logger(__name__)


class JobDataManager(BaseDataManager):
    """Data manager class for Job database operations.

    Provides CRUD operations for the unified job tracking table,
    including status management, filtering, and pagination.
    """

    # ---------- Create Methods ----------

    async def create_job(self, data: JobCreate) -> Job:
        """Create a new job in the database.

        Args:
            data: Job creation data.

        Returns:
            The created Job model instance.
        """
        job = Job(
            name=data.name,
            job_type=data.job_type,
            status=JobStatus.PENDING,
            source=data.source,
            cluster_id=data.cluster_id,
            source_id=data.source_id,
            namespace=data.namespace,
            endpoint_id=data.endpoint_id,
            priority=data.priority,
            config=data.config,
            metadata_=data.metadata_,
            timeout_seconds=data.timeout_seconds,
        )
        return await self.add_one(job)

    # ---------- Retrieve Methods ----------

    async def get_job_by_id(self, job_id: UUID, missing_ok: bool = False) -> Optional[Job]:
        """Retrieve a job by its ID.

        Args:
            job_id: The job's unique identifier.
            missing_ok: If True, return None instead of raising when not found.

        Returns:
            The Job instance if found, None if missing_ok=True and not found.

        Raises:
            HTTPException: If job not found and missing_ok=False.
        """
        stmt = select(Job).filter_by(id=job_id)
        db_job = await self.get_one_or_none(stmt)

        if not missing_ok and db_job is None:
            logger.info(f"Job not found: {job_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

        return db_job

    async def get_job_by_source_id(
        self, source: JobSource, source_id: UUID, missing_ok: bool = False
    ) -> Optional[Job]:
        """Retrieve a job by its source and source_id.

        Args:
            source: The source service that created the job.
            source_id: The ID in the source service.
            missing_ok: If True, return None instead of raising when not found.

        Returns:
            The Job instance if found.

        Raises:
            HTTPException: If job not found and missing_ok=False.
        """
        stmt = select(Job).filter_by(source=source, source_id=source_id)
        db_job = await self.get_one_or_none(stmt)

        if not missing_ok and db_job is None:
            logger.info(f"Job not found for source {source} with source_id {source_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

        return db_job

    async def get_jobs_by_cluster(self, cluster_id: UUID) -> Sequence[Job]:
        """Retrieve all jobs for a specific cluster.

        Args:
            cluster_id: The cluster's unique identifier.

        Returns:
            List of Job instances.
        """
        stmt = select(Job).filter_by(cluster_id=cluster_id)
        return await self.get_all(stmt)

    async def get_jobs_by_status(self, status_value: JobStatus) -> Sequence[Job]:
        """Retrieve all jobs with a specific status.

        Args:
            status_value: The status to filter by.

        Returns:
            List of Job instances.
        """
        stmt = select(Job).filter_by(status=status_value)
        return await self.get_all(stmt)

    async def get_jobs_by_source(self, source: JobSource) -> Sequence[Job]:
        """Retrieve all jobs from a specific source.

        Args:
            source: The source service to filter by.

        Returns:
            List of Job instances.
        """
        stmt = select(Job).filter_by(source=source)
        return await self.get_all(stmt)

    # ---------- Update Methods ----------

    async def update_job(self, job: Job, update_data: JobUpdate) -> Job:
        """Update a job with the provided data.

        Args:
            job: The Job instance to update.
            update_data: The update data.

        Returns:
            The updated Job instance.
        """
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(job, field, value)
        return await self.update_one(job)

    async def update_job_status(self, job: Job, new_status: JobStatus, error_message: Optional[str] = None) -> Job:
        """Update a job's status with automatic timestamp management.

        Args:
            job: The Job instance to update.
            new_status: The new status to set.
            error_message: Optional error message for failed status.

        Returns:
            The updated Job instance.
        """
        job.status = new_status

        # Set started_at when transitioning to RUNNING
        if new_status == JobStatus.RUNNING and job.started_at is None:
            job.started_at = datetime.now(timezone.utc)

        # Set completed_at when transitioning to a terminal status
        if new_status in TERMINAL_JOB_STATUSES and job.completed_at is None:
            job.completed_at = datetime.now(timezone.utc)

        # Set error message if provided
        if error_message:
            job.error_message = error_message

        return await self.update_one(job)

    # ---------- Delete Methods ----------

    async def delete_job(self, job: Job) -> None:
        """Delete a job from the database.

        Args:
            job: The Job instance to delete.
        """
        await self.delete_one(job)

    async def delete_job_by_id(self, job_id: UUID) -> None:
        """Delete a job by its ID.

        Args:
            job_id: The job's unique identifier.

        Raises:
            HTTPException: If job not found.
        """
        job = await self.get_job_by_id(job_id)
        await self.delete_one(job)

    # ---------- List Methods ----------

    async def get_all_jobs(
        self,
        filters: Optional[Dict] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Tuple[Sequence[Job], int]:
        """List all jobs with optional filtering and pagination.

        Args:
            filters: Dictionary of field-value pairs to filter by.
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            Tuple of (list of jobs, total count).
        """
        filters = filters or {}

        # Extract priority range filters if present
        priority_min = filters.pop("priority_min", None)
        priority_max = filters.pop("priority_max", None)

        await self.validate_fields(Job, filters)

        # Build filter conditions
        filter_conditions = []
        for field, value in filters.items():
            filter_conditions.append(getattr(Job, field) == value)

        if priority_min is not None:
            filter_conditions.append(Job.priority >= priority_min)
        if priority_max is not None:
            filter_conditions.append(Job.priority <= priority_max)

        # Build query
        if filter_conditions:
            stmt = select(Job).filter(and_(*filter_conditions))
            count_stmt = select(func.count()).select_from(Job).filter(and_(*filter_conditions))
        else:
            stmt = select(Job)
            count_stmt = select(func.count()).select_from(Job)

        # Get total count
        total = await self.execute_scalar_stmt(count_stmt)

        # Apply pagination
        if offset is not None or limit is not None:
            stmt = stmt.offset(offset).limit(limit)

        jobs = await self.get_all(stmt)
        return jobs, total  # type: ignore

    # ---------- Status Query Methods ----------

    async def get_active_jobs(self, cluster_id: Optional[UUID] = None) -> Sequence[Job]:
        """Get jobs that are currently active (RUNNING or RETRYING).

        Args:
            cluster_id: Optional filter by cluster.

        Returns:
            List of active Job instances.
        """
        conditions = [Job.status.in_([s.value for s in ACTIVE_JOB_STATUSES])]
        if cluster_id:
            conditions.append(Job.cluster_id == cluster_id)

        stmt = select(Job).filter(and_(*conditions))
        return await self.get_all(stmt)

    async def get_pending_jobs(self, cluster_id: Optional[UUID] = None) -> Sequence[Job]:
        """Get jobs that are pending (PENDING or QUEUED).

        Args:
            cluster_id: Optional filter by cluster.

        Returns:
            List of pending Job instances.
        """
        conditions = [Job.status.in_([s.value for s in PENDING_JOB_STATUSES])]
        if cluster_id:
            conditions.append(Job.cluster_id == cluster_id)

        stmt = select(Job).filter(and_(*conditions))
        return await self.get_all(stmt)

    async def get_jobs_for_cleanup(self, cutoff_date: datetime) -> Sequence[Job]:
        """Get completed jobs older than the cutoff date for cleanup.

        Args:
            cutoff_date: Jobs completed before this date are eligible for cleanup.

        Returns:
            List of Job instances eligible for cleanup.
        """
        stmt = select(Job).filter(
            and_(
                Job.status.in_([s.value for s in TERMINAL_JOB_STATUSES]),
                Job.completed_at < cutoff_date,
            )
        )
        return await self.get_all(stmt)

    # ---------- Retry Methods ----------

    async def increment_retry_count(self, job: Job) -> Job:
        """Increment a job's retry count and set status to RETRYING.

        Args:
            job: The Job instance to update.

        Returns:
            The updated Job instance.
        """
        job.retry_count += 1
        job.status = JobStatus.RETRYING
        return await self.update_one(job)

    # ---------- Error Handling Methods ----------

    async def set_job_error(self, job: Job, error_message: str) -> Job:
        """Set a job's error message and status to FAILED.

        Args:
            job: The Job instance to update.
            error_message: The error message to set.

        Returns:
            The updated Job instance.
        """
        job.error_message = error_message
        job.status = JobStatus.FAILED
        if job.completed_at is None:
            job.completed_at = datetime.now(timezone.utc)
        return await self.update_one(job)
