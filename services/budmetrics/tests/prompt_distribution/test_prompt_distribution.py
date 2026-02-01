"""Tests for POST /observability/metrics/distribution endpoint.

These tests validate the prompt distribution API by:
1. Testing all request body parameters (from_date, to_date, filters, bucket_by, metric, buckets)
2. Verifying response structure matches expected schema
3. Comparing values against InferenceFact ground truth

Run with: pytest tests/prompt_distribution/test_prompt_distribution.py -v -s
"""

import asyncio
from datetime import datetime, timedelta
from uuid import UUID

import pytest

from budmetrics.observability.models import ClickHouseClient, ClickHouseConfig


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# Test constants - match IDs used in generate_test_data.py
TEST_PROJECT_ID = UUID("119787c1-3de1-7b50-969b-e0a58514b6a4")
TEST_ENDPOINT_ID = UUID("119787c1-3de1-7b50-969b-e0a58514b6a2")
TEST_PROMPT_ID = "119787c1-3de1-7b50-969b-e0a58514b6a1"
TEST_PROMPT_ID_2 = "219787c1-3de1-7b50-969b-e0a58514b6a1"

# Time range for test data - covers all generated scenarios
TEST_FROM_DATE = datetime(2026, 1, 31, 10, 35, 0)
TEST_TO_DATE = datetime(2026, 1, 31, 10, 37, 0)

# API endpoint
ENDPOINT = "/observability/metrics/distribution"


async def _fetch_prompt_distribution_ground_truth():
    """Async helper to query ClickHouse for ground truth prompt distribution data."""
    config = ClickHouseConfig()
    client = ClickHouseClient(config)
    await client.initialize()

    try:
        ground_truth = {}
        date_filter = (
            f"request_arrival_time >= '{TEST_FROM_DATE}' AND "
            f"request_arrival_time < '{TEST_TO_DATE}' AND "
            f"prompt_id IS NOT NULL AND prompt_id != ''"
        )

        # Total prompt analytics records
        result = await client.execute_query(f"""
            SELECT COUNT(*) FROM InferenceFact WHERE {date_filter}
        """)
        ground_truth["total_count"] = result[0][0] if result else 0

        # Concurrency distribution (count of requests per second)
        result = await client.execute_query(f"""
            WITH request_counts AS (
                SELECT
                    toStartOfSecond(request_arrival_time) as second_bucket,
                    count(*) as concurrent_count
                FROM InferenceFact
                WHERE {date_filter}
                GROUP BY second_bucket
            )
            SELECT concurrent_count, count(*) as num_seconds
            FROM request_counts
            GROUP BY concurrent_count
            ORDER BY concurrent_count
        """)
        ground_truth["concurrency_distribution"] = [
            {"concurrency": r[0], "num_seconds": r[1]}
            for r in result
        ]

        # Token ranges
        result = await client.execute_query(f"""
            SELECT
                min(input_tokens) as min_input,
                max(input_tokens) as max_input,
                min(output_tokens) as min_output,
                max(output_tokens) as max_output,
                avg(input_tokens) as avg_input,
                avg(output_tokens) as avg_output
            FROM InferenceFact
            WHERE {date_filter}
        """)
        if result:
            ground_truth["token_stats"] = {
                "min_input": result[0][0],
                "max_input": result[0][1],
                "min_output": result[0][2],
                "max_output": result[0][3],
                "avg_input": result[0][4],
                "avg_output": result[0][5],
            }

        # Metric averages
        result = await client.execute_query(f"""
            SELECT
                avg(COALESCE(total_duration_ms, 0)) as avg_total_duration,
                avg(NULLIF(ttft_ms, 0)) as avg_ttft,
                avg(COALESCE(response_time_ms, 0)) as avg_response_time
            FROM InferenceFact
            WHERE {date_filter}
        """)
        if result:
            ground_truth["metric_averages"] = {
                "total_duration_ms": result[0][0],
                "ttft_ms": result[0][1],
                "response_time_ms": result[0][2],
            }

        # By prompt_id counts
        result = await client.execute_query(f"""
            SELECT prompt_id, count(*) as count
            FROM InferenceFact
            WHERE {date_filter}
            GROUP BY prompt_id
            ORDER BY count DESC
        """)
        ground_truth["by_prompt_id"] = {
            r[0]: r[1] for r in result
        }

        # By project_id counts
        result = await client.execute_query(f"""
            SELECT toString(project_id), count(*) as count
            FROM InferenceFact
            WHERE {date_filter}
            GROUP BY project_id
        """)
        ground_truth["by_project_id"] = {
            r[0]: r[1] for r in result
        }

        return ground_truth
    finally:
        await client.close()


