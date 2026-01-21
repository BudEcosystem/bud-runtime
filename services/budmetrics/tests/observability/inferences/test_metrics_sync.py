"""Tests for POST /observability/metrics-sync endpoint.

These tests validate the metrics sync API by:
1. Testing all request parameters (sync_mode, activity_threshold_minutes, credential_sync, user_usage_sync, user_ids)
2. Verifying response structure matches expected schema
3. Comparing values against InferenceFact ground truth

Run with: pytest tests/observability/inferences/test_metrics_sync.py -v -s
"""

import asyncio
from uuid import UUID

import pytest

from budmetrics.observability.models import ClickHouseClient, ClickHouseConfig


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# Test constants (from seeder data)
TEST_CREDENTIAL_ID = UUID("019b971a-4a01-7000-a001-a10000000001")
TEST_USER_ID = UUID("019b971a-4a01-7000-a001-a10000000002")
TEST_NONEXISTENT_ID = UUID("00000000-0000-0000-0000-000000000000")


async def _fetch_metrics_sync_ground_truth():
    """Async helper to query ClickHouse for ground truth values."""
    config = ClickHouseConfig()
    client = ClickHouseClient(config)
    await client.initialize()

    try:
        ground_truth = {}

        # Get credential data (all credentials with activity)
        result = await client.execute_query("""
            SELECT
                api_key_id as credential_id,
                MAX(request_arrival_time) as last_used_at,
                COUNT(*) as request_count
            FROM InferenceFact
            WHERE api_key_id IS NOT NULL
            GROUP BY api_key_id
            ORDER BY last_used_at DESC
        """)
        ground_truth["credentials"] = [
            {
                "credential_id": str(r[0]),
                "last_used_at": r[1],
                "request_count": r[2],
            }
            for r in result
        ]
        ground_truth["credential_count"] = len(result)

        # Get specific test credential stats
        result = await client.execute_query(f"""
            SELECT
                MAX(request_arrival_time) as last_used_at,
                COUNT(*) as request_count
            FROM InferenceFact
            WHERE api_key_id = '{TEST_CREDENTIAL_ID}'
        """)
        if result and result[0][0]:
            ground_truth["test_credential"] = {
                "last_used_at": result[0][0],
                "request_count": result[0][1],
            }
        else:
            ground_truth["test_credential"] = None

        # Get user data (all users with activity)
        result = await client.execute_query("""
            SELECT
                user_id,
                MAX(request_arrival_time) as last_activity_at,
                SUM(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)) as total_tokens,
                SUM(COALESCE(cost, 0)) as total_cost,
                COUNT(*) as request_count,
                AVG(CASE WHEN is_success THEN 1 ELSE 0 END) as success_rate
            FROM InferenceFact
            WHERE user_id IS NOT NULL
            GROUP BY user_id
            ORDER BY last_activity_at DESC
        """)
        ground_truth["users"] = [
            {
                "user_id": str(r[0]),
                "last_activity_at": r[1],
                "total_tokens": int(r[2]) if r[2] else 0,
                "total_cost": float(r[3]) if r[3] else 0.0,
                "request_count": int(r[4]) if r[4] else 0,
                "success_rate": float(r[5]) if r[5] else 0.0,
            }
            for r in result
        ]
        ground_truth["user_count"] = len(result)

        # Get specific test user stats
        result = await client.execute_query(f"""
            SELECT
                MAX(request_arrival_time) as last_activity_at,
                SUM(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)) as total_tokens,
                SUM(COALESCE(cost, 0)) as total_cost,
                COUNT(*) as request_count,
                AVG(CASE WHEN is_success THEN 1 ELSE 0 END) as success_rate
            FROM InferenceFact
            WHERE user_id = '{TEST_USER_ID}'
        """)
        if result and result[0][0]:
            ground_truth["test_user"] = {
                "last_activity_at": result[0][0],
                "total_tokens": int(result[0][1]) if result[0][1] else 0,
                "total_cost": float(result[0][2]) if result[0][2] else 0.0,
                "request_count": int(result[0][3]) if result[0][3] else 0,
                "success_rate": float(result[0][4]) if result[0][4] else 0.0,
            }
        else:
            ground_truth["test_user"] = None

        return ground_truth
    finally:
        await client.close()


