"""Unit tests for inference-related endpoints in budmetrics."""

import pytest
from datetime import datetime, timedelta
import uuid
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from budmetrics.observability.schemas import (
    InferenceListRequest,
    InferenceListResponse,
    InferenceDetailResponse,
    InferenceFeedbackResponse
)


@pytest.fixture
def mock_clickhouse_client():
    """Mock ClickHouse client."""
    with patch('budmetrics.observability.services.get_clickhouse_client') as mock:
        client = Mock()
        mock.return_value = client
        yield client


@pytest.fixture
def sample_inference_data():
    """Sample inference data for testing."""
    return {
        "inference_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow(),
        "project_id": str(uuid.uuid4()),
        "endpoint_id": str(uuid.uuid4()),
        "model_id": str(uuid.uuid4()),
        "model_name": "gpt-4",
        "model_provider": "openai",
        "is_success": True,
        "input_tokens": 150,
        "output_tokens": 250,
        "response_time_ms": 1234,
        "ttft_ms": 123,
        "cost": 0.0045,
        "cached": False,
        "ip_address": "192.168.1.100"
    }


@pytest.fixture
def sample_chat_data():
    """Sample chat inference data."""
    return {
        "system_prompt": "You are a helpful assistant",
        "messages": json.dumps([
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]),
        "output": "Hi there!",
        "finish_reason": "stop"
    }


@pytest.fixture
def sample_feedback_data():
    """Sample feedback data."""
    return [
        {
            "feedback_id": str(uuid.uuid4()),
            "feedback_type": "boolean",
            "metric_name": "helpful",
            "value": 1,
            "created_at": datetime.utcnow()
        },
        {
            "feedback_id": str(uuid.uuid4()),
            "feedback_type": "float",
            "metric_name": "quality_rating",
            "value": 4.5,
            "created_at": datetime.utcnow()
        }
    ]


