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

"""TDD Tests for BudCluster Client.

These tests follow TDD methodology - written BEFORE implementation.
Tests are expected to fail until the implementation is complete.

The BudCluster client provides Dapr service invocation to communicate
with the BudCluster service for job creation and deployment orchestration.
"""

from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

# ============================================================================
# BudCluster Client Schema Tests
# ============================================================================


class TestBudClusterSchemas:
    """Tests for BudCluster client request/response schemas."""

    def test_job_create_request_schema(self) -> None:
        """Test JobCreateRequest schema for creating jobs."""
        from budusecases.clients.budcluster.schemas import JobCreateRequest, JobSource, JobType

        request = JobCreateRequest(
            name="deploy-llama-3-8b",
            job_type=JobType.MODEL_DEPLOYMENT,
            source=JobSource.BUDUSECASES,
            source_id=str(uuid4()),
            cluster_id=uuid4(),
            config={"model_id": "meta-llama/Meta-Llama-3-8B-Instruct"},
            metadata_={"component_name": "llm"},
        )

        assert request.name == "deploy-llama-3-8b"
        assert request.job_type == JobType.MODEL_DEPLOYMENT
        assert request.source == JobSource.BUDUSECASES

    def test_job_create_request_minimal(self) -> None:
        """Test JobCreateRequest with minimal fields."""
        from budusecases.clients.budcluster.schemas import JobCreateRequest, JobSource, JobType

        request = JobCreateRequest(
            name="simple-job",
            job_type=JobType.GENERIC,
            source=JobSource.BUDUSECASES,
            source_id=str(uuid4()),
            cluster_id=uuid4(),
        )

        assert request.config == {}
        assert request.metadata_ == {}

    def test_job_response_schema(self) -> None:
        """Test JobResponse schema for job details."""
        from budusecases.clients.budcluster.schemas import JobResponse, JobStatus, JobType

        job_id = uuid4()
        cluster_id = uuid4()

        response = JobResponse(
            id=job_id,
            name="test-job",
            job_type=JobType.MODEL_DEPLOYMENT,
            status=JobStatus.PENDING,
            cluster_id=cluster_id,
            config={},
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        assert response.id == job_id
        assert response.status == JobStatus.PENDING

    def test_job_status_update_request(self) -> None:
        """Test JobStatusUpdateRequest schema."""
        from budusecases.clients.budcluster.schemas import (
            JobStatus,
            JobStatusUpdateRequest,
        )

        request = JobStatusUpdateRequest(
            status=JobStatus.RUNNING,
            message="Deployment started",
        )

        assert request.status == JobStatus.RUNNING
        assert request.message == "Deployment started"

    def test_job_list_response_schema(self) -> None:
        """Test JobListResponse schema for paginated results."""
        from budusecases.clients.budcluster.schemas import (
            JobListResponse,
            JobResponse,
            JobStatus,
            JobType,
        )

        jobs = [
            JobResponse(
                id=uuid4(),
                name="job-1",
                job_type=JobType.MODEL_DEPLOYMENT,
                status=JobStatus.COMPLETED,
                cluster_id=uuid4(),
                config={},
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
            ),
            JobResponse(
                id=uuid4(),
                name="job-2",
                job_type=JobType.MODEL_DEPLOYMENT,
                status=JobStatus.RUNNING,
                cluster_id=uuid4(),
                config={},
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
            ),
        ]

        response = JobListResponse(
            items=jobs,
            total=2,
            page=1,
            page_size=10,
        )

        assert len(response.items) == 2
        assert response.total == 2

    def test_cluster_info_response_schema(self) -> None:
        """Test ClusterInfoResponse schema."""
        from budusecases.clients.budcluster.schemas import (
            ClusterInfoResponse,
            ClusterStatus,
        )

        response = ClusterInfoResponse(
            id=uuid4(),
            name="prod-cluster",
            status=ClusterStatus.ACTIVE,
            provider="aws",
            region="us-east-1",
            kubernetes_version="1.28",
            node_count=5,
            gpu_available=True,
            gpu_count=8,
        )

        assert response.name == "prod-cluster"
        assert response.status == ClusterStatus.ACTIVE
        assert response.gpu_count == 8


# ============================================================================
# BudCluster Client Tests
# ============================================================================


class TestBudClusterClient:
    """Tests for BudClusterClient class."""

    @pytest.fixture
    def mock_dapr_client(self) -> MagicMock:
        """Create a mock Dapr client.

        Note: invoke_method is a regular Mock because the client uses
        asyncio.to_thread() to wrap the synchronous Dapr client call.
        """
        client = MagicMock()
        client.invoke_method = MagicMock()
        return client

    @pytest.fixture
    def client(self, mock_dapr_client: MagicMock) -> Any:
        """Create a BudClusterClient instance with mocked Dapr."""
        from budusecases.clients.budcluster.client import BudClusterClient

        with patch(
            "budusecases.clients.budcluster.client.DaprClient",
            return_value=mock_dapr_client,
        ):
            return BudClusterClient()

    def test_client_initialization(self) -> None:
        """Test BudClusterClient initialization."""
        from budusecases.clients.budcluster.client import BudClusterClient

        with patch("budusecases.clients.budcluster.client.DaprClient"):
            client = BudClusterClient()
            assert client.app_id == "budcluster"

    def test_client_custom_app_id(self) -> None:
        """Test BudClusterClient with custom app ID."""
        from budusecases.clients.budcluster.client import BudClusterClient

        with patch("budusecases.clients.budcluster.client.DaprClient"):
            client = BudClusterClient(app_id="custom-budcluster")
            assert client.app_id == "custom-budcluster"

    @pytest.mark.asyncio
    async def test_create_job(self, client: Any, mock_dapr_client: MagicMock) -> None:
        """Test creating a job via BudCluster."""
        from budusecases.clients.budcluster.schemas import (
            JobCreateRequest,
            JobResponse,
            JobSource,
            JobStatus,
            JobType,
        )

        job_id = uuid4()
        cluster_id = uuid4()

        # Mock response - must set status_code explicitly to avoid MagicMock comparison issues
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": str(job_id),
            "name": "deploy-llm",
            "job_type": "model_deployment",
            "status": "pending",
            "cluster_id": str(cluster_id),
            "config": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        mock_dapr_client.invoke_method.return_value = mock_response

        request = JobCreateRequest(
            name="deploy-llm",
            job_type=JobType.MODEL_DEPLOYMENT,
            source=JobSource.BUDUSECASES,
            source_id=str(uuid4()),
            cluster_id=cluster_id,
        )

        result = await client.create_job(request)

        assert isinstance(result, JobResponse)
        assert result.id == job_id
        assert result.status == JobStatus.PENDING

        mock_dapr_client.invoke_method.assert_called_once()
        call_args = mock_dapr_client.invoke_method.call_args
        assert call_args.kwargs["app_id"] == "budcluster"
        assert call_args.kwargs["method_name"] == "jobs"
        assert call_args.kwargs["http_verb"] == "POST"

    @pytest.mark.asyncio
    async def test_get_job(self, client: Any, mock_dapr_client: MagicMock) -> None:
        """Test getting a job by ID."""
        from budusecases.clients.budcluster.schemas import JobResponse, JobStatus

        job_id = uuid4()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": str(job_id),
            "name": "existing-job",
            "job_type": "model_deployment",
            "status": "running",
            "cluster_id": str(uuid4()),
            "config": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        mock_dapr_client.invoke_method.return_value = mock_response

        result = await client.get_job(job_id)

        assert isinstance(result, JobResponse)
        assert result.id == job_id
        assert result.status == JobStatus.RUNNING

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, client: Any, mock_dapr_client: MagicMock) -> None:
        """Test getting a job that doesn't exist."""
        from budusecases.clients.budcluster.exceptions import JobNotFoundError

        mock_dapr_client.invoke_method.return_value = MagicMock(
            status_code=404,
            json=MagicMock(return_value={"detail": "Job not found"}),
        )

        with pytest.raises(JobNotFoundError):
            await client.get_job(uuid4())

    @pytest.mark.asyncio
    async def test_list_jobs(self, client: Any, mock_dapr_client: MagicMock) -> None:
        """Test listing jobs with filters."""
        from budusecases.clients.budcluster.schemas import JobListResponse

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "id": str(uuid4()),
                    "name": "job-1",
                    "job_type": "model_deployment",
                    "status": "completed",
                    "cluster_id": str(uuid4()),
                    "config": {},
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 10,
        }
        mock_dapr_client.invoke_method.return_value = mock_response

        result = await client.list_jobs(
            source="BUDUSECASES",
            source_id=str(uuid4()),
            page=1,
            page_size=10,
        )

        assert isinstance(result, JobListResponse)
        assert len(result.items) == 1
        assert result.total == 1

    @pytest.mark.asyncio
    async def test_update_job_status(self, client: Any, mock_dapr_client: MagicMock) -> None:
        """Test updating a job's status."""
        from budusecases.clients.budcluster.schemas import (
            JobResponse,
            JobStatus,
            JobStatusUpdateRequest,
        )

        job_id = uuid4()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": str(job_id),
            "name": "job-to-update",
            "job_type": "model_deployment",
            "status": "completed",
            "cluster_id": str(uuid4()),
            "config": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        mock_dapr_client.invoke_method.return_value = mock_response

        request = JobStatusUpdateRequest(
            status=JobStatus.COMPLETED,
            message="Deployment successful",
        )

        result = await client.update_job_status(job_id, request)

        assert isinstance(result, JobResponse)
        assert result.status == JobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_cancel_job(self, client: Any, mock_dapr_client: MagicMock) -> None:
        """Test cancelling a job."""
        from budusecases.clients.budcluster.schemas import JobResponse, JobStatus

        job_id = uuid4()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": str(job_id),
            "name": "job-to-cancel",
            "job_type": "model_deployment",
            "status": "cancelled",
            "cluster_id": str(uuid4()),
            "config": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        mock_dapr_client.invoke_method.return_value = mock_response

        result = await client.cancel_job(job_id)

        assert isinstance(result, JobResponse)
        assert result.status == JobStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_get_cluster_info(self, client: Any, mock_dapr_client: MagicMock) -> None:
        """Test getting cluster information."""
        from budusecases.clients.budcluster.schemas import (
            ClusterInfoResponse,
            ClusterStatus,
        )

        cluster_id = uuid4()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": str(cluster_id),
            "name": "prod-cluster",
            "status": "active",
            "provider": "aws",
            "region": "us-east-1",
            "kubernetes_version": "1.28",
            "node_count": 5,
            "gpu_available": True,
            "gpu_count": 8,
        }
        mock_dapr_client.invoke_method.return_value = mock_response

        result = await client.get_cluster_info(cluster_id)

        assert isinstance(result, ClusterInfoResponse)
        assert result.id == cluster_id
        assert result.status == ClusterStatus.ACTIVE
        assert result.gpu_count == 8

    @pytest.mark.asyncio
    async def test_list_available_clusters(self, client: Any, mock_dapr_client: MagicMock) -> None:
        """Test listing available clusters for deployment."""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "id": str(uuid4()),
                    "name": "cluster-1",
                    "status": "active",
                    "provider": "aws",
                    "region": "us-east-1",
                    "kubernetes_version": "1.28",
                    "node_count": 5,
                    "gpu_available": True,
                    "gpu_count": 4,
                },
                {
                    "id": str(uuid4()),
                    "name": "cluster-2",
                    "status": "active",
                    "provider": "azure",
                    "region": "eastus",
                    "kubernetes_version": "1.27",
                    "node_count": 3,
                    "gpu_available": False,
                    "gpu_count": 0,
                },
            ],
            "total": 2,
        }
        mock_dapr_client.invoke_method.return_value = mock_response

        result = await client.list_available_clusters()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_check_cluster_capacity(self, client: Any, mock_dapr_client: MagicMock) -> None:
        """Test checking cluster capacity for deployment."""
        from budusecases.clients.budcluster.schemas import ClusterCapacityResponse

        cluster_id = uuid4()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "cluster_id": str(cluster_id),
            "has_capacity": True,
            "available_cpu": 16,
            "available_memory": "64Gi",
            "available_gpu": 4,
            "available_gpu_memory": "96Gi",
        }
        mock_dapr_client.invoke_method.return_value = mock_response

        result = await client.check_cluster_capacity(
            cluster_id=cluster_id,
            required_cpu=4,
            required_memory="16Gi",
            required_gpu=1,
        )

        assert isinstance(result, ClusterCapacityResponse)
        assert result.has_capacity is True
        assert result.available_gpu == 4


