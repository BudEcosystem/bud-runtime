"""Tests for POST /observability/usage/summary/bulk endpoint.

These tests validate the bulk usage summary API by:
1. Testing POST body parameters (user_ids, start_date, end_date, project_id)
2. Verifying response structure matches expected schema
3. Comparing values against InferenceFact ground truth
4. Testing batch size limits and validation errors

Run with: pytest tests/observability/usage/test_usage_summary_bulk.py -v -s
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
TEST_USER_ID_2 = UUID("019b971a-4a01-7000-a001-a10000000003")
TEST_FROM_DATE = datetime(2026, 1, 7, 0, 0, 0)
TEST_TO_DATE = datetime(2026, 1, 7, 23, 59, 59)
TEST_NONEXISTENT_ID = UUID("00000000-0000-0000-0000-000000000000")

# API endpoint URL
BULK_USAGE_URL = "/observability/usage/summary/bulk"


def _row_to_user_summary(row) -> dict:
    """Convert a query result row to user summary dict."""
    return {
        "request_count": row[0] or 0,
        "success_count": row[1] or 0,
        "total_cost": float(row[2] or 0),
        "total_input_tokens": row[3] or 0,
        "total_output_tokens": row[4] or 0,
    }


def _empty_user_summary() -> dict:
    """Return empty user summary structure."""
    return {
        "request_count": 0,
        "success_count": 0,
        "total_cost": 0.0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    }


async def _fetch_bulk_usage_ground_truth():
    """Async helper to query ClickHouse for ground truth values for multiple users."""
    config = ClickHouseConfig()
    client = ClickHouseClient(config)
    await client.initialize()

    try:
        ground_truth = {}
        date_filter = f"timestamp >= '{TEST_FROM_DATE}' AND timestamp <= '{TEST_TO_DATE}'"

        # 1. Single user summary (TEST_USER_ID)
        result = await client.execute_query(f"""
            SELECT
                COUNT(*) as request_count,
                SUM(CASE WHEN is_success THEN 1 ELSE 0 END) as success_count,
                SUM(COALESCE(cost, 0)) as total_cost,
                SUM(COALESCE(input_tokens, 0)) as total_input_tokens,
                SUM(COALESCE(output_tokens, 0)) as total_output_tokens
            FROM InferenceFact
            WHERE {date_filter} AND user_id = '{TEST_USER_ID}'
        """)
        ground_truth["user_1"] = _row_to_user_summary(result[0]) if result and result[0][0] else _empty_user_summary()

        # 2. All users in date range (for totals verification)
        result = await client.execute_query(f"""
            SELECT
                user_id,
                COUNT(*) as request_count,
                SUM(CASE WHEN is_success THEN 1 ELSE 0 END) as success_count,
                SUM(COALESCE(cost, 0)) as total_cost,
                SUM(COALESCE(input_tokens, 0)) as total_input_tokens,
                SUM(COALESCE(output_tokens, 0)) as total_output_tokens
            FROM InferenceFact
            WHERE {date_filter} AND user_id IS NOT NULL
            GROUP BY user_id
            ORDER BY total_cost DESC
        """)
        ground_truth["all_users"] = {str(row[0]): _row_to_user_summary(row[1:]) for row in result} if result else {}

        # 3. Overall totals for user_1
        result = await client.execute_query(f"""
            SELECT
                COUNT(*) as requests,
                SUM(COALESCE(cost, 0)) as cost,
                SUM(COALESCE(input_tokens, 0)) + SUM(COALESCE(output_tokens, 0)) as tokens
            FROM InferenceFact
            WHERE {date_filter} AND user_id = '{TEST_USER_ID}'
        """)
        ground_truth["totals_user_1"] = (
            {
                "requests": result[0][0] or 0,
                "cost": float(result[0][1] or 0),
                "tokens": result[0][2] or 0,
            }
            if result
            else {"requests": 0, "cost": 0.0, "tokens": 0}
        )

        return ground_truth
    finally:
        await client.close()


@pytest.fixture(scope="session")
def bulk_usage_ground_truth(seed_test_data):
    """Fetch ground truth from InferenceFact (seeding done by shared fixture)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch_bulk_usage_ground_truth())
    finally:
        loop.close()


def get_request_body(**kwargs) -> dict:
    """Build POST request body with defaults."""
    body = {
        "user_ids": [str(TEST_USER_ID)],
        "start_date": f"{TEST_FROM_DATE.isoformat()}Z",
        "end_date": f"{TEST_TO_DATE.isoformat()}Z",
    }
    body.update(kwargs)
    return body


