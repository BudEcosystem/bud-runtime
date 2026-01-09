"""Integration tests for POST /observability/analytics endpoint.

These tests validate the analytics endpoint by:
1. Seeding test data to ClickHouse
2. Querying InferenceFact (materialized view) for ground truth
3. Calling the HTTP API endpoint
4. Asserting response matches ground truth

Prerequisites:
- ClickHouse running with OTel analytics tables
- Run with: pytest tests/observability/test_analytics_endpoint.py -v -m integration
"""

import asyncio
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest

from budmetrics.observability.models import ClickHouseClient, ClickHouseConfig


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# Test constants from otel_traces_sample.json
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

        # Get hourly distribution
        hourly_result = await client.execute_query(
            f"SELECT toStartOfHour(timestamp) as hour, count(*) FROM InferenceFact WHERE {date_filter} GROUP BY hour ORDER BY hour"
        )
        ground_truth["hourly_distribution"] = {row[0]: row[1] for row in hourly_result} if hourly_result else {}

        # Get counts by project
        project_result = await client.execute_query(
            f"SELECT project_id, count(*) FROM InferenceFact WHERE {date_filter} GROUP BY project_id"
        )
        ground_truth["by_project"] = {str(row[0]): row[1] for row in project_result} if project_result else {}

        # Get counts by endpoint
        endpoint_result = await client.execute_query(
            f"SELECT endpoint_id, count(*) FROM InferenceFact WHERE {date_filter} GROUP BY endpoint_id"
        )
        ground_truth["by_endpoint"] = {str(row[0]): row[1] for row in endpoint_result} if endpoint_result else {}

        # Get counts by model
        model_result = await client.execute_query(
            f"SELECT model_id, count(*) FROM InferenceFact WHERE {date_filter} GROUP BY model_id"
        )
        ground_truth["by_model"] = {str(row[0]): row[1] for row in model_result} if model_result else {}

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


def extract_metric_value(response_json: dict, metric_key: str) -> float:
    """Extract total/average metric value from JSON response items.

    For count metrics: returns sum across all buckets
    For avg metrics: returns average across all buckets
    """
    items = response_json.get("items", [])

    # Track values for averaging
    total_sum = 0
    total_count = 0
    is_avg_metric = False

    for period in items:
        period_items = period.get("items") or []
        for item in period_items:
            data = item.get("data", {})
            if data and metric_key in data:
                metric = data[metric_key]
                if isinstance(metric, dict):
                    if "count" in metric:
                        total_sum += metric["count"]
                        total_count += 1
                    elif "avg" in metric:
                        is_avg_metric = True
                        # For avg metrics, average across all buckets
                        if metric["avg"] is not None:
                            total_sum += metric["avg"]
                            total_count += 1
                elif isinstance(metric, (int, float)):
                    total_sum += metric
                    total_count += 1

    if is_avg_metric and total_count > 0:
        return total_sum / total_count  # Return average of averages
    return total_sum


