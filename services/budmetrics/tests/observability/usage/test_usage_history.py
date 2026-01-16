"""Tests for GET /observability/usage/history endpoint.

These tests validate the usage history API by:
1. Testing all query parameters (user_id, project_id, start_date, end_date, granularity)
2. Verifying response structure matches expected schema (time-series data)
3. Comparing values against InferenceFact ground truth
4. Testing different granularity options (hourly, daily, weekly, monthly)

Run with: pytest tests/observability/usage/test_usage_history.py -v -s
"""

import asyncio
from datetime import datetime
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


def _rows_to_list(rows) -> list[dict]:
    """Convert query result rows to list of data point dicts."""
    if not rows:
        return []
    result = []
    for row in rows:
        result.append(
            {
                "date": str(row[0]),
                "requests": row[1] or 0,
                "cost": float(row[2] or 0),
                "input_tokens": row[3] or 0,
                "output_tokens": row[4] or 0,
                "tokens": (row[3] or 0) + (row[4] or 0),
            }
        )
    return result


async def _fetch_usage_history_ground_truth():
    """Async helper to query ClickHouse for ground truth time-series values."""
    config = ClickHouseConfig()
    client = ClickHouseClient(config)
    await client.initialize()

    try:
        ground_truth = {}
        date_filter = f"timestamp >= '{TEST_FROM_DATE}' AND timestamp <= '{TEST_TO_DATE}'"

        # Base SELECT clause for aggregations
        select_clause = """
            COUNT(*) as requests,
            SUM(COALESCE(cost, 0)) as cost,
            SUM(COALESCE(input_tokens, 0)) as input_tokens,
            SUM(COALESCE(output_tokens, 0)) as output_tokens
        """

        # 1. Daily granularity (overall)
        result = await client.execute_query(f"""
            SELECT toDate(timestamp) as period, {select_clause}
            FROM InferenceFact
            WHERE {date_filter}
            GROUP BY period ORDER BY period ASC
        """)
        ground_truth["daily_overall"] = _rows_to_list(result)

        # 2. Daily granularity (by user)
        result = await client.execute_query(f"""
            SELECT toDate(timestamp) as period, {select_clause}
            FROM InferenceFact
            WHERE {date_filter} AND user_id = '{TEST_USER_ID}'
            GROUP BY period ORDER BY period ASC
        """)
        ground_truth["daily_by_user"] = _rows_to_list(result)

        # 3. Daily granularity (by project)
        result = await client.execute_query(f"""
            SELECT toDate(timestamp) as period, {select_clause}
            FROM InferenceFact
            WHERE {date_filter} AND api_key_project_id = '{TEST_PROJECT_ID}'
            GROUP BY period ORDER BY period ASC
        """)
        ground_truth["daily_by_project"] = _rows_to_list(result)

        # 4. Daily granularity (by user AND project)
        result = await client.execute_query(f"""
            SELECT toDate(timestamp) as period, {select_clause}
            FROM InferenceFact
            WHERE {date_filter}
              AND user_id = '{TEST_USER_ID}'
              AND api_key_project_id = '{TEST_PROJECT_ID}'
            GROUP BY period ORDER BY period ASC
        """)
        ground_truth["daily_by_user_and_project"] = _rows_to_list(result)

        # 5. Hourly granularity (overall)
        result = await client.execute_query(f"""
            SELECT toStartOfHour(timestamp) as period, {select_clause}
            FROM InferenceFact
            WHERE {date_filter}
            GROUP BY period ORDER BY period ASC
        """)
        ground_truth["hourly_overall"] = _rows_to_list(result)

        # 6. Hourly granularity (by user)
        result = await client.execute_query(f"""
            SELECT toStartOfHour(timestamp) as period, {select_clause}
            FROM InferenceFact
            WHERE {date_filter} AND user_id = '{TEST_USER_ID}'
            GROUP BY period ORDER BY period ASC
        """)
        ground_truth["hourly_by_user"] = _rows_to_list(result)

        # 7. Total requests count for verification
        result = await client.execute_query(f"""
            SELECT COUNT(*), SUM(COALESCE(cost, 0)),
                   SUM(COALESCE(input_tokens, 0)), SUM(COALESCE(output_tokens, 0))
            FROM InferenceFact WHERE {date_filter}
        """)
        ground_truth["totals"] = (
            {
                "requests": result[0][0] or 0,
                "cost": float(result[0][1] or 0),
                "input_tokens": result[0][2] or 0,
                "output_tokens": result[0][3] or 0,
            }
            if result
            else {"requests": 0, "cost": 0.0, "input_tokens": 0, "output_tokens": 0}
        )

        return ground_truth
    finally:
        await client.close()