@pytest.fixture(scope="session")
def prompt_ground_truth(seeded_db):
    """Fetch ground truth from InferenceFact (seeding done by shared fixture)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch_prompt_distribution_ground_truth())
    finally:
        loop.close()


def get_base_payload(**kwargs) -> dict:
    """Build POST request payload with required fields."""
    payload = {
        "from_date": TEST_FROM_DATE.isoformat(),
        "bucket_by": "concurrency",
        "metric": "total_duration_ms",
    }
    payload.update(kwargs)
    return payload


@pytest.mark.usefixtures("seeded_db")
class TestBasicRequests:
    """Basic request tests for POST /observability/metrics/distribution."""

    def test_minimal_request(self, sync_client):
        """Test minimal request with required fields only."""
        payload = get_base_payload()
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "buckets" in data
        assert isinstance(data["buckets"], list)
        print(f"\n[minimal] Got {len(data['buckets'])} buckets")

    def test_request_with_date_range(self, sync_client):
        """Test request with from_date and to_date."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "buckets" in data
        print(f"\n[date_range] Got {len(data['buckets'])} buckets")

    def test_response_structure(self, sync_client):
        """Test that response has all expected fields."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Check top-level structure
        assert "object" in data
        assert "buckets" in data
        assert "total_count" in data
        assert "bucket_by" in data
        assert "metric" in data
        assert "date_range" in data
        assert "bucket_definitions" in data
        assert isinstance(data["buckets"], list)
        assert isinstance(data["date_range"], dict)
        assert isinstance(data["bucket_definitions"], list)
        print("\n[response_structure] All expected fields present")

    def test_response_object_type(self, sync_client):
        """Test that response object type is prompt_distribution."""
        payload = get_base_payload()
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "prompt_distribution"
        print("\n[response_object_type] Object type is prompt_distribution")

    def test_bucket_structure(self, sync_client):
        """Test that bucket items have expected fields."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        if data["buckets"]:
            bucket = data["buckets"][0]
            expected_fields = ["range", "bucket_start", "bucket_end", "count", "avg_value"]
            for field in expected_fields:
                assert field in bucket, f"Missing field: {field}"
        print("\n[bucket_structure] Bucket fields validated")

    def test_all_bucket_by_options(self, sync_client):
        """Test all valid bucket_by options."""
        bucket_by_options = ["concurrency", "input_tokens", "output_tokens"]

        for bucket_by in bucket_by_options:
            payload = get_base_payload(
                to_date=TEST_TO_DATE.isoformat(),
                bucket_by=bucket_by
            )
            response = sync_client.post(ENDPOINT, json=payload)
            assert response.status_code == 200, f"Failed for bucket_by={bucket_by}"
            data = response.json()
            assert data["bucket_by"] == bucket_by
        print(f"\n[all_bucket_by] All {len(bucket_by_options)} bucket_by options work")

    def test_all_metric_options(self, sync_client):
        """Test all valid metric options."""
        metric_options = ["total_duration_ms", "ttft_ms", "response_time_ms", "throughput_per_user"]

        for metric in metric_options:
            payload = get_base_payload(
                to_date=TEST_TO_DATE.isoformat(),
                metric=metric
            )
            response = sync_client.post(ENDPOINT, json=payload)
            assert response.status_code == 200, f"Failed for metric={metric}"
            data = response.json()
            assert data["metric"] == metric
        print(f"\n[all_metrics] All {len(metric_options)} metric options work")


