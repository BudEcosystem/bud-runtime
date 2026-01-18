"""Unit tests for user isolation in pipeline management.

Tests for user isolation feature (002-pipeline-event-persistence):
- User can only see their own pipelines
- User can access system-owned pipelines with include_system=true
- User cannot access other users' pipelines
- User context extraction from X-User-ID header
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from budpipeline.commons.dependencies import UserContext, get_user_context
from budpipeline.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def user_a_id():
    """User A's UUID."""
    return uuid4()


@pytest.fixture
def user_b_id():
    """User B's UUID."""
    return uuid4()


@pytest.fixture
def sample_dag():
    """Sample pipeline DAG definition."""
    return {
        "name": "test-pipeline",
        "version": "1.0",
        "steps": [
            {"id": "step1", "action": "log", "params": {"message": "test"}},
        ],
    }


@pytest.fixture
def mock_pipeline_user_a(user_a_id):
    """Create a mock pipeline owned by user A."""
    return {
        "id": str(uuid4()),
        "name": "user-a-pipeline",
        "version": "1.0",
        "status": "active",
        "created_at": "2024-01-01T00:00:00Z",
        "step_count": 1,
        "user_id": str(user_a_id),
        "system_owned": False,
    }


@pytest.fixture
def mock_pipeline_user_b(user_b_id):
    """Create a mock pipeline owned by user B."""
    return {
        "id": str(uuid4()),
        "name": "user-b-pipeline",
        "version": "1.0",
        "status": "active",
        "created_at": "2024-01-01T00:00:00Z",
        "step_count": 1,
        "user_id": str(user_b_id),
        "system_owned": False,
    }


@pytest.fixture
def mock_system_pipeline():
    """Create a mock system-owned pipeline."""
    return {
        "id": str(uuid4()),
        "name": "system-pipeline",
        "version": "1.0",
        "status": "active",
        "created_at": "2024-01-01T00:00:00Z",
        "step_count": 1,
        "user_id": None,
        "system_owned": True,
    }


class TestUserContextExtraction:
    """Tests for UserContext extraction from headers."""

    def test_user_context_with_valid_uuid(self):
        """Test that valid UUID in X-User-ID header creates user context."""
        import asyncio

        user_id = uuid4()
        context = asyncio.get_event_loop().run_until_complete(get_user_context(str(user_id)))

        assert context.user_id == user_id
        assert context.is_system is False

    def test_user_context_with_no_header(self):
        """Test that missing header creates system context."""
        import asyncio

        context = asyncio.get_event_loop().run_until_complete(get_user_context(None))

        assert context.user_id is None
        assert context.is_system is True

    def test_user_context_with_invalid_uuid(self):
        """Test that invalid UUID creates system context."""
        import asyncio

        context = asyncio.get_event_loop().run_until_complete(get_user_context("not-a-valid-uuid"))

        assert context.user_id is None
        assert context.is_system is True

    def test_user_context_user_id_str_property(self):
        """Test user_id_str property returns string."""
        user_id = uuid4()
        context = UserContext(user_id=user_id)

        assert context.user_id_str == str(user_id)

    def test_user_context_user_id_str_none(self):
        """Test user_id_str property returns None when no user."""
        context = UserContext(user_id=None, is_system=True)

        assert context.user_id_str is None