@pytest.mark.usefixtures("seed_test_data")
class TestBasicRequests:
    """Basic request tests for POST /observability/usage/summary/bulk."""

    def test_basic_request_single_user(self, sync_client, bulk_usage_ground_truth):
        """Test POST with single user_id returns users array."""
        body = get_request_body()
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        assert "param" in data
        param = data["param"]
        assert "users" in param
        assert isinstance(param["users"], list)
        assert len(param["users"]) == 1
        assert param["users"][0]["user_id"] == str(TEST_USER_ID)
        print(f"\n[basic_single_user] Got {len(param['users'])} user(s)")

    def test_basic_request_multiple_users(self, sync_client):
        """Test POST with multiple user_ids returns all users."""
        body = get_request_body(user_ids=[str(TEST_USER_ID), str(TEST_USER_ID_2)])
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]
        assert len(param["users"]) == 2
        user_ids_in_response = [u["user_id"] for u in param["users"]]
        assert str(TEST_USER_ID) in user_ids_in_response
        assert str(TEST_USER_ID_2) in user_ids_in_response
        print(f"\n[basic_multiple_users] Got {len(param['users'])} users")

    def test_response_structure(self, sync_client):
        """Test that response has all expected fields."""
        body = get_request_body()
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()

        # Check top-level structure
        assert "message" in data
        assert "param" in data

        # Check param structure
        param = data["param"]
        assert "users" in param
        assert "summary" in param
        print("\n[response_structure] All expected fields present")

    def test_user_structure(self, sync_client):
        """Test that each user has all required fields."""
        body = get_request_body()
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        if param["users"]:
            user = param["users"][0]
            expected_fields = [
                "user_id",
                "total_tokens",
                "total_input_tokens",
                "total_output_tokens",
                "total_cost",
                "request_count",
                "success_count",
                "success_rate",
            ]
            for field in expected_fields:
                assert field in user, f"Missing field in user: {field}"
            print(f"\n[user_structure] User has all expected fields: {list(user.keys())}")
        else:
            print("\n[user_structure] No users to verify")

    def test_summary_structure(self, sync_client):
        """Test that summary has all required fields."""
        body = get_request_body()
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        summary = param["summary"]
        expected_fields = [
            "total_users",
            "total_tokens_all",
            "total_cost_all",
            "total_requests_all",
            "date_range",
        ]
        for field in expected_fields:
            assert field in summary, f"Missing field in summary: {field}"
        print(f"\n[summary_structure] Summary has all expected fields: {list(summary.keys())}")

    def test_returns_all_requested_users(self, sync_client):
        """Test that all requested user_ids are in response, even with 0 usage."""
        body = get_request_body(user_ids=[str(TEST_USER_ID), str(TEST_NONEXISTENT_ID)])
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # Both users should be in response
        user_ids_in_response = [u["user_id"] for u in param["users"]]
        assert str(TEST_USER_ID) in user_ids_in_response
        assert str(TEST_NONEXISTENT_ID) in user_ids_in_response
        assert len(param["users"]) == 2
        print("\n[returns_all_requested] All requested users present in response")