class TestBucketByDimensions:
    """Test different bucket_by dimensions."""

    def test_bucket_by_concurrency(self, sync_client, prompt_ground_truth):
        """Test bucket_by=concurrency returns concurrency-based buckets."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            bucket_by="concurrency"
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify bucket_by is concurrency
        assert data["bucket_by"] == "concurrency"

        # Verify total count matches ground truth
        expected_total = prompt_ground_truth["total_count"]
        assert data["total_count"] == expected_total, \
            f"Total mismatch: API={data['total_count']}, DB={expected_total}"
        print(f"\n[bucket_by_concurrency] Total={data['total_count']}, buckets={len(data['buckets'])}")

    def test_bucket_by_input_tokens(self, sync_client, prompt_ground_truth):
        """Test bucket_by=input_tokens returns token-based buckets."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            bucket_by="input_tokens"
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["bucket_by"] == "input_tokens"
        assert data["total_count"] == prompt_ground_truth["total_count"]

        # Sum of bucket counts should equal total
        total_from_buckets = sum(b["count"] for b in data["buckets"])
        assert total_from_buckets == data["total_count"], \
            f"Bucket sum {total_from_buckets} != total {data['total_count']}"
        print(f"\n[bucket_by_input_tokens] Total={data['total_count']}, buckets={len(data['buckets'])}")

    def test_bucket_by_output_tokens(self, sync_client, prompt_ground_truth):
        """Test bucket_by=output_tokens returns token-based buckets."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            bucket_by="output_tokens"
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["bucket_by"] == "output_tokens"
        assert data["total_count"] == prompt_ground_truth["total_count"]

        # Sum of bucket counts should equal total
        total_from_buckets = sum(b["count"] for b in data["buckets"])
        assert total_from_buckets == data["total_count"]
        print(f"\n[bucket_by_output_tokens] Total={data['total_count']}, buckets={len(data['buckets'])}")


class TestMetrics:
    """Test different metric calculations."""

    def test_metric_total_duration_ms(self, sync_client, prompt_ground_truth):
        """Test metric=total_duration_ms returns duration averages."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            metric="total_duration_ms"
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["metric"] == "total_duration_ms"

        # Verify avg_value exists and is reasonable
        for bucket in data["buckets"]:
            if bucket["count"] > 0:
                assert bucket["avg_value"] >= 0, f"avg_value should be >= 0"
        print(f"\n[metric_total_duration] Verified avg_value for {len(data['buckets'])} buckets")

    def test_metric_ttft_ms(self, sync_client, prompt_ground_truth):
        """Test metric=ttft_ms returns TTFT averages."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            metric="ttft_ms"
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["metric"] == "ttft_ms"
        print(f"\n[metric_ttft] Got {len(data['buckets'])} buckets")

    def test_metric_response_time_ms(self, sync_client, prompt_ground_truth):
        """Test metric=response_time_ms returns response time averages."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            metric="response_time_ms"
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["metric"] == "response_time_ms"
        print(f"\n[metric_response_time] Got {len(data['buckets'])} buckets")

    def test_metric_throughput_per_user(self, sync_client, prompt_ground_truth):
        """Test metric=throughput_per_user returns throughput values."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            metric="throughput_per_user"
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["metric"] == "throughput_per_user"
        print(f"\n[metric_throughput] Got {len(data['buckets'])} buckets")


class TestFilters:
    """Test filter combinations."""

    def test_filter_project_id(self, sync_client, prompt_ground_truth):
        """Test filtering by project_id."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={"project_id": [str(TEST_PROJECT_ID)]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Filtered count should match DB count for this project
        expected = prompt_ground_truth["by_project_id"].get(str(TEST_PROJECT_ID), 0)
        assert data["total_count"] == expected, \
            f"Total mismatch: API={data['total_count']}, DB={expected}"
        print(f"\n[filter_project_id] Total={data['total_count']}")

    def test_filter_endpoint_id(self, sync_client, prompt_ground_truth):
        """Test filtering by endpoint_id."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={"endpoint_id": [str(TEST_ENDPOINT_ID)]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()
        # Should return results (endpoint_id matches test data)
        print(f"\n[filter_endpoint_id] Total={data['total_count']}")

    def test_filter_prompt_id(self, sync_client, prompt_ground_truth):
        """Test filtering by prompt_id."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={"prompt_id": [TEST_PROMPT_ID]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        expected = prompt_ground_truth["by_prompt_id"].get(TEST_PROMPT_ID, 0)
        assert data["total_count"] == expected, \
            f"Total mismatch: API={data['total_count']}, DB={expected}"
        print(f"\n[filter_prompt_id] Total={data['total_count']}")

    def test_filter_prompt_id_second(self, sync_client, prompt_ground_truth):
        """Test filtering by second prompt_id."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={"prompt_id": [TEST_PROMPT_ID_2]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        expected = prompt_ground_truth["by_prompt_id"].get(TEST_PROMPT_ID_2, 0)
        assert data["total_count"] == expected, \
            f"Total mismatch: API={data['total_count']}, DB={expected}"
        print(f"\n[filter_prompt_id_2] Total={data['total_count']}")

    def test_filter_combined(self, sync_client, prompt_ground_truth):
        """Test combining project_id and prompt_id filters."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={
                "project_id": [str(TEST_PROJECT_ID)],
                "prompt_id": [TEST_PROMPT_ID]
            }
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Combined filter should return subset
        max_possible = prompt_ground_truth["by_prompt_id"].get(TEST_PROMPT_ID, 0)
        assert data["total_count"] <= max_possible
        print(f"\n[filter_combined] Total={data['total_count']}")

    def test_filter_nonexistent_project(self, sync_client):
        """Test filtering by non-existent project returns empty."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={"project_id": ["00000000-0000-0000-0000-000000000000"]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 0
        print("\n[filter_nonexistent] Correctly returned 0")


class TestCustomBuckets:
    """Test custom bucket definitions."""

    def test_custom_buckets_concurrency(self, sync_client, prompt_ground_truth):
        """Test custom bucket definitions for concurrency."""
        custom_buckets = [
            {"min": 1, "max": 2, "label": "Low (1)"},
            {"min": 2, "max": 4, "label": "Medium (2-3)"},
            {"min": 4, "max": 100, "label": "High (4+)"},
        ]
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            bucket_by="concurrency",
            buckets=custom_buckets
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify bucket_definitions matches input
        assert len(data["bucket_definitions"]) == len(custom_buckets)

        # Sum of bucket counts should equal total
        total_from_buckets = sum(b["count"] for b in data["buckets"])
        assert total_from_buckets == data["total_count"]
        print(f"\n[custom_buckets_concurrency] {len(data['buckets'])} buckets, total={data['total_count']}")

    def test_custom_buckets_tokens(self, sync_client, prompt_ground_truth):
        """Test custom bucket definitions for input_tokens."""
        custom_buckets = [
            {"min": 0, "max": 500, "label": "Small (<500)"},
            {"min": 500, "max": 2000, "label": "Medium (500-2000)"},
            {"min": 2000, "max": 100000, "label": "Large (2000+)"},
        ]
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            bucket_by="input_tokens",
            buckets=custom_buckets
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify total matches
        assert data["total_count"] == prompt_ground_truth["total_count"]
        print(f"\n[custom_buckets_tokens] {len(data['buckets'])} buckets")

    def test_auto_bucket_generation(self, sync_client, prompt_ground_truth):
        """Test that buckets are auto-generated when not provided."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            bucket_by="input_tokens"
            # No buckets parameter - should auto-generate
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Should have generated bucket_definitions
        assert "bucket_definitions" in data
        assert len(data["bucket_definitions"]) > 0
        print(f"\n[auto_buckets] Auto-generated {len(data['bucket_definitions'])} bucket definitions")


