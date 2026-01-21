"""Tests for POST /observability/metrics/latency-distribution endpoint.

These tests validate the latency distribution API by:
1. Testing all request body parameters (from_date, to_date, filters, group_by, buckets)
2. Verifying response structure matches expected schema
3. Comparing values against InferenceFact ground truth

Run with: pytest tests/observability/latency/test_latency_distribution.py -v -s
"""

import asyncio
from datetime import datetime, timedelta
from uuid import UUID

import pytest

from budmetrics.observability.models import ClickHouseClient, ClickHouseConfig


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# Test constants
TEST_PROJECT_ID = UUID("019787c1-3de1-7b50-969b-e0a58514b6a1")  # 5 datasets
TEST_PROJECT_ID_2 = UUID("019787c1-3de1-7b50-969b-e0a58514b6a4")  # 1 dataset (data_3)
TEST_MODEL_ID = UUID("019787c1-3de1-7b50-969b-e0a58514b6a4")
TEST_FROM_DATE = datetime(2026, 1, 7, 0, 0, 0)
TEST_TO_DATE = datetime(2026, 1, 7, 23, 59, 59)

# API endpoint
ENDPOINT = "/observability/metrics/latency-distribution"

# Default bucket definitions
DEFAULT_BUCKETS = [
    {"min": 0, "max": 100, "label": "0-100ms"},
    {"min": 100, "max": 500, "label": "100-500ms"},
    {"min": 500, "max": 1000, "label": "500ms-1s"},
    {"min": 1000, "max": 2000, "label": "1-2s"},
    {"min": 2000, "max": 5000, "label": "2-5s"},
    {"min": 5000, "max": 10000, "label": "5-10s"},
    {"min": 10000, "max": 999999999, "label": ">10s"},
]


