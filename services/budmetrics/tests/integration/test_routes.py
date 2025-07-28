"""Integration tests for API routes."""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any

import httpx
from fastapi.testclient import TestClient
from fastapi import FastAPI
from httpx import ASGITransport

from budmetrics.observability.routes import observability_router
from budmetrics.observability.schemas import (
    ObservabilityMetricsRequest,
    InferenceDetailsMetrics,
    ObservabilityMetricsResponse,
    PeriodBin,
    MetricsData,
    CountMetric,
)
from budmetrics.commons.schemas import BulkCloudEventBase, CloudEventEntry, CloudEventMetaData
from uuid import uuid4
from tests.fixtures.test_data import (
    ANALYTICS_REQUEST_SAMPLES,
    SAMPLE_BULK_INFERENCE_DATA,
    get_mock_clickhouse_response,
)

def create_cloud_event_entry(inference_data: dict) -> dict:
    """Helper to create a CloudEventEntry-compatible dict."""
    return {
        "event": {"data": inference_data},
        "entryId": str(uuid4()),
        "metadata": {
            "cloudevent.id": str(uuid4()),
            "cloudevent.type": "com.bud.observability.inference"
        },
        "contentType": "application/json"
    }

def create_bulk_cloud_event(entries: list[dict]) -> dict:
    """Helper to create a BulkCloudEventBase-compatible dict."""
    cloud_entries = [create_cloud_event_entry(entry) for entry in entries]
    return {
        "entries": cloud_entries,
        "id": str(uuid4()),
        "metadata": {"source": "test-suite"},
        "pubsubname": "test-pubsub",
        "topic": "observability-metrics",
        "type": "com.bud.observability.bulk"
    }
@pytest.fixture
def app():
    """Create FastAPI test app."""
    app = FastAPI()
    app.include_router(observability_router)
    return app
@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)
@pytest.fixture
def mock_service():
    """Create a mock service that can be used with patch."""
    service = AsyncMock()
    # Set up default return values
    service.get_metrics = AsyncMock()
    service.insert_inference_details = AsyncMock(return_value={
        "total_records": 0,
        "inserted": 0,
        "duplicates": 0,
        "duplicate_ids": []
    })
    return service
