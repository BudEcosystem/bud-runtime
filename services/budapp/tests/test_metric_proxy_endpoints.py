"""Unit tests for metric proxy endpoints in budapp."""

import pytest
from datetime import datetime, timedelta
import uuid
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from budapp.metric_ops.schemas import (
    InferenceListRequest,
    InferenceListResponse,
    InferenceDetailResponse,
    InferenceFeedbackResponse
)
from budapp.user_ops.models import User
from budapp.project_ops.models import Project
from budapp.endpoint_ops.models import Endpoint
from budapp.model_ops.models import Model


@pytest.fixture
def mock_user():
    """Mock user for testing."""
    user = Mock(spec=User)
    user.id = str(uuid.uuid4())
    user.username = "testuser"
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_project():
    """Mock project for testing."""
    project = Mock(spec=Project)
    project.id = str(uuid.uuid4())
    project.name = "Test Project"
    project.organization_id = str(uuid.uuid4())
    return project


@pytest.fixture
def mock_endpoint():
    """Mock endpoint for testing."""
    endpoint = Mock(spec=Endpoint)
    endpoint.id = str(uuid.uuid4())
    endpoint.name = "Test Endpoint"
    endpoint.project_id = str(uuid.uuid4())
    return endpoint


@pytest.fixture
def mock_model():
    """Mock model for testing."""
    model = Mock(spec=Model)
    model.id = str(uuid.uuid4())
    model.name = "gpt-4"
    model.display_name = "GPT-4"
    model.provider = "openai"
    return model


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = Mock(spec=AsyncSession)
    return session


@pytest.fixture
def sample_inference_response():
    """Sample inference response from budmetrics."""
    return {
        "items": [{
            "inference_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "project_id": str(uuid.uuid4()),
            "endpoint_id": str(uuid.uuid4()),
            "model_id": str(uuid.uuid4()),
            "model_name": "gpt-4",
            "model_provider": "openai",
            "is_success": True,
            "input_tokens": 150,
            "output_tokens": 250,
            "response_time_ms": 1234,
            "cost": 0.0045,
            "cached": False,
            "prompt_preview": "Hello",
            "response_preview": "Hi there!"
        }],
        "total_count": 1,
        "offset": 0,
        "limit": 10
    }