async def _fetch_latency_ground_truth():
    """Async helper to query ClickHouse for ground truth latency distribution."""
    config = ClickHouseConfig()
    client = ClickHouseClient(config)
    await client.initialize()

    try:
        ground_truth = {}
        date_filter = f"timestamp >= '{TEST_FROM_DATE}' AND timestamp <= '{TEST_TO_DATE}'"

        # Overall distribution with default buckets
        # Use COALESCE to match API behavior (NULL -> 0)
        result = await client.execute_query(f"""
            SELECT
                CASE
                    WHEN COALESCE(response_time_ms, 0) >= 0 AND COALESCE(response_time_ms, 0) < 100 THEN '0-100ms'
                    WHEN COALESCE(response_time_ms, 0) >= 100 AND COALESCE(response_time_ms, 0) < 500 THEN '100-500ms'
                    WHEN COALESCE(response_time_ms, 0) >= 500 AND COALESCE(response_time_ms, 0) < 1000 THEN '500ms-1s'
                    WHEN COALESCE(response_time_ms, 0) >= 1000 AND COALESCE(response_time_ms, 0) < 2000 THEN '1-2s'
                    WHEN COALESCE(response_time_ms, 0) >= 2000 AND COALESCE(response_time_ms, 0) < 5000 THEN '2-5s'
                    WHEN COALESCE(response_time_ms, 0) >= 5000 AND COALESCE(response_time_ms, 0) < 10000 THEN '5-10s'
                    ELSE '>10s'
                END as bucket,
                COUNT(*) as count,
                AVG(COALESCE(response_time_ms, 0)) as avg_latency
            FROM InferenceFact
            WHERE {date_filter}
            GROUP BY bucket
            ORDER BY
                CASE bucket
                    WHEN '0-100ms' THEN 1
                    WHEN '100-500ms' THEN 2
                    WHEN '500ms-1s' THEN 3
                    WHEN '1-2s' THEN 4
                    WHEN '2-5s' THEN 5
                    WHEN '5-10s' THEN 6
                    ELSE 7
                END
        """)
        ground_truth["overall"] = [
            {
                "bucket": r[0],
                "count": r[1],
                "avg_latency": r[2],
            }
            for r in result
        ]

        # Total requests
        result = await client.execute_query(f"""
            SELECT COUNT(*) FROM InferenceFact WHERE {date_filter}
        """)
        ground_truth["total_requests"] = result[0][0] if result else 0

        # Project-filtered distribution (TEST_PROJECT_ID)
        result = await client.execute_query(f"""
            SELECT
                CASE
                    WHEN response_time_ms >= 0 AND response_time_ms < 100 THEN '0-100ms'
                    WHEN response_time_ms >= 100 AND response_time_ms < 500 THEN '100-500ms'
                    WHEN response_time_ms >= 500 AND response_time_ms < 1000 THEN '500ms-1s'
                    WHEN response_time_ms >= 1000 AND response_time_ms < 2000 THEN '1-2s'
                    WHEN response_time_ms >= 2000 AND response_time_ms < 5000 THEN '2-5s'
                    WHEN response_time_ms >= 5000 AND response_time_ms < 10000 THEN '5-10s'
                    ELSE '>10s'
                END as bucket,
                COUNT(*) as count,
                AVG(response_time_ms) as avg_latency
            FROM InferenceFact
            WHERE {date_filter} AND project_id = '{TEST_PROJECT_ID}'
            GROUP BY bucket
        """)
        ground_truth["by_project_id"] = [
            {"bucket": r[0], "count": r[1], "avg_latency": r[2]}
            for r in result
        ]
        ground_truth["by_project_id_total"] = sum(r[1] for r in result) if result else 0

        # Multiple projects distribution
        result = await client.execute_query(f"""
            SELECT
                CASE
                    WHEN response_time_ms >= 0 AND response_time_ms < 100 THEN '0-100ms'
                    WHEN response_time_ms >= 100 AND response_time_ms < 500 THEN '100-500ms'
                    WHEN response_time_ms >= 500 AND response_time_ms < 1000 THEN '500ms-1s'
                    WHEN response_time_ms >= 1000 AND response_time_ms < 2000 THEN '1-2s'
                    WHEN response_time_ms >= 2000 AND response_time_ms < 5000 THEN '2-5s'
                    WHEN response_time_ms >= 5000 AND response_time_ms < 10000 THEN '5-10s'
                    ELSE '>10s'
                END as bucket,
                COUNT(*) as count,
                AVG(response_time_ms) as avg_latency
            FROM InferenceFact
            WHERE {date_filter} AND project_id IN ('{TEST_PROJECT_ID}', '{TEST_PROJECT_ID_2}')
            GROUP BY bucket
        """)
        ground_truth["by_project_id_multiple"] = [
            {"bucket": r[0], "count": r[1], "avg_latency": r[2]}
            for r in result
        ]
        ground_truth["by_project_id_multiple_total"] = sum(r[1] for r in result) if result else 0

        # Model-filtered distribution
        result = await client.execute_query(f"""
            SELECT
                CASE
                    WHEN response_time_ms >= 0 AND response_time_ms < 100 THEN '0-100ms'
                    WHEN response_time_ms >= 100 AND response_time_ms < 500 THEN '100-500ms'
                    WHEN response_time_ms >= 500 AND response_time_ms < 1000 THEN '500ms-1s'
                    WHEN response_time_ms >= 1000 AND response_time_ms < 2000 THEN '1-2s'
                    WHEN response_time_ms >= 2000 AND response_time_ms < 5000 THEN '2-5s'
                    WHEN response_time_ms >= 5000 AND response_time_ms < 10000 THEN '5-10s'
                    ELSE '>10s'
                END as bucket,
                COUNT(*) as count,
                AVG(response_time_ms) as avg_latency
            FROM InferenceFact
            WHERE {date_filter} AND model_id = '{TEST_MODEL_ID}'
            GROUP BY bucket
        """)
        ground_truth["by_model_id"] = [
            {"bucket": r[0], "count": r[1], "avg_latency": r[2]}
            for r in result
        ]
        ground_truth["by_model_id_total"] = sum(r[1] for r in result) if result else 0

        # API key project ID filtered distribution
        result = await client.execute_query(f"""
            SELECT
                CASE
                    WHEN response_time_ms >= 0 AND response_time_ms < 100 THEN '0-100ms'
                    WHEN response_time_ms >= 100 AND response_time_ms < 500 THEN '100-500ms'
                    WHEN response_time_ms >= 500 AND response_time_ms < 1000 THEN '500ms-1s'
                    WHEN response_time_ms >= 1000 AND response_time_ms < 2000 THEN '1-2s'
                    WHEN response_time_ms >= 2000 AND response_time_ms < 5000 THEN '2-5s'
                    WHEN response_time_ms >= 5000 AND response_time_ms < 10000 THEN '5-10s'
                    ELSE '>10s'
                END as bucket,
                COUNT(*) as count,
                AVG(response_time_ms) as avg_latency
            FROM InferenceFact
            WHERE {date_filter} AND api_key_project_id = '{TEST_PROJECT_ID}'
            GROUP BY bucket
        """)
        ground_truth["by_api_key_project_id"] = [
            {"bucket": r[0], "count": r[1], "avg_latency": r[2]}
            for r in result
        ]
        ground_truth["by_api_key_project_id_total"] = sum(r[1] for r in result) if result else 0

        # Custom bucket: 0-2000ms (Fast) - for TestCustomBuckets
        result = await client.execute_query(f"""
            SELECT COUNT(*), AVG(response_time_ms)
            FROM InferenceFact
            WHERE {date_filter} AND response_time_ms >= 0 AND response_time_ms < 2000
        """)
        ground_truth["custom_fast_bucket"] = {
            "count": result[0][0] if result else 0,
            "avg_latency": result[0][1] if result else 0,
        }

        # Custom bucket: 2000ms+ (Slow)
        result = await client.execute_query(f"""
            SELECT COUNT(*), AVG(response_time_ms)
            FROM InferenceFact
            WHERE {date_filter} AND response_time_ms >= 2000
        """)
        ground_truth["custom_slow_bucket"] = {
            "count": result[0][0] if result else 0,
            "avg_latency": result[0][1] if result else 0,
        }

        # Group by model - get unique models with counts
        result = await client.execute_query(f"""
            SELECT model_id, COUNT(*) as count
            FROM InferenceFact
            WHERE {date_filter}
            GROUP BY model_id
            ORDER BY count DESC
        """)
        ground_truth["models"] = [
            {"model_id": str(r[0]) if r[0] else None, "count": r[1]}
            for r in result
        ]

        # Group by project - get unique projects with counts
        result = await client.execute_query(f"""
            SELECT project_id, COUNT(*) as count
            FROM InferenceFact
            WHERE {date_filter}
            GROUP BY project_id
            ORDER BY count DESC
        """)
        ground_truth["projects"] = [
            {"project_id": str(r[0]) if r[0] else None, "count": r[1]}
            for r in result
        ]

        return ground_truth
    finally:
        await client.close()


