"""Unit tests for ephemeral pipeline execution.

Tests for ephemeral execution feature (002-pipeline-event-persistence):
- Execute pipeline inline without saving the pipeline definition
- Execution is tracked and persisted but pipeline is NOT saved
- Execution has pipeline_id=None (ephemeral marker)
- Validation of inline pipeline definition
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from budpipeline.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def valid_pipeline_definition():
    """Valid inline pipeline definition."""
    return {
        "name": "ephemeral-test-pipeline",
        "version": "1.0",
        "steps": [
            {"id": "step1", "action": "log", "params": {"message": "Hello from ephemeral"}},
            {
                "id": "step2",
                "action": "log",
                "params": {"message": "Step 2"},
                "depends_on": ["step1"],
            },
        ],
    }


@pytest.fixture
def invalid_pipeline_definition():
    """Invalid pipeline definition with cycle."""
    return {
        "name": "invalid-pipeline",
        "version": "1.0",
        "steps": [
            {"id": "step1", "action": "log", "depends_on": ["step2"]},
            {"id": "step2", "action": "log", "depends_on": ["step1"]},  # Cycle!
        ],
    }


@pytest.fixture
def mock_execution_result():
    """Mock execution result."""
    execution_id = uuid4()
    return {
        "execution_id": str(execution_id),
        "workflow_id": "ephemeral",  # Special marker for ephemeral executions
        "workflow_name": "ephemeral-test-pipeline",
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "params": {"input": "test"},
    }


class TestEphemeralExecutionEndpoint:
    """Tests for POST /executions/run endpoint."""

    def test_ephemeral_execution_success(
        self, client, valid_pipeline_definition, mock_execution_result
    ):
        """Test successful ephemeral execution."""
        with patch("budpipeline.pipeline.execution_routes.pipeline_service") as mock_service:
            mock_service.validate_dag = MagicMock(return_value=(True, [], []))
            mock_service._execute_pipeline_impl = AsyncMock(return_value=mock_execution_result)

            response = client.post(
                "/executions/run",
                json={
                    "pipeline_definition": valid_pipeline_definition,
                    "params": {"input": "test"},
                },
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "execution_id" in data
        assert data["workflow_id"] == "ephemeral"
        assert data["status"] == "running"

    def test_ephemeral_execution_with_user_id(
        self, client, valid_pipeline_definition, mock_execution_result
    ):
        """Test ephemeral execution with user_id for tracking ownership."""
        user_id = str(uuid4())

        with patch("budpipeline.pipeline.execution_routes.pipeline_service") as mock_service:
            mock_service.validate_dag = MagicMock(return_value=(True, [], []))
            mock_service._execute_pipeline_impl = AsyncMock(return_value=mock_execution_result)

            response = client.post(
                "/executions/run",
                json={
                    "pipeline_definition": valid_pipeline_definition,
                    "user_id": user_id,
                },
            )

        assert response.status_code == status.HTTP_201_CREATED
        # user_id is passed to execution for tracking (verified by execution completion)

    def test_ephemeral_execution_with_callback_topics(
        self, client, valid_pipeline_definition, mock_execution_result
    ):
        """Test ephemeral execution with callback topics for real-time updates."""
        callback_topics = ["my-progress-topic", "analytics-topic"]

        with patch("budpipeline.pipeline.execution_routes.pipeline_service") as mock_service:
            mock_service.validate_dag = MagicMock(return_value=(True, [], []))
            mock_service._execute_pipeline_impl = AsyncMock(return_value=mock_execution_result)

            response = client.post(
                "/executions/run",
                json={
                    "pipeline_definition": valid_pipeline_definition,
                    "callback_topics": callback_topics,
                },
            )

        assert response.status_code == status.HTTP_201_CREATED

        # Verify callback_topics were passed
        call_kwargs = mock_service._execute_pipeline_impl.call_args.kwargs
        assert call_kwargs.get("callback_topics") == callback_topics

    def test_ephemeral_execution_pipeline_id_is_none(
        self, client, valid_pipeline_definition, mock_execution_result
    ):
        """Test that ephemeral execution has pipeline_id=None (ephemeral marker)."""
        with patch("budpipeline.pipeline.execution_routes.pipeline_service") as mock_service:
            mock_service.validate_dag = MagicMock(return_value=(True, [], []))
            mock_service._execute_pipeline_impl = AsyncMock(return_value=mock_execution_result)

            response = client.post(
                "/executions/run",
                json={"pipeline_definition": valid_pipeline_definition},
            )

        assert response.status_code == status.HTTP_201_CREATED

        # Verify pipeline_id was None (ephemeral marker)
        call_kwargs = mock_service._execute_pipeline_impl.call_args.kwargs
        assert call_kwargs.get("pipeline_id") is None

    def test_ephemeral_execution_invalid_pipeline(self, client, invalid_pipeline_definition):
        """Test ephemeral execution with invalid pipeline definition."""
        with patch("budpipeline.pipeline.execution_routes.pipeline_service") as mock_service:
            mock_service.validate_dag = MagicMock(
                return_value=(False, ["Cycle detected in DAG"], [])
            )

            response = client.post(
                "/executions/run",
                json={"pipeline_definition": invalid_pipeline_definition},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "detail" in data
        # Error should mention validation failure
        assert "validation" in str(data["detail"]).lower() or "cycle" in str(data["detail"]).lower()

    def test_ephemeral_execution_empty_pipeline(self, client):
        """Test ephemeral execution with empty pipeline definition."""
        with patch("budpipeline.pipeline.execution_routes.pipeline_service") as mock_service:
            mock_service.validate_dag = MagicMock(
                return_value=(False, ["Pipeline must have at least one step"], [])
            )

            response = client.post(
                "/executions/run",
                json={
                    "pipeline_definition": {"name": "empty", "version": "1.0", "steps": []},
                },
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_ephemeral_execution_with_custom_initiator(
        self, client, valid_pipeline_definition, mock_execution_result
    ):
        """Test ephemeral execution with custom initiator."""
        with patch("budpipeline.pipeline.execution_routes.pipeline_service") as mock_service:
            mock_service.validate_dag = MagicMock(return_value=(True, [], []))
            mock_service._execute_pipeline_impl = AsyncMock(return_value=mock_execution_result)

            response = client.post(
                "/executions/run",
                json={
                    "pipeline_definition": valid_pipeline_definition,
                    "initiator": "test-automation",
                },
            )

        assert response.status_code == status.HTTP_201_CREATED

        # Verify initiator was passed
        call_kwargs = mock_service._execute_pipeline_impl.call_args.kwargs
        assert call_kwargs.get("initiator") == "test-automation"


class TestEphemeralExecutionNotSaved:
    """Tests verifying that ephemeral pipelines are NOT saved to database."""

    def test_pipeline_definition_not_persisted(
        self, client, valid_pipeline_definition, mock_execution_result
    ):
        """Test that the pipeline definition is NOT saved to the database.

        This is the core property of ephemeral execution - the execution is tracked
        but the pipeline definition itself is not saved.
        """
        with patch("budpipeline.pipeline.execution_routes.pipeline_service") as mock_service:
            mock_service.validate_dag = MagicMock(return_value=(True, [], []))
            mock_service._execute_pipeline_impl = AsyncMock(return_value=mock_execution_result)

            # Execute ephemeral pipeline
            response = client.post(
                "/executions/run",
                json={"pipeline_definition": valid_pipeline_definition},
            )

        assert response.status_code == status.HTTP_201_CREATED

        # Verify create_pipeline_async was NOT called
        mock_service.create_pipeline_async.assert_not_called()

    def test_execution_is_persisted(self, client, valid_pipeline_definition, mock_execution_result):
        """Test that the execution itself IS persisted for tracking."""
        execution_id = uuid4()
        mock_execution_result["execution_id"] = str(execution_id)

        with patch("budpipeline.pipeline.execution_routes.pipeline_service") as mock_service:
            mock_service.validate_dag = MagicMock(return_value=(True, [], []))
            mock_service._execute_pipeline_impl = AsyncMock(return_value=mock_execution_result)

            response = client.post(
                "/executions/run",
                json={"pipeline_definition": valid_pipeline_definition},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # The execution should have a real ID (persisted)
        assert data["execution_id"] == str(execution_id)


class TestEphemeralExecutionResponse:
    """Tests for ephemeral execution response format."""

    def test_response_matches_execution_schema(
        self, client, valid_pipeline_definition, mock_execution_result
    ):
        """Test that response matches ExecutionResponse schema."""
        with patch("budpipeline.pipeline.execution_routes.pipeline_service") as mock_service:
            mock_service.validate_dag = MagicMock(return_value=(True, [], []))
            mock_service._execute_pipeline_impl = AsyncMock(return_value=mock_execution_result)

            response = client.post(
                "/executions/run",
                json={"pipeline_definition": valid_pipeline_definition},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # Required fields per ExecutionResponse schema
        assert "execution_id" in data
        assert "workflow_id" in data
        assert "workflow_name" in data
        assert "status" in data
        assert "started_at" in data

    def test_response_includes_workflow_name_from_definition(
        self, client, valid_pipeline_definition, mock_execution_result
    ):
        """Test that workflow_name comes from the pipeline definition."""
        mock_execution_result["workflow_name"] = valid_pipeline_definition["name"]

        with patch("budpipeline.pipeline.execution_routes.pipeline_service") as mock_service:
            mock_service.validate_dag = MagicMock(return_value=(True, [], []))
            mock_service._execute_pipeline_impl = AsyncMock(return_value=mock_execution_result)

            response = client.post(
                "/executions/run",
                json={"pipeline_definition": valid_pipeline_definition},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["workflow_name"] == "ephemeral-test-pipeline"


class TestEphemeralExecutionWithParams:
    """Tests for ephemeral execution with input parameters."""

    def test_params_passed_to_execution(
        self, client, valid_pipeline_definition, mock_execution_result
    ):
        """Test that params are passed to execution."""
        params = {"model_id": "test-model", "batch_size": 32}
        mock_execution_result["params"] = params

        with patch("budpipeline.pipeline.execution_routes.pipeline_service") as mock_service:
            mock_service.validate_dag = MagicMock(return_value=(True, [], []))
            mock_service._execute_pipeline_impl = AsyncMock(return_value=mock_execution_result)

            response = client.post(
                "/executions/run",
                json={
                    "pipeline_definition": valid_pipeline_definition,
                    "params": params,
                },
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["params"] == params

    def test_empty_params_default(self, client, valid_pipeline_definition, mock_execution_result):
        """Test that empty params works (defaults to empty dict)."""
        mock_execution_result["params"] = {}

        with patch("budpipeline.pipeline.execution_routes.pipeline_service") as mock_service:
            mock_service.validate_dag = MagicMock(return_value=(True, [], []))
            mock_service._execute_pipeline_impl = AsyncMock(return_value=mock_execution_result)

            response = client.post(
                "/executions/run",
                json={"pipeline_definition": valid_pipeline_definition},
                # No params provided
            )

        assert response.status_code == status.HTTP_201_CREATED


class TestEphemeralExecutionUseCases:
    """Tests for ephemeral execution use cases."""

    def test_one_off_execution_use_case(
        self, client, valid_pipeline_definition, mock_execution_result
    ):
        """Test one-off execution use case - run once without saving.

        Use case: User wants to test a pipeline definition before saving it.
        """
        with patch("budpipeline.pipeline.execution_routes.pipeline_service") as mock_service:
            mock_service.validate_dag = MagicMock(return_value=(True, [], []))
            mock_service._execute_pipeline_impl = AsyncMock(return_value=mock_execution_result)

            response = client.post(
                "/executions/run",
                json={
                    "pipeline_definition": valid_pipeline_definition,
                    "initiator": "pipeline-tester",
                },
            )

        assert response.status_code == status.HTTP_201_CREATED

    def test_temporary_workflow_use_case(
        self, client, valid_pipeline_definition, mock_execution_result
    ):
        """Test temporary/ad-hoc workflow use case.

        Use case: User needs to run a one-time data transformation that
        won't be repeated, so no need to save the pipeline definition.
        """
        ad_hoc_pipeline = {
            "name": "one-time-data-transform",
            "version": "1.0",
            "steps": [
                {"id": "transform", "action": "transform", "params": {"mode": "cleanup"}},
            ],
        }

        with patch("budpipeline.pipeline.execution_routes.pipeline_service") as mock_service:
            mock_service.validate_dag = MagicMock(return_value=(True, [], []))
            mock_service._execute_pipeline_impl = AsyncMock(return_value=mock_execution_result)

            response = client.post(
                "/executions/run",
                json={
                    "pipeline_definition": ad_hoc_pipeline,
                    "params": {"source_table": "old_data"},
                },
            )

        assert response.status_code == status.HTTP_201_CREATED

    def test_testing_pipeline_before_save_use_case(
        self, client, valid_pipeline_definition, mock_execution_result
    ):
        """Test: validate and run pipeline before committing to save it.

        Use case: Pipeline builder UI runs ephemeral execution to test
        before user clicks "Save Pipeline".
        """
        with patch("budpipeline.pipeline.execution_routes.pipeline_service") as mock_service:
            mock_service.validate_dag = MagicMock(return_value=(True, [], []))
            mock_service._execute_pipeline_impl = AsyncMock(return_value=mock_execution_result)

            response = client.post(
                "/executions/run",
                json={
                    "pipeline_definition": valid_pipeline_definition,
                    "callback_topics": ["builder-ui-updates"],  # UI listens for updates
                },
            )

        assert response.status_code == status.HTTP_201_CREATED
