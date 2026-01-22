"""Tests for GET /observability/gateway/top-routes endpoint.

These tests validate the gateway top routes API by:
1. Testing all query parameters (from_date, to_date, limit, project_id)
2. Verifying response structure matches expected schema
3. Comparing values against InferenceFact ground truth

Run with: pytest tests/observability/test_gateway_top_routes.py -v -s
"""

import asyncio
from datetime import datetime
from uuid import UUID

import pytest

from budmetrics.observability.models import ClickHouseClient, ClickHouseConfig


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# Test constants (same as other test files)
TEST_PROJECT_ID = UUID("019787c1-3de1-7b50-969b-e0a58514b6a1")
TEST_FROM_DATE = datetime(2026, 1, 7, 0, 0, 0)
TEST_TO_DATE = datetime(2026, 1, 7, 23, 59, 59)


async def _fetch_top_routes_ground_truth():
    """Async helper to query ClickHouse for ground truth values."""
    config = ClickHouseConfig()
    client = ClickHouseClient(config)
    await client.initialize()

    try:
        ground_truth = {}
        date_filter = f"timestamp >= '{TEST_FROM_DATE}' AND timestamp <= '{TEST_TO_DATE}'"

        # Get top routes with all metrics
        result = await client.execute_query(f"""
            SELECT
                path,
                method,
                count(*) as count,
                avg(response_time_ms) as avg_response_time,
                sum(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) * 100.0 / count(*) as error_rate
            FROM InferenceFact
            WHERE {date_filter}
            GROUP BY path, method
            ORDER BY count DESC
            LIMIT 20
        """)
        ground_truth["routes"] = [
            {
                "path": r[0],
                "method": r[1],
                "count": r[2],
                "avg_response_time": r[3] or 0,
                "error_rate": r[4] or 0,
            }
            for r in result
        ]
        ground_truth["total_route_count"] = len(result)

        # Get project-specific routes
        result = await client.execute_query(f"""
            SELECT path, method, count(*) as count
            FROM InferenceFact
            WHERE {date_filter} AND project_id = '{TEST_PROJECT_ID}'
            GROUP BY path, method
            ORDER BY count DESC
        """)
        ground_truth["project_routes"] = [
            {"path": r[0], "method": r[1], "count": r[2]}
            for r in result
        ]
        ground_truth["project_route_count"] = len(result)

        return ground_truth
    finally:
        await client.close()


@pytest.fixture(scope="session")
def routes_ground_truth(seed_test_data):
    """Fetch ground truth from InferenceFact (seeding done by shared fixture)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch_top_routes_ground_truth())
    finally:
        loop.close()


def get_base_url(**kwargs) -> str:
    """Build URL with query parameters."""
    base = "/observability/gateway/top-routes"
    params = {"from_date": TEST_FROM_DATE.isoformat()}
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
    """Basic request tests for /observability/gateway/top-routes."""

    def test_basic_request_minimal(self, sync_client):
        """Test minimal request with only from_date."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert "routes" in data
        assert isinstance(data["routes"], list)
        print(f"\n[basic_minimal] Got {len(data['routes'])} routes")

    def test_basic_request_with_date_range(self, sync_client):
        """Test request with from_date and to_date."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert "routes" in data
        print(f"\n[basic_date_range] Got {len(data['routes'])} routes")

    def test_response_structure(self, sync_client):
        """Test that response has all expected fields."""
        url = get_base_url(limit=1)
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        # Check top-level structure
        assert "routes" in data
        assert isinstance(data["routes"], list)

        # Check route item structure if we have routes
        if data["routes"]:
            route = data["routes"][0]
            expected_fields = ["path", "method", "count", "avg_response_time", "error_rate"]
            for field in expected_fields:
                assert field in route, f"Missing field: {field}"
        print("\n[response_structure] All expected fields present")


class TestLimit:
    """Limit parameter tests."""

    @pytest.mark.usefixtures("seed_test_data")
    def test_default_limit_10(self, sync_client):
        """Test default limit returns up to 10 routes."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        # Default limit is 10
        assert len(data["routes"]) <= 10
        print(f"\n[default_limit] Got {len(data['routes'])} routes (default limit 10)")

    @pytest.mark.usefixtures("seed_test_data")
    def test_custom_limit_5(self, sync_client):
        """Test limit=5 returns up to 5 routes."""
        url = get_base_url(limit=5)
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert len(data["routes"]) <= 5
        print(f"\n[limit_5] Got {len(data['routes'])} routes")

    @pytest.mark.usefixtures("seed_test_data")
    def test_custom_limit_20(self, sync_client):
        """Test limit=20 returns up to 20 routes."""
        url = get_base_url(limit=20)
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert len(data["routes"]) <= 20
        print(f"\n[limit_20] Got {len(data['routes'])} routes")

    def test_limit_1(self, sync_client, routes_ground_truth):
        """Test limit=1 returns exactly 1 route if data exists."""
        url = get_base_url(limit=1)
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        if routes_ground_truth["total_route_count"] > 0:
            assert len(data["routes"]) == 1
        else:
            assert len(data["routes"]) == 0
        print(f"\n[limit_1] Got {len(data['routes'])} route(s)")


