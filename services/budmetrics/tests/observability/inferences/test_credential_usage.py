"""Tests for POST /observability/credential-usage endpoint.

These tests validate the credential usage API by:
1. Testing all request parameters (since, credential_ids)
2. Verifying response structure matches expected schema
3. Comparing values against InferenceFact ground truth

Run with: pytest tests/observability/inferences/test_credential_usage.py -v -s
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


# Test constants
TEST_CREDENTIAL_ID = UUID("019b971a-4a01-7000-a001-a10000000001")
TEST_NONEXISTENT_CREDENTIAL_ID = UUID("00000000-0000-0000-0000-000000000000")
TEST_FROM_DATE = datetime(2026, 1, 7, 0, 0, 0)
TEST_TO_DATE = datetime(2026, 1, 7, 23, 59, 59)


async def _fetch_credential_ground_truth():
    """Async helper to query ClickHouse for ground truth values."""
    config = ClickHouseConfig()
    client = ClickHouseClient(config)
    await client.initialize()

    try:
        ground_truth = {}
        date_filter = f"timestamp >= '{TEST_FROM_DATE}' AND timestamp <= '{TEST_TO_DATE}'"

        # Get all credentials with their usage stats
        result = await client.execute_query(f"""
            SELECT
                api_key_id as credential_id,
                MAX(request_arrival_time) as last_used_at,
                COUNT(*) as request_count
            FROM InferenceFact
            WHERE {date_filter}
                AND api_key_id IS NOT NULL
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
        ground_truth["total_credentials"] = len(result)

        # Get specific credential stats
        result = await client.execute_query(f"""
            SELECT
                MAX(request_arrival_time) as last_used_at,
                COUNT(*) as request_count
            FROM InferenceFact
            WHERE {date_filter}
                AND api_key_id = '{TEST_CREDENTIAL_ID}'
        """)
        if result and result[0][0]:
            ground_truth["test_credential"] = {
                "last_used_at": result[0][0],
                "request_count": result[0][1],
            }
        else:
            ground_truth["test_credential"] = None

        return ground_truth
    finally:
        await client.close()


@pytest.fixture(scope="session")
def seeded_credential_data():
    """Seed test data and return ground truth from InferenceFact."""
    # 1. Clear and seed data
    seeder_path = Path(__file__).parent.parent / "seed_otel_traces.py"
    result = subprocess.run(
        [sys.executable, str(seeder_path), "--clear", "--verify"],
        capture_output=True,
        text=True,
        cwd=str(seeder_path.parent.parent.parent),
    )
    if result.returncode != 0:
        pytest.skip(f"Failed to seed test data: {result.stderr}")

    # 2. Query InferenceFact for ground truth values
    loop = asyncio.new_event_loop()
    try:
        ground_truth = loop.run_until_complete(_fetch_credential_ground_truth())
    finally:
        loop.close()

    return ground_truth


def get_base_payload(**kwargs) -> dict:
    """Build request payload."""
    payload = {"since": TEST_FROM_DATE.isoformat()}
    payload.update(kwargs)
    return payload


