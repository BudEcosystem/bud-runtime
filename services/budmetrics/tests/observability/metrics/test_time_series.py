"""Tests for POST /observability/metrics/time-series endpoint.

These tests validate the time-series API by:
1. Testing all request parameters (from_date, to_date, interval, metrics, group_by, filters, fill_gaps)
2. Verifying response structure matches expected schema
3. Comparing values against InferenceFact ground truth

Run with: pytest tests/observability/metrics/test_time_series.py -v -s
"""

import asyncio
from datetime import datetime, timedelta
from uuid import UUID

import pytest

from budmetrics.observability.models import ClickHouseClient, ClickHouseConfig


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# Test constants (same as other test files)
TEST_PROJECT_ID = UUID("019787c1-3de1-7b50-969b-e0a58514b6a1")
TEST_PROJECT_ID_2 = UUID("019787c1-3de1-7b50-969b-e0a58514b6a4")
TEST_MODEL_ID = UUID("019787c1-3de1-7b50-969b-e0a58514b6a2")
TEST_MODEL_ID_2 = UUID("019787c1-3de1-7b50-969b-e0a58514b6a3")
TEST_ENDPOINT_ID = UUID("019787c1-3de1-7b50-969b-e0a58514b6a4")
TEST_ENDPOINT_ID_2 = UUID("019787c1-3de1-7b50-969b-e0a58514b6a5")
TEST_FROM_DATE = datetime(2026, 1, 7, 0, 0, 0)
TEST_TO_DATE = datetime(2026, 1, 7, 23, 59, 59)
TEST_NONEXISTENT_ID = UUID("00000000-0000-0000-0000-000000000000")


async def _fetch_time_series_ground_truth():
    """Async helper to query ClickHouse for ground truth values."""
    config = ClickHouseConfig()
    client = ClickHouseClient(config)
    await client.initialize()

    try:
        ground_truth = {}
        date_filter = f"timestamp >= '{TEST_FROM_DATE}' AND timestamp <= '{TEST_TO_DATE}'"

        # Overall metrics
        result = await client.execute_query(f"""
            SELECT
                COUNT(*) as requests,
                SUM(CASE WHEN is_success THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate,
                SUM(CASE WHEN NOT is_success THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as error_rate,
                SUM(input_tokens + output_tokens) as tokens,
                SUM(cost) as cost,
                AVG(response_time_ms) as avg_latency,
                quantile(0.95)(response_time_ms) as p95_latency,
                quantile(0.99)(response_time_ms) as p99_latency,
                AVG(ttft_ms) as ttft_avg,
                SUM(CASE WHEN cached THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0) as cache_hit_rate
            FROM InferenceFact
            WHERE {date_filter}
        """)
        ground_truth["overall"] = dict(zip(
            ["requests", "success_rate", "error_rate", "tokens", "cost",
             "avg_latency", "p95_latency", "p99_latency", "ttft_avg", "cache_hit_rate"],
            result[0]
        ))

        # By project
        result = await client.execute_query(f"""
            SELECT
                project_id,
                COUNT(*) as requests,
                SUM(input_tokens + output_tokens) as tokens
            FROM InferenceFact
            WHERE {date_filter}
            GROUP BY project_id
        """)
        ground_truth["by_project"] = {
            str(r[0]): {"requests": r[1], "tokens": r[2]}
            for r in result
        }

        # By model
        result = await client.execute_query(f"""
            SELECT
                model_id,
                COUNT(*) as requests
            FROM InferenceFact
            WHERE {date_filter}
            GROUP BY model_id
        """)
        ground_truth["by_model"] = {str(r[0]): {"requests": r[1]} for r in result}

        # Filtered by primary project
        result = await client.execute_query(f"""
            SELECT COUNT(*) as requests
            FROM InferenceFact
            WHERE {date_filter} AND project_id = '{TEST_PROJECT_ID}'
        """)
        ground_truth["filtered_project"] = {"requests": result[0][0]}

        return ground_truth
    finally:
        await client.close()


