"""Unit tests for observability schemas."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import ValidationError

from budmetrics.observability.schemas import (
    ObservabilityMetricsRequest,
    ObservabilityMetricsResponse,
    PeriodBin,
    MetricsData,
    CountMetric,
    TimeMetric,
    PerformanceMetric,
    CacheMetric,
    InferenceDetailsMetrics
)


class TestObservabilityMetricsRequest:
    """Test cases for ObservabilityMetricsRequest schema."""
    
    def test_valid_basic_request(self):
        """Test valid basic request."""
        project_id = uuid4()
        data = {
            "metrics": ["request_count"],
            "from_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "to_date": datetime(2024, 1, 31, tzinfo=timezone.utc),
            "frequency_unit": "day",
            "filters": {
                "project": project_id
            }
        }
        
        request = ObservabilityMetricsRequest(**data)
        
        assert request.metrics == ["request_count"]
        assert request.from_date == datetime(2024, 1, 1, tzinfo=timezone.utc)
        assert request.to_date == datetime(2024, 1, 31, tzinfo=timezone.utc)
        assert request.frequency_unit == "day"
        assert request.filters["project"] == project_id
        assert request.frequency_interval is None
        assert request.group_by is None
        assert request.topk is None
        assert request.return_delta == True  # Default is True in schema
        assert request.fill_time_gaps == True  # Default is True in schema
    
    def test_valid_request_with_all_fields(self):
        """Test valid request with all optional fields."""
        project_id = uuid4()
        model_id = uuid4()
        endpoint_id = uuid4()
        data = {
            "metrics": ["request_count", "success_request", "latency"],
            "from_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "to_date": datetime(2024, 1, 31, tzinfo=timezone.utc),
            "frequency_unit": "hour",
            "frequency_interval": 3,
            "filters": {
                "project": project_id,
                "model": model_id,
                "endpoint": endpoint_id
            },
            "group_by": ["model", "endpoint"],
            "return_delta": False,
            "fill_time_gaps": False
        }
        
        request = ObservabilityMetricsRequest(**data)
        
        assert request.frequency_interval == 3
        assert request.filters["model"] == model_id
        assert request.filters["endpoint"] == endpoint_id
        assert request.group_by == ["model", "endpoint"]
        assert request.topk is None  # topk not allowed with filters
        assert request.return_delta == False
        assert request.fill_time_gaps == False
        
        # Test with topk but without filters
        data2 = {
            "metrics": ["request_count"],
            "from_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "to_date": datetime(2024, 1, 31, tzinfo=timezone.utc),
            "frequency_unit": "day",
            "group_by": ["model"],
            "topk": 10
        }
        
        request2 = ObservabilityMetricsRequest(**data2)
        assert request2.topk == 10
        assert request2.filters is None
    
    def test_invalid_missing_required_fields(self):
        """Test validation with missing required fields."""
        # Missing metrics
        with pytest.raises(ValidationError, match="metrics"):
            ObservabilityMetricsRequest(
                from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
                frequency_unit="day",
                filters={"project": uuid4()}
            )
        
        # Missing from_date
        with pytest.raises(ValidationError, match="from_date"):
            ObservabilityMetricsRequest(
                metrics=["request_count"],
                to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
                frequency_unit="day"
            )
    
    def test_invalid_date_range(self):
        """Test validation with invalid date ranges."""
        # from_date after to_date should be caught by validator
        with pytest.raises(ValidationError):
            ObservabilityMetricsRequest(
                metrics=["request_count"],
                from_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
                to_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                frequency_unit="day",
                filters={"project": uuid4()}
            )
    
    def test_invalid_frequency_interval(self):
        """Test validation with invalid frequency interval."""
        # Negative frequency interval
        with pytest.raises(ValidationError):
            ObservabilityMetricsRequest(
                metrics=["request_count"],
                from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
                frequency_unit="day",
                frequency_interval=-1,
                filters={"project": uuid4()}
            )
        
        # Zero frequency interval
        with pytest.raises(ValidationError):
            ObservabilityMetricsRequest(
                metrics=["request_count"],
                from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
                frequency_unit="day",
                frequency_interval=0,
                filters={"project": uuid4()}
            )
    
    def test_valid_frequency_units(self):
        """Test validation with valid frequency units."""
        valid_units = [
            "hour",
            "day",
            "week",
            "month",
            "quarter",
            "year"
        ]
        
        for unit in valid_units:
            request = ObservabilityMetricsRequest(
                metrics=["request_count"],
                from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
                frequency_unit=unit,
                filters={"project": uuid4()}
            )
            assert request.frequency_unit == unit
    
    def test_valid_metrics(self):
        """Test validation with valid metrics."""
        all_metrics = [
            "request_count", "success_request", "failure_request",
            "queuing_time", "latency", "ttft",
            "input_token", "output_token", "throughput",
            "concurrent_requests", "cache"
        ]
        
        request = ObservabilityMetricsRequest(
            metrics=all_metrics,
            from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            frequency_unit="day",
            filters={"project": uuid4()}
        )
        assert request.metrics == all_metrics
    
    def test_valid_group_by(self):
        """Test validation with valid group_by values."""
        valid_group_by = [
            ["model"],
            ["endpoint"],
            ["model", "endpoint"]
        ]
        
        for group_by in valid_group_by:
            request = ObservabilityMetricsRequest(
                metrics=["request_count"],
                from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
                frequency_unit="day",
                filters={"project": uuid4()},
                group_by=group_by
            )
            assert request.group_by == group_by
    
    def test_invalid_topk(self):
        """Test validation with invalid topk values."""
        # Negative topk
        with pytest.raises(ValidationError):
            ObservabilityMetricsRequest(
                metrics=["request_count"],
                from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
                frequency_unit="day",
                group_by=["model"],
                topk=-1
            )
        
        # Zero topk
        with pytest.raises(ValidationError):
            ObservabilityMetricsRequest(
                metrics=["request_count"],
                from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
                frequency_unit="day",
                group_by=["model"],
                topk=0
            )
    
    def test_topk_requires_group_by(self):
        """Test that topk requires group_by."""
        # topk without group_by should be caught by validator
        with pytest.raises(ValidationError, match="topk requires group_by"):
            ObservabilityMetricsRequest(
                metrics=["request_count"],
                from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
                frequency_unit="day",
                topk=10  # No group_by specified
            )


class TestObservabilityMetricsFilters:
    """Test cases for filters in ObservabilityMetricsRequest."""
    
    def test_valid_filters_single_uuid(self):
        """Test filters with single UUID values."""
        project_id = uuid4()
        model_id = uuid4()
        endpoint_id = uuid4()
        
        request = ObservabilityMetricsRequest(
            metrics=["request_count"],
            from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            frequency_unit="day",
            filters={
                "project": project_id,
                "model": model_id,
                "endpoint": endpoint_id
            }
        )
        
        assert request.filters["project"] == project_id
        assert request.filters["model"] == model_id
        assert request.filters["endpoint"] == endpoint_id
    
    def test_valid_filters_list_of_uuids(self):
        """Test filters with list of UUID values."""
        project_ids = [uuid4() for _ in range(3)]
        model_ids = [uuid4() for _ in range(2)]
        
        request = ObservabilityMetricsRequest(
            metrics=["request_count"],
            from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            frequency_unit="day",
            filters={
                "project": project_ids,
                "model": model_ids
            }
        )
        
        assert request.filters["project"] == project_ids
        assert request.filters["model"] == model_ids
    
    def test_empty_filter_list_invalid(self):
        """Test that empty filter lists are invalid."""
        with pytest.raises(ValidationError, match="filter must not be empty"):
            ObservabilityMetricsRequest(
                metrics=["request_count"],
                from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
                frequency_unit="day",
                filters={"project": []}  # Empty list
            )


class TestPeriodBin:
    """Test cases for PeriodBin schema."""
    
    def test_basic_period_bin(self):
        """Test basic PeriodBin creation."""
        period_bin = PeriodBin(
            time_period=datetime(2024, 1, 1, tzinfo=timezone.utc),
            items=[]
        )
        
        assert period_bin.time_period == datetime(2024, 1, 1, tzinfo=timezone.utc)
        assert period_bin.items == []
    
    def test_period_bin_with_data(self):
        """Test PeriodBin with metrics data."""
        count_metric = CountMetric(count=100)
        success_metric = CountMetric(count=95)
        failure_metric = CountMetric(count=5)
        
        metrics_data = [
            MetricsData(
                data={
                    "request_count": count_metric,
                    "success_request": success_metric,
                    "failure_request": failure_metric
                }
            )
        ]
        
        period_bin = PeriodBin(
            time_period=datetime(2024, 1, 1, tzinfo=timezone.utc),
            items=metrics_data
        )
        
        assert period_bin.time_period == datetime(2024, 1, 1, tzinfo=timezone.utc)
        assert len(period_bin.items) == 1
        assert period_bin.items[0].data["request_count"].count == 100
    
    def test_period_bin_with_group_by_data(self):
        """Test PeriodBin with group by fields."""
        model_id_1 = uuid4()
        model_id_2 = uuid4()
        endpoint_id = uuid4()
        
        count_metric_1 = CountMetric(count=100)
        count_metric_2 = CountMetric(count=50)
        
        metrics_data = [
            MetricsData(
                model_id=model_id_1,
                endpoint_id=endpoint_id,
                data={"request_count": count_metric_1}
            ),
            MetricsData(
                model_id=model_id_2,
                endpoint_id=endpoint_id,
                data={"request_count": count_metric_2}
            )
        ]
        
        period_bin = PeriodBin(
            time_period=datetime(2024, 1, 1, tzinfo=timezone.utc),
            items=metrics_data
        )
        
        assert len(period_bin.items) == 2
        assert period_bin.items[0].model_id == model_id_1
        assert period_bin.items[1].model_id == model_id_2


class TestObservabilityMetricsResponse:
    """Test cases for ObservabilityMetricsResponse schema."""
    
    def test_basic_response(self):
        """Test basic response creation."""
        count_metric_1 = CountMetric(count=100)
        count_metric_2 = CountMetric(count=120)
        
        periods = [
            PeriodBin(
                time_period=datetime(2024, 1, 1, tzinfo=timezone.utc),
                items=[MetricsData(data={"request_count": count_metric_1})]
            ),
            PeriodBin(
                time_period=datetime(2024, 1, 2, tzinfo=timezone.utc),
                items=[MetricsData(data={"request_count": count_metric_2})]
            )
        ]
        
        response = ObservabilityMetricsResponse(items=periods)
        
        assert response.object == "observability_metrics"
        assert len(response.items) == 2
        assert response.items[0].items[0].data["request_count"].count == 100
        assert response.items[1].items[0].data["request_count"].count == 120
    
    def test_empty_response(self):
        """Test empty response."""
        response = ObservabilityMetricsResponse(items=[])
        
        assert response.object == "observability_metrics"
        assert len(response.items) == 0
    
    def test_to_http_response(self):
        """Test to_http_response method."""
        count_metric = CountMetric(count=100)
        periods = [
            PeriodBin(
                time_period=datetime(2024, 1, 1, tzinfo=timezone.utc),
                items=[MetricsData(data={"request_count": count_metric})]
            )
        ]
        
        response = ObservabilityMetricsResponse(items=periods)
        http_response = response.to_http_response()
        
        # to_http_response returns an ORJSONResponse object
        assert hasattr(http_response, 'body')
        assert hasattr(http_response, 'status_code')


class TestInferenceDetailsMetrics:
    """Test cases for InferenceDetailsMetrics schema."""
    
    def test_valid_minimal_inference(self):
        """Test valid minimal inference details."""
        inference_id = uuid4()
        project_id = uuid4()
        endpoint_id = uuid4()
        model_id = uuid4()
        
        data = InferenceDetailsMetrics(
            inference_id=inference_id,
            project_id=project_id,
            endpoint_id=endpoint_id,
            model_id=model_id,
            is_success=True,
            request_arrival_time=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            request_forward_time=datetime(2024, 1, 1, 10, 0, 1, tzinfo=timezone.utc)
        )
        
        assert data.inference_id == inference_id
        assert data.project_id == project_id
        assert data.is_success == True
        assert data.request_arrival_time == datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    
    def test_valid_complete_inference(self):
        """Test valid complete inference details."""
        inference_id = uuid4()
        project_id = uuid4()
        endpoint_id = uuid4()
        model_id = uuid4()
        
        data = InferenceDetailsMetrics(
            inference_id=inference_id,
            project_id=project_id,
            model_id=model_id,
            endpoint_id=endpoint_id,
            cost=0.001234,
            response_analysis={"sentiment": "positive", "confidence": 0.95},
            is_success=True,
            request_arrival_time=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            request_forward_time=datetime(2024, 1, 1, 10, 0, 1, tzinfo=timezone.utc),
            request_ip="192.168.1.1"
        )
        
        assert data.cost == 0.001234
        assert data.response_analysis == {"sentiment": "positive", "confidence": 0.95}
        assert data.request_ip == "192.168.1.1"


class TestMetricTypes:
    """Test cases for specific metric type schemas."""
    
    def test_count_metric(self):
        """Test CountMetric schema."""
        # CountMetric requires count field
        metric = CountMetric(count=100)
        assert metric.count == 100
        assert metric.rate is None
        assert metric.delta is None
        assert metric.delta_percent is None
        
        # Test with all fields
        metric = CountMetric(count=100, rate=2.5, delta=10, delta_percent=11.1)
        assert metric.count == 100
        assert metric.rate == 2.5
        assert metric.delta == 10
        assert metric.delta_percent == 11.1
    
    def test_time_metric(self):
        """Test TimeMetric schema."""
        # TimeMetric requires avg_time_ms field
        metric = TimeMetric(avg_time_ms=123.45)
        assert metric.avg_time_ms == 123.45
        assert metric.delta is None
        assert metric.delta_percent is None
        
        # Test with all fields
        metric = TimeMetric(avg_time_ms=123.45, delta=10.5, delta_percent=-8.5)
        assert metric.avg_time_ms == 123.45
        assert metric.delta == 10.5
        assert metric.delta_percent == -8.5
    
    def test_performance_metric(self):
        """Test PerformanceMetric schema."""
        # PerformanceMetric requires avg field
        metric = PerformanceMetric(avg=50.0)
        assert metric.avg == 50.0
        assert metric.p99 is None
        assert metric.p95 is None
        assert metric.delta is None
        assert metric.delta_percent is None
        
        # Test with all fields
        metric = PerformanceMetric(avg=50.0, p99=98.5, p95=85.0, delta=5, delta_percent=11.1)
        assert metric.avg == 50.0
        assert metric.p99 == 98.5
        assert metric.p95 == 85.0
    
    def test_cache_metric(self):
        """Test CacheMetric schema."""
        # CacheMetric requires hit_rate and hit_count fields
        metric = CacheMetric(hit_rate=0.85, hit_count=850)
        assert metric.hit_rate == 0.85
        assert metric.hit_count == 850
        assert metric.avg_latency_ms is None
        assert metric.delta is None
        assert metric.delta_percent is None
    
    def test_inference_details_validation(self):
        """Test InferenceDetailsMetrics validation."""
        inference_id = uuid4()
        project_id = uuid4()
        endpoint_id = uuid4()
        model_id = uuid4()
        
        # Test invalid IP address
        with pytest.raises(ValidationError, match="Invalid IPv4 address"):
            InferenceDetailsMetrics(
                inference_id=inference_id,
                project_id=project_id,
                endpoint_id=endpoint_id,
                model_id=model_id,
                is_success=True,
                request_arrival_time=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
                request_forward_time=datetime(2024, 1, 1, 10, 0, 1, tzinfo=timezone.utc),
                request_ip="invalid-ip"
            )
        
        # Test negative cost
        with pytest.raises(ValidationError, match="Cost cannot be negative"):
            InferenceDetailsMetrics(
                inference_id=inference_id,
                project_id=project_id,
                endpoint_id=endpoint_id,
                model_id=model_id,
                is_success=True,
                request_arrival_time=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
                request_forward_time=datetime(2024, 1, 1, 10, 0, 1, tzinfo=timezone.utc),
                cost=-0.5
            )
        
        # Test forward time before arrival time
        with pytest.raises(ValidationError, match="request_forward_time cannot be before request_arrival_time"):
            InferenceDetailsMetrics(
                inference_id=inference_id,
                project_id=project_id,
                endpoint_id=endpoint_id,
                model_id=model_id,
                is_success=True,
                request_arrival_time=datetime(2024, 1, 1, 10, 0, 2, tzinfo=timezone.utc),
                request_forward_time=datetime(2024, 1, 1, 10, 0, 1, tzinfo=timezone.utc)
            )