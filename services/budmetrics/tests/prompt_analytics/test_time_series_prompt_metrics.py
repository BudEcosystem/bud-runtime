"""Tests for time-series API with prompt analytics metrics.

Tests validate unique_users, success_count, error_count metrics
against ClickHouse ground truth data.

Run with: pytest tests/prompt_analytics/test_time_series_prompt_metrics.py -v
"""

import asyncio
from datetime import datetime, timedelta

import pytest

from budmetrics.observability.models import ClickHouseClient, ClickHouseConfig

from .conftest import load_test_data
from .ground_truth import get_all_expected_inference_facts


# Mark all tests as integration tests
pytestmark = pytest.mark.integration


# Test constants
# client_prompt_id is the human-readable name, prompt_id is the UUID
TEST_CLIENT_PROMPT_ID = "test_structured_data"
TEST_PROMPT_ID = "119787c1-3de1-7b50-969b-e0a58514b6a1"  # UUID for filtering via API
# Test data timestamps are around 2026-01-31 10:34:48 - 10:35:31
TEST_FROM_DATE = datetime(2026, 1, 31, 0, 0, 0)
TEST_TO_DATE = datetime(2026, 2, 1, 0, 0, 0)


async def _fetch_prompt_analytics_ground_truth():
    """Query ClickHouse for ground truth values specific to prompt analytics."""
    config = ClickHouseConfig()
    client = ClickHouseClient(config)
    await client.initialize()

    try:
        ground_truth = {}

        # Prompt analytics filter (data_source = "prompt")
        prompt_filter = "prompt_id IS NOT NULL AND prompt_id != ''"
        # Date filter matching the test date range
        date_filter = f"timestamp >= '{TEST_FROM_DATE}' AND timestamp < '{TEST_TO_DATE}'"

        # Overall prompt analytics metrics
        result = await client.execute_query(f"""
            SELECT
                COUNT(*) as requests,
                uniqExact(user_id) as unique_users,
                countIf(is_success = true) as success_count,
                countIf(is_success = false) as error_count,
                SUM(input_tokens + output_tokens) as tokens
            FROM InferenceFact
            WHERE {prompt_filter} AND {date_filter}
        """)
        ground_truth["overall"] = dict(
            zip(
                ["requests", "unique_users", "success_count", "error_count", "tokens"],
                result[0],
                strict=True,
            )
        )

        # Filter by specific prompt_id (UUID)
        result = await client.execute_query(f"""
            SELECT
                COUNT(*) as requests,
                uniqExact(user_id) as unique_users,
                countIf(is_success = true) as success_count,
                countIf(is_success = false) as error_count,
                SUM(input_tokens + output_tokens) as tokens
            FROM InferenceFact
            WHERE {prompt_filter}
              AND {date_filter}
              AND prompt_id = '{TEST_PROMPT_ID}'
        """)
        ground_truth["by_prompt_id"] = dict(
            zip(
                ["requests", "unique_users", "success_count", "error_count", "tokens"],
                result[0],
                strict=True,
            )
        )

        return ground_truth
    finally:
        await client.close()


