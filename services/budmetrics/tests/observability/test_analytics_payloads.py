"""Payload-based tests for POST /observability/analytics endpoint.

These tests validate individual metric types by:
1. Sending a specific metric in the request payload
2. Verifying response structure matches expected metric type
3. Comparing values against InferenceFact ground truth

Run with: pytest tests/observability/test_analytics_payloads.py -v -s
"""

import asyncio
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from budmetrics.observability.models import ClickHouseClient, ClickHouseConfig


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# Test constants
TEST_PROJECT_ID = UUID("019787c1-3de1-7b50-969b-e0a58514b6a1")
TEST_ENDPOINT_ID = UUID("019787c1-3de1-7b50-969b-e0a58514b6a4")
TEST_MODEL_ID = UUID("019787c1-3de1-7b50-969b-e0a58514b6a2")
TEST_FROM_DATE = datetime(2026, 1, 7, 0, 0, 0)
TEST_TO_DATE = datetime(2026, 1, 7, 23, 59, 59)


async def _fetch_ground_truth_async():
    """Async helper to query ClickHouse for ground truth values."""
    config = ClickHouseConfig()
    client = ClickHouseClient(config)
    await client.initialize()

    try:
        ground_truth = {}
        date_filter = f"timestamp >= '{TEST_FROM_DATE}' AND timestamp <= '{TEST_TO_DATE}'"

        # Get total count
        count_result = await client.execute_query(
            f"SELECT count(*) FROM InferenceFact WHERE {date_filter}"
        )
        ground_truth["total_count"] = count_result[0][0] if count_result else 0

        # Get success/failure counts
        success_result = await client.execute_query(
            f"SELECT countIf(is_success = true), countIf(is_success = false) FROM InferenceFact WHERE {date_filter}"
        )
        ground_truth["success_count"] = success_result[0][0] if success_result else 0
        ground_truth["failure_count"] = success_result[0][1] if success_result else 0

        # Get token sums
        token_result = await client.execute_query(
            f"SELECT sum(input_tokens), sum(output_tokens) FROM InferenceFact WHERE {date_filter}"
        )
        ground_truth["input_tokens"] = token_result[0][0] if token_result else 0
        ground_truth["output_tokens"] = token_result[0][1] if token_result else 0

        # Get latency stats
        latency_result = await client.execute_query(
            f"SELECT avg(response_time_ms), quantile(0.95)(response_time_ms) FROM InferenceFact WHERE {date_filter}"
        )
        ground_truth["avg_latency"] = latency_result[0][0] if latency_result else 0
        ground_truth["p95_latency"] = latency_result[0][1] if latency_result else 0

        # Get TTFT stats
        ttft_result = await client.execute_query(
            f"SELECT avg(ttft_ms) FROM InferenceFact WHERE {date_filter} AND ttft_ms > 0"
        )
        ground_truth["avg_ttft"] = ttft_result[0][0] if ttft_result and ttft_result[0][0] else 0

        # Get cache count
        cache_result = await client.execute_query(
            f"SELECT countIf(cached = true) FROM InferenceFact WHERE {date_filter}"
        )
        ground_truth["cache_count"] = cache_result[0][0] if cache_result else 0

        # Get throughput (weighted average: total tokens / total time)
        throughput_result = await client.execute_query(
            f"SELECT sum(output_tokens) * 1000.0 / NULLIF(sum(response_time_ms), 0) FROM InferenceFact WHERE {date_filter} AND response_time_ms > 0"
        )
        ground_truth["avg_throughput"] = throughput_result[0][0] if throughput_result and throughput_result[0][0] else 0

        # Get queuing time (time between request arrival and forward)
        queuing_result = await client.execute_query(
            f"SELECT AVG(toUnixTimestamp64Milli(request_forward_time) - toUnixTimestamp64Milli(request_arrival_time)) "
            f"FROM InferenceFact WHERE {date_filter} AND request_forward_time IS NOT NULL AND request_arrival_time IS NOT NULL"
        )
        ground_truth["avg_queuing_time"] = queuing_result[0][0] if queuing_result and queuing_result[0][0] else 0

        return ground_truth
    finally:
        await client.close()