class TestMetricProxyEndpoints:
    """Test class for metric proxy endpoints."""

    @pytest.mark.asyncio
    async def test_list_inferences_success(
        self, mock_db_session, mock_user, mock_project, mock_endpoint, mock_model, sample_inference_response
    ):
        """Test successful inference list retrieval with enrichment."""
        from budapp.metric_ops.services import BudMetricService

        # Mock database queries
        mock_db_session.execute = AsyncMock()
        mock_db_session.execute.side_effect = [
            Mock(scalar_one_or_none=Mock(return_value=mock_project)),  # Project query
            Mock(scalars=Mock(return_value=Mock(all=Mock(return_value=[mock_project])))),  # Projects batch query
            Mock(scalars=Mock(return_value=Mock(all=Mock(return_value=[mock_endpoint])))),  # Endpoints batch query
            Mock(scalars=Mock(return_value=Mock(all=Mock(return_value=[mock_model])))),  # Models batch query
        ]

        # Mock budmetrics client
        with patch('budapp.metric_ops.services.httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_inference_response
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            service = BudMetricService()
            request = InferenceListRequest(
                project_id=uuid.UUID(mock_project.id),
                from_date=datetime.utcnow() - timedelta(days=7),
                limit=10,
                offset=0
            )

            response = await service.list_inferences(request, mock_db_session, mock_user)

            assert response.total_count == 1
            assert len(response.items) == 1
            assert response.items[0].project_name == "Test Project"
            assert response.items[0].endpoint_name == "Test Endpoint"
            assert response.items[0].model_display_name == "GPT-4"

    @pytest.mark.asyncio
    async def test_list_inferences_access_denied(self, mock_db_session, mock_user):
        """Test access denied for unauthorized project."""
        from budapp.metric_ops.services import BudMetricService

        # Mock project not found
        mock_db_session.execute = AsyncMock()
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None

        service = BudMetricService()
        request = InferenceListRequest(
            project_id=uuid.uuid4(),
            from_date=datetime.utcnow() - timedelta(days=7)
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.list_inferences(request, mock_db_session, mock_user)

        assert exc_info.value.status_code == 404
        assert "Project not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_inference_details_success(self, mock_db_session, mock_user, mock_project):
        """Test successful inference detail retrieval."""
        from budapp.metric_ops.services import BudMetricService

        inference_id = str(uuid.uuid4())
        sample_detail_response = {
            "inference_id": inference_id,
            "timestamp": datetime.utcnow().isoformat(),
            "project_id": mock_project.id,
            "endpoint_id": str(uuid.uuid4()),
            "model_id": str(uuid.uuid4()),
            "model_name": "gpt-4",
            "model_provider": "openai",
            "is_success": True,
            "input_tokens": 150,
            "output_tokens": 250,
            "response_time_ms": 1234,
            "cost": 0.0045,
            "cached": False,
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"}
            ],
            "system_prompt": "You are helpful",
            "output": "Hi there!",
            "finish_reason": "stop"
        }

        # Mock database queries
        mock_db_session.execute = AsyncMock()
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_project

        # Mock budmetrics client
        with patch('budapp.metric_ops.services.httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_detail_response
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            service = BudMetricService()
            response = await service.get_inference_details(inference_id, mock_db_session, mock_user)

            assert response.inference_id == inference_id
            assert response.model_name == "gpt-4"
            assert len(response.messages) == 2
            assert response.messages[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_get_inference_details_not_found(self, mock_db_session, mock_user):
        """Test inference detail not found."""
        from budapp.metric_ops.services import BudMetricService

        # Mock budmetrics client returning 404
        with patch('budapp.metric_ops.services.httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.text = "Inference not found"
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            service = BudMetricService()

            with pytest.raises(HTTPException) as exc_info:
                await service.get_inference_details(str(uuid.uuid4()), mock_db_session, mock_user)

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_inference_feedback_success(self, mock_db_session, mock_user, mock_project):
        """Test successful feedback retrieval."""
        from budapp.metric_ops.services import BudMetricService

        inference_id = str(uuid.uuid4())
        sample_feedback_response = [
            {
                "feedback_id": str(uuid.uuid4()),
                "inference_id": inference_id,
                "created_at": datetime.utcnow().isoformat(),
                "feedback_type": "boolean",
                "metric_name": "helpful",
                "value": 1
            },
            {
                "feedback_id": str(uuid.uuid4()),
                "inference_id": inference_id,
                "created_at": datetime.utcnow().isoformat(),
                "feedback_type": "float",
                "metric_name": "quality_rating",
                "value": 4.5
            }
        ]

        # Mock getting inference details first (for access check)
        with patch.object(BudMetricService, 'get_inference_details') as mock_get_details:
            mock_get_details.return_value = Mock(project_id=mock_project.id)

            # Mock budmetrics client
            with patch('budapp.metric_ops.services.httpx.AsyncClient') as mock_client:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = sample_feedback_response
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

                service = BudMetricService()
                response = await service.get_inference_feedback(inference_id, mock_db_session, mock_user)

                assert len(response) == 2
                assert response[0].feedback_type == "boolean"
                assert response[0].metric_name == "helpful"
                assert response[1].feedback_type == "float"
                assert response[1].value == 4.5

    @pytest.mark.asyncio
    async def test_enrichment_with_missing_entities(self, mock_db_session, mock_user, mock_project):
        """Test enrichment handles missing entities gracefully."""
        from budapp.metric_ops.services import BudMetricService

        sample_response = {
            "items": [{
                "inference_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat(),
                "project_id": mock_project.id,
                "endpoint_id": "non-existent-endpoint",
                "model_id": "non-existent-model",
                "model_name": "unknown-model",
                "model_provider": "unknown",
                "is_success": True,
                "input_tokens": 100,
                "output_tokens": 200,
                "response_time_ms": 500,
                "cost": 0.003,
                "cached": False,
                "prompt_preview": "Test",
                "response_preview": "Response"
            }],
            "total_count": 1,
            "offset": 0,
            "limit": 10
        }

        # Mock database queries
        mock_db_session.execute = AsyncMock()
        mock_db_session.execute.side_effect = [
            Mock(scalar_one_or_none=Mock(return_value=mock_project)),  # Project query
            Mock(scalars=Mock(return_value=Mock(all=Mock(return_value=[mock_project])))),  # Projects batch
            Mock(scalars=Mock(return_value=Mock(all=Mock(return_value=[])))),  # No endpoints found
            Mock(scalars=Mock(return_value=Mock(all=Mock(return_value=[])))),  # No models found
        ]

        # Mock budmetrics client
        with patch('budapp.metric_ops.services.httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_response
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            service = BudMetricService()
            request = InferenceListRequest(
                project_id=uuid.UUID(mock_project.id),
                from_date=datetime.utcnow() - timedelta(days=7)
            )

            response = await service.list_inferences(request, mock_db_session, mock_user)

            # Should still return data, but without enriched names
            assert response.total_count == 1
            assert response.items[0].project_name == "Test Project"
            assert response.items[0].endpoint_name is None
            assert response.items[0].model_display_name is None