class TestAnalyticsEndpoint:
    """Test cases for /observability/analytics endpoint."""

    @patch('budmetrics.observability.routes.service')
    def test_analytics_basic_request(self, mock_service, client):
        """Test basic analytics request."""
        # Create proper request payload
        from uuid import uuid4
        project_id = uuid4()
        model_id = uuid4()

        payload = {
            "metrics": ["request_count", "success_request"],
            "from_date": "2024-01-01T00:00:00Z",
            "to_date": "2024-01-31T00:00:00Z",
            "frequency_unit": "day",
            "filters": {
                "project": str(project_id),
                "model": str(model_id)
            }
        }

        # Mock service response - make it async
        mock_response = ObservabilityMetricsResponse(items=[])
        mock_service.get_metrics = AsyncMock(return_value=mock_response)

        response = client.post("/observability/analytics", json=payload)

        assert response.status_code == 200
        mock_service.get_metrics.assert_called_once()

    @patch('budmetrics.observability.routes.service')
    def test_analytics_with_all_parameters(self, mock_service, client):
        """Test analytics request with all parameters."""
        project_id = uuid4()
        model_id = uuid4()
        endpoint_id = uuid4()

        payload = {
            "filters": {
                "project": str(project_id),
                "model": str(model_id),
                "endpoint": str(endpoint_id)
            },
            "from_date": "2024-01-01T00:00:00Z",
            "to_date": "2024-01-31T00:00:00Z",
            "frequency_unit": "hour",
            "metrics": ["request_count", "latency", "success_request"],
            "group_by": ["model", "endpoint"],
            # Note: topk cannot be used with filters
        }

        mock_response = ObservabilityMetricsResponse(items=[])
        mock_service.get_metrics = AsyncMock(return_value=mock_response)

        response = client.post("/observability/analytics", json=payload)

        assert response.status_code == 200

        # Verify the service was called with correct parameters
        call_args = mock_service.get_metrics.call_args[0][0]
        assert call_args.filters["project"] == project_id
        assert call_args.filters["model"] == model_id
        assert call_args.filters["endpoint"] == endpoint_id
        assert call_args.frequency_unit == "hour"
        assert call_args.metrics == ["request_count", "latency", "success_request"]
        assert call_args.group_by == ["model", "endpoint"]

    @patch('budmetrics.observability.routes.service')
    def test_analytics_custom_frequency(self, mock_service, client):
        """Test analytics with custom frequency."""
        payload = {
            "filters": {"project": str(uuid4())},
            "from_date": "2024-01-01T00:00:00Z",
            "to_date": "2024-02-29T00:00:00Z",
            "frequency_unit": "day",
            "frequency_interval": 7,
            "metrics": ["request_count"],
        }

        mock_response = ObservabilityMetricsResponse(items=[])
        mock_service.get_metrics = AsyncMock(return_value=mock_response)

        response = client.post("/observability/analytics", json=payload)

        assert response.status_code == 200

        call_args = mock_service.get_metrics.call_args[0][0]
        assert call_args.frequency_unit == "day"
        assert call_args.frequency_interval == 7

    def test_analytics_validation_errors(self, client):
        """Test analytics request validation errors."""
        # Missing required field (metrics)
        invalid_payload = {
            "filters": {"project": str(uuid4())},
            "from_date": "2024-01-01T00:00:00Z",
            "to_date": "2024-01-31T00:00:00Z",
            "frequency_unit": "day",
            # Missing metrics
        }

        response = client.post("/observability/analytics", json=invalid_payload)
        assert response.status_code == 422

        # Invalid frequency
        invalid_payload = {
            "filters": {"project": str(uuid4())},
            "from_date": "2024-01-01T00:00:00Z",
            "to_date": "2024-01-31T00:00:00Z",
            "frequency_unit": "invalid_frequency",
            "metrics": ["request_count"],
        }

        response = client.post("/observability/analytics", json=invalid_payload)
        assert response.status_code == 422

        # Invalid metrics
        invalid_payload = {
            "filters": {"project": str(uuid4())},
            "from_date": "2024-01-01T00:00:00Z",
            "to_date": "2024-01-31T00:00:00Z",
            "frequency_unit": "day",
            "metrics": ["invalid_metric"],
        }

        response = client.post("/observability/analytics", json=invalid_payload)
        assert response.status_code == 422

    @patch('budmetrics.observability.routes.service')
    def test_analytics_date_range_validation(self, mock_service, client):
        """Test date range validation."""
        # from_date after to_date
        invalid_payload = {
            "filters": {"project": str(uuid4())},
            "from_date": "2024-01-31T00:00:00Z",
            "to_date": "2024-01-01T00:00:00Z",
            "frequency_unit": "day",
            "metrics": ["request_count"],
        }

        response = client.post("/observability/analytics", json=invalid_payload)
        assert response.status_code == 422

    @patch('budmetrics.observability.routes.service')
    def test_analytics_service_error(self, mock_service, client):
        """Test handling of service errors."""
        payload = {
            "filters": {"project": str(uuid4())},
            "from_date": "2024-01-01T00:00:00Z",
            "to_date": "2024-01-31T00:00:00Z",
            "frequency_unit": "day",
            "metrics": ["request_count"],
        }

        # Mock service to raise an error
        mock_service.get_metrics.side_effect = Exception("Database connection failed")

        response = client.post("/observability/analytics", json=payload)
        assert response.status_code == 500

    @patch('budmetrics.observability.routes.service')
    def test_analytics_response_structure(self, mock_service, client):
        """Test analytics response structure."""
        payload = {
            "filters": {"project": str(uuid4())},
            "from_date": "2024-01-01T00:00:00Z",
            "to_date": "2024-01-31T00:00:00Z",
            "frequency_unit": "day",
            "metrics": ["request_count", "success_request"],
        }

        # Mock detailed response
        from budmetrics.observability.schemas import (
            ObservabilityMetricsResponse,
            PeriodBin,
        )

        periods = [
            PeriodBin(
                time_period=datetime(2024, 1, 1, tzinfo=timezone.utc),
                items=[
                    MetricsData(
                        data={
                            "request_count": CountMetric(count=100),
                            "success_request": CountMetric(count=95)
                        }
                    )
                ]
            ),
            PeriodBin(
                time_period=datetime(2024, 1, 2, tzinfo=timezone.utc),
                items=[
                    MetricsData(
                        data={
                            "request_count": CountMetric(count=120),
                            "success_request": CountMetric(count=115)
                        }
                    )
                ]
            ),
        ]

        mock_response = ObservabilityMetricsResponse(items=periods)
        mock_service.get_metrics = AsyncMock(return_value=mock_response)

        response = client.post("/observability/analytics", json=payload)

        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert len(data["items"]) == 2

        # Check first period
        period1 = data["items"][0]
        assert "time_period" in period1
        assert "items" in period1
        assert len(period1["items"]) == 1
        assert "data" in period1["items"][0]
        assert "request_count" in period1["items"][0]["data"]
        assert "success_request" in period1["items"][0]["data"]
        assert period1["items"][0]["data"]["request_count"]["count"] == 100
        assert period1["items"][0]["data"]["success_request"]["count"] == 95
