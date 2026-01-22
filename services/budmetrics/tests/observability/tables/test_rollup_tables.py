"""Integration tests for rollup tables (InferenceMetrics5m, 1h, 1d).

Tests verify that Materialized Views correctly aggregate InferenceFact
rows into rollup tables with proper counts and sums.

Uses explicit ground truth values derived from data_1, data_4, data_6.

Note: Percentiles are NOT stored in rollup tables - they are computed
from raw data at query time for 100% accuracy.
"""

import json
import subprocess

import pytest

DATABASE = "default_v4"
CONTAINER = "otel-clickhouse"

# =============================================================================
# GROUND TRUTH VALUES
# =============================================================================
# These values represent exactly what the rollup tables SHOULD produce from
# the InferenceFact rows created by data_1, data_4, data_6.
#
# Source data summary:
# - data_1: success, 14 input, 21 output, 2125ms latency, 450ms ttft, cached, no cost
# - data_4: error, no tokens, no latency (NULL values)
# - data_6: success, 24 input, 31 output, 1125ms latency, 250ms ttft, cached, $0.00125

# Project ID shared by all test data
PROJECT_ID = "019787c1-3de1-7b50-969b-e0a58514b6a1"
ENDPOINT_ID = "019787c1-3de1-7b50-969b-e0a58514b6a4"
MODEL_ID = "019787c1-3de1-7b50-969b-e0a58514b6a2"

# Expected aggregated totals across all dimensions
EXPECTED_TOTALS = {
    "request_count": 3,
    "success_count": 2,
    "error_count": 1,
    "cached_count": 2,
    "total_input_tokens": 38,  # 14 + 24
    "total_output_tokens": 52,  # 21 + 31
    "total_cost": 0.00125,
    "sum_response_time_ms": 3250,  # 2125 + 1125
    "sum_ttft_ms": 700,  # 450 + 250
    "unique_inferences": 3,
}

# Expected values by dimension group
EXPECTED_SUCCESS_NO_GEO = {  # data_1: is_success=True, country_code=NULL
    "request_count": 1,
    "success_count": 1,
    "error_count": 0,
    "cached_count": 1,
    "total_input_tokens": 14,
    "total_output_tokens": 21,
    "total_cost": 0,
    "sum_response_time_ms": 2125,
    "sum_ttft_ms": 450,
}

EXPECTED_SUCCESS_US = {  # data_6: is_success=True, country_code='US'
    "request_count": 1,
    "success_count": 1,
    "error_count": 0,
    "cached_count": 1,
    "total_input_tokens": 24,
    "total_output_tokens": 31,
    "total_cost": 0.00125,
    "sum_response_time_ms": 1125,
    "sum_ttft_ms": 250,
}

EXPECTED_ERROR_NO_GEO = {  # data_4: is_success=False, country_code=NULL
    "request_count": 1,
    "success_count": 0,
    "error_count": 1,
    "cached_count": 0,
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "total_cost": 0,
    "sum_response_time_ms": 0,
    "sum_ttft_ms": 0,
}


def execute_query(query: str) -> str:
    """Execute ClickHouse query via docker."""
    cmd = ["docker", "exec", CONTAINER, "clickhouse-client", "--query", query]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Query failed: {result.stderr}")
    return result.stdout.strip()


def query_rollup_totals(table: str, project_id: str) -> dict:
    """Query aggregated totals from a rollup table."""
    query = f"""
    SELECT
        sum(request_count) as request_count,
        sum(success_count) as success_count,
        sum(error_count) as error_count,
        sum(cached_count) as cached_count,
        sum(total_input_tokens) as total_input_tokens,
        sum(total_output_tokens) as total_output_tokens,
        sum(total_cost) as total_cost,
        sum(sum_response_time_ms) as sum_response_time_ms,
        sum(sum_ttft_ms) as sum_ttft_ms,
        uniqMerge(unique_inferences) as unique_inferences
    FROM {DATABASE}.{table}
    WHERE project_id = '{project_id}'
    FORMAT JSONEachRow
    """
    result = execute_query(query)
    if not result:
        return {}
    return json.loads(result)


def query_rollup_by_success_geo(table: str, project_id: str, is_success: bool, country_code: str | None) -> dict:
    """Query aggregated values for a specific dimension group."""
    country_filter = f"country_code = '{country_code}'" if country_code else "country_code IS NULL"
    query = f"""
    SELECT
        sum(request_count) as request_count,
        sum(success_count) as success_count,
        sum(error_count) as error_count,
        sum(cached_count) as cached_count,
        sum(total_input_tokens) as total_input_tokens,
        sum(total_output_tokens) as total_output_tokens,
        sum(total_cost) as total_cost,
        sum(sum_response_time_ms) as sum_response_time_ms,
        sum(sum_ttft_ms) as sum_ttft_ms
    FROM {DATABASE}.{table}
    WHERE project_id = '{project_id}'
      AND is_success = {str(is_success).lower()}
      AND {country_filter}
    FORMAT JSONEachRow
    """
    result = execute_query(query)
    if not result:
        return {}
    return json.loads(result)


