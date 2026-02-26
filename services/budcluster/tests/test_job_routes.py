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

"""TDD Tests for Job REST API routes.

These tests are written BEFORE the implementation following TDD methodology.
The implementation should make all these tests pass.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from budcluster.jobs.enums import JobPriority, JobSource, JobStatus, JobType
from budcluster.jobs.schemas import JobListResponse, JobResponse


def create_mock_job_response(**overrides) -> JobResponse:
    """Create a mock JobResponse with valid attribute values."""
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
    return JobResponse(**defaults)


class TestJobRouterExists:
    """Test that job_router exists and has correct structure."""

    def test_job_router_exists(self):
        """Test that job_router can be imported."""
        from budcluster.jobs.routes import job_router

        assert job_router is not None

    def test_job_router_has_prefix(self):
        """Test that job_router has the correct prefix."""
        from budcluster.jobs.routes import job_router

        assert job_router.prefix == "/job"


class TestJobRoutesExist:
    """Test that all expected routes exist."""

    def _get_all_methods_for_path(self, router, path: str) -> set:
        """Get all HTTP methods for a given path across all routes."""
        methods = set()
        for route in router.routes:
            if route.path == path:
                methods.update(route.methods)
        return methods

    def test_create_job_route_exists(self):
        """Test that POST /job route exists."""
        from budcluster.jobs.routes import job_router

        routes = [route.path for route in job_router.routes]
        assert "/job" in routes
        # Check POST method exists on root path
        root_methods = self._get_all_methods_for_path(job_router, "/job")
        assert "POST" in root_methods

    def test_get_job_route_exists(self):
        """Test that GET /job/{job_id} route exists."""
        from budcluster.jobs.routes import job_router

        routes = [route.path for route in job_router.routes]
        assert "/job/{job_id}" in routes

    def test_list_jobs_route_exists(self):
        """Test that GET /job route exists."""
        from budcluster.jobs.routes import job_router

        routes = [route.path for route in job_router.routes]
        # Check GET method exists on root path
        root_methods = self._get_all_methods_for_path(job_router, "/job")
        assert "GET" in root_methods

    def test_update_job_route_exists(self):
        """Test that PATCH /job/{job_id} route exists."""
        from budcluster.jobs.routes import job_router

        routes = [route.path for route in job_router.routes]
        assert "/job/{job_id}" in routes
        job_id_methods = self._get_all_methods_for_path(job_router, "/job/{job_id}")
        assert "PATCH" in job_id_methods

    def test_delete_job_route_exists(self):
        """Test that DELETE /job/{job_id} route exists."""
        from budcluster.jobs.routes import job_router

        routes = [route.path for route in job_router.routes]
        assert "/job/{job_id}" in routes
        job_id_methods = self._get_all_methods_for_path(job_router, "/job/{job_id}")
        assert "DELETE" in job_id_methods


class TestJobStatusTransitionRoutes:
    """Test that status transition routes exist."""

    def test_start_job_route_exists(self):
        """Test that POST /job/{job_id}/start route exists."""
        from budcluster.jobs.routes import job_router

        routes = [route.path for route in job_router.routes]
        assert "/job/{job_id}/start" in routes

    def test_complete_job_route_exists(self):
        """Test that POST /job/{job_id}/complete route exists."""
        from budcluster.jobs.routes import job_router

        routes = [route.path for route in job_router.routes]
        assert "/job/{job_id}/complete" in routes

    def test_fail_job_route_exists(self):
        """Test that POST /job/{job_id}/fail route exists."""
        from budcluster.jobs.routes import job_router

        routes = [route.path for route in job_router.routes]
        assert "/job/{job_id}/fail" in routes

    def test_cancel_job_route_exists(self):
        """Test that POST /job/{job_id}/cancel route exists."""
        from budcluster.jobs.routes import job_router

        routes = [route.path for route in job_router.routes]
        assert "/job/{job_id}/cancel" in routes

    def test_retry_job_route_exists(self):
        """Test that POST /job/{job_id}/retry route exists."""
        from budcluster.jobs.routes import job_router

        routes = [route.path for route in job_router.routes]
        assert "/job/{job_id}/retry" in routes

    def test_timeout_job_route_exists(self):
        """Test that POST /job/{job_id}/timeout route exists."""
        from budcluster.jobs.routes import job_router

        routes = [route.path for route in job_router.routes]
        assert "/job/{job_id}/timeout" in routes


class TestJobQueryRoutes:
    """Test that query routes exist."""

    def test_active_jobs_route_exists(self):
        """Test that GET /job/active route exists."""
        from budcluster.jobs.routes import job_router

        routes = [route.path for route in job_router.routes]
        assert "/job/active" in routes

    def test_pending_jobs_route_exists(self):
        """Test that GET /job/pending route exists."""
        from budcluster.jobs.routes import job_router

        routes = [route.path for route in job_router.routes]
        assert "/job/pending" in routes

    def test_can_retry_route_exists(self):
        """Test that GET /job/{job_id}/can-retry route exists."""
        from budcluster.jobs.routes import job_router

        routes = [route.path for route in job_router.routes]
        assert "/job/{job_id}/can-retry" in routes


class TestJobSourceRoutes:
    """Test that source-based routes exist."""

    def test_get_by_source_route_exists(self):
        """Test that GET /job/source/{source}/{source_id} route exists."""
        from budcluster.jobs.routes import job_router

        routes = [route.path for route in job_router.routes]
        assert "/job/source/{source}/{source_id}" in routes

    def test_list_by_cluster_route_exists(self):
        """Test that GET /job/cluster/{cluster_id} route exists."""
        from budcluster.jobs.routes import job_router

        routes = [route.path for route in job_router.routes]
        assert "/job/cluster/{cluster_id}" in routes


class TestCreateJobEndpoint:
    """Test cases for POST /job endpoint."""

    @pytest.mark.asyncio
    async def test_create_job_success(self):
        """Test successful job creation."""
        from budcluster.jobs.routes import job_router, create_job

        cluster_id = uuid4()
        mock_response = create_mock_job_response(
            name="test-job",
            cluster_id=cluster_id,
        )

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.create_job = AsyncMock(return_value=mock_response)

            from budcluster.jobs.schemas import JobCreate

            job_data = JobCreate(
                name="test-job",
                job_type=JobType.MODEL_DEPLOYMENT,
                source=JobSource.MANUAL,
                cluster_id=cluster_id,
            )

            result = await create_job(job_data)
            assert result.name == "test-job"

    @pytest.mark.asyncio
    async def test_create_job_cluster_not_found(self):
        """Test job creation with non-existent cluster."""
        from budcluster.jobs.routes import create_job

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.create_job = AsyncMock(
                side_effect=HTTPException(status_code=404, detail="Cluster not found")
            )

            from budcluster.jobs.schemas import JobCreate

            job_data = JobCreate(
                name="test-job",
                job_type=JobType.MODEL_DEPLOYMENT,
                source=JobSource.MANUAL,
                cluster_id=uuid4(),
            )

            with pytest.raises(HTTPException) as exc_info:
                await create_job(job_data)
            assert exc_info.value.status_code == 404


class TestGetJobEndpoint:
    """Test cases for GET /job/{job_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_job_success(self):
        """Test successful job retrieval."""
        from budcluster.jobs.routes import get_job

        job_id = uuid4()
        mock_response = create_mock_job_response(id=job_id)

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.get_job = AsyncMock(return_value=mock_response)

            result = await get_job(job_id)
            assert result.id == job_id

    @pytest.mark.asyncio
    async def test_get_job_not_found(self):
        """Test job retrieval with non-existent job."""
        from budcluster.jobs.routes import get_job

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.get_job = AsyncMock(
                side_effect=HTTPException(status_code=404, detail="Job not found")
            )

            with pytest.raises(HTTPException) as exc_info:
                await get_job(uuid4())
            assert exc_info.value.status_code == 404


class TestListJobsEndpoint:
    """Test cases for GET /job endpoint."""

    @pytest.mark.asyncio
    async def test_list_jobs_success(self):
        """Test successful job listing."""
        from budcluster.jobs.routes import list_jobs

        mock_response = JobListResponse(
            jobs=[create_mock_job_response() for _ in range(5)],
            total=100,
            page=1,
            page_size=5,
        )

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.list_jobs = AsyncMock(return_value=mock_response)

            # Pass None explicitly to avoid Query objects
            result = await list_jobs(page=1, page_size=5, status=None, source=None, cluster_id=None)
            assert len(result.jobs) == 5
            assert result.total == 100

    @pytest.mark.asyncio
    async def test_list_jobs_with_filters(self):
        """Test job listing with filters."""
        from budcluster.jobs.routes import list_jobs

        mock_response = JobListResponse(
            jobs=[],
            total=0,
            page=1,
            page_size=10,
        )

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.list_jobs = AsyncMock(return_value=mock_response)

            result = await list_jobs(
                page=1,
                page_size=10,
                status=JobStatus.RUNNING,
                source=JobSource.BUDUSECASES,
                cluster_id=None,
            )
            mock_service.list_jobs.assert_called_once()


class TestUpdateJobEndpoint:
    """Test cases for PATCH /job/{job_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_job_success(self):
        """Test successful job update."""
        from budcluster.jobs.routes import update_job

        job_id = uuid4()
        mock_response = create_mock_job_response(id=job_id, status=JobStatus.RUNNING)

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.update_job = AsyncMock(return_value=mock_response)

            from budcluster.jobs.schemas import JobUpdate

            update_data = JobUpdate(status=JobStatus.RUNNING)
            result = await update_job(job_id, update_data)
            assert result.status == JobStatus.RUNNING


class TestDeleteJobEndpoint:
    """Test cases for DELETE /job/{job_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_job_success(self):
        """Test successful job deletion."""
        from budcluster.jobs.routes import delete_job

        job_id = uuid4()

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.delete_job = AsyncMock(return_value=None)

            result = await delete_job(job_id)
            mock_service.delete_job.assert_called_once_with(job_id)


class TestStatusTransitionEndpoints:
    """Test cases for status transition endpoints."""

    @pytest.mark.asyncio
    async def test_start_job_success(self):
        """Test successful job start."""
        from budcluster.jobs.routes import start_job

        job_id = uuid4()
        mock_response = create_mock_job_response(id=job_id, status=JobStatus.RUNNING)

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.start_job = AsyncMock(return_value=mock_response)

            result = await start_job(job_id)
            assert result.status == JobStatus.RUNNING

    @pytest.mark.asyncio
    async def test_complete_job_success(self):
        """Test successful job completion."""
        from budcluster.jobs.routes import complete_job

        job_id = uuid4()
        mock_response = create_mock_job_response(id=job_id, status=JobStatus.SUCCEEDED)

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.complete_job = AsyncMock(return_value=mock_response)

            result = await complete_job(job_id)
            assert result.status == JobStatus.SUCCEEDED

    @pytest.mark.asyncio
    async def test_fail_job_success(self):
        """Test successful job failure."""
        from budcluster.jobs.routes import fail_job

        job_id = uuid4()
        error_msg = "OOM Error"
        mock_response = create_mock_job_response(
            id=job_id, status=JobStatus.FAILED, error_message=error_msg
        )

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.fail_job = AsyncMock(return_value=mock_response)

            from budcluster.jobs.schemas import JobStatusTransition

            transition = JobStatusTransition(
                status=JobStatus.FAILED, error_message=error_msg
            )
            result = await fail_job(job_id, transition)
            assert result.status == JobStatus.FAILED

    @pytest.mark.asyncio
    async def test_cancel_job_success(self):
        """Test successful job cancellation."""
        from budcluster.jobs.routes import cancel_job

        job_id = uuid4()
        mock_response = create_mock_job_response(id=job_id, status=JobStatus.CANCELLED)

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.cancel_job = AsyncMock(return_value=mock_response)

            result = await cancel_job(job_id)
            assert result.status == JobStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_retry_job_success(self):
        """Test successful job retry."""
        from budcluster.jobs.routes import retry_job

        job_id = uuid4()
        mock_response = create_mock_job_response(
            id=job_id, status=JobStatus.RETRYING, retry_count=1
        )

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.retry_job = AsyncMock(return_value=mock_response)

            result = await retry_job(job_id)
            assert result.status == JobStatus.RETRYING

    @pytest.mark.asyncio
    async def test_timeout_job_success(self):
        """Test successful job timeout."""
        from budcluster.jobs.routes import timeout_job

        job_id = uuid4()
        mock_response = create_mock_job_response(id=job_id, status=JobStatus.TIMEOUT)

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.timeout_job = AsyncMock(return_value=mock_response)

            result = await timeout_job(job_id)
            assert result.status == JobStatus.TIMEOUT


class TestQueryEndpoints:
    """Test cases for query endpoints."""

    @pytest.mark.asyncio
    async def test_get_active_jobs_success(self):
        """Test successful active jobs retrieval."""
        from budcluster.jobs.routes import get_active_jobs

        mock_jobs = [
            create_mock_job_response(status=JobStatus.RUNNING),
            create_mock_job_response(status=JobStatus.RETRYING),
        ]

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.get_active_jobs = AsyncMock(return_value=mock_jobs)

            result = await get_active_jobs()
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_pending_jobs_success(self):
        """Test successful pending jobs retrieval."""
        from budcluster.jobs.routes import get_pending_jobs

        mock_jobs = [
            create_mock_job_response(status=JobStatus.PENDING),
            create_mock_job_response(status=JobStatus.QUEUED),
        ]

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.get_pending_jobs = AsyncMock(return_value=mock_jobs)

            result = await get_pending_jobs()
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_can_retry_true(self):
        """Test can_retry returns true when under limit."""
        from budcluster.jobs.routes import can_retry

        job_id = uuid4()

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.can_retry = AsyncMock(return_value=True)

            result = await can_retry(job_id)
            assert result["can_retry"] is True

    @pytest.mark.asyncio
    async def test_can_retry_false(self):
        """Test can_retry returns false when at limit."""
        from budcluster.jobs.routes import can_retry

        job_id = uuid4()

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.can_retry = AsyncMock(return_value=False)

            result = await can_retry(job_id)
            assert result["can_retry"] is False


class TestSourceRouteEndpoints:
    """Test cases for source-based route endpoints."""

    @pytest.mark.asyncio
    async def test_get_job_by_source_success(self):
        """Test successful job retrieval by source."""
        from budcluster.jobs.routes import get_job_by_source

        source_id = uuid4()
        mock_response = create_mock_job_response(
            source=JobSource.BUDUSECASES, source_id=source_id
        )

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.get_job_by_source_id = AsyncMock(return_value=mock_response)

            result = await get_job_by_source(JobSource.BUDUSECASES, source_id)
            assert result.source_id == source_id

    @pytest.mark.asyncio
    async def test_list_jobs_by_cluster_success(self):
        """Test successful job listing by cluster."""
        from budcluster.jobs.routes import list_jobs_by_cluster

        cluster_id = uuid4()
        mock_response = JobListResponse(
            jobs=[create_mock_job_response(cluster_id=cluster_id) for _ in range(3)],
            total=3,
            page=1,
            page_size=10,
        )

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.list_jobs_by_cluster = AsyncMock(return_value=mock_response)

            result = await list_jobs_by_cluster(cluster_id)
            assert len(result.jobs) == 3