@pytest.fixture(scope="session")
def latency_ground_truth(seed_test_data):
    """Fetch ground truth from InferenceFact (seeding done by shared fixture)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch_latency_ground_truth())
    finally:
        loop.close()


def get_base_payload(**kwargs) -> dict:
    """Build POST request payload."""
    payload = {"from_date": TEST_FROM_DATE.isoformat()}
    payload.update(kwargs)
    return payload


@pytest.mark.usefixtures("seed_test_data")
class TestBasicRequests:
    """Basic request tests for POST /observability/metrics/latency-distribution."""

    def test_basic_request_minimal(self, sync_client):
        """Test minimal request with only from_date."""
        payload = get_base_payload()
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "overall_distribution" in data
        assert isinstance(data["overall_distribution"], list)
        print(f"\n[basic_minimal] Got {len(data['overall_distribution'])} buckets")

    def test_basic_request_with_date_range(self, sync_client):
        """Test request with from_date and to_date."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "overall_distribution" in data
        print(f"\n[basic_date_range] Got {len(data['overall_distribution'])} buckets")

    def test_response_structure(self, sync_client):
        """Test that response has all expected fields."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Check top-level structure
        assert "object" in data
        assert "overall_distribution" in data
        assert "total_requests" in data
        assert "date_range" in data
        assert "bucket_definitions" in data
        assert isinstance(data["overall_distribution"], list)
        assert isinstance(data["date_range"], dict)
        assert isinstance(data["bucket_definitions"], list)
        print("\n[response_structure] All expected fields present")

    def test_response_object_type(self, sync_client):
        """Test that response object type is latency_distribution."""
        payload = get_base_payload()
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "latency_distribution"
        print("\n[response_object_type] Object type is latency_distribution")

    def test_bucket_structure(self, sync_client):
        """Test that bucket items have expected fields."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        if data["overall_distribution"]:
            bucket = data["overall_distribution"][0]
            expected_fields = ["range", "count", "percentage", "avg_latency"]
            for field in expected_fields:
                assert field in bucket, f"Missing field: {field}"
        print("\n[bucket_structure] Bucket fields validated")


