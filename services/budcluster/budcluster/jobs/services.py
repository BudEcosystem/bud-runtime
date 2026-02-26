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

"""Service layer for Job operations in BudCluster.

This module provides the JobService class which contains business logic
for unified job tracking operations.
"""

from typing import TYPE_CHECKING, Optional, Sequence
from uuid import UUID

from budmicroframe.commons.logging import get_logger
from budmicroframe.shared.psql_service import DBSession
from fastapi import HTTPException, status

from .constants import MAX_JOB_RETRIES
from .crud import JobDataManager
from .enums import JobSource, JobStatus
from .schemas import JobCreate, JobFilter, JobListResponse, JobResponse, JobUpdate


if TYPE_CHECKING:
    pass


logger = get_logger(__name__)


class JobService:
    """Service class for Job business logic.

    Provides methods for creating, retrieving, updating, and deleting jobs,
    as well as status transitions and query operations.
    """

    # ---------- Create Methods ----------

    @classmethod
    async def create_job(cls, data: JobCreate) -> JobResponse:
        """Create a new job.

        Args:
            data: Job creation data.

        Returns:
            JobResponse with the created job data.

        Raises:
            HTTPException: If cluster not found.
        """
        # Lazy import to avoid circular import and config loading at module level
        from ..cluster_ops.crud import ClusterDataManager

        with DBSession() as session:
            # Validate cluster exists
            cluster_dm = ClusterDataManager(session)
            cluster = await cluster_dm.retrieve_cluster_by_fields({"id": data.cluster_id}, missing_ok=True)
            if not cluster:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Cluster not found: {data.cluster_id}",
                )

            # Create the job
            job_dm = JobDataManager(session)
            job = await job_dm.create_job(data)

            logger.info(f"Created job {job.id} for cluster {data.cluster_id}")
            return JobResponse.model_validate(job)

    # ---------- Retrieve Methods ----------

    @classmethod
    async def get_job(cls, job_id: UUID) -> JobResponse:
        """Get a job by ID.

        Args:
            job_id: The job's unique identifier.

        Returns:
            JobResponse with the job data.

        Raises:
            HTTPException: If job not found.
        """
        with DBSession() as session:
            job_dm = JobDataManager(session)
            job = await job_dm.get_job_by_id(job_id)
            return JobResponse.model_validate(job)

    @classmethod
    async def get_job_by_source_id(cls, source: JobSource, source_id: UUID) -> JobResponse:
        """Get a job by source and source_id.

        Args:
            source: The source service.
            source_id: The ID in the source service.

        Returns:
            JobResponse with the job data.

        Raises:
            HTTPException: If job not found.
        """
        with DBSession() as session:
            job_dm = JobDataManager(session)
            job = await job_dm.get_job_by_source_id(source, source_id)
            return JobResponse.model_validate(job)

    # ---------- List Methods ----------

    @classmethod
    async def list_jobs(
        cls,
        page: int = 1,
        page_size: int = 10,
        filters: Optional[JobFilter] = None,
    ) -> JobListResponse:
        """List jobs with pagination and optional filtering.

        Args:
            page: Page number (1-indexed).
            page_size: Number of items per page.
            filters: Optional filter criteria.

        Returns:
            JobListResponse with paginated jobs.
        """
        with DBSession() as session:
            job_dm = JobDataManager(session)

            # Convert filters to dict
            filter_dict = {}
            if filters:
                filter_data = filters.model_dump(exclude_none=True)
                filter_dict.update(filter_data)

            # Calculate offset
            offset = (page - 1) * page_size

            jobs, total = await job_dm.get_all_jobs(
                filters=filter_dict,
                offset=offset,
                limit=page_size,
            )

            return JobListResponse(
                jobs=[JobResponse.model_validate(job) for job in jobs],
                total=total,
                page=page,
                page_size=page_size,
            )

    @classmethod
    async def list_jobs_by_cluster(cls, cluster_id: UUID, page: int = 1, page_size: int = 10) -> JobListResponse:
        """List jobs for a specific cluster.

        Args:
            cluster_id: The cluster's unique identifier.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            JobListResponse with paginated jobs.
        """
        filters = JobFilter(cluster_id=cluster_id)
        return await cls.list_jobs(page=page, page_size=page_size, filters=filters)

    @classmethod
    async def list_jobs_by_source(cls, source: JobSource, page: int = 1, page_size: int = 10) -> JobListResponse:
        """List jobs from a specific source.

        Args:
            source: The source service to filter by.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            JobListResponse with paginated jobs.
        """
        filters = JobFilter(source=source)
        return await cls.list_jobs(page=page, page_size=page_size, filters=filters)

    # ---------- Update Methods ----------

    @classmethod
    async def update_job(cls, job_id: UUID, data: JobUpdate) -> JobResponse:
        """Update a job.

        Args:
            job_id: The job's unique identifier.
            data: Update data.

        Returns:
            JobResponse with the updated job data.

        Raises:
            HTTPException: If job not found.
        """
        with DBSession() as session:
            job_dm = JobDataManager(session)
            job = await job_dm.get_job_by_id(job_id)
            updated_job = await job_dm.update_job(job, data)
            return JobResponse.model_validate(updated_job)

    # ---------- Delete Methods ----------

    @classmethod
    async def delete_job(cls, job_id: UUID) -> None:
        """Delete a job.

        Args:
            job_id: The job's unique identifier.

        Raises:
            HTTPException: If job not found.
        """
        with DBSession() as session:
            job_dm = JobDataManager(session)
            await job_dm.delete_job_by_id(job_id)
            logger.info(f"Deleted job {job_id}")

    # ---------- Status Transition Methods ----------

    @classmethod
    async def start_job(cls, job_id: UUID) -> JobResponse:
        """Start a job (transition to RUNNING).

        Args:
            job_id: The job's unique identifier.

        Returns:
            JobResponse with the updated job data.
        """
        with DBSession() as session:
            job_dm = JobDataManager(session)
            job = await job_dm.get_job_by_id(job_id)
            updated_job = await job_dm.update_job_status(job, JobStatus.RUNNING)
            logger.info(f"Started job {job_id}")
            return JobResponse.model_validate(updated_job)

    @classmethod
    async def complete_job(cls, job_id: UUID) -> JobResponse:
        """Complete a job (transition to SUCCEEDED).

        Args:
            job_id: The job's unique identifier.

        Returns:
            JobResponse with the updated job data.
        """
        with DBSession() as session:
            job_dm = JobDataManager(session)
            job = await job_dm.get_job_by_id(job_id)
            updated_job = await job_dm.update_job_status(job, JobStatus.SUCCEEDED)
            logger.info(f"Completed job {job_id}")
            return JobResponse.model_validate(updated_job)

    @classmethod
    async def fail_job(cls, job_id: UUID, error_message: str) -> JobResponse:
        """Fail a job (transition to FAILED with error message).

        Args:
            job_id: The job's unique identifier.
            error_message: The error message to record.

        Returns:
            JobResponse with the updated job data.
        """
        with DBSession() as session:
            job_dm = JobDataManager(session)
            job = await job_dm.get_job_by_id(job_id)
            updated_job = await job_dm.set_job_error(job, error_message)
            logger.info(f"Failed job {job_id}: {error_message}")
            return JobResponse.model_validate(updated_job)

    @classmethod
    async def cancel_job(cls, job_id: UUID) -> JobResponse:
        """Cancel a job (transition to CANCELLED).

        Args:
            job_id: The job's unique identifier.

        Returns:
            JobResponse with the updated job data.
        """
        with DBSession() as session:
            job_dm = JobDataManager(session)
            job = await job_dm.get_job_by_id(job_id)
            updated_job = await job_dm.update_job_status(job, JobStatus.CANCELLED)
            logger.info(f"Cancelled job {job_id}")
            return JobResponse.model_validate(updated_job)

    @classmethod
    async def timeout_job(cls, job_id: UUID) -> JobResponse:
        """Timeout a job (transition to TIMEOUT).

        Args:
            job_id: The job's unique identifier.

        Returns:
            JobResponse with the updated job data.
        """
        with DBSession() as session:
            job_dm = JobDataManager(session)
            job = await job_dm.get_job_by_id(job_id)
            updated_job = await job_dm.update_job_status(
                job, JobStatus.TIMEOUT, error_message="Job exceeded timeout limit"
            )
            logger.info(f"Timed out job {job_id}")
            return JobResponse.model_validate(updated_job)

    @classmethod
    async def retry_job(cls, job_id: UUID) -> JobResponse:
        """Retry a job (increment retry count and transition to RETRYING).

        Args:
            job_id: The job's unique identifier.

        Returns:
            JobResponse with the updated job data.
        """
        with DBSession() as session:
            job_dm = JobDataManager(session)
            job = await job_dm.get_job_by_id(job_id)
            updated_job = await job_dm.increment_retry_count(job)
            logger.info(f"Retrying job {job_id}, attempt {updated_job.retry_count}")
            return JobResponse.model_validate(updated_job)

    # ---------- Status Query Methods ----------

    @classmethod
    async def get_active_jobs(cls, cluster_id: Optional[UUID] = None) -> Sequence[JobResponse]:
        """Get all active jobs (RUNNING or RETRYING).

        Args:
            cluster_id: Optional filter by cluster.

        Returns:
            List of JobResponse objects.
        """
        with DBSession() as session:
            job_dm = JobDataManager(session)
            jobs = await job_dm.get_active_jobs(cluster_id)
            return [JobResponse.model_validate(job) for job in jobs]

    @classmethod
    async def get_pending_jobs(cls, cluster_id: Optional[UUID] = None) -> Sequence[JobResponse]:
        """Get all pending jobs (PENDING or QUEUED).

        Args:
            cluster_id: Optional filter by cluster.

        Returns:
            List of JobResponse objects.
        """
        with DBSession() as session:
            job_dm = JobDataManager(session)
            jobs = await job_dm.get_pending_jobs(cluster_id)
            return [JobResponse.model_validate(job) for job in jobs]

    # ---------- Retry Validation Methods ----------

    @classmethod
    async def can_retry(cls, job_id: UUID) -> bool:
        """Check if a job can be retried.

        Args:
            job_id: The job's unique identifier.

        Returns:
            True if the job can be retried, False otherwise.
        """
        with DBSession() as session:
            job_dm = JobDataManager(session)
            job = await job_dm.get_job_by_id(job_id)
            return job.retry_count < MAX_JOB_RETRIES
