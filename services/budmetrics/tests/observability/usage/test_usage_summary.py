"""Tests for GET /observability/usage/summary endpoint.

These tests validate the usage summary API by:
1. Testing all query parameters (user_id, project_id, start_date, end_date)
2. Verifying response structure matches expected schema
3. Comparing values against InferenceFact ground truth

Run with: pytest tests/observability/usage/test_usage_summary.py -v -s
"""

import asyncio
from datetime import datetime, timedelta
from uuid import UUID

import pytest

from budmetrics.observability.models import ClickHouseClient, ClickHouseConfig


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# Test constants (from seeder data)
TEST_PROJECT_ID = UUID("019787c1-3de1-7b50-969b-e0a58514b6a1")
TEST_USER_ID = UUID("019b971a-4a01-7000-a001-a10000000002")
TEST_FROM_DATE = datetime(2026, 1, 7, 0, 0, 0)
TEST_TO_DATE = datetime(2026, 1, 7, 23, 59, 59)
TEST_NONEXISTENT_ID = UUID("00000000-0000-0000-0000-000000000000")


def _empty_summary() -> dict:
    """Return empty summary structure."""
    return {
        "request_count": 0,
        "success_count": 0,
        "total_cost": 0.0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    }


def _row_to_dict(row) -> dict:
    """Convert a query result row to summary dict."""
    return {
        "request_count": row[0] or 0,
        "success_count": row[1] or 0,
        "total_cost": float(row[2] or 0),
        "total_input_tokens": row[3] or 0,
        "total_output_tokens": row[4] or 0,
    }


async def _fetch_usage_summary_ground_truth():
    """Async helper to query ClickHouse for ground truth values."""
    config = ClickHouseConfig()
    client = ClickHouseClient(config)
    await client.initialize()

    try:
        ground_truth = {}
        date_filter = f"timestamp >= '{TEST_FROM_DATE}' AND timestamp <= '{TEST_TO_DATE}'"

        # Base SELECT clause for all queries
        select_clause = """
            SELECT
                COUNT(*) as request_count,
                SUM(CASE WHEN is_success THEN 1 ELSE 0 END) as success_count,
                SUM(COALESCE(cost, 0)) as total_cost,
                SUM(COALESCE(input_tokens, 0)) as total_input_tokens,
                SUM(COALESCE(output_tokens, 0)) as total_output_tokens
            FROM InferenceFact
        """

        # 1. Overall totals (no filters)
        result = await client.execute_query(f"""
            {select_clause}
            WHERE {date_filter}
        """)
        ground_truth["overall"] = _row_to_dict(result[0]) if result and result[0][0] else _empty_summary()

        # 2. By user_id
        result = await client.execute_query(f"""
            {select_clause}
            WHERE {date_filter} AND user_id = '{TEST_USER_ID}'
        """)
        ground_truth["by_user"] = _row_to_dict(result[0]) if result and result[0][0] else _empty_summary()

        # 3. By project_id
        result = await client.execute_query(f"""
            {select_clause}
            WHERE {date_filter} AND api_key_project_id = '{TEST_PROJECT_ID}'
        """)
        ground_truth["by_project"] = _row_to_dict(result[0]) if result and result[0][0] else _empty_summary()

        # 4. By user_id AND project_id
        result = await client.execute_query(f"""
            {select_clause}
            WHERE {date_filter}
              AND user_id = '{TEST_USER_ID}'
              AND api_key_project_id = '{TEST_PROJECT_ID}'
        """)
        ground_truth["by_user_and_project"] = _row_to_dict(result[0]) if result and result[0][0] else _empty_summary()

        # 5. Non-existent user (should be empty)
        ground_truth["nonexistent_user"] = _empty_summary()

        # 6. Non-existent project (should be empty)
        ground_truth["nonexistent_project"] = _empty_summary()

        return ground_truth
    finally:
        await client.close()