class TestListPipelinesIsolation:
    """Tests for user isolation in list pipelines endpoint."""

    def test_user_sees_only_own_pipelines(
        self, client, user_a_id, mock_pipeline_user_a, mock_pipeline_user_b
    ):
        """Test that user A only sees their own pipelines."""
        with patch("budpipeline.pipeline.routes.pipeline_service") as mock_service:
            # Only return user A's pipeline
            mock_service.list_pipelines_async = AsyncMock(return_value=[mock_pipeline_user_a])

            response = client.get(
                "/pipelines",
                headers={"X-User-ID": str(user_a_id)},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "user-a-pipeline"
        assert data[0]["user_id"] == str(user_a_id)

    def test_user_cannot_see_other_users_pipelines(self, client, user_b_id, mock_pipeline_user_a):
        """Test that user B cannot see user A's pipelines."""
        with patch("budpipeline.pipeline.routes.pipeline_service") as mock_service:
            # Return empty list for user B
            mock_service.list_pipelines_async = AsyncMock(return_value=[])

            response = client.get(
                "/pipelines",
                headers={"X-User-ID": str(user_b_id)},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 0

    def test_user_sees_system_pipelines_with_flag(
        self, client, user_a_id, mock_pipeline_user_a, mock_system_pipeline
    ):
        """Test that user can see system pipelines with include_system=true."""
        with patch("budpipeline.pipeline.routes.pipeline_service") as mock_service:
            # Return both user's and system pipelines
            mock_service.list_pipelines_async = AsyncMock(
                return_value=[mock_pipeline_user_a, mock_system_pipeline]
            )

            response = client.get(
                "/pipelines?include_system=true",
                headers={"X-User-ID": str(user_a_id)},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

        # Verify service was called with correct params
        mock_service.list_pipelines_async.assert_called_once()
        call_kwargs = mock_service.list_pipelines_async.call_args.kwargs
        assert call_kwargs["include_system"] is True

    def test_user_does_not_see_system_pipelines_by_default(
        self, client, user_a_id, mock_pipeline_user_a
    ):
        """Test that user does NOT see system pipelines by default."""
        with patch("budpipeline.pipeline.routes.pipeline_service") as mock_service:
            # Only return user's pipelines
            mock_service.list_pipelines_async = AsyncMock(return_value=[mock_pipeline_user_a])

            response = client.get(
                "/pipelines",
                headers={"X-User-ID": str(user_a_id)},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1

        # Verify include_system was False
        call_kwargs = mock_service.list_pipelines_async.call_args.kwargs
        assert call_kwargs["include_system"] is False

    def test_no_user_context_returns_all_pipelines(
        self, client, mock_pipeline_user_a, mock_pipeline_user_b, mock_system_pipeline
    ):
        """Test that requests without X-User-ID header return all pipelines.

        This maintains backward compatibility for service-to-service calls.
        """
        with patch("budpipeline.pipeline.routes.pipeline_service") as mock_service:
            mock_service.list_pipelines_async = AsyncMock(
                return_value=[
                    mock_pipeline_user_a,
                    mock_pipeline_user_b,
                    mock_system_pipeline,
                ]
            )

            response = client.get("/pipelines")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3


class TestGetPipelineIsolation:
    """Tests for user isolation in get pipeline endpoint."""

    def test_user_can_get_own_pipeline(self, client, user_a_id, mock_pipeline_user_a):
        """Test that user A can get their own pipeline."""
        pipeline_id = mock_pipeline_user_a["id"]

        with patch("budpipeline.pipeline.routes.pipeline_service") as mock_service:
            mock_service.get_pipeline_async_for_user = AsyncMock(
                return_value={**mock_pipeline_user_a, "dag": {"steps": []}}
            )

            response = client.get(
                f"/pipelines/{pipeline_id}",
                headers={"X-User-ID": str(user_a_id)},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == pipeline_id

    def test_user_cannot_get_other_users_pipeline(self, client, user_b_id, mock_pipeline_user_a):
        """Test that user B cannot get user A's pipeline."""
        from budpipeline.commons.exceptions import WorkflowNotFoundError

        pipeline_id = mock_pipeline_user_a["id"]

        with patch("budpipeline.pipeline.routes.pipeline_service") as mock_service:
            mock_service.get_pipeline_async_for_user = AsyncMock(
                side_effect=WorkflowNotFoundError(f"Pipeline not found: {pipeline_id}")
            )

            response = client.get(
                f"/pipelines/{pipeline_id}",
                headers={"X-User-ID": str(user_b_id)},
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_user_can_get_system_pipeline(self, client, user_a_id, mock_system_pipeline):
        """Test that any user can get system-owned pipelines."""
        pipeline_id = mock_system_pipeline["id"]

        with patch("budpipeline.pipeline.routes.pipeline_service") as mock_service:
            mock_service.get_pipeline_async_for_user = AsyncMock(
                return_value={**mock_system_pipeline, "dag": {"steps": []}}
            )

            response = client.get(
                f"/pipelines/{pipeline_id}",
                headers={"X-User-ID": str(user_a_id)},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["system_owned"] is True


class TestCreatePipelineIsolation:
    """Tests for user isolation in create pipeline endpoint."""

    def test_create_pipeline_assigns_user_id_from_header(self, client, user_a_id, sample_dag):
        """Test that created pipeline is assigned to user from header."""
        with patch("budpipeline.pipeline.routes.pipeline_service") as mock_service:
            mock_service.create_pipeline_async = AsyncMock(
                return_value={
                    "id": str(uuid4()),
                    "name": sample_dag["name"],
                    "version": sample_dag["version"],
                    "status": "active",
                    "created_at": "2024-01-01T00:00:00Z",
                    "step_count": 1,
                    "user_id": str(user_a_id),
                    "system_owned": False,
                }
            )

            response = client.post(
                "/pipelines",
                headers={"X-User-ID": str(user_a_id)},
                json={"dag": sample_dag},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["user_id"] == str(user_a_id)

        # Verify service was called with user_id
        call_kwargs = mock_service.create_pipeline_async.call_args.kwargs
        assert call_kwargs["user_id"] == user_a_id

    def test_create_pipeline_user_id_in_body_takes_precedence(
        self, client, user_a_id, user_b_id, sample_dag
    ):
        """Test that user_id in request body takes precedence over header."""
        with patch("budpipeline.pipeline.routes.pipeline_service") as mock_service:
            mock_service.create_pipeline_async = AsyncMock(
                return_value={
                    "id": str(uuid4()),
                    "name": sample_dag["name"],
                    "version": sample_dag["version"],
                    "status": "active",
                    "created_at": "2024-01-01T00:00:00Z",
                    "step_count": 1,
                    "user_id": str(user_b_id),
                    "system_owned": False,
                }
            )

            response = client.post(
                "/pipelines",
                headers={"X-User-ID": str(user_a_id)},  # Header says user A
                json={"dag": sample_dag, "user_id": str(user_b_id)},  # Body says user B
            )

        assert response.status_code == status.HTTP_201_CREATED

        # Verify service was called with user B's ID (from body)
        call_kwargs = mock_service.create_pipeline_async.call_args.kwargs
        assert call_kwargs["user_id"] == user_b_id

    def test_create_system_pipeline(self, client, sample_dag):
        """Test creating a system-owned pipeline."""
        with patch("budpipeline.pipeline.routes.pipeline_service") as mock_service:
            mock_service.create_pipeline_async = AsyncMock(
                return_value={
                    "id": str(uuid4()),
                    "name": sample_dag["name"],
                    "version": sample_dag["version"],
                    "status": "active",
                    "created_at": "2024-01-01T00:00:00Z",
                    "step_count": 1,
                    "user_id": None,
                    "system_owned": True,
                }
            )

            response = client.post(
                "/pipelines",
                json={"dag": sample_dag, "system_owned": True},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["system_owned"] is True
        assert data["user_id"] is None


class TestDeletePipelineIsolation:
    """Tests for user isolation in delete pipeline endpoint."""

    def test_user_can_delete_own_pipeline(self, client, user_a_id, mock_pipeline_user_a):
        """Test that user A can delete their own pipeline."""
        pipeline_id = mock_pipeline_user_a["id"]

        with patch("budpipeline.pipeline.routes.pipeline_service") as mock_service:
            mock_service.get_pipeline_async_for_user = AsyncMock(
                return_value={**mock_pipeline_user_a, "dag": {"steps": []}}
            )
            mock_service.delete_pipeline_async = AsyncMock(return_value=True)

            response = client.delete(
                f"/pipelines/{pipeline_id}",
                headers={"X-User-ID": str(user_a_id)},
            )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_user_cannot_delete_other_users_pipeline(self, client, user_b_id, mock_pipeline_user_a):
        """Test that user B cannot delete user A's pipeline."""
        from budpipeline.commons.exceptions import WorkflowNotFoundError

        pipeline_id = mock_pipeline_user_a["id"]

        with patch("budpipeline.pipeline.routes.pipeline_service") as mock_service:
            mock_service.get_pipeline_async_for_user = AsyncMock(
                side_effect=WorkflowNotFoundError(f"Pipeline not found: {pipeline_id}")
            )

            response = client.delete(
                f"/pipelines/{pipeline_id}",
                headers={"X-User-ID": str(user_b_id)},
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdatePipelineIsolation:
    """Tests for user isolation in update pipeline endpoint."""

    def test_user_can_update_own_pipeline(
        self, client, user_a_id, mock_pipeline_user_a, sample_dag
    ):
        """Test that user A can update their own pipeline."""
        pipeline_id = mock_pipeline_user_a["id"]

        with patch("budpipeline.pipeline.routes.pipeline_service") as mock_service:
            mock_service.get_pipeline_async_for_user = AsyncMock(
                return_value={**mock_pipeline_user_a, "dag": {"steps": []}}
            )
            mock_service.update_pipeline_async = AsyncMock(
                return_value={
                    **mock_pipeline_user_a,
                    "name": "updated-name",
                }
            )

            response = client.put(
                f"/pipelines/{pipeline_id}",
                headers={"X-User-ID": str(user_a_id)},
                json={"dag": sample_dag, "name": "updated-name"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "updated-name"

    def test_user_cannot_update_other_users_pipeline(
        self, client, user_b_id, mock_pipeline_user_a, sample_dag
    ):
        """Test that user B cannot update user A's pipeline."""
        from budpipeline.commons.exceptions import WorkflowNotFoundError

        pipeline_id = mock_pipeline_user_a["id"]

        with patch("budpipeline.pipeline.routes.pipeline_service") as mock_service:
            mock_service.get_pipeline_async_for_user = AsyncMock(
                side_effect=WorkflowNotFoundError(f"Pipeline not found: {pipeline_id}")
            )

            response = client.put(
                f"/pipelines/{pipeline_id}",
                headers={"X-User-ID": str(user_b_id)},
                json={"dag": sample_dag},
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
