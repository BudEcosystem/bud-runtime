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

"""TDD Tests for Job CRUD operations (JobDataManager).

These tests are written BEFORE the implementation following TDD methodology.
They verify the JobDataManager class has the correct structure and methods.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

from budcluster.jobs.enums import JobPriority, JobSource, JobStatus, JobType
from budcluster.jobs.schemas import JobCreate, JobUpdate


class TestJobDataManagerExists:
    """Test that JobDataManager class exists and has correct structure."""

    def test_job_data_manager_exists(self):
        """Test that JobDataManager can be imported."""
        from budcluster.jobs.crud import JobDataManager

        assert JobDataManager is not None

    def test_job_data_manager_inherits_base(self):
        """Test that JobDataManager inherits from BaseDataManager."""
        from budcluster.commons.base_crud import BaseDataManager
        from budcluster.jobs.crud import JobDataManager

        assert issubclass(JobDataManager, BaseDataManager)


class TestJobDataManagerCreateMethods:
    """Test cases for job creation methods."""

    def test_has_create_job_method(self):
        """Test that JobDataManager has create_job method."""
        from budcluster.jobs.crud import JobDataManager

        assert hasattr(JobDataManager, "create_job")

    @pytest.mark.asyncio
    async def test_create_job_returns_job_model(self):
        """Test that create_job returns a Job model instance."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)

        job_data = JobCreate(
            name="test-job",
            job_type=JobType.MODEL_DEPLOYMENT,
            source=JobSource.MANUAL,
            cluster_id=uuid4(),
        )

        mock_job = MagicMock(spec=Job)
        with patch("budcluster.jobs.crud.Job", return_value=mock_job):
            with patch.object(data_manager, "add_one", new_callable=AsyncMock) as mock_add:
                mock_add.return_value = mock_job

                result = await data_manager.create_job(job_data)
                assert mock_add.called
                assert result == mock_job

    @pytest.mark.asyncio
    async def test_create_job_sets_default_status(self):
        """Test that create_job sets status to PENDING by default."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)

        job_data = JobCreate(
            name="test-job",
            job_type=JobType.MODEL_DEPLOYMENT,
            source=JobSource.MANUAL,
            cluster_id=uuid4(),
        )

        mock_job = MagicMock(spec=Job)
        mock_job.status = JobStatus.PENDING

        with patch("budcluster.jobs.crud.Job", return_value=mock_job) as mock_job_class:
            with patch.object(data_manager, "add_one", new_callable=AsyncMock) as mock_add:
                mock_add.return_value = mock_job

                result = await data_manager.create_job(job_data)
                # Verify Job was called with PENDING status
                call_kwargs = mock_job_class.call_args[1]
                assert call_kwargs["status"] == JobStatus.PENDING


class TestJobDataManagerRetrieveMethods:
    """Test cases for job retrieval methods."""

    def test_has_get_job_by_id_method(self):
        """Test that JobDataManager has get_job_by_id method."""
        from budcluster.jobs.crud import JobDataManager

        assert hasattr(JobDataManager, "get_job_by_id")

    def test_has_get_job_by_source_id_method(self):
        """Test that JobDataManager has get_job_by_source_id method."""
        from budcluster.jobs.crud import JobDataManager

        assert hasattr(JobDataManager, "get_job_by_source_id")

    def test_has_get_jobs_by_cluster_method(self):
        """Test that JobDataManager has get_jobs_by_cluster method."""
        from budcluster.jobs.crud import JobDataManager

        assert hasattr(JobDataManager, "get_jobs_by_cluster")

    def test_has_get_jobs_by_status_method(self):
        """Test that JobDataManager has get_jobs_by_status method."""
        from budcluster.jobs.crud import JobDataManager

        assert hasattr(JobDataManager, "get_jobs_by_status")

    @pytest.mark.asyncio
    async def test_get_job_by_id_returns_job(self):
        """Test that get_job_by_id returns a job when found."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)
        job_id = uuid4()

        with patch.object(data_manager, "get_one_or_none", new_callable=AsyncMock) as mock_get:
            mock_job = MagicMock(spec=Job)
            mock_job.id = job_id
            mock_get.return_value = mock_job

            result = await data_manager.get_job_by_id(job_id)
            assert result.id == job_id

    @pytest.mark.asyncio
    async def test_get_job_by_id_missing_ok_false_raises(self):
        """Test that get_job_by_id raises when job not found and missing_ok=False."""
        from fastapi import HTTPException

        from budcluster.jobs.crud import JobDataManager

        session = MagicMock()
        data_manager = JobDataManager(session)
        job_id = uuid4()

        with patch.object(data_manager, "get_one_or_none", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await data_manager.get_job_by_id(job_id, missing_ok=False)
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_job_by_id_missing_ok_true_returns_none(self):
        """Test that get_job_by_id returns None when job not found and missing_ok=True."""
        from budcluster.jobs.crud import JobDataManager

        session = MagicMock()
        data_manager = JobDataManager(session)
        job_id = uuid4()

        with patch.object(data_manager, "get_one_or_none", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            result = await data_manager.get_job_by_id(job_id, missing_ok=True)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_job_by_source_id_returns_job(self):
        """Test that get_job_by_source_id returns a job when found."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)
        source_id = uuid4()

        with patch.object(data_manager, "get_one_or_none", new_callable=AsyncMock) as mock_get:
            mock_job = MagicMock(spec=Job)
            mock_job.source_id = source_id
            mock_get.return_value = mock_job

            result = await data_manager.get_job_by_source_id(
                source=JobSource.BUDUSECASES, source_id=source_id
            )
            assert result.source_id == source_id

    @pytest.mark.asyncio
    async def test_get_jobs_by_cluster_returns_list(self):
        """Test that get_jobs_by_cluster returns a list of jobs."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)
        cluster_id = uuid4()

        with patch.object(data_manager, "get_all", new_callable=AsyncMock) as mock_get_all:
            mock_jobs = [MagicMock(spec=Job), MagicMock(spec=Job)]
            mock_get_all.return_value = mock_jobs

            result = await data_manager.get_jobs_by_cluster(cluster_id)
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_jobs_by_status_returns_list(self):
        """Test that get_jobs_by_status returns a list of jobs."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)

        with patch.object(data_manager, "get_all", new_callable=AsyncMock) as mock_get_all:
            mock_jobs = [MagicMock(spec=Job)]
            mock_get_all.return_value = mock_jobs

            result = await data_manager.get_jobs_by_status(JobStatus.RUNNING)
            assert len(result) == 1


class TestJobDataManagerUpdateMethods:
    """Test cases for job update methods."""

    def test_has_update_job_method(self):
        """Test that JobDataManager has update_job method."""
        from budcluster.jobs.crud import JobDataManager

        assert hasattr(JobDataManager, "update_job")

    def test_has_update_job_status_method(self):
        """Test that JobDataManager has update_job_status method."""
        from budcluster.jobs.crud import JobDataManager

        assert hasattr(JobDataManager, "update_job_status")

    @pytest.mark.asyncio
    async def test_update_job_applies_changes(self):
        """Test that update_job applies the update data to the job."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)

        mock_job = MagicMock(spec=Job)
        mock_job.status = JobStatus.PENDING
        update_data = JobUpdate(status=JobStatus.RUNNING)

        with patch.object(data_manager, "update_one", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = mock_job

            result = await data_manager.update_job(mock_job, update_data)
            assert mock_update.called

    @pytest.mark.asyncio
    async def test_update_job_status_changes_status(self):
        """Test that update_job_status changes the job status."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)

        mock_job = MagicMock(spec=Job)
        mock_job.status = JobStatus.PENDING

        with patch.object(data_manager, "update_one", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = mock_job

            await data_manager.update_job_status(mock_job, JobStatus.RUNNING)
            assert mock_job.status == JobStatus.RUNNING

    @pytest.mark.asyncio
    async def test_update_job_status_sets_started_at_when_running(self):
        """Test that update_job_status sets started_at when transitioning to RUNNING."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)

        mock_job = MagicMock(spec=Job)
        mock_job.status = JobStatus.PENDING
        mock_job.started_at = None

        with patch.object(data_manager, "update_one", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = mock_job

            await data_manager.update_job_status(mock_job, JobStatus.RUNNING)
            assert mock_job.started_at is not None

    @pytest.mark.asyncio
    async def test_update_job_status_sets_completed_at_on_terminal(self):
        """Test that update_job_status sets completed_at on terminal status."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)

        mock_job = MagicMock(spec=Job)
        mock_job.status = JobStatus.RUNNING
        mock_job.completed_at = None

        for terminal_status in [JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.TIMEOUT]:
            mock_job.completed_at = None
            with patch.object(data_manager, "update_one", new_callable=AsyncMock) as mock_update:
                mock_update.return_value = mock_job

                await data_manager.update_job_status(mock_job, terminal_status)
                assert mock_job.completed_at is not None


class TestJobDataManagerDeleteMethods:
    """Test cases for job deletion methods."""

    def test_has_delete_job_method(self):
        """Test that JobDataManager has delete_job method."""
        from budcluster.jobs.crud import JobDataManager

        assert hasattr(JobDataManager, "delete_job")

    def test_has_delete_job_by_id_method(self):
        """Test that JobDataManager has delete_job_by_id method."""
        from budcluster.jobs.crud import JobDataManager

        assert hasattr(JobDataManager, "delete_job_by_id")

    @pytest.mark.asyncio
    async def test_delete_job_removes_job(self):
        """Test that delete_job removes the job."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)

        mock_job = MagicMock(spec=Job)

        with patch.object(data_manager, "delete_one", new_callable=AsyncMock) as mock_delete:
            await data_manager.delete_job(mock_job)
            mock_delete.assert_called_once_with(mock_job)

    @pytest.mark.asyncio
    async def test_delete_job_by_id_retrieves_and_deletes(self):
        """Test that delete_job_by_id retrieves the job then deletes it."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)
        job_id = uuid4()

        mock_job = MagicMock(spec=Job)

        with patch.object(data_manager, "get_job_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_job
            with patch.object(data_manager, "delete_one", new_callable=AsyncMock) as mock_delete:
                await data_manager.delete_job_by_id(job_id)
                mock_get.assert_called_once_with(job_id)
                mock_delete.assert_called_once_with(mock_job)


class TestJobDataManagerListMethods:
    """Test cases for job listing methods."""

    def test_has_get_all_jobs_method(self):
        """Test that JobDataManager has get_all_jobs method."""
        from budcluster.jobs.crud import JobDataManager

        assert hasattr(JobDataManager, "get_all_jobs")

    @pytest.mark.asyncio
    async def test_get_all_jobs_with_pagination(self):
        """Test that get_all_jobs supports pagination."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)

        with patch.object(data_manager, "get_all", new_callable=AsyncMock) as mock_get_all:
            with patch.object(data_manager, "execute_scalar_stmt", new_callable=AsyncMock) as mock_count:
                mock_jobs = [MagicMock(spec=Job) for _ in range(10)]
                mock_get_all.return_value = mock_jobs
                mock_count.return_value = 100

                jobs, total = await data_manager.get_all_jobs(offset=0, limit=10)
                assert len(jobs) == 10
                assert total == 100

    @pytest.mark.asyncio
    async def test_get_all_jobs_with_filters(self):
        """Test that get_all_jobs supports filtering."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)
        cluster_id = uuid4()

        with patch.object(data_manager, "get_all", new_callable=AsyncMock) as mock_get_all:
            with patch.object(data_manager, "execute_scalar_stmt", new_callable=AsyncMock) as mock_count:
                mock_jobs = [MagicMock(spec=Job)]
                mock_get_all.return_value = mock_jobs
                mock_count.return_value = 1

                jobs, total = await data_manager.get_all_jobs(
                    filters={"cluster_id": cluster_id, "status": JobStatus.RUNNING}
                )
                assert len(jobs) == 1


class TestJobDataManagerStatusQueries:
    """Test cases for status-based query methods."""

    def test_has_get_active_jobs_method(self):
        """Test that JobDataManager has get_active_jobs method."""
        from budcluster.jobs.crud import JobDataManager

        assert hasattr(JobDataManager, "get_active_jobs")

    def test_has_get_pending_jobs_method(self):
        """Test that JobDataManager has get_pending_jobs method."""
        from budcluster.jobs.crud import JobDataManager

        assert hasattr(JobDataManager, "get_pending_jobs")

    def test_has_get_jobs_for_cleanup_method(self):
        """Test that JobDataManager has get_jobs_for_cleanup method."""
        from budcluster.jobs.crud import JobDataManager

        assert hasattr(JobDataManager, "get_jobs_for_cleanup")

    @pytest.mark.asyncio
    async def test_get_active_jobs_returns_running_and_retrying(self):
        """Test that get_active_jobs returns RUNNING and RETRYING jobs."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)

        with patch.object(data_manager, "get_all", new_callable=AsyncMock) as mock_get_all:
            mock_running = MagicMock(spec=Job)
            mock_running.status = JobStatus.RUNNING
            mock_retrying = MagicMock(spec=Job)
            mock_retrying.status = JobStatus.RETRYING
            mock_get_all.return_value = [mock_running, mock_retrying]

            result = await data_manager.get_active_jobs()
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_pending_jobs_returns_pending_and_queued(self):
        """Test that get_pending_jobs returns PENDING and QUEUED jobs."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)

        with patch.object(data_manager, "get_all", new_callable=AsyncMock) as mock_get_all:
            mock_pending = MagicMock(spec=Job)
            mock_pending.status = JobStatus.PENDING
            mock_queued = MagicMock(spec=Job)
            mock_queued.status = JobStatus.QUEUED
            mock_get_all.return_value = [mock_pending, mock_queued]

            result = await data_manager.get_pending_jobs()
            assert len(result) == 2


class TestJobDataManagerRetryMethods:
    """Test cases for retry-related methods."""

    def test_has_increment_retry_count_method(self):
        """Test that JobDataManager has increment_retry_count method."""
        from budcluster.jobs.crud import JobDataManager

        assert hasattr(JobDataManager, "increment_retry_count")

    @pytest.mark.asyncio
    async def test_increment_retry_count_increases_count(self):
        """Test that increment_retry_count increases the retry count."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)

        mock_job = MagicMock(spec=Job)
        mock_job.retry_count = 0

        with patch.object(data_manager, "update_one", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = mock_job

            await data_manager.increment_retry_count(mock_job)
            assert mock_job.retry_count == 1

    @pytest.mark.asyncio
    async def test_increment_retry_count_sets_status_to_retrying(self):
        """Test that increment_retry_count sets status to RETRYING."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)

        mock_job = MagicMock(spec=Job)
        mock_job.retry_count = 0
        mock_job.status = JobStatus.FAILED

        with patch.object(data_manager, "update_one", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = mock_job

            await data_manager.increment_retry_count(mock_job)
            assert mock_job.status == JobStatus.RETRYING


class TestJobDataManagerErrorHandling:
    """Test cases for error handling methods."""

    def test_has_set_job_error_method(self):
        """Test that JobDataManager has set_job_error method."""
        from budcluster.jobs.crud import JobDataManager

        assert hasattr(JobDataManager, "set_job_error")

    @pytest.mark.asyncio
    async def test_set_job_error_updates_error_message(self):
        """Test that set_job_error updates the error message."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)

        mock_job = MagicMock(spec=Job)
        mock_job.error_message = None

        with patch.object(data_manager, "update_one", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = mock_job

            await data_manager.set_job_error(mock_job, "OOM Error")
            assert mock_job.error_message == "OOM Error"

    @pytest.mark.asyncio
    async def test_set_job_error_sets_status_to_failed(self):
        """Test that set_job_error sets status to FAILED."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)

        mock_job = MagicMock(spec=Job)
        mock_job.status = JobStatus.RUNNING

        with patch.object(data_manager, "update_one", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = mock_job

            await data_manager.set_job_error(mock_job, "Error occurred")
            assert mock_job.status == JobStatus.FAILED


class TestJobDataManagerBulkOperations:
    """Test cases for bulk operations."""

    def test_has_get_jobs_by_source_method(self):
        """Test that JobDataManager has get_jobs_by_source method."""
        from budcluster.jobs.crud import JobDataManager

        assert hasattr(JobDataManager, "get_jobs_by_source")

    @pytest.mark.asyncio
    async def test_get_jobs_by_source_filters_correctly(self):
        """Test that get_jobs_by_source filters by source."""
        from budcluster.jobs.crud import JobDataManager
        from budcluster.jobs.models import Job

        session = MagicMock()
        data_manager = JobDataManager(session)

        with patch.object(data_manager, "get_all", new_callable=AsyncMock) as mock_get_all:
            mock_job = MagicMock(spec=Job)
            mock_job.source = JobSource.BUDUSECASES
            mock_get_all.return_value = [mock_job]

            result = await data_manager.get_jobs_by_source(JobSource.BUDUSECASES)
            assert len(result) == 1
            assert result[0].source == JobSource.BUDUSECASES


class TestJobDataManagerFieldValidation:
    """Test cases for field validation in queries."""

    @pytest.mark.asyncio
    async def test_get_all_jobs_validates_filter_fields(self):
        """Test that get_all_jobs validates filter fields."""
        from budcluster.jobs.crud import JobDataManager

        session = MagicMock()
        data_manager = JobDataManager(session)

        with patch.object(data_manager, "validate_fields", new_callable=AsyncMock) as mock_validate:
            with patch.object(data_manager, "get_all", new_callable=AsyncMock) as mock_get_all:
                with patch.object(data_manager, "execute_scalar_stmt", new_callable=AsyncMock) as mock_count:
                    mock_get_all.return_value = []
                    mock_count.return_value = 0

                    await data_manager.get_all_jobs(filters={"status": JobStatus.RUNNING})
                    mock_validate.assert_called()