# ============================================================================
# BudCluster Client Error Handling Tests
# ============================================================================


class TestBudClusterClientErrors:
    """Tests for BudCluster client error handling."""

    @pytest.fixture
    def mock_dapr_client(self) -> MagicMock:
        """Create a mock Dapr client.

        Note: invoke_method is a regular Mock because the client uses
        asyncio.to_thread() to wrap the synchronous Dapr client call.
        """
        client = MagicMock()
        client.invoke_method = MagicMock()
        return client

    @pytest.fixture
    def client(self, mock_dapr_client: MagicMock) -> Any:
        """Create a BudClusterClient instance with mocked Dapr."""
        from budusecases.clients.budcluster.client import BudClusterClient

        with patch(
            "budusecases.clients.budcluster.client.DaprClient",
            return_value=mock_dapr_client,
        ):
            return BudClusterClient()

    @pytest.mark.asyncio
    async def test_connection_error(self, client: Any, mock_dapr_client: MagicMock) -> None:
        """Test handling connection errors."""
        from budusecases.clients.budcluster.exceptions import BudClusterConnectionError

        mock_dapr_client.invoke_method.side_effect = Exception("Connection refused")

        with pytest.raises(BudClusterConnectionError):
            await client.get_job(uuid4())

    @pytest.mark.asyncio
    async def test_timeout_error(self, client: Any, mock_dapr_client: MagicMock) -> None:
        """Test handling timeout errors."""

        from budusecases.clients.budcluster.exceptions import BudClusterTimeoutError

        mock_dapr_client.invoke_method.side_effect = TimeoutError()

        with pytest.raises(BudClusterTimeoutError):
            await client.get_job(uuid4())

    @pytest.mark.asyncio
    async def test_cluster_not_found(self, client: Any, mock_dapr_client: MagicMock) -> None:
        """Test handling cluster not found errors."""
        from budusecases.clients.budcluster.exceptions import ClusterNotFoundError

        mock_dapr_client.invoke_method.return_value = MagicMock(
            status_code=404,
            json=MagicMock(return_value={"detail": "Cluster not found"}),
        )

        with pytest.raises(ClusterNotFoundError):
            await client.get_cluster_info(uuid4())

    @pytest.mark.asyncio
    async def test_validation_error(self, client: Any, mock_dapr_client: MagicMock) -> None:
        """Test handling validation errors from BudCluster."""
        from budusecases.clients.budcluster.exceptions import BudClusterValidationError

        mock_dapr_client.invoke_method.return_value = MagicMock(
            status_code=422,
            json=MagicMock(return_value={"detail": [{"loc": ["body", "name"], "msg": "required"}]}),
        )

        from budusecases.clients.budcluster.schemas import (
            JobCreateRequest,
            JobSource,
            JobType,
        )

        request = JobCreateRequest(
            name="",  # Invalid empty name
            job_type=JobType.MODEL_DEPLOYMENT,
            source=JobSource.BUDUSECASES,
            source_id=str(uuid4()),
            cluster_id=uuid4(),
        )

        with pytest.raises(BudClusterValidationError):
            await client.create_job(request)

    @pytest.mark.asyncio
    async def test_internal_server_error(self, client: Any, mock_dapr_client: MagicMock) -> None:
        """Test handling internal server errors."""
        from budusecases.clients.budcluster.exceptions import BudClusterError

        mock_dapr_client.invoke_method.return_value = MagicMock(
            status_code=500,
            json=MagicMock(return_value={"detail": "Internal server error"}),
        )

        with pytest.raises(BudClusterError):
            await client.get_job(uuid4())