class TestAddMetricsEndpoint:
    """Test cases for /observability/add endpoint."""

    @patch('budmetrics.observability.routes.service')
    def test_add_metrics_basic(self, mock_service, client):
        """Test basic metrics ingestion."""
        # Prepare inference data
        inference_entries = SAMPLE_BULK_INFERENCE_DATA[:5]

        # Create bulk event with proper cloud event structure
        bulk_event_data = create_bulk_cloud_event(inference_entries)

        # Mock service response
        mock_service.insert_inference_details = AsyncMock(return_value={
            "total_records": 5,
            "inserted": 5,
            "duplicates": 0,
            "duplicate_ids": []
        })

        response = client.post("/observability/add", json=bulk_event_data)

        assert response.status_code == 200
        data = response.json()

        # Check the response structure
        assert "message" in data
        assert "param" in data
        assert "summary" in data["param"]
        assert data["param"]["summary"]["successfully_inserted"] == 5
        assert data["param"]["summary"]["duplicates_skipped"] == 0

        mock_service.insert_inference_details.assert_called_once()

    @patch('budmetrics.observability.routes.service')
    def test_add_metrics_with_duplicates(self, mock_service, client):
        """Test metrics ingestion with duplicates."""
        # Prepare inference data
        inference_entries = SAMPLE_BULK_INFERENCE_DATA[:3]

        # Create bulk event with proper cloud event structure
        bulk_event_data = create_bulk_cloud_event(inference_entries)

        # Mock service response with duplicates
        mock_service.insert_inference_details = AsyncMock(return_value={
            "total_records": 3,
            "inserted": 2,
            "duplicates": 1,
            "duplicate_ids": [str(uuid4())]
        })

        response = client.post("/observability/add", json=bulk_event_data)

        assert response.status_code == 200
        data = response.json()

        # Check the response structure
        assert "message" in data
        assert "Successfully inserted 2 new records" in data["message"]
        assert "Skipped 1 duplicate records" in data["message"]
        assert data["param"]["summary"]["successfully_inserted"] == 2
        assert data["param"]["summary"]["duplicates_skipped"] == 1

    @patch('budmetrics.observability.routes.service')
    def test_add_metrics_validation_errors(self, mock_service, client):
        """Test metrics ingestion with validation errors."""
        # Create invalid entries
        invalid_entries = [
            {
                # Missing required fields
                "project_id": str(uuid4()),
                "is_success": True,
                # Missing inference_id and request_arrival_time
            },
            {
                "inference_id": "not-a-uuid",  # Invalid UUID format
                "project_id": str(uuid4()),
                "endpoint_id": str(uuid4()),
                "model_id": str(uuid4()),
                "is_success": "invalid",  # Wrong type
                "request_arrival_time": datetime.now(timezone.utc).isoformat(),
                "request_forward_time": datetime.now(timezone.utc).isoformat(),
            },
        ]

        bulk_event = {
            "type": "observability.inference",
            "source": "test",
            "entries": invalid_entries,
        }

        response = client.post("/observability/add", json=bulk_event)

        # Should return validation error
        assert response.status_code == 422

    @patch('budmetrics.observability.routes.service')
    def test_add_metrics_empty_entries(self, mock_service, client):
        """Test metrics ingestion with empty entries."""
        # Create bulk event with empty entries
        bulk_event_data = create_bulk_cloud_event([])

        response = client.post("/observability/add", json=bulk_event_data)

        # Should handle empty entries gracefully
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "No records to process"
        assert data["param"]["summary"]["total_entries"] == 0

    @patch('budmetrics.observability.routes.service')
    def test_add_metrics_service_error(self, mock_service, client):
        """Test handling of service errors during ingestion."""
        # Prepare inference data
        inference_entries = SAMPLE_BULK_INFERENCE_DATA[:3]

        # Create bulk event with proper cloud event structure
        bulk_event_data = create_bulk_cloud_event(inference_entries)

        # Mock service to raise an error
        mock_service.insert_inference_details.side_effect = Exception(
            "Database insert failed"
        )

        response = client.post("/observability/add", json=bulk_event_data)
        assert response.status_code == 500

        data = response.json()
        assert "error" in data["message"].lower()

    @patch('budmetrics.observability.routes.service')
    def test_add_metrics_large_batch(self, mock_service, client):
        """Test metrics ingestion with large batch."""
        # Use all available test data for large batch
        inference_entries = SAMPLE_BULK_INFERENCE_DATA

        # Create bulk event with proper cloud event structure
        bulk_event_data = create_bulk_cloud_event(inference_entries)

        mock_service.insert_inference_details = AsyncMock(return_value={
            "total_records": len(inference_entries),
            "inserted": len(inference_entries),
            "duplicates": 0,
            "duplicate_ids": []
        })

        response = client.post("/observability/add", json=bulk_event_data)

        assert response.status_code == 200
        data = response.json()
        assert data["param"]["summary"]["successfully_inserted"] == len(inference_entries)

    @patch('budmetrics.observability.routes.service')
    def test_add_metrics_response_structure(self, mock_service, client):
        """Test add metrics response structure."""
        # Prepare inference data
        inference_entries = SAMPLE_BULK_INFERENCE_DATA[:3]

        # Create bulk event with proper cloud event structure
        bulk_event_data = create_bulk_cloud_event(inference_entries)

        mock_service.insert_inference_details = AsyncMock(return_value={
            "total_records": 3,
            "inserted": 3,
            "duplicates": 0,
            "duplicate_ids": []
        })

        response = client.post("/observability/add", json=bulk_event_data)

        assert response.status_code == 200
        data = response.json()

        # Check required fields in the response
        assert "message" in data
        assert "param" in data
        assert "summary" in data["param"]

        # Check summary structure
        summary = data["param"]["summary"]
        assert "total_entries" in summary
        assert "successfully_inserted" in summary
        assert "duplicates_skipped" in summary
        assert "validation_failures" in summary

        # Verify values
        assert summary["total_entries"] == 3
        assert summary["successfully_inserted"] == 3
        assert summary["duplicates_skipped"] == 0
        assert summary["validation_failures"] == 0