class TestGroupBy:
    """Group by parameter tests for latency distribution."""

    def test_no_group_by_default(self, sync_client, latency_ground_truth):
        """Test default (no group_by) returns only overall_distribution."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Should have overall_distribution
        assert "overall_distribution" in data
        assert len(data["overall_distribution"]) > 0

        # groups should be empty or not present when no group_by
        groups = data.get("groups", [])
        assert len(groups) == 0 or groups is None or groups == []

        # Verify total matches ground truth
        assert data["total_requests"] == latency_ground_truth["total_requests"], \
            f"Total mismatch: API={data['total_requests']}, DB={latency_ground_truth['total_requests']}"
        print(f"\n[no_group_by] Got {len(data['overall_distribution'])} buckets, total={data['total_requests']}")

    def test_group_by_model(self, sync_client, latency_ground_truth):
        """Test group_by=model returns groups by model."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            group_by=["model"]
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Should have groups
        assert "groups" in data
        groups = data.get("groups", [])

        # Number of groups should match unique models in ground truth
        expected_model_count = len(latency_ground_truth["models"])
        assert len(groups) == expected_model_count, \
            f"Group count mismatch: API={len(groups)}, DB models={expected_model_count}"

        # Each group should have model_id field
        if groups:
            assert "model_id" in groups[0] or groups[0].get("model_id") is not None or "model_name" in groups[0]
        print(f"\n[group_by_model] Got {len(groups)} model groups")

    def test_group_by_project(self, sync_client, latency_ground_truth):
        """Test group_by=project returns groups by project."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            group_by=["project"]
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Should have groups
        groups = data.get("groups", [])

        # Number of groups should match unique projects
        expected_project_count = len(latency_ground_truth["projects"])
        assert len(groups) == expected_project_count, \
            f"Group count mismatch: API={len(groups)}, DB projects={expected_project_count}"
        print(f"\n[group_by_project] Got {len(groups)} project groups")

    def test_group_by_endpoint(self, sync_client, latency_ground_truth):
        """Test group_by=endpoint returns groups by endpoint."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            group_by=["endpoint"]
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Should have groups (may be empty if no endpoint data)
        assert "groups" in data or "overall_distribution" in data
        print(f"\n[group_by_endpoint] Got {len(data.get('groups', []))} endpoint groups")

    def test_group_by_user(self, sync_client, latency_ground_truth):
        """Test group_by=user returns groups by user."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            group_by=["user"]
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Should have groups (may be empty if no user data)
        assert "groups" in data or "overall_distribution" in data
        print(f"\n[group_by_user] Got {len(data.get('groups', []))} user groups")

    def test_group_by_multiple(self, sync_client, latency_ground_truth):
        """Test group_by with multiple dimensions."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            group_by=["model", "project"]
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Should have groups
        groups = data.get("groups", [])
        # Total requests should match ground truth
        assert data["total_requests"] == latency_ground_truth["total_requests"], \
            f"Total mismatch: API={data['total_requests']}, DB={latency_ground_truth['total_requests']}"
        print(f"\n[group_by_multiple] Got {len(groups)} combined groups, total={data['total_requests']}")