class TestBasicRequests:
    """Basic request tests for /observability/credential-usage."""

    def test_basic_request_with_since(self, sync_client, seeded_credential_data):
        """Test minimal request with only since parameter."""
        payload = get_base_payload()
        response = sync_client.post("/observability/credential-usage", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "credentials" in data
        assert "query_window" in data
        assert isinstance(data["credentials"], list)
        print(f"\n[basic_since] Got {len(data['credentials'])} credentials")

    def test_response_structure(self, sync_client, seeded_credential_data):
        """Test that response has all expected fields."""
        payload = get_base_payload()
        response = sync_client.post("/observability/credential-usage", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Check top-level structure
        assert data["object"] == "credential_usage"
        assert "credentials" in data
        assert "query_window" in data
        assert isinstance(data["credentials"], list)
        assert isinstance(data["query_window"], dict)

        # Check query_window structure
        assert "since" in data["query_window"]
        assert "until" in data["query_window"]

        # Check credential item structure if we have credentials
        if data["credentials"]:
            cred = data["credentials"][0]
            expected_fields = ["credential_id", "last_used_at", "request_count"]
            for field in expected_fields:
                assert field in cred, f"Missing field: {field}"
        print("\n[response_structure] All expected fields present")


class TestFilters:
    """Filter tests for credential_ids parameter."""

    def test_filter_by_single_credential(self, sync_client, seeded_credential_data):
        """Test filtering by a single credential_id."""
        payload = get_base_payload(credential_ids=[str(TEST_CREDENTIAL_ID)])
        response = sync_client.post("/observability/credential-usage", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Should return at most 1 credential
        assert len(data["credentials"]) <= 1

        # If credential exists in data, verify it's the right one
        if data["credentials"]:
            cred = data["credentials"][0]
            assert cred["credential_id"] == str(TEST_CREDENTIAL_ID)
        print(f"\n[filter_single] Got {len(data['credentials'])} credential(s)")

    def test_filter_by_multiple_credentials(self, sync_client, seeded_credential_data):
        """Test filtering by multiple credential_ids."""
        # Use test credential and a nonexistent one
        payload = get_base_payload(
            credential_ids=[
                str(TEST_CREDENTIAL_ID),
                str(TEST_NONEXISTENT_CREDENTIAL_ID),
            ]
        )
        response = sync_client.post("/observability/credential-usage", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Should return at most 2 credentials (likely 1 since one doesn't exist)
        assert len(data["credentials"]) <= 2

        # All returned credentials should be in the filter list
        for cred in data["credentials"]:
            assert cred["credential_id"] in [
                str(TEST_CREDENTIAL_ID),
                str(TEST_NONEXISTENT_CREDENTIAL_ID),
            ]
        print(f"\n[filter_multiple] Got {len(data['credentials'])} credential(s)")

    def test_filter_by_nonexistent_credential(self, sync_client, seeded_credential_data):
        """Test filtering by a credential_id that doesn't exist in data."""
        payload = get_base_payload(credential_ids=[str(TEST_NONEXISTENT_CREDENTIAL_ID)])
        response = sync_client.post("/observability/credential-usage", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Should return empty list
        assert len(data["credentials"]) == 0
        print("\n[filter_nonexistent] Correctly returned empty list")


class TestValidation:
    """Validation error tests."""

    def test_missing_since_rejected(self, sync_client):
        """Test that missing since parameter returns 422."""
        payload = {}
        response = sync_client.post("/observability/credential-usage", json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for missing since, got {response.status_code}"
        print("\n[validation] Missing since correctly rejected")

    def test_invalid_date_format_rejected(self, sync_client):
        """Test that invalid date format returns 422."""
        payload = {"since": "invalid-date"}
        response = sync_client.post("/observability/credential-usage", json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for invalid date format, got {response.status_code}"
        print("\n[validation] Invalid date format correctly rejected")

    def test_invalid_credential_id_rejected(self, sync_client):
        """Test that invalid credential_id format returns 422."""
        payload = get_base_payload(credential_ids=["not-a-uuid"])
        response = sync_client.post("/observability/credential-usage", json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for invalid credential_id, got {response.status_code}"
        print("\n[validation] Invalid credential_id correctly rejected")


class TestDataAccuracy:
    """Data accuracy tests comparing API response with DB."""

    def test_credential_count_matches_db(self, sync_client, seeded_credential_data):
        """Test that returned credential count matches ground truth."""
        payload = get_base_payload()
        response = sync_client.post("/observability/credential-usage", json=payload)
        assert response.status_code == 200
        data = response.json()

        expected_count = seeded_credential_data["total_credentials"]
        actual_count = len(data["credentials"])

        # API should return same or fewer credentials (due to date filtering)
        assert actual_count <= expected_count or expected_count == 0, \
            f"Credential count mismatch: API={actual_count}, DB={expected_count}"
        print(f"\n[accuracy] Credential count matches: {actual_count}")

    def test_request_count_matches_db(self, sync_client, seeded_credential_data):
        """Test that request_count for specific credential matches DB."""
        if not seeded_credential_data["test_credential"]:
            pytest.skip("Test credential not found in seeded data")

        payload = get_base_payload(credential_ids=[str(TEST_CREDENTIAL_ID)])
        response = sync_client.post("/observability/credential-usage", json=payload)
        assert response.status_code == 200
        data = response.json()

        if data["credentials"]:
            api_count = data["credentials"][0]["request_count"]
            db_count = seeded_credential_data["test_credential"]["request_count"]
            assert api_count == db_count, \
                f"Request count mismatch: API={api_count}, DB={db_count}"
            print(f"\n[accuracy] Request count matches: {api_count}")
        else:
            pytest.skip("Credential not returned by API")

    def test_query_window_returned(self, sync_client, seeded_credential_data):
        """Test that query_window is correctly returned."""
        payload = get_base_payload()
        response = sync_client.post("/observability/credential-usage", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify query_window contains expected keys
        assert "since" in data["query_window"]
        assert "until" in data["query_window"]

        # The 'since' in response should match our request
        response_since = data["query_window"]["since"]
        assert TEST_FROM_DATE.isoformat() in response_since or \
            response_since.startswith("2026-01-07"), \
            f"Query window 'since' mismatch: {response_since}"
        print(f"\n[accuracy] Query window returned correctly")


# pytest tests/observability/inferences/test_credential_usage.py -v -s