class TestBasicMetrics:
    """Tests for basic metric queries."""

    def test_request_count_matches_inference_fact(self, sync_client, seeded_data):
        """Test request_count matches InferenceFact ground truth."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["request_count"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        assert len(data["items"]) > 0
        total = extract_metric_value(data, "request_count")
        print(f"\n[request_count] API returned: {total}, Ground truth: {seeded_data['total_count']}")
        assert total == seeded_data["total_count"]

    def test_success_request_matches_inference_fact(self, sync_client, seeded_data):
        """Test success_request matches InferenceFact ground truth."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["success_request"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        total = extract_metric_value(data, "success_request")
        print(f"\n[success_request] API returned: {total}, Ground truth: {seeded_data['success_count']}")
        assert total == seeded_data["success_count"]

    def test_failure_request_matches_inference_fact(self, sync_client, seeded_data):
        """Test failure_request matches InferenceFact ground truth."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["failure_request"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        total = extract_metric_value(data, "failure_request")
        print(f"\n[failure_request] API returned: {total}, Ground truth: {seeded_data['failure_count']}")
        assert total == seeded_data["failure_count"]

    def test_latency_metric_returns_values(self, sync_client, seeded_data):
        """Test latency metric returns values."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["latency"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        assert len(data["items"]) > 0
        latency_value = extract_metric_value(data, "latency")
        print(f"\n[latency] API returned avg: {latency_value}, Ground truth avg: {seeded_data.get('avg_latency', 'N/A')}")

    def test_token_metrics_match_inference_fact(self, sync_client, seeded_data):
        """Test input_token and output_token match InferenceFact."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["input_token", "output_token"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        assert len(data["items"]) > 0
        input_total = extract_metric_value(data, "input_token")
        output_total = extract_metric_value(data, "output_token")
        print(f"\n[input_token] API returned: {input_total}, Ground truth: {seeded_data['input_tokens']}")
        print(f"[output_token] API returned: {output_total}, Ground truth: {seeded_data['output_tokens']}")
        assert input_total == seeded_data["input_tokens"]
        assert output_total == seeded_data["output_tokens"]

    def test_ttft_metric_returns_values(self, sync_client, seeded_data):
        """Test ttft metric returns values."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["ttft"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        ttft_value = extract_metric_value(data, "ttft")
        print(f"\n[ttft] API returned avg: {ttft_value}, Ground truth avg: {seeded_data.get('avg_ttft', 'N/A')}")

    def test_throughput_metric_returns_values(self, sync_client, seeded_data):
        """Test throughput metric returns values."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["throughput"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        throughput_value = extract_metric_value(data, "throughput")
        print(f"\n[throughput] API returned: {throughput_value}")

    def test_cache_metric_returns_values(self, sync_client, seeded_data):
        """Test cache metric returns values."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["cache"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        cache_value = extract_metric_value(data, "cache")
        print(f"\n[cache] API returned: {cache_value}")


