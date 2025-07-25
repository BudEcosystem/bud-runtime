"""Unit tests for ObservabilityMetricsService class."""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any

from budmetrics.observability.services import ObservabilityMetricsService
from budmetrics.observability.models import ClickHouseConfig
from budmetrics.observability.schemas import (
    ObservabilityMetricsRequest, 
    ObservabilityMetricsResponse,
    PeriodBin,
    InferenceDetailsMetrics,
    MetricsData,
    CountMetric,
    TimeMetric,
    PerformanceMetric
)
from tests.fixtures.test_data import (
    ANALYTICS_REQUEST_SAMPLES,
    get_mock_clickhouse_response,
    SAMPLE_BULK_INFERENCE_DATA
)
from uuid import uuid4


def create_test_request(request_type: str) -> ObservabilityMetricsRequest:
    """Create a test request based on type."""
    project_id = uuid4()
    model_id = uuid4()
    
    if request_type == "basic":
        return ObservabilityMetricsRequest(
            metrics=["request_count"],
            from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            frequency_unit="day",
            filters={"project": project_id}
        )
    elif request_type == "with_filters":
        return ObservabilityMetricsRequest(
            metrics=["latency", "throughput", "ttft"],
            from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            frequency_unit="hour",
            filters={"project": project_id, "model": model_id}
        )
    elif request_type == "with_groupby":
        return ObservabilityMetricsRequest(
            metrics=["request_count"],
            from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            frequency_unit="day",
            filters={"project": project_id},
            group_by=["model"]
        )
    elif request_type == "with_topk":
        return ObservabilityMetricsRequest(
            metrics=["request_count"],
            from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            frequency_unit="day",
            group_by=["model"],
            topk=3
        )
    elif request_type == "custom_interval":
        return ObservabilityMetricsRequest(
            metrics=["request_count"],
            from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            to_date=datetime(2024, 2, 28, tzinfo=timezone.utc),
            frequency_unit="week",
            frequency_interval=2,
            filters={"project": project_id}
        )
    else:
        raise ValueError(f"Unknown request type: {request_type}")