class TestFilters:
    """Filter tests for latency distribution - with ground truth comparison."""

    def test_filter_project_id_single(self, sync_client, latency_ground_truth):
        """Test filtering by single project_id and compare with DB ground truth."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={"project_id": [str(TEST_PROJECT_ID)]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Compare total with ground truth
        expected_total = latency_ground_truth["by_project_id_total"]
        assert data["total_requests"] == expected_total, \
            f"Total mismatch: API={data['total_requests']}, DB={expected_total}"

        # Verify sum of bucket counts equals total
        total_from_buckets = sum(b["count"] for b in data["overall_distribution"])
        assert total_from_buckets == data["total_requests"], \
            f"Bucket sum {total_from_buckets} != total {data['total_requests']}"
        print(f"\n[filter_project_id_single] Total={data['total_requests']}, matches DB")

    def test_filter_project_id_multiple(self, sync_client, latency_ground_truth):
        """Test filtering by multiple project_ids and compare with DB ground truth."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={"project_id": [str(TEST_PROJECT_ID), str(TEST_PROJECT_ID_2)]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Compare total with ground truth
        expected_total = latency_ground_truth["by_project_id_multiple_total"]
        assert data["total_requests"] == expected_total, \
            f"Total mismatch: API={data['total_requests']}, DB={expected_total}"
        print(f"\n[filter_project_id_multiple] Total={data['total_requests']}, matches DB")

    def test_filter_model_id(self, sync_client, latency_ground_truth):
        """Test filtering by model_id and compare with DB ground truth."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={"model_id": [str(TEST_MODEL_ID)]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Compare total with ground truth
        expected_total = latency_ground_truth["by_model_id_total"]
        assert data["total_requests"] == expected_total, \
            f"Total mismatch: API={data['total_requests']}, DB={expected_total}"

        # Compare bucket counts
        db_buckets = {b["bucket"]: b for b in latency_ground_truth["by_model_id"]}
        for api_bucket in data["overall_distribution"]:
            bucket_range = api_bucket["range"]
            if bucket_range in db_buckets:
                db_bucket = db_buckets[bucket_range]
                assert api_bucket["count"] == db_bucket["count"], \
                    f"Bucket {bucket_range} count mismatch: API={api_bucket['count']}, DB={db_bucket['count']}"
        print(f"\n[filter_model_id] Total={data['total_requests']}, matches DB")

    def test_filter_endpoint_id(self, sync_client, latency_ground_truth):
        """Test filtering by endpoint_id."""
        # Use a non-existent endpoint to test filter works
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={"endpoint_id": ["00000000-0000-0000-0000-000000000000"]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Non-existent endpoint should return 0 results
        assert data["total_requests"] == 0, \
            f"Expected 0 for non-existent endpoint, got {data['total_requests']}"
        print("\n[filter_endpoint_id] Non-existent endpoint correctly returns 0")

    def test_filter_api_key_project_id(self, sync_client, latency_ground_truth):
        """Test filtering by api_key_project_id and compare with DB ground truth."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={"api_key_project_id": [str(TEST_PROJECT_ID)]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Compare total with ground truth
        expected_total = latency_ground_truth["by_api_key_project_id_total"]
        assert data["total_requests"] == expected_total, \
            f"Total mismatch: API={data['total_requests']}, DB={expected_total}"
        print(f"\n[filter_api_key_project_id] Total={data['total_requests']}, matches DB")

    def test_filter_combined(self, sync_client, latency_ground_truth):
        """Test combining project_id and model_id filters."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={
                "project_id": [str(TEST_PROJECT_ID)],
                "model_id": [str(TEST_MODEL_ID)]
            }
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Combined filter should return subset of both individual filters
        assert data["total_requests"] <= latency_ground_truth["by_project_id_total"]
        assert data["total_requests"] <= latency_ground_truth["by_model_id_total"]
        print(f"\n[filter_combined] Total={data['total_requests']} (intersection)")

    def test_filter_nonexistent(self, sync_client, latency_ground_truth):
        """Test filtering by non-existent project returns empty distribution."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={"project_id": ["00000000-0000-0000-0000-000000000000"]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Should return 0 total
        assert data["total_requests"] == 0, \
            f"Expected 0 for non-existent project, got {data['total_requests']}"
        print("\n[filter_nonexistent] Correctly returned 0 total")


