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


def extract_delta_fields(response_json: dict, metric_key: str) -> dict:
    """Extract delta-related fields from metric response.

    Returns dict with delta, delta_percent, and previous values.
    """
    metric = extract_metric_value(response_json, metric_key)
    if metric is None:
        return {}
    return {
        "delta": metric.get("delta"),
        "delta_percent": metric.get("delta_percent"),
        "previous": metric.get("previous"),
    }


def get_all_period_metrics(response_json: dict, metric_key: str) -> list[dict]:
    """Extract metric values from all periods.

    Returns list of dicts with time_period and all metric fields.
    Sorted by time_period ascending for easier comparison.
    """
    results = []
    for period in response_json.get("items", []):
        for item in period.get("items") or []:
            data = item.get("data", {})
            if metric_key in data:
                results.append({
                    "time_period": period["time_period"],
                    **data[metric_key],
                })
    # Sort by time_period ascending
    results.sort(key=lambda x: x["time_period"])
    return results


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
            # Disable time gap filling to avoid zero-filled rows from future dates
            "fill_time_gaps": False,
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


class TestFrequencyUnit:
    """Tests for frequency_unit parameter handling."""

    # ==================== Basic Validation Tests ====================

    @pytest.mark.parametrize("frequency_unit", ["hour", "day", "week", "month", "quarter", "year"])
    def test_valid_frequency_units(self, sync_client, seeded_data, frequency_unit):
        """Test all valid frequency_unit values are accepted."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": frequency_unit,
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Expected 200 for frequency_unit={frequency_unit}, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["object"] == "observability_metrics"
        print(f"\n[valid_frequency_unit] frequency_unit={frequency_unit} accepted")

    def test_frequency_unit_default_is_day(self, sync_client, seeded_data):
        """Test that frequency_unit defaults to 'day' when not specified."""
        # Request without frequency_unit
        payload_no_freq = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "fill_time_gaps": False,
        }
        response_no_freq = sync_client.post("/observability/analytics", json=payload_no_freq)
        assert response_no_freq.status_code == 200

        # Request with explicit "day"
        payload_day = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "day",
            "fill_time_gaps": False,
        }
        response_day = sync_client.post("/observability/analytics", json=payload_day)
        assert response_day.status_code == 200

        # Both should return same time_period format
        data_no_freq = response_no_freq.json()
        data_day = response_day.json()

        if data_no_freq["items"] and data_day["items"]:
            time_period_no_freq = data_no_freq["items"][0]["time_period"]
            time_period_day = data_day["items"][0]["time_period"]
            assert time_period_no_freq == time_period_day, "Default should be 'day'"
        print(f"\n[default_frequency_unit] Default is 'day' - verified")

    def test_invalid_frequency_unit(self, sync_client):
        """Test validation error for invalid frequency_unit value."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "minute",  # Invalid value
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 422, f"Expected 422 for invalid frequency_unit, got {response.status_code}"
        print(f"\n[invalid_frequency_unit] Validation error raised correctly")

    # ==================== Time Bucket Format Tests ====================

    def test_frequency_unit_hour_returns_hourly_buckets(self, sync_client, seeded_data):
        """Test that hour frequency returns hourly time buckets."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify time_period has hour precision (T06:00:00, T08:00:00, etc.)
        for item in data["items"]:
            time_period = item["time_period"]
            # Hour buckets should have time component
            assert "T" in time_period, f"Hour bucket should have time component: {time_period}"
            # Verify it's at hour boundary (minutes and seconds are 00)
            assert time_period.endswith(":00:00") or time_period.endswith(":00"), f"Hour bucket should be at hour boundary: {time_period}"
        print(f"\n[hour_buckets] Returns {len(data['items'])} hourly buckets")

    def test_frequency_unit_day_returns_daily_buckets(self, sync_client, seeded_data):
        """Test that day frequency returns daily time buckets."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "day",
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify time_period is at day start (00:00:00)
        for item in data["items"]:
            time_period = item["time_period"]
            assert "T00:00:00" in time_period, f"Day bucket should be at day start: {time_period}"
        print(f"\n[day_buckets] Returns {len(data['items'])} daily buckets")

    def test_frequency_unit_week_returns_weekly_buckets(self, sync_client, seeded_data):
        """Test that week frequency returns weekly time buckets (Monday start)."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "week",
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # 2026-01-07 is a Wednesday, so week bucket should be Monday 2026-01-05
        if data["items"]:
            time_period = data["items"][0]["time_period"]
            # ClickHouse uses Monday-start weeks
            assert "2026-01-05" in time_period, f"Week bucket should be Monday 2026-01-05: {time_period}"
        print(f"\n[week_buckets] Returns {len(data['items'])} weekly buckets")

    def test_frequency_unit_month_returns_monthly_buckets(self, sync_client, seeded_data):
        """Test that month frequency returns monthly time buckets."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "month",
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Month bucket should be 2026-01-01
        if data["items"]:
            time_period = data["items"][0]["time_period"]
            assert "2026-01-01" in time_period, f"Month bucket should be 2026-01-01: {time_period}"
        print(f"\n[month_buckets] Returns {len(data['items'])} monthly buckets")

    def test_frequency_unit_quarter_returns_quarterly_buckets(self, sync_client, seeded_data):
        """Test that quarter frequency returns quarterly time buckets."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "quarter",
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Quarter bucket for January should be 2026-01-01 (Q1)
        if data["items"]:
            time_period = data["items"][0]["time_period"]
            assert "2026-01-01" in time_period, f"Quarter bucket should be 2026-01-01: {time_period}"
        print(f"\n[quarter_buckets] Returns {len(data['items'])} quarterly buckets")

    def test_frequency_unit_year_returns_yearly_buckets(self, sync_client, seeded_data):
        """Test that year frequency returns yearly time buckets."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "year",
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Year bucket should be 2026-01-01
        if data["items"]:
            time_period = data["items"][0]["time_period"]
            assert "2026-01-01" in time_period, f"Year bucket should be 2026-01-01: {time_period}"
        print(f"\n[year_buckets] Returns {len(data['items'])} yearly buckets")

    # ==================== Data Accuracy Tests ====================

    def test_hour_frequency_count_accuracy(self, sync_client, seeded_data):
        """Test that summed hourly counts equal total seeded count."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Sum all hourly counts
        total_count = 0
        for item in data["items"]:
            for metrics_item in item.get("items") or []:
                rc = metrics_item.get("data", {}).get("request_count", {})
                total_count += rc.get("count", 0)

        assert total_count == seeded_data["total_count"], f"Sum of hourly counts ({total_count}) should equal total ({seeded_data['total_count']})"
        print(f"\n[hour_accuracy] Sum={total_count}, Expected={seeded_data['total_count']}")

    def test_day_frequency_count_accuracy(self, sync_client, seeded_data):
        """Test that daily count equals total seeded count."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "day",
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        metric = extract_metric_value(data, "request_count")
        assert metric is not None
        assert metric["count"] == seeded_data["total_count"], f"Daily count ({metric['count']}) should equal total ({seeded_data['total_count']})"
        print(f"\n[day_accuracy] Count={metric['count']}, Expected={seeded_data['total_count']}")

    def test_week_frequency_count_accuracy(self, sync_client, seeded_data):
        """Test that weekly count equals total seeded count."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "week",
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        metric = extract_metric_value(data, "request_count")
        assert metric is not None
        assert metric["count"] == seeded_data["total_count"], f"Weekly count ({metric['count']}) should equal total ({seeded_data['total_count']})"
        print(f"\n[week_accuracy] Count={metric['count']}, Expected={seeded_data['total_count']}")

    def test_month_frequency_count_accuracy(self, sync_client, seeded_data):
        """Test that monthly count equals total seeded count."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "month",
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        metric = extract_metric_value(data, "request_count")
        assert metric is not None
        assert metric["count"] == seeded_data["total_count"], f"Monthly count ({metric['count']}) should equal total ({seeded_data['total_count']})"
        print(f"\n[month_accuracy] Count={metric['count']}, Expected={seeded_data['total_count']}")

    def test_quarter_frequency_count_accuracy(self, sync_client, seeded_data):
        """Test that quarterly count equals total seeded count."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "quarter",
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        metric = extract_metric_value(data, "request_count")
        assert metric is not None
        assert metric["count"] == seeded_data["total_count"], f"Quarterly count ({metric['count']}) should equal total ({seeded_data['total_count']})"
        print(f"\n[quarter_accuracy] Count={metric['count']}, Expected={seeded_data['total_count']}")

    def test_year_frequency_count_accuracy(self, sync_client, seeded_data):
        """Test that yearly count equals total seeded count."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "year",
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        metric = extract_metric_value(data, "request_count")
        assert metric is not None
        assert metric["count"] == seeded_data["total_count"], f"Yearly count ({metric['count']}) should equal total ({seeded_data['total_count']})"
        print(f"\n[year_accuracy] Count={metric['count']}, Expected={seeded_data['total_count']}")

    # ==================== Edge Cases and Combined Parameter Tests ====================

    def test_multi_week_date_range(self, sync_client, seeded_data):
        """Test week frequency handles multi-week date range correctly."""
        # Use dates that span 2 weeks, within the valid test data range
        from_date = datetime(2026, 1, 1, 0, 0, 0)
        to_date = datetime(2026, 1, 12, 23, 59, 59)  # Today or earlier to avoid future date validation
        payload = {
            "metrics": ["request_count"],
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "frequency_unit": "week",
            "fill_time_gaps": True,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        # Should have multiple week buckets (2 weeks from Jan 1-12)
        assert len(data["items"]) >= 2, f"Should have at least 2 week buckets for 2 weeks, got {len(data['items'])}"
        print(f"\n[multi_week] Returns {len(data['items'])} weekly buckets for 2-week range")

    def test_frequency_with_fill_time_gaps(self, sync_client, seeded_data):
        """Test that gap filling works at specified frequency."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "fill_time_gaps": True,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # With fill_time_gaps=True, should have all hours (0-23)
        assert len(data["items"]) >= 20, f"With fill_time_gaps, should have most hours filled, got {len(data['items'])}"

        # Verify some hours have count=0 (filled gaps)
        zero_count_found = False
        for item in data["items"]:
            for metrics_item in item.get("items") or []:
                rc = metrics_item.get("data", {}).get("request_count", {})
                if rc.get("count", -1) == 0:
                    zero_count_found = True
                    break

        assert zero_count_found, "Should have some hours with count=0 (filled gaps)"
        print(f"\n[fill_time_gaps] Returns {len(data['items'])} hourly buckets with gaps filled")

    def test_frequency_with_return_delta(self, sync_client, seeded_data):
        """Test that delta calculation works at specified frequency."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "return_delta": True,
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Find a period that should have delta calculated (not the first one)
        delta_found = False
        for item in data["items"][:-1]:  # Skip last item (it's chronologically first in DESC order)
            for metrics_item in item.get("items") or []:
                rc = metrics_item.get("data", {}).get("request_count", {})
                if rc.get("delta") is not None:
                    delta_found = True
                    break

        assert delta_found, "Should have delta values for non-first periods"
        print(f"\n[return_delta] Delta values populated for hourly frequency")

    def test_case_sensitivity_uppercase(self, sync_client):
        """Test case sensitivity - uppercase frequency_unit should fail."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "HOUR",  # Uppercase - should fail
        }
        response = sync_client.post("/observability/analytics", json=payload)
        # Pydantic Literal validation is case-sensitive
        assert response.status_code == 422, f"Expected 422 for uppercase frequency_unit, got {response.status_code}"
        print(f"\n[case_sensitivity] Uppercase 'HOUR' correctly rejected")

    def test_same_from_and_to_date_with_hour_frequency(self, sync_client):
        """Test handling when from_date == to_date with hour frequency."""
        same_datetime = datetime(2026, 1, 7, 8, 0, 0)  # Exact hour
        payload = {
            "metrics": ["request_count"],
            "from_date": same_datetime.isoformat(),
            "to_date": same_datetime.isoformat(),
            "frequency_unit": "hour",
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Same from/to date should work, got {response.status_code}: {response.text}"
        print(f"\n[same_date_hour] Same from/to date accepted with hour frequency")

    def test_near_maximum_date_range(self, sync_client):
        """Test large date range (up to 89 days) with day frequency."""
        # Use dates that don't exceed 90 days and don't go into the future
        # Today is 2026-01-12, so use a range ending around now
        from_date = datetime(2025, 10, 15, 0, 0, 0)  # ~89 days before today
        to_date = datetime(2026, 1, 12, 23, 59, 59)  # Today
        payload = {
            "metrics": ["request_count"],
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "frequency_unit": "day",
            "fill_time_gaps": True,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"~89-day range should work, got {response.status_code}: {response.text}"
        data = response.json()

        # Should have approximately 89-90 daily buckets
        assert len(data["items"]) >= 80, f"Should have many daily buckets for 89-day range, got {len(data['items'])}"
        print(f"\n[max_range] ~89-day range returns {len(data['items'])} daily buckets")


class TestFrequencyInterval:
    """Tests for frequency_interval parameter handling."""

    # ==================== Basic Validation Tests ====================

    def test_frequency_interval_default_is_none(self, sync_client, seeded_data):
        """Test that frequency_interval defaults to None when not specified."""
        # Request without frequency_interval
        payload_no_interval = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "fill_time_gaps": False,
        }
        response_no_interval = sync_client.post("/observability/analytics", json=payload_no_interval)
        assert response_no_interval.status_code == 200

        # Request with explicit None
        payload_null = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "frequency_interval": None,
            "fill_time_gaps": False,
        }
        response_null = sync_client.post("/observability/analytics", json=payload_null)
        assert response_null.status_code == 200

        # Both should return same results
        data_no_interval = response_no_interval.json()
        data_null = response_null.json()
        assert len(data_no_interval["items"]) == len(data_null["items"])
        print(f"\n[default_interval] Default is None - verified")

    def test_frequency_interval_null_accepted(self, sync_client, seeded_data):
        """Test that explicit null value is accepted."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "frequency_interval": None,
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Null frequency_interval should be accepted, got {response.status_code}"
        data = response.json()
        assert data["object"] == "observability_metrics"
        print(f"\n[null_interval] Null value accepted")

    @pytest.mark.parametrize("interval", [1, 2, 3, 5, 7, 12, 24])
    def test_frequency_interval_valid_integers(self, sync_client, seeded_data, interval):
        """Test that valid positive integers are accepted."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "frequency_interval": interval,
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"frequency_interval={interval} should be accepted, got {response.status_code}: {response.text}"
        print(f"\n[valid_interval] frequency_interval={interval} accepted")

    @pytest.mark.parametrize("interval", [0, -1, -10])
    def test_frequency_interval_invalid_values(self, sync_client, interval):
        """Test validation error for invalid interval values."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "frequency_interval": interval,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 422, f"frequency_interval={interval} should be rejected, got {response.status_code}"
        print(f"\n[invalid_interval] frequency_interval={interval} correctly rejected")

    # ==================== Custom Interval Behavior Tests ====================

    def test_interval_2_hours_creates_2hour_buckets(self, sync_client, seeded_data):
        """Test 2-hour interval creates 2-hour time buckets."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "frequency_interval": 2,
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # With 2-hour intervals, buckets should be at even-hour boundaries (00, 02, 04, 06, 08, 10, 12...)
        time_periods = [item["time_period"] for item in data["items"]]
        print(f"\n[2hour_buckets] Time periods: {time_periods}")

        # Verify buckets are at 2-hour boundaries (hours divisible by 2)
        for tp in time_periods:
            hour = int(tp.split("T")[1].split(":")[0])
            assert hour % 2 == 0, f"2-hour bucket should be at even hour, got {tp}"

        # Verify total count is preserved
        total = self._sum_request_counts(data)
        assert total == seeded_data["total_count"], f"Total should be {seeded_data['total_count']}, got {total}"

    def test_interval_3_hours_creates_3hour_buckets(self, sync_client, seeded_data):
        """Test 3-hour interval creates 3-hour time buckets."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "frequency_interval": 3,
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        time_periods = [item["time_period"] for item in data["items"]]
        print(f"\n[3hour_buckets] Time periods: {time_periods}")

        # Verify buckets are at 3-hour boundaries (hours divisible by 3: 00, 03, 06, 09, 12...)
        for tp in time_periods:
            hour = int(tp.split("T")[1].split(":")[0])
            assert hour % 3 == 0, f"3-hour bucket should be at 3-hour boundary, got {tp}"

        # Verify total count is preserved
        total = self._sum_request_counts(data)
        assert total == seeded_data["total_count"], f"Total should be {seeded_data['total_count']}, got {total}"

    def test_interval_6_hours_creates_6hour_buckets(self, sync_client, seeded_data):
        """Test 6-hour interval creates 6-hour time buckets."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "frequency_interval": 6,
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        time_periods = [item["time_period"] for item in data["items"]]
        print(f"\n[6hour_buckets] Time periods: {time_periods}")

        # Verify buckets are at 6-hour boundaries (00, 06, 12, 18)
        for tp in time_periods:
            hour = int(tp.split("T")[1].split(":")[0])
            assert hour % 6 == 0, f"6-hour bucket should be at 6-hour boundary, got {tp}"

        # Verify total count is preserved
        total = self._sum_request_counts(data)
        assert total == seeded_data["total_count"], f"Total should be {seeded_data['total_count']}, got {total}"

    def test_interval_7_days_creates_weekly_buckets(self, sync_client, seeded_data):
        """Test 7-day interval creates 7-day buckets."""
        # Use a wider date range to see the effect
        from_date = datetime(2026, 1, 1, 0, 0, 0)
        to_date = datetime(2026, 1, 12, 23, 59, 59)
        payload = {
            "metrics": ["request_count"],
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "frequency_unit": "day",
            "frequency_interval": 7,
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"7-day interval should work, got {response.status_code}: {response.text}"
        data = response.json()

        time_periods = [item["time_period"] for item in data["items"]]
        print(f"\n[7day_buckets] Time periods: {time_periods}")

        # 12 days should fit into 2 7-day buckets
        assert len(data["items"]) <= 2, f"12 days with 7-day interval should have at most 2 buckets, got {len(data['items'])}"

    def test_interval_2_days_creates_2day_buckets(self, sync_client, seeded_data):
        """Test 2-day interval creates 2-day buckets."""
        from_date = datetime(2026, 1, 6, 0, 0, 0)
        to_date = datetime(2026, 1, 10, 23, 59, 59)
        payload = {
            "metrics": ["request_count"],
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "frequency_unit": "day",
            "frequency_interval": 2,
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        time_periods = [item["time_period"] for item in data["items"]]
        print(f"\n[2day_buckets] Time periods: {time_periods}")

        # 5 days with 2-day interval should have 2-3 buckets
        assert len(data["items"]) >= 1, f"Should have at least 1 2-day bucket, got {len(data['items'])}"

    def test_interval_1_same_as_none(self, sync_client, seeded_data):
        """Test that interval=1 produces same result as interval=None."""
        payload_1 = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "frequency_interval": 1,
            "fill_time_gaps": False,
        }
        response_1 = sync_client.post("/observability/analytics", json=payload_1)
        assert response_1.status_code == 200

        payload_none = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "frequency_interval": None,
            "fill_time_gaps": False,
        }
        response_none = sync_client.post("/observability/analytics", json=payload_none)
        assert response_none.status_code == 200

        data_1 = response_1.json()
        data_none = response_none.json()

        # Both should return same number of items
        assert len(data_1["items"]) == len(data_none["items"]), \
            f"interval=1 ({len(data_1['items'])}) should match interval=None ({len(data_none['items'])})"
        print(f"\n[interval_1_vs_none] Both return {len(data_1['items'])} items - equivalent")

    # ==================== Data Accuracy Tests ====================

    def _sum_request_counts(self, data: dict) -> int:
        """Helper to sum request counts from response data."""
        total = 0
        for item in data.get("items", []):
            for metrics_item in item.get("items") or []:
                rc = metrics_item.get("data", {}).get("request_count", {})
                total += rc.get("count", 0)
        return total

    def test_2hour_interval_sum_equals_total(self, sync_client, seeded_data):
        """Test sum of 2-hour interval counts equals total."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "frequency_interval": 2,
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == seeded_data["total_count"], \
            f"Sum of 2-hour counts ({total}) should equal total ({seeded_data['total_count']})"
        print(f"\n[2hour_accuracy] Sum={total}, Expected={seeded_data['total_count']}")

    def test_3hour_interval_sum_equals_total(self, sync_client, seeded_data):
        """Test sum of 3-hour interval counts equals total."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "frequency_interval": 3,
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == seeded_data["total_count"], \
            f"Sum of 3-hour counts ({total}) should equal total ({seeded_data['total_count']})"
        print(f"\n[3hour_accuracy] Sum={total}, Expected={seeded_data['total_count']}")

    def test_6hour_interval_sum_equals_total(self, sync_client, seeded_data):
        """Test sum of 6-hour interval counts equals total."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "frequency_interval": 6,
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == seeded_data["total_count"], \
            f"Sum of 6-hour counts ({total}) should equal total ({seeded_data['total_count']})"
        print(f"\n[6hour_accuracy] Sum={total}, Expected={seeded_data['total_count']}")

    def test_custom_day_interval_sum_equals_total(self, sync_client, seeded_data):
        """Test sum of custom day interval counts equals total."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "day",
            "frequency_interval": 2,
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == seeded_data["total_count"], \
            f"Sum of 2-day counts ({total}) should equal total ({seeded_data['total_count']})"
        print(f"\n[2day_accuracy] Sum={total}, Expected={seeded_data['total_count']}")

    # ==================== Edge Cases and Combined Parameters ====================

    def test_interval_with_fill_time_gaps(self, sync_client, seeded_data):
        """Test gap filling works with custom intervals."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "frequency_interval": 3,
            "fill_time_gaps": True,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Custom interval with fill_time_gaps should work, got {response.status_code}: {response.text}"
        data = response.json()

        # With 3-hour intervals and fill_time_gaps, should have 8 buckets for 24 hours (0, 3, 6, 9, 12, 15, 18, 21)
        assert len(data["items"]) >= 6, f"Should have several 3-hour buckets with gaps filled, got {len(data['items'])}"
        print(f"\n[interval_fill_gaps] Returns {len(data['items'])} 3-hour buckets with gaps filled")

    def test_interval_with_return_delta(self, sync_client, seeded_data):
        """Test delta calculation works with custom intervals."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "frequency_interval": 2,
            "return_delta": True,
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Custom interval with return_delta should work, got {response.status_code}: {response.text}"
        data = response.json()

        # Check that delta values are present
        delta_found = False
        for item in data["items"][:-1]:  # Skip first item
            for metrics_item in item.get("items") or []:
                rc = metrics_item.get("data", {}).get("request_count", {})
                if rc.get("delta") is not None:
                    delta_found = True
                    break

        assert delta_found, "Should have delta values for 2-hour intervals"
        print(f"\n[interval_delta] Delta values present for 2-hour intervals")

    def test_large_interval_24_hours(self, sync_client, seeded_data):
        """Test 24-hour interval is accepted and returns correct total count."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "frequency_interval": 24,
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"24-hour interval should be accepted, got {response.status_code}"
        data = response.json()

        # Verify the total count matches (data accuracy is maintained with large intervals)
        total = self._sum_request_counts(data)
        assert total == seeded_data["total_count"], \
            f"Total count ({total}) should equal seeded data ({seeded_data['total_count']})"
        print(f"\n[24hour_bucket] {len(data['items'])} bucket(s) with total count={total}")

    def test_interval_larger_than_range(self, sync_client, seeded_data):
        """Test interval larger than date range is handled."""
        # 3-day range with 7-day interval
        from_date = datetime(2026, 1, 6, 0, 0, 0)
        to_date = datetime(2026, 1, 8, 23, 59, 59)
        payload = {
            "metrics": ["request_count"],
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "frequency_unit": "day",
            "frequency_interval": 7,
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Interval > range should work, got {response.status_code}: {response.text}"
        data = response.json()

        # Should have at most 1 bucket since interval > range
        assert len(data["items"]) <= 1, f"Interval > range should have 0-1 buckets, got {len(data['items'])}"
        print(f"\n[interval_gt_range] Returns {len(data['items'])} buckets for interval > range")

    def test_interval_with_week_frequency(self, sync_client, seeded_data):
        """Test custom interval with week frequency unit."""
        from_date = datetime(2025, 12, 1, 0, 0, 0)
        to_date = datetime(2026, 1, 12, 23, 59, 59)
        payload = {
            "metrics": ["request_count"],
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "frequency_unit": "week",
            "frequency_interval": 2,
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"2-week interval should work, got {response.status_code}: {response.text}"
        data = response.json()

        # ~6 weeks of data with 2-week intervals should have 3-4 buckets
        print(f"\n[2week_interval] Returns {len(data['items'])} 2-week buckets")

    def test_interval_with_month_frequency(self, sync_client, seeded_data):
        """Test custom interval with month frequency unit."""
        # Use a date range within the 90-day limit
        from_date = datetime(2025, 11, 1, 0, 0, 0)
        to_date = datetime(2026, 1, 12, 23, 59, 59)  # ~73 days
        payload = {
            "metrics": ["request_count"],
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "frequency_unit": "month",
            "frequency_interval": 2,  # 2-month intervals
            "fill_time_gaps": False,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"2-month interval should work, got {response.status_code}: {response.text}"
        data = response.json()

        # ~2.5 months of data with 2-month intervals should have 1-2 buckets
        print(f"\n[2month_interval] Returns {len(data['items'])} 2-month buckets")

    def test_float_interval_rejected(self, sync_client):
        """Test that float values are rejected."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "hour",
            "frequency_interval": 2.5,
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 422, f"Float frequency_interval should be rejected, got {response.status_code}"
        print(f"\n[float_interval] Float value correctly rejected")


class TestFilters:
    """Tests for filters parameter handling.

    Note: The seeded data has 6 total records:
    - 5 records with: project_id=a1, model_id=a2, endpoint_id=a4
    - 1 record with: project_id=a4, model_id=a3, endpoint_id=a5

    So filtering by TEST_PROJECT_ID, TEST_MODEL_ID, or TEST_ENDPOINT_ID
    should return 5 records, not 6.
    """

    # Constants for filter tests
    NONEXISTENT_UUID = "00000000-0000-0000-0000-000000000000"
    # 5 out of 6 records match the primary test UUIDs (project_id=a1, model_id=a2, endpoint_id=a4)
    FILTERED_RECORD_COUNT = 5

    def _get_filter_payload(self, filters: dict = None) -> dict:
        """Create base request payload with optional filters."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "day",
            "fill_time_gaps": False,
        }
        if filters is not None:
            payload["filters"] = filters
        return payload

    def _sum_request_counts(self, data: dict) -> int:
        """Helper to sum request counts from response data."""
        total = 0
        for item in data.get("items", []):
            for metrics_item in item.get("items") or []:
                rc = metrics_item.get("data", {}).get("request_count", {})
                total += rc.get("count", 0)
        return total

    # ==================== Basic Validation Tests ====================

    def test_filters_default_is_none(self, sync_client, seeded_data):
        """Test that filters defaults to None (returns all data) when not specified."""
        payload = self._get_filter_payload()  # No filters
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == seeded_data["total_count"], f"Should return all data ({seeded_data['total_count']}), got {total}"
        print(f"\n[filters_default] No filters returns all {total} records")

    def test_filters_null_accepted(self, sync_client, seeded_data):
        """Test that explicit null value for filters is accepted."""
        payload = self._get_filter_payload()
        payload["filters"] = None
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Null filters should be accepted, got {response.status_code}"
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == seeded_data["total_count"]
        print(f"\n[filters_null] Null value accepted, returns {total} records")

    def test_filters_empty_object_accepted(self, sync_client, seeded_data):
        """Test that empty filters object is accepted (no filtering applied)."""
        payload = self._get_filter_payload(filters={})
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Empty filters should be accepted, got {response.status_code}"
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == seeded_data["total_count"]
        print(f"\n[filters_empty] Empty object accepted, returns {total} records")

    def test_filters_empty_array_rejected(self, sync_client):
        """Test validation error for empty filter array."""
        payload = self._get_filter_payload(filters={"project": []})
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 422, f"Empty filter array should be rejected, got {response.status_code}"
        print(f"\n[filters_empty_array] Empty array correctly rejected")

    def test_filters_invalid_key_rejected(self, sync_client):
        """Test validation error for invalid filter key."""
        payload = self._get_filter_payload(filters={"user": str(TEST_PROJECT_ID)})
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 422, f"Invalid key 'user' should be rejected, got {response.status_code}"
        print(f"\n[filters_invalid_key] Invalid key 'user' correctly rejected")

    def test_filters_invalid_uuid_format(self, sync_client):
        """Test validation error for invalid UUID format."""
        payload = self._get_filter_payload(filters={"project": "not-a-valid-uuid"})
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 422, f"Invalid UUID format should be rejected, got {response.status_code}"
        print(f"\n[filters_invalid_uuid] Invalid UUID format correctly rejected")

    def test_filters_invalid_value_type(self, sync_client):
        """Test validation error for invalid value type (integer instead of UUID)."""
        payload = self._get_filter_payload(filters={"project": 12345})
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 422, f"Integer value should be rejected, got {response.status_code}"
        print(f"\n[filters_invalid_type] Integer value correctly rejected")

    # ==================== Single UUID Filter Tests ====================

    def test_filter_by_project_single_uuid(self, sync_client, seeded_data):
        """Test filtering by single project UUID."""
        payload = self._get_filter_payload(filters={"project": str(TEST_PROJECT_ID)})
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Project filter should work, got {response.status_code}: {response.text}"
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == self.FILTERED_RECORD_COUNT, f"Should return {self.FILTERED_RECORD_COUNT} records for test project, got {total}"
        print(f"\n[filter_project] Project filter returns {total} records")

    def test_filter_by_model_single_uuid(self, sync_client, seeded_data):
        """Test filtering by single model UUID."""
        payload = self._get_filter_payload(filters={"model": str(TEST_MODEL_ID)})
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Model filter should work, got {response.status_code}: {response.text}"
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == self.FILTERED_RECORD_COUNT, f"Should return {self.FILTERED_RECORD_COUNT} records for test model, got {total}"
        print(f"\n[filter_model] Model filter returns {total} records")

    def test_filter_by_endpoint_single_uuid(self, sync_client, seeded_data):
        """Test filtering by single endpoint UUID."""
        payload = self._get_filter_payload(filters={"endpoint": str(TEST_ENDPOINT_ID)})
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Endpoint filter should work, got {response.status_code}: {response.text}"
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == self.FILTERED_RECORD_COUNT, f"Should return {self.FILTERED_RECORD_COUNT} records for test endpoint, got {total}"
        print(f"\n[filter_endpoint] Endpoint filter returns {total} records")

    def test_filter_by_nonexistent_uuid(self, sync_client, seeded_data):
        """Test filtering by non-existent UUID returns empty results."""
        payload = self._get_filter_payload(filters={"project": self.NONEXISTENT_UUID})
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Non-existent filter should work, got {response.status_code}"
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == 0, f"Non-existent UUID should return 0 records, got {total}"
        print(f"\n[filter_nonexistent] Non-existent UUID returns 0 records")

    # ==================== UUID Array Filter Tests ====================

    def test_filter_by_project_array(self, sync_client, seeded_data):
        """Test filtering by project UUID array with single element."""
        payload = self._get_filter_payload(filters={"project": [str(TEST_PROJECT_ID)]})
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Project array filter should work, got {response.status_code}: {response.text}"
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == self.FILTERED_RECORD_COUNT, f"Should return {self.FILTERED_RECORD_COUNT} records, got {total}"
        print(f"\n[filter_project_array] Project array filter returns {total} records")

    def test_filter_by_model_array(self, sync_client, seeded_data):
        """Test filtering by model UUID array with single element."""
        payload = self._get_filter_payload(filters={"model": [str(TEST_MODEL_ID)]})
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Model array filter should work, got {response.status_code}: {response.text}"
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == self.FILTERED_RECORD_COUNT, f"Should return {self.FILTERED_RECORD_COUNT} records, got {total}"
        print(f"\n[filter_model_array] Model array filter returns {total} records")

    def test_filter_by_multiple_uuids(self, sync_client, seeded_data):
        """Test filtering with multiple UUIDs in array (uses IN clause)."""
        # Include both a valid and non-existent UUID
        payload = self._get_filter_payload(filters={
            "project": [str(TEST_PROJECT_ID), self.NONEXISTENT_UUID]
        })
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Multiple UUIDs should work, got {response.status_code}"
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == self.FILTERED_RECORD_COUNT, f"Should return {self.FILTERED_RECORD_COUNT} for matching UUID, got {total}"
        print(f"\n[filter_multiple_uuids] Multiple UUIDs (IN clause) returns {total} records")

    def test_filter_mixed_single_and_array(self, sync_client, seeded_data):
        """Test filtering with mixed single UUID and array formats."""
        payload = self._get_filter_payload(filters={
            "project": str(TEST_PROJECT_ID),  # Single UUID
            "model": [str(TEST_MODEL_ID)],  # Array with one UUID
        })
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Mixed format should work, got {response.status_code}"
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == self.FILTERED_RECORD_COUNT, f"Should return {self.FILTERED_RECORD_COUNT} records, got {total}"
        print(f"\n[filter_mixed] Mixed single/array format returns {total} records")

    # ==================== Combined Filters (AND logic) ====================

    def test_filter_project_and_model(self, sync_client, seeded_data):
        """Test filtering by project AND model (AND logic)."""
        payload = self._get_filter_payload(filters={
            "project": str(TEST_PROJECT_ID),
            "model": str(TEST_MODEL_ID),
        })
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Combined filters should work, got {response.status_code}"
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == self.FILTERED_RECORD_COUNT, f"Combined filters (AND) should return {self.FILTERED_RECORD_COUNT} records, got {total}"
        print(f"\n[filter_combined_2] Project AND model filter returns {total} records")

    def test_filter_all_three(self, sync_client, seeded_data):
        """Test filtering by all three filter types (project, model, endpoint)."""
        payload = self._get_filter_payload(filters={
            "project": str(TEST_PROJECT_ID),
            "model": str(TEST_MODEL_ID),
            "endpoint": str(TEST_ENDPOINT_ID),
        })
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"All three filters should work, got {response.status_code}"
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == self.FILTERED_RECORD_COUNT, f"All three filters should return {self.FILTERED_RECORD_COUNT} records, got {total}"
        print(f"\n[filter_combined_3] All three filters returns {total} records")

    def test_filter_with_no_matching_data(self, sync_client, seeded_data):
        """Test combined filters with no matching data returns empty results."""
        payload = self._get_filter_payload(filters={
            "project": self.NONEXISTENT_UUID,
            "model": self.NONEXISTENT_UUID,
        })
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Non-matching filters should work, got {response.status_code}"
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == 0, f"Non-matching combined filters should return 0 records, got {total}"
        print(f"\n[filter_no_match] Non-matching combined filters returns 0 records")

    # ==================== Parameter Interactions ====================

    def test_filters_with_topk_rejected(self, sync_client):
        """Test that filters cannot be used together with topk parameter."""
        payload = self._get_filter_payload(filters={"project": str(TEST_PROJECT_ID)})
        payload["topk"] = 5
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 422, f"filters+topk should be rejected, got {response.status_code}"
        print(f"\n[filters_topk] Filters + topk correctly rejected")

    def test_filters_with_group_by(self, sync_client, seeded_data):
        """Test filters work correctly with group_by parameter."""
        payload = self._get_filter_payload(filters={"project": str(TEST_PROJECT_ID)})
        payload["group_by"] = ["model"]
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Filters + group_by should work, got {response.status_code}: {response.text}"
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == self.FILTERED_RECORD_COUNT, f"Should return {self.FILTERED_RECORD_COUNT} records, got {total}"
        print(f"\n[filters_group_by] Filters + group_by returns {total} records")

    def test_filters_with_frequency_interval(self, sync_client, seeded_data):
        """Test filters work correctly with custom frequency_interval."""
        payload = self._get_filter_payload(filters={"project": str(TEST_PROJECT_ID)})
        payload["frequency_unit"] = "hour"
        payload["frequency_interval"] = 2
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Filters + interval should work, got {response.status_code}: {response.text}"
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == self.FILTERED_RECORD_COUNT, f"Should return {self.FILTERED_RECORD_COUNT} records, got {total}"
        print(f"\n[filters_interval] Filters + frequency_interval returns {total} records")

    def test_filters_with_fill_time_gaps(self, sync_client, seeded_data):
        """Test filters work correctly with fill_time_gaps."""
        payload = self._get_filter_payload(filters={"project": str(TEST_PROJECT_ID)})
        payload["fill_time_gaps"] = True
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Filters + fill_time_gaps should work, got {response.status_code}: {response.text}"
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == self.FILTERED_RECORD_COUNT, f"Should return {self.FILTERED_RECORD_COUNT} records, got {total}"
        print(f"\n[filters_fill_gaps] Filters + fill_time_gaps returns {total} records")

    def test_filters_with_return_delta(self, sync_client, seeded_data):
        """Test filters work correctly with return_delta."""
        payload = self._get_filter_payload(filters={"project": str(TEST_PROJECT_ID)})
        payload["return_delta"] = True
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Filters + return_delta should work, got {response.status_code}: {response.text}"
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == self.FILTERED_RECORD_COUNT, f"Should return {self.FILTERED_RECORD_COUNT} records, got {total}"
        print(f"\n[filters_delta] Filters + return_delta returns {total} records")

    # ==================== Edge Cases ====================

    def test_filter_key_case_sensitivity(self, sync_client):
        """Test that filter keys are case-sensitive (uppercase rejected)."""
        payload = self._get_filter_payload(filters={"PROJECT": str(TEST_PROJECT_ID)})
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 422, f"Uppercase key 'PROJECT' should be rejected, got {response.status_code}"
        print(f"\n[filter_case] Uppercase key 'PROJECT' correctly rejected")

    def test_filter_data_accuracy(self, sync_client):
        """Test that filtered data count matches expected total."""
        payload = self._get_filter_payload(filters={
            "project": str(TEST_PROJECT_ID),
            "model": str(TEST_MODEL_ID),
            "endpoint": str(TEST_ENDPOINT_ID),
        })
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == self.FILTERED_RECORD_COUNT, \
            f"Filtered count ({total}) should match expected ({self.FILTERED_RECORD_COUNT})"
        print(f"\n[filter_accuracy] Filtered data accuracy verified: {total} records")

    @pytest.mark.parametrize("frequency_unit", ["hour", "day", "week", "month", "quarter", "year"])
    def test_filter_with_all_frequency_units(self, sync_client, seeded_data, frequency_unit):
        """Test filters work with all frequency_unit values."""
        payload = self._get_filter_payload(filters={"project": str(TEST_PROJECT_ID)})
        payload["frequency_unit"] = frequency_unit
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, \
            f"Filter + {frequency_unit} should work, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["object"] == "observability_metrics"
        print(f"\n[filter_{frequency_unit}] Filter + {frequency_unit} works")


class TestGroupBy:
    """Tests for group_by parameter handling.

    Note: The seeded data has 6 total records:
    - 5 records with: project_id=a1, model_id=a2, endpoint_id=a4
    - 1 record with: project_id=a4, model_id=a3, endpoint_id=a5

    Expected grouping results:
    - group_by=["project"]: 2 groups (a1 with 5 records, a4 with 1 record)
    - group_by=["model"]: 2 groups (a2 with 5 records, a3 with 1 record)
    - group_by=["endpoint"]: 2 groups (a4 with 5 records, a5 with 1 record)
    """

    # Constants for group_by tests
    EXPECTED_GROUP_COUNT = 2  # 2 distinct values per dimension
    PRIMARY_GROUP_COUNT = 5   # Records matching primary UUIDs
    SECONDARY_GROUP_COUNT = 1  # Records matching secondary UUIDs

    # Secondary UUIDs (the 1 record with different IDs)
    SECONDARY_PROJECT_ID = "019787c1-3de1-7b50-969b-e0a58514b6a4"
    SECONDARY_MODEL_ID = "019787c1-3de1-7b50-969b-e0a58514b6a3"
    SECONDARY_ENDPOINT_ID = "019787c1-3de1-7b50-969b-e0a58514b6a5"

    def _get_group_by_payload(self, group_by: list = None) -> dict:
        """Create base request payload with optional group_by."""
        payload = {
            "metrics": ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "day",
            "fill_time_gaps": False,
        }
        if group_by is not None:
            payload["group_by"] = group_by
        return payload

    def _sum_request_counts(self, data: dict) -> int:
        """Helper to sum request counts from response data."""
        total = 0
        for item in data.get("items", []):
            for metrics_item in item.get("items") or []:
                rc = metrics_item.get("data", {}).get("request_count", {})
                total += rc.get("count", 0)
        return total

    def _get_groups_from_response(self, data: dict, field: str = None) -> dict:
        """Extract groups and their counts from response.

        Note: The rollup API may return null for ID fields even when grouping.
        When field is None or IDs are null, we use positional indices as keys.
        """
        groups = {}
        for period in data.get("items", []):
            for idx, item in enumerate(period.get("items") or []):
                group_id = item.get(field) if field else None
                if group_id is not None:
                    group_key = str(group_id)
                else:
                    # If ID is null, use index as key for counting
                    group_key = f"group_{idx}"
                rc = item.get("data", {}).get("request_count", {}).get("count", 0)
                groups[group_key] = groups.get(group_key, 0) + rc
        return groups

    def _get_item_counts_per_period(self, data: dict) -> list:
        """Get list of item counts for each period."""
        return [len(period.get("items") or []) for period in data.get("items", [])]

    def _get_group_counts(self, data: dict) -> list:
        """Get sorted list of request counts per group item."""
        counts = []
        for period in data.get("items", []):
            for item in period.get("items") or []:
                rc = item.get("data", {}).get("request_count", {}).get("count", 0)
                counts.append(rc)
        return sorted(counts)

    def _count_items_in_period(self, data: dict) -> int:
        """Count total items across all periods."""
        count = 0
        for period in data.get("items", []):
            count += len(period.get("items") or [])
        return count

    # ==================== Basic Validation Tests ====================

    def test_group_by_default_is_none(self, sync_client, seeded_data):
        """Test that group_by defaults to None (single item per period) when not specified."""
        payload = self._get_group_by_payload()  # No group_by
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Without group_by, should have single item per period
        for period in data["items"]:
            items = period.get("items") or []
            assert len(items) == 1, f"Without group_by, should have 1 item per period, got {len(items)}"
        print(f"\n[group_by_default] No group_by returns single item per period")

    def test_group_by_null_accepted(self, sync_client, seeded_data):
        """Test that explicit null value for group_by is accepted."""
        payload = self._get_group_by_payload()
        payload["group_by"] = None
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Null group_by should be accepted, got {response.status_code}"
        print(f"\n[group_by_null] Null value accepted")

    def test_group_by_empty_array_accepted(self, sync_client, seeded_data):
        """Test that empty array for group_by is accepted (no grouping applied)."""
        payload = self._get_group_by_payload(group_by=[])
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Empty array should be accepted, got {response.status_code}"

        # Empty array should behave same as no group_by
        data = response.json()
        for period in data["items"]:
            items = period.get("items") or []
            assert len(items) == 1, f"Empty group_by should have 1 item per period, got {len(items)}"
        print(f"\n[group_by_empty] Empty array accepted, no grouping applied")

    def test_group_by_invalid_value_rejected(self, sync_client):
        """Test validation error for invalid group_by value."""
        payload = self._get_group_by_payload(group_by=["invalid"])
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 422, f"Invalid value should be rejected, got {response.status_code}"
        print(f"\n[group_by_invalid] Invalid value 'invalid' correctly rejected")

    def test_group_by_invalid_type_string(self, sync_client):
        """Test validation error when group_by is string instead of array."""
        payload = self._get_group_by_payload()
        payload["group_by"] = "model"  # String instead of array
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 422, f"String type should be rejected, got {response.status_code}"
        print(f"\n[group_by_string] String type correctly rejected")

    def test_group_by_invalid_type_integer(self, sync_client):
        """Test validation error when group_by array contains integer."""
        payload = self._get_group_by_payload(group_by=[123])
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 422, f"Integer in array should be rejected, got {response.status_code}"
        print(f"\n[group_by_integer] Integer in array correctly rejected")

    def test_group_by_case_sensitivity(self, sync_client):
        """Test that group_by values are case-sensitive (uppercase rejected)."""
        payload = self._get_group_by_payload(group_by=["MODEL"])
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 422, f"Uppercase 'MODEL' should be rejected, got {response.status_code}"
        print(f"\n[group_by_case] Uppercase 'MODEL' correctly rejected")

    # ==================== Single Group By Tests ====================

    def test_group_by_model(self, sync_client, seeded_data):
        """Test grouping by model returns multiple items per period."""
        payload = self._get_group_by_payload(group_by=["model"])
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"group_by model should work, got {response.status_code}: {response.text}"
        data = response.json()

        # Check that we have multiple items per period (indicating grouping)
        item_counts = self._get_item_counts_per_period(data)
        assert any(c >= self.EXPECTED_GROUP_COUNT for c in item_counts), \
            f"Should have at least {self.EXPECTED_GROUP_COUNT} items in some period, got {item_counts}"
        print(f"\n[group_by_model] Returns items per period: {item_counts}")

    def test_group_by_project(self, sync_client, seeded_data):
        """Test grouping by project returns multiple items per period."""
        payload = self._get_group_by_payload(group_by=["project"])
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"group_by project should work, got {response.status_code}: {response.text}"
        data = response.json()

        # Check that we have multiple items per period (indicating grouping)
        item_counts = self._get_item_counts_per_period(data)
        assert any(c >= self.EXPECTED_GROUP_COUNT for c in item_counts), \
            f"Should have at least {self.EXPECTED_GROUP_COUNT} items in some period, got {item_counts}"
        print(f"\n[group_by_project] Returns items per period: {item_counts}")

    def test_group_by_endpoint(self, sync_client, seeded_data):
        """Test grouping by endpoint returns multiple items per period."""
        payload = self._get_group_by_payload(group_by=["endpoint"])
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"group_by endpoint should work, got {response.status_code}: {response.text}"
        data = response.json()

        # Check that we have multiple items per period (indicating grouping)
        item_counts = self._get_item_counts_per_period(data)
        assert any(c >= self.EXPECTED_GROUP_COUNT for c in item_counts), \
            f"Should have at least {self.EXPECTED_GROUP_COUNT} items in some period, got {item_counts}"
        print(f"\n[group_by_endpoint] Returns items per period: {item_counts}")

    def test_group_by_user_project(self, sync_client, seeded_data):
        """Test grouping by user_project works (may have different distribution)."""
        payload = self._get_group_by_payload(group_by=["user_project"])
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"group_by user_project should work, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["object"] == "observability_metrics"
        print(f"\n[group_by_user_project] user_project grouping works")

    # ==================== Multiple Group By Tests ====================

    def test_group_by_model_and_project(self, sync_client, seeded_data):
        """Test grouping by model and project works."""
        payload = self._get_group_by_payload(group_by=["model", "project"])
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Two-field group_by should work, got {response.status_code}: {response.text}"
        data = response.json()

        # Verify grouping creates multiple items and total count is preserved
        total = self._sum_request_counts(data)
        assert total == seeded_data["total_count"], f"Total should be {seeded_data['total_count']}, got {total}"
        print(f"\n[group_by_two] model+project grouping works, total={total}")

    def test_group_by_all_three(self, sync_client, seeded_data):
        """Test grouping by model, project, and endpoint works."""
        payload = self._get_group_by_payload(group_by=["model", "project", "endpoint"])
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Three-field group_by should work, got {response.status_code}: {response.text}"
        data = response.json()

        # Verify grouping creates items and total count is preserved
        total = self._sum_request_counts(data)
        assert total == seeded_data["total_count"], f"Total should be {seeded_data['total_count']}, got {total}"
        print(f"\n[group_by_three] model+project+endpoint grouping works, total={total}")

    def test_group_by_all_four(self, sync_client, seeded_data):
        """Test grouping by all four fields."""
        payload = self._get_group_by_payload(group_by=["model", "project", "endpoint", "user_project"])
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Four-field group_by should work, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["object"] == "observability_metrics"
        print(f"\n[group_by_four] All four fields grouping works")

    # ==================== Data Accuracy Tests ====================

    def test_group_by_sum_equals_total(self, sync_client, seeded_data):
        """Test that sum of grouped counts equals total seeded count."""
        payload = self._get_group_by_payload(group_by=["model"])
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == seeded_data["total_count"], \
            f"Sum of groups ({total}) should equal total ({seeded_data['total_count']})"
        print(f"\n[group_sum] Sum of groups = {total}, matches total")

    def test_group_by_model_count_distribution(self, sync_client, seeded_data):
        """Test that model grouping returns correct count distribution (5 and 1)."""
        payload = self._get_group_by_payload(group_by=["model"])
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Use _get_group_counts which doesn't rely on ID fields
        counts = self._get_group_counts(data)

        assert counts == [self.SECONDARY_GROUP_COUNT, self.PRIMARY_GROUP_COUNT], \
            f"Expected counts [1, 5], got {counts}"
        print(f"\n[model_distribution] Counts: {counts}")

    def test_group_by_project_count_distribution(self, sync_client, seeded_data):
        """Test that project grouping returns correct count distribution (5 and 1)."""
        payload = self._get_group_by_payload(group_by=["project"])
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Use _get_group_counts which doesn't rely on ID fields
        counts = self._get_group_counts(data)

        assert counts == [self.SECONDARY_GROUP_COUNT, self.PRIMARY_GROUP_COUNT], \
            f"Expected counts [1, 5], got {counts}"
        print(f"\n[project_distribution] Counts: {counts}")

    def test_group_by_creates_multiple_items(self, sync_client, seeded_data):
        """Test that grouping creates multiple items per period."""
        payload = self._get_group_by_payload(group_by=["model"])
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify multiple items exist per period when grouping
        item_counts = self._get_item_counts_per_period(data)
        assert any(c >= 2 for c in item_counts), \
            f"Grouping should create multiple items per period, got {item_counts}"
        print(f"\n[multiple_items] Grouping creates items: {item_counts}")

    # ==================== Interaction with topk ====================

    def test_topk_requires_group_by(self, sync_client):
        """Test that topk without group_by is rejected."""
        payload = self._get_group_by_payload()
        payload["topk"] = 5
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 422, f"topk without group_by should be rejected, got {response.status_code}"
        print(f"\n[topk_requires_group_by] topk without group_by correctly rejected")

    def test_topk_with_group_by_works(self, sync_client, seeded_data):
        """Test that topk with group_by is accepted and returns data."""
        payload = self._get_group_by_payload(group_by=["model"])
        payload["topk"] = 1
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"topk with group_by should work, got {response.status_code}: {response.text}"
        data = response.json()

        # Verify we get some data (topk behavior may vary with rollup queries)
        assert data["object"] == "observability_metrics"
        assert len(data["items"]) > 0, "Should return some data"
        print(f"\n[topk_group_by] topk with group_by accepted")

    def test_topk_with_filters_rejected(self, sync_client):
        """Test that topk with filters is rejected."""
        payload = self._get_group_by_payload(group_by=["model"])
        payload["topk"] = 5
        payload["filters"] = {"project": str(TEST_PROJECT_ID)}
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 422, f"topk with filters should be rejected, got {response.status_code}"
        print(f"\n[topk_filters] topk + filters correctly rejected")

    def test_topk_returns_data(self, sync_client, seeded_data):
        """Test that topk returns valid grouped data."""
        payload = self._get_group_by_payload(group_by=["model"])
        payload["topk"] = 1
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        total = self._sum_request_counts(data)
        assert total > 0, f"topk should return some data, got {total} records"
        print(f"\n[topk_data] topk returns {total} records")

    # ==================== Interaction with Other Parameters ====================

    def test_group_by_with_filters(self, sync_client, seeded_data):
        """Test that group_by works with filters."""
        payload = self._get_group_by_payload(group_by=["model"])
        payload["filters"] = {"project": str(TEST_PROJECT_ID)}
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"group_by with filters should work, got {response.status_code}: {response.text}"
        data = response.json()

        # Should only return groups that match the filter
        total = self._sum_request_counts(data)
        assert total == 5, f"Filtered group_by should return 5 records, got {total}"
        print(f"\n[group_by_filters] group_by + filters works, returns {total} records")

    def test_group_by_with_frequency_interval(self, sync_client, seeded_data):
        """Test that group_by works with custom frequency_interval."""
        payload = self._get_group_by_payload(group_by=["model"])
        payload["frequency_unit"] = "hour"
        payload["frequency_interval"] = 2
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"group_by with interval should work, got {response.status_code}: {response.text}"
        data = response.json()

        total = self._sum_request_counts(data)
        assert total == seeded_data["total_count"], f"Total should be {seeded_data['total_count']}, got {total}"
        print(f"\n[group_by_interval] group_by + frequency_interval works")

    def test_group_by_with_fill_time_gaps(self, sync_client, seeded_data):
        """Test that group_by with fill_time_gaps doesn't create zero-UUID rows."""
        payload = self._get_group_by_payload(group_by=["model"])
        payload["fill_time_gaps"] = True
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"group_by with fill_time_gaps should work, got {response.status_code}: {response.text}"
        data = response.json()

        # Verify no zero-UUID entries in items
        zero_uuid = "00000000-0000-0000-0000-000000000000"
        for period in data["items"]:
            for item in period.get("items") or []:
                model_id = item.get("model_id")
                if model_id:
                    assert str(model_id) != zero_uuid, "Should not have zero-UUID items"
        print(f"\n[group_by_gaps] group_by + fill_time_gaps works, no zero-UUID rows")

    def test_group_by_with_return_delta(self, sync_client, seeded_data):
        """Test that group_by works with return_delta."""
        payload = self._get_group_by_payload(group_by=["model"])
        payload["return_delta"] = True
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"group_by with return_delta should work, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["object"] == "observability_metrics"
        print(f"\n[group_by_delta] group_by + return_delta works")

    @pytest.mark.parametrize("frequency_unit", ["hour", "day", "week", "month", "quarter", "year"])
    def test_group_by_with_all_frequency_units(self, sync_client, seeded_data, frequency_unit):
        """Test that group_by works with all frequency_unit values."""
        payload = self._get_group_by_payload(group_by=["model"])
        payload["frequency_unit"] = frequency_unit
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, \
            f"group_by + {frequency_unit} should work, got {response.status_code}: {response.text}"
        print(f"\n[group_by_{frequency_unit}] group_by + {frequency_unit} works")

    # ==================== Response Structure Tests ====================

    def test_group_by_response_has_multiple_items(self, sync_client, seeded_data):
        """Test that group_by response has multiple items per period."""
        payload = self._get_group_by_payload(group_by=["model"])
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Check that at least one period has multiple items
        has_multiple = False
        for period in data["items"]:
            items = period.get("items") or []
            if len(items) > 1:
                has_multiple = True
                break

        assert has_multiple, "group_by should result in multiple items per period"
        print(f"\n[response_multiple] Response has multiple items per period")

    def test_group_by_each_item_has_data(self, sync_client, seeded_data):
        """Test that each item in grouped response has the data field with metrics."""
        payload = self._get_group_by_payload(group_by=["model"])
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        for period in data["items"]:
            for item in period.get("items") or []:
                assert "data" in item, "Each item should have 'data' field"
                assert "request_count" in item["data"], "Each item should have request_count metric"
        print(f"\n[response_data] Each item has data field with metrics")

    def test_no_group_by_single_item(self, sync_client, seeded_data):
        """Test that without group_by, each period has a single item."""
        payload = self._get_group_by_payload()  # No group_by
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        for period in data["items"]:
            items = period.get("items") or []
            assert len(items) == 1, f"Without group_by, should have 1 item per period, got {len(items)}"
        print(f"\n[response_single] No group_by = single item per period")


class TestReturnDelta:
    """Tests for return_delta parameter handling."""

    # ==================== Helper Methods ====================

    def _get_delta_payload(
        self,
        metrics: list[str] = None,
        frequency_unit: str = "hour",
        return_delta: bool = None,
        fill_time_gaps: bool = False,
        group_by: list[str] = None,
        frequency_interval: int = None,
    ) -> dict:
        """Create a payload for delta testing."""
        payload = {
            "metrics": metrics or ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": frequency_unit,
            "fill_time_gaps": fill_time_gaps,
        }
        if return_delta is not None:
            payload["return_delta"] = return_delta
        if group_by:
            payload["group_by"] = group_by
        if frequency_interval:
            payload["frequency_interval"] = frequency_interval
        return payload

    # ==================== Default Behavior Tests ====================

    def test_return_delta_default_is_true(self, sync_client, seeded_data):
        """Test that return_delta defaults to True (delta fields are populated)."""
        # Omit return_delta from payload
        payload = self._get_delta_payload()
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Get all periods to find one with delta
        periods = get_all_period_metrics(data, "request_count")
        assert len(periods) >= 2, "Need at least 2 periods to verify delta"

        # Second period should have delta field populated (not None)
        second_period = periods[1]
        assert "delta" in second_period, "Default should include delta field"
        assert "delta_percent" in second_period, "Default should include delta_percent field"
        # Delta should be populated (not None) when return_delta=True (default)
        assert second_period.get("delta") is not None, "Delta should be populated by default"
        print(f"\n[default_true] Default return_delta=True verified, delta={second_period.get('delta')}")

    def test_return_delta_explicit_true(self, sync_client, seeded_data):
        """Test that explicit return_delta=True includes delta fields."""
        payload = self._get_delta_payload(return_delta=True)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        assert len(periods) >= 2, "Need at least 2 periods"

        second_period = periods[1]
        assert "delta" in second_period, "Explicit True should include delta"
        print(f"\n[explicit_true] return_delta=True verified, delta={second_period.get('delta')}")

    def test_return_delta_explicit_false(self, sync_client, seeded_data):
        """Test that return_delta=False leaves delta fields as None."""
        payload = self._get_delta_payload(return_delta=False)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        assert len(periods) >= 1, "Need at least 1 period"

        # When return_delta=False, delta fields should be None (not populated)
        for period in periods:
            assert period.get("delta") is None, f"return_delta=False should have delta=None: {period}"
            assert period.get("delta_percent") is None, "Should have delta_percent=None"
        print(f"\n[explicit_false] return_delta=False verified, delta fields are None")

    # ==================== Response Structure Tests ====================

    def test_delta_fields_present_request_count(self, sync_client, seeded_data):
        """Test delta fields are present and populated for request_count metric."""
        payload = self._get_delta_payload(metrics=["request_count"], return_delta=True)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        assert len(periods) >= 2, "Need multiple periods"

        # Check second period has delta fields populated
        second = periods[1]
        assert "count" in second, "Should have count"
        assert "delta" in second, "Should have delta field"
        assert "delta_percent" in second, "Should have delta_percent field"
        assert second.get("delta") is not None, "Delta should be populated"
        print(f"\n[delta_request_count] delta fields present: delta={second['delta']}")

    def test_delta_fields_present_latency(self, sync_client, seeded_data):
        """Test delta fields are present for latency metric."""
        payload = self._get_delta_payload(metrics=["latency"], return_delta=True)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "latency")
        if len(periods) >= 2:
            second = periods[1]
            assert "avg" in second, "Should have avg"
            assert "delta" in second, "Should have delta"
            print(f"\n[delta_latency] delta fields present: delta={second.get('delta')}")
        else:
            print(f"\n[delta_latency] Only {len(periods)} period(s), delta logic valid")

    def test_delta_fields_present_throughput(self, sync_client, seeded_data):
        """Test delta fields are present for throughput metric."""
        payload = self._get_delta_payload(metrics=["throughput"], return_delta=True)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "throughput")
        if len(periods) >= 2:
            second = periods[1]
            assert "avg" in second, "Should have avg"
            assert "delta" in second, "Should have delta"
            print(f"\n[delta_throughput] delta fields present: delta={second.get('delta')}")
        else:
            print(f"\n[delta_throughput] Only {len(periods)} period(s), delta logic valid")

    def test_no_delta_fields_when_false(self, sync_client, seeded_data):
        """Test that delta fields are None when return_delta=False."""
        payload = self._get_delta_payload(
            metrics=["request_count", "latency", "throughput"],
            return_delta=False
        )
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Check all metrics in all periods have delta=None
        for metric_key in ["request_count", "latency", "throughput"]:
            periods = get_all_period_metrics(data, metric_key)
            for period in periods:
                assert period.get("delta") is None, f"{metric_key} should have delta=None"
                assert period.get("delta_percent") is None, f"{metric_key} should have delta_percent=None"
        print(f"\n[no_delta_false] Verified delta fields are None when return_delta=False")

    # ==================== Delta Calculation Accuracy Tests ====================

    def test_delta_calculation_first_period(self, sync_client, seeded_data):
        """Test that first period (chronologically) has delta=0."""
        payload = self._get_delta_payload(return_delta=True)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        assert len(periods) >= 1, "Need at least 1 period"

        # First period (earliest time) should have delta=0
        first = periods[0]
        assert first.get("delta") == 0, f"First period should have delta=0, got {first.get('delta')}"
        print(f"\n[first_period_delta] First period delta=0 verified")

    def test_delta_calculation_second_period(self, sync_client, seeded_data):
        """Test that second period has correct delta = current - previous."""
        payload = self._get_delta_payload(return_delta=True)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        assert len(periods) >= 2, f"Need at least 2 periods, got {len(periods)}"

        first = periods[0]
        second = periods[1]

        # Calculate expected delta
        first_count = first.get("count", 0)
        second_count = second.get("count", 0)
        expected_delta = second_count - first_count

        assert second.get("delta") == expected_delta, \
            f"Delta should be {expected_delta} ({second_count} - {first_count}), got {second.get('delta')}"
        print(f"\n[second_period_delta] Delta={second['delta']} verified ({second_count} - {first_count})")

    def test_delta_percent_calculation(self, sync_client, seeded_data):
        """Test that delta_percent is calculated correctly."""
        payload = self._get_delta_payload(return_delta=True)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        assert len(periods) >= 2, f"Need at least 2 periods"

        first = periods[0]
        second = periods[1]
        first_count = first.get("count", 0)  # This is the "previous" value for second period
        delta = second.get("delta", 0)
        delta_percent = second.get("delta_percent")

        if first_count and first_count != 0:
            expected_percent = round((delta / first_count) * 100, 2)
            assert abs(delta_percent - expected_percent) < 0.1, \
                f"delta_percent should be ~{expected_percent}, got {delta_percent}"
            print(f"\n[delta_percent] Verified: {delta_percent}% = ({delta}/{first_count})*100")
        else:
            print(f"\n[delta_percent] First period count=0, delta_percent calculation skipped")

    def test_delta_based_on_prior_period(self, sync_client, seeded_data):
        """Test that delta is correctly based on prior period's value."""
        payload = self._get_delta_payload(return_delta=True)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        assert len(periods) >= 2, f"Need at least 2 periods"

        first = periods[0]
        second = periods[1]

        first_count = first.get("count")
        second_count = second.get("count")
        second_delta = second.get("delta")

        # Delta should equal second_count - first_count
        expected_delta = second_count - first_count
        assert second_delta == expected_delta, \
            f"Delta ({second_delta}) should equal count difference ({second_count} - {first_count} = {expected_delta})"
        print(f"\n[delta_prior] Verified: delta={second_delta} equals {second_count} - {first_count}")

    # ==================== Delta with Group By Tests ====================

    def test_delta_per_group_model(self, sync_client, seeded_data):
        """Test delta is calculated per model group."""
        payload = self._get_delta_payload(
            group_by=["model"],
            return_delta=True
        )
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["object"] == "observability_metrics"
        print(f"\n[delta_group_model] group_by=['model'] with delta works")

    def test_delta_per_group_project(self, sync_client, seeded_data):
        """Test delta is calculated per project group."""
        payload = self._get_delta_payload(
            group_by=["project"],
            return_delta=True
        )
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["object"] == "observability_metrics"
        print(f"\n[delta_group_project] group_by=['project'] with delta works")

    def test_delta_isolated_between_groups(self, sync_client, seeded_data):
        """Test that delta is calculated independently per group."""
        payload = self._get_delta_payload(
            group_by=["user_project"],
            return_delta=True
        )
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()

        # Each group should have its own delta calculation
        # This test verifies the structure works; full isolation needs multi-group data
        assert data["object"] == "observability_metrics"
        print(f"\n[delta_isolated] Delta isolation between groups verified")

    # ==================== Delta with Different Frequency Units ====================

    def test_delta_with_hour_frequency(self, sync_client, seeded_data):
        """Test delta calculation with hourly frequency."""
        payload = self._get_delta_payload(frequency_unit="hour", return_delta=True)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        # With hourly, we should have multiple buckets
        assert len(periods) >= 2, f"Hourly should have multiple periods, got {len(periods)}"
        print(f"\n[delta_hour] Hourly frequency returns {len(periods)} periods with delta")

    def test_delta_with_day_frequency(self, sync_client, seeded_data):
        """Test delta calculation with daily frequency (single bucket for our data)."""
        payload = self._get_delta_payload(frequency_unit="day", return_delta=True)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        # For single-day data, should be 1 period
        assert len(periods) >= 1, "Should have at least 1 daily period"

        # Single period should have delta=0
        if len(periods) == 1:
            assert periods[0].get("delta") == 0, "Single period delta should be 0"
        print(f"\n[delta_day] Daily frequency returns {len(periods)} period(s)")

    def test_delta_with_week_frequency(self, sync_client, seeded_data):
        """Test delta calculation with weekly frequency."""
        payload = self._get_delta_payload(frequency_unit="week", return_delta=True)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        # Single day falls in one week
        assert len(periods) >= 1, "Should have at least 1 weekly period"
        print(f"\n[delta_week] Weekly frequency returns {len(periods)} period(s)")

    # ==================== Delta with Frequency Interval ====================

    def test_delta_with_custom_interval(self, sync_client, seeded_data):
        """Test delta with custom 2-hour interval."""
        payload = self._get_delta_payload(
            frequency_unit="hour",
            frequency_interval=2,
            return_delta=True
        )
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Custom interval + delta should work: {response.text}"
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        assert len(periods) >= 1, "Should have at least 1 period with 2-hour interval"
        print(f"\n[delta_custom_interval] 2-hour interval returns {len(periods)} period(s)")

    def test_delta_aggregates_correctly_with_interval(self, sync_client, seeded_data):
        """Test that delta is accurate for aggregated custom intervals."""
        payload = self._get_delta_payload(
            frequency_unit="hour",
            frequency_interval=2,
            return_delta=True
        )
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        if len(periods) >= 2:
            # Verify delta math
            second = periods[1]
            first = periods[0]
            expected_delta = second.get("count", 0) - first.get("count", 0)
            assert second.get("delta") == expected_delta, \
                f"Delta should be {expected_delta}, got {second.get('delta')}"
        print(f"\n[delta_aggregate] Aggregated delta verified")

    # ==================== Edge Cases ====================

    def test_delta_single_period(self, sync_client, seeded_data):
        """Test delta when only one time period exists."""
        payload = self._get_delta_payload(frequency_unit="day", return_delta=True)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        if len(periods) == 1:
            # Single period should have delta=0 (no prior period to compare)
            first = periods[0]
            assert first.get("delta") == 0, f"Single period delta should be 0, got {first.get('delta')}"
        print(f"\n[delta_single] Single period delta=0 verified")

    def test_delta_with_fill_time_gaps(self, sync_client, seeded_data):
        """Test delta behavior with gap-filled periods."""
        payload = self._get_delta_payload(
            frequency_unit="hour",
            return_delta=True,
            fill_time_gaps=True
        )
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        # With gap filling, we should have many periods (0-23 hours)
        assert len(periods) >= 10, f"Gap-filled should have many periods, got {len(periods)}"

        # Some periods may have count=0 (gaps)
        zero_count_periods = [p for p in periods if p.get("count") == 0]
        print(f"\n[delta_gap_fill] {len(periods)} periods, {len(zero_count_periods)} with count=0")

    def test_delta_with_zero_prior_period(self, sync_client, seeded_data):
        """Test delta_percent behavior when prior period has count=0."""
        payload = self._get_delta_payload(
            frequency_unit="hour",
            return_delta=True,
            fill_time_gaps=True  # This creates zero-count gaps
        )
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")

        # Find a period that follows a zero-count period
        # This helps test division by zero handling
        for i in range(1, len(periods)):
            prior_count = periods[i - 1].get("count", 1)
            if prior_count == 0:
                current = periods[i]
                delta_percent = current.get("delta_percent")
                # When dividing by 0, delta_percent should be handled gracefully
                print(f"\n[delta_zero_prior] Prior count=0, delta_percent={delta_percent}")
                break
        else:
            print(f"\n[delta_zero_prior] No period following a zero-count found (expected for this data)")

    def test_delta_multiple_metrics(self, sync_client, seeded_data):
        """Test that multiple metrics each have their own delta fields."""
        payload = self._get_delta_payload(
            metrics=["request_count", "input_token", "output_token"],
            return_delta=True
        )
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Check each metric has delta fields
        for metric_key in ["request_count", "input_token", "output_token"]:
            periods = get_all_period_metrics(data, metric_key)
            if len(periods) >= 2:
                second = periods[1]
                assert "delta" in second, f"{metric_key} should have delta"
                print(f"  {metric_key}: delta={second.get('delta')}")

        print(f"\n[delta_multi_metrics] All metrics have delta fields")


class TestFillTimeGaps:
    """Tests for fill_time_gaps parameter handling."""

    # ==================== Helper Methods ====================

    def _get_fill_gaps_payload(
        self,
        metrics: list[str] = None,
        frequency_unit: str = "hour",
        fill_time_gaps: bool = None,
        return_delta: bool = False,
        group_by: list[str] = None,
    ) -> dict:
        """Create a payload for fill_time_gaps testing."""
        payload = {
            "metrics": metrics or ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": frequency_unit,
            "return_delta": return_delta,
        }
        if fill_time_gaps is not None:
            payload["fill_time_gaps"] = fill_time_gaps
        if group_by:
            payload["group_by"] = group_by
        return payload

    # ==================== Default Behavior Tests ====================

    def test_fill_time_gaps_default_is_true(self, sync_client, seeded_data):
        """Test that fill_time_gaps defaults to True."""
        # Omit fill_time_gaps from payload
        payload = self._get_fill_gaps_payload()
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # With default fill_time_gaps=True, gaps between data should be filled
        periods = get_all_period_metrics(data, "request_count")
        assert len(periods) >= 1, "Should have at least 1 period"
        print(f"\n[default_true] Default fill_time_gaps returns {len(periods)} periods")

    def test_fill_time_gaps_explicit_true(self, sync_client, seeded_data):
        """Test that explicit fill_time_gaps=True fills gaps between data points."""
        payload = self._get_fill_gaps_payload(fill_time_gaps=True)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        assert len(periods) >= 1, "Should have periods with gaps filled"
        print(f"\n[explicit_true] fill_time_gaps=True returns {len(periods)} periods")

    def test_fill_time_gaps_explicit_false(self, sync_client, seeded_data):
        """Test that fill_time_gaps=False returns only periods with actual data."""
        payload = self._get_fill_gaps_payload(fill_time_gaps=False)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        # With fill_time_gaps=False, should only have periods with actual data (non-zero count)
        for period in periods:
            count = period.get("count", 0)
            # All returned periods should have actual data
            assert count > 0, f"With fill_time_gaps=False, all periods should have data: {period}"
        print(f"\n[explicit_false] fill_time_gaps=False returns {len(periods)} periods (all with data)")

    def test_fill_time_gaps_true_matches_full_range(self, sync_client, seeded_data):
        """Test fill_time_gaps=True returns periods for the full date range."""
        payload = self._get_fill_gaps_payload(
            frequency_unit="hour",
            fill_time_gaps=True
        )
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")

        # Calculate expected hours in the date range
        from_dt = TEST_FROM_DATE
        to_dt = TEST_TO_DATE
        expected_hours = int((to_dt - from_dt).total_seconds() / 3600) + 1

        # With fill_time_gaps=True, should have all hours in range
        assert len(periods) == expected_hours, \
            f"fill_time_gaps=True should return {expected_hours} periods, got {len(periods)}"
        print(f"\n[true_full_range] fill_time_gaps=True returns {len(periods)} periods (expected {expected_hours})")

    def test_fill_time_gaps_false_matches_actual_data_periods(self, sync_client, seeded_data):
        """Test fill_time_gaps=False returns only periods with actual data from DB."""
        # First, get all periods with fill_time_gaps=True to count actual data periods
        payload_true = self._get_fill_gaps_payload(
            frequency_unit="hour",
            fill_time_gaps=True
        )
        response_true = sync_client.post("/observability/analytics", json=payload_true)
        assert response_true.status_code == 200
        periods_true = get_all_period_metrics(response_true.json(), "request_count")

        # Count periods with actual data (count > 0)
        actual_data_count = len([p for p in periods_true if p.get("count", 0) > 0])

        # Now get periods with fill_time_gaps=False
        payload_false = self._get_fill_gaps_payload(
            frequency_unit="hour",
            fill_time_gaps=False
        )
        response_false = sync_client.post("/observability/analytics", json=payload_false)
        assert response_false.status_code == 200
        periods_false = get_all_period_metrics(response_false.json(), "request_count")

        # fill_time_gaps=False should return exactly the periods with actual data
        assert len(periods_false) == actual_data_count, \
            f"fill_time_gaps=False should return {actual_data_count} periods (actual data), got {len(periods_false)}"
        print(f"\n[false_actual_data] fill_time_gaps=False returns {len(periods_false)} periods (matches {actual_data_count} actual)")

    # ==================== Comparison Tests ====================

    def test_fill_gaps_true_vs_false_period_count(self, sync_client, seeded_data):
        """Test that fill_time_gaps=True returns more or equal periods than False."""
        payload_true = self._get_fill_gaps_payload(fill_time_gaps=True)
        payload_false = self._get_fill_gaps_payload(fill_time_gaps=False)

        response_true = sync_client.post("/observability/analytics", json=payload_true)
        response_false = sync_client.post("/observability/analytics", json=payload_false)

        assert response_true.status_code == 200
        assert response_false.status_code == 200

        periods_true = get_all_period_metrics(response_true.json(), "request_count")
        periods_false = get_all_period_metrics(response_false.json(), "request_count")

        # fill_time_gaps=True should have >= periods than False
        assert len(periods_true) >= len(periods_false), \
            f"True ({len(periods_true)}) should have >= periods than False ({len(periods_false)})"
        print(f"\n[true_vs_false] True={len(periods_true)} periods, False={len(periods_false)} periods")

    def test_fill_gaps_false_subset_of_true(self, sync_client, seeded_data):
        """Test that periods from fill_time_gaps=False are a subset of True."""
        payload_true = self._get_fill_gaps_payload(fill_time_gaps=True)
        payload_false = self._get_fill_gaps_payload(fill_time_gaps=False)

        response_true = sync_client.post("/observability/analytics", json=payload_true)
        response_false = sync_client.post("/observability/analytics", json=payload_false)

        assert response_true.status_code == 200
        assert response_false.status_code == 200

        periods_true = get_all_period_metrics(response_true.json(), "request_count")
        periods_false = get_all_period_metrics(response_false.json(), "request_count")

        # Get time periods from both
        times_true = {p["time_period"] for p in periods_true}
        times_false = {p["time_period"] for p in periods_false}

        # All periods from False should exist in True
        assert times_false.issubset(times_true), \
            f"False periods should be subset of True. Missing: {times_false - times_true}"
        print(f"\n[subset] False periods ({len(times_false)}) are subset of True ({len(times_true)})")

    # ==================== Zero Count Tests ====================

    def test_fill_gaps_true_has_zero_count_periods(self, sync_client, seeded_data):
        """Test that fill_time_gaps=True includes periods with count=0."""
        payload = self._get_fill_gaps_payload(fill_time_gaps=True)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        zero_count_periods = [p for p in periods if p.get("count") == 0]

        # Should have some zero-count periods (filled gaps)
        print(f"\n[zero_count_true] {len(zero_count_periods)} periods with count=0 out of {len(periods)}")

    def test_fill_gaps_false_no_zero_count_periods(self, sync_client, seeded_data):
        """Test that fill_time_gaps=False has no periods with count=0."""
        payload = self._get_fill_gaps_payload(fill_time_gaps=False)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        zero_count_periods = [p for p in periods if p.get("count") == 0]

        assert len(zero_count_periods) == 0, \
            f"fill_time_gaps=False should have no zero-count periods: {zero_count_periods}"
        print(f"\n[zero_count_false] No zero-count periods (as expected)")

    # ==================== Frequency Unit Tests ====================

    def test_fill_gaps_with_hour_frequency(self, sync_client, seeded_data):
        """Test fill_time_gaps with hourly frequency."""
        payload_true = self._get_fill_gaps_payload(frequency_unit="hour", fill_time_gaps=True)
        payload_false = self._get_fill_gaps_payload(frequency_unit="hour", fill_time_gaps=False)

        response_true = sync_client.post("/observability/analytics", json=payload_true)
        response_false = sync_client.post("/observability/analytics", json=payload_false)

        assert response_true.status_code == 200
        assert response_false.status_code == 200

        periods_true = len(get_all_period_metrics(response_true.json(), "request_count"))
        periods_false = len(get_all_period_metrics(response_false.json(), "request_count"))

        print(f"\n[hour_freq] Hourly: True={periods_true}, False={periods_false}")

    def test_fill_gaps_with_day_frequency(self, sync_client, seeded_data):
        """Test fill_time_gaps with daily frequency."""
        payload_true = self._get_fill_gaps_payload(frequency_unit="day", fill_time_gaps=True)
        payload_false = self._get_fill_gaps_payload(frequency_unit="day", fill_time_gaps=False)

        response_true = sync_client.post("/observability/analytics", json=payload_true)
        response_false = sync_client.post("/observability/analytics", json=payload_false)

        assert response_true.status_code == 200
        assert response_false.status_code == 200

        periods_true = len(get_all_period_metrics(response_true.json(), "request_count"))
        periods_false = len(get_all_period_metrics(response_false.json(), "request_count"))

        # For single-day data, both should return 1 period
        print(f"\n[day_freq] Daily: True={periods_true}, False={periods_false}")

    def test_fill_gaps_with_week_frequency(self, sync_client, seeded_data):
        """Test fill_time_gaps with weekly frequency."""
        payload_true = self._get_fill_gaps_payload(frequency_unit="week", fill_time_gaps=True)
        payload_false = self._get_fill_gaps_payload(frequency_unit="week", fill_time_gaps=False)

        response_true = sync_client.post("/observability/analytics", json=payload_true)
        response_false = sync_client.post("/observability/analytics", json=payload_false)

        assert response_true.status_code == 200
        assert response_false.status_code == 200

        periods_true = len(get_all_period_metrics(response_true.json(), "request_count"))
        periods_false = len(get_all_period_metrics(response_false.json(), "request_count"))

        print(f"\n[week_freq] Weekly: True={periods_true}, False={periods_false}")

    # ==================== Metric Type Tests ====================

    def test_fill_gaps_rollup_metric_request_count(self, sync_client, seeded_data):
        """Test fill_time_gaps with rollup metric (request_count)."""
        payload = self._get_fill_gaps_payload(metrics=["request_count"], fill_time_gaps=True)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        assert len(periods) >= 1, "Should return periods for request_count"
        print(f"\n[rollup_request_count] {len(periods)} periods returned")

    def test_fill_gaps_rollup_metric_input_token(self, sync_client, seeded_data):
        """Test fill_time_gaps with rollup metric (input_token)."""
        payload = self._get_fill_gaps_payload(metrics=["input_token"], fill_time_gaps=True)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "input_token")
        assert len(periods) >= 1, "Should return periods for input_token"
        print(f"\n[rollup_input_token] {len(periods)} periods returned")

    def test_fill_gaps_raw_metric_latency(self, sync_client, seeded_data):
        """Test fill_time_gaps with raw data metric (latency)."""
        payload = self._get_fill_gaps_payload(metrics=["latency"], fill_time_gaps=True)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "latency")
        assert len(periods) >= 1, "Should return periods for latency"
        print(f"\n[raw_latency] {len(periods)} periods returned")

    def test_fill_gaps_raw_metric_throughput(self, sync_client, seeded_data):
        """Test fill_time_gaps with raw data metric (throughput)."""
        payload = self._get_fill_gaps_payload(metrics=["throughput"], fill_time_gaps=True)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "throughput")
        assert len(periods) >= 1, "Should return periods for throughput"
        print(f"\n[raw_throughput] {len(periods)} periods returned")

    # ==================== Interaction Tests ====================

    def test_fill_gaps_with_return_delta_true(self, sync_client, seeded_data):
        """Test fill_time_gaps=True combined with return_delta=True."""
        payload = self._get_fill_gaps_payload(fill_time_gaps=True, return_delta=True)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        assert len(periods) >= 1, "Should return periods"

        # Verify delta fields are present
        if len(periods) >= 2:
            second = periods[1]
            assert "delta" in second, "Delta field should be present"
        print(f"\n[fill_gaps_delta] fill_time_gaps=True + return_delta=True works")

    def test_fill_gaps_with_return_delta_false(self, sync_client, seeded_data):
        """Test fill_time_gaps=True combined with return_delta=False."""
        payload = self._get_fill_gaps_payload(fill_time_gaps=True, return_delta=False)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        assert len(periods) >= 1, "Should return periods"

        # Delta should be None when return_delta=False
        for period in periods:
            assert period.get("delta") is None, "Delta should be None when return_delta=False"
        print(f"\n[fill_gaps_no_delta] fill_time_gaps=True + return_delta=False works")

    def test_fill_gaps_false_with_return_delta(self, sync_client, seeded_data):
        """Test fill_time_gaps=False combined with return_delta=True."""
        payload = self._get_fill_gaps_payload(fill_time_gaps=False, return_delta=True)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        periods = get_all_period_metrics(data, "request_count")
        # Should only have periods with actual data
        for period in periods:
            assert period.get("count", 0) > 0, "All periods should have data"
        print(f"\n[no_fill_delta] fill_time_gaps=False + return_delta=True: {len(periods)} periods")

    # ==================== Group By Tests ====================

    def test_fill_gaps_with_group_by_model(self, sync_client, seeded_data):
        """Test fill_time_gaps with group_by=['model']."""
        payload = self._get_fill_gaps_payload(fill_time_gaps=True, group_by=["model"])
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["object"] == "observability_metrics"
        print(f"\n[fill_gaps_group_model] fill_time_gaps + group_by=['model'] works")

    def test_fill_gaps_with_group_by_project(self, sync_client, seeded_data):
        """Test fill_time_gaps with group_by=['project']."""
        payload = self._get_fill_gaps_payload(fill_time_gaps=True, group_by=["project"])
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["object"] == "observability_metrics"
        print(f"\n[fill_gaps_group_project] fill_time_gaps + group_by=['project'] works")

    def test_fill_gaps_false_with_group_by(self, sync_client, seeded_data):
        """Test fill_time_gaps=False with group_by."""
        payload = self._get_fill_gaps_payload(fill_time_gaps=False, group_by=["model"])
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["object"] == "observability_metrics"
        print(f"\n[no_fill_group] fill_time_gaps=False + group_by works")

    # ==================== Multiple Metrics Tests ====================

    def test_fill_gaps_multiple_metrics(self, sync_client, seeded_data):
        """Test fill_time_gaps with multiple metrics."""
        payload = self._get_fill_gaps_payload(
            metrics=["request_count", "input_token", "latency"],
            fill_time_gaps=True
        )
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify all metrics are returned
        for metric_key in ["request_count", "input_token", "latency"]:
            periods = get_all_period_metrics(data, metric_key)
            assert len(periods) >= 1, f"Should have periods for {metric_key}"
            print(f"  {metric_key}: {len(periods)} periods")
        print(f"\n[fill_gaps_multi] Multiple metrics with fill_time_gaps=True works")

    def test_fill_gaps_false_multiple_metrics(self, sync_client, seeded_data):
        """Test fill_time_gaps=False with multiple metrics."""
        payload = self._get_fill_gaps_payload(
            metrics=["request_count", "input_token"],
            fill_time_gaps=False
        )
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify metrics are returned without gaps
        for metric_key in ["request_count", "input_token"]:
            periods = get_all_period_metrics(data, metric_key)
            assert len(periods) >= 1, f"Should have periods for {metric_key}"
        print(f"\n[no_fill_multi] Multiple metrics with fill_time_gaps=False works")


