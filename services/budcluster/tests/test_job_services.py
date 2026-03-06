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

"""TDD Tests for Job service layer.

These tests are written BEFORE the implementation following TDD methodology.
The implementation should make all these tests pass.
"""

import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from budcluster.jobs.enums import JobPriority, JobSource, JobStatus, JobType
from budcluster.jobs.schemas import JobCreate, JobFilter, JobUpdate


def create_mock_job(**overrides):
    """Create a mock Job object with valid attribute values."""
    defaults = {
        "id": uuid4(),
        "name": "test-job",
        "job_type": JobType.MODEL_DEPLOYMENT,
        "status": JobStatus.PENDING,
        "source": JobSource.MANUAL,
        "source_id": None,
        "cluster_id": uuid4(),
        "namespace": None,
        "endpoint_id": None,
        "priority": JobPriority.NORMAL.value,
        "config": None,
        "metadata_": None,
        "error_message": None,
        "retry_count": 0,
        "timeout_seconds": None,
        "started_at": None,
        "completed_at": None,
        "created_at": datetime.now(timezone.utc),
        "modified_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)

    mock_job = MagicMock()
    for key, value in defaults.items():
        setattr(mock_job, key, value)
    return mock_job


class TestJobServiceExists:
    """Test that JobService class exists and has correct structure."""

    def test_job_service_exists(self):
        """Test that JobService can be imported."""
        from budcluster.jobs.services import JobService

        assert JobService is not None

    def test_job_service_has_create_job_method(self):
        """Test that JobService has create_job method."""
        from budcluster.jobs.services import JobService

        assert hasattr(JobService, "create_job")

    def test_job_service_has_get_job_method(self):
        """Test that JobService has get_job method."""
        from budcluster.jobs.services import JobService

        assert hasattr(JobService, "get_job")

    def test_job_service_has_list_jobs_method(self):
        """Test that JobService has list_jobs method."""
        from budcluster.jobs.services import JobService

        assert hasattr(JobService, "list_jobs")

    def test_job_service_has_update_job_method(self):
        """Test that JobService has update_job method."""
        from budcluster.jobs.services import JobService

        assert hasattr(JobService, "update_job")

    def test_job_service_has_delete_job_method(self):
        """Test that JobService has delete_job method."""
        from budcluster.jobs.services import JobService

        assert hasattr(JobService, "delete_job")


class TestJobServiceCreateJob:
    """Test cases for JobService.create_job method."""

    @pytest.mark.asyncio
    async def test_create_job_returns_job_response(self):
        """Test that create_job returns a JobResponse."""
        from budcluster.jobs.schemas import JobResponse
        from budcluster.jobs.services import JobService

        cluster_id = uuid4()
        job_data = JobCreate(
            name="test-job",
            job_type=JobType.MODEL_DEPLOYMENT,
            source=JobSource.MANUAL,
            cluster_id=cluster_id,
        )

        mock_job = create_mock_job(
            name="test-job",
            job_type=JobType.MODEL_DEPLOYMENT,
            source=JobSource.MANUAL,
            cluster_id=cluster_id,
        )

        # Create mock ClusterDataManager class
        mock_cluster_dm_class = MagicMock()
        mock_cluster_dm_instance = MagicMock()
        mock_cluster_dm_instance.retrieve_cluster_by_fields = AsyncMock(return_value=MagicMock())
        mock_cluster_dm_class.return_value = mock_cluster_dm_instance

        # Create mock module to prevent config loading
        mock_cluster_ops_crud = MagicMock()
        mock_cluster_ops_crud.ClusterDataManager = mock_cluster_dm_class

        with patch("budcluster.jobs.services.DBSession") as mock_session:
            with patch("budcluster.jobs.services.JobDataManager") as mock_dm:
                # Pre-insert mock module into sys.modules to prevent real import
                with patch.dict(sys.modules, {"budcluster.cluster_ops.crud": mock_cluster_ops_crud}):
                    mock_dm_instance = MagicMock()
                    mock_dm_instance.create_job = AsyncMock(return_value=mock_job)
                    mock_dm.return_value = mock_dm_instance

                    result = await JobService.create_job(job_data)
                    assert result.name == "test-job"

    @pytest.mark.asyncio
    async def test_create_job_validates_cluster_exists(self):
        """Test that create_job validates that the cluster exists."""
        from budcluster.jobs.services import JobService

        job_data = JobCreate(
            name="test-job",
            job_type=JobType.MODEL_DEPLOYMENT,
            source=JobSource.MANUAL,
            cluster_id=uuid4(),
        )

        # Create mock ClusterDataManager class
        mock_cluster_dm_class = MagicMock()
        mock_cluster_dm_instance = MagicMock()
        mock_cluster_dm_instance.retrieve_cluster_by_fields = AsyncMock(return_value=None)
        mock_cluster_dm_class.return_value = mock_cluster_dm_instance

        # Create mock module to prevent config loading
        mock_cluster_ops_crud = MagicMock()
        mock_cluster_ops_crud.ClusterDataManager = mock_cluster_dm_class

        with patch("budcluster.jobs.services.DBSession") as mock_session:
            # Pre-insert mock module into sys.modules to prevent real import
            with patch.dict(sys.modules, {"budcluster.cluster_ops.crud": mock_cluster_ops_crud}):
                from fastapi import HTTPException

                with pytest.raises(HTTPException) as exc_info:
                    await JobService.create_job(job_data)
                assert exc_info.value.status_code == 404


class TestJobServiceGetJob:
    """Test cases for JobService.get_job method."""

    @pytest.mark.asyncio
    async def test_get_job_by_id(self):
        """Test getting a job by ID."""
        from budcluster.jobs.services import JobService

        job_id = uuid4()
        mock_job = create_mock_job(id=job_id, status=JobStatus.RUNNING)

        with patch("budcluster.jobs.services.DBSession") as mock_session:
            with patch("budcluster.jobs.services.JobDataManager") as mock_dm:
                mock_dm_instance = MagicMock()
                mock_dm_instance.get_job_by_id = AsyncMock(return_value=mock_job)
                mock_dm.return_value = mock_dm_instance

                result = await JobService.get_job(job_id)
                assert result.id == job_id

    @pytest.mark.asyncio
    async def test_get_job_not_found_raises_404(self):
        """Test that get_job raises 404 when job not found."""
        from fastapi import HTTPException

        from budcluster.jobs.services import JobService

        job_id = uuid4()

        with patch("budcluster.jobs.services.DBSession") as mock_session:
            with patch("budcluster.jobs.services.JobDataManager") as mock_dm:
                mock_dm_instance = MagicMock()
                mock_dm_instance.get_job_by_id = AsyncMock(
                    side_effect=HTTPException(status_code=404, detail="Job not found")
                )
                mock_dm.return_value = mock_dm_instance

                with pytest.raises(HTTPException) as exc_info:
                    await JobService.get_job(job_id)
                assert exc_info.value.status_code == 404


class TestJobServiceListJobs:
    """Test cases for JobService.list_jobs method."""

    @pytest.mark.asyncio
    async def test_list_jobs_returns_paginated_response(self):
        """Test that list_jobs returns a paginated response."""
        from budcluster.jobs.schemas import JobListResponse
        from budcluster.jobs.services import JobService

        with patch("budcluster.jobs.services.DBSession") as mock_session:
            with patch("budcluster.jobs.services.JobDataManager") as mock_dm:
                mock_jobs = [create_mock_job(name=f"job-{i}") for i in range(5)]

                mock_dm_instance = MagicMock()
                mock_dm_instance.get_all_jobs = AsyncMock(return_value=(mock_jobs, 100))
                mock_dm.return_value = mock_dm_instance

                result = await JobService.list_jobs(page=1, page_size=5)
                assert isinstance(result, JobListResponse)
                assert len(result.jobs) == 5
                assert result.total == 100

    @pytest.mark.asyncio
    async def test_list_jobs_with_filters(self):
        """Test that list_jobs applies filters correctly."""
        from budcluster.jobs.services import JobService

        cluster_id = uuid4()
        filters = JobFilter(
            status=JobStatus.RUNNING,
            cluster_id=cluster_id,
        )

        with patch("budcluster.jobs.services.DBSession") as mock_session:
            with patch("budcluster.jobs.services.JobDataManager") as mock_dm:
                mock_dm_instance = MagicMock()
                mock_dm_instance.get_all_jobs = AsyncMock(return_value=([], 0))
                mock_dm.return_value = mock_dm_instance

                result = await JobService.list_jobs(page=1, page_size=10, filters=filters)
                # Verify get_all_jobs was called with filters
                mock_dm_instance.get_all_jobs.assert_called_once()
                call_kwargs = mock_dm_instance.get_all_jobs.call_args[1]
                assert "filters" in call_kwargs

    @pytest.mark.asyncio
    async def test_list_jobs_by_cluster(self):
        """Test listing jobs filtered by cluster."""
        from budcluster.jobs.services import JobService

        cluster_id = uuid4()

        with patch("budcluster.jobs.services.DBSession") as mock_session:
            with patch("budcluster.jobs.services.JobDataManager") as mock_dm:
                mock_dm_instance = MagicMock()
                mock_dm_instance.get_all_jobs = AsyncMock(return_value=([], 0))
                mock_dm.return_value = mock_dm_instance

                result = await JobService.list_jobs_by_cluster(cluster_id)
                mock_dm_instance.get_all_jobs.assert_called()


class TestJobServiceUpdateJob:
    """Test cases for JobService.update_job method."""

    @pytest.mark.asyncio
    async def test_update_job_returns_updated_job(self):
        """Test that update_job returns the updated job."""
        from budcluster.jobs.services import JobService

        job_id = uuid4()
        update_data = JobUpdate(status=JobStatus.RUNNING)
        mock_job = create_mock_job(id=job_id, status=JobStatus.RUNNING)

        with patch("budcluster.jobs.services.DBSession") as mock_session:
            with patch("budcluster.jobs.services.JobDataManager") as mock_dm:
                mock_dm_instance = MagicMock()
                mock_dm_instance.get_job_by_id = AsyncMock(return_value=mock_job)
                mock_dm_instance.update_job = AsyncMock(return_value=mock_job)
                mock_dm.return_value = mock_dm_instance

                result = await JobService.update_job(job_id, update_data)
                assert result.status == JobStatus.RUNNING


class TestJobServiceStatusTransitions:
    """Test cases for JobService status transition methods."""

    def test_has_start_job_method(self):
        """Test that JobService has start_job method."""
        from budcluster.jobs.services import JobService

        assert hasattr(JobService, "start_job")

    def test_has_complete_job_method(self):
        """Test that JobService has complete_job method."""
        from budcluster.jobs.services import JobService

        assert hasattr(JobService, "complete_job")

    def test_has_fail_job_method(self):
        """Test that JobService has fail_job method."""
        from budcluster.jobs.services import JobService

        assert hasattr(JobService, "fail_job")

    def test_has_cancel_job_method(self):
        """Test that JobService has cancel_job method."""
        from budcluster.jobs.services import JobService

        assert hasattr(JobService, "cancel_job")

    def test_has_retry_job_method(self):
        """Test that JobService has retry_job method."""
        from budcluster.jobs.services import JobService

        assert hasattr(JobService, "retry_job")

    @pytest.mark.asyncio
    async def test_start_job_sets_status_to_running(self):
        """Test that start_job sets status to RUNNING."""
        from budcluster.jobs.services import JobService

        job_id = uuid4()
        mock_job = create_mock_job(id=job_id, status=JobStatus.RUNNING)

        with patch("budcluster.jobs.services.DBSession") as mock_session:
            with patch("budcluster.jobs.services.JobDataManager") as mock_dm:
                mock_dm_instance = MagicMock()
                mock_dm_instance.get_job_by_id = AsyncMock(return_value=mock_job)
                mock_dm_instance.update_job_status = AsyncMock(return_value=mock_job)
                mock_dm.return_value = mock_dm_instance

                await JobService.start_job(job_id)
                mock_dm_instance.update_job_status.assert_called_once()
                call_args = mock_dm_instance.update_job_status.call_args
                assert call_args[0][1] == JobStatus.RUNNING

    @pytest.mark.asyncio
    async def test_complete_job_sets_status_to_succeeded(self):
        """Test that complete_job sets status to SUCCEEDED."""
        from budcluster.jobs.services import JobService

        job_id = uuid4()
        mock_job = create_mock_job(id=job_id, status=JobStatus.SUCCEEDED)

        with patch("budcluster.jobs.services.DBSession") as mock_session:
            with patch("budcluster.jobs.services.JobDataManager") as mock_dm:
                mock_dm_instance = MagicMock()
                mock_dm_instance.get_job_by_id = AsyncMock(return_value=mock_job)
                mock_dm_instance.update_job_status = AsyncMock(return_value=mock_job)
                mock_dm.return_value = mock_dm_instance

                await JobService.complete_job(job_id)
                mock_dm_instance.update_job_status.assert_called_once()
                call_args = mock_dm_instance.update_job_status.call_args
                assert call_args[0][1] == JobStatus.SUCCEEDED

    @pytest.mark.asyncio
    async def test_fail_job_sets_status_and_error_message(self):
        """Test that fail_job sets status to FAILED with error message."""
        from budcluster.jobs.services import JobService

        job_id = uuid4()
        error_msg = "OOM Error"
        mock_job = create_mock_job(id=job_id, status=JobStatus.FAILED, error_message=error_msg)

        with patch("budcluster.jobs.services.DBSession") as mock_session:
            with patch("budcluster.jobs.services.JobDataManager") as mock_dm:
                mock_dm_instance = MagicMock()
                mock_dm_instance.get_job_by_id = AsyncMock(return_value=mock_job)
                mock_dm_instance.set_job_error = AsyncMock(return_value=mock_job)
                mock_dm.return_value = mock_dm_instance

                await JobService.fail_job(job_id, error_msg)
                mock_dm_instance.set_job_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_job_sets_status_to_cancelled(self):
        """Test that cancel_job sets status to CANCELLED."""
        from budcluster.jobs.services import JobService

        job_id = uuid4()
        mock_job = create_mock_job(id=job_id, status=JobStatus.CANCELLED)

        with patch("budcluster.jobs.services.DBSession") as mock_session:
            with patch("budcluster.jobs.services.JobDataManager") as mock_dm:
                mock_dm_instance = MagicMock()
                mock_dm_instance.get_job_by_id = AsyncMock(return_value=mock_job)
                mock_dm_instance.update_job_status = AsyncMock(return_value=mock_job)
                mock_dm.return_value = mock_dm_instance

                await JobService.cancel_job(job_id)
                mock_dm_instance.update_job_status.assert_called_once()
                call_args = mock_dm_instance.update_job_status.call_args
                assert call_args[0][1] == JobStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_retry_job_increments_count_and_sets_retrying(self):
        """Test that retry_job increments retry count and sets status."""
        from budcluster.jobs.services import JobService

        job_id = uuid4()
        mock_job = create_mock_job(id=job_id, status=JobStatus.RETRYING, retry_count=1)

        with patch("budcluster.jobs.services.DBSession") as mock_session:
            with patch("budcluster.jobs.services.JobDataManager") as mock_dm:
                mock_dm_instance = MagicMock()
                mock_dm_instance.get_job_by_id = AsyncMock(return_value=mock_job)
                mock_dm_instance.increment_retry_count = AsyncMock(return_value=mock_job)
                mock_dm.return_value = mock_dm_instance

                await JobService.retry_job(job_id)
                mock_dm_instance.increment_retry_count.assert_called_once()


class TestJobServiceDeleteJob:
    """Test cases for JobService.delete_job method."""

    @pytest.mark.asyncio
    async def test_delete_job_removes_job(self):
        """Test that delete_job removes the job."""
        from budcluster.jobs.services import JobService

        job_id = uuid4()

        with patch("budcluster.jobs.services.DBSession") as mock_session:
            with patch("budcluster.jobs.services.JobDataManager") as mock_dm:
                mock_dm_instance = MagicMock()
                mock_dm_instance.delete_job_by_id = AsyncMock()
                mock_dm.return_value = mock_dm_instance

                await JobService.delete_job(job_id)
                mock_dm_instance.delete_job_by_id.assert_called_once_with(job_id)


class TestJobServiceSourceTracking:
    """Test cases for source-based job tracking methods."""

    def test_has_get_job_by_source_id_method(self):
        """Test that JobService has get_job_by_source_id method."""
        from budcluster.jobs.services import JobService

        assert hasattr(JobService, "get_job_by_source_id")

    def test_has_list_jobs_by_source_method(self):
        """Test that JobService has list_jobs_by_source method."""
        from budcluster.jobs.services import JobService

        assert hasattr(JobService, "list_jobs_by_source")

    @pytest.mark.asyncio
    async def test_get_job_by_source_id(self):
        """Test getting a job by source and source_id."""
        from budcluster.jobs.services import JobService

        source_id = uuid4()
        mock_job = create_mock_job(
            source=JobSource.BUDUSECASES,
            source_id=source_id,
            status=JobStatus.RUNNING,
        )

        with patch("budcluster.jobs.services.DBSession") as mock_session:
            with patch("budcluster.jobs.services.JobDataManager") as mock_dm:
                mock_dm_instance = MagicMock()
                mock_dm_instance.get_job_by_source_id = AsyncMock(return_value=mock_job)
                mock_dm.return_value = mock_dm_instance

                result = await JobService.get_job_by_source_id(JobSource.BUDUSECASES, source_id)
                assert result.source_id == source_id


class TestJobServiceStatusQueries:
    """Test cases for status-based query methods."""

    def test_has_get_active_jobs_method(self):
        """Test that JobService has get_active_jobs method."""
        from budcluster.jobs.services import JobService

        assert hasattr(JobService, "get_active_jobs")

    def test_has_get_pending_jobs_method(self):
        """Test that JobService has get_pending_jobs method."""
        from budcluster.jobs.services import JobService

        assert hasattr(JobService, "get_pending_jobs")

    @pytest.mark.asyncio
    async def test_get_active_jobs_returns_running_jobs(self):
        """Test that get_active_jobs returns running and retrying jobs."""
        from budcluster.jobs.services import JobService

        mock_jobs = [
            create_mock_job(status=JobStatus.RUNNING),
            create_mock_job(status=JobStatus.RETRYING),
        ]

        with patch("budcluster.jobs.services.DBSession") as mock_session:
            with patch("budcluster.jobs.services.JobDataManager") as mock_dm:
                mock_dm_instance = MagicMock()
                mock_dm_instance.get_active_jobs = AsyncMock(return_value=mock_jobs)
                mock_dm.return_value = mock_dm_instance

                result = await JobService.get_active_jobs()
                assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_pending_jobs_returns_pending_jobs(self):
        """Test that get_pending_jobs returns pending and queued jobs."""
        from budcluster.jobs.services import JobService

        mock_jobs = [
            create_mock_job(status=JobStatus.PENDING),
            create_mock_job(status=JobStatus.QUEUED),
        ]

        with patch("budcluster.jobs.services.DBSession") as mock_session:
            with patch("budcluster.jobs.services.JobDataManager") as mock_dm:
                mock_dm_instance = MagicMock()
                mock_dm_instance.get_pending_jobs = AsyncMock(return_value=mock_jobs)
                mock_dm.return_value = mock_dm_instance

                result = await JobService.get_pending_jobs()
                assert len(result) == 2


class TestJobServiceRetryValidation:
    """Test cases for retry validation logic."""

    def test_has_can_retry_method(self):
        """Test that JobService has can_retry method."""
        from budcluster.jobs.services import JobService

        assert hasattr(JobService, "can_retry")

    @pytest.mark.asyncio
    async def test_can_retry_returns_true_when_under_limit(self):
        """Test that can_retry returns True when under retry limit."""
        from budcluster.jobs.services import JobService

        job_id = uuid4()

        with patch("budcluster.jobs.services.DBSession") as mock_session:
            with patch("budcluster.jobs.services.JobDataManager") as mock_dm:
                mock_job = MagicMock()
                mock_job.retry_count = 1  # Under default MAX_JOB_RETRIES of 3

                mock_dm_instance = MagicMock()
                mock_dm_instance.get_job_by_id = AsyncMock(return_value=mock_job)
                mock_dm.return_value = mock_dm_instance

                result = await JobService.can_retry(job_id)
                assert result is True

    @pytest.mark.asyncio
    async def test_can_retry_returns_false_when_at_limit(self):
        """Test that can_retry returns False when at retry limit."""
        from budcluster.jobs.services import JobService

        job_id = uuid4()

        with patch("budcluster.jobs.services.DBSession") as mock_session:
            with patch("budcluster.jobs.services.JobDataManager") as mock_dm:
                mock_job = MagicMock()
                mock_job.retry_count = 3  # At default MAX_JOB_RETRIES

                mock_dm_instance = MagicMock()
                mock_dm_instance.get_job_by_id = AsyncMock(return_value=mock_job)
                mock_dm.return_value = mock_dm_instance

                result = await JobService.can_retry(job_id)
                assert result is False


class TestJobServiceTimeoutHandling:
    """Test cases for timeout handling methods."""

    def test_has_timeout_job_method(self):
        """Test that JobService has timeout_job method."""
        from budcluster.jobs.services import JobService

        assert hasattr(JobService, "timeout_job")

    @pytest.mark.asyncio
    async def test_timeout_job_sets_status_to_timeout(self):
        """Test that timeout_job sets status to TIMEOUT."""
        from budcluster.jobs.services import JobService

        job_id = uuid4()
        mock_job = create_mock_job(id=job_id, status=JobStatus.TIMEOUT)

        with patch("budcluster.jobs.services.DBSession") as mock_session:
            with patch("budcluster.jobs.services.JobDataManager") as mock_dm:
                mock_dm_instance = MagicMock()
                mock_dm_instance.get_job_by_id = AsyncMock(return_value=mock_job)
                mock_dm_instance.update_job_status = AsyncMock(return_value=mock_job)
                mock_dm.return_value = mock_dm_instance

                await JobService.timeout_job(job_id)
                call_args = mock_dm_instance.update_job_status.call_args
                assert call_args[0][1] == JobStatus.TIMEOUT