# ============================================================================
# BudCluster Client Retry Tests
# ============================================================================


class TestBudClusterClientRetry:
    """Tests for BudCluster client retry behavior."""

    @pytest.fixture
    def mock_dapr_client(self) -> MagicMock:
        """Create a mock Dapr client.

        Note: invoke_method is a regular Mock because the client uses
        asyncio.to_thread() to wrap the synchronous Dapr client call.
        """
        client = MagicMock()
        client.invoke_method = MagicMock()
        return client

    @pytest.fixture
    def client_with_retry(self, mock_dapr_client: MagicMock) -> Any:
        """Create a BudClusterClient with retry configuration."""
        from budusecases.clients.budcluster.client import BudClusterClient

        with patch(
            "budusecases.clients.budcluster.client.DaprClient",
            return_value=mock_dapr_client,
        ):
            return BudClusterClient(
                max_retries=3,
                retry_delay=0.1,
            )

    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self, client_with_retry: Any, mock_dapr_client: MagicMock) -> None:
        """Test that transient errors trigger retry."""
        job_id = uuid4()

        # Create proper mock response for successful call
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "id": str(job_id),
            "name": "job",
            "job_type": "model_deployment",
            "status": "pending",
            "cluster_id": str(uuid4()),
            "config": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        # First two calls fail, third succeeds
        mock_dapr_client.invoke_method.side_effect = [
            Exception("Transient error"),
            Exception("Transient error"),
            success_response,
        ]

        result = await client_with_retry.get_job(job_id)

        assert result.id == job_id
        assert mock_dapr_client.invoke_method.call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, client_with_retry: Any, mock_dapr_client: MagicMock) -> None:
        """Test that max retries are respected."""
        from budusecases.clients.budcluster.exceptions import BudClusterConnectionError

        mock_dapr_client.invoke_method.side_effect = Exception("Persistent error")

        with pytest.raises(BudClusterConnectionError):
            await client_with_retry.get_job(uuid4())

        assert mock_dapr_client.invoke_method.call_count == 3


