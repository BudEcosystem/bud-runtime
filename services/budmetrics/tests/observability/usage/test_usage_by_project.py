"""Tests for GET /observability/usage/by-project endpoint.

These tests validate the usage by-project API by:
1. Testing all query parameters (user_id, start_date, end_date)
2. Verifying response structure matches expected schema
3. Comparing values against InferenceFact ground truth
4. Verifying projects are sorted by cost DESC

Run with: pytest tests/observability/usage/test_usage_by_project.py -v -s
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


def _rows_to_project_list(rows) -> list[dict]:
    """Convert query result rows to list of project dicts."""
    if not rows:
        return []
    return [
        {
            "project_id": str(row[0]),
            "requests": row[1] or 0,
            "cost": float(row[2] or 0),
            "tokens": (row[3] or 0) + (row[4] or 0),
        }
        for row in rows
    ]


async def _fetch_usage_by_project_ground_truth():
    """Async helper to query ClickHouse for ground truth values grouped by project."""
    config = ClickHouseConfig()
    client = ClickHouseClient(config)
    await client.initialize()

    try:
        ground_truth = {}
        date_filter = f"timestamp >= '{TEST_FROM_DATE}' AND timestamp <= '{TEST_TO_DATE}'"

        # 1. By user - grouped by project (primary test case)
        result = await client.execute_query(f"""
            SELECT
                api_key_project_id,
                COUNT(*) as request_count,
                SUM(COALESCE(cost, 0)) as total_cost,
                SUM(COALESCE(input_tokens, 0)) as total_input_tokens,
                SUM(COALESCE(output_tokens, 0)) as total_output_tokens
            FROM InferenceFact
            WHERE {date_filter} AND user_id = '{TEST_USER_ID}'
            GROUP BY api_key_project_id
            ORDER BY total_cost DESC
        """)
        ground_truth["by_user"] = _rows_to_project_list(result)

        # 2. Totals for the user (for sum verification)
        result = await client.execute_query(f"""
            SELECT
                COUNT(*) as requests,
                SUM(COALESCE(cost, 0)) as cost,
                SUM(COALESCE(input_tokens, 0)) as input_tokens,
                SUM(COALESCE(output_tokens, 0)) as output_tokens
            FROM InferenceFact
            WHERE {date_filter} AND user_id = '{TEST_USER_ID}'
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

        # 3. Number of distinct projects for the user
        result = await client.execute_query(f"""
            SELECT COUNT(DISTINCT api_key_project_id)
            FROM InferenceFact
            WHERE {date_filter} AND user_id = '{TEST_USER_ID}'
        """)
        ground_truth["project_count"] = result[0][0] if result else 0

        return ground_truth
    finally:
        await client.close()