class TestCustomBuckets:
    """Custom bucket tests for latency distribution - with ground truth comparison."""

    def test_custom_buckets_single(self, sync_client, latency_ground_truth):
        """Test single custom bucket and compare with DB ground truth."""
        custom_buckets = [{"min": 0, "max": 10000000, "label": "All"}]
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            buckets=custom_buckets
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Single bucket should contain all requests
        assert data["total_requests"] == latency_ground_truth["total_requests"]
        assert len(data["overall_distribution"]) >= 1

        # Find the "All" bucket
        all_bucket = next((b for b in data["overall_distribution"] if b["range"] == "All"), None)
        if all_bucket:
            assert all_bucket["count"] == latency_ground_truth["total_requests"], \
                f"All bucket count mismatch: API={all_bucket['count']}, DB={latency_ground_truth['total_requests']}"
            assert all_bucket["percentage"] == 100.0 or abs(all_bucket["percentage"] - 100.0) < 0.01
        print(f"\n[custom_buckets_single] All bucket contains {data['total_requests']} requests")

    def test_custom_buckets_multiple(self, sync_client, latency_ground_truth):
        """Test multiple custom buckets and compare with DB ground truth."""
        custom_buckets = [
            {"min": 0, "max": 2000, "label": "Fast"},
            {"min": 2000, "max": 10000000, "label": "Slow"}
        ]
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            buckets=custom_buckets
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Get bucket counts from API
        fast_bucket = next((b for b in data["overall_distribution"] if b["range"] == "Fast"), None)
        slow_bucket = next((b for b in data["overall_distribution"] if b["range"] == "Slow"), None)

        # Sum should equal total
        total_from_buckets = sum(b["count"] for b in data["overall_distribution"])
        assert total_from_buckets == data["total_requests"], \
            f"Bucket sum {total_from_buckets} != total {data['total_requests']}"

        # Verify total matches ground truth
        assert data["total_requests"] == latency_ground_truth["total_requests"], \
            f"Total mismatch: API={data['total_requests']}, DB={latency_ground_truth['total_requests']}"
        print(f"\n[custom_buckets_multiple] Fast={fast_bucket['count'] if fast_bucket else 0}, Slow={slow_bucket['count'] if slow_bucket else 0}, Total={data['total_requests']}")

    def test_custom_buckets_fine_grained(self, sync_client, latency_ground_truth):
        """Test fine-grained custom buckets (100ms increments)."""
        custom_buckets = [
            {"min": 0, "max": 1000, "label": "0-1s"},
            {"min": 1000, "max": 1500, "label": "1-1.5s"},
            {"min": 1500, "max": 2000, "label": "1.5-2s"},
            {"min": 2000, "max": 2500, "label": "2-2.5s"},
            {"min": 2500, "max": 10000000, "label": ">2.5s"}
        ]
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            buckets=custom_buckets
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Sum of all bucket counts should equal total
        total_from_buckets = sum(b["count"] for b in data["overall_distribution"])
        assert total_from_buckets == data["total_requests"], \
            f"Sum {total_from_buckets} != total {data['total_requests']}"
        print(f"\n[custom_buckets_fine_grained] {len(data['overall_distribution'])} buckets, total={data['total_requests']}")

    def test_custom_buckets_coarse(self, sync_client, latency_ground_truth):
        """Test coarse custom buckets (2 large buckets)."""
        custom_buckets = [
            {"min": 0, "max": 5000, "label": "Under 5s"},
            {"min": 5000, "max": 10000000, "label": "Over 5s"}
        ]
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            buckets=custom_buckets
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # All test data is under 5s, so "Over 5s" should be 0
        over_5s = next((b for b in data["overall_distribution"] if b["range"] == "Over 5s"), None)
        if over_5s:
            assert over_5s["count"] == 0, f"Expected 0 for Over 5s, got {over_5s['count']}"

        # "Under 5s" should have all data
        under_5s = next((b for b in data["overall_distribution"] if b["range"] == "Under 5s"), None)
        if under_5s:
            assert under_5s["count"] == latency_ground_truth["total_requests"]
        print(f"\n[custom_buckets_coarse] Under 5s={under_5s['count'] if under_5s else 0}, Over 5s={over_5s['count'] if over_5s else 0}")

    def test_bucket_definitions_in_response(self, sync_client, latency_ground_truth):
        """Test that bucket_definitions in response matches input."""
        custom_buckets = [
            {"min": 0, "max": 1000, "label": "Fast"},
            {"min": 1000, "max": 3000, "label": "Medium"},
            {"min": 3000, "max": 10000000, "label": "Slow"}
        ]
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            buckets=custom_buckets
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # bucket_definitions should match input
        assert "bucket_definitions" in data
        assert len(data["bucket_definitions"]) == len(custom_buckets)

        for i, bucket_def in enumerate(data["bucket_definitions"]):
            assert bucket_def["label"] == custom_buckets[i]["label"], \
                f"Label mismatch at index {i}"
        print("\n[bucket_definitions_in_response] Bucket definitions match input")


class TestValidation:
    """Validation error tests for latency distribution."""

    def test_missing_from_date_rejected(self, sync_client):
        """Test that missing from_date returns 422."""
        payload = {}
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for missing from_date, got {response.status_code}"
        print("\n[validation] Missing from_date correctly rejected")

    def test_invalid_date_format_rejected(self, sync_client):
        """Test that invalid date format returns 422."""
        payload = {"from_date": "invalid-date"}
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for invalid date format, got {response.status_code}"
        print("\n[validation] Invalid date format correctly rejected")

    def test_invalid_group_by_rejected(self, sync_client):
        """Test that invalid group_by value returns 422."""
        payload = get_base_payload(group_by=["invalid_dimension"])
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for invalid group_by, got {response.status_code}"
        print("\n[validation] Invalid group_by correctly rejected")

    def test_invalid_bucket_missing_min(self, sync_client):
        """Test that bucket without min returns 422."""
        payload = get_base_payload(buckets=[{"max": 1000, "label": "Test"}])
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for bucket missing min, got {response.status_code}"
        print("\n[validation] Bucket missing min correctly rejected")

    def test_invalid_bucket_missing_max(self, sync_client):
        """Test that bucket without max returns 422."""
        payload = get_base_payload(buckets=[{"min": 0, "label": "Test"}])
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for bucket missing max, got {response.status_code}"
        print("\n[validation] Bucket missing max correctly rejected")

    def test_invalid_bucket_missing_label(self, sync_client):
        """Test that bucket without label returns 422."""
        payload = get_base_payload(buckets=[{"min": 0, "max": 1000}])
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for bucket missing label, got {response.status_code}"
        print("\n[validation] Bucket missing label correctly rejected")

    def test_date_range_exceeds_90_days(self, sync_client):
        """Test that date range exceeding 90 days returns 422."""
        from_date = TEST_FROM_DATE
        to_date = from_date + timedelta(days=100)
        payload = {
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat()
        }
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for date range > 90 days, got {response.status_code}"
        print("\n[validation] Date range > 90 days correctly rejected")