# ============================================================================
# BudCluster Enums Tests
# ============================================================================


class TestBudClusterEnums:
    """Tests for BudCluster client enums."""

    def test_job_type_enum(self) -> None:
        """Test JobType enum values."""
        from budusecases.clients.budcluster.schemas import JobType

        assert JobType.MODEL_DEPLOYMENT == "model_deployment"
        assert JobType.GENERIC == "generic"

    def test_job_status_enum(self) -> None:
        """Test JobStatus enum values."""
        from budusecases.clients.budcluster.schemas import JobStatus

        assert JobStatus.PENDING == "pending"
        assert JobStatus.RUNNING == "running"
        assert JobStatus.COMPLETED == "completed"
        assert JobStatus.FAILED == "failed"
        assert JobStatus.CANCELLED == "cancelled"

    def test_job_source_enum(self) -> None:
        """Test JobSource enum values."""
        from budusecases.clients.budcluster.schemas import JobSource

        assert JobSource.BUDUSECASES == "BUDUSECASES"
        assert JobSource.BUDAPP == "BUDAPP"
        assert JobSource.MANUAL == "MANUAL"

    def test_cluster_status_enum(self) -> None:
        """Test ClusterStatus enum values."""
        from budusecases.clients.budcluster.schemas import ClusterStatus

        assert ClusterStatus.ACTIVE == "active"
        assert ClusterStatus.INACTIVE == "inactive"
        assert ClusterStatus.PROVISIONING == "provisioning"
        assert ClusterStatus.ERROR == "error"