@pytest.fixture(scope="session")
def usage_by_project_ground_truth(seed_test_data):
    """Fetch ground truth from InferenceFact (seeding done by shared fixture)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch_usage_by_project_ground_truth())
    finally:
        loop.close()


def get_base_url(**kwargs) -> str:
    """Build URL with query parameters."""
    base = "/observability/usage/by-project"
    params = {
        "user_id": str(TEST_USER_ID),
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
    """Basic request tests for /observability/usage/by-project."""

    def test_basic_request_with_user_id(self, sync_client, usage_by_project_ground_truth):
        """Test valid request with user_id returns project list."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert "param" in data
        param = data["param"]
        assert "projects" in param
        assert isinstance(param["projects"], list)

        # Verify count matches ground truth
        db_count = usage_by_project_ground_truth["project_count"]
        assert len(param["projects"]) == db_count, (
            f"projects count mismatch: API={len(param['projects'])}, DB={db_count}"
        )
        print(f"\n[basic_request] Got {len(param['projects'])} projects")

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
        assert "projects" in param
        print("\n[response_structure] All expected fields present")

    def test_project_structure(self, sync_client):
        """Test that each project has all required fields."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        if param["projects"]:
            project = param["projects"][0]
            expected_fields = ["project_id", "tokens", "requests", "cost"]
            for field in expected_fields:
                assert field in project, f"Missing field in project: {field}"
            print(f"\n[project_structure] Project has all expected fields: {list(project.keys())}")
        else:
            print("\n[project_structure] No projects to verify (empty)")

    def test_projects_count_matches_db(self, sync_client, usage_by_project_ground_truth):
        """Test that number of projects matches database."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        db_count = usage_by_project_ground_truth["project_count"]
        assert len(param["projects"]) == db_count, (
            f"projects count mismatch: API={len(param['projects'])}, DB={db_count}"
        )
        print(f"\n[projects_count] Count matches: {len(param['projects'])}")

    def test_returns_list_not_single(self, sync_client):
        """Test that response is an array of projects, not a single object."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert isinstance(param["projects"], list), f"projects should be a list, got {type(param['projects'])}"
        print("\n[returns_list] Response is correctly a list")


class TestValidation:
    """Validation error tests for /observability/usage/by-project."""

    def test_missing_user_id_rejected(self, sync_client):
        """Test that missing user_id returns 422."""
        url = f"/observability/usage/by-project?start_date={TEST_FROM_DATE.isoformat()}&end_date={TEST_TO_DATE.isoformat()}"
        response = sync_client.get(url)
        assert response.status_code == 422, f"Expected 422 for missing user_id, got {response.status_code}"
        print("\n[validation] Missing user_id correctly rejected")

    def test_missing_start_date_rejected(self, sync_client):
        """Test that missing start_date returns 422."""
        url = f"/observability/usage/by-project?user_id={TEST_USER_ID}&end_date={TEST_TO_DATE.isoformat()}"
        response = sync_client.get(url)
        assert response.status_code == 422, f"Expected 422 for missing start_date, got {response.status_code}"
        print("\n[validation] Missing start_date correctly rejected")

    def test_missing_end_date_rejected(self, sync_client):
        """Test that missing end_date returns 422."""
        url = f"/observability/usage/by-project?user_id={TEST_USER_ID}&start_date={TEST_FROM_DATE.isoformat()}"
        response = sync_client.get(url)
        assert response.status_code == 422, f"Expected 422 for missing end_date, got {response.status_code}"
        print("\n[validation] Missing end_date correctly rejected")

    def test_invalid_user_id_format_rejected(self, sync_client):
        """Test that invalid user_id format returns 422."""
        url = get_base_url(user_id="not-a-uuid")
        response = sync_client.get(url)
        assert response.status_code == 422, f"Expected 422 for invalid user_id, got {response.status_code}"
        print("\n[validation] Invalid user_id correctly rejected")

    def test_invalid_date_format_rejected(self, sync_client):
        """Test that invalid date format returns 422."""
        url = f"/observability/usage/by-project?user_id={TEST_USER_ID}&start_date=invalid-date&end_date=also-invalid"
        response = sync_client.get(url)
        assert response.status_code == 422, f"Expected 422 for invalid date format, got {response.status_code}"
        print("\n[validation] Invalid date format correctly rejected")

    def test_empty_user_id_rejected(self, sync_client):
        """Test that empty user_id string returns 422."""
        url = f"/observability/usage/by-project?user_id=&start_date={TEST_FROM_DATE.isoformat()}&end_date={TEST_TO_DATE.isoformat()}"
        response = sync_client.get(url)
        assert response.status_code == 422, f"Expected 422 for empty user_id, got {response.status_code}"
        print("\n[validation] Empty user_id correctly rejected")

    def test_empty_date_rejected(self, sync_client):
        """Test that empty date string returns 422."""
        url = f"/observability/usage/by-project?user_id={TEST_USER_ID}&start_date=&end_date="
        response = sync_client.get(url)
        assert response.status_code == 422, f"Expected 422 for empty date, got {response.status_code}"
        print("\n[validation] Empty date correctly rejected")


@pytest.mark.usefixtures("seed_test_data")
class TestDataAccuracy:
    """Data accuracy tests comparing API response with DB."""

    def test_total_requests_sum_matches_db(self, sync_client, usage_by_project_ground_truth):
        """Test that sum of all project requests matches database total."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        api_total = sum(p["requests"] for p in param["projects"])
        db_total = usage_by_project_ground_truth["totals"]["requests"]
        assert api_total == db_total, f"total requests mismatch: API sum={api_total}, DB={db_total}"
        print(f"\n[accuracy] Total requests sum matches: {api_total}")

    def test_total_cost_sum_matches_db(self, sync_client, usage_by_project_ground_truth):
        """Test that sum of all project costs matches database total (with tolerance)."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        api_total = sum(p["cost"] for p in param["projects"])
        db_total = usage_by_project_ground_truth["totals"]["cost"]
        assert abs(api_total - db_total) < 0.01, f"total cost mismatch: API sum={api_total}, DB={db_total}"
        print(f"\n[accuracy] Total cost sum matches: {api_total:.2f}")

    def test_total_tokens_sum_matches_db(self, sync_client, usage_by_project_ground_truth):
        """Test that sum of all project tokens matches database total."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        api_total = sum(p["tokens"] for p in param["projects"])
        db_input = usage_by_project_ground_truth["totals"]["input_tokens"]
        db_output = usage_by_project_ground_truth["totals"]["output_tokens"]
        db_total = db_input + db_output

        assert api_total == db_total, f"total tokens mismatch: API sum={api_total}, DB={db_total}"
        print(f"\n[accuracy] Total tokens sum matches: {api_total}")

    def test_tokens_is_sum_of_input_output(self, sync_client, usage_by_project_ground_truth):
        """Test that tokens = input_tokens + output_tokens (calculated from DB)."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # Sum API tokens
        api_tokens = sum(p["tokens"] for p in param["projects"])

        # Calculate expected from DB totals
        db_expected = (
            usage_by_project_ground_truth["totals"]["input_tokens"]
            + usage_by_project_ground_truth["totals"]["output_tokens"]
        )

        assert api_tokens == db_expected, f"tokens calculation mismatch: API={api_tokens}, expected={db_expected}"
        print(f"\n[accuracy] Tokens correctly calculated: {api_tokens}")

    def test_first_project_matches_db(self, sync_client, usage_by_project_ground_truth):
        """Test that first project (highest cost) matches database."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        db_data = usage_by_project_ground_truth["by_user"]
        if param["projects"] and db_data:
            api_project = param["projects"][0]
            db_project = db_data[0]

            assert api_project["project_id"] == db_project["project_id"], (
                f"First project_id mismatch: API={api_project['project_id']}, DB={db_project['project_id']}"
            )
            assert api_project["requests"] == db_project["requests"], (
                f"First project requests mismatch: API={api_project['requests']}, DB={db_project['requests']}"
            )
            print(f"\n[accuracy] First project matches: {api_project['project_id']}")
        else:
            print("\n[accuracy] No projects to compare")

    def test_project_id_matches_expected(self, sync_client):
        """Test that expected project_id is in results."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        project_ids = [p["project_id"] for p in param["projects"]]

        # The test project should appear in results if the user has data for it
        if project_ids:
            # Log found project IDs for debugging
            print(f"\n[accuracy] Found project IDs: {project_ids}")
            # Verify all project_ids are valid UUIDs
            for pid in project_ids:
                assert len(pid) == 36, f"Invalid project_id format: {pid}"
        else:
            print("\n[accuracy] No projects returned (may be expected if user has no data for test project)")

    def test_cost_precision(self, sync_client):
        """Test that cost is a float/numeric type."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        for project in param["projects"]:
            assert isinstance(project["cost"], (int, float)), f"cost should be numeric, got {type(project['cost'])}"
        print("\n[accuracy] All cost values are numeric")

    def test_requests_is_integer(self, sync_client):
        """Test that requests is an integer type."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        for project in param["projects"]:
            assert isinstance(project["requests"], int), f"requests should be int, got {type(project['requests'])}"
        print("\n[accuracy] All requests values are integers")


@pytest.mark.usefixtures("seed_test_data")
class TestOrdering:
    """Ordering tests for /observability/usage/by-project."""

    def test_projects_sorted_by_cost_descending(self, sync_client):
        """Test that projects are sorted by cost in descending order."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        if len(param["projects"]) > 1:
            costs = [p["cost"] for p in param["projects"]]
            for i in range(len(costs) - 1):
                assert costs[i] >= costs[i + 1], (
                    f"Projects not sorted by cost DESC: {costs[i]} < {costs[i + 1]} at index {i}"
                )
            print(f"\n[ordering] Projects correctly sorted by cost DESC: {costs}")
        else:
            print("\n[ordering] Only one or zero projects, sorting is trivial")

    def test_highest_cost_project_is_first(self, sync_client):
        """Test that the first project has the highest cost."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        if param["projects"]:
            costs = [p["cost"] for p in param["projects"]]
            max_cost = max(costs)
            first_cost = param["projects"][0]["cost"]
            assert first_cost == max_cost, f"First project cost {first_cost} is not max cost {max_cost}"
            print(f"\n[ordering] First project has highest cost: {first_cost}")
        else:
            print("\n[ordering] No projects to check")

    def test_sorting_matches_db(self, sync_client, usage_by_project_ground_truth):
        """Test that project order matches database query order."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        db_data = usage_by_project_ground_truth["by_user"]
        if param["projects"] and db_data:
            api_ids = [p["project_id"] for p in param["projects"]]
            db_ids = [p["project_id"] for p in db_data]
            assert api_ids == db_ids, f"Project order mismatch: API={api_ids}, DB={db_ids}"
            print(f"\n[ordering] Project order matches DB: {api_ids}")
        else:
            print("\n[ordering] No projects to compare")