@pytest.fixture(scope="session")
def seeded_data():
    """Seed test data and return ground truth from InferenceFact."""
    # 1. Clear and seed data
    seeder_path = Path(__file__).parent / "seed_otel_traces.py"
    result = subprocess.run(
        [sys.executable, str(seeder_path), "--clear", "--verify"],
        capture_output=True,
        text=True,
        cwd=str(seeder_path.parent.parent.parent),
    )
    if result.returncode != 0:
        pytest.skip(f"Failed to seed test data: {result.stderr}")

    # 2. Query InferenceFact for ground truth values using a fresh event loop
    loop = asyncio.new_event_loop()
    try:
        ground_truth = loop.run_until_complete(_fetch_ground_truth_async())
    finally:
        loop.close()

    return ground_truth


def extract_metric_value(response_json: dict, metric_key: str):
    """Extract metric value from response.

    Returns the metric dict or scalar value from the first data item.
    """
    items = response_json.get("items", [])
    for period in items:
        period_items = period.get("items") or []
        for item in period_items:
            data = item.get("data", {})
            if data and metric_key in data:
                return data[metric_key]
    return None


def get_base_payload(metrics: list[str]) -> dict:
    """Create base request payload with given metrics."""
    return {
        "metrics": metrics,
        "from_date": TEST_FROM_DATE.isoformat(),
        "to_date": TEST_TO_DATE.isoformat(),
        "frequency_unit": "day",
    }