@pytest.fixture(scope="session")
def usage_summary_ground_truth(seed_test_data):
    """Fetch ground truth from InferenceFact (seeding done by shared fixture)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch_usage_summary_ground_truth())
    finally:
        loop.close()


def get_base_url(**kwargs) -> str:
    """Build URL with query parameters."""
    base = "/observability/usage/summary"
    params = {
        "start_date": TEST_FROM_DATE.isoformat(),
        "end_date": TEST_TO_DATE.isoformat(),
    }
    params.update(kwargs)

    query_parts = []
    for key, value in params.items():
        if value is not None:
            query_parts.append(f"{key}={value}")

    if query_parts:
        return f"{base}?{'&'.join(query_parts)}"
    return base


@pytest.mark.usefixtures("seed_test_data")
class TestBasicRequests:
    """Basic request tests for /observability/usage/summary."""

    def test_basic_request_minimal(self, sync_client, usage_summary_ground_truth):
        """Test minimal request with only start_date and end_date."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert "param" in data
        param = data["param"]
        assert "request_count" in param
        assert "total_cost" in param

        # Compare with ground truth
        db_data = usage_summary_ground_truth["overall"]
        assert param["request_count"] == db_data["request_count"], (
            f"request_count mismatch: API={param['request_count']}, DB={db_data['request_count']}"
        )
        print(f"\n[basic_minimal] Got request_count={param['request_count']}")

    def test_basic_request_with_user_id(self, sync_client, usage_summary_ground_truth):
        """Test request with user_id filter."""
        url = get_base_url(user_id=str(TEST_USER_ID))
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # Compare with ground truth
        db_data = usage_summary_ground_truth["by_user"]
        assert param["request_count"] == db_data["request_count"], (
            f"request_count mismatch: API={param['request_count']}, DB={db_data['request_count']}"
        )
        print(f"\n[basic_user_id] Got request_count={param['request_count']} for user")

    def test_basic_request_with_project_id(self, sync_client, usage_summary_ground_truth):
        """Test request with project_id filter."""
        url = get_base_url(project_id=str(TEST_PROJECT_ID))
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # Compare with ground truth
        db_data = usage_summary_ground_truth["by_project"]
        assert param["request_count"] == db_data["request_count"], (
            f"request_count mismatch: API={param['request_count']}, DB={db_data['request_count']}"
        )
        print(f"\n[basic_project_id] Got request_count={param['request_count']} for project")

    def test_basic_request_with_both_filters(self, sync_client, usage_summary_ground_truth):
        """Test request with both user_id and project_id filters."""
        url = get_base_url(user_id=str(TEST_USER_ID), project_id=str(TEST_PROJECT_ID))
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # Compare with ground truth
        db_data = usage_summary_ground_truth["by_user_and_project"]
        assert param["request_count"] == db_data["request_count"], (
            f"request_count mismatch: API={param['request_count']}, DB={db_data['request_count']}"
        )
        print(f"\n[basic_both_filters] Got request_count={param['request_count']} for user+project")

    def test_response_structure(self, sync_client):
        """Test that response has all expected fields."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        # Check top-level structure
        assert "message" in data
        assert "param" in data

        # Check param structure
        param = data["param"]
        expected_fields = [
            "total_tokens",
            "total_input_tokens",
            "total_output_tokens",
            "total_cost",
            "request_count",
            "success_count",
            "success_rate",
        ]
        for field in expected_fields:
            assert field in param, f"Missing field: {field}"
        print("\n[response_structure] All expected fields present")


class TestFilters:
    """Filter tests for /observability/usage/summary."""

    def test_filter_user_id_returns_user_data(self, sync_client, usage_summary_ground_truth):
        """Test filtering by user_id returns correct data."""
        url = get_base_url(user_id=str(TEST_USER_ID))
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        db_data = usage_summary_ground_truth["by_user"]
        assert param["request_count"] == db_data["request_count"]
        assert param["success_count"] == db_data["success_count"]
        print(f"\n[filter_user_id] Got request_count={param['request_count']}")

    def test_filter_project_id_returns_project_data(self, sync_client, usage_summary_ground_truth):
        """Test filtering by project_id returns correct data."""
        url = get_base_url(project_id=str(TEST_PROJECT_ID))
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        db_data = usage_summary_ground_truth["by_project"]
        assert param["request_count"] == db_data["request_count"]
        assert param["success_count"] == db_data["success_count"]
        print(f"\n[filter_project_id] Got request_count={param['request_count']}")

    def test_filter_combined_user_and_project(self, sync_client, usage_summary_ground_truth):
        """Test filtering by both user_id and project_id."""
        url = get_base_url(user_id=str(TEST_USER_ID), project_id=str(TEST_PROJECT_ID))
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        db_data = usage_summary_ground_truth["by_user_and_project"]
        assert param["request_count"] == db_data["request_count"]
        print(f"\n[filter_combined] Got request_count={param['request_count']}")

    def test_filter_nonexistent_user_returns_zeros(self, sync_client):
        """Test filtering by non-existent user_id returns zeros."""
        url = get_base_url(user_id=str(TEST_NONEXISTENT_ID))
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert param["request_count"] == 0
        assert param["success_count"] == 0
        assert param["total_cost"] == 0.0
        assert param["total_tokens"] == 0
        print("\n[filter_nonexistent_user] Got zeros as expected")

    def test_filter_nonexistent_project_returns_zeros(self, sync_client):
        """Test filtering by non-existent project_id returns zeros."""
        url = get_base_url(project_id=str(TEST_NONEXISTENT_ID))
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert param["request_count"] == 0
        assert param["success_count"] == 0
        assert param["total_cost"] == 0.0
        assert param["total_tokens"] == 0
        print("\n[filter_nonexistent_project] Got zeros as expected")

    def test_date_range_no_data_returns_zeros(self, sync_client):
        """Test date range with no data returns zeros."""
        future_date = datetime(2030, 1, 1, 0, 0, 0)
        future_end = datetime(2030, 1, 31, 23, 59, 59)
        url = get_base_url(start_date=future_date.isoformat(), end_date=future_end.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert param["request_count"] == 0
        assert param["total_cost"] == 0.0
        print("\n[date_range_no_data] Got zeros for future date range")

    @pytest.mark.usefixtures("seed_test_data")
    def test_date_range_single_day(self, sync_client):
        """Test date range for a single day."""
        url = get_base_url(start_date=TEST_FROM_DATE.isoformat(), end_date=TEST_TO_DATE.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # Just verify we get a valid response
        assert isinstance(param["request_count"], int)
        assert isinstance(param["total_cost"], (int, float))
        print(f"\n[date_range_single_day] Got request_count={param['request_count']}")


class TestValidation:
    """Validation error tests for /observability/usage/summary."""

    def test_missing_start_date_rejected(self, sync_client):
        """Test that missing start_date returns 422."""
        url = f"/observability/usage/summary?end_date={TEST_TO_DATE.isoformat()}"
        response = sync_client.get(url)
        assert response.status_code == 422, f"Expected 422 for missing start_date, got {response.status_code}"
        print("\n[validation] Missing start_date correctly rejected")

    def test_missing_end_date_rejected(self, sync_client):
        """Test that missing end_date returns 422."""
        url = f"/observability/usage/summary?start_date={TEST_FROM_DATE.isoformat()}"
        response = sync_client.get(url)
        assert response.status_code == 422, f"Expected 422 for missing end_date, got {response.status_code}"
        print("\n[validation] Missing end_date correctly rejected")

    def test_invalid_date_format_rejected(self, sync_client):
        """Test that invalid date format returns 422."""
        url = "/observability/usage/summary?start_date=invalid-date&end_date=also-invalid"
        response = sync_client.get(url)
        assert response.status_code == 422, f"Expected 422 for invalid date format, got {response.status_code}"
        print("\n[validation] Invalid date format correctly rejected")

    def test_invalid_user_id_format_rejected(self, sync_client):
        """Test that invalid user_id format returns 422."""
        url = get_base_url(user_id="not-a-uuid")
        response = sync_client.get(url)
        assert response.status_code == 422, f"Expected 422 for invalid user_id, got {response.status_code}"
        print("\n[validation] Invalid user_id correctly rejected")

    def test_invalid_project_id_format_rejected(self, sync_client):
        """Test that invalid project_id format returns 422."""
        url = get_base_url(project_id="not-a-uuid")
        response = sync_client.get(url)
        assert response.status_code == 422, f"Expected 422 for invalid project_id, got {response.status_code}"
        print("\n[validation] Invalid project_id correctly rejected")

    def test_empty_date_rejected(self, sync_client):
        """Test that empty date string returns 422."""
        url = "/observability/usage/summary?start_date=&end_date="
        response = sync_client.get(url)
        assert response.status_code == 422, f"Expected 422 for empty date, got {response.status_code}"
        print("\n[validation] Empty date correctly rejected")


class TestDataAccuracy:
    """Data accuracy tests comparing API response with DB."""

    def test_request_count_matches_db(self, sync_client, usage_summary_ground_truth):
        """Test that request_count matches database."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        db_data = usage_summary_ground_truth["overall"]
        assert param["request_count"] == db_data["request_count"], (
            f"request_count mismatch: API={param['request_count']}, DB={db_data['request_count']}"
        )
        print(f"\n[accuracy] request_count matches: {param['request_count']}")

    def test_success_count_matches_db(self, sync_client, usage_summary_ground_truth):
        """Test that success_count matches database."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        db_data = usage_summary_ground_truth["overall"]
        assert param["success_count"] == db_data["success_count"], (
            f"success_count mismatch: API={param['success_count']}, DB={db_data['success_count']}"
        )
        print(f"\n[accuracy] success_count matches: {param['success_count']}")

    def test_total_cost_matches_db(self, sync_client, usage_summary_ground_truth):
        """Test that total_cost matches database (with tolerance)."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        db_data = usage_summary_ground_truth["overall"]
        # Use tolerance for float comparison
        assert abs(param["total_cost"] - db_data["total_cost"]) < 0.01, (
            f"total_cost mismatch: API={param['total_cost']}, DB={db_data['total_cost']}"
        )
        print(f"\n[accuracy] total_cost matches: {param['total_cost']}")

    def test_input_tokens_matches_db(self, sync_client, usage_summary_ground_truth):
        """Test that total_input_tokens matches database."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        db_data = usage_summary_ground_truth["overall"]
        assert param["total_input_tokens"] == db_data["total_input_tokens"], (
            f"input_tokens mismatch: API={param['total_input_tokens']}, DB={db_data['total_input_tokens']}"
        )
        print(f"\n[accuracy] input_tokens matches: {param['total_input_tokens']}")

    def test_output_tokens_matches_db(self, sync_client, usage_summary_ground_truth):
        """Test that total_output_tokens matches database."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        db_data = usage_summary_ground_truth["overall"]
        assert param["total_output_tokens"] == db_data["total_output_tokens"], (
            f"output_tokens mismatch: API={param['total_output_tokens']}, DB={db_data['total_output_tokens']}"
        )
        print(f"\n[accuracy] output_tokens matches: {param['total_output_tokens']}")

    def test_total_tokens_is_sum(self, sync_client, usage_summary_ground_truth):
        """Test that total_tokens = input_tokens + output_tokens."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        expected_total = param["total_input_tokens"] + param["total_output_tokens"]
        assert param["total_tokens"] == expected_total, (
            f"total_tokens {param['total_tokens']} != input({param['total_input_tokens']}) + output({param['total_output_tokens']})"
        )
        print(f"\n[accuracy] total_tokens calculation correct: {param['total_tokens']}")

    def test_success_rate_calculation(self, sync_client, usage_summary_ground_truth):
        """Test that success_rate = (success_count / request_count) * 100."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        if param["request_count"] > 0:
            expected_rate = (param["success_count"] / param["request_count"]) * 100
            assert abs(param["success_rate"] - expected_rate) < 0.01, (
                f"success_rate {param['success_rate']} != expected {expected_rate}"
            )
        else:
            assert param["success_rate"] == 0.0
        print(f"\n[accuracy] success_rate calculation correct: {param['success_rate']}%")

    def test_success_rate_zero_requests(self, sync_client):
        """Test that success_rate is 0.0 when request_count is 0."""
        # Use non-existent user to ensure 0 requests
        url = get_base_url(user_id=str(TEST_NONEXISTENT_ID))
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert param["request_count"] == 0
        assert param["success_rate"] == 0.0, (
            f"success_rate should be 0.0 when no requests, got {param['success_rate']}"
        )
        print("\n[accuracy] success_rate is 0.0 for zero requests")

    @pytest.mark.usefixtures("seed_test_data")
    def test_success_rate_valid_range(self, sync_client):
        """Test that success_rate is a valid percentage (0-100)."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert 0 <= param["success_rate"] <= 100, f"success_rate {param['success_rate']} is not in valid range (0-100)"
        print(f"\n[accuracy] success_rate is valid: {param['success_rate']}%")

    @pytest.mark.usefixtures("seed_test_data")
    def test_cost_precision(self, sync_client):
        """Test that total_cost is a float."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert isinstance(param["total_cost"], (int, float)), (
            f"total_cost should be numeric, got {type(param['total_cost'])}"
        )
        print(f"\n[accuracy] total_cost is float: {param['total_cost']}")