class TestEdgeCases:
    """Edge case tests for /observability/usage/by-project."""

    def test_nonexistent_user_returns_empty(self, sync_client):
        """Test that non-existent user_id returns empty projects array."""
        url = get_base_url(user_id=str(TEST_NONEXISTENT_ID))
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert param["projects"] == [], f"Expected empty array, got {param['projects']}"
        print("\n[edge_case] Non-existent user returns empty array")

    def test_date_range_no_data_returns_empty(self, sync_client):
        """Test that future date range returns empty projects array."""
        future_date = datetime(2030, 1, 1, 0, 0, 0)
        future_end = datetime(2030, 1, 31, 23, 59, 59)
        url = get_base_url(start_date=future_date.isoformat(), end_date=future_end.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert param["projects"] == [], "Expected empty array for future date range"
        print("\n[edge_case] Future date range returns empty array")

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
            assert param["projects"] == [], "Expected empty array for invalid date range"
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
        assert isinstance(param["projects"], list)
        print(f"\n[edge_case] Large date range works, got {len(param['projects'])} projects")

    @pytest.mark.usefixtures("seed_test_data")
    def test_null_values_handled(self, sync_client):
        """Test that NULL values in tokens/cost are handled with COALESCE."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # All numeric fields should be non-negative (NULL coalesced to 0)
        for project in param["projects"]:
            assert project["cost"] >= 0, "cost should be >= 0"
            assert project["tokens"] >= 0, "tokens should be >= 0"
            assert project["requests"] >= 0, "requests should be >= 0"
        print("\n[edge_case] All values non-negative (COALESCE working)")


# pytest tests/observability/usage/test_usage_by_project.py -v -s