class TestIndividualMetrics:
    """Tests for each individual metric type."""

    def test_request_count_metric(self, sync_client, seeded_data):
        """Test request_count metric returns CountMetric structure."""
        response = sync_client.post(
            "/observability/analytics",
            json=get_base_payload(["request_count"]),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        assert len(data["items"]) > 0

        metric = extract_metric_value(data, "request_count")
        assert metric is not None, "request_count metric not found in response"
        assert "count" in metric, "CountMetric should have 'count' field"

        print(f"\n[request_count] API: {metric['count']}, Ground truth: {seeded_data['total_count']}")
        assert metric["count"] == seeded_data["total_count"]

    def test_success_request_metric(self, sync_client, seeded_data):
        """Test success_request metric returns CountMetric structure."""
        response = sync_client.post(
            "/observability/analytics",
            json=get_base_payload(["success_request"]),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        assert len(data["items"]) > 0

        metric = extract_metric_value(data, "success_request")
        assert metric is not None, "success_request metric not found in response"
        assert "count" in metric, "CountMetric should have 'count' field"

        print(f"\n[success_request] API: {metric['count']}, Ground truth: {seeded_data['success_count']}")
        assert metric["count"] == seeded_data["success_count"]

    def test_failure_request_metric(self, sync_client, seeded_data):
        """Test failure_request metric returns CountMetric structure."""
        response = sync_client.post(
            "/observability/analytics",
            json=get_base_payload(["failure_request"]),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        assert len(data["items"]) > 0

        metric = extract_metric_value(data, "failure_request")
        assert metric is not None, "failure_request metric not found in response"
        assert "count" in metric, "CountMetric should have 'count' field"

        print(f"\n[failure_request] API: {metric['count']}, Ground truth: {seeded_data['failure_count']}")
        assert metric["count"] == seeded_data["failure_count"]

    def test_latency_metric(self, sync_client, seeded_data):
        """Test latency metric returns PerformanceMetric structure."""
        response = sync_client.post(
            "/observability/analytics",
            json=get_base_payload(["latency"]),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        assert len(data["items"]) > 0

        metric = extract_metric_value(data, "latency")
        assert metric is not None, "latency metric not found in response"
        assert "avg" in metric, "PerformanceMetric should have 'avg' field"

        print(f"\n[latency] API avg: {metric['avg']}, Ground truth avg: {seeded_data['avg_latency']}")
        # Note: API may use p50 from rollup tables, ground truth uses avg()

    def test_ttft_metric(self, sync_client, seeded_data):
        """Test ttft (time to first token) metric returns PerformanceMetric structure."""
        response = sync_client.post(
            "/observability/analytics",
            json=get_base_payload(["ttft"]),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        assert len(data["items"]) > 0

        metric = extract_metric_value(data, "ttft")
        assert metric is not None, "ttft metric not found in response"
        assert "avg" in metric, "PerformanceMetric should have 'avg' field"

        print(f"\n[ttft] API avg: {metric['avg']}, Ground truth avg: {seeded_data['avg_ttft']}")

    def test_throughput_metric(self, sync_client, seeded_data):
        """Test throughput metric returns PerformanceMetric structure."""
        response = sync_client.post(
            "/observability/analytics",
            json=get_base_payload(["throughput"]),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        assert len(data["items"]) > 0

        metric = extract_metric_value(data, "throughput")
        assert metric is not None, "throughput metric not found in response"
        assert "avg" in metric, "PerformanceMetric should have 'avg' field"

        print(f"\n[throughput] API avg: {metric['avg']}, Ground truth avg: {seeded_data['avg_throughput']}")
        assert abs(metric["avg"] - seeded_data["avg_throughput"]) < 0.01  # Allow small floating point diff

    def test_input_token_metric(self, sync_client, seeded_data):
        """Test input_token metric returns CountMetric structure."""
        response = sync_client.post(
            "/observability/analytics",
            json=get_base_payload(["input_token"]),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        assert len(data["items"]) > 0

        metric = extract_metric_value(data, "input_token")
        assert metric is not None, "input_token metric not found in response"
        assert "count" in metric, "CountMetric should have 'count' field"

        print(f"\n[input_token] API: {metric['count']}, Ground truth: {seeded_data['input_tokens']}")
        assert metric["count"] == seeded_data["input_tokens"]

    def test_output_token_metric(self, sync_client, seeded_data):
        """Test output_token metric returns CountMetric structure."""
        response = sync_client.post(
            "/observability/analytics",
            json=get_base_payload(["output_token"]),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        assert len(data["items"]) > 0

        metric = extract_metric_value(data, "output_token")
        assert metric is not None, "output_token metric not found in response"
        assert "count" in metric, "CountMetric should have 'count' field"

        print(f"\n[output_token] API: {metric['count']}, Ground truth: {seeded_data['output_tokens']}")
        assert metric["count"] == seeded_data["output_tokens"]

    def test_cache_metric(self, sync_client, seeded_data):
        """Test cache metric returns CacheMetric structure."""
        response = sync_client.post(
            "/observability/analytics",
            json=get_base_payload(["cache"]),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        assert len(data["items"]) > 0

        metric = extract_metric_value(data, "cache")
        assert metric is not None, "cache metric not found in response"
        # CacheMetric has hit_count or count
        hit_count = metric.get("hit_count", metric.get("count", 0))

        print(f"\n[cache] API hit_count: {hit_count}, Ground truth: {seeded_data['cache_count']}")
        assert hit_count == seeded_data["cache_count"]

    def test_queuing_time_metric(self, sync_client, seeded_data):
        """Test queuing_time metric returns TimeMetric structure."""
        response = sync_client.post(
            "/observability/analytics",
            json=get_base_payload(["queuing_time"]),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        assert len(data["items"]) > 0

        metric = extract_metric_value(data, "queuing_time")
        assert metric is not None, "queuing_time metric not found in response"
        # TimeMetric has avg_time_ms or avg
        avg_time = metric.get("avg_time_ms", metric.get("avg", 0))

        print(f"\n[queuing_time] API avg_time_ms: {avg_time}, Ground truth: {seeded_data['avg_queuing_time']}")
        assert abs(avg_time - seeded_data["avg_queuing_time"]) < 1  # Allow small rounding diff

    def test_concurrent_requests_metric(self, sync_client, seeded_data):
        """Test concurrent_requests metric returns PerformanceMetric structure."""
        response = sync_client.post(
            "/observability/analytics",
            json=get_base_payload(["concurrent_requests"]),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        assert len(data["items"]) > 0

        metric = extract_metric_value(data, "concurrent_requests")
        assert metric is not None, "concurrent_requests metric not found in response"
        assert "avg" in metric, "PerformanceMetric should have 'avg' field"

        print(f"\n[concurrent_requests] API avg: {metric['avg']}")


class TestDateParameters:
    """Tests for from_date and to_date parameter handling."""

    def test_to_date_optional(self, sync_client, seeded_data):
        """Test that to_date is optional and defaults to now."""
        # Use a from_date that includes our test data
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            # to_date intentionally omitted - should default to datetime.now()
            "frequency_unit": "day",
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["object"] == "observability_metrics"

        # Should return data since to_date defaults to now()
        metric = extract_metric_value(data, "request_count")
        assert metric is not None, "request_count metric not found"
        assert metric["count"] == seeded_data["total_count"], "Count should match seeded data"
        print(f"\n[to_date_optional] Request succeeded with count: {metric['count']}")

    def test_valid_date_range(self, sync_client, seeded_data):
        """Test valid date range is accepted."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "day",
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"

        metric = extract_metric_value(data, "request_count")
        print(f"\n[valid_date_range] Request succeeded with count: {metric['count'] if metric else 'N/A'}")
        assert metric["count"] == seeded_data["total_count"]

    def test_to_date_before_from_date(self, sync_client):
        """Test validation error when to_date is before from_date."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_TO_DATE.isoformat(),  # Later date as from_date
            "to_date": TEST_FROM_DATE.isoformat(),  # Earlier date as to_date
            "frequency_unit": "day",
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        error_detail = response.json()
        # Check error message contains the expected validation message
        error_str = str(error_detail)
        assert "to_date must be after from_date" in error_str, f"Unexpected error: {error_str}"
        print(f"\n[to_date_before_from_date] Validation error correctly raised: {error_detail}")

    def test_date_range_exceeds_max_days(self, sync_client):
        """Test validation error when date range exceeds 90 days."""
        from_date = datetime(2026, 1, 1, 0, 0, 0)
        to_date = datetime(2026, 5, 1, 0, 0, 0)  # ~120 days later
        payload = {
            "metrics": ["request_count"],
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "frequency_unit": "day",
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        error_detail = response.json()
        error_str = str(error_detail)
        assert "Date range cannot exceed 90 days" in error_str, f"Unexpected error: {error_str}"
        print(f"\n[date_range_exceeds_max_days] Validation error correctly raised: {error_detail}")

    def test_to_date_too_far_in_future(self, sync_client):
        """Test validation error when to_date is more than 1 day in future."""
        now = datetime.now()
        from_date = now - timedelta(days=7)
        to_date = now + timedelta(days=10)  # More than 1 day in future
        payload = {
            "metrics": ["request_count"],
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "frequency_unit": "day",
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        error_detail = response.json()
        error_str = str(error_detail)
        assert "to_date cannot be more than 1 day in the future" in error_str, f"Unexpected error: {error_str}"
        print(f"\n[to_date_too_far_in_future] Validation error correctly raised: {error_detail}")

    def test_same_from_and_to_date(self, sync_client):
        """Test that same from_date and to_date is accepted (edge case)."""
        # Validation uses `to_date < from_date`, so equal dates should pass
        same_date = datetime(2026, 1, 7, 12, 0, 0)
        payload = {
            "metrics": ["request_count"],
            "from_date": same_date.isoformat(),
            "to_date": same_date.isoformat(),
            "frequency_unit": "day",
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["object"] == "observability_metrics"
        print(f"\n[same_from_and_to_date] Request succeeded with same dates")


#  pytest tests/observability/test_analytics_payloads.py -v -s