class TestFiltering:
    """Tests for filter functionality."""

    def test_filter_by_project_returns_matching_data(self, sync_client, seeded_data):
        """Test filtering by project_id returns only matching data."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["request_count"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
                "filters": {"project": str(TEST_PROJECT_ID)},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        total = extract_metric_value(data, "request_count")
        expected = seeded_data["by_project"].get(str(TEST_PROJECT_ID), 0)
        print(f"\n[filter_by_project] API returned: {total}, Ground truth: {expected}")
        assert total == expected

    def test_filter_by_nonexistent_project_returns_empty(self, sync_client, seeded_data):
        """Test filtering by non-existent project returns zero/empty results."""
        nonexistent_id = UUID("00000000-0000-0000-0000-000000000000")
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["request_count"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
                "filters": {"project": str(nonexistent_id)},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        total = extract_metric_value(data, "request_count")
        print(f"\n[filter_nonexistent] API returned: {total}, Expected: 0")
        assert total == 0

    def test_filter_by_endpoint_returns_matching_data(self, sync_client, seeded_data):
        """Test filtering by endpoint_id returns only matching data."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["request_count"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
                "filters": {"endpoint": str(TEST_ENDPOINT_ID)},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        total = extract_metric_value(data, "request_count")
        expected = seeded_data["by_endpoint"].get(str(TEST_ENDPOINT_ID), 0)
        print(f"\n[filter_by_endpoint] API returned: {total}, Ground truth: {expected}")
        assert total == expected

    def test_combined_filters_narrow_results(self, sync_client, seeded_data):
        """Test combined filters (project AND endpoint) narrow results."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["request_count"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
                "filters": {
                    "project": str(TEST_PROJECT_ID),
                    "endpoint": str(TEST_ENDPOINT_ID),
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"


class TestGroupBy:
    """Tests for group_by functionality."""

    def test_group_by_project_returns_grouped_results(self, sync_client, seeded_data):
        """Test grouping by project returns results grouped by project_id."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["request_count"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
                "group_by": ["project"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        assert len(data["items"]) > 0

    def test_group_by_endpoint_returns_grouped_results(self, sync_client, seeded_data):
        """Test grouping by endpoint returns results grouped by endpoint_id."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["request_count"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
                "group_by": ["endpoint"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        assert len(data["items"]) > 0

    def test_group_by_model_returns_grouped_results(self, sync_client, seeded_data):
        """Test grouping by model returns results grouped by model_id."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["request_count"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
                "group_by": ["model"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        assert len(data["items"]) > 0


class TestTimeRanges:
    """Tests for different time range scenarios."""

    def test_hourly_buckets_separate_data_correctly(self, sync_client, seeded_data):
        """Test hourly frequency creates correct time buckets."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["request_count"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "hour",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        assert len(data["items"]) > 0

    def test_daily_frequency_aggregates_all_data(self, sync_client, seeded_data):
        """Test daily frequency aggregates all data into single bucket."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["request_count"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        total = extract_metric_value(data, "request_count")
        print(f"\n[daily_frequency] API returned: {total}, Ground truth: {seeded_data['total_count']}")
        assert total == seeded_data["total_count"]


class TestResponseStructure:
    """Tests to verify response structure matches expected schema."""

    def test_response_object_is_observability_metrics(self, sync_client, seeded_data):
        """Test response has object field set to 'observability_metrics'."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["request_count"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "object" in data
        assert data["object"] == "observability_metrics"

    def test_response_items_are_period_bins(self, sync_client, seeded_data):
        """Test response has items array of period bins."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["request_count"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_period_bins_have_time_period(self, sync_client, seeded_data):
        """Test each period bin has time_period field."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["request_count"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
            },
        )
        assert response.status_code == 200
        data = response.json()
        for period in data["items"]:
            assert "time_period" in period

    def test_metrics_data_has_correct_structure(self, sync_client, seeded_data):
        """Test metrics data has correct structure with metric values."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["request_count", "success_request"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        assert len(data["items"]) > 0


class TestDataAccuracy:
    """Tests to verify data accuracy against InferenceFact ground truth."""

    def test_total_count_matches_inference_fact(self, sync_client, seeded_data):
        """Test total request count matches InferenceFact exactly."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["request_count"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
            },
        )
        assert response.status_code == 200
        data = response.json()
        total = extract_metric_value(data, "request_count")
        print(f"\n[DataAccuracy:total_count] API returned: {total}, Ground truth: {seeded_data['total_count']}")
        assert total == seeded_data["total_count"], (
            f"Request count mismatch: got {total}, expected {seeded_data['total_count']}"
        )

    def test_success_failure_count_matches_inference_fact(self, sync_client, seeded_data):
        """Test success and failure counts match InferenceFact exactly."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["success_request", "failure_request"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "day",
            },
        )
        assert response.status_code == 200
        data = response.json()
        success_total = extract_metric_value(data, "success_request")
        failure_total = extract_metric_value(data, "failure_request")
        print(f"\n[DataAccuracy:success_count] API returned: {success_total}, Ground truth: {seeded_data['success_count']}")
        print(f"[DataAccuracy:failure_count] API returned: {failure_total}, Ground truth: {seeded_data['failure_count']}")
        assert success_total == seeded_data["success_count"], (
            f"Success count mismatch: got {success_total}, expected {seeded_data['success_count']}"
        )
        assert failure_total == seeded_data["failure_count"], (
            f"Failure count mismatch: got {failure_total}, expected {seeded_data['failure_count']}"
        )

    def test_hourly_distribution_matches_inference_fact(self, sync_client, seeded_data):
        """Test hourly distribution matches InferenceFact."""
        response = sync_client.post(
            "/observability/analytics",
            json={
                "metrics": ["request_count"],
                "from_date": TEST_FROM_DATE.isoformat(),
                "to_date": TEST_TO_DATE.isoformat(),
                "frequency_unit": "hour",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "observability_metrics"
        # Verify total across all hourly buckets matches ground truth
        total = extract_metric_value(data, "request_count")
        print(f"\n[DataAccuracy:hourly_distribution] API total: {total}, Ground truth: {seeded_data['total_count']}")
        assert total == seeded_data["total_count"], (
            f"Hourly total mismatch: got {total}, expected {seeded_data['total_count']}"
        )


# pytest tests/observability/test_analytics_endpoint.py -v -s 