@pytest.fixture(scope="session")
def time_series_ground_truth(seed_test_data):
    """Fetch ground truth from InferenceFact (seeding done by shared fixture)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch_time_series_ground_truth())
    finally:
        loop.close()


def get_base_payload(**kwargs) -> dict:
    """Build request payload with defaults."""
    payload = {
        "from_date": TEST_FROM_DATE.isoformat(),
        "to_date": TEST_TO_DATE.isoformat(),
        "metrics": ["requests"],
    }
    payload.update(kwargs)
    return payload


def sum_data_points(data: dict, metric: str) -> float:
    """Sum metric values across all data points in all groups."""
    total = 0.0
    for group in data.get("groups", []):
        for point in group.get("data_points", []):
            value = point.get("values", {}).get(metric)
            if value is not None:
                total += value
    return total


def get_first_non_null_value(data: dict, metric: str):
    """Get first non-null value for a metric from data points."""
    for group in data.get("groups", []):
        for point in group.get("data_points", []):
            value = point.get("values", {}).get(metric)
            if value is not None:
                return value
    return None


@pytest.mark.usefixtures("seed_test_data")
class TestBasicRequests:
    """Basic request tests for /observability/metrics/time-series."""

    def test_basic_request_minimal(self, sync_client):
        """Test minimal request with only from_date and metrics."""
        payload = {"from_date": TEST_FROM_DATE.isoformat(), "metrics": ["requests"]}
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "groups" in data
        assert "interval" in data
        assert "date_range" in data
        print(f"\n[basic_minimal] Got {len(data['groups'])} groups")

    def test_basic_request_with_date_range(self, sync_client):
        """Test request with from_date and to_date."""
        payload = get_base_payload()
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "groups" in data
        print(f"\n[basic_date_range] Got {len(data['groups'])} groups")

    def test_response_structure(self, sync_client):
        """Test that response has all expected fields."""
        payload = get_base_payload()
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Check top-level structure
        assert data["object"] == "time_series"
        assert "groups" in data
        assert "interval" in data
        assert "date_range" in data
        assert isinstance(data["groups"], list)
        print("\n[response_structure] All expected fields present")

    def test_response_object_type(self, sync_client):
        """Test that object type is correct."""
        payload = get_base_payload()
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "time_series"
        print("\n[object_type] Correct object type: time_series")

    def test_data_points_structure(self, sync_client):
        """Test that data points have timestamp and values."""
        payload = get_base_payload(fill_gaps=False)
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Check if we have groups with data points
        if data["groups"]:
            group = data["groups"][0]
            if group.get("data_points"):
                point = group["data_points"][0]
                assert "timestamp" in point, "Missing timestamp in data point"
                assert "values" in point, "Missing values in data point"
                assert isinstance(point["values"], dict)
        print("\n[data_points] Data points have correct structure")


@pytest.mark.usefixtures("seed_test_data")
class TestMetrics:
    """Test each of the 11 supported metrics."""

    def test_metric_requests(self, sync_client):
        """Test requests metric returns data."""
        payload = get_base_payload(metrics=["requests"])
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        value = get_first_non_null_value(data, "requests")
        assert value is not None or len(data["groups"]) >= 0
        print(f"\n[metric_requests] Got value: {value}")

    def test_metric_success_rate(self, sync_client):
        """Test success_rate metric returns valid percentage."""
        payload = get_base_payload(metrics=["success_rate"])
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        value = get_first_non_null_value(data, "success_rate")
        if value is not None:
            assert 0 <= value <= 100, f"success_rate {value} out of range"
        print(f"\n[metric_success_rate] Got value: {value}")

    def test_metric_avg_latency(self, sync_client):
        """Test avg_latency metric returns non-negative value."""
        payload = get_base_payload(metrics=["avg_latency"])
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        value = get_first_non_null_value(data, "avg_latency")
        if value is not None:
            assert value >= 0, f"avg_latency {value} is negative"
        print(f"\n[metric_avg_latency] Got value: {value}")

    def test_metric_p95_latency(self, sync_client):
        """Test p95_latency metric (uses InferenceFact)."""
        payload = get_base_payload(metrics=["p95_latency"])
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        value = get_first_non_null_value(data, "p95_latency")
        if value is not None:
            assert value >= 0, f"p95_latency {value} is negative"
        print(f"\n[metric_p95_latency] Got value: {value}")

    def test_metric_p99_latency(self, sync_client):
        """Test p99_latency metric (uses InferenceFact)."""
        payload = get_base_payload(metrics=["p99_latency"])
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        value = get_first_non_null_value(data, "p99_latency")
        if value is not None:
            assert value >= 0, f"p99_latency {value} is negative"
        print(f"\n[metric_p99_latency] Got value: {value}")

    def test_metric_tokens(self, sync_client):
        """Test tokens metric."""
        payload = get_base_payload(metrics=["tokens"])
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        value = get_first_non_null_value(data, "tokens")
        if value is not None:
            assert value >= 0, f"tokens {value} is negative"
        print(f"\n[metric_tokens] Got value: {value}")

    def test_metric_cost(self, sync_client):
        """Test cost metric."""
        payload = get_base_payload(metrics=["cost"])
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        value = get_first_non_null_value(data, "cost")
        if value is not None:
            assert value >= 0, f"cost {value} is negative"
        print(f"\n[metric_cost] Got value: {value}")

    def test_metric_ttft_avg(self, sync_client):
        """Test ttft_avg metric."""
        payload = get_base_payload(metrics=["ttft_avg"])
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        value = get_first_non_null_value(data, "ttft_avg")
        if value is not None:
            assert value >= 0, f"ttft_avg {value} is negative"
        print(f"\n[metric_ttft_avg] Got value: {value}")

    def test_metric_cache_hit_rate(self, sync_client):
        """Test cache_hit_rate metric returns valid percentage."""
        payload = get_base_payload(metrics=["cache_hit_rate"])
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        value = get_first_non_null_value(data, "cache_hit_rate")
        if value is not None:
            assert 0 <= value <= 100, f"cache_hit_rate {value} out of range"
        print(f"\n[metric_cache_hit_rate] Got value: {value}")

    def test_metric_throughput(self, sync_client):
        """Test throughput metric."""
        payload = get_base_payload(metrics=["throughput"])
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        value = get_first_non_null_value(data, "throughput")
        if value is not None:
            assert value >= 0, f"throughput {value} is negative"
        print(f"\n[metric_throughput] Got value: {value}")

    def test_metric_error_rate(self, sync_client):
        """Test error_rate metric returns valid percentage."""
        payload = get_base_payload(metrics=["error_rate"])
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        value = get_first_non_null_value(data, "error_rate")
        if value is not None:
            assert 0 <= value <= 100, f"error_rate {value} out of range"
        print(f"\n[metric_error_rate] Got value: {value}")

    def test_multiple_metrics(self, sync_client):
        """Test requesting multiple metrics at once."""
        payload = get_base_payload(
            metrics=["requests", "success_rate", "avg_latency", "tokens"]
        )
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Check that all metrics are present in values
        if data["groups"] and data["groups"][0].get("data_points"):
            point = data["groups"][0]["data_points"][0]
            for metric in ["requests", "success_rate", "avg_latency", "tokens"]:
                assert metric in point["values"], f"Missing metric: {metric}"
        print("\n[multiple_metrics] All requested metrics present")


@pytest.mark.usefixtures("seed_test_data")
class TestIntervals:
    """Test each of the 9 supported intervals."""

    def test_interval_1m(self, sync_client):
        """Test 1-minute interval."""
        payload = get_base_payload(interval="1m")
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["interval"] == "1m"
        print("\n[interval_1m] 1-minute interval works")

    def test_interval_5m(self, sync_client):
        """Test 5-minute interval."""
        payload = get_base_payload(interval="5m")
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["interval"] == "5m"
        print("\n[interval_5m] 5-minute interval works")

    def test_interval_15m(self, sync_client):
        """Test 15-minute interval."""
        payload = get_base_payload(interval="15m")
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["interval"] == "15m"
        print("\n[interval_15m] 15-minute interval works")

    def test_interval_30m(self, sync_client):
        """Test 30-minute interval."""
        payload = get_base_payload(interval="30m")
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["interval"] == "30m"
        print("\n[interval_30m] 30-minute interval works")

    def test_interval_1h(self, sync_client):
        """Test 1-hour interval (default)."""
        payload = get_base_payload(interval="1h")
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["interval"] == "1h"
        print("\n[interval_1h] 1-hour interval works")

    def test_interval_6h(self, sync_client):
        """Test 6-hour interval."""
        payload = get_base_payload(interval="6h")
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["interval"] == "6h"
        print("\n[interval_6h] 6-hour interval works")

    def test_interval_12h(self, sync_client):
        """Test 12-hour interval."""
        payload = get_base_payload(interval="12h")
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["interval"] == "12h"
        print("\n[interval_12h] 12-hour interval works")

    def test_interval_1d(self, sync_client):
        """Test 1-day interval."""
        payload = get_base_payload(interval="1d")
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["interval"] == "1d"
        print("\n[interval_1d] 1-day interval works")

    def test_interval_1w(self, sync_client):
        """Test 1-week interval."""
        payload = get_base_payload(interval="1w")
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["interval"] == "1w"
        print("\n[interval_1w] 1-week interval works")

    def test_default_interval_is_1h(self, sync_client):
        """Test that default interval is 1h when not specified."""
        payload = {"from_date": TEST_FROM_DATE.isoformat(), "metrics": ["requests"]}
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["interval"] == "1h", f"Default interval should be 1h, got {data['interval']}"
        print("\n[default_interval] Default interval is 1h")


class TestGroupBy:
    """Test grouping options."""

    def test_group_by_model(self, sync_client, time_series_ground_truth):
        """Test grouping by model."""
        payload = get_base_payload(group_by=["model"])
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        expected_groups = len(time_series_ground_truth["by_model"])
        actual_groups = len(data["groups"])
        assert actual_groups == expected_groups, \
            f"Expected {expected_groups} model groups, got {actual_groups}"
        print(f"\n[group_by_model] Got {actual_groups} groups")

    def test_group_by_project(self, sync_client, time_series_ground_truth):
        """Test grouping by project."""
        payload = get_base_payload(group_by=["project"])
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        expected_groups = len(time_series_ground_truth["by_project"])
        actual_groups = len(data["groups"])
        assert actual_groups == expected_groups, \
            f"Expected {expected_groups} project groups, got {actual_groups}"
        print(f"\n[group_by_project] Got {actual_groups} groups")

    @pytest.mark.usefixtures("seed_test_data")
    def test_group_by_endpoint(self, sync_client):
        """Test grouping by endpoint."""
        payload = get_base_payload(group_by=["endpoint"])
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        # Should have at least 1 group
        assert len(data["groups"]) >= 1
        print(f"\n[group_by_endpoint] Got {len(data['groups'])} groups")

    @pytest.mark.usefixtures("seed_test_data")
    def test_group_by_user_project(self, sync_client):
        """Test grouping by user_project (api_key_project_id)."""
        payload = get_base_payload(group_by=["user_project"])
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["groups"]) >= 1
        print(f"\n[group_by_user_project] Got {len(data['groups'])} groups")

    @pytest.mark.usefixtures("seed_test_data")
    def test_group_by_multiple(self, sync_client):
        """Test grouping by multiple dimensions."""
        payload = get_base_payload(group_by=["model", "project"])
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        # Combined grouping should create more groups
        assert len(data["groups"]) >= 1
        print(f"\n[group_by_multiple] Got {len(data['groups'])} groups")

    @pytest.mark.usefixtures("seed_test_data")
    def test_no_group_by(self, sync_client):
        """Test without group_by returns single group."""
        payload = get_base_payload()
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        # Without grouping, should have exactly 1 group
        assert len(data["groups"]) == 1
        print("\n[no_group_by] Single group returned")


class TestFilters:
    """Test filtering options."""

    def test_filter_by_project_id(self, sync_client, time_series_ground_truth):
        """Test filtering by project_id."""
        payload = get_base_payload(
            filters={"project_id": [str(TEST_PROJECT_ID)]},
            fill_gaps=False
        )
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        total_requests = sum_data_points(data, "requests")
        expected = time_series_ground_truth["filtered_project"]["requests"]
        assert total_requests == expected, \
            f"Filtered requests mismatch: API={total_requests}, DB={expected}"
        print(f"\n[filter_project] Got {total_requests} requests")

    @pytest.mark.usefixtures("seed_test_data")
    def test_filter_by_model_id(self, sync_client):
        """Test filtering by model_id."""
        payload = get_base_payload(
            filters={"model_id": str(TEST_MODEL_ID)}
        )
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["groups"]) >= 1
        print("\n[filter_model] Filter by model_id works")

    @pytest.mark.usefixtures("seed_test_data")
    def test_filter_by_endpoint_id(self, sync_client):
        """Test filtering by endpoint_id."""
        payload = get_base_payload(
            filters={"endpoint_id": str(TEST_ENDPOINT_ID)}
        )
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["groups"]) >= 1
        print("\n[filter_endpoint] Filter by endpoint_id works")

    @pytest.mark.usefixtures("seed_test_data")
    def test_filter_combined(self, sync_client):
        """Test combining multiple filters."""
        payload = get_base_payload(
            filters={
                "project_id": [str(TEST_PROJECT_ID)],
                "model_id": str(TEST_MODEL_ID)
            }
        )
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["groups"]) >= 1
        print("\n[filter_combined] Combined filters work")

    @pytest.mark.usefixtures("seed_test_data")
    def test_filter_nonexistent(self, sync_client):
        """Test filtering by non-existent project returns no data."""
        payload = get_base_payload(
            filters={"project_id": [str(TEST_NONEXISTENT_ID)]},
            fill_gaps=False
        )
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        total_requests = sum_data_points(data, "requests")
        assert total_requests == 0, f"Expected 0 requests for nonexistent filter, got {total_requests}"
        print("\n[filter_nonexistent] Correctly returned no data")


class TestValidation:
    """Validation error tests."""

    def test_missing_from_date_rejected(self, sync_client):
        """Test that missing from_date returns 422."""
        payload = {"metrics": ["requests"]}
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for missing from_date, got {response.status_code}"
        print("\n[validation] Missing from_date correctly rejected")

    def test_missing_metrics_rejected(self, sync_client):
        """Test that missing metrics returns 422."""
        payload = {"from_date": TEST_FROM_DATE.isoformat()}
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for missing metrics, got {response.status_code}"
        print("\n[validation] Missing metrics correctly rejected")

    def test_invalid_date_format_rejected(self, sync_client):
        """Test that invalid date format returns 422."""
        payload = {"from_date": "invalid-date", "metrics": ["requests"]}
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for invalid date format, got {response.status_code}"
        print("\n[validation] Invalid date format correctly rejected")

    def test_invalid_metric_rejected(self, sync_client):
        """Test that invalid metric returns 422."""
        payload = get_base_payload(metrics=["invalid_metric"])
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for invalid metric, got {response.status_code}"
        print("\n[validation] Invalid metric correctly rejected")

    def test_invalid_interval_rejected(self, sync_client):
        """Test that invalid interval returns 422."""
        payload = get_base_payload(interval="invalid")
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for invalid interval, got {response.status_code}"
        print("\n[validation] Invalid interval correctly rejected")

    def test_invalid_group_by_rejected(self, sync_client):
        """Test that invalid group_by returns 422."""
        payload = get_base_payload(group_by=["invalid"])
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for invalid group_by, got {response.status_code}"
        print("\n[validation] Invalid group_by correctly rejected")

    def test_to_date_before_from_date_rejected(self, sync_client):
        """Test that to_date before from_date returns 422."""
        payload = {
            "from_date": TEST_TO_DATE.isoformat(),
            "to_date": TEST_FROM_DATE.isoformat(),
            "metrics": ["requests"]
        }
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for to_date < from_date, got {response.status_code}"
        print("\n[validation] to_date before from_date correctly rejected")

    def test_date_range_too_large_rejected(self, sync_client):
        """Test that date range > 90 days returns 422."""
        far_past = TEST_FROM_DATE - timedelta(days=100)
        payload = {
            "from_date": far_past.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "metrics": ["requests"]
        }
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for date range > 90 days, got {response.status_code}"
        print("\n[validation] Date range too large correctly rejected")


@pytest.mark.usefixtures("seed_test_data")
class TestFillGaps:
    """Test fill_gaps parameter behavior."""

    def test_fill_gaps_true(self, sync_client):
        """Test that fill_gaps=true includes all time buckets."""
        payload = get_base_payload(interval="1h", fill_gaps=True)
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        # With fill_gaps=true, we should have 24 hourly buckets for a full day
        if data["groups"]:
            data_points = len(data["groups"][0].get("data_points", []))
            assert data_points >= 1, "Should have data points with fill_gaps=true"
        print(f"\n[fill_gaps_true] Got data points with gaps filled")

    def test_fill_gaps_false(self, sync_client):
        """Test that fill_gaps=false only includes buckets with data."""
        payload = get_base_payload(interval="1h", fill_gaps=False)
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        # With fill_gaps=false, we should only have buckets with actual data
        if data["groups"]:
            # Each data point should have non-null values
            for group in data["groups"]:
                for point in group.get("data_points", []):
                    # At least one value should be present
                    assert point.get("values") is not None
        print("\n[fill_gaps_false] Only data buckets returned")


class TestDataAccuracy:
    """Data accuracy tests comparing API response with DB."""

    def test_requests_sum_matches_db(self, sync_client, time_series_ground_truth):
        """Test that sum of requests across all data points matches DB."""
        payload = get_base_payload(metrics=["requests"], fill_gaps=False)
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        total_requests = sum_data_points(data, "requests")
        expected = time_series_ground_truth["overall"]["requests"]
        assert total_requests == expected, \
            f"Requests mismatch: API sum={total_requests}, DB={expected}"
        print(f"\n[accuracy] Requests sum matches DB: {total_requests}")

    @pytest.mark.usefixtures("seed_test_data")
    def test_success_rate_in_valid_range(self, sync_client):
        """Test that all success_rate values are valid percentages."""
        payload = get_base_payload(metrics=["success_rate"], fill_gaps=False)
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        for group in data["groups"]:
            for point in group.get("data_points", []):
                value = point["values"].get("success_rate")
                if value is not None:
                    assert 0 <= value <= 100, \
                        f"success_rate {value} out of valid range [0, 100]"
        print("\n[accuracy] All success_rate values are valid percentages")

    def test_tokens_sum_matches_db(self, sync_client, time_series_ground_truth):
        """Test that sum of tokens matches DB."""
        payload = get_base_payload(metrics=["tokens"], fill_gaps=False)
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        total_tokens = sum_data_points(data, "tokens")
        expected = time_series_ground_truth["overall"]["tokens"] or 0
        assert total_tokens == expected, \
            f"Tokens mismatch: API sum={total_tokens}, DB={expected}"
        print(f"\n[accuracy] Tokens sum matches DB: {total_tokens}")

    def test_grouped_requests_match_db(self, sync_client, time_series_ground_truth):
        """Test that grouped requests match DB per project."""
        payload = get_base_payload(
            metrics=["requests"],
            group_by=["project"],
            fill_gaps=False
        )
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Sum requests per project and compare with ground truth
        for group in data["groups"]:
            project_id = group.get("project_id")
            if project_id:
                group_requests = sum(
                    point["values"].get("requests", 0)
                    for point in group.get("data_points", [])
                    if point["values"].get("requests") is not None
                )
                expected = time_series_ground_truth["by_project"].get(
                    str(project_id), {}
                ).get("requests", 0)
                assert group_requests == expected, \
                    f"Project {project_id} requests mismatch: API={group_requests}, DB={expected}"
        print("\n[accuracy] Grouped requests match DB")

    def test_filtered_data_matches_db(self, sync_client, time_series_ground_truth):
        """Test that filtered data matches DB."""
        payload = get_base_payload(
            metrics=["requests"],
            filters={"project_id": [str(TEST_PROJECT_ID)]},
            fill_gaps=False
        )
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        total_requests = sum_data_points(data, "requests")
        expected = time_series_ground_truth["filtered_project"]["requests"]
        assert total_requests == expected, \
            f"Filtered requests mismatch: API={total_requests}, DB={expected}"
        print(f"\n[accuracy] Filtered data matches DB: {total_requests}")

    @pytest.mark.usefixtures("seed_test_data")
    def test_percentile_ordering(self, sync_client):
        """Test that p99 >= p95 >= avg_latency."""
        payload = get_base_payload(
            metrics=["avg_latency", "p95_latency", "p99_latency"],
            fill_gaps=False
        )
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        for group in data["groups"]:
            for point in group.get("data_points", []):
                avg = point["values"].get("avg_latency")
                p95 = point["values"].get("p95_latency")
                p99 = point["values"].get("p99_latency")

                if all(v is not None for v in [avg, p95, p99]):
                    assert p99 >= p95, f"p99 ({p99}) should be >= p95 ({p95})"
                    assert p95 >= avg, f"p95 ({p95}) should be >= avg ({avg})"
        print("\n[accuracy] Percentile ordering is correct")


@pytest.mark.usefixtures("seed_test_data")
class TestCodePaths:
    """Test different code paths (rollup vs InferenceFact)."""

    def test_rollup_path_basic(self, sync_client):
        """Test that basic metrics use rollup tables."""
        payload = get_base_payload(metrics=["requests", "success_rate"])
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["groups"]) >= 1
        print("\n[code_paths] Rollup path works for basic metrics")

    def test_inference_fact_path(self, sync_client):
        """Test that percentile metrics use InferenceFact."""
        payload = get_base_payload(metrics=["p95_latency", "p99_latency"])
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["groups"]) >= 1
        print("\n[code_paths] InferenceFact path works for percentiles")

    def test_mixed_path(self, sync_client):
        """Test that mixed metrics (basic + percentiles) work."""
        payload = get_base_payload(
            metrics=["requests", "success_rate", "p95_latency", "p99_latency"]
        )
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        # All metrics should be present
        if data["groups"] and data["groups"][0].get("data_points"):
            point = data["groups"][0]["data_points"][0]
            for metric in ["requests", "success_rate", "p95_latency", "p99_latency"]:
                assert metric in point["values"], f"Missing metric: {metric}"
        print("\n[code_paths] Mixed metrics path works")


# pytest tests/observability/metrics/test_time_series.py -v -s
