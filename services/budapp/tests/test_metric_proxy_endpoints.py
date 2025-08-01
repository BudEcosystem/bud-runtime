"""Unit tests for metric proxy endpoints in budapp."""

import pytest
from datetime import datetime, timedelta
import uuid
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException
from sqlalchemy.orm import Session
import aiohttp

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
    user = Mock()
    user.id = str(uuid.uuid4())
    user.username = "testuser"
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_project():
    """Mock project for testing."""
    project = Mock()
    project_id = str(uuid.uuid4())
    project.id = project_id
    project.name = "Test Project"
    project.organization_id = str(uuid.uuid4())
    return project


@pytest.fixture
def mock_endpoint():
    """Mock endpoint for testing."""
    endpoint = Mock()
    endpoint.id = str(uuid.uuid4())
    endpoint.name = "Test Endpoint"
    endpoint.project_id = str(uuid.uuid4())
    return endpoint


@pytest.fixture
def mock_model():
    """Mock model for testing."""
    model = Mock()
    model.id = str(uuid.uuid4())
    model.name = "gpt-4"
    model.display_name = "GPT-4"
    model.provider = "openai"
    return model


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = Mock(spec=Session)
    return session


@pytest.fixture
def sample_inference_response(mock_project, mock_endpoint, mock_model):
    """Sample inference response from budmetrics."""
    return {
        "items": [{
            "inference_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "project_id": str(mock_project.id),  # Use mock project ID
            "endpoint_id": str(mock_endpoint.id),  # Use mock endpoint ID
            "model_id": str(mock_model.id),  # Use mock model ID
            "model_name": "gpt-4",
            "model_provider": "openai",
            "is_success": True,
            "input_tokens": 150,
            "output_tokens": 250,
            "total_tokens": 400,  # Required field
            "response_time_ms": 1234,
            "cost": 0.0045,
            "cached": False,
            "prompt_preview": "Hello",
            "response_preview": "Hi there!"
        }],
        "total_count": 1,
        "offset": 0,
        "limit": 10,
        "has_more": False  # Required field
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
        mock_db_session.execute = Mock()
        mock_db_session.scalars = Mock()
        mock_db_session.execute.side_effect = [
            Mock(scalar_one_or_none=Mock(return_value=mock_project)),  # Project query
            Mock(scalars=Mock(return_value=Mock(all=Mock(return_value=[mock_project])))),  # Projects batch query
            Mock(scalars=Mock(return_value=Mock(all=Mock(return_value=[mock_endpoint])))),  # Endpoints batch query
            Mock(scalars=Mock(return_value=Mock(all=Mock(return_value=[mock_model])))),  # Models batch query
        ]
        mock_db_session.scalars.side_effect = [
            Mock(all=Mock(return_value=[mock_user.id])),  # Project membership check
        ]

        # Create a mock for aiohttp.ClientSession that properly implements async context manager
        from unittest.mock import create_autospec

        # Create mock response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=sample_inference_response)

        # Create mock session with post method returning a context manager
        mock_session = Mock()
        mock_post_context = Mock()
        mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = Mock(return_value=mock_post_context)

        # Create mock session context manager
        mock_session_context = Mock()
        mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session_context):

            service = BudMetricService(mock_db_session)
            request = InferenceListRequest(
                project_id=uuid.UUID(mock_project.id),
                from_date=datetime.utcnow() - timedelta(days=7),
                limit=10,
                offset=0
            )

            response = await service.list_inferences(request, mock_user)

            assert response is not None, "Response should not be None"
            assert response.total_count == 1
            assert len(response.items) == 1
            assert response.items[0].project_name == "Test Project"
            assert response.items[0].endpoint_name == "Test Endpoint"
            assert response.items[0].model_display_name == "gpt-4"

    @pytest.mark.asyncio
    async def test_list_inferences_access_denied(self, mock_db_session, mock_user):
        """Test access denied for unauthorized project."""
        from budapp.metric_ops.services import BudMetricService

        # Mock project not found
        mock_db_session.execute = Mock()
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None

        service = BudMetricService(mock_db_session)
        request = InferenceListRequest(
            project_id=uuid.uuid4(),
            from_date=datetime.utcnow() - timedelta(days=7)
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.list_inferences(request, mock_user)

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
        mock_db_session.execute = Mock()
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_project

        # Mock budmetrics client
        with patch('budapp.metric_ops.services.aiohttp.ClientSession') as mock_session:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=sample_detail_response)
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            service = BudMetricService(mock_db_session)
            response = await service.get_inference_details(inference_id, mock_user)

            assert response.inference_id == inference_id
            assert response.model_name == "gpt-4"
            assert len(response.messages) == 2
            assert response.messages[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_get_inference_details_not_found(self, mock_db_session, mock_user):
        """Test inference detail not found."""
        from budapp.metric_ops.services import BudMetricService

        # Mock budmetrics client returning 404
        with patch('budapp.metric_ops.services.aiohttp.ClientSession') as mock_session:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.text = "Inference not found"
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            service = BudMetricService(mock_db_session)

            with pytest.raises(HTTPException) as exc_info:
                await service.get_inference_details(str(uuid.uuid4()), mock_user)

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
            with patch('budapp.metric_ops.services.aiohttp.ClientSession') as mock_session:
                mock_response = Mock()
                mock_response.status = 200
                mock_response.json = AsyncMock(return_value=sample_feedback_response)
                mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

                service = BudMetricService(mock_db_session)
                response = await service.get_inference_feedback(inference_id, mock_user)

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
        mock_db_session.execute = Mock()
        mock_db_session.execute.side_effect = [
            Mock(scalar_one_or_none=Mock(return_value=mock_project)),  # Project query
            Mock(scalars=Mock(return_value=Mock(all=Mock(return_value=[mock_project])))),  # Projects batch
            Mock(scalars=Mock(return_value=Mock(all=Mock(return_value=[])))),  # No endpoints found
            Mock(scalars=Mock(return_value=Mock(all=Mock(return_value=[])))),  # No models found
        ]

        # Mock budmetrics client
        with patch('budapp.metric_ops.services.aiohttp.ClientSession') as mock_session:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=sample_response)
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response

            service = BudMetricService(mock_db_session)
            request = InferenceListRequest(
                project_id=uuid.UUID(mock_project.id),
                from_date=datetime.utcnow() - timedelta(days=7)
            )
            response = await service.list_inferences(request, mock_user)

            # Should still return data, but without enriched names
            assert response.total_count == 1
            assert response.items[0].project_name == "Test Project"
            assert response.items[0].endpoint_name is None
            assert response.items[0].model_display_name is None