class TestValidation:
    """Validation error tests for POST /observability/usage/summary/bulk."""

    def test_empty_user_ids_rejected(self, sync_client):
        """Test that empty user_ids array returns error."""
        body = get_request_body(user_ids=[])
        response = sync_client.post(BULK_USAGE_URL, json=body)
        # Should return error (not 200)
        assert response.status_code != 200 or "error" in response.json().get("message", "").lower()
        print("\n[validation] Empty user_ids correctly rejected")

    def test_missing_user_ids_rejected(self, sync_client):
        """Test that missing user_ids field returns error."""
        body = {
            "start_date": f"{TEST_FROM_DATE.isoformat()}Z",
            "end_date": f"{TEST_TO_DATE.isoformat()}Z",
        }
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code != 200 or "error" in response.json().get("message", "").lower()
        print("\n[validation] Missing user_ids correctly rejected")

    def test_missing_start_date_rejected(self, sync_client):
        """Test that missing start_date returns error."""
        body = {
            "user_ids": [str(TEST_USER_ID)],
            "end_date": f"{TEST_TO_DATE.isoformat()}Z",
        }
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code != 200 or "error" in response.json().get("message", "").lower()
        print("\n[validation] Missing start_date correctly rejected")

    def test_missing_end_date_rejected(self, sync_client):
        """Test that missing end_date returns error."""
        body = {
            "user_ids": [str(TEST_USER_ID)],
            "start_date": f"{TEST_FROM_DATE.isoformat()}Z",
        }
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code != 200 or "error" in response.json().get("message", "").lower()
        print("\n[validation] Missing end_date correctly rejected")

    def test_invalid_user_id_format_rejected(self, sync_client):
        """Test that invalid user_id format returns error."""
        body = get_request_body(user_ids=["not-a-uuid"])
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code != 200 or "error" in response.json().get("message", "").lower()
        print("\n[validation] Invalid user_id format correctly rejected")

    def test_invalid_date_format_rejected(self, sync_client):
        """Test that invalid date format returns error."""
        body = get_request_body(start_date="invalid-date", end_date="also-invalid")
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code != 200 or "error" in response.json().get("message", "").lower()
        print("\n[validation] Invalid date format correctly rejected")

    def test_invalid_project_id_format_rejected(self, sync_client):
        """Test that invalid project_id format returns error."""
        body = get_request_body(project_id="not-a-uuid")
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code != 200 or "error" in response.json().get("message", "").lower()
        print("\n[validation] Invalid project_id format correctly rejected")

    def test_batch_size_limit_enforced(self, sync_client):
        """Test that more than 1000 users returns error."""
        # Generate 1001 fake UUIDs
        fake_users = [str(UUID(f"00000000-0000-0000-0000-{i:012d}")) for i in range(1001)]
        body = get_request_body(user_ids=fake_users)
        response = sync_client.post(BULK_USAGE_URL, json=body)
        # Should return error about batch size
        assert response.status_code != 200 or "1000" in response.json().get("message", "")
        print("\n[validation] Batch size limit correctly enforced")

    def test_empty_body_rejected(self, sync_client):
        """Test that empty POST body returns error."""
        response = sync_client.post(BULK_USAGE_URL, json={})
        assert response.status_code != 200 or "error" in response.json().get("message", "").lower()
        print("\n[validation] Empty body correctly rejected")