class TestFilters:
    """Filter tests."""

    def test_filter_by_project_id(self, sync_client, routes_ground_truth):
        """Test filtering by project_id."""
        url = get_base_url(
            to_date=TEST_TO_DATE.isoformat(),
            project_id=str(TEST_PROJECT_ID)
        )
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        expected_count = routes_ground_truth["project_route_count"]
        assert len(data["routes"]) <= expected_count, \
            f"Got more routes than expected: {len(data['routes'])} > {expected_count}"
        print(f"\n[filter_project] Got {len(data['routes'])} routes for project")

    @pytest.mark.usefixtures("seed_test_data")
    def test_filter_combined_all_params(self, sync_client):
        """Test combining all parameters."""
        url = get_base_url(
            to_date=TEST_TO_DATE.isoformat(),
            limit=5,
            project_id=str(TEST_PROJECT_ID)
        )
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert len(data["routes"]) <= 5
        print(f"\n[filter_combined] Got {len(data['routes'])} routes with all params")


class TestValidation:
    """Validation error tests."""

    def test_missing_from_date_rejected(self, sync_client):
        """Test that missing from_date returns 422."""
        url = "/observability/gateway/top-routes"
        response = sync_client.get(url)
        assert response.status_code == 422, \
            f"Expected 422 for missing from_date, got {response.status_code}"
        print("\n[validation] Missing from_date correctly rejected")

    def test_invalid_date_format_rejected(self, sync_client):
        """Test that invalid date format returns 422."""
        url = "/observability/gateway/top-routes?from_date=invalid-date"
        response = sync_client.get(url)
        assert response.status_code == 422, \
            f"Expected 422 for invalid date format, got {response.status_code}"
        print("\n[validation] Invalid date format correctly rejected")

    def test_invalid_project_id_rejected(self, sync_client):
        """Test that invalid project_id format returns 422."""
        url = get_base_url(project_id="not-a-uuid")
        response = sync_client.get(url)
        assert response.status_code == 422, \
            f"Expected 422 for invalid project_id, got {response.status_code}"
        print("\n[validation] Invalid project_id correctly rejected")


class TestDataAccuracy:
    """Data accuracy tests comparing API response with DB."""

    @pytest.mark.usefixtures("seed_test_data")
    def test_routes_sorted_by_count_desc(self, sync_client):
        """Test that routes are sorted by count descending."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat(), limit=20)
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        if len(data["routes"]) > 1:
            counts = [route["count"] for route in data["routes"]]
            assert counts == sorted(counts, reverse=True), \
                f"Routes not sorted by count desc: {counts}"
        print("\n[accuracy] Routes sorted correctly by count desc")

    def test_routes_count_matches_db(self, sync_client, routes_ground_truth):
        """Test that route counts match database."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat(), limit=20)
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        db_routes = routes_ground_truth["routes"]
        if db_routes and data["routes"]:
            # Compare first route's count
            api_first = data["routes"][0]
            db_first = db_routes[0]

            # Path and method should match
            assert api_first["path"] == db_first["path"], \
                f"Path mismatch: API={api_first['path']}, DB={db_first['path']}"
            assert api_first["count"] == db_first["count"], \
                f"Count mismatch: API={api_first['count']}, DB={db_first['count']}"
        print("\n[accuracy] Route counts match DB")

    @pytest.mark.usefixtures("seed_test_data")
    def test_error_rate_is_percentage(self, sync_client):
        """Test that error_rate is a valid percentage (0-100)."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        for route in data["routes"]:
            error_rate = route["error_rate"]
            assert 0 <= error_rate <= 100, \
                f"error_rate {error_rate} is not a valid percentage for path={route['path']}"
        print("\n[accuracy] All error_rate values are valid percentages")

    @pytest.mark.usefixtures("seed_test_data")
    def test_avg_response_time_non_negative(self, sync_client):
        """Test that avg_response_time is non-negative."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        for route in data["routes"]:
            avg_time = route["avg_response_time"]
            assert avg_time >= 0, \
                f"avg_response_time {avg_time} is negative for path={route['path']}"
        print("\n[accuracy] All avg_response_time values are non-negative")


# pytest tests/observability/test_gateway_top_routes.py -v -s