class TestInferenceEndpoints:
    """Test class for inference endpoints."""

    @pytest.mark.asyncio
    async def test_list_inferences_success(self, mock_clickhouse_client, sample_inference_data):
        """Test successful inference list retrieval."""
        # Mock ClickHouse responses
        mock_clickhouse_client.execute.side_effect = [
            [(1,)],  # Count query
            [(
                sample_inference_data["inference_id"],
                sample_inference_data["timestamp"],
                sample_inference_data["project_id"],
                sample_inference_data["endpoint_id"],
                sample_inference_data["model_id"],
                sample_inference_data["model_name"],
                sample_inference_data["model_provider"],
                sample_inference_data["is_success"],
                sample_inference_data["input_tokens"],
                sample_inference_data["output_tokens"],
                sample_inference_data["response_time_ms"],
                sample_inference_data["ttft_ms"],
                sample_inference_data["cost"],
                sample_inference_data["cached"],
                "Hello",  # prompt_preview
                "Hi there!",  # response_preview
                1,  # feedback_count
                4.5  # average_rating
            )]  # Data query
        ]

        from budmetrics.observability.services import ObservabilityService
        service = ObservabilityService()

        request = InferenceListRequest(
            project_id=uuid.UUID(sample_inference_data["project_id"]),
            from_date=datetime.utcnow() - timedelta(days=7),
            limit=10,
            offset=0
        )

        response = await service.list_inferences(request)

        assert response.total_count == 1
        assert len(response.items) == 1
        assert response.items[0].inference_id == sample_inference_data["inference_id"]
        assert response.items[0].model_name == "gpt-4"
        assert response.items[0].is_success is True

    @pytest.mark.asyncio
    async def test_list_inferences_with_filters(self, mock_clickhouse_client):
        """Test inference list with various filters."""
        mock_clickhouse_client.execute.side_effect = [
            [(0,)],  # Count query
            []  # Data query
        ]

        from budmetrics.observability.services import ObservabilityService
        service = ObservabilityService()

        request = InferenceListRequest(
            project_id=uuid.uuid4(),
            endpoint_id=uuid.uuid4(),
            model_id=uuid.uuid4(),
            from_date=datetime.utcnow() - timedelta(days=1),
            to_date=datetime.utcnow(),
            is_success=True,
            min_tokens=100,
            max_tokens=500,
            max_latency_ms=1000,
            sort_by="latency",
            sort_order="desc"
        )

        response = await service.list_inferences(request)

        assert response.total_count == 0
        assert len(response.items) == 0

        # Verify the query was built with all filters
        calls = mock_clickhouse_client.execute.call_args_list
        count_query = calls[0][0][0]
        assert "endpoint_id =" in count_query
        assert "model_id =" in count_query
        assert "is_success = 1" in count_query
        assert "input_tokens + output_tokens >= 100" in count_query
        assert "input_tokens + output_tokens <= 500" in count_query
        assert "response_time_ms <= 1000" in count_query

    @pytest.mark.asyncio
    async def test_get_inference_details_success(
        self, mock_clickhouse_client, sample_inference_data, sample_chat_data
    ):
        """Test successful inference detail retrieval."""
        inference_id = sample_inference_data["inference_id"]

        # Mock responses for different queries
        mock_clickhouse_client.execute.side_effect = [
            # ModelInference query
            [(
                inference_id,
                sample_inference_data["timestamp"],
                sample_inference_data["project_id"],
                sample_inference_data["endpoint_id"],
                sample_inference_data["model_id"],
                sample_inference_data["model_name"],
                sample_inference_data["model_provider"],
                sample_inference_data["is_success"],
                sample_inference_data["input_tokens"],
                sample_inference_data["output_tokens"],
                sample_inference_data["response_time_ms"],
                sample_inference_data["ttft_ms"],
                None,  # processing_time_ms
                sample_inference_data["cost"],
                sample_inference_data["cached"],
                sample_inference_data["ip_address"],
                1,  # feedback_count
                4.5  # average_rating
            )],
            # ChatInference query
            [(
                sample_chat_data["system_prompt"],
                sample_chat_data["messages"],
                sample_chat_data["output"],
                sample_chat_data["finish_reason"]
            )],
            # ModelInferenceDetails query
            [(
                '{"model": "gpt-4", "messages": []}',  # raw_request
                '{"choices": [{"message": {"content": "Hi"}}]}',  # raw_response
                1000  # processing_time_ms
            )]
        ]

        from budmetrics.observability.services import ObservabilityService
        service = ObservabilityService()

        response = await service.get_inference_details(inference_id)

        assert response.inference_id == inference_id
        assert response.model_name == "gpt-4"
        assert response.is_success is True
        assert response.system_prompt == sample_chat_data["system_prompt"]
        assert len(response.messages) == 2
        assert response.messages[0]["role"] == "user"
        assert response.raw_request is not None
        assert response.raw_response is not None

    @pytest.mark.asyncio
    async def test_get_inference_details_not_found(self, mock_clickhouse_client):
        """Test inference detail retrieval when not found."""
        mock_clickhouse_client.execute.return_value = []

        from budmetrics.observability.services import ObservabilityService
        service = ObservabilityService()

        with pytest.raises(ValueError, match="Inference not found"):
            await service.get_inference_details(str(uuid.uuid4()))

    @pytest.mark.asyncio
    async def test_get_inference_feedback_success(self, mock_clickhouse_client, sample_feedback_data):
        """Test successful feedback retrieval."""
        inference_id = str(uuid.uuid4())

        mock_clickhouse_client.execute.return_value = [
            (
                fb["feedback_id"],
                inference_id,
                fb["created_at"],
                fb["feedback_type"],
                fb["metric_name"],
                fb["value"]
            )
            for fb in sample_feedback_data
        ]

        from budmetrics.observability.services import ObservabilityService
        service = ObservabilityService()

        response = await service.get_inference_feedback(inference_id)

        assert len(response) == 2
        assert response[0].feedback_type == "boolean"
        assert response[0].metric_name == "helpful"
        assert response[0].value == 1
        assert response[1].feedback_type == "float"
        assert response[1].metric_name == "quality_rating"
        assert response[1].value == 4.5

    @pytest.mark.asyncio
    async def test_get_inference_feedback_empty(self, mock_clickhouse_client):
        """Test feedback retrieval with no feedback."""
        mock_clickhouse_client.execute.return_value = []

        from budmetrics.observability.services import ObservabilityService
        service = ObservabilityService()

        response = await service.get_inference_feedback(str(uuid.uuid4()))

        assert len(response) == 0

    def test_inference_list_request_validation(self):
        """Test request validation for inference list."""
        # Valid request
        request = InferenceListRequest(
            from_date=datetime.utcnow() - timedelta(days=7),
            limit=50,
            offset=0
        )
        assert request.limit == 50
        assert request.offset == 0

        # Test with all optional parameters
        request = InferenceListRequest(
            project_id=uuid.uuid4(),
            endpoint_id=uuid.uuid4(),
            model_id=uuid.uuid4(),
            from_date=datetime.utcnow() - timedelta(days=7),
            to_date=datetime.utcnow(),
            is_success=True,
            min_tokens=100,
            max_tokens=500,
            max_latency_ms=1000,
            sort_by="timestamp",
            sort_order="desc",
            limit=100,
            offset=50
        )
        assert request.sort_by == "timestamp"
        assert request.sort_order == "desc"

    def test_inference_response_serialization(self, sample_inference_data):
        """Test response serialization."""
        from budmetrics.observability.schemas import InferenceListItem

        item = InferenceListItem(
            inference_id=sample_inference_data["inference_id"],
            timestamp=sample_inference_data["timestamp"],
            project_id=sample_inference_data["project_id"],
            endpoint_id=sample_inference_data["endpoint_id"],
            model_id=sample_inference_data["model_id"],
            model_name=sample_inference_data["model_name"],
            model_provider=sample_inference_data["model_provider"],
            is_success=sample_inference_data["is_success"],
            input_tokens=sample_inference_data["input_tokens"],
            output_tokens=sample_inference_data["output_tokens"],
            response_time_ms=sample_inference_data["response_time_ms"],
            cost=sample_inference_data["cost"],
            cached=sample_inference_data["cached"],
            prompt_preview="Hello",
            response_preview="Hi there!"
        )

        # Test JSON serialization
        json_data = item.model_dump_json()
        assert sample_inference_data["inference_id"] in json_data
        assert "gpt-4" in json_data