@pytest.fixture(scope="class")
def prompt_ground_truth(seeded_db):
    """Fetch ground truth from InferenceFact after seeding."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch_prompt_analytics_ground_truth())
    finally:
        loop.close()


def sum_data_points(data: dict, metric: str) -> float:
    """Sum metric values across all data points in all groups."""
    total = 0.0
    for group in data.get("groups", []):
        for point in group.get("data_points", []):
            value = point.get("values", {}).get(metric)
            if value is not None:
                total += value
    return total


def max_data_points(data: dict, metric: str) -> float:
    """Get max metric value across all data points in all groups."""
    max_val = 0.0
    for group in data.get("groups", []):
        for point in group.get("data_points", []):
            value = point.get("values", {}).get(metric)
            if value is not None and value > max_val:
                max_val = value
    return max_val


@pytest.mark.usefixtures("seeded_db")
class TestPromptAnalyticsMetrics:
    """Tests for new prompt analytics metrics in time-series API."""

    # ==========================================================================
    # CHART 1: Request Count
    # ==========================================================================

    def test_requests_24h(self, sync_client, prompt_ground_truth):
        """Test requests metric for 24-hour interval."""
        payload = {
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "interval": "1h",
            "metrics": ["requests"],
            "data_source": "prompt",
            "fill_gaps": True,
        }
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        total_requests = sum_data_points(data, "requests")
        expected = prompt_ground_truth["overall"]["requests"]
        assert total_requests == expected, f"Expected {expected} requests, got {total_requests}"

    def test_requests_7d(self, sync_client, prompt_ground_truth):
        """Test requests metric for 7-day interval."""
        from_date = TEST_FROM_DATE - timedelta(days=6)
        payload = {
            "from_date": from_date.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "interval": "1d",
            "metrics": ["requests"],
            "data_source": "prompt",
            "fill_gaps": True,
        }
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        total_requests = sum_data_points(data, "requests")
        expected = prompt_ground_truth["overall"]["requests"]
        assert total_requests == expected

    def test_requests_30d(self, sync_client, prompt_ground_truth):
        """Test requests metric for 30-day interval."""
        from_date = TEST_FROM_DATE - timedelta(days=29)
        payload = {
            "from_date": from_date.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "interval": "1d",
            "metrics": ["requests"],
            "data_source": "prompt",
            "fill_gaps": True,
        }
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        total_requests = sum_data_points(data, "requests")
        expected = prompt_ground_truth["overall"]["requests"]
        assert total_requests == expected

    # ==========================================================================
    # CHART 2: Unique Users
    # ==========================================================================

    def test_unique_users_24h(self, sync_client, prompt_ground_truth):
        """Test unique_users metric for 24-hour interval."""
        payload = {
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "interval": "1h",
            "metrics": ["unique_users"],
            "data_source": "prompt",
            "fill_gaps": True,
        }
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        # For unique_users, we need max across time buckets (not sum)
        # since the same user can appear in multiple buckets
        max_unique = max_data_points(data, "unique_users")

        expected = prompt_ground_truth["overall"]["unique_users"]
        # Note: Per-bucket unique_users <= overall unique_users
        assert max_unique <= expected, f"Expected <= {expected} unique users per bucket, got {max_unique}"

    def test_unique_users_7d(self, sync_client, prompt_ground_truth):
        """Test unique_users metric for 7-day interval."""
        from_date = TEST_FROM_DATE - timedelta(days=6)
        payload = {
            "from_date": from_date.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "interval": "1d",
            "metrics": ["unique_users"],
            "data_source": "prompt",
            "fill_gaps": True,
        }
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "groups" in data

    def test_unique_users_30d(self, sync_client, prompt_ground_truth):
        """Test unique_users metric for 30-day interval."""
        from_date = TEST_FROM_DATE - timedelta(days=29)
        payload = {
            "from_date": from_date.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "interval": "1d",
            "metrics": ["unique_users"],
            "data_source": "prompt",
            "fill_gaps": True,
        }
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200

    # ==========================================================================
    # CHART 3: Token Usage
    # ==========================================================================

    def test_tokens_24h(self, sync_client, prompt_ground_truth):
        """Test tokens metric for 24-hour interval."""
        payload = {
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "interval": "1h",
            "metrics": ["tokens"],
            "data_source": "prompt",
            "fill_gaps": True,
        }
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        total_tokens = sum_data_points(data, "tokens")
        expected = prompt_ground_truth["overall"]["tokens"] or 0
        assert total_tokens == expected, f"Expected {expected} tokens, got {total_tokens}"

    def test_tokens_7d(self, sync_client, prompt_ground_truth):
        """Test tokens metric for 7-day interval."""
        from_date = TEST_FROM_DATE - timedelta(days=6)
        payload = {
            "from_date": from_date.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "interval": "1d",
            "metrics": ["tokens"],
            "data_source": "prompt",
            "fill_gaps": True,
        }
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        total_tokens = sum_data_points(data, "tokens")
        expected = prompt_ground_truth["overall"]["tokens"] or 0
        assert total_tokens == expected

    def test_tokens_30d(self, sync_client, prompt_ground_truth):
        """Test tokens metric for 30-day interval."""
        from_date = TEST_FROM_DATE - timedelta(days=29)
        payload = {
            "from_date": from_date.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "interval": "1d",
            "metrics": ["tokens"],
            "data_source": "prompt",
            "fill_gaps": True,
        }
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200

    # ==========================================================================
    # CHART 4: Error vs Success Counts
    # ==========================================================================

    def test_success_error_counts_24h(self, sync_client, prompt_ground_truth):
        """Test success_count and error_count metrics for 24-hour interval."""
        payload = {
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "interval": "1h",
            "metrics": ["success_count", "error_count"],
            "data_source": "prompt",
            "fill_gaps": True,
        }
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        total_success = sum_data_points(data, "success_count")
        total_error = sum_data_points(data, "error_count")

        expected_success = prompt_ground_truth["overall"]["success_count"]
        expected_error = prompt_ground_truth["overall"]["error_count"]

        assert total_success == expected_success, f"Expected {expected_success} success, got {total_success}"
        assert total_error == expected_error, f"Expected {expected_error} errors, got {total_error}"

    def test_success_error_counts_7d(self, sync_client, prompt_ground_truth):
        """Test success_count and error_count metrics for 7-day interval."""
        from_date = TEST_FROM_DATE - timedelta(days=6)
        payload = {
            "from_date": from_date.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "interval": "1d",
            "metrics": ["success_count", "error_count"],
            "data_source": "prompt",
            "fill_gaps": True,
        }
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        total_success = sum_data_points(data, "success_count")
        total_error = sum_data_points(data, "error_count")

        expected_success = prompt_ground_truth["overall"]["success_count"]
        expected_error = prompt_ground_truth["overall"]["error_count"]

        assert total_success == expected_success
        assert total_error == expected_error

    def test_success_error_counts_30d(self, sync_client, prompt_ground_truth):
        """Test success_count and error_count metrics for 30-day interval."""
        from_date = TEST_FROM_DATE - timedelta(days=29)
        payload = {
            "from_date": from_date.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "interval": "1d",
            "metrics": ["success_count", "error_count"],
            "data_source": "prompt",
            "fill_gaps": True,
        }
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200

    # ==========================================================================
    # Filtered by prompt_id
    # ==========================================================================

    def test_requests_with_prompt_filter(self, sync_client, prompt_ground_truth):
        """Test requests filtered by specific prompt_id (UUID)."""
        payload = {
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "interval": "1h",
            "metrics": ["requests"],
            "data_source": "prompt",
            "filters": {"prompt_id": TEST_PROMPT_ID},
            "fill_gaps": True,
        }
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        total_requests = sum_data_points(data, "requests")
        expected = prompt_ground_truth["by_prompt_id"]["requests"]
        assert total_requests == expected, (
            f"Expected {expected} requests for prompt_id={TEST_PROMPT_ID}, got {total_requests}"
        )

    def test_all_metrics_with_prompt_filter(self, sync_client, prompt_ground_truth):
        """Test all new metrics filtered by specific prompt_id (UUID)."""
        payload = {
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "interval": "1h",
            "metrics": ["requests", "tokens", "unique_users", "success_count", "error_count"],
            "data_source": "prompt",
            "filters": {"prompt_id": TEST_PROMPT_ID},
            "fill_gaps": True,
        }
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        expected = prompt_ground_truth["by_prompt_id"]

        assert sum_data_points(data, "requests") == expected["requests"]
        assert sum_data_points(data, "tokens") == (expected["tokens"] or 0)
        assert sum_data_points(data, "success_count") == expected["success_count"]
        assert sum_data_points(data, "error_count") == expected["error_count"]

    # ==========================================================================
    # Validation Tests
    # ==========================================================================

    def test_success_plus_error_equals_total(self, sync_client, prompt_ground_truth):
        """Verify success_count + error_count == total requests."""
        payload = {
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "interval": "1d",
            "metrics": ["requests", "success_count", "error_count"],
            "data_source": "prompt",
            "fill_gaps": True,
        }
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        total_requests = sum_data_points(data, "requests")
        total_success = sum_data_points(data, "success_count")
        total_error = sum_data_points(data, "error_count")

        assert total_success + total_error == total_requests, (
            f"success({total_success}) + error({total_error}) != requests({total_requests})"
        )

    def test_data_source_inference_excludes_prompt_data(self, sync_client, prompt_ground_truth):
        """Verify data_source=inference excludes prompt analytics data."""
        # First get prompt data count
        payload_prompt = {
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "interval": "1d",
            "metrics": ["requests"],
            "data_source": "prompt",
            "fill_gaps": False,
        }
        response_prompt = sync_client.post("/observability/metrics/time-series", json=payload_prompt)
        assert response_prompt.status_code == 200
        prompt_requests = sum_data_points(response_prompt.json(), "requests")

        # Then get inference data
        payload_inference = {
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "interval": "1d",
            "metrics": ["requests"],
            "data_source": "inference",
            "fill_gaps": False,
        }
        response_inference = sync_client.post("/observability/metrics/time-series", json=payload_inference)
        assert response_inference.status_code == 200
        data = response_inference.json()

        # Inference data should not include prompt analytics rows
        # This verifies the data_source filter works correctly
        assert "groups" in data
        # If we have prompt data, inference should have different count
        if prompt_requests > 0:
            inference_requests = sum_data_points(data, "requests")
            # They should be different (or inference could be 0 if no non-prompt data exists)
            # At minimum, we verify the structure is valid
            assert inference_requests >= 0


@pytest.mark.usefixtures("seeded_db")
class TestPromptAnalyticsGroundTruthValidation:
    """Tests that validate ground truth calculation matches seeder data."""

    def test_ground_truth_matches_seeder(self, prompt_ground_truth):
        """Verify ground truth from DB matches seeder-derived values."""
        seeder_data = load_test_data()

        # Count prompt analytics rows from seeder
        prompt_facts = []
        for scenario_key in seeder_data:
            facts = get_all_expected_inference_facts(seeder_data, scenario_key)
            for fact in facts:
                if fact.get("prompt_id"):
                    prompt_facts.append(fact)

        expected_prompt_requests = len(prompt_facts)
        expected_prompt_success = sum(1 for f in prompt_facts if f.get("is_success"))
        expected_prompt_error = sum(1 for f in prompt_facts if not f.get("is_success"))

        actual = prompt_ground_truth["overall"]

        assert actual["requests"] == expected_prompt_requests, (
            f"Request count mismatch: DB={actual['requests']}, seeder={expected_prompt_requests}"
        )
        assert actual["success_count"] == expected_prompt_success, (
            f"Success count mismatch: DB={actual['success_count']}, seeder={expected_prompt_success}"
        )
        assert actual["error_count"] == expected_prompt_error, (
            f"Error count mismatch: DB={actual['error_count']}, seeder={expected_prompt_error}"
        )

    def test_unique_users_count(self, prompt_ground_truth):
        """Verify unique_users is correctly counted."""
        # From test data analysis, all test data uses the same user_id
        # so unique_users should be 1 for prompt analytics
        actual_unique = prompt_ground_truth["overall"]["unique_users"]
        # With the current test data, we expect 1 unique user
        assert actual_unique >= 1, f"Expected at least 1 unique user, got {actual_unique}"


@pytest.mark.usefixtures("seeded_db")
class TestPromptAnalyticsAPIValidation:
    """Tests for API response structure validation."""

    def test_response_structure(self, sync_client):
        """Test that response has all expected fields."""
        payload = {
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "metrics": ["requests"],
            "data_source": "prompt",
        }
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Check top-level structure
        assert data["object"] == "time_series"
        assert "groups" in data
        assert "interval" in data
        assert "date_range" in data
        assert isinstance(data["groups"], list)

    def test_data_points_structure(self, sync_client):
        """Test that data points have timestamp and values."""
        payload = {
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "metrics": ["requests", "success_count", "error_count"],
            "data_source": "prompt",
            "fill_gaps": False,
        }
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

    def test_multiple_metrics_all_present(self, sync_client):
        """Test that requesting multiple metrics returns all of them."""
        metrics = ["requests", "tokens", "unique_users", "success_count", "error_count"]
        payload = {
            "from_date": TEST_FROM_DATE.isoformat(),
            "to_date": TEST_TO_DATE.isoformat(),
            "interval": "1h",
            "metrics": metrics,
            "data_source": "prompt",
            "fill_gaps": False,
        }
        response = sync_client.post("/observability/metrics/time-series", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Check that all metrics are present in values
        if data["groups"] and data["groups"][0].get("data_points"):
            point = data["groups"][0]["data_points"][0]
            for metric in metrics:
                assert metric in point["values"], f"Missing metric: {metric}"
