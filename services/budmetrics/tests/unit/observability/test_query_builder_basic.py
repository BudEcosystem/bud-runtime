"""Unit tests for QueryBuilder class - basic query functionality."""

import pytest
from datetime import datetime, timezone
from uuid import UUID, uuid4
from unittest.mock import Mock, patch

from budmetrics.observability.models import QueryBuilder, FrequencyUnit
from budmetrics.observability.schemas import ObservabilityMetricsRequest


class TestQueryBuilderBasic:
    """Test cases for basic QueryBuilder functionality."""

    @pytest.fixture
    def query_builder(self):
        """Fixture for QueryBuilder instance."""
        return QueryBuilder()

    @pytest.fixture
    def sample_project_id(self):
        """Sample project UUID."""
        return uuid4()

    @pytest.fixture
    def sample_model_id(self):
        """Sample model UUID."""
        return uuid4()

    def test_initialization(self, query_builder):
        """Test QueryBuilder initialization."""
        assert query_builder is not None
        assert hasattr(query_builder, 'metric_type')
        assert isinstance(query_builder.metric_type, dict)

        # Check that metric types are mapped
        assert "request_count" in query_builder.metric_type
        assert "success_request" in query_builder.metric_type
        assert "latency" in query_builder.metric_type

    def test_build_query_basic_request_count(self, query_builder, sample_project_id, sample_model_id):
        """Test building a basic request_count query."""
        metrics = ["request_count"]
        from_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        to_date = datetime(2024, 1, 31, tzinfo=timezone.utc)
        frequency_unit = "day"
        frequency_interval = None
        filters = {
            "project": sample_project_id,
            "model": sample_model_id
        }

        query, field_order = query_builder.build_query(
            metrics=metrics,
            from_date=from_date,
            to_date=to_date,
            frequency_unit=frequency_unit,
            frequency_interval=frequency_interval,
            filters=filters,
            group_by=None,
            return_delta=False,
            fill_time_gaps=False,
            topk=None
        )

        # Check query components
        assert "SELECT" in query
        assert "COUNT(mid.inference_id) AS request_count" in query
        assert "FROM ModelInferenceDetails" in query
        assert "WHERE" in query
        assert str(sample_project_id) in query
        assert "GROUP BY time_bucket" in query
        assert "ORDER BY time_bucket" in query

        # Check field order
        assert "time_bucket" in field_order
        assert "request_count" in field_order

    def test_build_query_multiple_metrics(self, query_builder, sample_project_id):
        """Test building query with multiple metrics."""
        metrics = ["request_count", "success_request", "failure_request"]
        filters = {"project": sample_project_id}

        query, field_order = query_builder.build_query(
            metrics=metrics,
            from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            frequency_unit="day",
            frequency_interval=None,
            filters=filters,
            group_by=None,
            return_delta=False,
            fill_time_gaps=False,
            topk=None
        )

        assert "COUNT(mid.inference_id) AS request_count" in query
        assert "SUM(CASE WHEN mid.is_success THEN 1 ELSE 0 END) AS success_request_count" in query
        assert "SUM(CASE WHEN NOT mid.is_success THEN 1 ELSE 0 END) AS failure_request_count" in query

    def test_build_query_with_model_inference_join(self, query_builder, sample_project_id):
        """Test query with metrics requiring ModelInference join."""
        metrics = ["latency", "input_token"]
        filters = {"project": sample_project_id}

        query, field_order = query_builder.build_query(
            metrics=metrics,
            from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            frequency_unit="day",
            frequency_interval=None,
            filters=filters,
            group_by=None,
            return_delta=False,
            fill_time_gaps=False,
            topk=None
        )

        assert "FROM ModelInference mi" in query
        assert "AVG(mi.response_time_ms) AS avg_latency_ms" in query
        assert "SUM(mi.input_tokens) AS input_token_count" in query


    def test_frequency_expressions(self, query_builder, sample_project_id):
        """Test different frequency expressions in queries."""
        frequencies = [
            ("hour", None, "toStartOfHour"),
            ("day", None, "toDate"),
            ("week", None, "toStartOfWeek"),
            ("month", None, "toStartOfMonth"),
            ("quarter", None, "toStartOfQuarter"),
            ("year", None, "toStartOfYear"),
        ]

        for freq_unit, freq_interval, expected_func in frequencies:
            query, _ = query_builder.build_query(
                metrics=["request_count"],
                from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                to_date=datetime(2024, 12, 31, tzinfo=timezone.utc),
                frequency_unit=freq_unit,
                frequency_interval=freq_interval,
                filters={"project": sample_project_id},
                group_by=None,
                return_delta=False,
                fill_time_gaps=False,
                topk=None
            )
            assert expected_func in query

    def test_custom_interval_query(self, query_builder, sample_project_id):
        """Test query with custom interval."""
        query, _ = query_builder.build_query(
            metrics=["request_count"],
            from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            frequency_unit="day",
            frequency_interval=7,  # 7 days
            filters={"project": sample_project_id},
            group_by=None,
            return_delta=False,
            fill_time_gaps=False,
            topk=None
        )

        # Custom interval implementation uses a different approach
        # Check that the query includes the custom interval calculation
        assert "floor((toUnixTimestamp" in query or "toStartOfInterval" in query
        # Check for the interval value - 7 days = 604800 seconds
        assert "604800" in query  # 7 days in seconds

    def test_concurrent_requests_metric(self, query_builder, sample_project_id):
        """Test concurrent_requests metric with special CTE."""
        query, _ = query_builder.build_query(
            metrics=["concurrent_requests"],
            from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            frequency_unit="hour",
            frequency_interval=None,
            filters={"project": sample_project_id},
            group_by=None,
            return_delta=False,
            fill_time_gaps=False,
            topk=None
        )

        # Should have CTE for concurrent requests
        assert "WITH concurrent_counts AS" in query
        # Check for concurrent request calculation logic
        assert "request_arrival_time" in query
        assert "COUNT" in query

    def test_cache_metric_query(self, query_builder, sample_project_id):
        """Test cache metric query."""
        query, _ = query_builder.build_query(
            metrics=["cache"],
            from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
            frequency_unit="day",
            frequency_interval=None,
            filters={"project": sample_project_id},
            group_by=None,
            return_delta=False,
            fill_time_gaps=False,
            topk=None
        )

        # Cache metric uses CASE WHEN for hit rate calculation
        assert "AVG(CASE WHEN mi.cached THEN 1 ELSE 0 END)" in query
        assert "FROM ModelInference" in query

    def test_metric_type_mapping(self, query_builder):
        """Test that all metric types are properly mapped."""
        expected_metrics = [
            "request_count", "success_request", "failure_request",
            "queuing_time", "input_token", "output_token",
            "concurrent_requests", "ttft", "latency", "throughput", "cache"
        ]

        for metric in expected_metrics:
            assert metric in query_builder.metric_type
            assert callable(query_builder.metric_type[metric])

    def test_empty_metrics_handling(self, query_builder, sample_project_id):
        """Test handling of empty metrics list."""
        with pytest.raises(ValueError):
            query_builder.build_query(
                metrics=[],
                from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                to_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
                frequency_unit="day",
                frequency_interval=None,
                filters={"project": sample_project_id},
                group_by=None,
                return_delta=False,
                fill_time_gaps=False,
                topk=None
            )