class TestDataAccuracy:
    """Data accuracy tests comparing API response with DB ground truth."""

    def test_total_requests_matches_db(self, sync_client, latency_ground_truth):
        """Test that total_requests matches DB COUNT(*)."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        expected = latency_ground_truth["total_requests"]
        assert data["total_requests"] == expected, \
            f"Total mismatch: API={data['total_requests']}, DB={expected}"
        print(f"\n[accuracy] total_requests={data['total_requests']} matches DB")

    def test_bucket_counts_match_db(self, sync_client, latency_ground_truth):
        """Test that each bucket count matches DB CASE query."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        db_buckets = {b["bucket"]: b for b in latency_ground_truth["overall"]}
        for api_bucket in data["overall_distribution"]:
            bucket_range = api_bucket["range"]
            if bucket_range in db_buckets and api_bucket["count"] > 0:
                db_bucket = db_buckets[bucket_range]
                assert api_bucket["count"] == db_bucket["count"], \
                    f"Bucket {bucket_range}: API={api_bucket['count']}, DB={db_bucket['count']}"
        print("\n[accuracy] All bucket counts match DB")

    def test_bucket_percentages_sum_to_100(self, sync_client, latency_ground_truth):
        """Test that sum of percentages is approximately 100%."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        if data["total_requests"] > 0:
            total_percentage = sum(b["percentage"] for b in data["overall_distribution"])
            assert 99.0 <= total_percentage <= 101.0, \
                f"Sum of percentages {total_percentage} is not approximately 100%"
        print("\n[accuracy] Bucket percentages sum to ~100%")

    def test_bucket_percentages_match_db(self, sync_client, latency_ground_truth):
        """Test that each bucket percentage matches calculated value."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        total = data["total_requests"]
        if total > 0:
            for api_bucket in data["overall_distribution"]:
                expected_pct = (api_bucket["count"] / total) * 100
                assert abs(api_bucket["percentage"] - expected_pct) < 0.1, \
                    f"Bucket {api_bucket['range']}: API pct={api_bucket['percentage']}, expected={expected_pct}"
        print("\n[accuracy] Bucket percentages match calculated values")

    def test_avg_latency_per_bucket_matches_db(self, sync_client, latency_ground_truth):
        """Test that avg_latency per bucket matches DB AVG()."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        db_buckets = {b["bucket"]: b for b in latency_ground_truth["overall"]}
        for api_bucket in data["overall_distribution"]:
            bucket_range = api_bucket["range"]
            if bucket_range in db_buckets and api_bucket["count"] > 0:
                db_bucket = db_buckets[bucket_range]
                api_avg = api_bucket.get("avg_latency") or 0
                db_avg = db_bucket.get("avg_latency") or 0
                # Allow 1% tolerance for floating point
                if db_avg > 0:
                    assert abs(api_avg - db_avg) / db_avg < 0.01, \
                        f"Bucket {bucket_range} avg: API={api_avg}, DB={db_avg}"
        print("\n[accuracy] avg_latency per bucket matches DB")

    def test_overall_distribution_matches_db(self, sync_client, latency_ground_truth):
        """Test that overall distribution matches ungrouped query."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Count non-empty buckets
        api_non_empty = [b for b in data["overall_distribution"] if b["count"] > 0]
        db_non_empty = latency_ground_truth["overall"]

        assert len(api_non_empty) == len(db_non_empty), \
            f"Non-empty bucket count mismatch: API={len(api_non_empty)}, DB={len(db_non_empty)}"
        print(f"\n[accuracy] Overall distribution has {len(api_non_empty)} non-empty buckets")

    def test_grouped_totals_match_overall(self, sync_client, latency_ground_truth):
        """Test that sum of group totals equals overall total."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            group_by=["project"]
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        groups = data.get("groups", [])
        if groups:
            groups_total = sum(g.get("total_requests", 0) for g in groups)
            assert groups_total == data["total_requests"], \
                f"Groups total {groups_total} != overall {data['total_requests']}"
        print(f"\n[accuracy] Grouped totals sum to overall total")

    def test_filtered_counts_match_db(self, sync_client, latency_ground_truth):
        """Test that filtered results match WHERE clause in DB."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={"project_id": [str(TEST_PROJECT_ID)]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        expected = latency_ground_truth["by_project_id_total"]
        assert data["total_requests"] == expected, \
            f"Filtered total mismatch: API={data['total_requests']}, DB={expected}"
        print(f"\n[accuracy] Filtered count={data['total_requests']} matches DB")

    def test_custom_bucket_counts_match_db(self, sync_client, latency_ground_truth):
        """Test that custom bucket counts sum to total requests."""
        custom_buckets = [
            {"min": 0, "max": 2000, "label": "Fast"},
            {"min": 2000, "max": 10000000, "label": "Slow"}
        ]
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            buckets=custom_buckets
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        fast_bucket = next((b for b in data["overall_distribution"] if b["range"] == "Fast"), None)
        slow_bucket = next((b for b in data["overall_distribution"] if b["range"] == "Slow"), None)

        # Verify sum equals total
        total_from_buckets = sum(b["count"] for b in data["overall_distribution"])
        assert total_from_buckets == data["total_requests"], \
            f"Bucket sum {total_from_buckets} != total {data['total_requests']}"

        # Verify total matches ground truth
        assert data["total_requests"] == latency_ground_truth["total_requests"], \
            f"Total mismatch: API={data['total_requests']}, DB={latency_ground_truth['total_requests']}"
        print(f"\n[accuracy] Custom buckets: Fast={fast_bucket['count'] if fast_bucket else 0}, Slow={slow_bucket['count'] if slow_bucket else 0}")

    def test_empty_buckets_have_zero_count(self, sync_client, latency_ground_truth):
        """Test that buckets with no data have count=0 and percentage=0."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify that buckets with count=0 have percentage=0
        for api_bucket in data["overall_distribution"]:
            if api_bucket["count"] == 0:
                assert api_bucket["percentage"] == 0.0, \
                    f"Bucket {api_bucket['range']} has count=0 but percentage={api_bucket['percentage']}"

        # Verify all bucket counts match ground truth
        db_buckets = {b["bucket"]: b["count"] for b in latency_ground_truth["overall"]}
        for api_bucket in data["overall_distribution"]:
            bucket_range = api_bucket["range"]
            if bucket_range in db_buckets:
                assert api_bucket["count"] == db_buckets[bucket_range], \
                    f"Bucket {bucket_range}: API={api_bucket['count']}, DB={db_buckets[bucket_range]}"
        print("\n[accuracy] All bucket counts verified against DB")


class TestEdgeCases:
    """Edge case tests for latency distribution."""

    def test_empty_date_range(self, sync_client, latency_ground_truth):
        """Test that empty date range returns empty distribution."""
        # Use a date range with no data
        payload = {
            "from_date": "2020-01-01T00:00:00",
            "to_date": "2020-01-02T00:00:00"
        }
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["total_requests"] == 0, \
            f"Expected 0 for empty date range, got {data['total_requests']}"
        print("\n[edge_case] Empty date range returns 0 total")

    def test_all_data_in_one_bucket(self, sync_client, latency_ground_truth):
        """Test single bucket containing all data shows 100%."""
        custom_buckets = [{"min": 0, "max": 10000000, "label": "All"}]
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            buckets=custom_buckets
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        all_bucket = next((b for b in data["overall_distribution"] if b["range"] == "All"), None)
        if all_bucket and data["total_requests"] > 0:
            assert abs(all_bucket["percentage"] - 100.0) < 0.01, \
                f"Expected 100%, got {all_bucket['percentage']}%"
        print("\n[edge_case] Single bucket shows 100%")

    @pytest.mark.usefixtures("seed_test_data")
    def test_null_latency_handling(self, sync_client):
        """Test that NULL response_time_ms is handled gracefully."""
        # This test verifies the API doesn't crash with NULL values
        # The seeded data shouldn't have NULL latencies, so this is more of a smoke test
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Should return valid response structure
        assert "overall_distribution" in data
        assert "total_requests" in data
        print("\n[edge_case] NULL latency handling works")

    def test_very_large_latency(self, sync_client, latency_ground_truth):
        """Test that >10s latency falls in correct bucket."""
        # Test data doesn't have >10s latencies, but we can verify the bucket exists
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Find >10s bucket
        large_bucket = next((b for b in data["overall_distribution"] if b["range"] == ">10s"), None)
        if large_bucket:
            # Should be 0 since test data has no >10s latencies
            assert large_bucket["count"] == 0, \
                f"Expected 0 for >10s bucket, got {large_bucket['count']}"
        print("\n[edge_case] >10s bucket correctly shows 0")


# pytest tests/observability/latency/test_latency_distribution.py -v -s