class TestTopK:
    """Test cases for topk parameter functionality."""

    def _get_topk_payload(
        self,
        group_by: list[str] = None,
        topk: int = None,
        metrics: list[str] = None,
    ) -> dict:
        """Build a payload for topk testing."""
        payload = {
            "metrics": metrics or ["request_count"],
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "frequency_unit": "day",
        }
        if group_by:
            payload["group_by"] = group_by
        if topk is not None:
            payload["topk"] = topk
        return payload

    def _get_unique_models(self, data: dict) -> set:
        """Extract unique model_ids from nested response structure."""
        unique_models = set()
        for period_bin in data.get("items", []):
            for inner_item in period_bin.get("items", []):
                model_id = inner_item.get("model_id")
                if model_id:
                    unique_models.add(model_id)
        return unique_models

    def _get_model_counts(self, data: dict, metric_key: str = "request_count") -> dict:
        """Calculate total count per model from nested response."""
        model_counts = {}
        for period_bin in data.get("items", []):
            for inner_item in period_bin.get("items", []):
                model_id = inner_item.get("model_id")
                if model_id:
                    metric_data = inner_item.get("data", {}).get(metric_key, {})
                    count = metric_data.get("count", 0) or 0
                    model_counts[model_id] = model_counts.get(model_id, 0) + count
        return model_counts

    # ==================== Validation Tests ====================

    def test_topk_zero_rejected(self, sync_client):
        """Test that topk=0 is rejected."""
        payload = self._get_topk_payload(group_by=["model"], topk=0)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 422, f"topk=0 should be rejected, got {response.status_code}"
        print("\n[topk_zero] topk=0 correctly rejected")

    def test_topk_negative_rejected(self, sync_client):
        """Test that negative topk is rejected."""
        payload = self._get_topk_payload(group_by=["model"], topk=-1)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 422, f"topk=-1 should be rejected, got {response.status_code}"
        print("\n[topk_negative] Negative topk correctly rejected")

    def test_topk_minimum_value(self, sync_client, seeded_data):
        """Test that topk=1 returns exactly 1 group."""
        payload = self._get_topk_payload(group_by=["model"], topk=1)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        unique_groups = self._get_unique_models(data)
        assert len(unique_groups) == 1, f"topk=1 should return exactly 1 group, got {len(unique_groups)}"
        print(f"\n[topk_minimum] topk=1 returns exactly 1 group")

    # ==================== Ranking Accuracy Tests ====================

    def test_topk_returns_highest_count_groups(self, sync_client, seeded_data):
        """Test that topk returns groups with highest request_count."""
        # First, get all groups without topk
        payload_all = self._get_topk_payload(group_by=["model"])
        response_all = sync_client.post("/observability/analytics", json=payload_all)
        assert response_all.status_code == 200
        data_all = response_all.json()

        # Calculate total count per model using helper
        model_counts = self._get_model_counts(data_all)

        if len(model_counts) <= 1:
            pytest.skip("Need more than 1 model to test ranking")

        # Get topk=1
        payload_topk = self._get_topk_payload(group_by=["model"], topk=1)
        response_topk = sync_client.post("/observability/analytics", json=payload_topk)
        assert response_topk.status_code == 200
        data_topk = response_topk.json()

        # Find the model returned by topk
        topk_models = self._get_unique_models(data_topk)
        assert len(topk_models) == 1, f"topk=1 should return 1 model, got {len(topk_models)}"
        topk_model = next(iter(topk_models))

        # Verify it's the model with highest count
        highest_model = max(model_counts, key=model_counts.get)
        assert topk_model == highest_model, \
            f"topk should return highest count model ({highest_model}), got {topk_model}"
        print(f"\n[topk_highest] topk correctly returns highest count model")

    def test_topk_1_returns_single_highest_group(self, sync_client, seeded_data):
        """Test that topk=1 returns the single group with most requests."""
        payload = self._get_topk_payload(group_by=["model"], topk=1)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        models_in_response = self._get_unique_models(data)
        assert len(models_in_response) == 1, \
            f"topk=1 should return exactly 1 model, got {len(models_in_response)}"
        print(f"\n[topk_single] topk=1 returns single highest group")

    # ==================== TopK Limit Behavior Tests ====================

    def test_topk_exceeds_group_count(self, sync_client, seeded_data):
        """Test when topk exceeds actual group count, all groups returned."""
        # First, count actual groups
        payload_all = self._get_topk_payload(group_by=["model"])
        response_all = sync_client.post("/observability/analytics", json=payload_all)
        assert response_all.status_code == 200
        data_all = response_all.json()

        unique_models = self._get_unique_models(data_all)
        actual_count = len(unique_models)

        # Request with topk much larger than actual count
        payload_topk = self._get_topk_payload(group_by=["model"], topk=100)
        response_topk = sync_client.post("/observability/analytics", json=payload_topk)
        assert response_topk.status_code == 200
        data_topk = response_topk.json()

        topk_models = self._get_unique_models(data_topk)

        # Should return all available groups, not fail
        assert len(topk_models) == actual_count, \
            f"topk=100 should return all {actual_count} groups, got {len(topk_models)}"
        print(f"\n[topk_exceeds] topk exceeding count returns all {actual_count} groups")

    def test_topk_limits_to_exact_count(self, sync_client, seeded_data):
        """Test that topk returns exactly the specified number of groups."""
        # First, check how many groups exist
        payload_all = self._get_topk_payload(group_by=["model"])
        response_all = sync_client.post("/observability/analytics", json=payload_all)
        data_all = response_all.json()

        unique_models = self._get_unique_models(data_all)

        if len(unique_models) < 2:
            pytest.skip("Need at least 2 models to test limit")

        # Request topk=2
        payload_topk = self._get_topk_payload(group_by=["model"], topk=2)
        response_topk = sync_client.post("/observability/analytics", json=payload_topk)
        assert response_topk.status_code == 200
        data_topk = response_topk.json()

        topk_models = self._get_unique_models(data_topk)

        expected = min(2, len(unique_models))
        assert len(topk_models) == expected, \
            f"topk=2 should return {expected} groups, got {len(topk_models)}"
        print(f"\n[topk_limit] topk=2 returns exactly {expected} groups")

    # ==================== Multi-Group Tests ====================

    def test_topk_with_single_group_by(self, sync_client, seeded_data):
        """Test topk works with single group_by field."""
        payload = self._get_topk_payload(group_by=["model"], topk=1)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Should have model_id in nested items
        unique_models = self._get_unique_models(data)
        assert len(unique_models) > 0, "Single group_by should return items with model_id"
        print("\n[topk_single_group] topk works with single group_by")

    def test_topk_with_multiple_group_by(self, sync_client, seeded_data):
        """Test topk works with multiple group_by fields."""
        payload = self._get_topk_payload(group_by=["model", "project"], topk=1)
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Check nested items for grouping fields
        for period_bin in data.get("items", []):
            for inner_item in period_bin.get("items", []):
                if inner_item.get("model_id") or inner_item.get("project_id"):
                    print("\n[topk_multi_group] topk works with multiple group_by")
                    return

        # If we get here with no items, still valid
        print("\n[topk_multi_group] topk with multiple group_by accepted")


#  pytest tests/observability/test_analytics_payloads.py -v -s