class TestObservabilityMetricsService:
    """Test cases for ObservabilityMetricsService class."""
    
    
    @pytest.fixture
    def service(self):
        """Create ObservabilityMetricsService instance."""
        # Create service with mock config
        service = ObservabilityMetricsService()
        # Inject mock client
        service._clickhouse_client = AsyncMock()
        service._query_builder = Mock()
        return service
    
    @pytest.fixture
    def basic_request(self):
        """Basic analytics request fixture."""
        return ObservabilityMetricsRequest(
            metrics=["request_count"],
            from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            frequency_unit="day",
            filters={"project": uuid4()}
        )
    
    @pytest.mark.asyncio
    async def test_get_metrics_basic(self, service, basic_request):
        """Test basic metrics retrieval."""
        # Mock QueryBuilder
        service._query_builder.build_query = Mock(return_value=("SELECT * FROM test", ["time_bucket", "request_count"]))
        
        # Mock ClickHouse response - service expects tuples, not dicts
        mock_response = [
            (datetime(2024, 1, 1, tzinfo=timezone.utc), 100),
            (datetime(2024, 1, 2, tzinfo=timezone.utc), 120)
        ]
        service._clickhouse_client.execute_query = AsyncMock(return_value=mock_response)
        
        result = await service.get_metrics(basic_request)
        
        # Verify response structure
        assert isinstance(result, ObservabilityMetricsResponse)
        assert len(result.items) == 2
        
        # Verify first period
        period = result.items[0]
        assert isinstance(period, PeriodBin)
        assert period.time_period == datetime(2024, 1, 2, tzinfo=timezone.utc)  # Results are sorted descending
        assert len(period.items) == 1
        assert "request_count" in period.items[0].data
        
        # Verify query was called
        service._clickhouse_client.execute_query.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_metrics_multiple_metrics(self, service):
        """Test metrics with multiple metrics."""
        request = create_test_request("with_filters")
        
        # Mock QueryBuilder
        service._query_builder.build_query = Mock(return_value=(
            "SELECT * FROM test", 
            ["time_bucket", "avg_latency_ms", "avg_throughput_tokens_per_sec", "avg_ttft_ms"]
        ))
        
        # Mock response with multiple metrics as tuples
        mock_response = [
            (datetime(2024, 1, 1, tzinfo=timezone.utc), 250.5, 15.2, 125.3),
            (datetime(2024, 1, 1, 1, tzinfo=timezone.utc), 275.8, 12.8, 130.1)
        ]
        service._clickhouse_client.execute_query = AsyncMock(return_value=mock_response)
        
        result = await service.get_metrics(request)
        
        assert len(result.items) == 2
        
        # Check first period has all metrics
        period = result.items[0]
        assert len(period.items) == 1
        metrics_data = period.items[0].data
        assert "latency" in metrics_data
        assert "throughput" in metrics_data
        assert "ttft" in metrics_data
    
    @pytest.mark.asyncio
    async def test_get_metrics_with_groupby(self, service):
        """Test metrics with GROUP BY."""
        request = create_test_request("with_groupby")
        
        # Mock QueryBuilder
        service._query_builder.build_query = Mock(return_value=(
            "SELECT * FROM test", 
            ["time_bucket", "model_id", "request_count"]
        ))
        
        # Mock grouped response as tuples
        model_id_1 = uuid4()
        model_id_2 = uuid4()
        mock_response = [
            (datetime(2024, 1, 1, tzinfo=timezone.utc), model_id_1, 100),
            (datetime(2024, 1, 1, tzinfo=timezone.utc), model_id_2, 50)
        ]
        service._clickhouse_client.execute_query = AsyncMock(return_value=mock_response)
        
        result = await service.get_metrics(request)
        
        # Should have one time period with multiple items
        assert len(result.items) == 1
        assert len(result.items[0].items) == 2  # Two different models
    
    @pytest.mark.asyncio
    async def test_get_metrics_with_topk(self, service):
        """Test metrics with TopK."""
        request = create_test_request("with_topk")
        
        # Mock QueryBuilder
        service._query_builder.build_query = Mock(return_value=(
            "SELECT ... LIMIT 3 BY time_bucket", 
            ["time_bucket", "model_id", "request_count"]
        ))
        
        # Mock TopK response (should be limited)
        model_ids = [uuid4() for _ in range(3)]
        mock_response = [
            (datetime(2024, 1, 1, tzinfo=timezone.utc), model_ids[0], 150),
            (datetime(2024, 1, 1, tzinfo=timezone.utc), model_ids[1], 120),
            (datetime(2024, 1, 1, tzinfo=timezone.utc), model_ids[2], 100)
        ]
        service._clickhouse_client.execute_query = AsyncMock(return_value=mock_response)
        
        # Mock metric processor
        service._metric_processors = {
            "request_count": lambda row, fi, dm, pm: (
                "request_count", 
                CountMetric(count=row[fi["request_count"]])
            )
        }
        
        result = await service.get_metrics(request)
        
        # Should respect TopK limit
        assert len(result.items) == 1  # One time bucket
        assert len(result.items[0].items) == 3  # Top 3 models
    
    @pytest.mark.asyncio
    async def test_process_query_results_basic(self, service):
        """Test basic result processing."""
        # Service expects tuples, not dicts
        mock_results = [
            (datetime(2024, 1, 1, tzinfo=timezone.utc), 100, 95),
            (datetime(2024, 1, 2, tzinfo=timezone.utc), 120, 115)
        ]
        field_order = ["time_bucket", "request_count", "success_request"]
        metrics = ["request_count", "success_request"]
        
        # Mock metric processors
        service._metric_processors = {
            "request_count": lambda row, fi, dm, pm: ("request_count", CountMetric(count=row[fi["request_count"]])),
            "success_request": lambda row, fi, dm, pm: ("success_request", CountMetric(count=row[fi["success_request"]]))
        }
        
        result = service._process_query_results(mock_results, field_order, metrics)
        
        assert len(result) == 2
        # Results are sorted by time descending
        assert result[0].time_period == datetime(2024, 1, 2, tzinfo=timezone.utc)
        assert result[0].items[0].data["request_count"].count == 120
    
    def test_process_query_results_with_groupby(self, service):
        """Test result processing with GROUP BY fields."""
        model_id_1 = uuid4()
        model_id_2 = uuid4()
        endpoint_id = uuid4()
        
        mock_results = [
            (datetime(2024, 1, 1, tzinfo=timezone.utc), model_id_1, endpoint_id, 50),
            (datetime(2024, 1, 1, tzinfo=timezone.utc), model_id_2, endpoint_id, 30)
        ]
        field_order = ["time_bucket", "model", "endpoint", "request_count"]
        metrics = ["request_count"]
        group_by = ["model", "endpoint"]  # Use group field names without _id suffix
        
        # Mock metric processor
        service._metric_processors = {
            "request_count": lambda row, fi, dm, pm: (
                "request_count", 
                CountMetric(count=row[fi["request_count"]])
            )
        }
        
        result = service._process_query_results(mock_results, field_order, metrics, group_by)
        
        assert len(result) == 1  # One time bucket
        assert len(result[0].items) == 2  # Two different models
        # Since we use "model" in group_by but "model_id" in field_order, 
        # the service maps group fields to their actual column names
        found_model_ids = {item.model_id for item in result[0].items}
        assert model_id_1 in found_model_ids
        assert model_id_2 in found_model_ids
    
    def test_process_query_results_gap_detection(self, service):
        """Test detection of gap-filled rows."""
        model_id = uuid4()
        from uuid import UUID
        zero_uuid = UUID("00000000-0000-0000-0000-000000000000")
        
        mock_results = [
            (datetime(2024, 1, 1, tzinfo=timezone.utc), model_id, 100),
            (datetime(2024, 1, 1, tzinfo=timezone.utc), zero_uuid, 0)  # Gap-filled
        ]
        field_order = ["time_bucket", "model_id", "request_count"]
        metrics = ["request_count"]
        group_by = ["model_id"]  # Use actual column name
        
        # Mock the _ZERO_UUID attribute - it's already set in the service
        # service._ZERO_UUID = UUID("00000000-0000-0000-0000-000000000000")
        
        # Mock metric processor
        service._metric_processors = {
            "request_count": lambda row, fi, dm, pm: (
                "request_count", 
                CountMetric(count=row[fi["request_count"]])
            )
        }
        
        result = service._process_query_results(mock_results, field_order, metrics, group_by)
        
        # Gap-filled rows should be filtered out
        assert len(result) == 1
        assert len(result[0].items) == 1  # Only one item (gap-filled filtered)
    
    def test_sanitize_delta_percent(self, service):
        """Test delta percent sanitization."""
        # Normal values should pass through
        assert service._sanitize_delta_percent(10.5) == 10.5
        assert service._sanitize_delta_percent(-25.3) == -25.3
        assert service._sanitize_delta_percent(0.0) == 0.0
        
        # Extreme values should be capped at 100/-100
        assert service._sanitize_delta_percent(float('inf')) == 100.0
        assert service._sanitize_delta_percent(float('-inf')) == -100.0
        
        # NaN should become 0.0
        assert service._sanitize_delta_percent(float('nan')) == 0.0
    
    def test_process_time_metric(self, service):
        """Test time metric processing."""
        # Mock data with time metrics
        row = (datetime(2024, 1, 1, tzinfo=timezone.utc), 250.5, 10.0, 4.16)
        field_indices = {
            "time_bucket": 0,
            "avg_queuing_time_ms": 1,
            "avg_queuing_time_ms_delta": 2,
            "avg_queuing_time_ms_percent_change": 3
        }
        delta_map = {"avg_queuing_time_ms": "avg_queuing_time_ms_delta"}
        percent_map = {"avg_queuing_time_ms": "avg_queuing_time_ms_percent_change"}
        config = {"output_key": "queuing_time", "time_field": "avg_queuing_time_ms"}
        
        key, metric = service._process_time_metric(row, field_indices, delta_map, percent_map, config)
        
        assert key == "queuing_time"
        assert isinstance(metric, TimeMetric)
        assert metric.avg_time_ms == 250.5
        assert metric.delta == 10.0
        assert metric.delta_percent == 4.16
    
    def test_process_count_metric(self, service):
        """Test count metric processing."""
        # Mock data
        row = (datetime(2024, 1, 1, tzinfo=timezone.utc), 100, 95, 5.0, 5.26)
        field_indices = {
            "time_bucket": 0,
            "request_count": 1,
            "success_request_count": 2,
            "request_count_delta": 3,
            "request_count_percent_change": 4
        }
        delta_map = {"request_count": "request_count_delta"}
        percent_map = {"request_count": "request_count_percent_change"}
        config = {"output_key": "request_count", "count_field": "request_count", "rate_field": None}
        
        key, metric = service._process_count_metric(row, field_indices, delta_map, percent_map, config)
        
        assert key == "request_count"
        assert isinstance(metric, CountMetric)
        assert metric.count == 100
        assert metric.delta == 5.0
        assert metric.delta_percent == 5.26
    
    @pytest.mark.asyncio
    async def test_insert_inference_details_basic(self, service):
        """Test basic metrics ingestion."""
        # Prepare test data as tuples (matching what routes.py sends)
        batch_data = [
            (
                uuid4(),  # inference_id
                "192.168.1.1",  # request_ip
                uuid4(),  # project_id
                uuid4(),  # endpoint_id
                uuid4(),  # model_id
                0.001,  # cost
                '{"analysis": "test"}',  # response_analysis
                True,  # is_success
                datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),  # request_arrival_time
                datetime(2024, 1, 1, 10, 0, 1, tzinfo=timezone.utc)  # request_forward_time
            )
            for _ in range(5)
        ]
        
        # Mock execute for INSERT
        service._clickhouse_client.execute = AsyncMock(return_value=None)
        
        result = await service.insert_inference_details(batch_data)
        
        # Should return success info
        assert result["total_records"] == 5
        assert result["inserted"] == 5
        assert result["duplicates"] == 0
    
    @pytest.mark.asyncio
    async def test_insert_inference_details_with_duplicates(self, service):
        """Test metrics ingestion with duplicates."""
        # Create batch with duplicates
        inference_id_1 = uuid4()
        inference_id_2 = uuid4()
        
        batch_data = []
        # Add unique records
        for i in range(3):
            batch_data.append((
                uuid4() if i < 2 else inference_id_1,  # Third is duplicate of first
                "192.168.1.1",
                uuid4(),
                uuid4(),
                uuid4(),
                0.001,
                None,
                True,
                datetime.now(timezone.utc),
                datetime.now(timezone.utc)
            ))
        
        # Mock execute_query to simulate duplicate detection
        # First call is the SELECT to check for existing IDs
        # Second call is the INSERT which should succeed
        call_count = 0
        async def mock_execute_query(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # SELECT query - return one existing ID to simulate duplicate
                return [(batch_data[0][0],)]  # First record's inference_id
            else:
                # INSERT query - succeeds
                return None
            
        service._clickhouse_client.execute_query = mock_execute_query
        
        result = await service.insert_inference_details(batch_data)
        
        # Should handle duplicates gracefully
        assert result["duplicates"] > 0
    
    def test_escape_string(self, service):
        """Test string escaping for SQL."""
        # Test basic escaping
        assert service._escape_string("test") == "'test'"
        assert service._escape_string("test's") == "'test''s'"
        assert service._escape_string(None) == "NULL"
        assert service._escape_string(123) == "123"
    
    @pytest.mark.asyncio
    async def test_error_handling(self, service):
        """Test error handling in service methods."""
        request = create_test_request("basic")
        
        # Mock QueryBuilder and client to raise an error
        service._query_builder.build_query = Mock(return_value=("SELECT * FROM test", ["time_bucket", "request_count"]))
        service._clickhouse_client.execute_query.side_effect = Exception("Database connection failed")
        
        with pytest.raises(RuntimeError, match="Failed to execute metrics query"):
            await service.get_metrics(request)
    
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_metric_handling(self, service):
        """Test special handling for concurrent_requests metric."""
        request = ObservabilityMetricsRequest(
            metrics=["concurrent_requests"],
            from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            frequency_unit="hour",
            filters={"project": uuid4()}
        )
        
        # Mock QueryBuilder and response
        service._query_builder.build_query = Mock(return_value=(
            "WITH concurrent_cte AS ...", 
            ["time_bucket", "concurrent_requests"]
        ))
        
        mock_response = [
            (datetime(2024, 1, 1, 0, tzinfo=timezone.utc), 5),
            (datetime(2024, 1, 1, 1, tzinfo=timezone.utc), 8)
        ]
        service._clickhouse_client.execute_query = AsyncMock(return_value=mock_response)
        
        # Mock metric processor for concurrent requests
        service._metric_processors = {
            "concurrent_requests": lambda row, fi, dm, pm: (
                "concurrent_requests", 
                PerformanceMetric(avg=row[fi["concurrent_requests"]])
            )
        }
        
        result = await service.get_metrics(request)
        
        assert len(result.items) == 2
    
    @pytest.mark.asyncio
    async def test_large_dataset_processing(self, service):
        """Test processing of large datasets."""
        # Create large mock response as tuples
        large_response = []
        model_ids = [uuid4() for _ in range(10)]
        for i in range(1000):
            large_response.append((
                datetime(2024, 1, 1, i % 24, tzinfo=timezone.utc),
                model_ids[i % 10],
                100 + i
            ))
        
        # Mock setup
        service._query_builder.build_query = Mock(return_value=(
            "SELECT ...", 
            ["time_bucket", "model_id", "request_count"]
        ))
        service._clickhouse_client.execute_query = AsyncMock(return_value=large_response)
        
        # Mock metric processor
        service._metric_processors = {
            "request_count": lambda row, fi, dm, pm: (
                "request_count", 
                CountMetric(count=row[fi["request_count"]])
            )
        }
        
        request = ObservabilityMetricsRequest(
            metrics=["request_count"],
            from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            frequency_unit="hour",
            group_by=["model"]
        )
        
        result = await service.get_metrics(request)
        
        # Should handle large datasets efficiently
        # Results are grouped by time_bucket, so we should have 24 unique hours
        assert len(result.items) == 24
        # Each time bucket should have multiple items (one per model)
        total_items = sum(len(period.items) for period in result.items)
        assert total_items == 1000