class TestValidation:
    """Test input validation."""

    def test_missing_bucket_by_rejected(self, sync_client):
        """Test that missing bucket_by returns 422."""
        payload = {
            "from_date": TEST_FROM_DATE.isoformat(),
            "metric": "total_duration_ms"
        }
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422
        print("\n[validation] Missing bucket_by correctly rejected")

    def test_missing_metric_rejected(self, sync_client):
        """Test that missing metric returns 422."""
        payload = {
            "from_date": TEST_FROM_DATE.isoformat(),
            "bucket_by": "concurrency"
        }
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422
        print("\n[validation] Missing metric correctly rejected")

    def test_invalid_bucket_by_rejected(self, sync_client):
        """Test that invalid bucket_by value returns 422."""
        payload = get_base_payload(bucket_by="invalid_dimension")
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422
        print("\n[validation] Invalid bucket_by correctly rejected")

    def test_invalid_metric_rejected(self, sync_client):
        """Test that invalid metric value returns 422."""
        payload = get_base_payload(metric="invalid_metric")
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422
        print("\n[validation] Invalid metric correctly rejected")

    def test_missing_from_date_rejected(self, sync_client):
        """Test that missing from_date returns 422."""
        payload = {"bucket_by": "concurrency", "metric": "total_duration_ms"}
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422
        print("\n[validation] Missing from_date correctly rejected")

    def test_invalid_date_format_rejected(self, sync_client):
        """Test that invalid date format returns 422."""
        payload = {
            "from_date": "invalid-date",
            "bucket_by": "concurrency",
            "metric": "total_duration_ms"
        }
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422
        print("\n[validation] Invalid date format correctly rejected")

    def test_date_range_exceeds_90_days(self, sync_client):
        """Test that date range exceeding 90 days returns 422."""
        from_date = TEST_FROM_DATE
        to_date = from_date + timedelta(days=100)
        payload = get_base_payload(
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat()
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422
        print("\n[validation] Date range > 90 days correctly rejected")

    def test_invalid_bucket_missing_min(self, sync_client):
        """Test that bucket without min returns 422."""
        payload = get_base_payload(buckets=[{"max": 100, "label": "Test"}])
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422
        print("\n[validation] Bucket missing min correctly rejected")

    def test_invalid_bucket_missing_label(self, sync_client):
        """Test that bucket without label returns 422."""
        payload = get_base_payload(buckets=[{"min": 0, "max": 100}])
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422
        print("\n[validation] Bucket missing label correctly rejected")


class TestDataAccuracy:
    """Test accuracy against ground truth."""

    def test_total_count_matches_db(self, sync_client, prompt_ground_truth):
        """Test that total_count matches DB COUNT(*)."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        expected = prompt_ground_truth["total_count"]
        assert data["total_count"] == expected, \
            f"Total mismatch: API={data['total_count']}, DB={expected}"
        print(f"\n[accuracy] total_count={data['total_count']} matches DB")

    def test_bucket_counts_sum_to_total_input_tokens(self, sync_client, prompt_ground_truth):
        """Test that sum of bucket counts equals total_count for input_tokens bucketing.

        Note: For concurrency bucketing, auto-generated buckets may have decimal boundaries
        that don't align with integer concurrency values, so we test with input_tokens.
        """
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            bucket_by="input_tokens"
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        total_from_buckets = sum(b["count"] for b in data["buckets"])
        assert total_from_buckets == data["total_count"], \
            f"Bucket sum {total_from_buckets} != total {data['total_count']}"
        print(f"\n[accuracy] Bucket sum matches total: {total_from_buckets}")

    def test_filtered_counts_match_db(self, sync_client, prompt_ground_truth):
        """Test that filtered results match ground truth."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={"prompt_id": [TEST_PROMPT_ID]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        expected = prompt_ground_truth["by_prompt_id"].get(TEST_PROMPT_ID, 0)
        assert data["total_count"] == expected, \
            f"Filtered total mismatch: API={data['total_count']}, DB={expected}"
        print(f"\n[accuracy] Filtered count matches DB: {data['total_count']}")

    def test_avg_values_are_positive(self, sync_client, prompt_ground_truth):
        """Test that avg_value in buckets are positive when count > 0."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            metric="total_duration_ms"
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        for bucket in data["buckets"]:
            if bucket["count"] > 0:
                assert bucket["avg_value"] >= 0, \
                    f"Bucket {bucket['range']} has negative avg_value: {bucket['avg_value']}"
        print("\n[accuracy] All avg_values are non-negative")

    def test_bucket_ranges_are_ordered(self, sync_client, prompt_ground_truth):
        """Test that bucket_start values are in ascending order."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        bucket_starts = [b["bucket_start"] for b in data["buckets"]]
        assert bucket_starts == sorted(bucket_starts), \
            "Buckets are not in ascending order"
        print(f"\n[accuracy] {len(data['buckets'])} buckets in correct order")

    def test_concurrency_bucket_sum_equals_total(self, sync_client, prompt_ground_truth):
        """Verify bucket counts sum exactly to total_count for concurrency.

        Regression test for duplicate bucket counting bug caused by floating-point
        bucket boundaries producing duplicate labels when formatted with .0f.
        """
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            bucket_by="concurrency",
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        bucket_sum = sum(b["count"] for b in data["buckets"])
        assert bucket_sum == data["total_count"], \
            f"Bucket sum {bucket_sum} != total {data['total_count']}"
        print(f"\n[accuracy] Concurrency bucket sum {bucket_sum} == total {data['total_count']}")

    def test_ttft_bucket_sum_equals_total(self, sync_client, prompt_ground_truth):
        """Verify bucket counts sum exactly to total_count for ttft_ms metric.

        Regression test for NULL ttft_ms values being excluded from bucket counts
        but included in total_count.
        """
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            bucket_by="concurrency",
            metric="ttft_ms",
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        bucket_sum = sum(b["count"] for b in data["buckets"])
        assert bucket_sum == data["total_count"], \
            f"TTFT bucket sum {bucket_sum} != total {data['total_count']}"
        print(f"\n[accuracy] TTFT bucket sum {bucket_sum} == total {data['total_count']}")


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_date_range(self, sync_client):
        """Test that empty date range returns zero total."""
        payload = get_base_payload(
            from_date="2020-01-01T00:00:00",
            to_date="2020-01-02T00:00:00"
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 0
        print("\n[edge_case] Empty date range returns 0")

    def test_single_second_range(self, sync_client, prompt_ground_truth):
        """Test querying a single second range."""
        # Use a time where we know there's high concurrency data
        single_second = datetime(2026, 1, 31, 10, 36, 10)
        payload = get_base_payload(
            from_date=single_second.isoformat(),
            to_date=(single_second + timedelta(seconds=1)).isoformat()
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()
        # Should return the high concurrency burst data
        print(f"\n[edge_case] Single second returned {data['total_count']} records")

    def test_null_ttft_handling(self, sync_client):
        """Test that NULL/zero TTFT is handled gracefully."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            metric="ttft_ms"
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()
        # Should return valid response structure
        assert "buckets" in data
        print("\n[edge_case] NULL TTFT handling works")

    def test_very_wide_bucket_range(self, sync_client, prompt_ground_truth):
        """Test single bucket containing all data."""
        custom_buckets = [
            {"min": 0, "max": 1000000, "label": "All"}
        ]
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            bucket_by="input_tokens",
            buckets=custom_buckets
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # All data should be in the single bucket
        if data["buckets"]:
            all_bucket = data["buckets"][0]
            assert all_bucket["count"] == data["total_count"]
        print(f"\n[edge_case] Wide bucket contains all {data['total_count']} records")

    def test_zero_response_time_handling(self, sync_client):
        """Test that zero response_time is handled (throughput calculation)."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            metric="throughput_per_user"
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()
        # Should not crash on zero division
        assert "buckets" in data
        print("\n[edge_case] Zero response_time handling works")


# Run: pytest tests/prompt_distribution/test_prompt_distribution.py -v -s
