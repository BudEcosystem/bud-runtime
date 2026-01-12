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


#  pytest tests/observability/test_analytics_payloads.py -v -s