def seed_data(data_keys: list[str]) -> dict:
    """Seed specific data keys to ClickHouse."""
    from tests.observability.seed_otel_traces import seed_otel_traces

    return seed_otel_traces(data_keys=data_keys, database=DATABASE, container=CONTAINER)


def clear_tables():
    """Clear all test tables."""
    tables = [
        "otel_traces",
        "InferenceFact",
        "InferenceMetrics5m",
        "InferenceMetrics1h",
        "InferenceMetrics1d",
    ]
    for table in tables:
        try:
            execute_query(f"TRUNCATE TABLE {DATABASE}.{table}")
        except RuntimeError:
            pass  # Table might not exist


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Clear tables before each test."""
    clear_tables()
    yield


class TestRollupMetrics5m:
    """Test InferenceMetrics5m aggregation from InferenceFact."""

    @pytest.mark.integration
    def test_request_counts_match_ground_truth(self):
        """Verify request counts aggregate correctly."""
        result = seed_data(["data_1", "data_4", "data_6"])
        assert result.get("success"), f"Seed failed: {result}"

        actual = query_rollup_totals("InferenceMetrics5m", PROJECT_ID)
        assert actual, "No data in InferenceMetrics5m"

        assert actual["request_count"] == EXPECTED_TOTALS["request_count"]
        assert actual["success_count"] == EXPECTED_TOTALS["success_count"]
        assert actual["error_count"] == EXPECTED_TOTALS["error_count"]
        assert actual["cached_count"] == EXPECTED_TOTALS["cached_count"]

    @pytest.mark.integration
    def test_token_totals_match_ground_truth(self):
        """Verify token totals aggregate correctly."""
        result = seed_data(["data_1", "data_4", "data_6"])
        assert result.get("success"), f"Seed failed: {result}"

        actual = query_rollup_totals("InferenceMetrics5m", PROJECT_ID)
        assert actual, "No data in InferenceMetrics5m"

        assert actual["total_input_tokens"] == EXPECTED_TOTALS["total_input_tokens"]
        assert actual["total_output_tokens"] == EXPECTED_TOTALS["total_output_tokens"]

    @pytest.mark.integration
    def test_cost_totals_match_ground_truth(self):
        """Verify cost totals aggregate correctly."""
        result = seed_data(["data_1", "data_4", "data_6"])
        assert result.get("success"), f"Seed failed: {result}"

        actual = query_rollup_totals("InferenceMetrics5m", PROJECT_ID)
        assert actual, "No data in InferenceMetrics5m"

        assert abs(actual["total_cost"] - EXPECTED_TOTALS["total_cost"]) < 0.0001

    @pytest.mark.integration
    def test_latency_sums_match_ground_truth(self):
        """Verify latency sums aggregate correctly."""
        result = seed_data(["data_1", "data_4", "data_6"])
        assert result.get("success"), f"Seed failed: {result}"

        actual = query_rollup_totals("InferenceMetrics5m", PROJECT_ID)
        assert actual, "No data in InferenceMetrics5m"

        assert actual["sum_response_time_ms"] == EXPECTED_TOTALS["sum_response_time_ms"]
        assert actual["sum_ttft_ms"] == EXPECTED_TOTALS["sum_ttft_ms"]

    @pytest.mark.integration
    def test_unique_inferences_count(self):
        """Verify unique inference count is correct."""
        result = seed_data(["data_1", "data_4", "data_6"])
        assert result.get("success"), f"Seed failed: {result}"

        actual = query_rollup_totals("InferenceMetrics5m", PROJECT_ID)
        assert actual, "No data in InferenceMetrics5m"

        assert actual["unique_inferences"] == EXPECTED_TOTALS["unique_inferences"]

    @pytest.mark.integration
    def test_dimension_group_success_no_geo(self):
        """Verify aggregation for is_success=True, country_code=NULL (data_1)."""
        result = seed_data(["data_1", "data_4", "data_6"])
        assert result.get("success"), f"Seed failed: {result}"

        actual = query_rollup_by_success_geo("InferenceMetrics5m", PROJECT_ID, True, None)
        assert actual, "No data for is_success=True, country_code=NULL"

        for field, expected in EXPECTED_SUCCESS_NO_GEO.items():
            if isinstance(expected, float):
                assert abs(actual[field] - expected) < 0.0001, f"{field}: expected {expected}, got {actual[field]}"
            else:
                assert actual[field] == expected, f"{field}: expected {expected}, got {actual[field]}"

    @pytest.mark.integration
    def test_dimension_group_success_us(self):
        """Verify aggregation for is_success=True, country_code='US' (data_6)."""
        result = seed_data(["data_1", "data_4", "data_6"])
        assert result.get("success"), f"Seed failed: {result}"

        actual = query_rollup_by_success_geo("InferenceMetrics5m", PROJECT_ID, True, "US")
        assert actual, "No data for is_success=True, country_code='US'"

        for field, expected in EXPECTED_SUCCESS_US.items():
            if isinstance(expected, float):
                assert abs(actual[field] - expected) < 0.0001, f"{field}: expected {expected}, got {actual[field]}"
            else:
                assert actual[field] == expected, f"{field}: expected {expected}, got {actual[field]}"

    @pytest.mark.integration
    def test_dimension_group_error(self):
        """Verify aggregation for is_success=False, country_code=NULL (data_4)."""
        result = seed_data(["data_1", "data_4", "data_6"])
        assert result.get("success"), f"Seed failed: {result}"

        actual = query_rollup_by_success_geo("InferenceMetrics5m", PROJECT_ID, False, None)
        assert actual, "No data for is_success=False, country_code=NULL"

        for field, expected in EXPECTED_ERROR_NO_GEO.items():
            if isinstance(expected, float):
                assert abs(actual[field] - expected) < 0.0001, f"{field}: expected {expected}, got {actual[field]}"
            else:
                assert actual[field] == expected, f"{field}: expected {expected}, got {actual[field]}"


class TestRollupMetrics1h:
    """Test InferenceMetrics1h cascading aggregation from 5m."""

    @pytest.mark.integration
    def test_cascading_aggregation_totals(self):
        """Verify 1h table has same totals as 5m (cascading MV)."""
        result = seed_data(["data_1", "data_4", "data_6"])
        assert result.get("success"), f"Seed failed: {result}"

        actual = query_rollup_totals("InferenceMetrics1h", PROJECT_ID)
        assert actual, "No data in InferenceMetrics1h"

        assert actual["request_count"] == EXPECTED_TOTALS["request_count"]
        assert actual["success_count"] == EXPECTED_TOTALS["success_count"]
        assert actual["total_input_tokens"] == EXPECTED_TOTALS["total_input_tokens"]
        assert actual["total_output_tokens"] == EXPECTED_TOTALS["total_output_tokens"]
        assert actual["unique_inferences"] == EXPECTED_TOTALS["unique_inferences"]


class TestRollupMetrics1d:
    """Test InferenceMetrics1d cascading aggregation from 1h."""

    @pytest.mark.integration
    def test_daily_totals_correct(self):
        """Verify 1d table has same totals as other tables."""
        result = seed_data(["data_1", "data_4", "data_6"])
        assert result.get("success"), f"Seed failed: {result}"

        actual = query_rollup_totals("InferenceMetrics1d", PROJECT_ID)
        assert actual, "No data in InferenceMetrics1d"

        assert actual["request_count"] == EXPECTED_TOTALS["request_count"]
        assert actual["success_count"] == EXPECTED_TOTALS["success_count"]
        assert actual["total_input_tokens"] == EXPECTED_TOTALS["total_input_tokens"]
        assert actual["total_output_tokens"] == EXPECTED_TOTALS["total_output_tokens"]
        assert actual["unique_inferences"] == EXPECTED_TOTALS["unique_inferences"]


@pytest.mark.integration
@pytest.mark.parametrize(
    "table_name",
    ["InferenceMetrics5m", "InferenceMetrics1h", "InferenceMetrics1d"],
)
def test_all_rollup_tables_consistent_totals(table_name):
    """Parametrized test validating all rollup tables have consistent totals."""
    clear_tables()

    result = seed_data(["data_1", "data_4", "data_6"])
    assert result.get("success"), f"Seed failed: {result}"

    actual = query_rollup_totals(table_name, PROJECT_ID)
    assert actual, f"No data in {table_name}"

    # All tables should have identical totals
    assert actual["request_count"] == EXPECTED_TOTALS["request_count"], (
        f"{table_name}: request_count mismatch"
    )
    assert actual["success_count"] == EXPECTED_TOTALS["success_count"], (
        f"{table_name}: success_count mismatch"
    )
    assert actual["error_count"] == EXPECTED_TOTALS["error_count"], (
        f"{table_name}: error_count mismatch"
    )
    assert actual["total_input_tokens"] == EXPECTED_TOTALS["total_input_tokens"], (
        f"{table_name}: total_input_tokens mismatch"
    )
    assert actual["total_output_tokens"] == EXPECTED_TOTALS["total_output_tokens"], (
        f"{table_name}: total_output_tokens mismatch"
    )
    assert actual["unique_inferences"] == EXPECTED_TOTALS["unique_inferences"], (
        f"{table_name}: unique_inferences mismatch"
    )