@pytest.mark.usefixtures("seed_test_data")
class TestDataAccuracy:
    """Data accuracy tests comparing API response with DB."""

    def test_user_request_count_matches_db(self, sync_client, bulk_usage_ground_truth):
        """Test that user's request_count matches database."""
        body = get_request_body()
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        user = param["users"][0]
        db_data = bulk_usage_ground_truth["user_1"]
        assert user["request_count"] == db_data["request_count"], (
            f"request_count mismatch: API={user['request_count']}, DB={db_data['request_count']}"
        )
        print(f"\n[accuracy] request_count matches: {user['request_count']}")

    def test_user_success_count_matches_db(self, sync_client, bulk_usage_ground_truth):
        """Test that user's success_count matches database."""
        body = get_request_body()
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        user = param["users"][0]
        db_data = bulk_usage_ground_truth["user_1"]
        assert user["success_count"] == db_data["success_count"], (
            f"success_count mismatch: API={user['success_count']}, DB={db_data['success_count']}"
        )
        print(f"\n[accuracy] success_count matches: {user['success_count']}")

    def test_user_cost_matches_db(self, sync_client, bulk_usage_ground_truth):
        """Test that user's total_cost matches database (with tolerance)."""
        body = get_request_body()
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        user = param["users"][0]
        db_data = bulk_usage_ground_truth["user_1"]
        assert abs(user["total_cost"] - db_data["total_cost"]) < 0.01, (
            f"total_cost mismatch: API={user['total_cost']}, DB={db_data['total_cost']}"
        )
        print(f"\n[accuracy] total_cost matches: {user['total_cost']:.2f}")

    def test_user_tokens_matches_db(self, sync_client, bulk_usage_ground_truth):
        """Test that user's total_tokens matches database."""
        body = get_request_body()
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        user = param["users"][0]
        db_data = bulk_usage_ground_truth["user_1"]
        db_tokens = db_data["total_input_tokens"] + db_data["total_output_tokens"]
        assert user["total_tokens"] == db_tokens, f"total_tokens mismatch: API={user['total_tokens']}, DB={db_tokens}"
        print(f"\n[accuracy] total_tokens matches: {user['total_tokens']}")

    def test_summary_total_users_correct(self, sync_client):
        """Test that summary.total_users equals len(user_ids)."""
        user_ids = [str(TEST_USER_ID), str(TEST_USER_ID_2)]
        body = get_request_body(user_ids=user_ids)
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert param["summary"]["total_users"] == len(user_ids), (
            f"total_users mismatch: API={param['summary']['total_users']}, expected={len(user_ids)}"
        )
        print(f"\n[accuracy] total_users correct: {param['summary']['total_users']}")

    def test_user_input_tokens_matches_db(self, sync_client, bulk_usage_ground_truth):
        """Test that user's total_input_tokens matches database."""
        body = get_request_body()
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        user = param["users"][0]
        db_data = bulk_usage_ground_truth["user_1"]
        assert user["total_input_tokens"] == db_data["total_input_tokens"], (
            f"total_input_tokens mismatch: API={user['total_input_tokens']}, DB={db_data['total_input_tokens']}"
        )
        print(f"\n[accuracy] total_input_tokens matches: {user['total_input_tokens']}")

    def test_user_output_tokens_matches_db(self, sync_client, bulk_usage_ground_truth):
        """Test that user's total_output_tokens matches database."""
        body = get_request_body()
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        user = param["users"][0]
        db_data = bulk_usage_ground_truth["user_1"]
        assert user["total_output_tokens"] == db_data["total_output_tokens"], (
            f"total_output_tokens mismatch: API={user['total_output_tokens']}, DB={db_data['total_output_tokens']}"
        )
        print(f"\n[accuracy] total_output_tokens matches: {user['total_output_tokens']}")

    def test_summary_totals_match_db(self, sync_client, bulk_usage_ground_truth):
        """Test that summary totals match database ground truth."""
        body = get_request_body()
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # Compare summary totals against DB ground truth for single user
        db_totals = bulk_usage_ground_truth["totals_user_1"]
        assert param["summary"]["total_requests_all"] == db_totals["requests"], (
            f"total_requests_all mismatch: API={param['summary']['total_requests_all']}, DB={db_totals['requests']}"
        )
        assert abs(param["summary"]["total_cost_all"] - db_totals["cost"]) < 0.01, (
            f"total_cost_all mismatch: API={param['summary']['total_cost_all']}, DB={db_totals['cost']}"
        )
        assert param["summary"]["total_tokens_all"] == db_totals["tokens"], (
            f"total_tokens_all mismatch: API={param['summary']['total_tokens_all']}, DB={db_totals['tokens']}"
        )
        print("\n[accuracy] Summary totals match DB ground truth")

    def test_success_rate_matches_db(self, sync_client, bulk_usage_ground_truth):
        """Test that success_rate matches calculated value from database."""
        body = get_request_body()
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        user = param["users"][0]
        db_data = bulk_usage_ground_truth["user_1"]

        # Calculate expected success_rate from DB ground truth
        if db_data["request_count"] > 0:
            expected_rate = (db_data["success_count"] / db_data["request_count"]) * 100
        else:
            expected_rate = 0.0

        assert abs(user["success_rate"] - expected_rate) < 0.01, (
            f"success_rate mismatch: API={user['success_rate']}, expected from DB={expected_rate}"
        )
        print(f"\n[accuracy] success_rate matches DB: {user['success_rate']:.2f}%")


@pytest.mark.usefixtures("seed_test_data")
class TestProjectFilter:
    """Project filter tests for POST /observability/usage/summary/bulk."""

    def test_project_filter_applied(self, sync_client):
        """Test that project_id filter is applied."""
        body = get_request_body(project_id=str(TEST_PROJECT_ID))
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # Response should be valid (may have filtered data)
        assert isinstance(param["users"], list)
        print(f"\n[project_filter] Project filter applied, got {len(param['users'])} user(s)")

    def test_project_filter_in_summary(self, sync_client):
        """Test that summary.project_id reflects the filter."""
        body = get_request_body(project_id=str(TEST_PROJECT_ID))
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert param["summary"]["project_id"] == str(TEST_PROJECT_ID), (
            f"project_id in summary mismatch: {param['summary']['project_id']}"
        )
        print(f"\n[project_filter] summary.project_id correctly set: {param['summary']['project_id']}")

    def test_nonexistent_project_returns_zeros(self, sync_client):
        """Test that non-existent project_id returns zero usage for all users."""
        body = get_request_body(project_id=str(TEST_NONEXISTENT_ID))
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # All users should have zero usage
        for user in param["users"]:
            assert user["request_count"] == 0
            assert user["total_cost"] == 0.0
            assert user["total_tokens"] == 0
        print("\n[project_filter] Non-existent project returns zeros for all users")

    def test_without_project_filter(self, sync_client):
        """Test that without project_id, summary.project_id is null."""
        body = get_request_body()  # No project_id
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        assert param["summary"]["project_id"] is None, (
            f"project_id should be null without filter, got: {param['summary']['project_id']}"
        )
        print("\n[project_filter] summary.project_id is null without filter")