@pytest.fixture(scope="session")
def usage_history_ground_truth(seed_test_data):
    """Fetch ground truth from InferenceFact (seeding done by shared fixture)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch_usage_history_ground_truth())
    finally:
        loop.close()


def get_base_url(**kwargs) -> str:
    """Build URL with query parameters."""
    base = "/observability/usage/history"
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
    """Basic request tests for /observability/usage/history."""

    def test_basic_request_minimal(self, sync_client, usage_history_ground_truth):
        """Test minimal request with only start_date and end_date."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert "param" in data
        param = data["param"]
        assert "data" in param
        assert isinstance(param["data"], list)

        # Verify data points exist
        db_data = usage_history_ground_truth["daily_overall"]
        assert len(param["data"]) == len(db_data), (
            f"data points count mismatch: API={len(param['data'])}, DB={len(db_data)}"
        )
        print(f"\n[basic_minimal] Got {len(param['data'])} data points")

    def test_basic_request_with_user_id(self, sync_client, usage_history_ground_truth):
        """Test request with user_id filter."""
        url = get_base_url(user_id=str(TEST_USER_ID))
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # Compare with ground truth
        db_data = usage_history_ground_truth["daily_by_user"]
        assert len(param["data"]) == len(db_data), (
            f"data points count mismatch: API={len(param['data'])}, DB={len(db_data)}"
        )
        print(f"\n[basic_user_id] Got {len(param['data'])} data points for user")

    def test_basic_request_with_project_id(self, sync_client, usage_history_ground_truth):
        """Test request with project_id filter."""
        url = get_base_url(project_id=str(TEST_PROJECT_ID))
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # Compare with ground truth
        db_data = usage_history_ground_truth["daily_by_project"]
        assert len(param["data"]) == len(db_data), (
            f"data points count mismatch: API={len(param['data'])}, DB={len(db_data)}"
        )
        print(f"\n[basic_project_id] Got {len(param['data'])} data points for project")

    def test_basic_request_with_both_filters(self, sync_client, usage_history_ground_truth):
        """Test request with both user_id and project_id filters."""
        url = get_base_url(user_id=str(TEST_USER_ID), project_id=str(TEST_PROJECT_ID))
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # Compare with ground truth
        db_data = usage_history_ground_truth["daily_by_user_and_project"]
        assert len(param["data"]) == len(db_data), (
            f"data points count mismatch: API={len(param['data'])}, DB={len(db_data)}"
        )
        print(f"\n[basic_both_filters] Got {len(param['data'])} data points for user+project")

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
        assert "data" in param
        assert "granularity" in param
        print("\n[response_structure] All expected fields present")

    def test_data_point_structure(self, sync_client):
        """Test that each data point has all required fields."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        if param["data"]:
            data_point = param["data"][0]
            expected_fields = ["date", "tokens", "input_tokens", "output_tokens", "requests", "cost"]
            for field in expected_fields:
                assert field in data_point, f"Missing field in data point: {field}"
            print(f"\n[data_point_structure] Data point has all expected fields: {list(data_point.keys())}")
        else:
            print("\n[data_point_structure] No data points to verify (empty)")


@pytest.mark.usefixtures("seed_test_data")
class TestGranularity:
    """Granularity tests for /observability/usage/history."""

    def test_default_granularity_is_daily(self, sync_client):
        """Test that default granularity is 'daily' when not specified."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert param["granularity"] == "daily", f"Expected default granularity 'daily', got '{param['granularity']}'"
        print("\n[granularity] Default granularity is 'daily'")

    def test_granularity_hourly(self, sync_client, usage_history_ground_truth):
        """Test hourly granularity returns correct buckets."""
        url = get_base_url(granularity="hourly")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert param["granularity"] == "hourly"
        db_data = usage_history_ground_truth["hourly_overall"]
        assert len(param["data"]) == len(db_data), (
            f"hourly data points mismatch: API={len(param['data'])}, DB={len(db_data)}"
        )
        print(f"\n[granularity_hourly] Got {len(param['data'])} hourly data points")

    def test_granularity_daily(self, sync_client, usage_history_ground_truth):
        """Test daily granularity returns correct buckets."""
        url = get_base_url(granularity="daily")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert param["granularity"] == "daily"
        db_data = usage_history_ground_truth["daily_overall"]
        assert len(param["data"]) == len(db_data), (
            f"daily data points mismatch: API={len(param['data'])}, DB={len(db_data)}"
        )
        print(f"\n[granularity_daily] Got {len(param['data'])} daily data points")

    def test_granularity_weekly(self, sync_client):
        """Test weekly granularity returns valid response."""
        url = get_base_url(granularity="weekly")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert param["granularity"] == "weekly"
        # Weekly will group by Monday, so we should get valid data points
        assert isinstance(param["data"], list)
        print(f"\n[granularity_weekly] Got {len(param['data'])} weekly data points")

    def test_granularity_monthly(self, sync_client):
        """Test monthly granularity returns valid response."""
        url = get_base_url(granularity="monthly")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert param["granularity"] == "monthly"
        # Monthly will group by month start
        assert isinstance(param["data"], list)
        print(f"\n[granularity_monthly] Got {len(param['data'])} monthly data points")

    def test_hourly_returns_datetime_format(self, sync_client):
        """Test that hourly granularity returns datetime with time component."""
        url = get_base_url(granularity="hourly")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        if param["data"]:
            date_str = param["data"][0]["date"]
            # Hourly should have time component (e.g., "2026-01-07T00:00:00" or "2026-01-07 00:00:00")
            assert ":" in date_str or "T" in date_str, f"Hourly date should have time component: {date_str}"
            print(f"\n[hourly_datetime] Hourly date format: {date_str}")
        else:
            print("\n[hourly_datetime] No data points to check format")

    def test_daily_returns_date_format(self, sync_client):
        """Test that daily granularity returns date-only format."""
        url = get_base_url(granularity="daily")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        if param["data"]:
            date_str = param["data"][0]["date"]
            # Daily should be date-only (e.g., "2026-01-07")
            # May or may not include time depending on API implementation
            assert len(date_str) >= 10, f"Date string too short: {date_str}"
            print(f"\n[daily_date] Daily date format: {date_str}")
        else:
            print("\n[daily_date] No data points to check format")

    def test_invalid_granularity(self, sync_client):
        """Test that invalid granularity returns error or is ignored."""
        url = get_base_url(granularity="invalid_granularity")
        response = sync_client.get(url)
        # API should return 422 for invalid enum value
        assert response.status_code in [200, 422], (
            f"Expected 200 or 422 for invalid granularity, got {response.status_code}"
        )
        print(f"\n[invalid_granularity] Got status {response.status_code}")


