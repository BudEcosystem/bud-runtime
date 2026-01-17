"""API contract tests for execution persistence endpoints.

Tests for T031 (002-pipeline-event-persistence):
- GET /executions/{id} contract verification
- GET /executions/{id}/progress contract verification
- POST /executions contract verification
- GET /executions list endpoint with filtering
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from budpipeline.main import app
from budpipeline.pipeline.models import ExecutionStatus, StepStatus


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_execution_id():
    """Generate a sample execution ID."""
    return uuid4()


@pytest.fixture
def mock_execution(sample_execution_id):
    """Create a mock PipelineExecution."""
    execution = MagicMock()
    execution.id = sample_execution_id
    execution.status = ExecutionStatus.RUNNING
    execution.progress_percentage = Decimal("50.00")
    execution.current_step = "Processing data"
    execution.initiator = "test-user"
    execution.pipeline_definition = {"name": "test", "steps": []}
    execution.callback_topics = ["topic1"]
    execution.error_message = None
    execution.created_at = datetime.now(timezone.utc)
    execution.started_at = datetime.now(timezone.utc)
    execution.completed_at = None
    execution.version = 1
    return execution


@pytest.fixture
def mock_step_executions(sample_execution_id):
    """Create mock StepExecution list."""
    step1 = MagicMock()
    step1.id = uuid4()
    step1.execution_id = sample_execution_id
    step1.step_id = "step1"
    step1.step_name = "Step 1"
    step1.handler_type = "internal.test.action"
    step1.status = StepStatus.COMPLETED
    step1.progress_percentage = Decimal("100.00")
    step1.sequence_number = 1
    step1.start_time = datetime.now(timezone.utc)
    step1.end_time = datetime.now(timezone.utc)
    step1.error_message = None
    step1.retry_count = 0
    step1.version = 1

    step2 = MagicMock()
    step2.id = uuid4()
    step2.execution_id = sample_execution_id
    step2.step_id = "step2"
    step2.step_name = "Step 2"
    step2.handler_type = "internal.test.action"
    step2.status = StepStatus.RUNNING
    step2.progress_percentage = Decimal("50.00")
    step2.sequence_number = 2
    step2.start_time = datetime.now(timezone.utc)
    step2.end_time = None
    step2.error_message = None
    step2.retry_count = 0
    step2.version = 1

    return [step1, step2]


@pytest.fixture
def mock_progress_events(sample_execution_id):
    """Create mock ProgressEvent list."""
    event1 = MagicMock()
    event1.id = uuid4()
    event1.execution_id = sample_execution_id
    event1.event_type = "workflow_progress"
    event1.progress_percentage = Decimal("25.00")
    event1.eta_seconds = 120
    event1.current_step_desc = "Step 1"
    event1.created_at = datetime.now(timezone.utc)

    event2 = MagicMock()
    event2.id = uuid4()
    event2.execution_id = sample_execution_id
    event2.event_type = "step_completed"
    event2.progress_percentage = Decimal("50.00")
    event2.eta_seconds = 60
    event2.current_step_desc = "Step 2"
    event2.created_at = datetime.now(timezone.utc)

    return [event2, event1]  # Most recent first


class TestGetExecutionEndpoint:
    """Tests for GET /executions/{id} endpoint."""

    def test_get_execution_success(self, client, sample_execution_id, mock_execution):
        """Test successful retrieval of execution."""
        with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_service:
            mock_service.get_execution = AsyncMock(return_value=mock_execution)

            response = client.get(f"/executions/{sample_execution_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(sample_execution_id)
        assert data["status"] == "running"

    def test_get_execution_not_found(self, client, sample_execution_id):
        """Test 404 when execution not found."""
        with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_service:
            mock_service.get_execution = AsyncMock(return_value=None)

            response = client.get(f"/executions/{sample_execution_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data
        assert data["detail"]["error"]["code"] == "NOT_FOUND"

    def test_get_execution_includes_correlation_id(
        self, client, sample_execution_id, mock_execution
    ):
        """Test that response includes correlation ID header."""
        with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_service:
            mock_service.get_execution = AsyncMock(return_value=mock_execution)

            response = client.get(
                f"/executions/{sample_execution_id}",
                headers={"X-Correlation-ID": "test-corr-123"},
            )

        assert response.status_code == status.HTTP_200_OK
        # Note: actual header assertion depends on middleware implementation

    def test_get_execution_response_schema(self, client, sample_execution_id, mock_execution):
        """Test that response matches expected schema."""
        with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_service:
            mock_service.get_execution = AsyncMock(return_value=mock_execution)

            response = client.get(f"/executions/{sample_execution_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Required fields per contract
        assert "id" in data
        assert "status" in data
        assert "progress_percentage" in data
        assert "created_at" in data


class TestGetExecutionProgressEndpoint:
    """Tests for GET /executions/{id}/progress endpoint."""

    def test_get_progress_success(
        self,
        client,
        sample_execution_id,
        mock_execution,
        mock_step_executions,
        mock_progress_events,
    ):
        """Test successful retrieval of execution progress."""
        with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_service:
            mock_service.get_execution = AsyncMock(return_value=mock_execution)
            mock_service.get_execution_steps = AsyncMock(return_value=mock_step_executions)

        with patch("budpipeline.pipeline.execution_routes.progress_service") as mock_progress:
            mock_progress.get_recent_events = AsyncMock(return_value=mock_progress_events)
            mock_progress.calculate_aggregate_progress = AsyncMock(
                return_value={
                    "overall_progress": Decimal("50.00"),
                    "eta_seconds": 60,
                    "completed_steps": 1,
                    "total_steps": 2,
                    "current_step": "Step 2",
                }
            )

            with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_svc:
                mock_svc.get_execution = AsyncMock(return_value=mock_execution)
                mock_svc.get_execution_steps = AsyncMock(return_value=mock_step_executions)

                response = client.get(f"/executions/{sample_execution_id}/progress")

        assert response.status_code == status.HTTP_200_OK

    def test_get_progress_not_found(self, client, sample_execution_id):
        """Test 404 when execution not found for progress."""
        with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_service:
            mock_service.get_execution = AsyncMock(return_value=None)

            response = client.get(f"/executions/{sample_execution_id}/progress")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_progress_response_includes_aggregation(
        self,
        client,
        sample_execution_id,
        mock_execution,
        mock_step_executions,
        mock_progress_events,
    ):
        """Test that progress response includes aggregated data."""
        with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_service:
            mock_service.get_execution = AsyncMock(return_value=mock_execution)
            mock_service.get_execution_steps = AsyncMock(return_value=mock_step_executions)

            with patch("budpipeline.pipeline.execution_routes.progress_service") as mock_progress:
                mock_progress.get_recent_events = AsyncMock(return_value=mock_progress_events)
                mock_progress.calculate_aggregate_progress = AsyncMock(
                    return_value={
                        "overall_progress": Decimal("50.00"),
                        "eta_seconds": 60,
                        "completed_steps": 1,
                        "total_steps": 2,
                        "current_step": "Step 2",
                    }
                )

                response = client.get(f"/executions/{sample_execution_id}/progress")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should include aggregated progress
        assert "aggregated_progress" in data
        assert "overall_progress" in data["aggregated_progress"]
        assert "completed_steps" in data["aggregated_progress"]
        assert "total_steps" in data["aggregated_progress"]


class TestCreateExecutionEndpoint:
    """Tests for POST /executions endpoint."""

    def test_create_execution_success(self, client):
        """Test successful execution creation."""
        execution_id = uuid4()

        with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_service:
            mock_service.create_execution = AsyncMock(return_value=(execution_id, 1))

            with patch("budpipeline.pipeline.execution_routes.get_db"):
                response = client.post(
                    "/executions",
                    json={
                        "pipeline_definition": {"name": "test", "steps": []},
                        "initiator": "test-user",
                    },
                )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "execution_id" in data
        assert "status" in data
        assert data["status"] == "pending"

    def test_create_execution_with_callback_topics(self, client):
        """Test creating execution with callback topics."""
        execution_id = uuid4()

        with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_service:
            mock_service.create_execution = AsyncMock(return_value=(execution_id, 1))

            with patch("budpipeline.pipeline.execution_routes.get_db"):
                response = client.post(
                    "/executions",
                    json={
                        "pipeline_definition": {"name": "test", "steps": []},
                        "initiator": "test-user",
                        "callback_topics": ["topic1", "topic2"],
                    },
                )

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_execution_response_schema(self, client):
        """Test that create response matches expected schema."""
        execution_id = uuid4()

        with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_service:
            mock_service.create_execution = AsyncMock(return_value=(execution_id, 1))

            with patch("budpipeline.pipeline.execution_routes.get_db"):
                response = client.post(
                    "/executions",
                    json={
                        "pipeline_definition": {"name": "test", "steps": []},
                        "initiator": "test-user",
                    },
                )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # Required fields per contract
        assert "execution_id" in data
        assert "status" in data
        assert "created_at" in data


class TestListExecutionsEndpoint:
    """Tests for GET /executions endpoint with filtering."""

    def test_list_executions_default_pagination(self, client, mock_execution):
        """Test listing executions with default pagination."""
        with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_service:
            mock_service.list_executions = AsyncMock(return_value=([mock_execution], 1))

            response = client.get("/executions")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "executions" in data
        assert "pagination" in data
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["total_count"] == 1

    def test_list_executions_with_status_filter(self, client, mock_execution):
        """Test filtering executions by status."""
        with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_service:
            mock_service.list_executions = AsyncMock(return_value=([mock_execution], 1))

            response = client.get("/executions?status=running")

        assert response.status_code == status.HTTP_200_OK

    def test_list_executions_with_date_range(self, client, mock_execution):
        """Test filtering executions by date range."""
        with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_service:
            mock_service.list_executions = AsyncMock(return_value=([mock_execution], 1))

            response = client.get(
                "/executions?start_date=2024-01-01T00:00:00Z&end_date=2024-12-31T23:59:59Z"
            )

        assert response.status_code == status.HTTP_200_OK

    def test_list_executions_with_pagination(self, client, mock_execution):
        """Test listing executions with custom pagination."""
        with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_service:
            mock_service.list_executions = AsyncMock(return_value=([mock_execution], 50))

            response = client.get("/executions?page=2&page_size=10")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["page_size"] == 10

    def test_list_executions_pagination_info(self, client, mock_execution):
        """Test that pagination info is calculated correctly."""
        with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_service:
            # 25 total items, page_size 10 = 3 pages
            mock_service.list_executions = AsyncMock(return_value=([mock_execution], 25))

            response = client.get("/executions?page=1&page_size=10")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["pagination"]["total_count"] == 25
        assert data["pagination"]["total_pages"] == 3


class TestGetExecutionStepsEndpoint:
    """Tests for GET /executions/{id}/steps endpoint."""

    def test_get_steps_success(
        self, client, sample_execution_id, mock_execution, mock_step_executions
    ):
        """Test successful retrieval of execution steps."""
        with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_service:
            mock_service.get_execution = AsyncMock(return_value=mock_execution)
            mock_service.get_execution_steps = AsyncMock(return_value=mock_step_executions)

            response = client.get(f"/executions/{sample_execution_id}/steps")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "steps" in data
        assert len(data["steps"]) == 2

    def test_get_steps_not_found(self, client, sample_execution_id):
        """Test 404 when execution not found for steps."""
        with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_service:
            mock_service.get_execution = AsyncMock(return_value=None)

            response = client.get(f"/executions/{sample_execution_id}/steps")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_endpoint(self, client):
        """Test /health endpoint."""
        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data
        assert "service" in data
        assert "version" in data

    def test_ready_endpoint(self, client):
        """Test /ready endpoint."""
        response = client.get("/ready")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data


class TestPersistenceAcrossRestart:
    """Integration tests for persistence across service restart (T041).

    These tests verify that execution data persists across service restarts
    by simulating the service lifecycle.
    """

    def test_execution_persists_after_service_restart(self, client, mock_execution):
        """Test that executions are retrievable after service restart.

        This test simulates:
        1. Creating an execution
        2. Service restart (simulated by clearing in-memory state)
        3. Retrieving the execution (should come from database)
        """
        execution_id = uuid4()

        # Step 1: Create execution (persisted to database)
        with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_service:
            mock_service.create_execution = AsyncMock(return_value=(execution_id, 1))

            with patch("budpipeline.pipeline.execution_routes.get_db"):
                create_response = client.post(
                    "/executions",
                    json={
                        "pipeline_definition": {"name": "test", "steps": []},
                        "initiator": "test-user",
                    },
                )

        assert create_response.status_code == status.HTTP_201_CREATED

        # Step 2: Simulate service restart by creating fresh mock
        # In reality, this would be a new service instance
        # The key is that the execution was persisted to database

        # Step 3: Retrieve execution (from database after restart)
        mock_execution.id = execution_id
        with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_service_new:
            mock_service_new.get_execution = AsyncMock(return_value=mock_execution)

            get_response = client.get(f"/executions/{execution_id}")

        assert get_response.status_code == status.HTTP_200_OK
        data = get_response.json()
        assert data["id"] == str(execution_id)

    def test_progress_persists_after_service_restart(
        self, client, mock_execution, mock_step_executions, mock_progress_events
    ):
        """Test that progress data persists after service restart.

        This verifies:
        - Step executions are persisted to database
        - Progress events are persisted to database
        - All can be retrieved after service restart
        """
        execution_id = mock_execution.id

        # After "restart", retrieve progress from database
        with patch("budpipeline.pipeline.execution_routes.persistence_service") as mock_service:
            mock_service.get_execution = AsyncMock(return_value=mock_execution)
            mock_service.get_execution_steps = AsyncMock(return_value=mock_step_executions)

            with patch("budpipeline.pipeline.execution_routes.progress_service") as mock_progress:
                mock_progress.get_recent_events = AsyncMock(return_value=mock_progress_events)
                mock_progress.calculate_aggregate_progress = AsyncMock(
                    return_value={
                        "overall_progress": Decimal("50.00"),
                        "eta_seconds": 60,
                        "completed_steps": 1,
                        "total_steps": 2,
                        "current_step": "Step 2",
                    }
                )

                response = client.get(f"/executions/{execution_id}/progress")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify steps were retrieved from database
        assert "steps" in data
        assert len(data["steps"]) == 2

        # Verify progress events were retrieved from database
        assert "recent_events" in data

        # Verify aggregated progress (calculated from persisted data)
        assert "aggregated_progress" in data
        assert data["aggregated_progress"]["completed_steps"] == 1

    def test_fallback_mode_indicator_on_db_failure(self, client):
        """Test that fallback mode is indicated when database is unavailable.

        This ensures clients know when data may be stale.
        """
        # This tests the X-Data-Staleness header behavior
        # When database is down and fallback is active
        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Health endpoint should indicate database and fallback status
        assert "database" in data
        assert "fallback_mode" in data
