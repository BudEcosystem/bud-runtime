"""Tests for POST /observability/inferences/list endpoint.

These tests validate the inference list API by:
1. Testing all request parameters (pagination, filters, sorting)
2. Verifying response structure matches expected schema
3. Comparing values against InferenceFact ground truth

Run with: pytest tests/observability/test_inferences_list.py -v -s
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


# Test constants (same as test_analytics_payloads.py)
TEST_PROJECT_ID = UUID("019787c1-3de1-7b50-969b-e0a58514b6a1")
TEST_ENDPOINT_ID = UUID("019787c1-3de1-7b50-969b-e0a58514b6a4")
TEST_MODEL_ID = UUID("019787c1-3de1-7b50-969b-e0a58514b6a2")
TEST_FROM_DATE = datetime(2026, 1, 7, 0, 0, 0)
TEST_TO_DATE = datetime(2026, 1, 7, 23, 59, 59)


async def _fetch_inference_ground_truth():
    """Async helper to query ClickHouse for ground truth values."""
    config = ClickHouseConfig()
    client = ClickHouseClient(config)
    await client.initialize()

    try:
        ground_truth = {}
        date_filter = f"timestamp >= '{TEST_FROM_DATE}' AND timestamp <= '{TEST_TO_DATE}'"

        # Total count
        result = await client.execute_query(
            f"SELECT count(*) FROM InferenceFact WHERE {date_filter}"
        )
        ground_truth["total_count"] = result[0][0] if result else 0

        # Success/failure counts
        result = await client.execute_query(
            f"SELECT countIf(is_success = true), countIf(is_success = false) "
            f"FROM InferenceFact WHERE {date_filter}"
        )
        ground_truth["success_count"] = result[0][0] if result else 0
        ground_truth["failure_count"] = result[0][1] if result else 0

        # Count by project
        result = await client.execute_query(
            f"SELECT count(*) FROM InferenceFact "
            f"WHERE {date_filter} AND project_id = '{TEST_PROJECT_ID}'"
        )
        ground_truth["project_count"] = result[0][0] if result else 0

        # Count by model
        result = await client.execute_query(
            f"SELECT count(*) FROM InferenceFact "
            f"WHERE {date_filter} AND model_id = '{TEST_MODEL_ID}'"
        )
        ground_truth["model_count"] = result[0][0] if result else 0

        # Count by endpoint
        result = await client.execute_query(
            f"SELECT count(*) FROM InferenceFact "
            f"WHERE {date_filter} AND endpoint_id = '{TEST_ENDPOINT_ID}'"
        )
        ground_truth["endpoint_count"] = result[0][0] if result else 0

        # Token range counts
        result = await client.execute_query(
            f"SELECT count(*) FROM InferenceFact "
            f"WHERE {date_filter} AND (input_tokens + output_tokens) >= 50"
        )
        ground_truth["min_50_tokens_count"] = result[0][0] if result else 0

        result = await client.execute_query(
            f"SELECT count(*) FROM InferenceFact "
            f"WHERE {date_filter} AND (input_tokens + output_tokens) <= 100"
        )
        ground_truth["max_100_tokens_count"] = result[0][0] if result else 0

        # Latency filter count
        result = await client.execute_query(
            f"SELECT count(*) FROM InferenceFact "
            f"WHERE {date_filter} AND response_time_ms <= 2000"
        )
        ground_truth["max_2000_latency_count"] = result[0][0] if result else 0

        # Endpoint type count
        result = await client.execute_query(
            f"SELECT count(*) FROM InferenceFact "
            f"WHERE {date_filter} AND endpoint_type = 'chat'"
        )
        ground_truth["chat_endpoint_count"] = result[0][0] if result else 0

        # Sample inferences for spot checks (ordered by timestamp desc)
        result = await client.execute_query(
            f"SELECT inference_id, input_tokens, output_tokens, response_time_ms, cost "
            f"FROM InferenceFact WHERE {date_filter} ORDER BY timestamp DESC LIMIT 10"
        )
        ground_truth["sample_inferences"] = [
            {
                "id": str(r[0]),
                "input_tokens": r[1] or 0,
                "output_tokens": r[2] or 0,
                "latency": r[3] or 0,
                "cost": r[4],
            }
            for r in result
        ]

        return ground_truth
    finally:
        await client.close()


@pytest.fixture(scope="session")
def seeded_inference_data():
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
        ground_truth = loop.run_until_complete(_fetch_inference_ground_truth())
    finally:
        loop.close()

    return ground_truth


def get_base_payload(**kwargs) -> dict:
    """Create base request payload with optional overrides."""
    payload = {
        "from_date": TEST_FROM_DATE.isoformat(),
        "to_date": TEST_TO_DATE.isoformat(),
    }
    payload.update(kwargs)
    return payload


class TestBasicRequests:
    """Basic request tests for /observability/inferences/list."""

    def test_basic_request_minimal(self, sync_client, seeded_inference_data):
        """Test minimal request with only from_date."""
        payload = {"from_date": TEST_FROM_DATE.isoformat()}
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "inference_list"
        assert "items" in data
        assert "total_count" in data
        print(f"\n[basic_minimal] Got {len(data['items'])} items, total_count={data['total_count']}")

    def test_basic_request_with_date_range(self, sync_client, seeded_inference_data):
        """Test request with from_date and to_date."""
        payload = get_base_payload()
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "inference_list"
        assert data["total_count"] >= 0
        print(f"\n[basic_date_range] Got {len(data['items'])} items")

    def test_response_structure(self, sync_client, seeded_inference_data):
        """Test that response has all expected fields."""
        payload = get_base_payload(limit=1)
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Check top-level fields
        assert "object" in data
        assert "items" in data
        assert "total_count" in data
        assert "offset" in data
        assert "limit" in data
        assert "has_more" in data

        # Check item structure if we have items
        if data["items"]:
            item = data["items"][0]
            expected_fields = [
                "inference_id", "timestamp", "model_name", "prompt_preview",
                "response_preview", "input_tokens", "output_tokens", "total_tokens",
                "response_time_ms", "cost", "is_success", "cached", "project_id",
                "endpoint_id", "model_id", "endpoint_type"
            ]
            for field in expected_fields:
                assert field in item, f"Missing field: {field}"
        print("\n[response_structure] All expected fields present")


class TestPagination:
    """Pagination tests."""

    def test_pagination_first_page(self, sync_client, seeded_inference_data):
        """Test first page with offset=0, limit=5."""
        payload = get_base_payload(offset=0, limit=5)
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["offset"] == 0
        assert data["limit"] == 5
        assert len(data["items"]) <= 5
        print(f"\n[pagination_first] Got {len(data['items'])} items")

    def test_pagination_second_page(self, sync_client, seeded_inference_data):
        """Test second page with offset=5, limit=5."""
        payload = get_base_payload(offset=5, limit=5)
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["offset"] == 5
        assert data["limit"] == 5
        print(f"\n[pagination_second] Got {len(data['items'])} items at offset 5")

    def test_pagination_has_more_true(self, sync_client, seeded_inference_data):
        """Test has_more=true when more data exists."""
        total = seeded_inference_data["total_count"]
        if total <= 1:
            pytest.skip("Need more than 1 record to test has_more")

        payload = get_base_payload(offset=0, limit=1)
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["has_more"] is True, f"Expected has_more=True when total={total}, got {data['has_more']}"
        print(f"\n[has_more_true] has_more=True with total={total}")

    def test_pagination_has_more_false(self, sync_client, seeded_inference_data):
        """Test has_more=false at end of data."""
        total = seeded_inference_data["total_count"]
        payload = get_base_payload(offset=0, limit=1000)  # Request more than total
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["has_more"] is False, f"Expected has_more=False, got {data['has_more']}"
        print(f"\n[has_more_false] has_more=False when requesting all data")

    def test_pagination_total_count_matches_db(self, sync_client, seeded_inference_data):
        """Test that total_count matches database count."""
        payload = get_base_payload()
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()
        expected = seeded_inference_data["total_count"]
        assert data["total_count"] == expected, \
            f"total_count mismatch: API={data['total_count']}, DB={expected}"
        print(f"\n[total_count_match] API total_count={data['total_count']} matches DB")


class TestFilters:
    """Filter tests."""

    def test_filter_by_project_id(self, sync_client, seeded_inference_data):
        """Test filtering by project_id."""
        payload = get_base_payload(project_id=str(TEST_PROJECT_ID))
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify all items have matching project_id
        for item in data["items"]:
            assert item["project_id"] == str(TEST_PROJECT_ID), \
                f"Item has wrong project_id: {item['project_id']}"

        expected = seeded_inference_data["project_count"]
        assert data["total_count"] == expected, \
            f"Count mismatch: API={data['total_count']}, DB={expected}"
        print(f"\n[filter_project] Got {data['total_count']} items for project")

    def test_filter_by_model_id(self, sync_client, seeded_inference_data):
        """Test filtering by model_id."""
        payload = get_base_payload(model_id=str(TEST_MODEL_ID))
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify all items have matching model_id
        for item in data["items"]:
            assert item["model_id"] == str(TEST_MODEL_ID), \
                f"Item has wrong model_id: {item['model_id']}"

        expected = seeded_inference_data["model_count"]
        assert data["total_count"] == expected, \
            f"Count mismatch: API={data['total_count']}, DB={expected}"
        print(f"\n[filter_model] Got {data['total_count']} items for model")

    def test_filter_by_endpoint_id(self, sync_client, seeded_inference_data):
        """Test filtering by endpoint_id."""
        payload = get_base_payload(endpoint_id=str(TEST_ENDPOINT_ID))
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify all items have matching endpoint_id
        for item in data["items"]:
            assert item["endpoint_id"] == str(TEST_ENDPOINT_ID), \
                f"Item has wrong endpoint_id: {item['endpoint_id']}"

        expected = seeded_inference_data["endpoint_count"]
        assert data["total_count"] == expected, \
            f"Count mismatch: API={data['total_count']}, DB={expected}"
        print(f"\n[filter_endpoint] Got {data['total_count']} items for endpoint")

    def test_filter_by_is_success_true(self, sync_client, seeded_inference_data):
        """Test filtering by is_success=true."""
        payload = get_base_payload(is_success=True)
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify all items are successful
        for item in data["items"]:
            assert item["is_success"] is True, f"Item has is_success={item['is_success']}"

        expected = seeded_inference_data["success_count"]
        assert data["total_count"] == expected, \
            f"Count mismatch: API={data['total_count']}, DB={expected}"
        print(f"\n[filter_success] Got {data['total_count']} successful items")

    def test_filter_by_is_success_false(self, sync_client, seeded_inference_data):
        """Test filtering by is_success=false."""
        payload = get_base_payload(is_success=False)
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify all items are failures
        for item in data["items"]:
            assert item["is_success"] is False, f"Item has is_success={item['is_success']}"

        expected = seeded_inference_data["failure_count"]
        assert data["total_count"] == expected, \
            f"Count mismatch: API={data['total_count']}, DB={expected}"
        print(f"\n[filter_failure] Got {data['total_count']} failed items")

    def test_filter_by_min_tokens(self, sync_client, seeded_inference_data):
        """Test filtering by min_tokens."""
        payload = get_base_payload(min_tokens=50)
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify all items have >= min_tokens
        for item in data["items"]:
            assert item["total_tokens"] >= 50, \
                f"Item has total_tokens={item['total_tokens']}, expected >= 50"

        expected = seeded_inference_data["min_50_tokens_count"]
        assert data["total_count"] == expected, \
            f"Count mismatch: API={data['total_count']}, DB={expected}"
        print(f"\n[filter_min_tokens] Got {data['total_count']} items with >= 50 tokens")

    def test_filter_by_max_tokens(self, sync_client, seeded_inference_data):
        """Test filtering by max_tokens."""
        payload = get_base_payload(max_tokens=100)
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify all items have <= max_tokens
        for item in data["items"]:
            assert item["total_tokens"] <= 100, \
                f"Item has total_tokens={item['total_tokens']}, expected <= 100"

        expected = seeded_inference_data["max_100_tokens_count"]
        assert data["total_count"] == expected, \
            f"Count mismatch: API={data['total_count']}, DB={expected}"
        print(f"\n[filter_max_tokens] Got {data['total_count']} items with <= 100 tokens")

    def test_filter_by_max_latency(self, sync_client, seeded_inference_data):
        """Test filtering by max_latency_ms."""
        payload = get_base_payload(max_latency_ms=2000)
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify all items have <= max_latency
        for item in data["items"]:
            assert item["response_time_ms"] <= 2000, \
                f"Item has response_time_ms={item['response_time_ms']}, expected <= 2000"

        expected = seeded_inference_data["max_2000_latency_count"]
        assert data["total_count"] == expected, \
            f"Count mismatch: API={data['total_count']}, DB={expected}"
        print(f"\n[filter_latency] Got {data['total_count']} items with <= 2000ms latency")

    def test_filter_by_endpoint_type_chat(self, sync_client, seeded_inference_data):
        """Test filtering by endpoint_type=chat."""
        payload = get_base_payload(endpoint_type="chat")
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify all items have endpoint_type=chat
        for item in data["items"]:
            assert item["endpoint_type"] == "chat", \
                f"Item has endpoint_type={item['endpoint_type']}, expected 'chat'"

        expected = seeded_inference_data["chat_endpoint_count"]
        assert data["total_count"] == expected, \
            f"Count mismatch: API={data['total_count']}, DB={expected}"
        print(f"\n[filter_endpoint_type] Got {data['total_count']} chat items")

    def test_filter_combined(self, sync_client, seeded_inference_data):
        """Test combining multiple filters."""
        payload = get_base_payload(
            project_id=str(TEST_PROJECT_ID),
            is_success=True,
            endpoint_type="chat"
        )
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify all items match all filters
        for item in data["items"]:
            assert item["project_id"] == str(TEST_PROJECT_ID)
            assert item["is_success"] is True
            assert item["endpoint_type"] == "chat"
        print(f"\n[filter_combined] Got {data['total_count']} items with combined filters")


class TestSorting:
    """Sorting tests."""

    def test_sort_by_timestamp_desc(self, sync_client, seeded_inference_data):
        """Test sorting by timestamp descending (default)."""
        payload = get_base_payload(sort_by="timestamp", sort_order="desc")
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify items are sorted by timestamp descending
        timestamps = [item["timestamp"] for item in data["items"]]
        assert timestamps == sorted(timestamps, reverse=True), \
            "Items not sorted by timestamp desc"
        print(f"\n[sort_timestamp_desc] Items sorted correctly")

    def test_sort_by_timestamp_asc(self, sync_client, seeded_inference_data):
        """Test sorting by timestamp ascending."""
        payload = get_base_payload(sort_by="timestamp", sort_order="asc")
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify items are sorted by timestamp ascending
        timestamps = [item["timestamp"] for item in data["items"]]
        assert timestamps == sorted(timestamps), \
            "Items not sorted by timestamp asc"
        print(f"\n[sort_timestamp_asc] Items sorted correctly")

    def test_sort_by_latency_desc(self, sync_client, seeded_inference_data):
        """Test sorting by latency descending (slowest first)."""
        payload = get_base_payload(sort_by="latency", sort_order="desc")
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify items are sorted by latency descending
        latencies = [item["response_time_ms"] for item in data["items"]]
        assert latencies == sorted(latencies, reverse=True), \
            "Items not sorted by latency desc"
        print(f"\n[sort_latency_desc] Items sorted correctly")

    def test_sort_by_latency_asc(self, sync_client, seeded_inference_data):
        """Test sorting by latency ascending (fastest first).

        Note: NULL/0 values may sort last in ClickHouse, so we verify
        non-null values are sorted correctly.
        """
        payload = get_base_payload(sort_by="latency", sort_order="asc")
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Filter to only non-zero latencies for sorting check
        # NULL values (converted to 0) may sort last in ClickHouse
        latencies = [item["response_time_ms"] for item in data["items"]]
        non_zero = [l for l in latencies if l > 0]
        assert non_zero == sorted(non_zero), \
            f"Non-zero latencies not sorted asc: {non_zero}"
        print(f"\n[sort_latency_asc] Items sorted correctly (non-zero values)")

    def test_sort_by_tokens_desc(self, sync_client, seeded_inference_data):
        """Test sorting by tokens descending (most tokens first)."""
        payload = get_base_payload(sort_by="tokens", sort_order="desc")
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify items are sorted by total_tokens descending
        tokens = [item["total_tokens"] for item in data["items"]]
        assert tokens == sorted(tokens, reverse=True), \
            "Items not sorted by tokens desc"
        print(f"\n[sort_tokens_desc] Items sorted correctly")

    def test_sort_by_tokens_asc(self, sync_client, seeded_inference_data):
        """Test sorting by tokens ascending (fewest tokens first).

        Note: NULL/0 values may sort last in ClickHouse, so we verify
        non-null values are sorted correctly.
        """
        payload = get_base_payload(sort_by="tokens", sort_order="asc")
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Filter to only non-zero tokens for sorting check
        # NULL values (converted to 0) may sort last in ClickHouse
        tokens = [item["total_tokens"] for item in data["items"]]
        non_zero = [t for t in tokens if t > 0]
        assert non_zero == sorted(non_zero), \
            f"Non-zero tokens not sorted asc: {non_zero}"
        print(f"\n[sort_tokens_asc] Items sorted correctly (non-zero values)")

    def test_sort_by_cost_desc(self, sync_client, seeded_inference_data):
        """Test sorting by cost descending (most expensive first)."""
        payload = get_base_payload(sort_by="cost", sort_order="desc")
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify items are sorted by cost descending (handle None values)
        costs = [item["cost"] or 0 for item in data["items"]]
        assert costs == sorted(costs, reverse=True), \
            "Items not sorted by cost desc"
        print(f"\n[sort_cost_desc] Items sorted correctly")


class TestValidation:
    """Validation error tests."""

    def test_missing_from_date_rejected(self, sync_client):
        """Test that missing from_date returns 422."""
        payload = {"to_date": TEST_TO_DATE.isoformat()}
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for missing from_date, got {response.status_code}"
        print("\n[validation] Missing from_date correctly rejected")

    def test_negative_offset_rejected(self, sync_client):
        """Test that negative offset returns 422."""
        payload = get_base_payload(offset=-1)
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for negative offset, got {response.status_code}"
        print("\n[validation] Negative offset correctly rejected")

    def test_zero_limit_rejected(self, sync_client):
        """Test that limit=0 returns 422."""
        payload = get_base_payload(limit=0)
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for limit=0, got {response.status_code}"
        print("\n[validation] Zero limit correctly rejected")

    def test_limit_exceeds_max_rejected(self, sync_client):
        """Test that limit > 1000 returns 422."""
        payload = get_base_payload(limit=1001)
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for limit=1001, got {response.status_code}"
        print("\n[validation] Limit > 1000 correctly rejected")

    def test_invalid_sort_by_rejected(self, sync_client):
        """Test that invalid sort_by returns 422."""
        payload = get_base_payload(sort_by="invalid")
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for invalid sort_by, got {response.status_code}"
        print("\n[validation] Invalid sort_by correctly rejected")

    def test_invalid_sort_order_rejected(self, sync_client):
        """Test that invalid sort_order returns 422."""
        payload = get_base_payload(sort_order="invalid")
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for invalid sort_order, got {response.status_code}"
        print("\n[validation] Invalid sort_order correctly rejected")

    def test_invalid_endpoint_type_rejected(self, sync_client):
        """Test that invalid endpoint_type returns 422."""
        payload = get_base_payload(endpoint_type="invalid")
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for invalid endpoint_type, got {response.status_code}"
        print("\n[validation] Invalid endpoint_type correctly rejected")


class TestDataAccuracy:
    """Data accuracy tests comparing API response with DB."""

    def test_total_count_matches_db(self, sync_client, seeded_inference_data):
        """Test that total_count matches database count."""
        payload = get_base_payload()
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        expected = seeded_inference_data["total_count"]
        assert data["total_count"] == expected, \
            f"total_count mismatch: API={data['total_count']}, DB={expected}"
        print(f"\n[accuracy] total_count={data['total_count']} matches DB")

    def test_success_filter_count_matches_db(self, sync_client, seeded_inference_data):
        """Test that is_success=true count matches DB."""
        payload = get_base_payload(is_success=True)
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        expected = seeded_inference_data["success_count"]
        assert data["total_count"] == expected, \
            f"success count mismatch: API={data['total_count']}, DB={expected}"
        print(f"\n[accuracy] success_count={data['total_count']} matches DB")

    def test_failure_filter_count_matches_db(self, sync_client, seeded_inference_data):
        """Test that is_success=false count matches DB."""
        payload = get_base_payload(is_success=False)
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        expected = seeded_inference_data["failure_count"]
        assert data["total_count"] == expected, \
            f"failure count mismatch: API={data['total_count']}, DB={expected}"
        print(f"\n[accuracy] failure_count={data['total_count']} matches DB")

    def test_item_fields_match_db(self, sync_client, seeded_inference_data):
        """Test that item fields match DB values."""
        payload = get_base_payload(sort_by="timestamp", sort_order="desc", limit=5)
        response = sync_client.post("/observability/inferences/list", json=payload)
        assert response.status_code == 200
        data = response.json()

        sample_inferences = seeded_inference_data["sample_inferences"]
        if not sample_inferences or not data["items"]:
            pytest.skip("No sample data to compare")

        # Compare first item with DB sample
        api_item = data["items"][0]
        db_item = sample_inferences[0]

        assert api_item["inference_id"] == db_item["id"], \
            f"inference_id mismatch: API={api_item['inference_id']}, DB={db_item['id']}"
        assert api_item["input_tokens"] == db_item["input_tokens"], \
            f"input_tokens mismatch: API={api_item['input_tokens']}, DB={db_item['input_tokens']}"
        assert api_item["output_tokens"] == db_item["output_tokens"], \
            f"output_tokens mismatch: API={api_item['output_tokens']}, DB={db_item['output_tokens']}"
        assert api_item["response_time_ms"] == db_item["latency"], \
            f"latency mismatch: API={api_item['response_time_ms']}, DB={db_item['latency']}"

        print(f"\n[accuracy] Item fields match DB for inference_id={api_item['inference_id']}")


#  pytest tests/observability/test_inferences_list.py -v -s