class TestFilters:
    """Filter tests for /observability/usage/history."""

    def test_filter_user_id_returns_user_data(self, sync_client, usage_history_ground_truth):
        """Test filtering by user_id returns correct data points."""
        url = get_base_url(user_id=str(TEST_USER_ID))
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        db_data = usage_history_ground_truth["daily_by_user"]
        assert len(param["data"]) == len(db_data)
        print(f"\n[filter_user_id] Got {len(param['data'])} data points")

    def test_filter_project_id_returns_project_data(self, sync_client, usage_history_ground_truth):
        """Test filtering by project_id returns correct data points."""
        url = get_base_url(project_id=str(TEST_PROJECT_ID))
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        db_data = usage_history_ground_truth["daily_by_project"]
        assert len(param["data"]) == len(db_data)
        print(f"\n[filter_project_id] Got {len(param['data'])} data points")

    def test_filter_combined_user_and_project(self, sync_client, usage_history_ground_truth):
        """Test filtering by both user_id and project_id."""
        url = get_base_url(user_id=str(TEST_USER_ID), project_id=str(TEST_PROJECT_ID))
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        db_data = usage_history_ground_truth["daily_by_user_and_project"]
        assert len(param["data"]) == len(db_data)
        print(f"\n[filter_combined] Got {len(param['data'])} data points")

    def test_filter_nonexistent_user_returns_empty(self, sync_client):
        """Test filtering by non-existent user_id returns empty array."""
        url = get_base_url(user_id=str(TEST_NONEXISTENT_ID))
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert param["data"] == [], f"Expected empty array, got {param['data']}"
        print("\n[filter_nonexistent_user] Got empty array as expected")

    def test_filter_nonexistent_project_returns_empty(self, sync_client):
        """Test filtering by non-existent project_id returns empty array."""
        url = get_base_url(project_id=str(TEST_NONEXISTENT_ID))
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert param["data"] == [], f"Expected empty array, got {param['data']}"
        print("\n[filter_nonexistent_project] Got empty array as expected")

    def test_date_range_no_data_returns_empty(self, sync_client):
        """Test date range with no data returns empty array."""
        future_date = datetime(2030, 1, 1, 0, 0, 0)
        future_end = datetime(2030, 1, 31, 23, 59, 59)
        url = get_base_url(start_date=future_date.isoformat(), end_date=future_end.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert param["data"] == [], "Expected empty array for future date range"
        print("\n[date_range_no_data] Got empty array for future date range")

    def test_granularity_with_filter(self, sync_client, usage_history_ground_truth):
        """Test that granularity works with user filter."""
        url = get_base_url(user_id=str(TEST_USER_ID), granularity="hourly")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert param["granularity"] == "hourly"
        db_data = usage_history_ground_truth["hourly_by_user"]
        assert len(param["data"]) == len(db_data), (
            f"hourly+user data points mismatch: API={len(param['data'])}, DB={len(db_data)}"
        )
        print(f"\n[granularity_with_filter] Got {len(param['data'])} hourly data points for user")


class TestValidation:
    """Validation error tests for /observability/usage/history."""

    def test_missing_start_date_rejected(self, sync_client):
        """Test that missing start_date returns 422."""
        url = f"/observability/usage/history?end_date={TEST_TO_DATE.isoformat()}"
        response = sync_client.get(url)
        assert response.status_code == 422, f"Expected 422 for missing start_date, got {response.status_code}"
        print("\n[validation] Missing start_date correctly rejected")

    def test_missing_end_date_rejected(self, sync_client):
        """Test that missing end_date returns 422."""
        url = f"/observability/usage/history?start_date={TEST_FROM_DATE.isoformat()}"
        response = sync_client.get(url)
        assert response.status_code == 422, f"Expected 422 for missing end_date, got {response.status_code}"
        print("\n[validation] Missing end_date correctly rejected")

    def test_invalid_date_format_rejected(self, sync_client):
        """Test that invalid date format returns 422."""
        url = "/observability/usage/history?start_date=invalid-date&end_date=also-invalid"
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
        url = "/observability/usage/history?start_date=&end_date="
        response = sync_client.get(url)
        assert response.status_code == 422, f"Expected 422 for empty date, got {response.status_code}"
        print("\n[validation] Empty date correctly rejected")


@pytest.mark.usefixtures("seed_test_data")
class TestDataAccuracy:
    """Data accuracy tests comparing API response with DB."""

    def test_data_points_count_matches_db(self, sync_client, usage_history_ground_truth):
        """Test that number of data points matches database."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        db_data = usage_history_ground_truth["daily_overall"]
        assert len(param["data"]) == len(db_data), (
            f"data points count mismatch: API={len(param['data'])}, DB={len(db_data)}"
        )
        print(f"\n[accuracy] Data points count matches: {len(param['data'])}")

    def test_total_requests_sum_matches_db(self, sync_client, usage_history_ground_truth):
        """Test that sum of all requests matches database total."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        api_total = sum(dp["requests"] for dp in param["data"])
        db_total = usage_history_ground_truth["totals"]["requests"]
        assert api_total == db_total, f"total requests mismatch: API sum={api_total}, DB={db_total}"
        print(f"\n[accuracy] Total requests sum matches: {api_total}")

    def test_total_cost_sum_matches_db(self, sync_client, usage_history_ground_truth):
        """Test that sum of all costs matches database total (with tolerance)."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        api_total = sum(dp["cost"] for dp in param["data"])
        db_total = usage_history_ground_truth["totals"]["cost"]
        assert abs(api_total - db_total) < 0.01, f"total cost mismatch: API sum={api_total}, DB={db_total}"
        print(f"\n[accuracy] Total cost sum matches: {api_total:.2f}")

    def test_total_tokens_sum_matches_db(self, sync_client, usage_history_ground_truth):
        """Test that sum of all tokens matches database total."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        api_input = sum(dp["input_tokens"] for dp in param["data"])
        api_output = sum(dp["output_tokens"] for dp in param["data"])
        db_input = usage_history_ground_truth["totals"]["input_tokens"]
        db_output = usage_history_ground_truth["totals"]["output_tokens"]

        assert api_input == db_input, f"input_tokens mismatch: API sum={api_input}, DB={db_input}"
        assert api_output == db_output, f"output_tokens mismatch: API sum={api_output}, DB={db_output}"
        print(f"\n[accuracy] Total tokens sum matches: input={api_input}, output={api_output}")

    def test_tokens_is_sum_of_input_output(self, sync_client):
        """Test that tokens = input_tokens + output_tokens for each data point."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        for i, dp in enumerate(param["data"]):
            expected_tokens = dp["input_tokens"] + dp["output_tokens"]
            assert dp["tokens"] == expected_tokens, (
                f"Data point {i}: tokens {dp['tokens']} != input({dp['input_tokens']}) + output({dp['output_tokens']})"
            )
        print(f"\n[accuracy] All {len(param['data'])} data points have correct tokens calculation")

    def test_data_sorted_by_date_ascending(self, sync_client):
        """Test that data is sorted by date in ascending order."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        if len(param["data"]) > 1:
            dates = [dp["date"] for dp in param["data"]]
            sorted_dates = sorted(dates)
            assert dates == sorted_dates, f"Data not sorted by date: {dates[:5]}..."
            print(f"\n[accuracy] Data is sorted by date (first: {dates[0]}, last: {dates[-1]})")
        else:
            print("\n[accuracy] Only one or zero data points, sorting is trivial")

    def test_first_data_point_matches_db(self, sync_client, usage_history_ground_truth):
        """Test that first data point values match database."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        db_data = usage_history_ground_truth["daily_overall"]
        if param["data"] and db_data:
            api_dp = param["data"][0]
            db_dp = db_data[0]

            assert api_dp["requests"] == db_dp["requests"], (
                f"First data point requests mismatch: API={api_dp['requests']}, DB={db_dp['requests']}"
            )
            print(f"\n[accuracy] First data point matches: requests={api_dp['requests']}")
        else:
            print("\n[accuracy] No data points to compare")

    def test_cost_precision(self, sync_client):
        """Test that cost is a float/numeric type."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        for dp in param["data"]:
            assert isinstance(dp["cost"], (int, float)), f"cost should be numeric, got {type(dp['cost'])}"
        print("\n[accuracy] All cost values are numeric")


class TestEdgeCases:
    """Edge case tests for /observability/usage/history."""

    @pytest.mark.usefixtures("seed_test_data")
    def test_start_date_after_end_date(self, sync_client):
        """Test behavior when start_date is after end_date."""
        # Swap dates so start > end
        url = get_base_url(start_date=TEST_TO_DATE.isoformat(), end_date=TEST_FROM_DATE.isoformat())
        response = sync_client.get(url)
        # API should return 200 with empty array or 422 if validated
        assert response.status_code in [200, 422], f"Unexpected status code: {response.status_code}"
        if response.status_code == 200:
            data = response.json()
            param = data["param"]
            # Should return empty array for invalid date range
            assert param["data"] == [], "Expected empty array for invalid date range"
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
        assert isinstance(param["data"], list)
        print(f"\n[edge_case] Large date range works, got {len(param['data'])} data points")

    @pytest.mark.usefixtures("seed_test_data")
    def test_single_day_range(self, sync_client):
        """Test single day date range."""
        url = get_base_url(start_date=TEST_FROM_DATE.isoformat(), end_date=TEST_TO_DATE.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # For daily granularity on a single day, should get 1 bucket
        assert isinstance(param["data"], list)
        print(f"\n[edge_case] Single day range works, got {len(param['data'])} data points")

    @pytest.mark.usefixtures("seed_test_data")
    def test_null_values_handled(self, sync_client):
        """Test that NULL values in tokens/cost are handled with COALESCE."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # All numeric fields should be non-negative (NULL coalesced to 0)
        for dp in param["data"]:
            assert dp["cost"] >= 0, "cost should be >= 0"
            assert dp["input_tokens"] >= 0, "input_tokens should be >= 0"
            assert dp["output_tokens"] >= 0, "output_tokens should be >= 0"
            assert dp["tokens"] >= 0, "tokens should be >= 0"
            assert dp["requests"] >= 0, "requests should be >= 0"
        print("\n[edge_case] All values non-negative (COALESCE working)")


# pytest tests/observability/usage/test_usage_history.py -v -s