class TestEdgeCases:
    """Edge case tests for POST /observability/usage/summary/bulk."""

    def test_nonexistent_users_return_zeros(self, sync_client):
        """Test that all non-existent user_ids return zero usage but are present."""
        fake_users = [str(TEST_NONEXISTENT_ID), str(UUID("00000000-0000-0000-0000-000000000001"))]
        body = get_request_body(user_ids=fake_users)
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # All users should be present with zero usage
        assert len(param["users"]) == 2
        for user in param["users"]:
            assert user["request_count"] == 0
            assert user["total_cost"] == 0.0
            assert user["total_tokens"] == 0
            assert user["success_rate"] == 0.0
        print("\n[edge_case] Non-existent users return zeros but are present")

    @pytest.mark.usefixtures("seed_test_data")
    def test_mixed_existing_nonexistent_users(self, sync_client, bulk_usage_ground_truth):
        """Test mix of real and fake users: real have data, fake have zeros."""
        body = get_request_body(user_ids=[str(TEST_USER_ID), str(TEST_NONEXISTENT_ID)])
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # Find users by ID
        users_by_id = {u["user_id"]: u for u in param["users"]}

        # Real user should have data (if in DB)
        real_user = users_by_id.get(str(TEST_USER_ID))
        if real_user:
            db_data = bulk_usage_ground_truth["user_1"]
            assert real_user["request_count"] == db_data["request_count"]

        # Fake user should have zeros
        fake_user = users_by_id.get(str(TEST_NONEXISTENT_ID))
        if fake_user:
            assert fake_user["request_count"] == 0
            assert fake_user["total_cost"] == 0.0

        print("\n[edge_case] Mixed users: real have data, fake have zeros")

    def test_date_range_no_data_returns_zeros(self, sync_client):
        """Test that future date range returns zero usage for all users."""
        future_start = "2030-01-01T00:00:00Z"
        future_end = "2030-01-31T23:59:59Z"
        body = get_request_body(start_date=future_start, end_date=future_end)
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # All users should have zero usage
        for user in param["users"]:
            assert user["request_count"] == 0
            assert user["total_cost"] == 0.0
            assert user["total_tokens"] == 0
        print("\n[edge_case] Future date range returns zeros for all users")

    @pytest.mark.usefixtures("seed_test_data")
    def test_start_date_after_end_date(self, sync_client):
        """Test behavior when start_date is after end_date."""
        # Swap dates so start > end
        body = get_request_body(
            start_date=f"{TEST_TO_DATE.isoformat()}Z",
            end_date=f"{TEST_FROM_DATE.isoformat()}Z",
        )
        response = sync_client.post(BULK_USAGE_URL, json=body)
        # Should return 200 with zeros or error
        if response.status_code == 200:
            data = response.json()
            param = data["param"]
            for user in param["users"]:
                assert user["request_count"] == 0
        print(f"\n[edge_case] start_date > end_date handled (status={response.status_code})")

    @pytest.mark.usefixtures("seed_test_data")
    def test_null_values_handled(self, sync_client):
        """Test that NULL values in tokens/cost are handled with COALESCE."""
        body = get_request_body()
        response = sync_client.post(BULK_USAGE_URL, json=body)
        assert response.status_code == 200
        data = response.json()
        param = data["param"]

        # All numeric fields should be non-negative (NULL coalesced to 0)
        for user in param["users"]:
            assert user["total_cost"] >= 0, "total_cost should be >= 0"
            assert user["total_tokens"] >= 0, "total_tokens should be >= 0"
            assert user["total_input_tokens"] >= 0, "total_input_tokens should be >= 0"
            assert user["total_output_tokens"] >= 0, "total_output_tokens should be >= 0"
            assert user["request_count"] >= 0, "request_count should be >= 0"
            assert user["success_count"] >= 0, "success_count should be >= 0"
            assert 0 <= user["success_rate"] <= 100, "success_rate should be 0-100"
        print("\n[edge_case] All values non-negative (COALESCE working)")


# pytest tests/observability/usage/test_usage_summary_bulk.py -v -s