class TestHealthAndStatus:
    """Test cases for health and status endpoints."""

    @patch('budmetrics.observability.routes.service')
    def test_health_endpoint(self, mock_service, client):
        """Test health check endpoint if available."""
        # This would test a health endpoint if it exists
        # For now, just test that the router is properly mounted
        response = client.get("/observability/")
        # Might return 404 if no root endpoint is defined, which is fine
        assert response.status_code in [200, 404, 405]  # Various acceptable responses
class TestConcurrentRequests:
    """Test cases for concurrent request handling."""

    @pytest.mark.asyncio
    @patch('budmetrics.observability.routes.service')
    async def test_concurrent_analytics_requests(self, mock_service):
        """Test handling of concurrent analytics requests."""
        # Setup the app and use the ASGI transport
        app = FastAPI()
        app.include_router(observability_router)

        payload = {
            "filters": {"project": str(uuid4())},
            "from_date": "2024-01-01T00:00:00Z",
            "to_date": "2024-01-31T00:00:00Z",
            "frequency_unit": "day",
            "metrics": ["request_count"],
        }

        mock_response = ObservabilityMetricsResponse(items=[])
        mock_service.get_metrics = AsyncMock(return_value=mock_response)

        # Create multiple concurrent requests using ASGITransport
        from httpx import ASGITransport
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            tasks = [
                client.post("/observability/analytics", json=payload) for _ in range(10)
            ]
            responses = await asyncio.gather(*tasks)

        # All requests should succeed
        for response in responses:
            assert response.status_code == 200

        # Service should be called for each request
        assert mock_service.get_metrics.call_count == 10
class TestErrorHandling:
    """Test cases for error handling."""

    @patch('budmetrics.observability.routes.service')
    def test_malformed_json(self, mock_service, client):
        """Test handling of malformed JSON."""
        response = client.post(
            "/observability/analytics",
            content="invalid json{",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    @patch('budmetrics.observability.routes.service')
    def test_unsupported_content_type(self, mock_service, client):
        """Test handling of unsupported content type."""
        response = client.post(
            "/observability/analytics",
            content="some data",
            headers={"Content-Type": "text/plain"},
        )

        assert response.status_code == 422

    @patch('budmetrics.observability.routes.service')
    def test_oversized_request(self, mock_service, client):
        """Test handling of oversized requests."""
        # Create a very large payload
        large_entries = []
        project_id = uuid4()
        endpoint_id = uuid4()
        model_id = uuid4()
        for i in range(10000):  # Very large number of entries
            large_entries.append(
                {
                    "inference_id": str(uuid4()),
                    "project_id": str(project_id),
                    "endpoint_id": str(endpoint_id),
                    "model_id": str(model_id),
                    "is_success": True,
                    "request_arrival_time": datetime.now(timezone.utc).isoformat(),
                    "request_forward_time": datetime.now(timezone.utc).isoformat(),
                }
            )

        bulk_event = {
            "type": "observability.inference",
            "source": "test",
            "entries": large_entries,
        }

        response = client.post("/observability/add", json=bulk_event)

        # Might succeed or fail depending on server limits
        # This test ensures the server doesn't crash
        assert response.status_code in [200, 413, 422, 500]