class TestEdgeCases:
    """Edge case tests for /observability/usage/summary."""

    @pytest.mark.usefixtures("seed_test_data")
    def test_start_date_after_end_date(self, sync_client):
        """Test behavior when start_date is after end_date."""
        # Swap dates so start > end
        url = get_base_url(start_date=TEST_TO_DATE.isoformat(), end_date=TEST_FROM_DATE.isoformat())
        response = sync_client.get(url)
        # API should return 200 with zeros (or 422 if validated)
        assert response.status_code in [200, 422], f"Unexpected status code: {response.status_code}"
        if response.status_code == 200:
            data = response.json()
            param = data["param"]
            # Should return zero results for invalid date range
            assert param["request_count"] == 0
        print(f"\n[edge_case] start_date > end_date handled (status={response.status_code})")

    @pytest.mark.usefixtures("seed_test_data")
    def test_very_large_date_range(self, sync_client):
        """Test very large date range (multi-year)."""
        start = datetime(2020, 1, 1, 0, 0, 0)
        end = datetime(2030, 12, 31, 23, 59, 59)
        url = get_base_url(start_date=start.isoformat(), end_date=end.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # Just verify we get a valid response
        assert isinstance(param["request_count"], int)
        assert isinstance(param["total_cost"], (int, float))
        print(f"\n[edge_case] Large date range works, request_count={param['request_count']}")

    @pytest.mark.usefixtures("seed_test_data")
    def test_very_small_date_range(self, sync_client):
        """Test very small date range (< 1 hour)."""
        start = TEST_FROM_DATE
        end = start + timedelta(minutes=30)
        url = get_base_url(start_date=start.isoformat(), end_date=end.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # Just verify we get a valid response
        assert isinstance(param["request_count"], int)
        print(f"\n[edge_case] Small date range works, request_count={param['request_count']}")

    @pytest.mark.usefixtures("seed_test_data")
    def test_null_values_handled(self, sync_client, usage_summary_ground_truth):
        """Test that NULL values in tokens/cost are handled with COALESCE."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # All numeric fields should be non-negative (NULL coalesced to 0)
        assert param["total_cost"] >= 0
        assert param["total_input_tokens"] >= 0
        assert param["total_output_tokens"] >= 0
        assert param["total_tokens"] >= 0
        assert param["request_count"] >= 0
        assert param["success_count"] >= 0
        print("\n[edge_case] All values non-negative (COALESCE working)")


# pytest tests/observability/usage/test_usage_summary.py -v -s
