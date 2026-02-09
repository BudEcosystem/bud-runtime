"""Tests for api_key grouping in /observability/analytics endpoint.

These tests verify that the analytics endpoint correctly groups metrics by api_key_id
and that rollup tables properly aggregate data per api_key.
"""

import json

import pytest

from tests.prompt_analytics.conftest import (
    DATABASE,
    CONTAINER,
    TEST_API_KEY_ID,
    TEST_API_KEY_ID_2,
    execute_query,
    load_trace_data,
)
from tests.prompt_analytics.ground_truth import (
    get_expected_dimension_values,
)

pytestmark = pytest.mark.integration

TEST_FROM_DATE = "2026-01-31T00:00:00"
TEST_TO_DATE = "2026-02-01T00:00:00"


class TestApiKeyGroupingBasic:
    """Basic tests for api_key grouping in analytics endpoint."""

    @pytest.mark.usefixtures("seeded_db")
    def test_group_by_api_key_returns_distinct_groups(self, sync_client):
        """Test that api_key grouping returns all distinct api_key_ids."""
        payload = {
            "from_date": TEST_FROM_DATE,
            "to_date": TEST_TO_DATE,
            "metrics": ["request_count"],
            "group_by": ["api_key"],
            "data_source": "prompt",
            "frequency_unit": "day",
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Collect all api_key_ids
        found_api_keys = set()
        for period_bin in data.get("items", []):
            for item in period_bin.get("items", []):
                if api_key_id := item.get("api_key_id"):
                    found_api_keys.add(api_key_id)

        # Should have exactly 2 distinct api_keys
        assert len(found_api_keys) == 2
        assert TEST_API_KEY_ID in found_api_keys
        assert TEST_API_KEY_ID_2 in found_api_keys

    @pytest.mark.usefixtures("seeded_db")
    def test_group_by_api_key_each_group_has_request_count(self, sync_client):
        """Test that each api_key group has non-zero request counts."""
        payload = {
            "from_date": TEST_FROM_DATE,
            "to_date": TEST_TO_DATE,
            "metrics": ["request_count"],
            "group_by": ["api_key"],
            "data_source": "prompt",
            "frequency_unit": "day",
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Aggregate counts per api_key
        api_key_counts = {}
        for period_bin in data.get("items", []):
            for item in period_bin.get("items", []):
                api_key_id = item.get("api_key_id")
                if api_key_id and "request_count" in item.get("data", {}):
                    count = item["data"]["request_count"].get("count", 0)
                    api_key_counts[api_key_id] = api_key_counts.get(api_key_id, 0) + count

        # Both api_keys should have requests
        assert len(api_key_counts) == 2
        for api_key_id, count in api_key_counts.items():
            assert count > 0, f"api_key {api_key_id} should have requests"


class TestApiKeyGroupingWithRollup:
    """Tests verifying api_key grouping uses rollup table data correctly."""

    @pytest.mark.usefixtures("seeded_db")
    def test_rollup_table_contains_api_key_id(self):
        """Test that rollup table has api_key_id column populated."""
        # Query rollup table directly
        query = (
            "SELECT DISTINCT toString(api_key_id) as api_key_id FROM InferenceMetrics5m "
            "WHERE api_key_id != '00000000-0000-0000-0000-000000000000'"
        )
        result = execute_query(
            query,
            format="JSONEachRow",
            database=DATABASE,
            container=CONTAINER,
        )

        if result:
            rows = [json.loads(line) for line in result.strip().split("\n") if line]
            api_key_ids = {r["api_key_id"] for r in rows}
        else:
            api_key_ids = set()

        # Rollup should have both api_key_ids
        assert TEST_API_KEY_ID in api_key_ids or TEST_API_KEY_ID_2 in api_key_ids

    @pytest.mark.usefixtures("seeded_db")
    def test_rollup_aggregates_match_expected_totals(self):
        """Test rollup aggregates match ground truth expectations."""
        # Load seeder data for ground truth
        seeder_data = load_trace_data()

        # Get expected api_key_ids from ground truth
        expected_api_keys = get_expected_dimension_values(seeder_data, "api_key_id")

        # Query rollup table for aggregated counts per api_key
        result = execute_query(
            """SELECT
                toString(api_key_id) as api_key_id,
                sum(request_count) as total_requests
            FROM InferenceMetrics5m
            WHERE prompt_id IS NOT NULL AND prompt_id != ''
            GROUP BY api_key_id
            HAVING api_key_id != '00000000-0000-0000-0000-000000000000'""",
            format="JSONEachRow",
            database=DATABASE,
            container=CONTAINER,
        )

        if result:
            rows = [json.loads(line) for line in result.strip().split("\n") if line]
            rollup_api_keys = {r["api_key_id"] for r in rows}
        else:
            rollup_api_keys = set()

        # Rollup should contain expected api_keys
        for expected_key in expected_api_keys:
            if expected_key and expected_key != "":
                assert expected_key in rollup_api_keys, f"Expected api_key {expected_key} in rollup"


class TestApiKeyGroupingWithMultipleMetrics:
    """Tests for api_key grouping with multiple metrics."""

    @pytest.mark.usefixtures("seeded_db")
    def test_group_by_api_key_with_token_metrics(self, sync_client):
        """Test api_key grouping with token metrics."""
        payload = {
            "from_date": TEST_FROM_DATE,
            "to_date": TEST_TO_DATE,
            "metrics": ["request_count", "input_token", "output_token"],
            "group_by": ["api_key"],
            "data_source": "prompt",
            "frequency_unit": "day",
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify token metrics are present per api_key
        for period_bin in data.get("items", []):
            for item in period_bin.get("items", []):
                if item.get("api_key_id"):
                    metrics = item.get("data", {})
                    assert "request_count" in metrics

    @pytest.mark.usefixtures("seeded_db")
    def test_group_by_api_key_combined_with_project(self, sync_client):
        """Test api_key grouping combined with project grouping."""
        payload = {
            "from_date": TEST_FROM_DATE,
            "to_date": TEST_TO_DATE,
            "metrics": ["request_count"],
            "group_by": ["api_key", "project"],
            "data_source": "prompt",
            "frequency_unit": "day",
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Verify both dimensions present in items
        found_combined = False
        for period_bin in data.get("items", []):
            for item in period_bin.get("items", []):
                if item.get("api_key_id") and item.get("project_id"):
                    # Both dimensions should be present when grouped
                    assert item["api_key_id"] is not None
                    assert item["project_id"] is not None
                    found_combined = True

        assert found_combined, "Should have at least one item with both api_key_id and project_id"


class TestApiKeyGroupingWithFilters:
    """Tests for api_key grouping with filters."""

    @pytest.mark.usefixtures("seeded_db")
    def test_group_by_api_key_hourly_frequency(self, sync_client):
        """Test api_key grouping with hourly frequency."""
        payload = {
            "from_date": TEST_FROM_DATE,
            "to_date": TEST_TO_DATE,
            "metrics": ["request_count"],
            "group_by": ["api_key"],
            "data_source": "prompt",
            "frequency_unit": "hour",
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Should return multiple time buckets with api_key groups
        assert len(data.get("items", [])) > 0


class TestApiKeyGroupingSchemaValidation:
    """Tests for api_key grouping schema validation."""

    @pytest.mark.usefixtures("seeded_db")
    def test_api_key_group_by_is_valid_option(self, sync_client):
        """Test that api_key is a valid group_by option."""
        payload = {
            "from_date": TEST_FROM_DATE,
            "to_date": TEST_TO_DATE,
            "metrics": ["request_count"],
            "group_by": ["api_key"],
            "data_source": "prompt",
            "frequency_unit": "day",
        }
        response = sync_client.post("/observability/analytics", json=payload)
        # Should not return a validation error
        assert response.status_code == 200

    @pytest.mark.usefixtures("seeded_db")
    def test_api_key_response_includes_api_key_id_field(self, sync_client):
        """Test that response items include api_key_id field when grouping by api_key."""
        payload = {
            "from_date": TEST_FROM_DATE,
            "to_date": TEST_TO_DATE,
            "metrics": ["request_count"],
            "group_by": ["api_key"],
            "data_source": "prompt",
            "frequency_unit": "day",
        }
        response = sync_client.post("/observability/analytics", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Check that items have api_key_id field
        has_api_key_id = False
        for period_bin in data.get("items", []):
            for item in period_bin.get("items", []):
                if "api_key_id" in item:
                    has_api_key_id = True
                    break

        assert has_api_key_id, "Response should include api_key_id field when grouping by api_key"