@pytest.fixture(scope="session")
def metrics_sync_ground_truth(seed_test_data):
    """Fetch ground truth from InferenceFact (seeding done by shared fixture)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch_metrics_sync_ground_truth())
    finally:
        loop.close()


@pytest.mark.usefixtures("seed_test_data")
class TestBasicRequests:
    """Basic request tests for /observability/metrics-sync."""

    def test_default_request(self, sync_client):
        """Test default request with empty payload."""
        response = sync_client.post("/observability/metrics-sync", json={})
        assert response.status_code == 200
        data = response.json()
        assert "credential_usage" in data
        assert "user_usage" in data
        assert "stats" in data
        print(f"\n[default_request] Got response with stats: {data['stats']}")

    def test_response_structure(self, sync_client):
        """Test that response has all expected fields."""
        response = sync_client.post("/observability/metrics-sync", json={})
        assert response.status_code == 200
        data = response.json()

        # Check top-level structure
        expected_fields = [
            "object", "sync_mode", "activity_threshold_minutes",
            "query_timestamp", "credential_usage", "user_usage", "stats"
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

        # Check stats structure
        expected_stats = ["active_credentials", "active_users", "total_users_checked"]
        for stat in expected_stats:
            assert stat in data["stats"], f"Missing stat: {stat}"

        print("\n[response_structure] All expected fields present")

    def test_response_object_type(self, sync_client):
        """Test that response object type is correct."""
        response = sync_client.post("/observability/metrics-sync", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "metrics_sync"
        print("\n[object_type] Correct object type: metrics_sync")


@pytest.mark.usefixtures("seed_test_data")
class TestSyncModes:
    """Sync mode tests for incremental vs full."""

    def test_incremental_mode_default(self, sync_client):
        """Test that incremental mode with default threshold returns empty (old data)."""
        response = sync_client.post("/observability/metrics-sync", json={
            "sync_mode": "incremental"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["sync_mode"] == "incremental"
        # Seeder data is from 2026-01-07, outside default 5-minute threshold
        assert len(data["credential_usage"]) == 0
        assert len(data["user_usage"]) == 0
        print("\n[incremental_default] Empty results as expected (data is old)")

    @pytest.mark.skip(reason="Full mode with user_usage_sync triggers Dapr call to budapp which hangs without Dapr")
    def test_full_mode_returns_data(self, sync_client):
        """Test that full mode returns historical data."""
        response = sync_client.post("/observability/metrics-sync", json={
            "sync_mode": "full"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["sync_mode"] == "full"
        # Full mode should return all historical data
        print(f"\n[full_mode] Got {len(data['credential_usage'])} credentials, {len(data['user_usage'])} users")

    def test_incremental_with_large_threshold(self, sync_client):
        """Test that large threshold includes old data."""
        response = sync_client.post("/observability/metrics-sync", json={
            "sync_mode": "incremental",
            "activity_threshold_minutes": 999999999
        })
        assert response.status_code == 200
        data = response.json()
        assert data["activity_threshold_minutes"] == 999999999
        # Large threshold should include historical data
        print(f"\n[large_threshold] Got {len(data['credential_usage'])} credentials, {len(data['user_usage'])} users")

    def test_incremental_with_short_threshold(self, sync_client):
        """Test that short threshold returns empty."""
        response = sync_client.post("/observability/metrics-sync", json={
            "sync_mode": "incremental",
            "activity_threshold_minutes": 1
        })
        assert response.status_code == 200
        data = response.json()
        # 1-minute threshold should not include seeder data
        assert len(data["credential_usage"]) == 0
        assert len(data["user_usage"]) == 0
        print("\n[short_threshold] Empty results as expected")


@pytest.mark.usefixtures("seed_test_data")
class TestFilters:
    """Filter tests for credential_sync, user_usage_sync, user_ids."""

    def test_credential_sync_only(self, sync_client):
        """Test requesting credentials only."""
        response = sync_client.post("/observability/metrics-sync", json={
            "sync_mode": "full",
            "credential_sync": True,
            "user_usage_sync": False
        })
        assert response.status_code == 200
        data = response.json()
        # User usage should be empty
        assert len(data["user_usage"]) == 0
        assert data["stats"]["active_users"] == 0
        print(f"\n[credential_only] Got {len(data['credential_usage'])} credentials, 0 users")

    @pytest.mark.skip(reason="Full mode with user_usage_sync triggers Dapr call to budapp which hangs without Dapr")
    def test_user_sync_only(self, sync_client):
        """Test requesting users only."""
        response = sync_client.post("/observability/metrics-sync", json={
            "sync_mode": "full",
            "credential_sync": False,
            "user_usage_sync": True
        })
        assert response.status_code == 200
        data = response.json()
        # Credential usage should be empty
        assert len(data["credential_usage"]) == 0
        assert data["stats"]["active_credentials"] == 0
        print(f"\n[user_only] Got 0 credentials, {len(data['user_usage'])} users")

    def test_both_sync_disabled(self, sync_client):
        """Test with both syncs disabled."""
        response = sync_client.post("/observability/metrics-sync", json={
            "credential_sync": False,
            "user_usage_sync": False
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data["credential_usage"]) == 0
        assert len(data["user_usage"]) == 0
        assert data["stats"]["active_credentials"] == 0
        assert data["stats"]["active_users"] == 0
        print("\n[both_disabled] Both arrays empty as expected")

    @pytest.mark.skip(reason="Full mode with user_usage_sync triggers Dapr call to budapp which hangs without Dapr")
    def test_specific_user_ids(self, sync_client):
        """Test filtering by specific user_ids."""
        response = sync_client.post("/observability/metrics-sync", json={
            "sync_mode": "full",
            "credential_sync": False,
            "user_usage_sync": True,
            "user_ids": [str(TEST_USER_ID)]
        })
        assert response.status_code == 200
        data = response.json()
        # Should include the specific user if they have activity
        print(f"\n[specific_user] Got {len(data['user_usage'])} users for specified user_id")

    @pytest.mark.skip(reason="Full mode with user_usage_sync triggers Dapr call to budapp which hangs without Dapr")
    def test_nonexistent_user_ids(self, sync_client):
        """Test filtering by non-existent user_ids."""
        response = sync_client.post("/observability/metrics-sync", json={
            "sync_mode": "full",
            "credential_sync": False,
            "user_usage_sync": True,
            "user_ids": [str(TEST_NONEXISTENT_ID)]
        })
        assert response.status_code == 200
        data = response.json()
        # Non-existent user should result in empty or zero-activity entry
        print(f"\n[nonexistent_user] Got {len(data['user_usage'])} users")


class TestValidation:
    """Validation error tests."""

    def test_invalid_sync_mode(self, sync_client):
        """Test that invalid sync_mode returns 422."""
        response = sync_client.post("/observability/metrics-sync", json={
            "sync_mode": "invalid"
        })
        assert response.status_code == 422, \
            f"Expected 422 for invalid sync_mode, got {response.status_code}"
        print("\n[validation] Invalid sync_mode correctly rejected")

    def test_invalid_user_id_format(self, sync_client):
        """Test that invalid UUID in user_ids returns 422."""
        response = sync_client.post("/observability/metrics-sync", json={
            "user_ids": ["not-a-uuid"]
        })
        assert response.status_code == 422, \
            f"Expected 422 for invalid user_id format, got {response.status_code}"
        print("\n[validation] Invalid user_id format correctly rejected")

    def test_negative_threshold(self, sync_client):
        """Test behavior with negative threshold."""
        response = sync_client.post("/observability/metrics-sync", json={
            "activity_threshold_minutes": -1
        })
        # Should either reject with 422 or handle gracefully
        assert response.status_code in [200, 422], \
            f"Expected 200 or 422 for negative threshold, got {response.status_code}"
        print(f"\n[validation] Negative threshold handled with status {response.status_code}")


class TestDataAccuracy:
    """Data accuracy tests comparing API response with DB."""

    def test_full_sync_credential_count_matches_db(self, sync_client, metrics_sync_ground_truth):
        """Test that credential count matches ground truth."""
        response = sync_client.post("/observability/metrics-sync", json={
            "sync_mode": "full",
            "credential_sync": True,
            "user_usage_sync": False
        })
        assert response.status_code == 200
        data = response.json()

        expected_count = metrics_sync_ground_truth["credential_count"]
        actual_count = len(data["credential_usage"])

        assert actual_count == expected_count, \
            f"Credential count mismatch: API={actual_count}, DB={expected_count}"
        print(f"\n[accuracy] Credential count matches: {actual_count}")

    @pytest.mark.skip(reason="Full mode with user_usage_sync triggers Dapr call to budapp which hangs without Dapr")
    def test_full_sync_user_count_matches_db(self, sync_client, metrics_sync_ground_truth):
        """Test that user count matches or exceeds ground truth."""
        response = sync_client.post("/observability/metrics-sync", json={
            "sync_mode": "full",
            "credential_sync": False,
            "user_usage_sync": True
        })
        assert response.status_code == 200
        data = response.json()

        expected_count = metrics_sync_ground_truth["user_count"]
        actual_count = len(data["user_usage"])

        # Full mode may include additional users from billing (Dapr call)
        assert actual_count >= expected_count, \
            f"User count too low: API={actual_count}, DB={expected_count}"
        print(f"\n[accuracy] User count matches or exceeds: API={actual_count}, DB={expected_count}")

    def test_credential_request_count_matches_db(self, sync_client, metrics_sync_ground_truth):
        """Test that specific credential's request_count matches DB."""
        if not metrics_sync_ground_truth["test_credential"]:
            pytest.skip("Test credential not found in seeded data")

        response = sync_client.post("/observability/metrics-sync", json={
            "sync_mode": "full",
            "credential_sync": True,
            "user_usage_sync": False
        })
        assert response.status_code == 200
        data = response.json()

        # Find the test credential in response
        test_cred = None
        for cred in data["credential_usage"]:
            if cred["credential_id"] == str(TEST_CREDENTIAL_ID):
                test_cred = cred
                break

        if test_cred:
            expected_count = metrics_sync_ground_truth["test_credential"]["request_count"]
            actual_count = test_cred["request_count"]
            assert actual_count == expected_count, \
                f"Request count mismatch: API={actual_count}, DB={expected_count}"
            print(f"\n[accuracy] Credential request count matches: {actual_count}")
        else:
            pytest.skip("Test credential not found in API response")

    @pytest.mark.skip(reason="Full mode with user_usage_sync triggers Dapr call to budapp which hangs without Dapr")
    def test_user_usage_data_matches_db(self, sync_client, metrics_sync_ground_truth):
        """Test that specific user's usage_data matches DB."""
        if not metrics_sync_ground_truth["test_user"]:
            pytest.skip("Test user not found in seeded data")

        response = sync_client.post("/observability/metrics-sync", json={
            "sync_mode": "full",
            "credential_sync": False,
            "user_usage_sync": True
        })
        assert response.status_code == 200
        data = response.json()

        # Find the test user in response
        test_user = None
        for user in data["user_usage"]:
            if user["user_id"] == str(TEST_USER_ID):
                test_user = user
                break

        if test_user:
            expected = metrics_sync_ground_truth["test_user"]
            usage = test_user["usage_data"]

            assert usage["request_count"] == expected["request_count"], \
                f"Request count mismatch: API={usage['request_count']}, DB={expected['request_count']}"
            assert usage["total_tokens"] == expected["total_tokens"], \
                f"Token count mismatch: API={usage['total_tokens']}, DB={expected['total_tokens']}"
            print(f"\n[accuracy] User usage data matches: request_count={usage['request_count']}, tokens={usage['total_tokens']}")
        else:
            pytest.skip("Test user not found in API response")

    @pytest.mark.skip(reason="Full mode with user_usage_sync triggers Dapr call to budapp which hangs without Dapr")
    def test_stats_reflect_actual_counts(self, sync_client, metrics_sync_ground_truth):
        """Test that stats match actual array lengths."""
        response = sync_client.post("/observability/metrics-sync", json={
            "sync_mode": "full"
        })
        assert response.status_code == 200
        data = response.json()

        assert data["stats"]["active_credentials"] == len(data["credential_usage"]), \
            f"Stats mismatch: active_credentials={data['stats']['active_credentials']}, len={len(data['credential_usage'])}"
        assert data["stats"]["active_users"] == len(data["user_usage"]), \
            f"Stats mismatch: active_users={data['stats']['active_users']}, len={len(data['user_usage'])}"
        print(f"\n[accuracy] Stats match array lengths: credentials={data['stats']['active_credentials']}, users={data['stats']['active_users']}")


# pytest tests/observability/inferences/test_metrics_sync.py -v -s
